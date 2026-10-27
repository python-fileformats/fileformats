import io
import typing as ty
from pathlib import Path

from fileformats.core.decorators import (
    classproperty,
    mtime_cached_property,
    validated_property,
)
from fileformats.core.exceptions import (
    FormatMismatchError,
    UnconstrainedExtensionException,
)
from fileformats.core.fileset import FileSet

from .fsobject import FsObject


class File(FsObject):
    """Generic file type"""

    @validated_property
    def fspath(self) -> Path:
        fspath = self.select_by_ext()
        if not fspath:
            raise FormatMismatchError(
                f"No paths in {type(self)} ({list(self.fspaths)}) "
                f"match extension {self.ext}"
            )
        if fspath.is_dir():
            # fspath is guaranteed to exist
            raise FormatMismatchError(
                f'Path that matches extension of {type(self)}, "{fspath}", '
                f"is a directory not a file"
            )
        return fspath

    @classproperty  # type: ignore[arg-type]
    def unconstrained(cls) -> bool:
        """Whether the file-format is unconstrained by extension, magic number or another
        constraint"""
        return super().unconstrained and (cls.ext is None or None in cls.alternate_exts)

    def is_dir(self) -> bool:
        return False

    def is_file(self) -> bool:
        return True

    @classmethod
    def copy_ext(
        cls,
        old_path: Path,
        new_path: Path,
        decomposition_mode: FileSet.ExtensionDecomposition = FileSet.ExtensionDecomposition.none,
    ) -> Path:
        """Copy extension from the old path to the new path, ensuring that all
        of the extension is used (e.g. 'my.gz' instead of 'gz')

        Parameters
        ----------
        old_path: Path or str
            The path from which to copy the extension from
        new_path: Path or str
            The path to append the extension to
        decomposition_mode : FileSet.ExtensionDecomposition, optional
            if the file doesn't have an explicit extension, how to interpret "." within
            the filename

        Returns
        -------
        Path
            The new path with the copied extension
        """
        if not cls.matching_exts([old_path], [cls.ext]):
            raise FormatMismatchError(
                f"Extension of old path ('{str(old_path)}') does not match that "
                f"of file, '{cls.ext}'"
            )
        suffix = (
            cls.ext
            if cls.ext
            else cls.decompose_fspath(old_path, mode=decomposition_mode)[-1]
        )
        return Path(new_path).with_suffix(suffix)

    @mtime_cached_property
    def raw_contents(self) -> ty.Union[str, bytes]:
        return self.read_contents()

    def open(
        self,
        mode: str = "r",
        buffering: int = -1,
        encoding: ty.Optional[str] = None,
        errors: ty.Optional[str] = None,
        newline: ty.Optional[str] = None,
    ) -> ty.Union[ty.IO[str], ty.IO[bytes]]:
        """Open a I/O stream to the file"""
        return self.fspath.open(
            mode=mode,
            buffering=buffering,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )

    def read_contents(
        self, size: ty.Optional[int] = None, offset: int = 0
    ) -> ty.Union[str, bytes]:
        with self.open("rb" if getattr(self, "binary", True) else "r") as f:
            if offset:
                f.seek(offset, (io.SEEK_SET if offset >= 0 else io.SEEK_END))
            contents = f.read(size) if size else f.read()
        return contents

    @property
    def actual_ext(self) -> str:
        "The actual file extension (out of the primary  and alternate extensions possible)"
        constrained_exts = [
            e for e in self.possible_exts if e is not None
        ]  # strip out unconstrained
        matching = [e for e in constrained_exts if self.fspath.name.endswith(e)]
        if not matching:
            raise UnconstrainedExtensionException(
                f"Cannot determine actual extension of {self.fspath}, as it doesn't "
                f"match any of the defined extensions {constrained_exts} "
                "(i.e. matches the None extension)"
            )
        # Return the longest matching extension, useful for optional extensions
        return sorted(matching, key=len)[-1]  # type: ignore[no-any-return]

    @property
    def stem(self) -> str:
        if self.actual_ext:
            stem = self.fspath.name[: -len(self.actual_ext)]
        else:
            stem = self.fspath.name
        return stem

    def read_bytes(self) -> bytes:
        return self.fspath.read_bytes()


class UnicodeFile(File):

    binary = False

    def open(
        self,
        mode: str = "r",
        buffering: int = -1,
        encoding: ty.Optional[str] = None,
        errors: ty.Optional[str] = None,
        newline: ty.Optional[str] = None,
    ) -> ty.IO[str]:
        """Open a I/O stream to the file"""
        if mode.endswith("b"):
            raise ValueError(
                f"Cannot open text file with binary mode '{mode}'. If you need to do this "
                "access the underlying path directly, e.g. my_file.fspath.open(mode='rb')"
            )
        io: ty.IO[str] = super().open(  # type: ignore[assignment]
            mode=mode,
            buffering=buffering,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )
        return io

    def read_contents(self, size: ty.Optional[int] = None, offset: int = 0) -> str:
        contents: str = super().read_contents(size=size, offset=offset)  # type: ignore[assignment]
        return contents

    def read_text(self, **kwargs: ty.Any) -> str:
        return self.fspath.read_text(**kwargs)

    def write_text(
        self,
        data: str,
        **kwargs: ty.Any,
    ) -> int:  # Returns number of characters written
        return self.fspath.write_text(data=data, **kwargs)


class BinaryFile(File):

    binary = True

    def open(
        self,
        mode: str = "r",
        buffering: int = -1,
        encoding: ty.Optional[str] = None,
        errors: ty.Optional[str] = None,
        newline: ty.Optional[str] = None,
    ) -> ty.IO[bytes]:
        """Open a I/O stream to the file"""
        if not mode.endswith("b"):
            mode += "b"
        io: ty.IO[bytes] = super().open(  # type: ignore[assignment]
            mode=mode,
            buffering=buffering,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )
        return io

    def read_contents(self, size: ty.Optional[int] = None, offset: int = 0) -> bytes:
        contents: bytes = super().read_contents(size=size, offset=offset)  # type: ignore[assignment]
        return contents
