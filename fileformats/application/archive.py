import contextlib
import bz2
import gzip
import lzma
import typing as ty

from fileformats.core import FileSet
from fileformats.core.decorators import validated_property
from fileformats.core.mixin import WithClassifier, WithMagicNumber
from fileformats.generic import BinaryFile


class Archive(BinaryFile):
    "Base class for archives (e.g. zip, tar)"

    archived_type: ty.Optional[ty.Type[FileSet]] = None


class Compressed(BinaryFile):
    "Base class for compressed file stream (e.g zip, bzip, xz)"

    archived_type: ty.Optional[ty.Type[FileSet]] = None


class WithArchiveClassifiers(WithClassifier):
    "Base class for compressed archives"

    classifiers_attr_name = "archived_type"
    allowed_classifiers = (FileSet,)
    generically_classifiable = True


# Compressed formats
class BaseZip(WithMagicNumber, Archive):
    ext = ".zip"
    magic_number = "504B0304"


class BaseBzip(WithMagicNumber, Compressed):
    ext = ".bzip"
    magic_number = "425a"

    @validated_property
    def validate_outer_magic(self):
        with super().open('rb') as fh:
            self._validate_magic_number(
                fh=fh,
                magic_number=BaseBzip.magic_number,
                binary=BaseBzip.binary,
                magic_number_offset=BaseBzip.magic_number_offset,
            )

    @contextlib.contextmanager
    def open(
            self,
            mode: str = "r",
            buffering: int = -1,
            encoding: ty.Optional[str] = None,
            errors: ty.Optional[str] = None,
            newline: ty.Optional[str] = None,
    ) -> ty.Union[ty.IO[str], ty.IO[bytes]]:
        """Open a I/O stream to the file"""
        with super().open(mode=mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline) as fh:
            yield bz2.open(
                fh,
                mode=mode,
                encoding=encoding,
                errors=errors,
                newline=newline,
            )


class BaseGzip(WithMagicNumber, Compressed):
    ext = ".gz"
    magic_number = "1F8B08"

    @validated_property
    def validate_outer_magic(self):
        with super().open('rb') as fh:
            self._validate_magic_number(
                fh=fh,
                magic_number=BaseGzip.magic_number,
                binary=BaseGzip.binary,
                magic_number_offset=BaseGzip.magic_number_offset,
            )

    @contextlib.contextmanager
    def open(
            self,
            mode: str = "r",
            buffering: int = -1,
            encoding: ty.Optional[str] = None,
            errors: ty.Optional[str] = None,
            newline: ty.Optional[str] = None,
    ) -> ty.Union[ty.IO[str], ty.IO[bytes]]:
        """Open a I/O stream to the file"""
        with super().open(mode=mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline) as fh:
            yield gzip.open(
                self.fspath,
                mode=mode,
                encoding=encoding,
                errors=errors,
                newline=newline,
            )


class BaseXz(WithMagicNumber, Compressed):
    ext = ".xz"
    magic_number = "FD 37 7A 58 5A 00"

    @validated_property
    def validate_outer_magic(self):
        with super().open('rb') as fh:
            self._validate_magic_number(
                fh=fh,
                magic_number=BaseXz.magic_number,
                binary=BaseXz.binary,
                magic_number_offset=BaseXz.magic_number_offset,
            )

    @contextlib.contextmanager
    def open(
            self,
            mode: str = "r",
            buffering: int = -1,
            encoding: ty.Optional[str] = None,
            errors: ty.Optional[str] = None,
            newline: ty.Optional[str] = None,
    ) -> ty.Union[ty.IO[str], ty.IO[bytes]]:
        """Open a I/O stream to the file"""
        with super().open(mode=mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline) as fh:
            yield lzma.open(
                self.fspath,
                mode=mode,
                encoding=encoding,
                errors=errors,
                newline=newline,
            )


class BaseTar(WithMagicNumber, Archive):
    ext = ".tar"
    magic_number = "7573746172"
    magic_number_offset = 257


class BaseTarGzip(WithMagicNumber, Archive):
    # FIXME: Should capture the relationship to Gzip and Tar somehow, but a bit
    # tricky to get it right
    ext = ".tar.gz"
    magic_number = "1F8B08"
    alternate_exts = (".tgz",)


class Zip(WithArchiveClassifiers, BaseZip):
    iana_mime = "application/zip"


class Bzip(WithArchiveClassifiers, BaseBzip):
    iana_mime = "application/bzip"


class Gzip(WithArchiveClassifiers, BaseGzip):
    iana_mime = "application/gzip"


class Xz(WithArchiveClassifiers, BaseXz):
    iana_mime = "application/x-xz"


class Tar(WithArchiveClassifiers, BaseTar):
    iana_mime = "application/x-tar"


class TarGzip(WithArchiveClassifiers, BaseTarGzip):
    iana_mime = "application/x-tar+gzip"
