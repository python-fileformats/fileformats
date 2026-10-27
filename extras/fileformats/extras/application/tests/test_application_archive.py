import filecmp
import os
import time
import zipfile

import pytest
from fileformats.generic import File, Directory, SetOf
from fileformats.application import Zip, Gzip, Tar, TarGzip
from fileformats.text import Plain as PlainText

TEST_DIR = "__test_dir__"
TEST_FILE = "__test_file__.txt"

INPUT_TYPES = ["file", "directory"]


@pytest.fixture(params=INPUT_TYPES)
def archive_input(work_dir, request):
    if request.param == "file":
        test_file = work_dir / TEST_FILE
        with open(test_file, "w") as f:
            f.write("test file contents")
        inpt = PlainText(test_file)
    elif request.param == "directory":
        test_dir = work_dir / TEST_DIR
        test_dir.mkdir()
        for i in range(1, 3):
            with open(test_dir / f"file{i}.txt", "w") as f:
                f.write(f"test file {i}")
        sub_dir = test_dir / "sub-dir"
        sub_dir.mkdir()
        for i in range(4, 6):
            with open(sub_dir / f"file{i}.txt", "w") as f:
                f.write(f"test file {i}")
        inpt = Directory(test_dir)
    else:
        assert False, f"Unrecognised request param {request.param}"
    return inpt


def test_zip_roundtrip(archive_input):
    _roundtrip(archive_input, Zip)


def test_zip_reproducible_roundtrip(archive_input):
    _roundtrip(archive_input, Zip, reproducible=True)


@pytest.mark.parametrize(
    "compression", ["ZIP_STORED", "ZIP_DEFLATED", "ZIP_BZIP2", "ZIP_LZMA"]
)
def test_zip_reproducible_metadata(archive_input, compression):
    first = Zip.convert(archive_input, reproducible=True, compression=compression)
    before = first.fspath.read_bytes()
    paths = [archive_input.fspath]
    if archive_input.is_dir():
        paths.extend(archive_input.fspath.rglob("*"))
    for path in paths:
        os.utime(path, (946684800, 946684800))
        path.chmod(0o700 if path.is_dir() else 0o600)
    second = Zip.convert(archive_input, reproducible=True, compression=compression)
    assert second.fspath.read_bytes() == before
    with zipfile.ZipFile(second.fspath) as archive:
        for info in archive.infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert info.create_system == 3
            assert info.compress_type == (
                zipfile.ZIP_STORED if info.is_dir() else getattr(zipfile, compression)
            )
            assert info.external_attr == (
                (0o40755 << 16) | 0x10 if info.is_dir() else 0o100644 << 16
            )
            if not info.is_dir():
                assert archive.read(info) == (
                    archive_input.fspath.parent / info.filename
                ).read_bytes()


def test_zip_reproducible_walk_order(work_dir, monkeypatch):
    root = work_dir / "input"
    for directory in ("z", "a"):
        path = root / directory
        path.mkdir(parents=True)
        for name in ("z.txt", "a.txt"):
            (path / name).write_text(name)
    first = Zip.convert(Directory(root), reproducible=True).fspath.read_bytes()
    original_walk = os.walk

    def reversed_walk(*args, **kwargs):
        for path, dirs, files in original_walk(*args, **kwargs):
            dirs.reverse()
            files.reverse()
            yield path, dirs, files

    monkeypatch.setattr(os, "walk", reversed_walk)
    second = Zip.convert(Directory(root), reproducible=True).fspath.read_bytes()
    assert first == second


def test_zip_default_preserves_mtime(archive_input):
    paths = [archive_input.fspath]
    if archive_input.is_dir():
        paths.extend(archive_input.fspath.rglob("*"))
    timestamp = 946684800
    for path in paths:
        os.utime(path, (timestamp, timestamp))
    archive = Zip.convert(archive_input)
    with zipfile.ZipFile(archive.fspath) as zfile:
        assert all(
            info.date_time == time.localtime(timestamp)[:6]
            for info in zfile.infolist()
        )


@pytest.mark.parametrize("num_files", [1, 2])
def test_zip_typed_set(work_dir, num_files):
    first = work_dir / "first.txt"
    first.write_text("first")
    paths = [first]
    if num_files == 2:
        nested = work_dir / "nested"
        nested.mkdir()
        second = nested / "second.txt"
        second.write_text("second")
        paths.append(second)

    fileset = SetOf[PlainText](paths)
    for archive_type in (Zip, Zip[type(fileset)]):
        archive = archive_type.convert(fileset)
        with zipfile.ZipFile(archive.fspath) as zfile:
            assert {name: zfile.read(name).decode() for name in zfile.namelist()} == {
                path.relative_to(work_dir).as_posix(): path.read_text()
                for path in paths
            }


@pytest.mark.parametrize(
    "compression", ["ZIP_STORED", "ZIP_DEFLATED", "ZIP_BZIP2", "ZIP_LZMA"]
)
def test_zip_roundtrip_string_compression(archive_input, compression):
    _roundtrip(archive_input, Zip, compression=compression)


def test_zip_string_compression_invalid(archive_input):
    compressed_type = Directory if archive_input.is_dir() else PlainText
    with pytest.raises(ValueError, match="Invalid compression type"):
        Zip[compressed_type].convert(archive_input, compression="not-a-real-type")


@pytest.mark.xfail(reason="Gzip converter is not implemented yet")
def test_gzip_roundtrip(archive_input):
    _roundtrip(archive_input, Gzip)


def test_tar_roundtrip(archive_input):
    _roundtrip(archive_input, Tar)


def test_tar_gz_roundtrip(archive_input):
    _roundtrip(archive_input, TarGzip)


def _roundtrip(input, archive_klass, **kwargs):
    archive_klass.convert(input, **kwargs)  # test generic archive
    # Create classified archive that can be reversed
    compressed_type = Directory if input.is_dir() else PlainText
    archive = archive_klass[compressed_type].convert(input, **kwargs)
    assert isinstance(archive, archive_klass)
    output = compressed_type.convert(archive)
    if isinstance(input, File):
        assert filecmp.cmp(output.fspath, input.fspath)
    else:
        _assert_extracted_dir_matches(output, input)


def _assert_extracted_dir_matches(extracted: Directory, reference: Directory):
    def assert_exact_match(cmp):
        assert (
            not cmp.left_only
        ), f"{cmp.left_only} missing from unarchved dir {cmp.right}"
        assert not cmp.right_only, (
            f"Additional {cmp.right_only} found in unarchived dir " + cmp.right
        )
        for subdir in cmp.subdirs.values():
            assert_exact_match(subdir)

    assert_exact_match(filecmp.dircmp(reference.fspath, extracted.fspath))
