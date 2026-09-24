import typing as ty
from pathlib import Path

from fileformats.core.collection import TypedCollection
from fileformats.core.decorators import mtime_cached_property, validated_property
from fileformats.core.exceptions import FormatMismatchError
from fileformats.core.fileset import FILE_CHUNK_LEN_DEFAULT, FileSet
from fileformats.core.mixin import WithClassifiers
from fileformats.core.typing import CryptoMethod

from .file import File
from .fsobject import FsObject


class Directory(FsObject):
    """Base directory to be overridden by subtypes that represent directories but don't
    want to inherit content type "qualifers" (i.e. most of them)"""

    content_types: ty.Tuple[ty.Type[FileSet], ...] = ()

    @validated_property
    def fspath(self) -> Path:
        # fspaths are checked for existence with the exception of mock classes
        dirs = [p for p in self.fspaths if not p.is_file()]
        if not dirs:
            raise FormatMismatchError(f"No directory paths provided {repr(self)}")
        if len(dirs) > 1:
            raise FormatMismatchError(
                f"More than one directory path provided {dirs} to {repr(self)}"
            )
        return dirs[0]

    @mtime_cached_property
    def contents(self) -> ty.List[ty.Union[File, "Directory"]]:
        contents: ty.List[ty.Union[File, Directory]] = []
        for p in self.fspath.iterdir():
            if p.is_dir():
                contents.append(Directory(p))
            else:
                contents.append(File(p))
        return contents

    def is_dir(self) -> bool:
        return True

    def is_file(self) -> bool:
        return False

    def hash_files(
        self,
        crypto: CryptoMethod = None,
        mtime: bool = False,
        chunk_len: int = FILE_CHUNK_LEN_DEFAULT,
        relative_to: ty.Optional[Path] = None,
        ignore_hidden_files: bool = False,
        ignore_hidden_dirs: bool = False,
    ) -> ty.Dict[str, str]:
        if relative_to is None:
            relative_to = self.fspath
        return super().hash_files(
            crypto=crypto,
            mtime=mtime,
            chunk_len=chunk_len,
            relative_to=relative_to,
            ignore_hidden_files=ignore_hidden_files,
            ignore_hidden_dirs=ignore_hidden_dirs,
        )

    @property
    def content_fspaths(self) -> ty.Iterable[Path]:
        return self.fspath.iterdir()

    # Duck-type Path methods

    def __div__(self, other: ty.Union[str, Path]) -> Path:
        return self.fspath / other

    def glob(self, pattern: str) -> ty.Iterator[Path]:
        return self.fspath.glob(pattern)

    def rglob(self, pattern: str) -> ty.Iterator[Path]:
        return self.fspath.rglob(pattern)

    def joinpath(self, other: ty.Union[str, Path]) -> Path:
        return self.fspath.joinpath(other)

    def iterdir(self) -> ty.Iterator[Path]:
        return self.fspath.iterdir()


class TypedDirectory(TypedCollection, Directory):  # type: ignore[misc]
    """Directory that must contain a specific set of content types. Only files that match
    the content types will be considered as contents in the `contents` property.

    Class Attributes
    ----------------
    content_types: ty.Tuple[FileSet, ...]
        the content types that are expected to be found within the directory
    """

    @property
    def content_fspaths(self) -> ty.Iterable[Path]:
        return self.fspath.iterdir()


class DirectoryOf(WithClassifiers, TypedDirectory):  # type: ignore[misc]
    """Generic directory classified by the formats of its contents"""

    # WithClassifiers-required class attrs
    classifiers_attr_name = "content_types"
    allowed_classifiers = (FileSet,)
    allow_optional_classifiers = True
    generically_classifiable = True
