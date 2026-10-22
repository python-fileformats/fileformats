import contextlib
import bz2
import gzip
import io
import lzma
import tempfile
import typing as ty
import zipfile
from pathlib import Path

from fileformats.core import FileSet
from fileformats.core.archive import ZipPath, zip_members
from fileformats.core.decorators import mtime_cached_property, validated_property
from fileformats.core.exceptions import FormatMismatchError
from fileformats.core.fileset import indirect_safe
from fileformats.core.mixin import WithClassifier, WithMagicNumber
from fileformats.generic import BinaryFile


class _ClosesUnderlying:
    """Mixin: also close the file object this stream was layered on top of.

    Cooperative — `super().close()` runs the codec's own close first, then we
    close the handle beneath it. Works through a TextIOWrapper too, since that
    closes its buffer (this object) on close.
    """

    _underlying: ty.IO[bytes]

    def close(self) -> None:
        try:
            super().close()
        finally:
            self._underlying.close()


class _BZ2File(_ClosesUnderlying, bz2.BZ2File):
    def __init__(self, fh: ty.IO[bytes], mode: str) -> None:
        self._underlying = fh
        super().__init__(fh, mode)


class _LZMAFile(_ClosesUnderlying, lzma.LZMAFile):
    def __init__(self, fh: ty.IO[bytes], mode: str) -> None:
        self._underlying = fh
        super().__init__(fh, mode)


class _GzipFile(_ClosesUnderlying, gzip.GzipFile):
    def __init__(self, fh: ty.IO[bytes], mode: str) -> None:
        self._underlying = fh
        super().__init__(fileobj=fh, mode=mode)  # gzip's one difference


CODECS = {
    'bz2': _BZ2File,
    'gzip': _GzipFile,
    'lzma': _LZMAFile
}


class Archive(BinaryFile):
    "Base class for archives (e.g. zip, tar)"

    archived_type: ty.Optional[ty.Type[FileSet]] = None


class Compressed(BinaryFile):
    "Base class for compressed file stream (e.g zip, bzip, xz)"

    archived_type: ty.Optional[ty.Type[FileSet]] = None
    codec: _ClosesUnderlying

    def open_raw(
            self,
            mode: str = "r",
            buffering: int = -1,
            encoding: ty.Optional[str] = None,
            errors: ty.Optional[str] = None,
            newline: ty.Optional[str] = None,
    ) -> ty.Union[ty.IO[str], ty.IO[bytes]]:
        return super().open(mode=mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline)

    def open(
            self,
            mode: str = "r",
            buffering: int = -1,
            encoding: ty.Optional[str] = None,
            errors: ty.Optional[str] = None,
            newline: ty.Optional[str] = None,
            *,
            compression: str = "gzip",
    ) -> ty.Union[ty.IO[str], ty.IO[bytes]]:
        """Open an I/O stream to the compressed file."""
        # The codec operates on bytes, so the layer beneath it must be binary.
        letter = next((c for c in mode if c in "rwxa"), "r")
        fh = super().open(mode=letter + "b", buffering=buffering)
        try:
            stream: ty.IO = self.codec(fh, letter)
        except BaseException:
            fh.close()
            raise

        if "t" in mode:
            try:
                stream = io.TextIOWrapper(
                    stream, encoding=encoding, errors=errors, newline=newline
                )
            except BaseException:
                stream.close()  # cascades to fh
                raise

        return stream


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
    codec = _BZ2File

    @indirect_safe
    @validated_property
    def validate_outer_magic(self):
        with self.open_raw('rb') as fh:
            self._validate_magic_number(
                fh=fh,
                magic_number=BaseBzip.magic_number,
                binary=BaseBzip.binary,
                magic_number_offset=BaseBzip.magic_number_offset,
            )


class BaseGzip(WithMagicNumber, Compressed):
    ext = ".gz"
    magic_number = "1F8B08"
    codec = _GzipFile

    @indirect_safe
    @validated_property
    def validate_outer_magic(self):
        with self.open_raw('rb') as fh:
            self._validate_magic_number(
                fh=fh,
                magic_number=BaseGzip.magic_number,
                binary=BaseGzip.binary,
                magic_number_offset=BaseGzip.magic_number_offset,
            )


class BaseXz(WithMagicNumber, Compressed):
    ext = ".xz"
    magic_number = "FD 37 7A 58 5A 00"
    codec = _LZMAFile

    @indirect_safe
    @validated_property
    def validate_outer_magic(self):
        with self.open_raw('rb') as fh:
            self._validate_magic_number(
                fh=fh,
                magic_number=BaseXz.magic_number,
                binary=BaseXz.binary,
                magic_number_offset=BaseXz.magic_number_offset,
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
    """A zip archive, optionally classified by the type of file-set it contains, e.g.
    ``Zip[DicomSeries]``. The contained file-set can be inspected *without* extracting
    it via ``archived`` (backed by `ZipPath` objects, so only ``@archive_safe``
    properties and extras are available), or materialised on disk with ``extract()``.
    """

    iana_mime = "application/zip"

    @property
    def root(self) -> ZipPath:
        """ReadablePath path to the root of the archive"""
        return ZipPath(zipfile_obj=self.fspath)

    @mtime_cached_property
    def archived(self) -> FileSet:
        """The archived file-set, viewed in place inside the archive"""
        archived_type = self.archived_type or FileSet
        data = self._archived_fspaths(archived_type)
        return archived_type(*data)

    @validated_property
    def _check_archived(self) -> None:
        # Only validate the contents for classified zips, e.g. Zip[DicomSeries]
        if self.archived_type is not None:
            try:
                self.archived
            except FormatMismatchError as e:
                raise FormatMismatchError(
                    f"Contents of {self.fspath} are not a valid "
                    f"{self.archived_type.__name__}: {e}"
                ) from e

    def extract(self, dest_dir: ty.Optional[Path] = None) -> FileSet:
        """Extract the archive and return the contained file-set on the real
        file-system, e.g. to pass to tools that need real paths"""
        if dest_dir is None:
            dest_dir = Path(tempfile.mkdtemp())
        dest_dir = Path(dest_dir).absolute()
        with zipfile.ZipFile(self.fspath) as zf:
            zf.extractall(dest_dir)
        archived_type = self.archived_type or FileSet
        return archived_type(
            *(dest_dir / p.at for p in self._archived_fspaths(archived_type))
        )

    def _archived_fspaths(self, archived_type: ty.Type[FileSet]) -> ty.List[ZipPath]:
        from fileformats.generic import Directory

        if isinstance(archived_type, type) and issubclass(archived_type, Directory):
            tops = {p for p in self.root.iterdir()}
            if len(tops) != 1:
                raise FormatMismatchError(
                    f"Expected a single top-level directory in {self.fspath} for "
                    f"{archived_type.__name__}, found {sorted(str(t) for t in tops)}"
                )
            return list(tops)  # type: ignore[arg-type]
        return zip_members(self.fspath)


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
