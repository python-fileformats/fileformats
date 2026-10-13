"""Support for viewing file-sets stored inside archives (e.g. ``Zip[DicomSeries]``)
without extracting them to disk.

The design rests on three pieces:

* :class:`ArchivePath` - a path to a member of an archive. It implements the
  :class:`importlib.resources.abc.Traversable` interface (``open``, ``iterdir``,
  ``is_file``, ``name``, ``/`` ...) plus a ``stat()`` that reports the *archive's*
  modification time (so ``mtime_cached_property`` still works). It deliberately does
  NOT behave as an ``os.PathLike``: ``os.fspath()`` raises :class:`ArchiveAccessError`,
  which is the safety net that stops archive members being handed to external tools.

* :func:`archive_safe` - a marker for validated properties, methods and extra
  implementations that only touch ``self.fspath``/``self.fspaths`` through the
  ``Traversable`` interface (typically ``with self.open() as f: ...``).

* Gating - when a ``FileSet`` is built from ``ArchivePath`` objects (see
  ``FileSet.is_archived``), only ``archive_safe`` validated properties are checked and
  only ``archive_safe`` extra implementations may be dispatched to. Anything else must
  go through an explicit ``extract()`` / ``convert()``.
"""

import os
import stat as stat_module
import typing as ty
import zipfile
from pathlib import Path, PurePosixPath

from .exceptions import FileFormatsError

ARCHIVE_SAFE_FLAG = "__fileformats_archive_safe__"

T = ty.TypeVar("T")


class ArchiveAccessError(FileFormatsError):
    """Raised when an operation that needs a real file-system path is attempted on a
    file-set that lives inside an archive"""


def archive_safe(obj: T) -> T:
    """Mark a validated property, method or extra implementation as safe to run on a
    file-set whose paths are :class:`ArchivePath` objects.

    Safe code may only use the ``Traversable`` subset of the path API on
    ``self.fspath``/``self.fspaths`` (``open``, ``read_bytes``, ``iterdir``,
    ``is_file``, ``is_dir``, ``name``, ``joinpath``/``/``) or ``self.open()``. It must
    not call ``os.fspath``/``str`` on the path and pass it to anything else.

    Can be stacked with ``@validated_property``/``@property`` (in either order) and with
    ``@extra_implementation`` (place it *below* ``@extra_implementation`` so the flag is
    set on the function that gets registered).
    """
    target = obj.fget if isinstance(obj, property) else obj  # type: ignore[attr-defined]
    setattr(target, ARCHIVE_SAFE_FLAG, True)
    return obj


def as_path(p: ty.Any) -> ty.Union[Path, "ArchivePath"]:
    """Like ``Path(p)`` but leaves `ArchivePath` objects untouched. Core code that
    normalises paths should use this instead of ``Path(...)``"""
    return p if isinstance(p, ArchivePath) else Path(p)


def is_archive_safe(obj: ty.Any) -> bool:
    if isinstance(obj, property):
        obj = obj.fget
    return bool(getattr(obj, ARCHIVE_SAFE_FLAG, False))


class ArchivePath:
    """Abstract marker/base for paths that point *inside* an archive. Concrete
    implementations: :class:`ZipPath` (and later e.g. ``TarPath``)."""

    #: the archive file on the real file-system that contains this member
    archive: Path

    def __fspath__(self) -> str:
        raise ArchiveAccessError(
            f"'{self}' is inside the archive '{self.archive}' and has no file-system "
            "path. Either use only archive-safe operations (e.g. `.open()`) or "
            "extract/convert the archive first, e.g. `zipped.extract()` or "
            "`TargetFormat.convert(zipped)`"
        )

    def absolute(self) -> "ArchivePath":
        return self

    def stat(self, follow_symlinks: bool = True) -> os.stat_result:
        raise NotImplementedError


class ZipPath(ArchivePath, zipfile.Path):
    """A :class:`zipfile.Path` that knows which archive it came from, is hashable,
    sortable, and reports the archive's mtime."""

    def __init__(self, root: ty.Union[str, os.PathLike, zipfile.ZipFile], at: str = ""):  # type: ignore[type-arg]
        if isinstance(root, zipfile.ZipFile):
            archive = Path(root.filename)  # type: ignore[arg-type]
        else:
            archive = Path(root)
        super().__init__(root, at)
        self.archive = archive.absolute()

    # zipfile.Path creates children through `_next`, keep our subclass + archive
    def _next(self, at: str) -> "ZipPath":
        child = type(self).__new__(type(self))
        zipfile.Path.__init__(child, self.root, at)
        child.archive = self.archive
        return child

    @property
    def member(self) -> PurePosixPath:
        "The path of the member relative to the root of the archive"
        return PurePosixPath(self.at)

    def stat(self, follow_symlinks: bool = True) -> os.stat_result:
        """Size comes from the member, mtime from the archive file itself so that
        mtime-based caches are invalidated whenever the archive changes"""
        archive_stat = self.archive.stat()
        if self.is_dir():
            mode, size = stat_module.S_IFDIR | 0o555, 0
        else:
            mode = stat_module.S_IFREG | 0o444
            size = self.root.getinfo(self.at).file_size
        return _stat_result(mode, size, archive_stat)

    def relative_to(self, other: "ZipPath") -> PurePosixPath:
        return self.member.relative_to(other.member)

    def __str__(self) -> str:
        return f"{self.archive}::{self.at}"

    def __repr__(self) -> str:
        return f"ZipPath('{self.archive}', '{self.at}')"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ZipPath)
            and other.archive == self.archive
            and other.at == self.at
        )

    def __hash__(self) -> int:
        return hash((self.archive, self.at))

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, (ZipPath, Path)):
            return NotImplemented
        return str(self) < str(other)


def _stat_result(mode: int, size: int, archive_stat: os.stat_result) -> os.stat_result:
    # st_mtime_ns etc. are only populated from the 10-tuple via the floats, so build the
    # result from the full 'n_sequence_fields' tuple to keep ns precision
    fields = [mode, 0, 0, 1, 0, 0, size,
              int(archive_stat.st_atime), int(archive_stat.st_mtime),
              int(archive_stat.st_ctime)]
    extras = {
        "st_atime": archive_stat.st_atime,
        "st_mtime": archive_stat.st_mtime,
        "st_ctime": archive_stat.st_ctime,
        "st_atime_ns": archive_stat.st_atime_ns,
        "st_mtime_ns": archive_stat.st_mtime_ns,
        "st_ctime_ns": archive_stat.st_ctime_ns,
    }
    return os.stat_result(fields, extras)


def zip_members(archive: ty.Union[str, os.PathLike]) -> ty.List[ZipPath]:  # type: ignore[type-arg]
    """All *file* members of a zip archive (directory entries are skipped)"""
    root = ZipPath(archive)
    return sorted(
        root._next(name) for name in root.root.namelist() if not name.endswith("/")
    )
