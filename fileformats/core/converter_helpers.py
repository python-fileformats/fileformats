import logging
import types
import typing as ty
from abc import ABCMeta

from .classifier import Classifier
from .datatype import DataType
from .exceptions import FormatConversionError, FormatDefinitionError

if ty.TYPE_CHECKING:
    from pydra.compose.base import Task

    import fileformats.core

    from . import mixin

logger = logging.getLogger("fileformats")

T = ty.TypeVar("T")
DT = ty.TypeVar("DT", bound=DataType)


class SubtypeVar:
    """To handle the case where the target format is a placeholder (type-var) defined by
    by its relationship to the source format, e.g.

    AnyFileFormat = FileSet.type_var("AnyFileFormat")

    @converter
    @python.define  # type: ignore[untyped-decorator]
    def unzip(in_file: Zip[AnyFileFormat], out_file: AnyFileFormat):
        ...
    """

    converters: ty.Dict[ty.Type["fileformats.core.FileSet"], "Converter"] = {}

    @classmethod
    def new(cls, name: str, klass: type) -> "SubtypeVar":
        """Create a new subtype

        Parameters
        ----------
        name : str
            name for the subtype
        klass : ty.Type[DataType]
            the class to sub-type

        Returns
        -------
        SubtypeVar
            a sub-type that is
        """
        return ABCMeta(name, (cls, klass), {"bound": klass})  # type: ignore

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        if issubclass(subclass, SubtypeVar):
            return issubclass(subclass.bound, cls.bound)  # type: ignore
        return type.__subclasscheck__(cls, subclass)

    @classmethod
    def get_converter_defs(
        cls, source_format: ty.Type["mixin.WithClassifiers"], target_format: type
    ) -> ty.List["Converter"]:
        # check to see whether there are converters from a base class of the source
        # format
        available_converters: ty.List[Converter] = []
        # assert isinstance(source_format, WithClassifiers)
        if source_format.is_classified:
            for template_source_format, converter in cls.converters.items():
                if not issubclass(
                    template_source_format.unclassified, source_format.unclassified  # type: ignore
                ):
                    continue
                assert len(template_source_format.wildcard_classifiers()) == 1  # type: ignore
                non_wildcards = template_source_format.non_wildcard_classifiers()  # type: ignore
                if not non_wildcards.issubset(source_format.classifiers):
                    continue
                from_types = tuple(
                    set(source_format.classifiers).difference(non_wildcards)
                )
                if any(issubclass(q, target_format) for q in from_types):
                    available_converters.append(converter)
        return available_converters

    @classmethod
    def register_converter(
        cls,
        source_format: ty.Type["mixin.WithClassifiers"],
        converter: "Converter",
    ) -> None:
        """Registers a converter task within a class attribute. Called by the
        @fileformats.core.converter decorator.

        Parameters
        ----------
        source_format : type
            the source format to register a converter from
        converter : Converter
            The converter object to register

        Raises
        ------
        FormatConversionError
            if there is already a converter registered between the two types
        """
        # Ensure "converters" dict is defined in the target class and not in a superclass
        if len(source_format.wildcard_classifiers()) > 1:
            raise FormatDefinitionError(
                "Cannot register a conversion to a generic type from a type with more "
                f"than one wildcard {source_format} ({list(source_format.wildcard_classifiers())})"
            )
        prev_registered = [
            f
            for f in cls.converters
            if (
                f.unclassified is source_format.unclassified  # type: ignore
                and f.non_wildcard_classifiers()  # type: ignore
                == source_format.non_wildcard_classifiers()
            )
        ]
        assert len(prev_registered) <= 1
        if prev_registered:
            prev_def = cls.converters[prev_registered[0]]
            # task, task_kwargs, _ = converter_spec
            # prev_task, prev_kwargs = prev_tuple
            if converter.task == prev_def.task:
                logger.warning(
                    "Ignoring duplicate registrations of the same converter %s",
                    converter.task,
                )
                return  # actually the same task but just imported twice for some reason
            generic_type = tuple(prev_def.task.wildcard_classifiers())[0]  # type: ignore
            raise FormatDefinitionError(
                f"Cannot register converter from {source_format} to the generic type "
                f"'{generic_type}', {converter.task} "
                f"because there is already one registered, {prev_def.task}"
            )

        cls.converters[source_format] = converter  # type: ignore


class Converter:
    """Specification of a converter task, including the task callable, its arguments and
    the classifiers"""

    task: "Task[ty.Any]"
    classifiers: ty.Tuple[ty.Type[Classifier], ...]
    in_file: str
    out_file: str

    def __init__(
        self,
        task: "Task[T]",
        classifiers: ty.Tuple[ty.Type[Classifier], ...] = (),
        in_file: str = "in_file",
        out_file: str = "out_file",
    ):
        self.task = task
        self.classifiers = classifiers
        self.in_file = in_file
        self.out_file = out_file

    @property
    def is_chain(self) -> bool:
        """Whether the converter chains other converters together to convert via
        intermediate formats"""
        return (
            type(self.task).__name__ == "ConverterChain"
            and type(self.task).__module__ == "fileformats.core.converter_chain"
        )

    def __eq__(self, other: object) -> bool:
        from pydra.utils.hash import hash_function

        return (
            isinstance(other, Converter)
            and self.task == other.task
            and hash_function(self.classifiers) == hash_function(other.classifiers)
            and self.in_file == other.in_file
            and self.out_file == other.out_file
        )


def union_members(datatype: ty.Any) -> ty.Tuple[type, ...]:
    """The members of a union type (or the type itself if it isn't a union), with
    ``Annotated`` wrappers (e.g. ``ConvertibleTo[Png]``) stripped, nested unions
    flattened and ``None`` removed (so ``Optional[X]`` gives ``(X,)``)

    Parameters
    ----------
    datatype : type
        a datatype, union of datatypes, optional datatype or annotated datatype

    Returns
    -------
    tuple[type, ...]
        the unique members of the union, in the order they appear
    """
    origin = ty.get_origin(datatype)
    if origin is ty.Annotated:
        return union_members(ty.get_args(datatype)[0])
    if origin in (ty.Union, types.UnionType):
        members = (m for a in ty.get_args(datatype) for m in union_members(a))
        return tuple(dict.fromkeys(members))
    if datatype is None or datatype is type(None):
        return ()
    return (datatype,)


def get_converter(
    target: ty.Any,
    source: ty.Any,
    allow_chains: bool = True,
) -> ty.Optional[Converter]:
    """Get a converter from the source format into the target format, where the target
    format can be a union (or optional/annotated) of formats, in which case the
    converter into the first member of the union that the source format can be
    converted into is returned (or None if the source is already one of the members).

    Parameters
    ----------
    target : type | Union[type, ...]
        the format, or union of formats, to convert into
    source : type
        the format to convert from. May be optional or annotated, but not a union of
        multiple formats (see `get_converters`)
    allow_chains : bool, optional
        whether to chain converters together to convert via intermediate formats
        if there is no direct converter available, by default True

    Returns
    -------
    Converter | None
        the converter, or None if no conversion is required

    Raises
    ------
    FormatConversionError
        if the source format can't be converted into any of the target formats
    """
    from .fileset import FileSet

    targets = union_members(target)
    sources = union_members(source)
    if not targets:
        raise TypeError(f"No target formats found in {target!r}")
    if len(sources) != 1:
        raise TypeError(
            f"Source format must be a single format, not {source!r}, use "
            "`get_converters` to get converters from each member of a union"
        )
    (src,) = sources
    # Favour target formats that don't require any conversion
    if any(issubclass(src, t) for t in targets):
        return None
    msgs = []
    for tgt in targets:
        try:
            if issubclass(tgt, FileSet):
                return tgt.get_converter(src, allow_chains=allow_chains)
            if not issubclass(tgt, DataType):
                raise TypeError(f"Target format {tgt!r} is not a fileformats DataType")
            return tgt.get_converter(src)
        except FormatConversionError as e:
            msgs.append(str(e))
    raise FormatConversionError(
        f"Could not find converter from {_format_name(src)} to any of "
        f"{', '.join(_format_name(t) for t in targets)}:\n" + "\n".join(msgs)
    )


def get_converters(
    target: ty.Any,
    source: ty.Any,
    allow_chains: bool = True,
) -> ty.Dict[type, ty.Optional[Converter]]:
    """Get converters from each member of the source format, which can be a union (or
    optional/annotated) of formats, into the target format, which can also be a union.
    See `get_converter` for how the converter for each source member is selected.

    Parameters
    ----------
    target : type | Union[type, ...]
        the format, or union of formats, to convert into
    source : type | Union[type, ...]
        the format, or union of formats, to convert from
    allow_chains : bool, optional
        whether to chain converters together to convert via intermediate formats
        if there is no direct converter available, by default True

    Returns
    -------
    dict[type, Converter | None]
        the converter for each member of the source union, or None for the members
        that don't require conversion

    Raises
    ------
    FormatConversionError
        if any member of the source union can't be converted into the target format(s)
    """
    converters = {}
    msgs = []
    for src in union_members(source):
        try:
            converters[src] = get_converter(target, src, allow_chains=allow_chains)
        except FormatConversionError as e:
            msgs.append(str(e))
    if msgs:
        raise FormatConversionError("\n".join(msgs))
    return converters


def _format_name(datatype: type) -> str:
    try:
        return repr(datatype.mime_like)  # type: ignore[attr-defined]
    except Exception:
        return repr(datatype)
