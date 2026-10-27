from __future__ import annotations

import typing as ty

from .datatype import DataType
from .decorators import classproperty
from .exceptions import FormatMismatchError

ValueType = ty.TypeVar("ValueType")
PrimitiveType = ty.TypeVar("PrimitiveType")


class Field(ty.Generic[ValueType, PrimitiveType], DataType):
    """Base class for all field formats"""

    value: ValueType
    primitive: ty.Type[PrimitiveType]
    is_field = True
    metadata: None = None  # for duck-typing with FileSet

    def __init__(self, value: ValueType):
        self.value = value

    def __eq__(self, field: object) -> bool:
        return (
            isinstance(field, Field)
            and self.mime_like == field.mime_like
            and self.value == field.value
        )

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return hash((self.mime_like, self.value))

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return f"{self.type_name}({str(self)})"

    @classproperty  # type: ignore[arg-type]
    def all_fields(
        cls,
    ) -> ty.List[ty.Type["Field[ty.Any, ty.Any]"]]:
        """Iterate over all field formats in fileformats.* namespaces"""
        import fileformats.field  # noqa

        if cls._all_fields is None:
            cls._all_fields = [f for f in Field.subclasses() if getattr(f, "primitive", None) is not None]  # type: ignore
        return cls._all_fields

    def to_primitive(self) -> PrimitiveType:
        return self.primitive(self)  # type: ignore

    @classmethod
    def from_primitive(cls, dtype: type) -> ty.Type[Field[ty.Any, ty.Any]]:
        try:
            datatype: ty.Type[Field[ty.Any, ty.Any]] = next(
                iter(f for f in cls.all_fields if f.primitive is dtype)
            )
        except StopIteration as e:
            field_types_str = ", ".join(t.__name__ for t in cls.all_fields)
            raise FormatMismatchError(
                f"{dtype} doesn't not correspond to a valid fileformats field type "
                f"({field_types_str})"
            ) from e
        return datatype

    _all_fields: ty.Optional[ty.List[ty.Type["Field[ty.Any, ty.Any]"]]] = None
    type: type  # Put this at the bottom to avoid name clash with built-in type
