"""Adds support for "field" data types

While not "file-formats", in some workflows, particularly when interacting with a data
store such as in Arcana, it is useful to interchangeably interact with file and field
data, so the classes in this module are provided to support these use cases.
"""

import decimal
import typing as ty

from fileformats.core import Field, FieldPrimitive, __version__  # noqa: F401
from fileformats.core.exceptions import FormatMismatchError
from fileformats.core.mixin import WithClassifier

ValueType = ty.TypeVar("ValueType")
PrimitiveType = ty.TypeVar("PrimitiveType", bound=FieldPrimitive)


class Singular(Field[ValueType, PrimitiveType]):
    pass


class LogicalMixin:
    def __bool__(self) -> bool:
        return bool(self.value)  # type: ignore

    def __and__(self, other: "LogicalMixin") -> bool:
        return self.value and other.value  # type: ignore

    def __or__(self, other: "LogicalMixin") -> bool:
        return self.value or other.value  # type: ignore

    def __not__(self) -> bool:
        return not self.value  # type: ignore

    def __invert__(self) -> bool:
        return not self.value  # type: ignore


class ScalarMixin(LogicalMixin, Field[ValueType, PrimitiveType]):
    value: ValueType

    def __add__(self, other: PrimitiveType) -> PrimitiveType:
        return self.value + other  # type: ignore

    def __sub__(self, other: PrimitiveType) -> PrimitiveType:
        return self.value - other  # type: ignore

    def __mul__(self, other: PrimitiveType) -> PrimitiveType:
        return self.value * other  # type: ignore

    def __truediv__(self, other: PrimitiveType) -> PrimitiveType:
        return self.value / other  # type: ignore

    def __floordiv__(self, other: PrimitiveType) -> PrimitiveType:
        return self.value // other  # type: ignore

    def __mod__(self, other: PrimitiveType) -> PrimitiveType:
        return self.value % other  # type: ignore

    def __pow__(self, other: PrimitiveType) -> PrimitiveType:
        return self.value**other  # type: ignore

    def __neg__(self) -> PrimitiveType:
        return -self.value  # type: ignore

    def __pos__(self) -> PrimitiveType:
        return +self.value  # type: ignore

    def __abs__(self) -> PrimitiveType:
        return abs(self.value)  # type: ignore


class Text(Singular[str, str]):
    value: str

    primitive = str

    def __init__(self, value: ty.Any):
        try:
            self.value = str(value)
        except ValueError as e:
            raise FormatMismatchError(str(e)) from None

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f'{self.type_name}("{self.value}")'

    def __str__(self) -> str:
        return self.value

    def __fspath__(self) -> str:
        return self.value


class Integer(Singular[int, int], ScalarMixin[int, int]):
    value: int

    primitive = int

    def __init__(self, value: ty.Any):
        if isinstance(value, float):
            raise FormatMismatchError(
                f"Cannot convert float ({value}) to integer field without potential loss "
                "of information"
            )
        try:
            self.value = int(value)
        except ValueError as e:
            raise FormatMismatchError(str(e)) from None

    def __int__(self) -> int:
        return self.value

    def __float__(self) -> float:
        return float(self.value)

    def __bool__(self) -> bool:
        return bool(self.value)

    def __hash__(self) -> int:
        return hash(self.value)


class Decimal(Singular[decimal.Decimal, float], ScalarMixin[decimal.Decimal, float]):
    value: decimal.Decimal

    primitive = float

    def __init__(self, value: ty.Any):
        if isinstance(value, Decimal):
            self.value = value.value
        try:
            self.value = (
                value.value if isinstance(value, Decimal) else decimal.Decimal(value)
            )
        except decimal.InvalidOperation as e:
            raise FormatMismatchError(str(e)) from None

    def __float__(self) -> float:
        return float(self.value)

    def __bool__(self) -> bool:
        return bool(self.value)

    def __hash__(self) -> int:
        return hash(self.value)


class Boolean(Singular[bool, bool], LogicalMixin):
    primitive = bool

    value: bool

    def __init__(self, value: ty.Any):
        if isinstance(value, str):
            if value.lower() in ("true", "1", "yes"):
                value = True
            elif value.lower() in ("false", "0", "no"):
                value = False
            else:
                raise FormatMismatchError(
                    f"Cannot convert string '{value}' to boolean value"
                )
        else:
            try:
                value = bool(value)
            except ValueError as e:
                raise FormatMismatchError(str(e)) from None
        assert isinstance(value, bool)
        self.value = value

    def __str__(self) -> str:
        return str(self.value).lower()

    def __bool__(self) -> bool:
        return self.value

    def __hash__(self) -> int:
        return hash(self.value)


ItemType = ty.TypeVar("ItemType", bound=ty.Union[decimal.Decimal, int, float, bool])


class Array(
    WithClassifier,
    Field[ty.Sequence[ItemType], ty.Sequence[ItemType]],
    ty.Sequence[ItemType],
):
    # WithClassifiers class attrs
    classifiers_attr_name: str = "item_type"
    allowed_classifiers: ty.Tuple[ty.Type[Singular[ty.Any, ty.Any]]] = (Singular,)
    item_type: ty.Optional[ty.Type[Singular[ItemType, ty.Any]]] = None

    primitive = tuple  # type: ignore[assignment]

    value: ty.Tuple[ItemType, ...]

    def __init__(self, value: ty.Union[str, ty.Sequence[ty.Any]]):

        if isinstance(value, str):
            if (value.startswith("[") and value.endswith("]")) or (
                value.startswith("(") and value.endswith(")")
            ):
                value = value[1:-1]
            elif (
                value.startswith("[")
                or value.endswith("]")
                or value.startswith("(")
                or value.endswith(")")
            ):
                raise FormatMismatchError(f"Unmatched brackets in array field {value}")
            value = tuple(v.strip() for v in value.split(","))
        else:
            try:
                value = tuple(value)
            except ValueError as e:
                raise FormatMismatchError(str(e)) from None
        assert isinstance(value, tuple)
        # Ensure items are of the correct type
        # if self.item_type is not None:
        if self.item_type is not None:
            parsed_value: ty.Tuple[ItemType, ...] = tuple(
                self.item_type(i).value for i in value
            )
        else:
            parsed_value = value
        self.value = parsed_value

    def __str__(self) -> str:
        return (
            "["
            + ",".join(
                (
                    str(self.item_type(i)) if self.item_type is not None else i  # type: ignore
                )  # pylint: disable=not-callable
                for i in self.value
            )
            + "]"
        )

    def __iter__(self) -> ty.Iterator[ty.Any]:
        return iter(self.value)

    def __hash__(self) -> int:
        return hash(self.value)

    def __len__(self) -> int:
        return len(self.value)

    @ty.overload
    def __getitem__(self, index: int) -> ItemType: ...  # noqa: E704

    @ty.overload
    def __getitem__(self, slice: slice) -> ty.Sequence[ItemType]: ...  # noqa: E704

    def __getitem__(self, key: ty.Any) -> ty.Any:
        return self.value[key]
