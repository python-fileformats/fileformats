"""`Loaded[Format]` annotations for in-memory data loaded from a file format.

``Loaded[Json]`` evaluates at runtime to::

    Annotated[Json.loaded_type, LoadedMarker(Json)]

so ``Json.load()`` still returns a plain ``dict``, while anything that reads
signatures (pydra, xnat-ingest, docs tooling) can recover the source format with
``LoadedMarker.from_hint(hint).format``. Static type checkers see ``Loaded[X]`` as
``Any``.

`FileSet.loaded_type` is either a type or, for types from optional dependencies, a
dotted path (e.g. ``"pydicom.FileDataset"``) that is only imported if the package is
installed.
"""

import inspect
import pkgutil
import types
import typing as ty
from dataclasses import dataclass
from typing import Annotated

if ty.TYPE_CHECKING:
    from typing_extensions import TypeAliasType

    from .fileset import FileSet

__all__ = ["Loaded", "LoadedMarker", "check_loaded"]


MarkerT = ty.TypeVar("MarkerT", bound="FormatMarker")


@dataclass(frozen=True)
class FormatMarker:
    """Base for metadata attached to an ``Annotated`` hint recording the format it was
    created from, e.g. ``Loaded[X]`` or ``ConvertibleTo[X]``"""

    format: ty.Type["FileSet"]

    @classmethod
    def from_hint(cls: ty.Type[MarkerT], tp: ty.Any) -> ty.Optional[MarkerT]:
        """Return the marker of a ``Loaded[X]`` or ``Loaded[X] | None`` hint, or None
        for any other hint.

        Hints must be obtained with ``get_type_hints(..., include_extras=True)`` or
        ``inspect.signature(..., eval_str=True)``, otherwise ``Annotated`` is stripped.
        """
        if ty.get_origin(tp) in (ty.Union, types.UnionType):
            args = [a for a in ty.get_args(tp) if a is not type(None)]
            if len(args) != 1:
                return None
            tp = args[0]
        return cls._from_annotated(tp)

    @classmethod
    def all_from_hint(
        cls: ty.Type[MarkerT], tp: ty.Any
    ) -> ty.Optional[ty.List[MarkerT]]:
        """Return the markers of a union of ``Loaded[X]`` hints, optionally including
        None (e.g. ``Loaded[X] | Loaded[Y] | None``), in the order they appear, which
        callers can use to find the formats that data can be loaded from. A single
        ``Loaded[X]`` hint returns a one-item list.

        Returns None if any member of the union (other than None) isn't a
        ``Loaded[X]`` hint, or for any other hint.

        Hints must be obtained with ``get_type_hints(..., include_extras=True)`` or
        ``inspect.signature(..., eval_str=True)``, otherwise ``Annotated`` is stripped.
        """
        if ty.get_origin(tp) in (ty.Union, types.UnionType):
            args = [a for a in ty.get_args(tp) if a is not type(None)]
        else:
            args = [tp]
        markers = [cls._from_annotated(a) for a in args]
        if not markers or any(m is None for m in markers):
            return None
        return markers  # type: ignore[return-value]

    @classmethod
    def _from_annotated(cls: ty.Type[MarkerT], tp: ty.Any) -> ty.Optional[MarkerT]:
        if ty.get_origin(tp) is Annotated:
            for meta in tp.__metadata__:
                if isinstance(meta, cls):
                    return meta
        return None


@dataclass(frozen=True)
class LoadedMarker(FormatMarker):
    """Metadata attached to an ``Annotated`` hint recording the source format"""

    def accepts(self, fmt: ty.Type["FileSet"]) -> bool:
        """Whether data loaded from `fmt` satisfies this marker (covariant)"""
        return issubclass(fmt, self.format)


def resolve_loaded_type(tp: ty.Any) -> ty.Any:
    """Resolve a dotted-path string such as "pydicom.FileDataset" to the object it
    names, or ``Any`` if its package isn't installed. Non-strings pass through."""
    if not isinstance(tp, str):
        return tp
    try:
        return pkgutil.resolve_name(tp)
    except (ImportError, AttributeError, ValueError):
        return ty.Any


def _runtime_classes(tp: ty.Any) -> ty.Optional[ty.Tuple[type, ...]]:
    """Reduce a hint to classes usable with isinstance, None if unconstrained"""
    if tp is ty.Any or isinstance(tp, (str, ty.TypeVar)):
        return None
    if ty.get_origin(tp) in (ty.Union, types.UnionType):
        classes: ty.List[type] = []
        for arg in ty.get_args(tp):
            sub = _runtime_classes(arg)
            if sub is None:
                return None
            classes.extend(sub)
        return tuple(classes)
    origin = ty.get_origin(tp) or tp
    return (origin,) if inspect.isclass(origin) else None


def check_loaded(fmt: ty.Type["FileSet"], data: ty.Any) -> None:
    """Shallow check that `data` is the kind of object `fmt.load()` produces,
    e.g. at the top of `save()` or when pydra coerces a `Loaded[X]` input.
    Skipped when the loaded type is unknown or not runtime-checkable."""
    classes = _runtime_classes(resolve_loaded_type(fmt.loaded_type))
    if classes and not isinstance(data, classes):
        raise TypeError(
            f"Expected data loaded from {fmt.type_name} "
            f"({' | '.join(c.__name__ for c in classes)}), got {type(data).__name__}"
        )


if ty.TYPE_CHECKING:
    # Checkers can't evaluate __class_getitem__, so give them a generic alias to
    # Any: `Loaded[Json]` is accepted everywhere and accepts anything.
    # No bound: a forward ref to FileSet here is circular and crashes mypy
    FormatT = ty.TypeVar("FormatT")
    Loaded = TypeAliasType("Loaded", ty.Any, type_params=(FormatT,))
else:

    class Loaded:
        """``Loaded[Format]`` -> ``Annotated[<loaded type>, LoadedMarker(Format)]``"""

        def __new__(cls, *args: ty.Any, **kwargs: ty.Any) -> ty.NoReturn:
            raise TypeError("Loaded is only for annotations, use Format.load()")

        def __class_getitem__(cls, fmt: ty.Any) -> ty.Any:
            # `Loaded[Self]` in FileSet.load/save is resolved against the format an
            # extra implementation is registered for when its signature is checked.
            # Handled before importing FileSet, as on Python < 3.14 the annotations
            # in the FileSet class body are evaluated before FileSet is defined
            if fmt is ty.Self:
                return Annotated[ty.Any, LoadedMarker(fmt)]
            if isinstance(fmt, ty.TypeVar):
                return ty.Any

            from .fileset import FileSet

            if not (inspect.isclass(fmt) and issubclass(fmt, FileSet)):
                raise TypeError(f"Loaded[...] requires a FileSet subclass, not {fmt!r}")
            return Annotated[resolve_loaded_type(fmt.loaded_type), LoadedMarker(fmt)]
