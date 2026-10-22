import io
import os
import pickle
import stat
import time
import zipfile
from pathlib import Path

import pytest
from pathlib_abc import vfsopen

from fileformats.core.exceptions import IndirectAccessError
from fileformats.core.fileset import IndirectPath
from fileformats.core.archive import ZipPath

DCM = b"\0" * 128 + b"DICM" + b"rest"


@pytest.fixture
def zpath(tmp_path: Path) -> Path:
    path = tmp_path / "series.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("series/img0.dcm", DCM)
        zf.writestr("series/img1.dcm", DCM)
        zf.writestr("README.txt", "héllo\n")
        zf.writestr("explicit_dir/", b"")
        zf.writestr("a//odd/./name.txt", b"odd")  # non-normalised stored name
    return path


@pytest.fixture
def root(zpath: Path) -> ZipPath:
    return ZipPath(zipfile_obj=zpath)


# -- construction ----------------------------------------------------------------


def test_accepts_path_str_or_zipfile(zpath: Path) -> None:
    with zipfile.ZipFile(zpath) as zf:
        assert ZipPath(zipfile_obj=zf) == ZipPath(zipfile_obj=str(zpath))
    assert ZipPath(zipfile_obj=zpath).archive == zpath.absolute()


def test_rejects_zip_without_file_on_disk(zpath: Path) -> None:
    with pytest.raises(ValueError, match="local file-system"):
        ZipPath(zipfile_obj=zipfile.ZipFile(io.BytesIO(zpath.read_bytes())))


def test_children_share_the_handle(root: ZipPath) -> None:
    child = root / "series" / "img0.dcm"
    assert child._handle is root._handle
    assert child.parent._handle is root._handle
    assert all(c._handle is root._handle for c in root.iterdir())


# -- names and normalisation -----------------------------------------------------


def test_member_normalisation(root: ZipPath) -> None:
    img = root / "series" / "img0.dcm"
    assert img.member == "series/img0.dcm"
    assert (root / "./series//img0.dcm").member == "series/img0.dcm"
    assert (root / "series" / ".." / "README.txt").member == "README.txt"
    assert (root / ".." / "README.txt").member == "README.txt"  # can't escape root
    assert root.member == ""


def test_dotdot_member_is_found(root: ZipPath) -> None:
    assert (root / "series" / ".." / "README.txt").read_text(encoding="utf-8") == "héllo\n"


def test_non_normalised_stored_name_readable(root: ZipPath) -> None:
    odd = root / "a" / "odd" / "name.txt"
    assert odd.is_file()
    assert odd.read_bytes() == b"odd"
    assert odd.size == 3


def test_pure_path_operations(root: ZipPath) -> None:
    img = root / "series" / "img0.dcm"
    assert (img.name, img.stem, img.suffix) == ("img0.dcm", "img0", ".dcm")
    assert img.parent == root / "series"
    assert img.with_suffix(".bak").member == "series/img0.bak"
    assert img.relative_to(root / "series").__vfspath__() == "img0.dcm"


# -- identity --------------------------------------------------------------------


def test_equality_and_hash(root: ZipPath, zpath: Path) -> None:
    a = root / "series" / "img0.dcm"
    b = ZipPath("series", "img0.dcm", zipfile_obj=zpath)  # separately opened
    c = root / "series" / ".." / "series" / "img0.dcm"
    assert a == b == c
    assert len({a, b, c}) == 1
    assert a != root / "series" / "img1.dcm"
    assert a != Path("series/img0.dcm")
    assert (a == "series/img0.dcm") is False


def test_equality_symmetric_with_subclass(root: ZipPath) -> None:
    class SubZipPath(ZipPath):
        pass

    a = root / "README.txt"
    b = SubZipPath("README.txt", zipfile_obj=root._handle)
    assert (a == b) is (b == a) is False


def test_sorting(root: ZipPath) -> None:
    paths = [root / "series" / "img1.dcm", root / "README.txt", root / "series" / "img0.dcm"]
    assert [p.member for p in sorted(paths)] == [
        "README.txt",
        "series/img0.dcm",
        "series/img1.dcm",
    ]
    with pytest.raises(TypeError):
        sorted([root / "README.txt", Path("x")])


def test_repr_and_str(root: ZipPath, zpath: Path) -> None:
    img = root / "series" / "img0.dcm"
    assert repr(img) == f"ZipPath({str(zpath.absolute())!r}, 'series/img0.dcm')"
    assert str(img) == f"{zpath.absolute()}::series/img0.dcm"


# -- file-type queries -----------------------------------------------------------


@pytest.mark.parametrize(
    "parts, is_file, is_dir",
    [
        ((), False, True),
        (("series",), False, True),  # implicit directory
        (("explicit_dir",), False, True),
        (("series", "img0.dcm"), True, False),
        (("missing",), False, False),
    ],
)
def test_file_type_queries(root: ZipPath, parts: tuple, is_file: bool, is_dir: bool) -> None:
    path = root.joinpath(*parts)
    assert path.is_file() is is_file is path.info.is_file()
    assert path.is_dir() is is_dir is path.info.is_dir()
    assert path.exists() is (is_file or is_dir)
    assert path.is_symlink() is False


def test_iterdir(root: ZipPath) -> None:
    assert [p.name for p in root.iterdir()] == ["README.txt", "a", "explicit_dir", "series"]
    assert [p.name for p in (root / "series").iterdir()] == ["img0.dcm", "img1.dcm"]
    assert list((root / "explicit_dir").iterdir()) == []
    with pytest.raises(NotADirectoryError):
        list((root / "README.txt").iterdir())
    with pytest.raises(FileNotFoundError):
        list((root / "missing").iterdir())


def test_glob_and_walk(root: ZipPath) -> None:
    assert sorted(p.name for p in root.glob("series/*.dcm")) == ["img0.dcm", "img1.dcm"]
    walked = {d.member: sorted(files) for d, _, files in root.walk()}
    assert walked["series"] == ["img0.dcm", "img1.dcm"]


def test_readlink(root: ZipPath) -> None:
    with pytest.raises(OSError, match="Not a symbolic link"):
        (root / "README.txt").readlink()


# -- reading ---------------------------------------------------------------------


def test_open_binary_and_text(root: ZipPath) -> None:
    img = root / "series" / "img0.dcm"
    with img.open("rb") as f:
        f.seek(128)
        assert f.read(4) == b"DICM"
    with (root / "README.txt").open(encoding="utf-8") as f:
        assert f.read() == "héllo\n"


def test_read_helpers_and_vfsopen(root: ZipPath) -> None:
    # read_bytes/vfsopen first try the built-in open(), which calls __fspath__; this
    # only works because IndirectAccessError is a TypeError
    img = root / "series" / "img0.dcm"
    assert img.read_bytes() == DCM
    assert vfsopen(img, "rb").read(4) == b"\0\0\0\0"


def test_open_errors(root: ZipPath) -> None:
    with pytest.raises(FileNotFoundError):
        (root / "missing").open("rb")
    with pytest.raises(IsADirectoryError):
        (root / "series").open("rb")


@pytest.mark.parametrize("mode", ["w", "wb", "a", "x", "r+", "rb+"])
def test_open_for_writing_is_refused(root: ZipPath, mode: str) -> None:
    with pytest.raises(io.UnsupportedOperation, match="read-only"):
        (root / "README.txt").open(mode)


# -- local file-system access ----------------------------------------------------


def test_fspath_refused_with_helpful_error(root: ZipPath) -> None:
    img = root / "series" / "img0.dcm"
    with pytest.raises(IndirectAccessError, match="no local file-system path"):
        os.fspath(img)
    with pytest.raises(TypeError):  # still a TypeError for generic callers
        Path(img)
    with pytest.raises(TypeError):
        open(img, "rb")  # type: ignore[call-overload]
    assert isinstance(img, os.PathLike)  # documented trap: check IndirectPath first


def test_absolute_is_self(root: ZipPath) -> None:
    img = root / "README.txt"
    assert img.absolute() is img


# -- stat / mtime ----------------------------------------------------------------


def test_stat(root: ZipPath, zpath: Path) -> None:
    st = (root / "series" / "img0.dcm").stat()
    assert stat.S_ISREG(st.st_mode)
    assert st.st_size == len(DCM)
    assert st.st_mtime_ns == zpath.stat().st_mtime_ns
    assert st.st_mtime == pytest.approx(zpath.stat().st_mtime)
    assert stat.S_ISDIR((root / "series").stat().st_mode)
    with pytest.raises(FileNotFoundError):
        (root / "missing").stat()


def test_mtime_follows_archive(root: ZipPath, zpath: Path) -> None:
    img = root / "README.txt"
    before = img.mtime_ns
    later = before + 5 * 10**9
    os.utime(zpath, ns=(later, later))
    assert img.mtime_ns == later == img.stat().st_mtime_ns


# -- pickling --------------------------------------------------------------------


def test_pickle_round_trip(root: ZipPath) -> None:
    img = root / "series" / "img0.dcm"
    restored = pickle.loads(pickle.dumps(img))
    assert restored == img
    assert restored.read_bytes() == DCM
    assert restored._handle is not img._handle  # reopened by path


# -- scale -----------------------------------------------------------------------


def test_large_archive_is_indexed_once(tmp_path: Path) -> None:
    zpath = tmp_path / "big.zip"
    n = 5000
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_STORED) as zf:
        for i in range(n):
            zf.writestr(f"series/img{i:05d}.dcm", b"x")
    root = ZipPath(zipfile_obj=zpath)
    start = time.perf_counter()
    files = [p for p in (root / "series").iterdir() if p.is_file()]
    elapsed = time.perf_counter() - start
    assert len(files) == n
    # Scanning namelist() per child would be ~25M string checks; indexed it's ~10k
    assert elapsed < 1.0, f"iterdir + is_file took {elapsed:.2f}s for {n} members"


def test_base_class_requires_key_and_mtime() -> None:
    assert {"_key", "mtime_ns"} <= IndirectPath.__abstractmethods__
