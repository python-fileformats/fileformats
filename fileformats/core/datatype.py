from __future__ import annotations

import decimal
import importlib
import itertools
import sys
import typing as ty
from abc import ABCMeta
from inspect import isclass

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

from fileformats.core.typing import Self

from .classifier import Classifier
from .decorators import classproperty
from .exceptions import (
    FileFormatsError,
    FormatConversionError,
    FormatMismatchError,
    FormatRecognitionError,
)
from .identification import (
    IANA_MIME_TYPE_REGISTRIES,
    formats_by_mime_format_name,
    from_mime_format_name,
)
from .utils import add_exc_note, subpackages

if ty.TYPE_CHECKING:
    from .converter_helpers import Converter

FieldPrimitive: TypeAlias = ty.Union[
    str,
    int,
    float,
    bool,
    decimal.Decimal,
    ty.Sequence[str],
    ty.Sequence[int],
    ty.Sequence[float],
    ty.Sequence[bool],
    ty.Sequence[decimal.Decimal],
]


class DataType(Classifier, metaclass=ABCMeta):
    """
    Base class for all file formats and fields.
    """

    is_fileset = False
    is_field = False

    @classproperty
    def nested_types(cls) -> ty.Tuple[ty.Type[Classifier], ...]:
        return ()

    # Store converters registered by @converter decorator that convert to FileSet
    # NB: each class will have its own version of this dictionary
    converters: ty.Dict[
        ty.Type["DataType"], "fileformats.core.converter_helpers.Converter"  # type: ignore[type-arg]
    ] = {}

    @classmethod
    def type_var(cls, name: str) -> "fileformats.core.converter_helpers.SubtypeVar":
        import fileformats.core.converter_helpers

        return fileformats.core.converter_helpers.SubtypeVar.new(name, cls)

    @classmethod
    def matches(cls, values: ty.Any) -> bool:
        """Checks whether the given value (fspaths for file-sets) match the datatype
        specified by the class

        Parameters
        ----------
        values : ty.Any
            values to check whether they match the given datatype

        Returns
        -------
        matches : bool
            whether the datatype matches the provided values
        """
        try:
            cls(values)  # type: ignore
        except (FormatMismatchError, FileNotFoundError):
            return False
        else:
            return True

    @classproperty  # type: ignore[arg-type]
    def all_types(self) -> ty.Iterator[ty.Type[DataType]]:
        return itertools.chain(FileSet.all_formats, Field.all_fields)

    @classmethod
    def subclasses(cls, **kwargs: ty.Any) -> ty.Generator[ty.Type[Self], None, None]:
        """Iterate over all installed subclasses"""
        for subpkg in subpackages(**kwargs):
            for attr_name in dir(subpkg):
                attr = getattr(subpkg, attr_name)
                if (
                    attr is not cls
                    and isclass(attr)
                    and issubclass(attr, cls)
                    and ty.get_origin(attr) is None
                ):
                    yield attr

    @classmethod
    def get_converter(
        cls,
        source_format: ty.Type[DataType],
    ) -> "ty.Optional[Converter]":
        if issubclass(source_format, cls):
            return None
        else:
            raise FormatConversionError(
                f"Cannot converter between '{cls.mime_like}' and '{source_format.mime_like}'"
            )

    @classproperty  # type: ignore[arg-type]
    def mime_type(cls) -> str:
        """Generates a MIME type identifier from a format class (i.e. an identifier
        for a non-MIME class in the MIME."""
        raise FileFormatsError(f"MIME type not defined for {cls} class")

    @classproperty  # type: ignore[arg-type]
    def mime_like(cls) -> str:
        """Generates a "MIME-like" identifier from a format class. The fileformats
        package namespace forms a superset of IANA MIME registries. Formats with
        official MIME types will return their MIME type, while extension formats will
        return a MIME-like identifier, e.g. "text/plain" for fileformats.text.Plain.
        and "medimage/nifti" for fileformats.medimage.Nifti.
        """
        mime_like: str = cls.namespace + "/"
        if cls.vendor:
            mime_like += "vnd." + cls.vendor + "."
        mime_like += cls._mime_format_name(cls.namespace, cls.vendor)
        return mime_like

    @classmethod
    def from_mime(cls, mime_string: str) -> ty.Type[DataType]:
        """Resolves a FileFormat class from a MIME (IANA) or "MIME-like" identifier (i.e.
        an identifier for a non-MIME class in the MIME style), e.g.

            "text/plain" resolves to fileformats.text.Plain

        and

            "image/tiff-fx" resolves to fileformats.image.TiffFx

        Parameters
        ----------
        mime_string : str
            MIME identifier

        Returns
        -------
        type
            the corresponding file format class

        Raises
        ------
        FormatRecognitionError
            if the MIME string does not correspond to a valid file format class
        """
        try:
            # Split on the first "/" only, as foreign-namespace classifiers can contain
            # "/" within brackets, e.g. "field/[testing/test-field]+array"
            namespace, format_name = mime_string.split("/", 1)
            if not namespace or not format_name or "[" in namespace:
                raise ValueError
        except ValueError:
            raise FormatRecognitionError(
                f"Format '{mime_string}' is not a valid MIME-like format of <namespace>/<format>"
            ) from None
        else:
            namespace = namespace.replace("-", "_")
        # Attempt to load file type using their `iana_mime` attribute
        try:
            return FileSet.formats_by_iana_mime[mime_string]  # type: ignore[no-any-return]
        except KeyError:
            pass
        if namespace == "application" and format_name.startswith("x-"):
            # We treat the "application/x-" namespace as a catch-all for any formats
            # that are not explicitly covered by the IANA standard (which is how the IANA
            # treats it). Therefore, we loop through all subclasses across the different
            # namespaces to find one that matches the name.
            format_name = format_name[2:]  # remove "x-" prefix
            matching_name: ty.Collection[ty.Type[FileSet]] = (
                FileSet.formats_by_name.get(format_name, ())
            )
            matching_name = [
                m
                for m in matching_name
                if m.__module__ not in IANA_MIME_TYPE_REGISTRIES
            ]
            if not matching_name:
                namespace_names = [
                    p.__name__
                    for p in subpackages()
                    if p.__name__.split(".")[-1] not in IANA_MIME_TYPE_REGISTRIES
                ]
                class_name = from_mime_format_name(format_name)
                raise FormatRecognitionError(
                    f"Did not find class matching extension the class name '{class_name}' "
                    f"corresponding to MIME type '{mime_string}' "
                    f"in any of the installed nonnamespaces: {namespace_names}"
                )
            elif len(matching_name) > 1:
                namespace_names = [f.__module__ for f in matching_name]
                raise FormatRecognitionError(
                    f"Ambiguous extended MIME type '{mime_string}', could refer to "
                    f"{', '.join(repr(f) for f in matching_name)} installed types. "
                    f"Explicitly set the 'iana_mime' attribute on one or all of these types "
                    f"to disambiguate, or uninstall all but one of the following "
                    "namespaces: "
                )
            else:
                klass = next(iter(matching_name))
        else:
            klass = cls._resolve_mime_like(  # type: ignore[assignment]
                namespace, format_name, mime_string
            )
        if not (ty.get_origin(klass) is ty.Union or issubclass(klass, cls)):
            raise FormatRecognitionError(
                f"Class '{klass}' does not inherit from '{cls}'"
            )
        return klass

    @classmethod
    def _resolve_mime_like(
        cls, namespace: str, format_name: str, mime_string: str
    ) -> ty.Type[Classifier]:
        """Resolve the format part of a "MIME-like" string within the given namespace,
        including classified types, e.g. "b..a+k", which can be nested by enclosing
        classified classifiers in brackets, e.g. "[informal-schema+json]+zip", and
        refer to classifiers in other namespaces by including their namespace within the
        brackets, e.g. "[testing/test-field]+array"

        Parameters
        ----------
        namespace : str
            the namespace (with "-" replaced by "_") to resolve the format in
        format_name : str
            the format part of the MIME-like string (i.e. after the "/")
        mime_string : str
            the full MIME-like string being resolved, for error messages

        Returns
        -------
        type
            the resolved datatype or classifier
        """
        # Get the path to the module to load the class from
        if format_name.startswith("vnd."):
            name_parts = format_name.split(".")
            vendor = name_parts[1]
            format_name = ".".join(name_parts[2:])
            module_path = f"fileformats.vendor.{vendor}.{namespace}"
        else:
            module_path = f"fileformats.{namespace}"
        module_path = module_path.replace("-", "_")
        try:
            module = importlib.import_module(module_path)
        except ImportError:
            raise FormatRecognitionError(
                f"Did not find fileformats namespace package at '{module_path}' "
                f"required to interpret '{mime_string}' MIME, or MIME-like, type. "
                f"try installing the namespace package with "
                f"'python3 -m pip install fileformats-{namespace}'."
            ) from None
        if "[" not in format_name:
            class_name = from_mime_format_name(format_name)
            try:
                return getattr(module, class_name)  # type: ignore[no-any-return]
            except AttributeError:
                if "+" not in format_name:
                    raise FormatRecognitionError(
                        f"Did not find '{class_name}' class in {module_path} "
                        f"corresponding to MIME, or MIME-like, type {mime_string}"
                    ) from None

        parent_namespace: ty.Optional[str]
        if "_" in namespace:
            parent_namespace = namespace.split("_")[0]
            parent_module = importlib.import_module("fileformats." + parent_namespace)
        else:
            parent_namespace = parent_module = None

        def get_format(mime_name: str) -> ty.Type[Classifier]:
            name = from_mime_format_name(mime_name)
            try:
                return getattr(module, name)  # type: ignore
            except AttributeError:
                if parent_module:
                    try:
                        return getattr(parent_module, name)  # type: ignore
                    except AttributeError:
                        pass
                    err_msg_part = f" or fileformats.{parent_namespace}"
                else:
                    err_msg_part = ""
                raise FormatRecognitionError(
                    f"Could not load format class {name} (from "
                    f"'{mime_name}') fileformats.{namespace}"
                    f"{err_msg_part} corresponding "
                    f"to MIME, or MIME-like, type {mime_string}"
                ) from None

        def parse_item(item: str) -> ty.Type[Classifier]:
            if _is_single_bracketed(item):
                inner = item[1:-1]
                parts = _split_top_level(inner, "/", mime_string)
                if len(parts) == 2:
                    # Classifier from another namespace, e.g. "[testing/test-field]"
                    return cls._resolve_mime_like(
                        parts[0].replace("-", "_"), parts[1], mime_string
                    )
                if len(parts) > 2:
                    raise FormatRecognitionError(
                        f"Invalid classifier '{item}' in MIME-like type {mime_string}"
                    )
                return parse(inner)
            if "[" in item or "]" in item:
                raise FormatRecognitionError(
                    f"Invalid classifier '{item}' in MIME-like type {mime_string}, "
                    "brackets must enclose the whole classifier"
                )
            return get_format(item)

        def parse(name: str) -> ty.Type[Classifier]:
            parts = _split_top_level(name, "+", mime_string)
            if len(parts) == 1:
                return parse_item(name)
            if len(parts) > 2:
                raise FormatRecognitionError(
                    f"Could not parse '{name}' in MIME-like type {mime_string}, "
                    "classified types used as classifiers need to be enclosed in "
                    "brackets, e.g. '[informal-schema+json]+zip'"
                )
            classifiers_str, classified_name = parts
            classifiers = [
                parse_item(c)
                for c in _split_top_level(classifiers_str, "..", mime_string)
            ]
            classified: ty.Type[Classifier]
            if _is_single_bracketed(classified_name):
                classified = parse_item(classified_name)
            else:
                try:
                    classified = get_format(classified_name)
                except FormatRecognitionError as e:
                    try:
                        classified = cls.generically_classifiable_by_name[
                            classified_name
                        ]
                    except KeyError:
                        add_exc_note(
                            e,
                            (
                                "neither list of generic types "
                                f"({list(cls.generically_classifiable_by_name)})"
                            ),
                        )
                        raise e
            return classified[classifiers]  # type: ignore

        return parse(format_name)

    @classproperty  # type: ignore[arg-type]
    def generically_classifiable_by_name(cls) -> ty.Dict[str, ty.Type[DataType]]:
        if cls._generically_classifiable_by_name is None:
            cls._generically_classifiable_by_name = dict(
                formats_by_mime_format_name(
                    f
                    for f in FileSet.all_formats
                    if getattr(f, "generically_classifiable", False)
                )
            )
        return cls._generically_classifiable_by_name

    # Register all generically classified types
    _generically_classifiable_by_name: ty.Optional[ty.Dict[str, ty.Type[DataType]]] = (
        None
    )

    REQUIRED_ANNOTATION = "__fileformats_required__"
    CHECK_ANNOTATION = "__fileformats_check__"


def _split_top_level(string: str, sep: str, mime_string: str) -> ty.List[str]:
    """Split `string` on `sep`, ignoring occurrences of `sep` within brackets"""
    parts = []
    depth = 0
    start = 0
    i = 0
    while i < len(string):
        char = string[i]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth < 0:
                break
        elif depth == 0 and string.startswith(sep, i):
            parts.append(string[start:i])
            i += len(sep)
            start = i
            continue
        i += 1
    if depth != 0:
        raise FormatRecognitionError(
            f"Unbalanced brackets in MIME-like type {mime_string}"
        )
    parts.append(string[start:])
    return parts


def _is_single_bracketed(item: str) -> bool:
    """Whether `item` is enclosed in a single pair of matching brackets, e.g. "[a+b]"
    but not "[a]..[b]" """
    if not (item.startswith("[") and item.endswith("]")):
        return False
    depth = 0
    for i, char in enumerate(item):
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0 and i != len(item) - 1:
                return False
    return depth == 0


import fileformats.core.converter_helpers  # noqa

from .field import Field  # noqa
from .fileset import FileSet  # noqa
