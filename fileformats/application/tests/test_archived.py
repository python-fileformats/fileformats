import os
import typing as ty
import zipfile
from pathlib import Path

import pytest

from fileformats.application import Zip
from fileformats.core import FileSet, extra_implementation
from fileformats.core.archive import ArchiveAccessError, ZipPath, archive_safe
from fileformats.core.exceptions import FormatMismatchError
from fileformats.generic import Directory
from fileformats.image import Png

PNG_MAGIC = bytes.fromhex("89504E470D0A1A0A")


@pytest.fixture
def png_zip(tmp_path: Path) -> Path:
    zpath = tmp_path / "image.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("image.png", PNG_MAGIC + b"\x00" * 64)
    return zpath


@pytest.fixture
def txt_zip(tmp_path: Path) -> Path:
    zpath = tmp_path / "text.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("image.png", b"not really a png" * 4)
    return zpath


def test_classified_zip_validates_contents_in_place(png_zip: Path) -> None:
    zipped = Zip[Png](png_zip)
    archived = zipped.archived
    assert isinstance(archived, Png)
    assert archived.is_archived
    assert isinstance(archived.fspath, ZipPath)
    assert archived.read_contents(len(PNG_MAGIC)) == PNG_MAGIC


def test_classified_zip_rejects_wrong_contents(txt_zip: Path) -> None:
    with pytest.raises(FormatMismatchError, match="Magic number"):
        Zip[Png](txt_zip)
    Zip(txt_zip)  # unclassified zips don't look inside


def test_archived_has_no_fspath(png_zip: Path) -> None:
    archived = Zip[Png](png_zip).archived
    with pytest.raises(ArchiveAccessError):
        os.fspath(archived)
    with pytest.raises(ArchiveAccessError):
        archived.open("wb")


def test_archived_mtime_follows_archive(png_zip: Path) -> None:
    archived = Zip[Png](png_zip).archived
    ((_, mtime),) = archived.mtimes
    assert mtime == png_zip.stat().st_mtime_ns


def test_extras_gated_by_archive_safe(png_zip: Path, tmp_path: Path) -> None:
    calls: ty.List[str] = []

    class _UnsafePng(Png):  # local subtype so registrations don't leak
        pass

    class _SafePng(Png):
        pass

    @extra_implementation(FileSet.read_metadata)
    def _unsafe(fs: _UnsafePng, **kwargs: ty.Any) -> ty.Mapping[str, ty.Any]:
        calls.append("unsafe")
        return {}

    @extra_implementation(FileSet.read_metadata)
    @archive_safe
    def _safe(fs: _SafePng, **kwargs: ty.Any) -> ty.Mapping[str, ty.Any]:
        with fs.open() as f:
            return {"magic": f.read(len(PNG_MAGIC))}

    with pytest.raises(ArchiveAccessError, match="not marked @archive_safe"):
        Zip[_UnsafePng](png_zip).archived.read_metadata()
    assert not calls
    assert Zip[_SafePng](png_zip).archived.read_metadata() == {"magic": PNG_MAGIC}


def test_extract_gives_real_paths(png_zip: Path, tmp_path: Path) -> None:
    extracted = Zip[Png](png_zip).extract(tmp_path / "out")
    assert not extracted.is_archived
    assert Path(os.fspath(extracted)).read_bytes().startswith(PNG_MAGIC)


def test_zipped_directory(tmp_path: Path) -> None:
    zpath = tmp_path / "dir.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("adir/a.txt", "a")
        zf.writestr("adir/b.txt", "b")
    archived = Zip[Directory](zpath).archived
    assert archived.fspath.name == "adir"
