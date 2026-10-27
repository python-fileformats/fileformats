"""`ConvertibleTo[Format]` annotation for the formats that can be converted to a file
format.

``ConvertibleTo[Png]`` evaluates at runtime to ``Png.convertible_from()``, which is::

    Annotated[<union of formats>, ConvertibleToMarker(Png)]

i.e. the union of the formats that can be converted to ``Png`` by the converters
installed in the current environment, while anything that reads signatures can recover
the target format with ``ConvertibleToMarker.from_hint(hint).format``. Static type
checkers see it as ``Any``.

It is written to MIME-like strings as "<namespace>/<format>+convertible-to" by
`to_mime`, so the union is resolved again from the converters that are installed in the
environment the string is read in.
"""

import inspect
import typing as ty
from dataclasses import dataclass

from .loaded import FormatMarker

if ty.TYPE_CHECKING:
    from typing_extensions import TypeAliasType

__all__ = ["ConvertibleTo", "ConvertibleToMarker"]


@dataclass(frozen=True)
class ConvertibleToMarker(FormatMarker):
    """Metadata attached to an ``Annotated`` hint recording the format that the
    annotated types can be converted to"""

    # Appended to the MIME-like string of the format by `to_mime`
    mime_suffix: ty.ClassVar[str] = "+convertible-to"

    def hint(self) -> ty.Any:
        """The hint for the marker, resolved from the converters that are currently
        registered, which may have changed since the hint was created"""
        return self.format.convertible_from()

    def resolve(self) -> ty.Any:
        """The format, or union of formats, that can be converted to the format with
        the converters that are currently registered, i.e. `hint` without the
        annotation"""
        return ty.get_args(self.hint())[0]


if ty.TYPE_CHECKING:
    # Checkers can't evaluate __class_getitem__, so give them a generic alias to Any,
    # see `Loaded`
    FormatT = ty.TypeVar("FormatT")
    ConvertibleTo = TypeAliasType("ConvertibleTo", ty.Any, type_params=(FormatT,))
else:

    class ConvertibleTo:
        """``ConvertibleTo[Format]`` -> ``Format.convertible_from()``, i.e.
        ``Annotated[<union of formats>, ConvertibleToMarker(Format)]``"""

        def __new__(cls, *args: ty.Any, **kwargs: ty.Any) -> ty.NoReturn:
            raise TypeError(
                "ConvertibleTo is only for annotations, use Format.convert()"
            )

        def __class_getitem__(cls, fmt: ty.Any) -> ty.Any:
            if isinstance(fmt, ty.TypeVar):
                return ty.Any

            from .fileset import FileSet

            if not (inspect.isclass(fmt) and issubclass(fmt, FileSet)):
                raise TypeError(
                    f"ConvertibleTo[...] requires a FileSet subclass, not {fmt!r}"
                )
            return ConvertibleToMarker(fmt).hint()
