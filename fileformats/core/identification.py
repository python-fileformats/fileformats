import functools
import inspect
import operator
import re
import typing as ty
from pathlib import Path

import fileformats.core
from fileformats.core.exceptions import FormatDefinitionError, FormatRecognitionError

from .utils import (
    add_exc_note,
    fspaths_converter,
    get_optional_type,
    is_optional,
    is_union,
)

LIST_MIME = "+list-of"
TUPLE_MIME = "+tuple-of"
IANA_MIME_TYPE_REGISTRIES = [
    "application",
    "audio",
    "font",
    "image",
    "message",
    "model",
    "multipart",
    "text",
    "video",
    "vendor.ms_excel",
    "vendor.ms_powerpoint",
    "vendor.ms_word",
    "vendor.openxmlformats_officedocument",
]
ALL_STANDARD_TYPE_REGISTRIES = IANA_MIME_TYPE_REGISTRIES + [
    "field",
    "testing",
    "vendor.testing",
]
# Namespaces that are shipped within the main "fileformats" package, and therefore have
# their "extras" implementations bundled together in the "fileformats-extras" package.
# Note that "generic" is included here even though it isn't a "standard" type registry,
# since generic types are defined in the main package alongside the standard ones
BUNDLED_EXTRAS_NAMESPACES = ALL_STANDARD_TYPE_REGISTRIES + ["generic"]


def find_matching(
    fspaths: ty.Collection[Path],
    candidates: ty.Optional[ty.Collection[ty.Type["fileformats.core.FileSet"]]] = None,
    standard_only: bool = False,
    include_generic: bool = False,
    skip_unconstrained: bool = True,
) -> ty.List[ty.Type["fileformats.core.FileSet"]]:
    """Detect the corresponding file format from a set of file-system paths

    Parameters
    ----------
    fspaths : list[Path]
        file-system paths to detect the format of
    candidates: sequence[FileSet], optional
        the candidates to select from, by default all file formats
    standard_only : bool, optional
        If you only want to return matches from the "standard" IANA types. Only relevant
        if candidates is None, by default False
    skip_unconstrained : bool, optional
        skip formats that aren't constrained by extension, magic number or another check.
        Only relevant if candidates is None

    Returns
    -------
    list[FileSet]
        the file formats that match the given file-system paths
    """
    import fileformats.core.mixin

    fspaths = fspaths_converter(fspaths)
    matches: ty.List[ty.Type["fileformats.core.FileSet"]] = []
    if candidates is None:
        candidates = fileformats.core.FileSet.all_formats
    for frmt in candidates:
        if skip_unconstrained and frmt.unconstrained:
            continue
        namespace = frmt.namespace
        if (
            frmt.matches(fspaths)
            and (not standard_only or namespace in IANA_MIME_TYPE_REGISTRIES)
            and (include_generic or namespace != "generic")
        ):
            matches.append(frmt)
    return matches


def from_mime(
    mime_str: str,
) -> ty.Union[ty.Type["fileformats.core.DataType"], "ty.Type[ty.Union]"]:
    """Resolves a MIME type (or MIME-like) string into the corresponding type

    Parameters
    ----------
    mime_str : str
        the MIME type, or MIME-like (i.e. using the fileformats namespace scheme
        instead of putting all non-standard types into the 'application' registry), string to
        resolve

    Returns
    -------
    datatype : type
        the resolved datatype

    Raises
    ------
    FormatRecognitionError
        if the MIME string does not correspond to a valid file format class
    """
    if mime_str.endswith("?"):
        return from_mime(mime_str[:-1]) | None  # type: ignore[operator,no-any-return,return-value]
    if match := re.match(
        r".*(" + re.escape(LIST_MIME) + "|" + re.escape(TUPLE_MIME) + r")$", mime_str
    ):
        item_mime = mime_str[: -len(match.group(1))]
        if item_mime.startswith("[") and item_mime.endswith("]"):
            item_mime = item_mime[1:-1]
        if match.group(1) == LIST_MIME:
            return list[from_mime(item_mime)]  # type: ignore
        else:
            return tuple[from_mime(item_mime)]  # type: ignore
    if "|" in mime_str:
        return functools.reduce(operator.or_, (from_mime(t) for t in mime_str.split("|")))  # type: ignore
    return fileformats.core.DataType.from_mime(mime_str)


def to_mime(
    datatype: ty.Type["fileformats.core.DataType"], official: bool = True
) -> str:
    """Returns the mime-type or mime-like (i.e. using fileformats namespaces instead
    of putting all non-standard types in the 'application' registry) string corresponding
    to the given datatype

    Parameters
    ----------
    datatype : type
        the datatype to get the mime string for
    official : bool
        whether to use the official mime-type instead of mime-like

    Returns
    -------
    mime_str : str
        the MIME type string if `iana=True`, or MIME-like (i.e. using the fileformats
        namespace scheme instead of putting all non-standard types into the 'application'
        registry if not
    """
    if is_optional(datatype):
        return to_mime(get_optional_type(datatype)) + "?"
    # Handle forward references
    if isinstance(datatype, ty.ForwardRef):
        datatype = datatype.__forward_arg__
    origin = ty.get_origin(datatype)
    if (
        origin is None
        and inspect.isclass(datatype)
        and not issubclass(datatype, fileformats.core.DataType)
    ):
        raise TypeError(
            f"Cannot convert {datatype} to mime-type as it is not a file-set class"
        )
    if official and (origin or datatype.namespace == "field"):
        raise TypeError(
            f"Cannot convert {datatype} to official mime-type as it is not a proper "
            'file-type, please use official=False to convert to "mime-like" string instead'
        )
    if origin in (list, tuple):
        item_mime = to_mime(ty.get_args(datatype)[0], official=official)
        if "," in item_mime:
            item_mime = "[" + item_mime + "]"
        item_mime += LIST_MIME if origin is list else TUPLE_MIME
        return item_mime
    if is_union(datatype):
        return "|".join(to_mime(t, official=official) for t in ty.get_args(datatype))
    if (
        isinstance(datatype, str)
        and datatype.startswith("fileformats.")
        and not official
    ):
        ns, class_name = datatype.split(".")[1:]
        ns = ns.replace("_", "-")
        class_name = to_mime_format_name(class_name)
        return ns + "/" + class_name
    mime: str = datatype.mime_type if official else datatype.mime_like
    if official:
        mime = datatype.mime_type
    else:
        mime = datatype.mime_like
        try:
            from_mime(mime)
        except FormatRecognitionError as e:
            add_exc_note(
                e,
                (
                    f"Cannot create reversible MIME type for {datatype}. Please ensure "
                    "it is imported into a top-level fileformats namespace package "
                    f"'{datatype.namespace}'"
                ),
            )
            raise e
    return mime


def from_paths(
    fspaths: ty.Iterable[Path],
    *candidates: ty.Type["fileformats.core.FileSet"],
    common_ok: bool = False,
    ignore: ty.Optional[str] = None,
    **kwargs: ty.Any,
) -> ty.List["fileformats.core.FileSet"]:
    """Given a list of candidate classes (defaults to all installed in alphabetical order),
    instantiates all possible file-set instances from a collection of file-system paths.

    Note that the order in which the candidates are provided is important as the first
    valid match for each path will be returned.

    Parameters
    ----------
    fspaths : ty.Iterable[Path]
        file-system paths to instantiate file-sets from
    *candidates : tuple[fileformats.core.FileSet]
        the file-set classes to instantiate. If none are provided, then all installed
        filesets will be tried in alphabetical order of their "mime-like" representation.
    common_ok : bool
        whether file-system paths can be used as secondary files in multiple file-sets
    ignore: str, optional
        regular expression pattern for file/directory names to ignore if they aren't
        used in any of the returned file-sets. Any remaining file-paths that are not
        matched by this pattern will cause an error to be raised.
    **kwargs: dict[str, Any]
        keyword arguments passed on to the underlying call to FileSet.from_paths

    Returns
    -------
    list[fileformats.core.FileSet]
        the instantiated file-sets
    """
    if candidates:
        # Unwrap any nested tuples into a flat list of file-setclasses
        unwrapped = []

        def unwrap(candidate: ty.Type["fileformats.core.FileSet"]) -> None:
            if is_union(candidate):
                arg: ty.Type["fileformats.core.FileSet"]
                for arg in ty.get_args(candidate):
                    unwrap(arg)
            else:
                unwrapped.append(candidate)

        for candidate in candidates:
            unwrap(candidate)
        candidates = tuple(unwrapped)
        candidates_str = ", ".join(to_mime(c, official=False) for c in candidates)
    else:
        # Use all installed file-set classes if no candidates are provided, sorted
        # alphabetically to ensure behaviour is consistent between runs
        candidates = tuple(
            sorted(
                fileformats.core.FileSet.subclasses(),
                key=operator.attrgetter("mime_like"),
            )
        )
        candidates_str = "all installed"

    remaining = fspaths
    filesets: ty.List["fileformats.core.FileSet"] = []
    for candidate in candidates:
        fsets, remaining = candidate.from_paths(
            remaining, common_ok=common_ok, **kwargs
        )
        filesets.extend(fsets)
    if ignore:
        ignore_re = re.compile(ignore)
        remaining = [p for p in remaining if not ignore_re.match(p.name)]
    if remaining:
        raise FormatRecognitionError(
            "the following file-system paths were not recognised by any of the "
            f"candidate formats ({candidates_str}):\n"
            + "\n".join(str(p) for p in remaining)
        )
    return filesets


def to_mime_format_name(format_name: str) -> str:
    if "____" in format_name:
        raise FormatDefinitionError(
            f"Cannot convert name of format class {format_name} to mime string as it "
            "contains quadruple underscore, which is undefined behavior (triple underscore "
            "is used to indicate '+' in mime string, double underscores are used as "
            "delimiters between classifiers, and single underscores are used to indicate '.')"
        )
    if format_name.startswith("_"):
        format_name = format_name[1:]
    format_name = format_name[0].lower() + format_name[1:]
    format_name = re.sub("___([A-Z])", lambda m: "+" + m.group(1).lower(), format_name)
    format_name = re.sub("_([A-Z])", lambda m: "." + m.group(1).lower(), format_name)
    format_name = format_name.replace("_.", "..")
    format_name = re.sub("([A-Z])", lambda m: "-" + m.group(1).lower(), format_name)
    return format_name


def from_mime_format_name(format_name: str) -> str:
    if format_name.startswith("x-"):
        format_name = format_name[2:]
    if re.match(r"^[0-9]", format_name):
        format_name = "_" + format_name
    format_name = format_name.capitalize()
    format_name = re.sub(r"\.(\w)", lambda m: "_" + m.group(1).upper(), format_name)
    format_name = re.sub(r"\+(\w)", lambda m: "___" + m.group(1).upper(), format_name)
    format_name = re.sub(r"\+$", "___", format_name)
    format_name = re.sub(r"-(\d)", lambda m: "_" + m.group(1), format_name)
    format_name = re.sub(r"-(\w)", lambda m: m.group(1).upper(), format_name)
    return format_name
