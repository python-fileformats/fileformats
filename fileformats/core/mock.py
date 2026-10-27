import typing as ty

from .decorators import classproperty
from .exceptions import FormatDefinitionError
from .typing import FspathsInputType
from .utils import fspaths_converter

if ty.TYPE_CHECKING:
    from .fileset import FileSet


class MockMixin:
    """Strips out validation methods of a class, allowing it to be mocked in a way that
    still satisfies type-checking"""

    _load_kwargs: ty.Dict[str, ty.Any]

    def __init__(
        self,
        fspaths: FspathsInputType,
        metadata: ty.Union[ty.Dict[str, ty.Any], bool, None] = False,
    ):
        self.fspaths = fspaths_converter(fspaths)
        self._metadata = metadata
        self._load_kwargs = {}

    @classproperty  # type: ignore[arg-type]
    def type_name(cls) -> str:
        return cls.mocked.type_name  # type: ignore[no-any-return]

    def __bytes_repr__(self, cache: ty.Dict[str, ty.Any]) -> ty.Iterable[bytes]:
        yield from (str(fspath).encode() for fspath in self.fspaths)

    @classproperty  # type: ignore[arg-type]
    def mocked(cls) -> "FileSet":
        """The "true" class that the mocked class is based on"""
        return next(c for c in cls.__mro__ if not issubclass(c, MockMixin))  # type: ignore[no-any-return, attr-defined]

    @classproperty  # type: ignore[arg-type]
    def namespace(cls) -> str:
        """The "namespace" the format belongs to under the "fileformats" umbrella
        namespace"""
        mro: ty.Tuple[ty.Type] = cls.__mro__  # type: ignore
        for base in mro:
            if issubclass(base, MockMixin):
                continue
            try:
                return base.namespace  # type: ignore
            except FormatDefinitionError:
                pass
        raise FormatDefinitionError(
            f"None of of the bases classes of {cls} ({mro}) have a valid namespace"
        )
