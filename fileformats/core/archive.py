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
import typing as ty
import zipfile

from pathlib_abc import PathInfo

from fileformats.core.exceptions import ArchiveAccessError
from fileformats.core.fileset import IndirectPath

T = ty.TypeVar("T")


class ArchivePath(IndirectPath):
    """Abstract marker/base for paths that point *inside* an archive. Concrete
    implementations: :class:`ZipPath` (and later e.g. ``TarPath``)."""

    def __fspath__(self) -> str:
        raise ArchiveAccessError(
            f"'{self}' is inside the archive '{self.archive}' and has no file-system "
            "path. Either use only archive-safe operations (e.g. `.open()`) or "
            "extract/convert the archive first, e.g. `zipped.extract()` or "
            "`TargetFormat.convert(zipped)`"
        )


class ZipInfo(PathInfo):
    def __init__(self, zf, at):
        self._zf, self._at = zf, at
        names = set(zf.namelist())
        self._file = at in names
        self._dir = not at or (at + "/") in names or any(n.startswith(at + "/") for n in names)

    def exists(self, *, follow_symlinks=True):
        return self._file or self._dir

    def is_dir(self, *, follow_symlinks=True):
        return self._dir

    def is_file(self, *, follow_symlinks=True):
        return self._file

    def is_symlink(self):
        return False


class ZipPath(ArchivePath):
    """A :class:`zipfile.Path` that knows which archive it came from, is hashable,
    sortable, and reports the archive's mtime."""

    def __init__(self, *segments, zipfile_obj):
        self._segments = segments

        if not isinstance(zipfile_obj, zipfile.ZipFile):
            zipfile_obj = zipfile.ZipFile(zipfile_obj)

        self.zipfile_obj = zipfile_obj # shared reference to the zipfile, carried to children

    def __vfspath__(self):
        return self.parser.join(*self._segments) if self._segments else ""

    def with_segments(self, *segments):
        return type(self)(*segments, zipfile_obj=self.zipfile_obj)

    @property
    def _at(self):                          # member name inside the zip
        return self.__vfspath__().lstrip("/").removeprefix("./").rstrip("/")

    @property
    def info(self):
        return ZipInfo(self.zipfile_obj, self._at)

    def __open_reader__(self):
        return self.zipfile_obj.open(self._at)

    def iterdir(self):
        prefix = self._at + "/" if self._at else ""
        kids = {n[len(prefix):].split("/")[0] for n in self.zipfile_obj.namelist() if n.startswith(prefix) and n != prefix}
        return (self / k for k in sorted(kids))

    def readlink(self):
        raise NotImplementedError("zip archives have no symlinks")

    def _key(self):
        return (self.zipfile_obj.filename, self.parser.normpath(self.__vfspath__() or "."))


def zip_members(archive: ty.Union[str, os.PathLike]) -> ty.List[ZipPath]:  # type: ignore[type-arg]
    """All *file* members of a zip archive (directory entries are skipped)"""
    root = ZipPath(zipfile_obj=archive)
    return sorted(
        root._next(name) for name in root.root.namelist() if not name.endswith("/")
    )
