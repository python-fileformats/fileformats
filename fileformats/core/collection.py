import typing as ty
from abc import ABCMeta, abstractmethod
from pathlib import Path

from fileformats.core import FileSet, mtime_cached_property, validated_property
from fileformats.core.decorators import classproperty
from fileformats.core.exceptions import FormatMismatchError
from fileformats.core.utils import get_optional_type


class TypedCollection(FileSet, metaclass=ABCMeta):
    """Base class for collections of files-sets of specific types either in a directory
    or a collection of file paths"""

    content_types: ty.Tuple[
        ty.Union[ty.Type[FileSet], ty.Type[ty.Optional[FileSet]]], ...
    ] = ()

    @property
    @abstractmethod
    def content_fspaths(self) -> ty.Iterable[Path]: ...  # noqa: E704

    @mtime_cached_property
    def contents(self) -> ty.List[FileSet]:
        contnts = []
        for content_type in self.potential_content_types:
            assert content_type
            for p in self.content_fspaths:
                try:
                    contnts.append(content_type([p], **self._load_kwargs))
                except FormatMismatchError:
                    continue
        return contnts

    # @property
    # def last_modified(self) -> int:
    #     """The latest modification time of all files in the set"""
    #     return max(c.last_modified for c in self.contents)

    @validated_property
    def _validate_required_content_types(self) -> None:
        not_found = set(self.required_content_types)
        if not not_found:
            return
        for fspath in self.content_fspaths:
            for content_type in list(not_found):
                if content_type.matches(fspath):
                    not_found.remove(content_type)
                    if not not_found:
                        return
        assert not_found
        raise FormatMismatchError(
            f"Did not find the required content types, {not_found}, in {self}, paths: "
            f"{[str(p) for p in self.content_fspaths]}"
        )

    @classproperty  # type: ignore[arg-type]
    def potential_content_types(cls) -> ty.Tuple[ty.Type[FileSet], ...]:
        content_types: ty.List[ty.Type[FileSet]] = []
        for content_type in cls.content_types:  # type: ignore[assignment]
            content_types.append(get_optional_type(content_type))  # type: ignore[arg-type]
        return tuple(content_types)

    @classproperty  # type: ignore[arg-type]
    def required_content_types(cls) -> ty.Tuple[ty.Type[FileSet], ...]:
        content_types: ty.List[ty.Type[FileSet]] = []
        for content_type in cls.content_types:  # type: ignore[assignment]
            if ty.get_origin(content_type) is None:
                content_types.append(content_type)  # type: ignore[arg-type]
        return tuple(content_types)

    @classproperty  # type: ignore[arg-type]
    def unconstrained(cls) -> bool:
        """Whether the file-format is unconstrained by extension, magic number or another
        constraint"""
        return super().unconstrained and not cls.content_types

    def __len__(self) -> int:
        return len(self.contents)
