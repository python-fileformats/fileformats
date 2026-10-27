import errno
import functools
import hashlib
import inspect
import itertools
import logging
import operator
import os
import shutil
import struct
import sys
import tempfile
import typing as ty
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import copy
from enum import Enum, IntEnum
from operator import itemgetter
from pathlib import Path
from warnings import warn

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

from fileformats.core.converter_helpers import SubtypeVar
from fileformats.core.typing import Self
from fileformats.core.utils import _excluded_subpackages

from .classifier import Classifier
from .convertible import ConvertibleToMarker
from .datatype import DataType
from .decorators import VALIDATED_PROPERTY_FLAG, classproperty, mtime_cached_property
from .exceptions import (
    FileFormatsExtrasError,
    FileFormatsExtrasPkgNotCheckedError,
    FileFormatsExtrasPkgUninstalledError,
    FileFormatsNotRelativePathError,
    FormatConversionError,
    FormatDefinitionError,
    FormatMismatchError,
    UnconstrainedExtensionException,
    UnsatisfiableCopyModeError,
)
from .extras import extra
from .fs_mount_identifier import FsMountIdentifier
from .identification import IANA_MIME_TYPE_REGISTRIES, formats_by_mime_format_name
from .loaded import Loaded, check_loaded
from .mock import MockMixin
from .sampling import SampleFileGenerator
from .typing import CryptoMethod, FspathsInputType, PathType
from .utils import add_exc_note, fspaths_converter, import_extras_module

if ty.TYPE_CHECKING:
    from .converter_helpers import Converter


class SupportsDunderLT(ty.Protocol):
    def __lt__(self, other: ty.Any) -> bool: ...


class SupportsDunderGT(ty.Protocol):
    def __gt__(self, other: ty.Any) -> bool: ...


def specificity_sort_key(datatype: ty.Type[DataType]) -> ty.Tuple[int, str]:
    """Key to sort types from the most to the least specific, and then by their name.
    A class always has more classes in its MRO than any of its base classes, so
    subclasses are always sorted before their base classes"""
    return (-len(inspect.getmro(datatype)), datatype.__name__)


FileSetPrimitive: TypeAlias = ty.Union[os.PathLike[str], ty.Sequence[os.PathLike[str]]]


FILE_CHUNK_LEN_DEFAULT = 8192
# Filesets with fewer files than this are hashed serially, as the overhead of starting
# a thread pool outweighs any gains
MIN_FILES_FOR_THREADED_HASHING = 3


logger = logging.getLogger("fileformats")

T = ty.TypeVar("T")


class FileSetMetadata(ty.MutableMapping[str, ty.Any]):
    """A dict-like, writable view of a :class:`FileSet`'s metadata.

    It layers two sources:

    * an in-memory **overlay** of values set directly on the object - either via
      ``fileset.metadata[key] = value`` or the ``metadata=`` argument to
      ``FileSet(...)`` - and
    * the metadata **loaded** from the file(s) by the ``read_metadata`` extra hook.

    Overlay entries take precedence over loaded entries with the same key. The loaded
    layer is cached and re-read when the file mtimes change (see
    ``FileSet._loaded_metadata``); the overlay is kept separately from that cache, so
    values set on the object are not lost when the loaded layer is invalidated. When
    the ``FileSet`` was constructed with an explicit ``metadata=`` mapping the file is
    not read at all and only the overlay is exposed.
    """

    def __init__(
        self,
        fileset: "FileSet",
        overlay: ty.Optional[ty.Mapping[str, ty.Any]] = None,
        read_disabled: bool = False,
    ) -> None:
        self._fileset = fileset
        self._overlay: ty.Dict[str, ty.Any] = dict(overlay) if overlay else {}
        self._read_disabled = read_disabled

    @property
    def _loaded(self) -> ty.Mapping[str, ty.Any]:
        if self._read_disabled:
            return {}
        loaded: ty.Mapping[str, ty.Any] = self._fileset._loaded_metadata
        return loaded

    def __getitem__(self, key: str) -> ty.Any:
        try:
            return self._overlay[key]
        except KeyError:
            return self._loaded[key]

    def __setitem__(self, key: str, value: ty.Any) -> None:
        self._overlay[key] = value

    def __delitem__(self, key: str) -> None:
        del self._overlay[key]

    def __iter__(self) -> ty.Iterator[str]:
        yield from self._overlay
        for key in self._loaded:
            if key not in self._overlay:
                yield key

    def __len__(self) -> int:
        return len(self._overlay.keys() | self._loaded.keys())

    def __contains__(self, key: object) -> bool:
        return key in self._overlay or key in self._loaded

    def __repr__(self) -> str:
        loaded = "read-disabled" if self._read_disabled else "lazy"
        return f"{type(self).__name__}(overlay={self._overlay!r}, loaded=<{loaded}>)"

    def as_dict(self) -> ty.Dict[str, ty.Any]:
        """A plain ``dict`` snapshot with the overlay merged over the loaded metadata."""
        merged: ty.Dict[str, ty.Any] = dict(self._loaded)
        merged.update(self._overlay)
        return merged


def _check_load_result(
    load: ty.Callable[..., ty.Any],
    fileset: "FileSet",
    **kwargs: ty.Any,
) -> ty.Any:
    """Check that the data returned by the `load` implementation is of the
    `loaded_type` of the fileset"""
    data = load(fileset, **kwargs)
    try:
        check_loaded(type(fileset), data)
    except TypeError as e:
        impl = load.dispatch(type(fileset))  # type: ignore[attr-defined]
        add_exc_note(
            e,
            f"Returned by the {impl.__module__}.{impl.__qualname__} implementation of "
            f"'load', which is a bug in that implementation (or in the `loaded_type` "
            f"of {type(fileset).type_name}), please report it to the package maintainers",
        )
        raise
    return data


def _check_save_data(
    save: ty.Callable[..., None],
    fileset: "FileSet",
    data: ty.Any,
    **kwargs: ty.Any,
) -> None:
    """Check that `data` is of the `loaded_type` of the fileset before saving it"""
    check_loaded(type(fileset), data)
    save(fileset, data, **kwargs)


class FileSet(DataType):
    """
    The base class for all format types within the fileformats package. A generic
    representation of a collection of files related to a single data resource. A
    file-set can be a single file or directory or a collection thereof, such as a
    primary file with a "side-car" header.

    Parameters
    ----------
    *fspaths : Path | str | FileSet | Collection[Path | str | FileSet]
        a set of file-system paths pointing to all the resources in the file-set
    metadata : dict[str, Any] | None
        metadata associated with the file-set, typically lazily loaded via `read_metadata`
        extra hook but can be provided directly at the time of instantiation. Providing it
        here also suppresses reading from the file(s); further entries can still be added
        via ``fileset.metadata[key] = value``.
    read_metadata : bool
        whether the file(s) may be read (lazily, via the `read_metadata` extra) to
        populate ``metadata``. Pass ``False`` to start from an empty, in-memory-only
        metadata mapping that is still writable via ``fileset.metadata[key] = value``.
    **load_kwargs : ty.Any
        Any keyword arguments to be passed through to `read_metadata` and `load`
        implementations when loading metadata and data to fill the `metadata` and `contents`
        properties respectively.
    """

    # Class attributes

    # differentiate between Field and other DataType classes
    is_fileset = True

    # File extensions associated with file format
    ext: ty.Optional[str] = None
    alternate_exts: ty.Tuple[ty.Optional[str], ...] = ()

    # to be overridden in subclasses
    # Explicitly set the Internet Assigned Numbers Authority (https://iana_mime.org) MIME
    # type to None for any base classes that should not correspond to a MIME or MIME-like
    # type.
    iana_mime = ""

    # The type of the object returned by `load` (and accepted by `save`) for the
    # `Loaded[Format]` annotation, either a type or a dotted-path string (e.g.
    # "pydicom.FileDataset") for types from optional dependencies
    loaded_type: ty.ClassVar[ty.Any] = ty.Any

    # Member attributes
    fspaths: ty.FrozenSet[Path]
    _explicit_metadata: ty.Optional[ty.Mapping[str, ty.Any]]
    _load_kwargs: ty.Dict[str, ty.Any]

    def __init__(
        self,
        *fspaths: FspathsInputType,
        metadata: ty.Optional[ty.Dict[str, ty.Any]] = None,
        **load_kwargs: ty.Any,
    ):
        self._explicit_metadata = metadata
        self._load_kwargs = load_kwargs
        self._validate_class()
        self.fspaths = frozenset(
            itertools.chain(*(fspaths_converter(p) for p in fspaths))
        )
        self._validate_fspaths()
        self._additional_fspaths()
        if metadata is not None and not isinstance(metadata, dict):
            raise TypeError(
                f"FileSet metadata value needs to be None or dict, not {metadata} ({self})"
            )
        # The file(s) are not read for metadata when ``read_metadata=False`` is passed
        # or when an explicit ``metadata=`` mapping is given; in either case values can
        # still be added/overridden later via ``fileset.metadata[key] = value`` (see
        # ``FileSetMetadata``).
        self._metadata = FileSetMetadata(
            self,
            overlay=metadata,
        )
        self._validate_properties()

    def _validate_fspaths(self) -> None:
        if not self.fspaths:
            raise ValueError(f"No file-system paths provided to {type(self)}")
        missing = [p for p in self.fspaths if not p or not p.exists()]
        if missing:
            missing_str = "\n".join(str(p) for p in missing)
            msg = (
                f"The following file system paths provided to {type(self)} do not "
                f"exist:\n\n{missing_str}\n\n"
            )
            present_parents = set()
            for fspath in missing:
                if fspath and fspath.parent.exists():
                    present_parents.add(fspath.parent)
            for parent in present_parents:
                msg += f"\n\nFiles in the present parent directory '{parent!s}' are:\n"
                msg += "\n".join(str(p) for p in parent.iterdir())
            raise FileNotFoundError(msg)

    def _validate_class(self) -> ty.Union[bool, None]:
        """Check that the class has been correctly defined"""
        if self._valid_class:
            return True
        type(self)._valid_class = True
        module_name = type(self).__module__
        if (
            not module_name.startswith("fileformats")
            and not isinstance(self, MockMixin)
            and "test" not in module_name
        ):
            raise FormatDefinitionError(
                f"FileSet class {type(self).__name__} should be defined in the "
                f"fileformats namespace not {module_name} unless it is in a test module"
            )
        return None  # Continue with subclass validation

    def _additional_fspaths(self) -> None:
        """Additional checks to be performed on the file-system paths provided to the"""

    def _validate_properties(self) -> None:
        # Check required properties don't raise errors
        for prop_name in self.validated_properties():
            getattr(self, prop_name)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, FileSet)
            and type(self) is type(other)
            and self.fspaths == other.fspaths
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        tp = type(self)
        return hash((tp.__module__, tp.__name__, self.fspaths))

    def __repr__(self) -> str:
        return f"{self.type_name}('" + "', '".join(str(p) for p in self.fspaths) + "')"

    @extra(wrapper=_check_load_result)
    def load(self, **kwargs: ty.Any) -> Loaded[Self]:
        """Load the contents of the file into an object of type that make sense for the
        datat type

        Parameters
        ----------
        **kwargs : Any
            any format-specific keyword arguments to pass to the loader

        Returns
        -------
        Loaded[Self]
            the data loaded from the file, of type `loaded_type`

        Raises
        ------
        TypeError
            if the implementation returns data that isn't of the format's `loaded_type`
        """
        raise NotImplementedError

    @extra(wrapper=_check_save_data)
    def save(self, data: Loaded[Self], **kwargs: ty.Any) -> None:
        """Save new contents from a format-specific object

        Parameters
        ----------
        data: Loaded[Self]
            the data to be saved to the file, of type `loaded_type` (i.e. matching the
            one returned by the `load` method)
        **kwargs : Any
            any format-specific keyword arguments to pass to the saver

        Raises
        ------
        TypeError
            if `data` isn't an instance of the format's `loaded_type`
        """
        raise NotImplementedError

    @classmethod
    def new(
        cls, fspath: ty.Union[str, Path], data: Loaded[Self], **kwargs: ty.Any
    ) -> Self:
        """Create a new file-set object with the given data saved to the file

        Parameters
        ----------
        fspath: str | Path
            the file-system path to save the data to. Additional paths should be
            able to be inferred from this path
        data: Loaded[Self]
            the data to be saved to the file, of type `loaded_type` (i.e. matching the
            one returned by the `load` method)
        **kwargs : Any
            any format-specific keyword arguments to pass to the saver

        Returns
        -------
        FileSet
            a new file-set object with the given data saved to the file
        """
        # We have to use a mock object as the data file hasn't been written yet so can't
        # be validated
        mock = cls.mock(fspath)
        mock.save(data, **kwargs)
        return cls(fspath)

    @property
    def parent(self) -> Path:
        "A common parent directory for all the top-level paths in the file-set"
        return Path(os.path.commonpath([p.parent for p in self.fspaths]))

    @property
    def parents(self) -> ty.Sequence[Path]:
        return [self.parent] + list(self.parent.parents)

    @property
    def relative_fspaths(self) -> ty.Iterator[Path]:
        "Paths for all top-level paths in the file-set relative to the common parent directory"
        return (p.relative_to(self.parent) for p in self.fspaths)

    @property
    def mtimes(self) -> ty.Tuple[ty.Tuple[str, int], ...]:
        """Modification times of all fspaths in the file-set

        Returns
        -------
        tuple[tuple[str, int], ...]
            a tuple of tuples containing the file paths and the modification time (ns)
            sorted by the file path
        """
        return tuple((str(p), p.stat().st_mtime_ns) for p in sorted(self.fspaths))

    @property
    def last_modified(self) -> int:
        """The latest modification time of all files in the set"""
        return max(m for _, m in self.mtimes)

    @classproperty  # type: ignore[arg-type]
    def mime_type(cls) -> str:
        """Generates a MIME type (IANA) identifier from a format class. If an official
        IANA MIME type doesn't exist it will create one in the in the MIME style, e.g.

            fileformats.text.Plain to "text/plain"

            fileformats.image.TiffFx to "image/tiff-fx"

            fileformats.mynamespace.MyFormat to "application/x-my-format

        Returns
        -------
        str
            the MIME type corresponding to the class
        """
        mime_type = cls.__dict__.get("iana_mime", "")
        assert isinstance(mime_type, str)
        if mime_type:
            return mime_type
        format_name = cls._mime_format_name()
        return f"application/x-{format_name}"

    @classproperty  # type: ignore[arg-type]
    def strext(cls) -> str:
        """Return extension that is guaranteed to be a string (i.e. not None)"""
        return cls.ext if cls.ext is not None else ""

    @classproperty  # type: ignore[arg-type]
    def unconstrained(cls) -> bool:
        """Whether the file-format is unconstrained by extension, magic number or another
        constraint"""
        return not list(cls.validated_properties())

    @classproperty  # type: ignore[arg-type]
    def possible_exts(cls) -> ty.List[ty.Optional[str]]:
        """All possible extensions of the file format"""
        possible = [cls.ext]
        try:
            possible.extend(cls.alternate_exts)
        except AttributeError:
            pass
        return possible

    @mtime_cached_property
    def _loaded_metadata(self) -> ty.Mapping[str, ty.Any]:
        """Metadata read from the file(s) via the ``read_metadata`` extra, cached until
        the file mtimes change. Returns an empty mapping when no reader is available."""
        try:
            metadata = self.read_metadata(**self._load_kwargs)
        except FileFormatsExtrasPkgUninstalledError:
            raise
        except FileFormatsExtrasPkgNotCheckedError as e:
            logger.warning(str(e))
            metadata = {}
        except FileFormatsExtrasError:
            metadata = {}
        return metadata

    @property
    def metadata(self) -> "FileSetMetadata":
        """A dict-like, writable view of the file-set's metadata (see
        :class:`FileSetMetadata`).

        Reading falls back from an in-memory overlay to the metadata loaded lazily from
        the file(s) via the ``read_metadata`` extra. Values assigned via
        ``fileset.metadata[key] = value`` are stored in the overlay: they take
        precedence over the loaded metadata and persist even when the loaded layer is
        re-read after the file(s) change."""
        try:
            return self._metadata
        except AttributeError:  # e.g. instance created without calling __init__
            self._metadata = FileSetMetadata(self)
            return self._metadata

    @mtime_cached_property
    def contents(self) -> ty.Any:
        """The contents of the file-set, will be an object of a type that makes sense
        for the format, as loaded by the `load` method"""
        return self.load()

    @extra
    def read_metadata(self, **kwargs: ty.Any) -> ty.Mapping[str, ty.Any]:
        """Reads any metadata associated with the fileset and returns it as a dict

        Parameters
        ----------
        **kwargs : Any
            any format-specific keyword arguments to pass to the metadata reader

        Returns
        -------
        metadata : Mapping[str, Any]
            a mapping from names of the metadata fields to their values
        """
        raise NotImplementedError

    @classmethod
    def validated_properties(cls) -> ty.Tuple[str, ...]:
        """Find all properties required to treat file-set as being in the format specified
        by the class

        Returns
        -------
        tuple[str, ...]
            a tuple containing all the properties names defined outside of core and
            generic classes
        """
        if required_props := cls.__dict__.get("_required_props"):
            assert isinstance(required_props, tuple) and all(
                isinstance(p, str) for p in required_props
            )
            return required_props  # return cached value
        fileset_props = dir(FileSet)
        required_props = []
        for attr_name in dir(cls):
            if attr_name in fileset_props:
                continue
            attr = getattr(cls, attr_name)
            if isinstance(attr, property):
                try:
                    attr.fget.__annotations__[VALIDATED_PROPERTY_FLAG]
                except KeyError:
                    pass
                else:
                    required_props.append(attr_name)
        return tuple(required_props)

    def required_paths(self) -> ty.FrozenSet[Path]:
        """Returns all fspaths that are required for the format"""
        required = set()
        for prop_name in self.validated_properties():
            prop = getattr(self, prop_name)
            paths = []
            if hasattr(prop, "required_paths"):
                try:
                    paths = prop.required_paths()
                except RecursionError:
                    warn(
                        f"Recursion error when trying to get required paths from {prop_name} "
                        f"property of {type(self)}"
                    )
                    raise
            elif isinstance(prop, os.PathLike):
                paths = [Path(prop)]
            elif isinstance(prop, ty.Iterable):
                for p in prop:
                    if isinstance(p, os.PathLike):
                        paths.append(Path(p))
            for path in paths:
                if path in self.fspaths:
                    required.add(path)
        return frozenset(required)

    def nested_filesets(self, recursive: bool = True) -> ty.List["FileSet"]:
        """Returns all nested filesets that are required for the format, i.e. those
        returned by its validated properties, including those within dicts and
        sequences returned by them

        Parameters
        ----------
        recursive : bool, optional
            whether to also include the filesets nested within the nested filesets, by
            default True

        Returns
        ------
        fileset : list[FileSet]
            a fileset that is nested within the broader fileset
        """
        nested: ty.List[FileSet] = []

        def collect(value: ty.Any) -> None:
            if isinstance(value, FileSet):
                nested.append(value)
                if recursive:
                    nested.extend(value.nested_filesets())
            elif isinstance(value, ty.Mapping):
                for v in value.values():
                    collect(v)
            elif isinstance(value, (list, tuple, set, frozenset)):
                for v in value:
                    collect(v)

        for prop_name in sorted(self.validated_properties()):
            collect(getattr(self, prop_name))
        return nested

    def map_nested(
        self,
        out_dir: "os.PathLike[str] | str",
        func: ty.Callable[["FileSet", Path], ty.Optional["FileSet"]],
    ) -> Self:
        """Writes a copy of the fileset to `out_dir`, in which the filesets nested
        directly within it (see `nested_filesets`) are written by `func` and its
        remaining files are copied unchanged, keeping the same layout relative to their
        common parent directory. For example, to write converted or otherwise modified
        versions of the nested filesets.

        Nested filesets that point outside of the fileset (i.e. aren't made up of its
        paths) aren't part of it, so are left out of the copy, as they are by `copy`

        Parameters
        ----------
        out_dir : PathLike[str] | str
            the directory to write the copy to
        func : Callable[[FileSet, Path], FileSet | None]
            called with each nested fileset and the directory it should be written to,
            to be in the same position relative to the copy as the nested fileset is
            to this fileset. It should write its counterpart there with the same
            layout (e.g. names, so that the copy is still of this fileset's type) and
            return it, or return None to have the nested fileset copied unchanged along
            with the rest of the files. Nested filesets that are entirely within ones
            already written by `func` aren't passed to it.

        Returns
        -------
        Self
            the copy of the fileset

        Raises
        ------
        ValueError
            if a nested fileset is made up of paths both within and outside the fileset
        """
        out_dir = Path(out_dir)
        src_root = _root_dir(self)
        own_paths = set(self.all_file_paths())
        written: ty.Set[Path] = set()
        for nested in self.nested_filesets(recursive=False):
            nested_paths = set(nested.all_file_paths())
            if outside := sorted(nested_paths - own_paths):
                if outside == sorted(nested_paths):
                    continue  # not part of the fileset
                raise ValueError(
                    f"{nested} is nested within {self}, but is made up of paths both "
                    f"within it and outside it, {outside}"
                )
            if nested_paths <= written:
                continue
            dest_dir = out_dir / _root_dir(nested).relative_to(src_root)
            if func(nested, dest_dir) is not None:
                written.update(nested_paths)
        for path in own_paths - written:
            dest = out_dir / path.relative_to(src_root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        # Reinstantiating the type checks that `func` preserved the layout it requires
        # (e.g. didn't rename files it looks for)
        return type(self)([out_dir / p.relative_to(src_root) for p in self.fspaths])

    def trim_paths(self) -> Self:
        """Trims paths in fspaths to only those that are "required" by the format class
        i.e. returned by a required property"""
        self.fspaths = fspaths_converter(self.required_paths())
        return self

    def select_by_ext(self, fileformat: ty.Optional[ty.Type["FileSet"]] = None) -> Path:
        """Selects a single path from a set of file-system paths based on the file
        extension

        Parameters
        ----------
        fileformat : type
            the format class of the path to select

        Returns
        -------
        Path
            the selected file-system path that matches the extension

        Raises
        ------
        FormatMismatchError
            if more than one paths matches the extension
        """
        if fileformat is None:
            fileformat = type(self)
        exts = [fileformat.ext]
        try:
            exts.extend(fileformat.alternate_exts)
        except AttributeError:
            pass
        matches = self.matching_exts(self.fspaths, exts)
        if not matches:
            paths_str = ", ".join(str(p) for p in self.fspaths)
            raise FormatMismatchError(
                f"No matching files with extensions in {exts} in file set {paths_str}"
            )
        elif len(matches) > 1:
            matches_str = ", ".join(str(p) for p in matches)
            raise FormatMismatchError(
                f"Multiple files with {exts} extensions found in : {matches_str}"
            )
        return matches[0]

    @classmethod
    def matching_exts(
        cls,
        fspaths: ty.Collection[Path],
        exts: ty.Optional[ty.List[ty.Optional[str]]] = None,
    ) -> ty.List[Path]:
        """Returns the paths out of the candidates provided that matches the
        given extension (by default the extension of the class)

        Parameters
        ----------
        fspaths: list[Path]
            The paths to select from
        ext: list[str], optional
            the extensions to match, by default the primary and alternate extensions of
            the class

        Returns
        -------
        list[Path]
            the matching paths

        Raises
        ------
        FileFormatError
            When no paths match or more than one path matches the given extension"""
        if isinstance(fspaths, (str, Path)):
            fspaths = [fspaths]
        if exts is None:
            if cls.ext is None:
                return list(fspaths)
            exts = cls.possible_exts
        return [
            p for p in fspaths if any(e is None or str(p).endswith(e) for e in exts)
        ]

    @classmethod
    def convert(
        cls,
        fileset: "FileSet",
        **kwargs: ty.Any,
    ) -> Self:
        """Convert a given file-set into the format specified by the class

        Parameters
        ----------
        fileset : FileSet
            the file-set object to convert
        cache_root : Path, optional
            a directory to use for any temporary files created during the conversion,
            by default None which will use the default Pydra cache
        **kwargs
            args to pass to customise the converter task definition

        Returns
        -------
        FileSet
            the file-set converted into the type of the current class
        """
        import attrs

        # Make unique, yet somewhat recognisable task name
        converter = cls.get_converter(source_format=type(fileset))
        if converter is None:
            assert isinstance(fileset, cls)
            return copy(fileset)
        if converter.is_chain:
            from .converter_chain import assign_kwargs

            # Check the kwargs can be assigned to the converters in the chain before
            # running the workflow, where they are applied
            assign_kwargs(converter.task.chain, kwargs)
            kwargs = {"converter_kwargs": kwargs} if kwargs else {}
        kwargs[converter.in_file] = fileset
        task = attrs.evolve(converter.task, **kwargs)
        # We need to use a fresh cache root each time to avoid picking up previous
        # conversions that no longer exist
        outputs = task(cache_root=tempfile.mkdtemp())  # type: ignore[call-arg]
        out_file = getattr(outputs, converter.out_file)
        if not isinstance(out_file, cls):
            out_file = cls(out_file)
        return out_file  # type: ignore

    @classmethod
    def get_converter(
        cls,
        source_format: ty.Type[DataType],
        allow_chains: bool = True,
    ) -> "ty.Optional[Converter]":
        """Get a converter that converts from the source format type
        into the format specified by the class

        Parameters
        ----------
        source_format : type
            the format to convert from
        allow_chains : bool, optional
            whether to chain converters together to convert via intermediate formats
            if there is no direct converter available, by default True

        Returns
        -------
        pydra.spec.TaskDef | None
            a pydra task definition to perform the conversion, or None if no
            conversion is required

        Raises
        ------
        FileFormatConversionError
            no converters found between source and dest format
        FileFormatConversionError
            ambiguous (i.e. more than one) converters found between source and dest format
        """
        if issubclass(source_format, cls):
            return None
        # import extras modules
        source_format._import_extras_module()  # type: ignore[attr-defined]

        def find_direct(target: type[FileSet]) -> "Converter | None":
            """Find a converter directly from the source format to the given target"""
            # trigger loading of standard converters for target format
            converters = target.get_converters_dict()
            target._import_extras_module()
            try:
                return converters[source_format]
            except KeyError:
                pass
            # If no direct mapping check for mapping from source super types and wildcard
            # matches
            available_converters = target.get_converter_defs(source_format)
            if len(available_converters) > 1:
                # FIXME: Hack to avoid situation where multiple converters get added but are identical
                if all(a == available_converters[0] for a in available_converters[1:]):
                    available_converters = [available_converters[0]]
                else:
                    available_str = "\n".join(str(a.task) for a in available_converters)
                    raise FormatConversionError(
                        f"Ambiguous converters found between '{target.mime_like}' and "
                        f"'{source_format.mime_like}':\n{available_str}"
                    ) from None
            if not available_converters:
                return None
            converter = available_converters[0]
            # Store mapping for future reference
            converters[source_format] = converter
            return converter

        converter = find_direct(cls)
        if converter is not None and (allow_chains or not converter.is_chain):
            return converter
        # If there is no direct converter, search back from the target format through
        # the formats that can be converted into it (breadth-first, so the shortest
        # chains are found) until one is found that the source format can be converted
        # into directly
        chains: list[list[Converter]] = []
        visited: set[type] = {cls, source_format}
        # Formats to search from, along with the chain of converters from them to the
        # target format
        level: list[tuple[type[FileSet], list[Converter]]] = [(cls, [])]
        while allow_chains and level and not chains:
            next_level = []
            for target, downstream in level:
                for intermediate, conv in list(target.get_converters_dict().items()):
                    # Skip converters with wildcards, as the intermediate format they
                    # convert from isn't fully defined, previously cached chains, and
                    # formats already searched to avoid circular conversions
                    if (
                        conv.classifiers
                        or conv.is_chain
                        or not (
                            inspect.isclass(intermediate)
                            and issubclass(intermediate, FileSet)
                        )
                        or intermediate in visited
                    ):
                        continue
                    chain = [conv] + downstream
                    first = find_direct(intermediate)
                    if first is None:
                        next_level.append((intermediate, chain))
                    elif first.is_chain:
                        # Flatten previously cached chains
                        chains.append(list(first.task.chain) + chain)
                    else:
                        chains.append([first] + chain)
            # Mark visited only after the whole level has been searched so that all
            # alternative chains of the same length are found
            visited.update(f for f, _ in next_level)
            level = next_level
        if not chains:
            msg = (
                f"Could not find converter between '{source_format.mime_like}' and "
                f"'{cls.mime_like}' formats"
            )
            extras_mod = import_extras_module(cls)
            if not extras_mod.imported:
                msg += (
                    f'. Was not able to import "extras" module, {extras_mod.pkg}, '
                    f"you may want to try installing the '{extras_mod.pypi}' package "
                    f"from PyPI (e.g. pip install {extras_mod.pypi}) or check it isn't broken"
                )
            raise FormatConversionError(msg)

        from .converter_chain import ConverterChain
        from .converter_helpers import Converter

        def chain_sort_key(chain: list[Converter]) -> tuple[int, int, list[str]]:
            """Favour shorter chains, then those with fewer templated (i.e. wildcard
            or generic) converters, then alphabetical order of converter names"""
            num_templated = sum(
                bool(c.classifiers)
                or any(c is t for t in SubtypeVar.converters.values())
                for c in chain
            )
            return (len(chain), num_templated, [type(c.task).__name__ for c in chain])

        converter = Converter(ConverterChain(chain=min(chains, key=chain_sort_key)))
        # Store mapping for future reference
        cls.get_converters_dict()[source_format] = converter
        return converter

    @classmethod
    def _import_extras_module(cls) -> None:
        try:
            unclassified = cls.unclassified  # type: ignore
        except AttributeError:
            import_extras_module(cls)
        else:
            import_extras_module(unclassified)

    @classmethod
    def get_converters_dict(
        cls, klass: ty.Optional[ty.Type[DataType]] = None
    ) -> ty.Dict[ty.Type[DataType], "Converter"]:
        # Only access converters to the specific class, not superclasses (which may not
        # be able to convert to the specific type)
        if klass is None:
            klass = cls
        # import related extras module for the target class
        import_extras_module(klass)
        converters_dict: ty.Dict[ty.Type[DataType], "Converter"]
        try:
            converters_dict = klass.__dict__["converters"]
        except KeyError:
            converters_dict = klass.converters = {}
        return converters_dict

    @classmethod
    def convertible_from(
        cls,
        union_sort_key: ty.Callable[
            [ty.Type[DataType]],
            ty.Union[SupportsDunderLT, SupportsDunderGT],
        ] = specificity_sort_key,
    ) -> ty.Any:
        """Union of types that can be converted to this type, including the current type
        (or just the current type if there are no other types that can be converted to
        it), annotated with the type it was created from so that it can be written to
        a MIME-like string as "<namespace>/<format>+convertible-to" instead of the
        union, i.e. ``Annotated[<union>, ConvertibleToMarker(cls)]``, which is what
        ``ConvertibleTo[cls]`` evaluates to

        Parameters
        ----------
        union_sort_key : callable[[DataType], Any], optional
            A function used to sort the union of types. Defaults to sorting from the
            most to the least specific type (i.e. subclasses before their base classes),
            so that the first type in the union that matches a file-set is the most
            specific one, and then by the type name.

        Returns
        -------
        Annotated[Type[DataType], ConvertibleToMarker]
            The annotated type or union of types that can be converted to this type.
        """

        datatypes: ty.List[ty.Type[DataType]] = [cls]
        cls._import_extras_module()
        if cls.namespace == "generic":
            subclasses = [cls]
        else:
            exclude_subpackages = copy(_excluded_subpackages)
            exclude_subpackages.discard(cls.namespace)
            subclasses = list(FileSet.subclasses(exclude=exclude_subpackages))
        for subcls in subclasses:
            if issubclass(subcls, cls):
                subcls._import_extras_module()
                # Skip the source types of generic converters (e.g. `SetOf[T]` for
                # `SetOf[T]` -> `DirectoryOf[T]`), which can't be used as concrete
                # datatypes, and are added below with their wildcards resolved from the
                # classifiers of this type where possible
                datatypes.extend(
                    t
                    for t in subcls.get_converters_dict().keys()
                    if not _has_wildcard_classifiers(t)
                )
        datatypes.extend(cls._resolved_wildcard_sources())
        marker = ConvertibleToMarker(cls)
        if len(datatypes) == 1:
            return ty.Annotated[cls, marker]
        concrete_datatypes = set()

        def add_concrete(datatype: ty.Type[DataType]) -> None:
            """Adds datatype to concrete_datatypes list if not abstract, otherwise adds all non-abstract subclasses"""
            if inspect.isabstract(datatype):
                for subclass in datatype.subclasses():
                    add_concrete(subclass)
            elif issubclass(datatype, SubtypeVar):
                concrete_datatypes.add(datatype.bound)
            else:
                concrete_datatypes.add(datatype)

        # Create list of non-abstract datatypes
        for datatype in datatypes:
            add_concrete(datatype)
        # TODO: Might want to sort datatypes in a more specific order
        union = functools.reduce(
            operator.or_, sorted(concrete_datatypes, key=union_sort_key)
        )
        return ty.Annotated[union, marker]

    @classmethod
    def _resolved_wildcard_sources(cls) -> ty.List[ty.Type[DataType]]:
        """The source types of the generic converters that can convert to this type,
        with their wildcard classifiers resolved from this type, e.g. `Zip[TextFile]`
        for `TextFile` (from `Zip[Compressed]` -> `Compressed`) and `SetOf[TextFile]`
        for `DirectoryOf[TextFile]` (from `SetOf[T]` -> `DirectoryOf[T]`). Only those
        that a converter can actually be found from with `get_converter` are returned.
        """
        from .converter_helpers import SubtypeVar

        if _has_wildcard_classifiers(cls):
            return []  # nothing to resolve the wildcards from
        # The extras modules of generically classifiable types (e.g. archives) register
        # generic converters to and from them for any type (e.g. `Zip[X]` -> `X`), so
        # import them, so the result doesn't depend on which happen to be imported
        for generic_type in set(DataType.generically_classifiable_by_name.values()):
            generic_type._import_extras_module()  # type: ignore[attr-defined]

        # The source types of generic converters, and the types their wildcards resolve
        # to for this type
        candidates: ty.List[
            ty.Tuple[ty.Type[DataType], ty.Dict[ty.Type[DataType], ty.Type[DataType]]]
        ] = []
        # Converters from generic types to the types they are classified by, e.g.
        # `Zip[Compressed]` -> `Compressed`
        for extracted_from in SubtypeVar.converters:
            (wildcard,) = extracted_from.wildcard_classifiers()  # type: ignore[attr-defined]
            if issubclass(cls, wildcard.bound):  # type: ignore[attr-defined]
                candidates.append((extracted_from, {wildcard: cls}))
        # Converters between generic types, or to a generic type, registered on the
        # unclassified type, e.g. `SetOf[T]` -> `DirectoryOf[T]` and
        # `Compressed` -> `Zip[Compressed]`, where the wildcard is resolved from the
        # classifier of this type in place of the target's wildcard
        if getattr(cls, "is_classified", False):
            converters_dict = FileSet.get_converters_dict(
                cls.unclassified  # type: ignore[attr-defined]
            )
            for source_template, generic_converter in converters_dict.items():
                if not generic_converter.classifiers:
                    continue  # not a generic converter
                wildcards = cls.wildcard_classifiers(  # type: ignore[attr-defined]
                    generic_converter.classifiers
                )
                non_wildcards = cls.non_wildcard_classifiers(  # type: ignore[attr-defined]
                    generic_converter.classifiers
                )
                actual = set(cls.classifiers).difference(  # type: ignore[attr-defined]
                    non_wildcards
                )
                if (
                    len(wildcards) != 1
                    or len(actual) != 1
                    or not non_wildcards.issubset(cls.classifiers)  # type: ignore[attr-defined]
                ):
                    continue
                candidates.append(
                    (source_template, {next(iter(wildcards)): next(iter(actual))})
                )
        resolved = []
        for unresolved, mapping in candidates:
            try:
                # Resolving the wildcards can produce an invalid type (e.g. one with
                # classifiers that clash), in which case there is nothing to add
                candidate = _resolve_wildcards(unresolved, mapping)
                if candidate is cls:
                    continue
                found = cls.get_converter(candidate)
            except (FormatConversionError, FormatDefinitionError):
                continue
            if found is not None:  # i.e. not just a subclass of this type
                resolved.append(candidate)
        return resolved

    @classmethod
    def get_converter_defs(cls, source_format: type) -> ty.List["Converter"]:
        """Search the registered converters to find any matches and return list of
        task and associated key-word args to perform the conversion between source and
        target formats

        Parameters
        ----------
        source_format : type(FileSet)
            the source format to convert from

        Returns
        -------
        available : list[tuple[TaskBase, dict[str, Any]]]
            list of available converters between the source and target formats
        """
        from .converter_helpers import SubtypeVar

        converters_dict = cls.get_converters_dict()
        available = []
        for src_frmt, converter in converters_dict.items():
            # Ignore converters with wildcards at this point
            if not converter.classifiers and issubclass(source_format, src_frmt):
                available.append(converter)
        if not available and hasattr(source_format, "unclassified"):
            available = SubtypeVar.get_converter_defs(source_format, target_format=cls)
        return available

    @classmethod
    def register_converter(
        cls,
        source_format: ty.Type["FileSet"],
        converter: "Converter",
    ) -> None:
        """Registers a converter task within a class attribute. Called by the
        @fileformats.core.converter decorator.

        Parameters
        ----------
        source_format : type
            the source format to register a converter from
        converter_spec
            a tuple consisting of a `task_spec` callable that resolves to a Pydra task
            and a dictionary of keyword arguments to be passed to the task spec at
            initialisation time

        Raises
        ------
        FormatConversionError
            if there is already a converter registered between the two types
        """
        converters_dict = cls.get_converters_dict()
        # If no converters are loaded, attempt to load from the standard location
        if source_format in converters_dict:
            prev_converter = cls.converters[source_format]
            # task, task_kwargs = converter_spec
            # prev_task, prev_kwargs = prev_tuple
            if converter.task == prev_converter.task:
                logger.warning(
                    "Ignoring duplicate registrations of the same converter %s",
                    converter.task,
                )
                return  # actually the same task but just imported twice for some reason
            raise FormatConversionError(
                f"Cannot register converter from {source_format.__name__} "
                f"to {cls.__name__}, {converter.task}, because there is already "
                f"one registered from {prev_converter.task}:"
                f"\n\n{converter.task}\n\n"
                f"and {prev_converter.task}\n\n"
            )
        converters_dict[source_format] = converter

    @classproperty  # type: ignore[arg-type]
    def all_formats(cls) -> ty.Set[ty.Type["FileSet"]]:
        """Iterate over all FileSet formats in fileformats.* namespaces"""
        if cls._all_formats is None:
            cls._all_formats = set(
                f
                for f in FileSet.subclasses()
                if (f.__dict__.get("iana_mime", True) and not inspect.isabstract(f))
            )
        return cls._all_formats

    @classproperty  # type: ignore[arg-type]
    def standard_formats(cls) -> ty.Iterable[ty.Type["FileSet"]]:
        """Iterate over all formats in the standard fileformats.* namespaces"""
        return (f for f in cls.all_formats if f.namespace in IANA_MIME_TYPE_REGISTRIES)

    @classproperty  # type: ignore[arg-type]
    def formats_by_iana_mime(cls) -> ty.Dict[str, ty.Type["FileSet"]]:
        """a dictionary containing all formats by their IANA MIME type (if applicable)"""
        if cls._formats_by_iana_mime is None:
            cls._formats_by_iana_mime = {
                f.iana_mime.lower(): f
                for f in FileSet.all_formats
                if f.__dict__.get("iana_mime", "")
            }
        return cls._formats_by_iana_mime

    @classproperty  # type: ignore[arg-type]
    def formats_by_name(cls) -> ty.Dict[str, ty.Set[ty.Type["FileSet"]]]:
        """a dictionary containing lists of formats by their translated class names,
        i.e. their can be more than one format with the same translated name"""
        if cls._formats_by_name is None:
            cls._formats_by_name = {
                k: set(v for _, v in g)
                for k, g in itertools.groupby(
                    sorted(
                        formats_by_mime_format_name(
                            f
                            for f in FileSet.all_formats
                            if not f.__dict__.get("iana_mime", "")
                        ),
                        key=itemgetter(0),
                    ),
                    key=itemgetter(0),
                )
            }
        return cls._formats_by_name

    def all_file_paths(
        self,
        ignore_hidden_files: bool = False,
        ignore_hidden_dirs: bool = False,
    ) -> ty.List[Path]:
        """Paths of all files within the fileset, including those nested within
        directories

        Parameters
        ----------
        ignore_hidden_files : bool
            whether to ignore hidden files within nested directories (i.e. those
            starting with '.')
        ignore_hidden_dirs : bool
            whether to ignore hidden directories within nested directories (i.e. those
            starting with '.'), along with everything beneath them

        Returns
        -------
        file_paths : list[Path]
            the paths of the files within the fileset, in sorted order. Files that are
            both listed explicitly and nested within a listed directory are only
            included once. Listed paths that aren't directories are included whether
            they exist or not

        Raises
        ------
        FileNotFoundError
            if a symbolic link within a nested directory is broken
        """
        file_paths: ty.Set[Path] = set()
        for fspath in self.fspaths:
            if not fspath.is_dir():
                # Included even if it doesn't exist (e.g. in mocked filesets), so the
                # keys yielded by `byte_chunks` don't change if it is created later
                file_paths.add(fspath)
            else:
                for dpath, dirnames, filenames in os.walk(fspath):
                    if ignore_hidden_dirs:
                        # Prune in-place so the walk doesn't descend into them
                        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                    for filename in filenames:
                        if ignore_hidden_files and filename.startswith("."):
                            continue
                        file_path = Path(dpath) / filename
                        if not file_path.exists():
                            raise FileNotFoundError(
                                f"Broken symbolic link '{file_path}' found within {self}"
                            )
                        file_paths.add(file_path)
        return sorted(file_paths)

    def byte_chunks(
        self,
        mtime: bool = False,
        chunk_len: int = FILE_CHUNK_LEN_DEFAULT,
        relative_to: ty.Union[Path, str, None] = None,
        ignore_hidden_files: bool = False,
        ignore_hidden_dirs: bool = False,
    ) -> ty.Generator[ty.Tuple[str, ty.Iterator[bytes]], None, None]:
        """Yields relative paths for all files within the file-set along with iterators
        over their byte-contents. To be used when generating hashes for the file set.

        Files are yielded once each, in the sorted order of `all_file_paths`.

        Parameters
        ----------
        mtime : bool, optional
            instead of iterating over the entire contents of the file-set, simply yield
            a bytes repr of the last modification time.
        chunk_len : int, optional
            the chunk length to break up the file and calculate the hash over, by default 8192
        relative_to : Path | str, optional
            the base path by which to record the file system paths in the dictionary keys
            to. Can be a common parent or a parent + file-stem such that only the extensions
            are used in the file keys (allowing transportability of the hashes to different stems),
            by default the common prefix + stem of all files in the fileset is used.
        ignore_hidden_files : bool
            whether to ignore hidden files within nested directories (i.e. those
            starting with '.')
        ignore_hidden_dirs : bool
            whether to ignore hidden directories within nested directories (i.e. those
            starting with '.')

        Yields
        -------
        rel_path: str
            relative path to either 'relative_to' arg or common base path for each file
            in the file set
        byte_iter : Generator[bytes, None, None]
            an iterator over the bytes contents of the file, chunked into 'chunk_len'
            chunks
        """
        # Ensure relative is a Path object

        # If "relative_to" is not provided, get the common path between
        if relative_to is None:
            relative_to_dir = Path(os.path.commonpath(list(self.fspaths))).absolute()
            # Add the common stem prefix to the relative_to parent directory
            if all(p.is_file() and p.parent == relative_to_dir for p in self.fspaths):
                relative_to_stem = os.path.commonprefix(
                    [p.name for p in self.fspaths]
                ).rstrip(".")
            else:
                relative_to_stem = ""
            relative_to = relative_to_dir / relative_to_stem
        else:
            relative_to = Path(relative_to).absolute()
            if relative_to.is_dir():
                relative_to_dir = relative_to
                relative_to_stem = ""
            else:
                relative_to_dir = relative_to.parent
                relative_to_stem = relative_to.name

        def relative_path_str(p: Path) -> str:
            r = p.relative_to(relative_to_dir)
            if relative_to_stem:
                if str(r.parent) != "." or not p.name.startswith(relative_to_stem):
                    raise FileFormatsNotRelativePathError(
                        f"Path {p} in {self} is not relative to the value provided to "
                        f"'relative_to' ({relative_to})"
                    )
                if p.name == relative_to_stem:
                    return "."
                return p.name[len(relative_to_stem) :]
            return str(r)

        # yield the absolute base path if using mtimes instead of contents
        if mtime:
            yield ("<base-path>", iter([str(relative_to).encode()]))

            def chunk_file(fspath: Path) -> ty.Iterator[bytes]:
                """Yields a byte representation of the last modified time for the file"""
                yield bytes(struct.pack("<d", os.stat(fspath).st_mtime))

        else:

            def chunk_file(fspath: Path) -> ty.Iterator[bytes]:
                """Yields the contents of the file in byte chunks"""
                with open(fspath, "rb") as fp:
                    for chunk in iter(functools.partial(fp.read, chunk_len), b""):
                        yield chunk

        for fspath in self.all_file_paths(
            ignore_hidden_files=ignore_hidden_files,
            ignore_hidden_dirs=ignore_hidden_dirs,
        ):
            yield (relative_path_str(fspath), chunk_file(fspath))

    def hash(
        self,
        crypto: CryptoMethod = None,
        mtime: bool = False,
        chunk_len: int = FILE_CHUNK_LEN_DEFAULT,
        relative_to: ty.Optional[Path] = None,
        ignore_hidden_files: bool = False,
        ignore_hidden_dirs: bool = False,
    ) -> str:
        """Calculate a unique hash for the file-set based on the relative paths and
        contents of its constituent files

        Parameters
        ----------
        crypto : function, optional
            the cryptography method used to hash the files, by default hashlib.sha256
        **kwargs
            keyword args passed directly through to the ``hash_dir`` function

        Returns
        -------
        hash : str
            unique hash for the file-set
        """
        if crypto is None:
            crypto = hashlib.sha256
        crypto_obj = crypto()
        for path, bytes_iter in self.byte_chunks(
            mtime=mtime,
            chunk_len=chunk_len,
            relative_to=relative_to,
            ignore_hidden_files=ignore_hidden_files,
            ignore_hidden_dirs=ignore_hidden_dirs,
        ):
            crypto_obj.update(path.encode())
            for bytes_str in bytes_iter:
                crypto_obj.update(bytes_str)
        digest: str = crypto_obj.hexdigest()
        return digest

    def hash_files(
        self,
        crypto: CryptoMethod = None,  # s
        mtime: bool = False,
        chunk_len: int = FILE_CHUNK_LEN_DEFAULT,
        relative_to: ty.Optional[Path] = None,
        ignore_hidden_files: bool = False,
        ignore_hidden_dirs: bool = False,
        max_workers: ty.Optional[int] = None,
    ) -> ty.Dict[str, str]:
        """Calculate hashes for all files in the file-set based on the relative paths and
        contents of its constituent files

        Parameters
        ----------
        crypto : function, optional
            the cryptography method used to hash the files, by default hashlib.sha256
        max_workers : int, optional
            the number of threads used to hash the files concurrently. If None, defaults
            to the default of ``concurrent.futures.ThreadPoolExecutor``. Pass 1 to hash
            the files serially. Filesets with only a few files are always hashed serially
        **kwargs
            keyword args passed directly through to the ``hash_dir`` function

        Returns
        -------
        file_hashes : dict[str, bytes]
            unique hashes for each file in the file-set
        """
        if crypto is None:
            crypto = hashlib.sha256

        def hash_file(item: ty.Tuple[str, ty.Iterator[bytes]]) -> ty.Tuple[str, str]:
            path, bytes_iter = item
            crypto_obj = crypto()
            for bytes_str in bytes_iter:
                crypto_obj.update(bytes_str)
            return str(path), crypto_obj.hexdigest()

        # Consume the generator up-front so that any errors in resolving the paths are
        # raised here. The byte iterators are lazy, so no files are opened yet.
        items = list(
            self.byte_chunks(
                mtime=mtime,
                chunk_len=chunk_len,
                relative_to=relative_to,
                ignore_hidden_files=ignore_hidden_files,
                ignore_hidden_dirs=ignore_hidden_dirs,
            )
        )
        if mtime or max_workers == 1 or len(items) < MIN_FILES_FOR_THREADED_HASHING:
            return dict(map(hash_file, items))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return dict(executor.map(hash_file, items))

    @classmethod
    def referenced_types(cls) -> ty.Set[ty.Type[Classifier]]:
        """Returns a flattened list of nested types referenced within the fileset type

        Returns
        -------
        types : set[Classifier]
            all the types that are referenced in shape or form within the class
        """
        types: ty.Set[ty.Type[Classifier]] = set([cls])
        for b in cls.__mro__:
            try:
                nested = b.nested_types  # type: ignore
            except AttributeError:
                continue
            for t in nested:
                if issubclass(t, FileSet):
                    types.update(t.referenced_types())
        return types

    @classmethod
    def mock(cls, *fspaths: ty.Union[Path, str]) -> "Self":
        """Return an instance of a mocked sub-class of the file format to be used in
        test routines like doctests that doesn't require to point at actual files

        Parameters
        ----------
        *fspaths: sequence[Path | str]
            the paths to be provided to the mocked class, by default will be ["mock/<class-name-lower>"]

        Returns
        -------
        Self
            a file-set that will pass type-checking as an instance of the given
            fileset class but which doesn't actually point to any FS objects.
        """
        mock_cls: ty.Type[Self] = type(
            cls.__name__ + "Mock", (MockMixin, cls), {"TRUE_CLASS": cls}
        )
        fspaths_lst = list(fspaths)
        if not fspaths:
            fspaths_lst = []
            fspath = f"/mock/{cls.__name__.lower()}"
            if cls.ext:
                fspath += cls.ext
            fspaths_lst.append(fspath)
        return mock_cls(fspaths=fspaths_lst)

    @classmethod
    def sample(
        cls,
        dest_dir: ty.Optional[Path] = None,
        seed: ty.Union[int, str] = 0,
        stem: ty.Optional[str] = None,
    ) -> Self:
        """Return an sample instance of the file-set type for classes where the
        `test_data` extra has been implemented

        Parameters
        ----------
        dest_dir : Path, optional
            the path in which to create the test data
        seed : int
            seed used to generate content. Defaults to 0 (rather than a timestamp), so
            the default method call produces consistent runs between calls
        stem : str
            the filename stem to give the file

        Returns
        -------
        FileSet
            an instance of the given file-set class
        """
        if not dest_dir:
            dest_dir = Path(tempfile.mkdtemp())
        else:
            dest_dir = Path(dest_dir)
        # If the dest dir is actually the destination path
        if not stem and cls.ext and cls.matching_exts([dest_dir], [cls.ext]):
            dest_dir = dest_dir.parent
            stem = dest_dir.name
        # Need to use mock to get an instance in order to use the singledispatch-based
        # extra decorator
        fspaths = cls.sample_data(
            SampleFileGenerator(dest_dir=dest_dir, seed=seed, fname_stem=stem)
        )
        try:
            obj = cls(fspaths)
        except FormatMismatchError as e:
            try:
                mime_like = cls.mime_like
            except FormatDefinitionError:
                mime_like = cls.__module__ + "." + cls.__name__
            raise NotImplementedError(
                f"File paths generated by override of FileSet.generate_sample_data() "
                f"({fspaths}) do not match '{mime_like}' file type. A more specific "
                f"implementation is required. Reason:\n\n{e}"
            ) from e
        return obj

    @classmethod
    def sample_data(cls, generator: SampleFileGenerator) -> ty.Iterable[Path]:
        """Converts the `generate_sample_data` method into a class method by mocking up
        a class instance and calling the method on it

        Parameters
        ----------
        generator : SampleFileGenerator
            the generator to use to create the sample data

        Returns
        -------
        ty.Iterable[Path]
            the generated file-system paths
        """
        mock: FileSet = cls.mock()
        return mock.generate_sample_data(generator)

    @extra
    def generate_sample_data(
        self,
        generator: SampleFileGenerator,
    ) -> ty.List[Path]:
        """Generate test data at the fspaths of the file-set

        Parameters
        ----------
        dest_dir : Path
            the directory to generate the test data within
        seed : int
            seed used to generate content. Defaults to 0 (rather than a timestamp), so
            the default method call produces consistent runs between calls
        stem : str
            the filename stem to give the file

        Returns
        -------
        fspaths : ty.Iterable
            the generated fspaths
        """
        raise NotImplementedError

    class ExtensionDecomposition(IntEnum):
        """What to consider the file extension to be for paths without an explicitly
        defined extension

        Options
        -------
        none
            assume it doesn't have a file extension, i.e. all parts are included in the stem
        single
            assume that anything after the last '.' is the extension, e.g. the extension
            of "file.nii.gz" would be ".gz"
        multiple
            assume that anything after the first '.' is the extension, e.g. the extension
            of "file.nii.gz" would be "nii.gz"
        """

        none = 0
        single = 1
        multiple = 2

        def __str__(self) -> str:
            return self.name

    def decomposed_fspaths(
        self,
        required_only: bool = True,
        decomposition_mode: ExtensionDecomposition = ExtensionDecomposition.single,
    ) -> ty.List[ty.Tuple[Path, str, str]]:
        """Decompose paths into parent directory, filename stem, and extension

        Parameters
        ----------
        required_only : bool, optional
            only include required paths, by default True
        assume_implicit_ext : FileSet.ExtensionDecomposition, optional
            how to interpret paths without an explicitly defined extension (i.e. by
            either the extension of the FileSet or nested filesets), by default single

        Returns
        -------
        decomposed_fspath : list[tuple[Path, str, str]]
            a tuple consisting of the parent directory, file-stem and extension
        """
        from ..generic import File

        decomposed_fspaths = []
        required_paths = self.required_paths() if required_only else None
        implicit = set(required_paths if required_paths else self.fspaths)

        def is_subpath(path: Path, others: ty.AbstractSet[Path]) -> bool:
            # Check the (few) parents of the path against the set of other paths, rather
            # than checking the path against each of the (potentially many) others
            return any(p in others for p in path.parents)

        # Paths that are to be included in the decomposition
        to_include = frozenset(implicit)
        # Maps paths decomposed by a typed file-set to the file-set and its decomposition
        decomposed_by: dict[Path, tuple[FileSet, tuple[Path, str, str]]] = {}
        for fileset in [self] + self.nested_filesets():
            if isinstance(fileset, File):
                # Skip files that are nested within other included paths (e.g.
                # directories) of the file-set, as they will be handled along with
                # their parent
                if is_subpath(fileset.fspath, to_include):
                    implicit.discard(fileset.fspath)
                    continue
                # Skip files that aren't to be included (e.g. not required)
                if fileset.fspath not in to_include:
                    continue
                try:
                    decomposed = (
                        fileset.fspath.parent,
                        fileset.stem,
                        fileset.actual_ext,
                    )
                except UnconstrainedExtensionException:
                    # Leave in implicit to be decomposed with the default mode, unless
                    # it has already been decomposed by a typed file-set
                    continue
                if fileset.fspath in implicit:
                    decomposed_fspaths.append(decomposed)
                    implicit.remove(fileset.fspath)
                    decomposed_by[fileset.fspath] = (fileset, decomposed)
                else:
                    previous_fileset, previous = decomposed_by[fileset.fspath]
                    if previous == decomposed:
                        continue
                    warn(
                        f"The '{fileset.fspath}' path within {self} into has been decomposed as "
                        f"{previous} as it was interpreted as a {type(previous_fileset)} "
                        f"file, whereas it is also interpreted as a {type(fileset)}, in "
                        f"which case it could be alternatively decomposed into {decomposed}"
                    )
        for fspath in implicit:
            decomposed_fspaths.append(
                self.decompose_fspath(fspath, mode=decomposition_mode)
            )
        # Drop any paths that are nested within other paths in the set, as they will
        # be copied/moved along with their parent
        full_paths = [p / (s + e) for p, s, e in decomposed_fspaths]
        full_paths_set = frozenset(full_paths)
        return [
            d
            for d, fp in zip(decomposed_fspaths, full_paths)
            if not is_subpath(fp, full_paths_set)
        ]

    @classmethod
    def decompose_fspath(
        cls,
        fspath: ty.Union[Path, str],
        mode: ExtensionDecomposition = ExtensionDecomposition.single,
    ) -> ty.Tuple[Path, str, str]:
        if isinstance(fspath, str):
            fspath = Path(fspath)
        """Decompose an arbitrary file-system path into parent dir, stem and extension
        given the assumption on what constitutes an extension"""
        if mode == cls.ExtensionDecomposition.multiple:
            ext = "".join(fspath.suffixes)
            stem = fspath.name[: -len(ext)]
        elif mode == cls.ExtensionDecomposition.single:
            stem = fspath.stem
            ext = fspath.suffix
        else:
            assert mode == cls.ExtensionDecomposition.none
            stem = str(fspath)
            ext = ""
        return fspath.parent, stem, ext

    @classmethod
    def from_paths(
        cls, fspaths: ty.Iterable[Path], common_ok: bool = False, **kwargs: ty.Any
    ) -> ty.Tuple[ty.Set[Self], ty.Set[Path]]:
        """Finds all instances of the fileset class that can be constructed from a
        collection of file-system paths.

        Parameters
        ----------
        fspaths : Iterable[Path]
            file-system paths to instantiate file-sets from
        common_ok : bool
            whether secondary file-system paths can be shared between multiple instances
            of the returned filesets
        **kwargs: Any
            additional keyword arguments to pass to the file

        Returns
        -------
        filesets : set[FileSet]
            file-sets instantiated from the provided paths
        remaining : set[Path]
            remaining file-system paths that weren't used in any of the file-sets
        """
        fspaths = [Path(p) for p in fspaths]
        filesets = set()
        remaining = set(fspaths)
        for fspath in fspaths:
            try:
                fileset = cls(fspath, **kwargs)
            except FormatMismatchError:
                continue
            else:
                filesets.add(fileset)
                fileset.trim_paths()  # only included required paths in the file set
                if not common_ok and not all(p in remaining for p in fileset.fspaths):
                    continue
                for p in fileset.fspaths:
                    remaining.remove(p)
        return filesets, remaining

    class CopyMode(Enum):
        """Designates the desired behaviour of the FileSet.copy() method with regards to
        symbolic, hard or full copies

        Basic options (in order of preference)
        --------------------------------------
        leave
            simply leave the files where they are (i.e. do nothing)
        hardlink
            hardlink the files into the destination directory
        symlink
            symlink the files into the destination directory
        copy
            duplicate (actually copy) the files into the destination directory

        Common combinations
        -------------------
        link
            use either linking method (preferring symbolic)
        link_or_copy
            use either link method or copy (preferring hard, sym, then copy)
        symlink_or_copy
            "  symbolic "   "         "
        hardlink_or_copy
            "  hard "   "         "

        Masks
        -----
        any
            use any method (preferring leave)
        none
            none of the requested methods are supported (i.e. after masking with the
            supported options mask)
        """

        # Bases

        leave = 0b0001
        hardlink = 0b0010
        symlink = 0b0100
        copy = 0b1000

        # Common combinations
        link = 0b0110
        link_or_copy = 0b1110
        hardlink_or_copy = 0b1010
        symlink_or_copy = 0b1100

        # Masks
        any = 0b1111
        none = 0b0000

        # All other combinations (typically the result of bit-masking)
        leave_or_copy = 0b1001
        leave_or_hardlink = 0b0011
        leave_or_symlink = 0b0101
        leave_or_link = 0b0111
        leave_or_hardlink_or_copy = 0b1011
        leave_or_symlink_or_copy = 0b1101

        def __xor__(self, other: "FileSet.CopyMode") -> "FileSet.CopyMode":
            return type(self)(self.value ^ other.value)

        def __and__(self, other: "FileSet.CopyMode") -> "FileSet.CopyMode":
            return type(self)(self.value & other.value)

        def __or__(self, other: "FileSet.CopyMode") -> "FileSet.CopyMode":
            return type(self)(self.value | other.value)

        def __sub__(self, other: "FileSet.CopyMode") -> "FileSet.CopyMode":
            return type(self)((self.value & (self.value ^ other.value)))

        def __bool__(self) -> bool:
            return bool(self.value)

        def __str__(self) -> str:
            return self.name

    class CopyCollation(IntEnum):
        """Designates the desired "collation" behaviour of the FileSet.copy() method

        Values
        ------
        any
            If mode == leave, paths can exist in separate directories in the
            file-system. For other copy modes, the relative directory structure between
            the "copied" paths (incl. links) in the set will be maintained within the
            destination directory. This guarantees there won't be name clashes between
            copied paths.
        siblings
            copied paths are guaranteed to be "copied" to the root of the destination
            directory, i.e be siblings. However, this requires that the file/dir name
            in fspaths are unique.
        adjacent
            copied paths are guaranteed to have the same name-stem and only differ in
            file-extensions. Requires that the file-set only includes files/dirs with
            unique suffixes (NB: suffixes are considered to be everything after the first
            '.' in the filename).
        """

        any = 0
        siblings = 1
        adjacent = 2

        def __str__(self) -> str:
            return self.name

    def copy(
        self,
        dest_dir: PathType,
        mode: ty.Union[CopyMode, str] = CopyMode.copy,
        collation: ty.Union[CopyCollation, str] = CopyCollation.any,
        new_stem: ty.Optional[str] = None,
        prefix: str = "",
        stem_suffix: str = "",
        trim: bool = True,
        make_dirs: bool = False,
        overwrite: bool = False,
        avoid_clashes: ty.Union[bool, ty.Set[Path]] = False,
        clash_template: str = "{stem} ({counter})",
        supported_modes: CopyMode = CopyMode.any,
        extension_decomposition: ExtensionDecomposition = ExtensionDecomposition.single,
    ) -> Self:
        """Copies the file-set to a new directory, optionally renaming the files
        to have consistent name-stems.

        Based on the range of options provided, copy determines the "laziest" mode to use,
        i.e. if we can leave the files where they are and satisfy both the explicit mode
        requested by the user and the "collation" requirements (see FileSet.CopyCollation),
        we prefer to do so, otherwise we prefer to symlink, then hardlink,
        then as a last resort a full copy.

        Parameters
        ----------
        dest_dir : str
            Path to the parent directory to save the file-set
        mode : FileSet.CopyMode or str, optional
            designates whether to perform an actual copy or whether a link (symbolic or
            hard) is okay, 'duplicate' by default. See FielSet.CopyMode for details
        collation : FileSet.CopyCollation or str, optional
            how to treat relative paths within the fileset, i.e. whether to move them
            to a single directory, rename them to the same file-stem or maintain
            relative directory structure. See FileSet.CopyCollation for details
        new_stem: str, optional
            the file name excluding file extensions, to give the files/dirs in the parent
            directory, by default the original file name is used
        prefix : str, optional
            the prefix to append to the stem of the file name, by default ""
        stem_suffix : str, optional
            the suffix to append to the stem of the file name (i.e. before the extension),
            by default ""
        trim : bool, optional
            Only copy the paths in the file-set that are "required" by the format,
            true by default
        make_dirs : bool, optional
            Make the parent destination and all missing ancestors if they are missing,
            false by default
        overwrite : bool, optional
            whether to overwrite existing files/directories if present, ignored if
            avoid_clashes is set to True, by default False
        avoid_clashes : bool or set[Path], optional
            Can either be a boolean to avoid clashes with any existing files (i.e. the
            overwrite flag is irrelevant), or a set of paths to avoid clashes with.
            If a set is provided, then the copied files will be added to that set as they
            are copied to allow a series of copies to guarantee to have unique paths
            (useful when copying multiple filesets to the same destination directory).
            By default False
        clash_template: str
            The template used to generate a new file name if there is a clash with an
            existing file. It should be a string template containing "stem", "counter"
            and "ext", where counter is the number of files found with the same stem/
            extension, by default "{stem} ({counter}){ext}",
        supported_modes : CopyMode, optional
            supported modes for the copy operation. Used to mask out the requested
            copy mode
        extension_decomposition : FileSet.ExtensionDecomposition, optional
            whether to consider file extensions to start from the first '.' (multiple) or the
            last (single) or be empty (none), when the extension of a fspath in the
            FileSet isn't explicitly defined by the FileSet class. Only relevant when
            collation mode is set to "adjacent". By default True
        """
        self._check_clash_template(clash_template)
        dest_dir = Path(dest_dir)
        # Logic to determine the laziest mode to use
        mode = self.CopyMode[mode] if isinstance(mode, str) else mode
        logger.debug("Requested '%s' for the copy operation", mode)
        if len(self.fspaths) == 1:
            # If there is only one path to copy, then collation isn't meaningful
            collation = self.CopyCollation.any
            logger.debug(
                "Collation mode is set to 'any' as there is only one path in the fileset"
            )
        else:
            collation = (
                self.CopyCollation[collation]
                if isinstance(collation, str)
                else collation
            )
            logger.debug(
                "Collation mode is set to '%s' for the copy operation", collation
            )
        # Rule out any copy modes that are not supported given the collation mode
        # and file-system mounts the paths and destination directory reside on
        constraints = []
        if (
            not FsMountIdentifier.symlinks_supported(dest_dir)
            and mode & self.CopyMode.symlink
        ):
            supported_modes -= self.CopyMode.symlink
            constraint = (
                f"Destination directory is on CIFS mount ({dest_dir}) "
                "and we therefore cannot create a symlink"
            )
            logger.debug(
                constraint + ", supported modes restricted to %s", supported_modes
            )
            constraints.append(constraint)
        not_on_same_mount = [
            p for p in self.fspaths if not FsMountIdentifier.on_same_mount(p, dest_dir)
        ]
        if not_on_same_mount and mode & self.CopyMode.hardlink:
            supported_modes -= self.CopyMode.hardlink
            constraint = (
                f"Some paths ({', '.join(str(p) for p in not_on_same_mount)}) are on "
                f"not on same file-system mount as the destination directory {dest_dir}"
                "and therefore cannot be hard-linked"
            )
            logger.debug(
                constraint + ", supported modes restricted to %s", supported_modes
            )
            constraints.append(constraint)
        if (
            new_stem
            or prefix
            or stem_suffix
            or (
                collation >= self.CopyCollation.siblings
                and not all(p.parent == self.parent for p in self.fspaths)
            )
        ):
            supported_modes -= self.CopyMode.leave
            logger.debug(
                "Collation mode is set to '%s' or new_stem/prefix/stem_suffix is set, "
                "therefore we cannot leave the files where they are",
                collation,
            )

        # Get the intersection of copy modes that are supported and have been requested
        selected_mode = mode & supported_modes
        logger.debug(
            "Selected copy mode is '%s' for the copy operation (requested %s)",
            selected_mode,
            mode,
        )
        if not selected_mode:
            msg = (
                f"Cannot copy {self} using '{mode}' mode as it is not supported by "
                f"the '{supported_modes}' given the collation specification, {collation}"
            )
            if constraints:
                msg += ", and the following constraints:\n" + "\n".join(constraints)
            raise UnsatisfiableCopyModeError(msg)
        if selected_mode & self.CopyMode.leave:
            logger.debug(
                "Selected copy mode is set to 'leave', therefore we are not copying anything"
            )
            return self  # Don't need to do anything

        copy_file: ty.Callable[[Path, Path], None]
        copy_dir: ty.Callable[[Path, Path], None]

        # Select inner copy/link methods
        if selected_mode & self.CopyMode.symlink:
            logger.debug('Using symbolic links for the "copy" operation')
            copy_dir = copy_file = os.symlink
        elif selected_mode & self.CopyMode.hardlink:
            logger.debug('Using hard links for the "copy" operation')
            copy_file = os.link

            def hardlink_dir(src: Path, dest: Path) -> None:
                for dpath_str, _, fpaths in os.walk(src):
                    dpath = Path(dpath_str)
                    relpath = dpath.relative_to(src)
                    (dest / relpath).mkdir()
                    for fpath in fpaths:
                        os.link(dpath / fpath, dest / relpath / fpath)

            copy_dir = hardlink_dir
        else:
            logger.debug('Using full copy for the "copy" operation')
            assert selected_mode & self.CopyMode.copy
            copy_dir = shutil.copytree  # type: ignore
            copy_file = shutil.copyfile  # type: ignore

        # Prepare destination directory
        dest_dir = Path(dest_dir)
        if make_dirs:
            dest_dir.mkdir(parents=True, exist_ok=True)

        # Get source/destination pairs for each of the paths in the fileset
        src_dest = self._src_dest_pairs(
            dest_dir=dest_dir,
            new_stem=new_stem,
            trim=trim,
            prefix=prefix,
            stem_suffix=stem_suffix,
            collation=collation,
            overwrite=overwrite,
            clash_template=clash_template,
            avoid_clashes=avoid_clashes,
            extension_decomposition=extension_decomposition,
        )
        # Iterate through the paths to copy, copying them to the destination directory
        new_paths: ty.List[Path] = []
        for fspath, new_path in src_dest:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            if fspath.is_dir():
                if new_path.is_relative_to(fspath):  # type: ignore[attr-defined]
                    raise ValueError(
                        f"Cannot copy directory {fspath} into itself at {new_path}"
                    )
                copy_dir(fspath, new_path)
            else:
                try:
                    copy_file(fspath, new_path)
                except PermissionError as e:
                    if e.errno == errno.EPERM and copy_file is not shutil.copyfile:  # type: ignore[comparison-overlap]
                        # Fallback to proper copy if the link fails for some reason
                        shutil.copyfile(fspath, new_path)
                    else:
                        raise

            new_paths.append(new_path)
        return type(self)(new_paths)

    def move(
        self,
        dest_dir: PathType,
        collation: ty.Union[CopyCollation, str] = CopyCollation.any,
        new_stem: ty.Optional[str] = None,
        prefix: str = "",
        stem_suffix: str = "",
        trim: bool = True,
        make_dirs: bool = False,
        overwrite: bool = False,
        avoid_clashes: ty.Union[bool, ty.Set[Path]] = False,
        clash_template: str = "{stem} ({counter})",
        extension_decomposition: ExtensionDecomposition = ExtensionDecomposition.single,
    ) -> Self:
        """Moves the file-set to a new directory, optionally renaming the files
        to have consistent name-stems.

        Parameters
        ----------
        dest_dir : str
            Path to the parent directory to save the file-set
        collation : FileSet.CopyCollation or str, optional
            how to treat relative paths within the fileset, i.e. whether to move them
            to a single directory, rename them to the same file-stem or maintain
            relative directory structure. See FileSet.CopyCollation for details
        new_stem: str, optional
            the file name excluding file extensions, to give the files/dirs in the parent
            directory, by default the original file name is used
        prefix : str, optional
            the prefix to append to the stem of the file name
        stem_suffix : str, optional
            the stem_suffix to append to the file name (i.e. before the extension), by default
        trim : bool, optional
            Only copy the paths in the file-set that are "required" by the format,
            true by default
        make_dirs : bool, optional
            Make the parent destination and all missing ancestors if they are missing,
            false by default
        overwrite : bool, optional
            whether to overwrite existing files/directories if present, ignored if
            avoid_clashes is set to True, by default False
        avoid_clashes : bool or set[Path], optional
            whether to avoid name clashes between files in the file-set and existing files.
            In this case the clash_template is used to generate a new name for the file
            that doesn't clash with any existing files. If a set of paths is provided, then
            Can either be a boolean to avoid clashes with any existing files (i.e. the
            overwrite flag is irrelevant), or a set of paths to avoid clashes with.
            If a set is provided, then the copied files will be added to that set as they
            are copied to allow a series of copies to guarantee to have unique paths.
        clash_template: str
            The template used to generate a new file name if there is a clash with an
            existing file. It should be a string template containing "stem", "counter"
            and "ext", where counter is the number of files found with the same stem/
            extension, by default "{stem} ({counter})",
        extension_decomposition : FileSet.ExtensionDecomposition, optional
            whether to consider file extensions to start from the first '.' (multiple) or the
            last (single) or be empty (none), when the extension of a fspath in the
            FileSet isn't explicitly defined by the FileSet class. Only relevant when
            collation mode is set to "adjacent". By default True
        """
        self._check_clash_template(clash_template)
        dest_dir = Path(dest_dir)
        if len(self.fspaths) == 1:
            # If there is only one path to copy, then collation isn't meaningful
            collation = self.CopyCollation.any
        else:
            collation = (
                self.CopyCollation[collation]
                if isinstance(collation, str)
                else collation
            )
        # Create destination directory
        dest_dir = Path(dest_dir)  # ensure a Path not a string
        if make_dirs:
            dest_dir.mkdir(parents=True, exist_ok=True)

        # Get source/destination pairs for each of the paths in the fileset
        to_move_pairs = self._src_dest_pairs(
            dest_dir=dest_dir,
            new_stem=new_stem,
            trim=trim,
            prefix=prefix,
            stem_suffix=stem_suffix,
            overwrite=overwrite,
            collation=collation,
            clash_template=clash_template,
            avoid_clashes=avoid_clashes,
            extension_decomposition=extension_decomposition,
        )
        new_paths: ty.List[Path] = []
        for fspath, new_path in to_move_pairs:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(fspath), new_path)
            new_paths.append(new_path)
        self.fspaths = frozenset(new_paths)
        return self

    def _src_dest_pairs(
        self,
        dest_dir: Path,
        new_stem: ty.Optional[str],
        trim: bool,
        prefix: str,
        stem_suffix: str,
        collation: CopyCollation,
        clash_template: str,
        overwrite: bool,
        avoid_clashes: ty.Union[bool, ty.Set[Path]],
        extension_decomposition: ExtensionDecomposition,
    ) -> ty.List[ty.Tuple[Path, Path]]:
        """Returns the source-destination pairs for the file-paths to be copied/moved

        Parameters
        ----------
        fspaths : list[Path]
            the file-paths to be copied/moved
        dest_dir : Path
            the destination directory
        new_stem : str
            the file name excluding file extensions, to give the files/dirs in the parent
            directory, by default the original file name is used
        prefix : str
            the prefix to append to the stem of the file name
        stem_suffix : str
            the stem_suffix to append to the file name (i.e. before the extension)
        collation : FileSet.CopyCollation
            how to treat relative paths within the fileset, i.e. whether to move them to a
            single directory, rename them to the same file-stem or maintain relative
            directory structure. See FileSet.CopyCollation for details
        clash_template: str
            The template used to generate a new file name if there is a clash with an
            existing file. It should be a string template containing "stem", "counter"
            and "ext", where counter is the number of files found with the same stem/
            extension

        Returns
        -------
        pairs : list[tuple[Path, Path]]
            the source-destination pairs for the file-paths to be copied/moved
        """
        decomposed_fspaths = self.decomposed_fspaths(
            required_only=trim, decomposition_mode=extension_decomposition
        )
        if not decomposed_fspaths:
            raise UnsatisfiableCopyModeError(
                f"Cannot copy {self} because none of the fspaths in the file-set are "
                "required. Set trim=False to copy all file-paths"
            )
        if collation >= self.CopyCollation.siblings:
            duplicate_names = [
                n for n, c in Counter(p.name for p in self.fspaths).items() if c > 1
            ]
            if duplicate_names:
                raise UnsatisfiableCopyModeError(
                    f"Cannot copy/move {self} with collation mode "
                    f'"{collation}", as there are duplicate filenames, {duplicate_names}, '
                    f"in file paths: " + "\n".join(str(p) for p in self.fspaths)
                )
        if collation == self.CopyCollation.adjacent or new_stem:
            exts = [d[-1] for d in decomposed_fspaths]
            duplicate_exts = [n for n, c in Counter(exts).items() if c > 1]
            if duplicate_exts:
                reason = ""
                if new_stem:
                    reason += f"with a new stem, {new_stem!r}, "
                if collation == self.CopyCollation.adjacent:
                    reason += f"with collation mode '{collation}', "
                raise UnsatisfiableCopyModeError(
                    f"Cannot copy/move {self} {reason} as there are duplicate "
                    f"extensions, {duplicate_exts}, in file paths: "
                    + "\n".join(str(p) for p in self.fspaths)
                )
            # Set default for new_stem if not provided and collating file-set to be adjacent
            if new_stem is None:
                new_stem = sorted(decomposed_fspaths)[0][1]
        if len(self.fspaths) == 1:
            # Now that we have passed all the checks, we can set the collation to siblings
            # to signify that we don't need to worry about relative paths
            collation = self.CopyCollation.siblings
        # Iterate through the paths to copy/move and determine their destination paths
        counter = 0
        previous_clashes = set()
        pairs: ty.List[ty.Tuple[Path, Path]] = []
        # We loop until we have a set of paths that don't clash with existing files
        # in the destination directory, if avoid_clashes is set to True or a set
        while not pairs:
            iterate_counter = False
            for parent_dir, stem, ext in decomposed_fspaths:
                fspath = parent_dir / (stem + ext)
                new_path = self._new_copy_path(
                    parent_dir=parent_dir,
                    stem=stem,
                    ext=ext,
                    dest_dir=dest_dir,
                    new_stem=new_stem,
                    prefix=prefix,
                    stem_suffix=stem_suffix,
                    collation=collation,
                    counter=counter,
                    clash_template=clash_template,
                    extension_decomposition=extension_decomposition,
                )
                if counter and new_path in previous_clashes:
                    raise RuntimeError(
                        f"Cannot avoid clash for {str(fspath)!r} with template "
                        f"{clash_template!r}, as it is not possible to generate a "
                        f"unique path, tried {str(new_path)!r}"
                    )
                if self._destination_to_avoid(new_path, overwrite, avoid_clashes):
                    iterate_counter = True
                    previous_clashes.add(new_path)
                    break
                pairs.append((fspath, new_path))
            if iterate_counter:
                # Path clash to avoid detected, iterate counter and try again
                pairs = []
                counter += 1
        # Update the paths to avoid with the new paths
        if isinstance(avoid_clashes, set):
            avoid_clashes.update(n for o, n in pairs)
        return pairs

    def _new_copy_path(
        self,
        parent_dir: Path,
        stem: str,
        ext: str,
        dest_dir: Path,
        new_stem: ty.Optional[str],
        prefix: str,
        stem_suffix: str,
        collation: CopyCollation,
        counter: int,
        clash_template: str,
        extension_decomposition: ExtensionDecomposition,
    ) -> Path:
        """Returns the new path for a file to be copied/moved based on the collation mode
        and new_stem

        Parameters
        ----------
        dest_dir : Path
            the destination directory
        fspath : Path | tuple[Path, str, str]
            the file-path to be copied/moved
        new_stem : str
            the file name excluding file extensions, to give the files/dirs in the parent
            directory, by default the original file name is used
        prefix : str, optional
            the prefix to append to the stem of the file name
        stem_suffix : str, optional
            the stem_suffix to append to the file name (i.e. before the extension), by default
            None
        collation : FileSet.CopyCollation
            how to treat relative paths within the fileset, i.e. whether to move them to a
            single directory, rename them to the same file-stem or maintain relative
            directory structure. See FileSet.CopyCollation for details
        counter : int
            the counter to use in the clash_template to avoid name clashes
        clash_template: str
            The template used to generate a new file name if there is a clash with an
            existing file. It should be a string template containing "stem", "counter"
            and "ext", where counter is the number of files found with the same stem/
            extension, by default "{stem} ({counter})",
        extension_decomposition : FileSet.ExtensionDecomposition
            whether to consider file extensions to start from the first '.' (multiple) or
            the last (single) or be empty (none), when the extension of a fspath in the
            FileSet isn't explicitly defined by the FileSet class. Only relevant when
            collation mode is set to "adjacent". By default True

        Returns
        -------
        new_path : Path
            the new path for the file to be copied/moved
        fspath : Path
            the original file-path, reconstructed from its decomposition if necessary
        """
        if collation == self.CopyCollation.any:
            relpath = parent_dir.relative_to(self.parent)
            if parts := relpath.parts:
                # If the fileset contains relative sub-directory structure that may need
                # to be retained
                if counter:
                    # Apply the clash template to the first top-level sub-directory
                    # to be copied into the destination directory
                    new_dir = clash_template.format(stem=parts[0], counter=counter)
                    relpath = Path(new_dir).joinpath(*parts[1:])
                    counter = 0  # counter has already been applied
                dest_dir = dest_dir / relpath
        if new_stem:
            stem = new_stem
        # apply the prefix and suffix to the stem
        stem = prefix + stem + stem_suffix
        # Append the filename-stem with a counter to avoid name clashes if provided
        if counter:
            stem = clash_template.format(stem=stem, counter=counter)
        return dest_dir / (stem + ext)

    def _check_clash_template(self, clash_template: str) -> None:
        parts = ["stem", "counter"]
        if missing := [p for p in parts if "{" + p + "}" not in clash_template]:
            raise ValueError(
                f"Invalid clash template {clash_template!r}, it must contain template "
                f"args for {parts}, missing {missing}"
            )

    def _destination_to_avoid(
        self,
        new_path: Path,
        overwrite: bool,
        avoid_clashes: ty.Union[bool, ty.Set[Path]],
    ) -> bool:
        """Check if the destination path already exists and whether to avoid it"""
        if overwrite and avoid_clashes is True:
            raise ValueError(
                "Cannot set both 'overwrite' and 'avoid_clashes' to True, as they are "
                "mutually exclusive"
            )
        if new_path.exists():
            if overwrite:
                if new_path.is_dir():
                    shutil.rmtree(new_path)
                else:
                    os.unlink(new_path)
                assert not new_path.exists()
            elif avoid_clashes is True or (avoid_clashes and new_path in avoid_clashes):
                return True
            else:
                raise FileExistsError(
                    f"Destination path '{str(new_path)}' exists, set "
                    "'overwrite' to overwrite it"
                )
        return isinstance(avoid_clashes, set) and new_path in avoid_clashes

    # Class attributes, used to cache the results of the class methods
    _all_formats: ty.Optional[ty.Set[ty.Type["FileSet"]]] = None
    _formats_by_iana_mime: ty.Optional[ty.Dict[str, ty.Type["FileSet"]]] = None
    _formats_by_name: ty.Optional[ty.Dict[str, ty.Set[ty.Type["FileSet"]]]] = None
    _required_props: ty.Optional[ty.Tuple[str, ...]] = None
    _valid_class: ty.Optional[bool] = None


def _root_dir(fileset: FileSet) -> Path:
    """The directory containing all of the fileset's paths (the parent of a directory
    fileset rather than the directory itself)"""
    return Path(os.path.commonpath([p.parent for p in fileset.fspaths]))


def _has_wildcard_classifiers(datatype: ty.Type[DataType]) -> bool:
    """Whether the type is classified by wildcards (e.g. `SetOf[T]`), i.e. a template
    for the source or target types of generic converters"""
    try:
        return bool(datatype.wildcard_classifiers())  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        return False


def _resolve_wildcards(
    template: ty.Type[DataType],
    mapping: ty.Mapping[ty.Type[DataType], ty.Type[DataType]],
) -> ty.Type[DataType]:
    """Substitute the wildcard classifiers of a generic converter's source type with the
    types they resolve to, e.g. `SetOf[T]` with {T: TextFile} -> `SetOf[TextFile]`, or
    the type itself if the source type is the wildcard, e.g. `Compressed` -> `TextFile`
    """
    from .converter_helpers import SubtypeVar

    if issubclass(template, SubtypeVar):
        return mapping[template]
    classifiers = tuple(
        mapping.get(c, c) for c in template.classifiers  # type: ignore[attr-defined]
    )
    unclassified = template.unclassified  # type: ignore[attr-defined]
    return unclassified[classifiers if len(classifiers) > 1 else classifiers[0]]  # type: ignore[no-any-return]
