"""Support for viewing file-sets stored inside archives (e.g. ``Zip[DicomSeries]``)
without extracting them to disk.

The design rests on three pieces:

* :class:`ArchivePath` - a path to a member of an archive. It implements the
  IndirectPath which in turn implements the pathlib_abc.ReadablePath and some
  extra helpers.
"""

import errno
import os
import posixpath
import typing as ty
import zipfile
from pathlib import Path

from pathlib_abc import PathInfo

from fileformats.core.exceptions import ArchiveAccessError
from fileformats.core.fileset import IndirectPath

T = ty.TypeVar("T")


class ArchivePath(IndirectPath):
    """A path to a member of an archive file on the local file-system.

    Provides ``mtime_ns`` (the archive's own mtime: every member changes when the
    archive is rewritten), ``member`` (the normalised member name) and ``_key()``.
    Subclasses provide the archive access.
    """

    #: the archive file on the local file-system
    archive: Path

    @property
    def member(self) -> str:
        """Normalised posix name of the member inside the archive ("" for the root).
        Collapses ".", ".." and repeated separators, which pathlib-abc leaves in place
        (correct for symlinks, but archive members are looked up by name)"""
        member = posixpath.normpath("/" + self.__vfspath__()).lstrip("/")
        return "" if member == "." else member

    @property
    def mtime_ns(self) -> int:
        return self.archive.stat().st_mtime_ns

    def _key(self) -> ty.Tuple[str, str]:
        return (str(self.archive), self.member)

    def __str__(self) -> str:
        # Starts with the archive's real path, so code that derives information from
        # str(path) (e.g. the mtime resolution of its file-system) sees the right
        # mount, and a stray use in a shell command fails instead of silently pointing
        # at a different local file
        return f"{self.archive}::{self.member}"




class _ZipIndex:
    """Files and directories of a zip archive, read once from its central directory.

    Zip files often list directories only implicitly (as the parents of members), so
    those are added too. Makes ``info`` O(1) and ``iterdir()`` O(children) instead of
    scanning ``namelist()`` on every call.
    """

    def __init__(self, zf: zipfile.ZipFile):
        self.files: ty.Set[str] = set()
        self.dirs: ty.Set[str] = {""}
        # normalised name -> name as stored, which ZipFile.open()/getinfo() need
        self.stored_names: ty.Dict[str, str] = {}
        self.children: ty.Dict[str, ty.Set[str]] = {"": set()}
        for name in zf.namelist():
            stored = name
            is_dir = name.endswith("/")
            name = posixpath.normpath("/" + name).lstrip("/")
            if not name or name == ".":
                continue
            (self.dirs if is_dir else self.files).add(name)
            if not is_dir:
                self.stored_names[name] = stored
            # Register the member and all its (possibly implicit) parent directories
            while name:
                parent, _, leaf = name.rpartition("/")
                self.children.setdefault(parent, set()).add(leaf)
                if parent:
                    self.dirs.add(parent)
                name = parent
        for d in self.dirs:
            self.children.setdefault(d, set())


class _ZipHandle:
    """The open ZipFile and its index, shared by every path derived from one root"""

    def __init__(self, zf: zipfile.ZipFile):
        if not zf.filename:
            raise ValueError(
                "ZipPath needs a zip archive on the local file-system, not one opened "
                "from a file object"
            )
        self.zipfile = zf
        self.archive = Path(zf.filename).absolute()
        self._index: ty.Optional[_ZipIndex] = None

    @property
    def index(self) -> _ZipIndex:
        if self._index is None:
            self._index = _ZipIndex(self.zipfile)
        return self._index


class _ZipInfo(PathInfo):
    """File-type information for a zip member (zip archives have no symlinks, so
    ``follow_symlinks`` makes no difference)"""

    __slots__ = ("_is_file", "_is_dir")

    def __init__(self, is_file: bool, is_dir: bool):
        self._is_file = is_file
        self._is_dir = is_dir

    def exists(self, *, follow_symlinks: bool = True) -> bool:
        return self._is_file or self._is_dir

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        return self._is_dir

    def is_file(self, *, follow_symlinks: bool = True) -> bool:
        return self._is_file

    def is_symlink(self) -> bool:
        return False


class ZipPath(ArchivePath):
    """A path to a member of a zip archive.

    >>> root = ZipPath(zipfile_obj="series.zip")
    >>> [p.name for p in (root / "series").iterdir()]
    ['img0.dcm', 'img1.dcm']

    Parameters
    ----------
    *segments : str
        path segments inside the archive (none for the root)
    zipfile_obj : zipfile.ZipFile | str | os.PathLike
        the archive, either already open or a path to it. The open ZipFile and its
        member index are shared by every path derived from this one (via ``/``,
        ``parent``, ``iterdir()``...). The ZipFile is read as it was when it was
        opened, so open a new root after the archive is rewritten.
    """

    def __init__(
            self,
            *segments: str,
            zipfile_obj: ty.Union[zipfile.ZipFile, str, "os.PathLike[str]", _ZipHandle],
    ):
        if isinstance(zipfile_obj, _ZipHandle):  # internal, from with_segments()
            handle = zipfile_obj
        else:
            if not isinstance(zipfile_obj, zipfile.ZipFile):
                zipfile_obj = zipfile.ZipFile(zipfile_obj)
            handle = _ZipHandle(zipfile_obj)
        self._segments = segments
        self._handle = handle

    @property
    def archive(self) -> Path:  # type: ignore[override]
        return self._handle.archive

    @property
    def zipfile_obj(self) -> zipfile.ZipFile:
        return self._handle.zipfile

    # -- JoinablePath ----------------------------------------------------------------

    def __vfspath__(self) -> str:
        return self.parser.join(*self._segments) if self._segments else ""

    def with_segments(self, *pathsegments: str) -> "ZipPath":
        return type(self)(*pathsegments, zipfile_obj=self._handle)

    # -- ReadablePath ----------------------------------------------------------------

    @property
    def info(self) -> _ZipInfo:
        index = self._handle.index
        member = self.member
        return _ZipInfo(is_file=member in index.files, is_dir=member in index.dirs)

    def __open_reader__(self) -> ty.IO[bytes]:
        index = self._handle.index
        member = self.member
        if member in index.dirs:
            raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), repr(self))
        if member not in index.files:
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), repr(self))
        return self._handle.zipfile.open(index.stored_names[member])

    def iterdir(self) -> ty.Iterator["ZipPath"]:
        index = self._handle.index
        member = self.member
        if member not in index.dirs:
            if member in index.files:
                raise NotADirectoryError(
                    errno.ENOTDIR, os.strerror(errno.ENOTDIR), repr(self)
                )
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), repr(self))
        return (self / name for name in sorted(index.children[member]))

    def readlink(self) -> "ZipPath":
        # Same error os.readlink() raises for something that isn't a symlink
        raise OSError(errno.EINVAL, "Not a symbolic link (zip archives have none)", repr(self))

    # -- IndirectPath ----------------------------------------------------------------

    @property
    def size(self) -> int:
        index = self._handle.index
        stored = index.stored_names.get(self.member)
        return self._handle.zipfile.getinfo(stored).file_size if stored else 0

    # -- pickling (e.g. pydra sends file-sets to worker processes) -------------------

    def __reduce__(self) -> ty.Tuple[ty.Any, ...]:
        # An open ZipFile can't be pickled, so reopen the archive by path
        return (_unpickle_zip_path, (str(self.archive), self._segments))


def _unpickle_zip_path(archive: str, segments: ty.Tuple[str, ...]) -> ZipPath:
    return ZipPath(*segments, zipfile_obj=archive)


def zip_members(archive: ty.Union[str, os.PathLike]) -> ty.List[ZipPath]:  # type: ignore[type-arg]
    """All *file* members of a zip archive (directory entries are skipped)"""
    root = ZipPath(zipfile_obj=archive)
    return [root.joinpath(name) for name in sorted(root._handle.index.files)]
