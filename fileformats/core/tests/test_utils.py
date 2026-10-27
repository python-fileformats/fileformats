import os.path
import random
import shutil
import time
import warnings
import typing as ty
from pathlib import Path

import pytest
from fileformats.generic import File, BinaryFile, Directory, FsObject, SetOf
from fileformats.core import (
    FileSet,
    MockMixin,
    validated_property,
    mtime_cached_property,
)
from fileformats.text import TextFile
from fileformats.core.exceptions import (
    FileFormatsNotRelativePathError,
    UnsatisfiableCopyModeError,
)
from fileformats.core.mixin import WithSeparateHeader
from fileformats.core.utils import collate_metadata_series
from fileformats.testing import Foo

from conftest import write_test_file

class Mario(BinaryFile):
    ext = ".mario"


class Luigi(WithSeparateHeader, BinaryFile):
    ext = ".luigi"
    header_type = Mario


class Bowser(Directory):
    content_types = (Mario,)


@pytest.fixture
def bowser_dir(work_dir):
    bowser_dir = work_dir / "bowser"
    bowser_dir.mkdir()
    for i in range(5):
        bar_fspath = bowser_dir / f"{i}.mario"
        write_test_file(bar_fspath)
    return Bowser(bowser_dir)


@pytest.fixture
def luigi_file(work_dir):
    luigi_fspath = work_dir / "x.luigi"
    write_test_file(luigi_fspath)
    bar_fspath = work_dir / "y.mario"
    write_test_file(bar_fspath)
    return Luigi([luigi_fspath, bar_fspath])


@pytest.fixture(params=["luigi", "bowser"])
def fsobject(luigi_file, bowser_dir, request):
    if request.param == "luigi":
        return luigi_file
    elif request.param == "bowser":
        return bowser_dir
    else:
        assert False


@pytest.fixture
def mock_fileset():
    return SetOf[TextFile].mock("/path/to/a/mock", "/path/to/another/mock")


@pytest.fixture
def dest_dir(work_dir):
    dest_dir = work_dir / "new-dir"
    dest_dir.mkdir()
    return dest_dir


def test_copy(fsobject: FsObject, dest_dir: Path):
    cpy = fsobject.copy(dest_dir)
    assert all(p.parent == dest_dir for p in cpy.fspaths)
    assert set(p.name for p in cpy.fspaths) == set(p.name for p in fsobject.fspaths)
    assert cpy.hash() == fsobject.hash()


def test_copy_symlink(fsobject: FsObject, dest_dir: Path):
    cpy = fsobject.copy(dest_dir, mode=File.CopyMode.symlink)
    assert all(p.parent == dest_dir for p in cpy.fspaths)
    assert set(p.name for p in cpy.fspaths) == set(p.name for p in fsobject.fspaths)
    assert all(p.is_symlink() for p in cpy.fspaths)
    assert cpy.hash() == fsobject.hash()


def test_copy_symlink_with_fallback(fsobject: FsObject, dest_dir: Path):
    "Simulate source object on CIFS share, should be copied not symlinked"
    cpy = fsobject.copy(
        dest_dir,
        mode=File.CopyMode.link_or_copy,
        supported_modes=File.CopyMode.hardlink_or_copy,
    )
    assert all(p.parent == dest_dir for p in cpy.fspaths)
    assert set(p.name for p in cpy.fspaths) == set(p.name for p in fsobject.fspaths)
    assert not any(p.is_symlink() for p in cpy.fspaths)
    assert cpy.hash() == fsobject.hash()


def test_copy_symlink_with_unrequired_fallback(fsobject: FsObject, dest_dir: Path):
    "Simulate source object not on CIFS share, should be symlinked not copied"
    cpy = fsobject.copy(
        dest_dir, mode=File.CopyMode.link_or_copy, supported_modes=File.CopyMode.link
    )
    assert all(p.parent == dest_dir for p in cpy.fspaths)
    assert set(p.name for p in cpy.fspaths) == set(p.name for p in fsobject.fspaths)
    assert all(p.is_symlink() for p in cpy.fspaths)
    assert cpy.hash() == fsobject.hash()


def test_copy_hardlink(fsobject: FsObject, dest_dir: Path):
    cpy = fsobject.copy(dest_dir, mode=File.CopyMode.hardlink_or_copy)
    assert all(p.parent == dest_dir for p in cpy.fspaths)
    assert set(p.name for p in cpy.fspaths) == set(p.name for p in fsobject.fspaths)
    assert all(
        c != o and os.path.samefile(c, o)
        for c, o in zip(sorted(cpy.fspaths), sorted(fsobject.fspaths))
        if o.is_file()
    )
    assert cpy.hash() == fsobject.hash()


def test_copy_collation_same_name(work_dir: Path, dest_dir: Path):
    a = work_dir / "a" / "file.txt"
    b = work_dir / "b" / "file.txt"
    c = work_dir / "c" / "d" / "file.txt"
    fspaths = (a, b, c)

    for x in fspaths:
        x.parent.mkdir(parents=True)
        Path.touch(x)

    fileset = FileSet(fspaths)

    with pytest.raises(
        UnsatisfiableCopyModeError,
        match="as there are duplicate filenames",
    ):
        fileset.copy(dest_dir=dest_dir, collation="siblings")
    cpy = fileset.copy(dest_dir=dest_dir, collation="any")
    assert sorted(cpy.relative_fspaths) == sorted(fileset.relative_fspaths)
    assert cpy.parent == dest_dir


def test_copy_collation_same_ext(work_dir: Path, dest_dir: Path):
    a = work_dir / "a" / "filea.txt"
    b = work_dir / "b" / "fileb.txt"
    c = work_dir / "c" / "d" / "filec.txt"
    fspaths = (a, b, c)

    for x in fspaths:
        x.parent.mkdir(parents=True)
        Path.touch(x)

    fileset = FileSet(fspaths)

    with pytest.raises(
        UnsatisfiableCopyModeError,
        match="as there are duplicate extensions",
    ):
        fileset.copy(dest_dir=dest_dir, collation="adjacent")
    cpy = fileset.copy(dest_dir=dest_dir, collation="siblings")
    assert sorted(p.name for p in cpy.fspaths) == sorted(
        p.name for p in fileset.fspaths
    )
    assert all(p.parent == dest_dir for p in cpy.fspaths)


def test_copy_collation_diff_ext(work_dir: Path, dest_dir: Path):
    a = work_dir / "a" / "filea.x"
    b = work_dir / "b" / "fileb.y"
    c = work_dir / "c" / "d" / "filec.z"
    fspaths = (a, b, c)

    for x in fspaths:
        x.parent.mkdir(parents=True)
        Path.touch(x)

    fileset = FileSet(fspaths)

    cpy = fileset.copy(dest_dir=dest_dir, collation="adjacent")
    assert all(p.parent == dest_dir for p in cpy.fspaths)
    assert all(p.stem == "filea" for p in cpy.fspaths)


def test_copy_collation_stem(work_dir: Path, dest_dir: Path):
    a = work_dir / "a" / "filea.x"
    b = work_dir / "b" / "fileb.y"
    c = work_dir / "c" / "d" / "filec.z"
    fspaths = (a, b, c)

    for x in fspaths:
        x.parent.mkdir(parents=True)
        Path.touch(x)

    fileset = FileSet(fspaths)

    cpy = fileset.copy(dest_dir=dest_dir, collation="adjacent", new_stem="newfile")
    assert all(p.parent == dest_dir for p in cpy.fspaths)
    assert all(p.stem == "newfile" for p in cpy.fspaths)


def test_copy_with_suffix(work_dir: Path, dest_dir: Path):
    a = work_dir / "a" / "filea.x"
    b = work_dir / "b" / "fileb.y"
    c = work_dir / "c" / "d" / "filec.z"
    fspaths = (a, b, c)

    for x in fspaths:
        x.parent.mkdir(parents=True)
        Path.touch(x)

    fileset = FileSet(fspaths)

    stem_suffix = "-2"

    cpy = fileset.copy(dest_dir=dest_dir, stem_suffix=stem_suffix)
    assert all(p.stem.endswith(stem_suffix) for p in cpy.fspaths)
    assert set(p.suffix for p in cpy.fspaths) == set([".x", ".y", ".z"])


def test_copy_with_prefix(work_dir: Path, dest_dir: Path):
    a = work_dir / "a" / "filea.x"
    b = work_dir / "b" / "fileb.y"
    c = work_dir / "c" / "d" / "filec.z"
    fspaths = (a, b, c)

    for x in fspaths:
        x.parent.mkdir(parents=True)
        Path.touch(x)

    fileset = FileSet(fspaths)

    prefix = "my-"

    cpy = fileset.copy(dest_dir=dest_dir, prefix=prefix)
    assert all(p.stem.startswith(prefix) for p in cpy.fspaths)
    assert set(p.suffix for p in cpy.fspaths) == set([".x", ".y", ".z"])


def test_copy_retain_dir_structure(work_dir: Path, dest_dir: Path):
    a = work_dir / "a" / "file"
    b = work_dir / "b" / "file"
    c = work_dir / "c" / "file"
    fspaths = (a, b, c)

    for x in fspaths:
        x.parent.mkdir(parents=True)
        Path.touch(x)

    fileset = FileSet(fspaths)

    cpy = fileset.copy(dest_dir=dest_dir)
    assert all(p.parent.parent == dest_dir for p in cpy.fspaths)
    assert set(p.parent.name for p in cpy.fspaths) == set(["a", "b", "c"])


def test_copy_avoid_clashes1(work_dir: Path, dest_dir: Path):
    a = work_dir / "file1"
    b = work_dir / "file2"
    c = work_dir / "file3"
    fspaths = (a, b, c)

    for x in fspaths:
        Path.touch(x)

    fileset = FileSet(fspaths)

    # Create an existing file to avoid
    Path.touch(dest_dir / "file3")

    cpy = fileset.copy(dest_dir=dest_dir, avoid_clashes=True)
    assert all(p.parent == dest_dir for p in cpy.fspaths)
    assert set(p.name for p in cpy.fspaths) == set(
        ["file1 (1)", "file2 (1)", "file3 (1)"]
    )


def test_copy_avoid_clashes2(work_dir: Path, dest_dir: Path):
    a = work_dir / "a" / "file.x"
    b = work_dir / "file.y"
    c = work_dir / "c" / "file.z"
    fspaths = (a, b, c)

    for x in fspaths:
        x.parent.mkdir(parents=True, exist_ok=True)
        Path.touch(x)

    fileset = FileSet(fspaths)
    for x in fspaths:
        Path.touch(x)

    fileset = FileSet(fspaths)

    # Create an existing file to avoid
    (dest_dir / "a").mkdir()
    Path.touch(dest_dir / "a" / "file.x")

    cpy = fileset.copy(dest_dir=dest_dir, avoid_clashes=True)
    assert set(p.parent.parent == dest_dir or p.parent == dest_dir for p in cpy.fspaths)
    assert set(p for p in cpy.relative_fspaths) == set(
        [Path("a (1)") / "file.x", Path("file (1).y"), Path("c (1)") / "file.z"]
    )


def test_copy_avoid_clashes3(work_dir: Path, dest_dir: Path):
    sub_dirs = ("a", "b", "c")

    files: ty.List[File] = []
    for x in sub_dirs:
        p = work_dir / x / "file.txt"
        p.parent.mkdir()
        p.touch()
        files.append(File(p))

    avoid_clashes: ty.Set[Path] = set()
    copied: ty.List[File] = []
    for file in files:
        copied.append(file.copy(dest_dir=dest_dir, avoid_clashes=avoid_clashes))
    assert all(f.parent == dest_dir for f in copied)
    assert set(f.name for f in copied) == set(
        ["file.txt", "file (1).txt", "file (2).txt"]
    )


def test_copy_avoid_clashes4(work_dir: Path, dest_dir: Path):
    filesets: ty.List[FileSet] = []
    for y in ("x", "y", "z"):
        a = work_dir / y / "a" / "file.x"
        b = work_dir / y / "file.y"
        c = work_dir / y / "c" / "file.z"
        fspaths = (a, b, c)
        for x in fspaths:
            x.parent.mkdir(parents=True, exist_ok=True)
            x.touch()
        filesets.append(FileSet(fspaths))

    avoid_clashes: ty.Set[Path] = set()
    copied: ty.List[FileSet] = []
    for fileset in filesets:
        copied.append(fileset.copy(dest_dir=dest_dir, avoid_clashes=avoid_clashes))
    assert all(f.parent == dest_dir for f in copied)
    assert sorted(
        (Path(ppath) / fname).relative_to(dest_dir)
        for ppath, _, fnames in os.walk(dest_dir)
        for fname in fnames
    ) == [
        Path("a") / "file.x",
        Path("a (1)") / "file.x",
        Path("a (2)") / "file.x",
        Path("c") / "file.z",
        Path("c (1)") / "file.z",
        Path("c (2)") / "file.z",
        Path("file (1).y"),
        Path("file (2).y"),
        Path("file.y"),
    ]


def test_copy_collation_leave_diff_dir(work_dir: Path, dest_dir: Path):
    a = work_dir / "a" / "file.x"
    b = work_dir / "b" / "file.y"
    c = work_dir / "c" / "file.z"
    fspaths = (a, b, c)

    for x in fspaths:
        x.parent.mkdir(parents=True)
        Path.touch(x)

    fileset = FileSet(fspaths)

    with pytest.raises(
        UnsatisfiableCopyModeError,
        match="given the collation specification",
    ):
        fileset.copy(dest_dir=dest_dir, mode="leave", collation="siblings")

    with pytest.raises(
        UnsatisfiableCopyModeError,
        match="given the collation specification",
    ):
        fileset.copy(dest_dir=dest_dir, mode="leave", collation="adjacent")


def test_copy_ext(work_dir):
    assert (
        File.copy_ext(
            work_dir / "x.luigi.mario",
            work_dir / "y",
            decomposition_mode=FileSet.ExtensionDecomposition.none,
        )
        == work_dir / "y"
    )
    assert (
        File.copy_ext(
            work_dir / "x.luigi.mario",
            work_dir / "y",
            decomposition_mode=FileSet.ExtensionDecomposition.single,
        )
        == work_dir / "y.mario"
    )
    assert (
        File.copy_ext(
            work_dir / "x.luigi.mario",
            work_dir / "y",
            decomposition_mode=FileSet.ExtensionDecomposition.multiple,
        )
        == work_dir / "y.luigi.mario"
    )
    assert (
        Mario.copy_ext(work_dir / "x.luigi.mario", work_dir / "y")
        == work_dir / "y.mario"
    )


def test_move(fsobject: FsObject, dest_dir: Path):
    orig_names = set(p.name for p in fsobject.fspaths)
    orig_hash = fsobject.hash()
    moved = fsobject.move(dest_dir)
    assert all(p.parent == dest_dir for p in moved.fspaths)
    assert set(p.name for p in moved.fspaths) == orig_names
    assert moved.hash() == orig_hash


def test_decompose_fspaths(work_dir):
    class LuigiMario(File):
        ext = ".luigi.mario"

    class DoubleMario(FileSet):
        @validated_property
        def bar(self):
            return Mario(self.select_by_ext(Mario))

        @validated_property
        def luigi_bar(self):
            return LuigiMario(self.select_by_ext(LuigiMario))

    fspath = work_dir / "file.luigi.mario"
    Path.touch(fspath)
    double_bar = DoubleMario(fspath)

    with pytest.warns(match="whereas it is also interpreted as a"):
        decomposed = double_bar.decomposed_fspaths()

    assert decomposed == [(work_dir, "file.luigi", ".mario")]


def test_decompose_fspaths_drops_subpaths(work_dir):
    sub_dir = work_dir / "sub"
    sub_dir.mkdir()
    Path.touch(sub_dir / "nested.mario")
    Path.touch(sub_dir / "deeper.mario")
    Path.touch(work_dir / "sibling.mario")

    fileset = FileSet(
        [
            sub_dir,
            sub_dir / "nested.mario",
            sub_dir / "deeper.mario",
            work_dir / "sibling.mario",
        ]
    )

    decomposed = fileset.decomposed_fspaths(required_only=False)

    assert sorted(decomposed) == [
        (work_dir, "sibling", ".mario"),
        (work_dir, "sub", ""),
    ]


def test_decompose_fspaths_ignores_external_nested_filesets(work_dir):
    class MarioWithExternals(Mario):
        @validated_property
        def sidecar(self):
            # extension isn't constrained
            return File(self.fspath.with_suffix(".sidecar"))

        @validated_property
        def header(self):
            # extension is constrained
            return Mario(self.fspath.with_name("header.mario"))

    fspath = work_dir / "file.mario"
    Path.touch(fspath)
    Path.touch(work_dir / "file.sidecar")
    Path.touch(work_dir / "header.mario")

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        decomposed = MarioWithExternals(fspath).decomposed_fspaths()

    assert decomposed == [(work_dir, "file", ".mario")]


def test_decompose_fspaths_nested_fileset_in_directory(work_dir):
    class MarioDir(Directory):
        @validated_property
        def header(self):
            return Mario(self.fspath / "header.mario")

    mario_dir = work_dir / "mario_dir"
    mario_dir.mkdir()
    Path.touch(mario_dir / "header.mario")

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        decomposed = MarioDir(mario_dir).decomposed_fspaths()

    assert decomposed == [(work_dir, "mario_dir", "")]


def test_decompose_fspaths_required_file_in_unrequired_directory(work_dir):
    class NestedMario(FileSet):
        @validated_property
        def header(self):
            return Mario(next(p for p in self.fspaths if p.is_file()))

    sub_dir = work_dir / "sub"
    sub_dir.mkdir()
    Path.touch(sub_dir / "header.mario")
    Path.touch(sub_dir / "other.mario")

    fileset = NestedMario([sub_dir, sub_dir / "header.mario"])

    # The directory isn't required, so the required file nested within it shouldn't
    # be dropped in favour of it
    assert fileset.decomposed_fspaths(required_only=True) == [
        (sub_dir, "header", ".mario")
    ]
    assert fileset.decomposed_fspaths(required_only=False) == [(work_dir, "sub", "")]


def test_copy_trimmed_required_file_in_unrequired_directory(work_dir):
    class NestedMario(FileSet):
        @validated_property
        def header(self):
            return Mario(next(p for p in self.fspaths if p.is_file()))

    src_dir = work_dir / "src"
    sub_dir = src_dir / "sub"
    sub_dir.mkdir(parents=True)
    (sub_dir / "header.mario").write_text("header")
    (sub_dir / "other.mario").write_text("other")
    dest_dir = work_dir / "dest"
    dest_dir.mkdir()

    fileset = NestedMario([sub_dir, sub_dir / "header.mario"])
    copied = fileset.copy(dest_dir, trim=True)

    assert [p.relative_to(dest_dir) for p in copied.fspaths] == [
        Path("sub") / "header.mario"
    ]
    assert (dest_dir / "sub" / "header.mario").read_text() == "header"
    assert not (dest_dir / "sub" / "other.mario").exists()


def test_copy_with_subpaths(work_dir):
    src_dir = work_dir / "src"
    src_dir.mkdir()
    sub_dir = src_dir / "sub"
    sub_dir.mkdir()
    (sub_dir / "nested.mario").write_text("nested")
    (src_dir / "sibling.mario").write_text("sibling")
    dest_dir = work_dir / "dest"
    dest_dir.mkdir()

    fileset = FileSet([sub_dir, sub_dir / "nested.mario", src_dir / "sibling.mario"])
    copied = fileset.copy(dest_dir, trim=False)

    assert sorted(p.relative_to(dest_dir) for p in copied.fspaths) == [
        Path("sibling.mario"),
        Path("sub"),
    ]
    assert (dest_dir / "sub" / "nested.mario").read_text() == "nested"


def test_hash(tmp_path: Path):
    file_1 = tmp_path / "file_1.txt"
    file_2 = tmp_path / "file_2.txt"
    file_1.write_text("hello")
    file_2.write_text("hello")

    assert File(file_1).hash() == File(file_2).hash()


def test_hash_function_files_mismatch(tmp_path: Path):
    file_1 = tmp_path / "file_1.txt"
    file_2 = tmp_path / "file_2.txt"
    file_1.write_text("hello")
    file_2.write_text("hi")

    assert File(file_1).hash() != File(file_2).hash()


def test_hash_dir(tmp_path: Path):
    dir1 = tmp_path / "luigi"
    dir2 = tmp_path / "bar"
    for d in (dir1, dir2):
        d.mkdir()
        for i in range(3):
            f = d / f"{i}.txt"
            f.write_text(str(i))

    assert Directory(dir1).hash() == Directory(dir2).hash()


def test_hash_nested_dir(tmp_path: Path):
    dpath = tmp_path / "dir"
    dpath.mkdir()
    hidden = dpath / ".hidden"
    nested = dpath / "nested"
    hidden.mkdir()
    nested.mkdir()
    file_1 = dpath / "file_1.txt"
    file_2 = hidden / "file_2.txt"
    file_3 = nested / ".file_3.txt"
    file_4 = nested / "file_4.txt"

    for fx in [file_1, file_2, file_3, file_4]:
        fx.write_text(str(random.randint(0, 1000)))

    nested_dir = Directory(dpath)

    orig_hash = nested_dir.hash()

    nohidden_hash = nested_dir.hash(ignore_hidden_dirs=True, ignore_hidden_files=True)
    nohiddendirs_hash = nested_dir.hash(ignore_hidden_dirs=True)
    nohiddenfiles_hash = nested_dir.hash(ignore_hidden_files=True)

    assert orig_hash != nohidden_hash
    assert orig_hash != nohiddendirs_hash
    assert orig_hash != nohiddenfiles_hash

    os.remove(file_3)
    assert nested_dir.hash() == nohiddenfiles_hash
    shutil.rmtree(hidden)
    assert nested_dir.hash() == nohidden_hash


def test_hash_mtime(tmp_path: Path):
    file_1 = tmp_path / "file_1.txt"
    file_2 = tmp_path / "file_2.txt"
    file_1.write_text("hello")
    file_2.write_text("hello")

    orig_hash = File(file_1).hash(mtime=True)

    assert File(file_1).hash(mtime=True) == orig_hash
    assert File(file_2).hash(mtime=True) != orig_hash

    time.sleep(1)
    Path.touch(file_1)
    assert File(file_1).hash(mtime=True) != orig_hash


def test_hash_files(fsobject: FsObject, work_dir: Path, dest_dir: Path):
    file_hashes = fsobject.hash_files(relative_to=work_dir)
    assert sorted(Path(p) for p in file_hashes) == sorted(
        p.relative_to(work_dir) for p in fsobject.all_file_paths()
    )
    cpy = fsobject.copy(dest_dir)
    assert cpy.hash_files() == fsobject.hash_files()


class MtimeTestFile(File):

    flag: int

    @mtime_cached_property
    def cached_prop(self):
        return self.flag


def test_mtime_cached_property(tmp_path: Path):
    fspath = tmp_path / "file_1.txt"
    fspath.write_text("hello")

    file = MtimeTestFile(fspath)

    file.flag = 0
    assert file.cached_prop == 0
    # Need a long delay to ensure the mtime changes on Ubuntu and particularly on Windows
    # On MacOS, the mtime resolution is much higher so not usually an issue. Use
    # explicitly cache clearing if needed
    time.sleep(2)
    file.flag = 1
    assert file.cached_prop == 0
    time.sleep(2)
    fspath.write_text("world")
    assert file.cached_prop == 1


def test_mtime_cached_property_force_clear(tmp_path: Path):
    fspath = tmp_path / "file_1.txt"
    fspath.write_text("hello")

    file = MtimeTestFile(fspath)

    file.flag = 0
    assert file.cached_prop == 0
    file.flag = 1
    MtimeTestFile.cached_prop.clear(file)
    assert file.cached_prop == 1


def test_hash_mock_files(mock_fileset: MockMixin, work_dir: Path, dest_dir: Path):
    file_hashes = mock_fileset.hash_files(relative_to="")
    assert sorted(Path(p) for p in file_hashes) == sorted(
        p for p in mock_fileset.fspaths
    )
def test_all_file_paths(work_dir: Path):
    sub_dir = work_dir / "sub"
    deep_dir = sub_dir / "deep"
    deep_dir.mkdir(parents=True)
    Path.touch(sub_dir / "b.mario")
    Path.touch(sub_dir / "a.mario")
    Path.touch(deep_dir / "c.mario")
    Path.touch(work_dir / "sibling.mario")

    # "a.mario" is both listed explicitly and nested within the listed directory
    fileset = FileSet([sub_dir, sub_dir / "a.mario", work_dir / "sibling.mario"])
    all_file_paths = fileset.all_file_paths()

    assert [p.relative_to(work_dir) for p in all_file_paths] == [
        Path("sibling.mario"),
        Path("sub") / "a.mario",
        Path("sub") / "b.mario",
        Path("sub") / "deep" / "c.mario",
    ]


def test_all_file_paths_ignore_hidden(work_dir: Path):
    sub_dir = work_dir / "sub"
    hidden_dir = sub_dir / ".hidden"
    below_hidden_dir = hidden_dir / "below"
    below_hidden_dir.mkdir(parents=True)
    Path.touch(sub_dir / "a.mario")
    Path.touch(sub_dir / ".b.mario")
    Path.touch(hidden_dir / "c.mario")
    Path.touch(below_hidden_dir / "d.mario")
    Path.touch(work_dir / ".listed.mario")

    # Explicitly listed paths are always included, even if they are hidden
    fileset = FileSet([sub_dir, work_dir / ".listed.mario"])

    def rel_paths(**kwargs: bool) -> ty.List[str]:
        return [
            p.relative_to(work_dir).as_posix() for p in fileset.all_file_paths(**kwargs)
        ]

    assert rel_paths() == [
        ".listed.mario",
        "sub/.b.mario",
        "sub/.hidden/below/d.mario",
        "sub/.hidden/c.mario",
        "sub/a.mario",
    ]
    assert rel_paths(ignore_hidden_files=True) == [
        ".listed.mario",
        "sub/.hidden/below/d.mario",
        "sub/.hidden/c.mario",
        "sub/a.mario",
    ]
    assert rel_paths(ignore_hidden_dirs=True) == [
        ".listed.mario",
        "sub/.b.mario",
        "sub/a.mario",
    ]
    assert rel_paths(ignore_hidden_files=True, ignore_hidden_dirs=True) == [
        ".listed.mario",
        "sub/a.mario",
    ]


def test_all_file_paths_broken_symlink(work_dir: Path):
    sub_dir = work_dir / "sub"
    sub_dir.mkdir()
    Path.touch(sub_dir / "a.mario")
    (sub_dir / "broken.mario").symlink_to(work_dir / "missing.mario")

    fileset = FileSet(sub_dir)

    with pytest.raises(FileNotFoundError, match="Broken symbolic link"):
        fileset.all_file_paths()
    with pytest.raises(FileNotFoundError, match="Broken symbolic link"):
        fileset.hash_files()


def test_byte_chunks_keys_of_mock_unchanged_by_creation(work_dir: Path):
    """The keys of a mocked fileset don't depend on whether its files exist, so its
    hash doesn't change if they are created (e.g. by the task it is passed to)"""
    fspath = work_dir / "new.mario"
    mock = FileSet.mock(fspath)
    keys = [k for k, _ in mock.byte_chunks()]
    fspath.touch()
    assert [k for k, _ in mock.byte_chunks()] == keys == ["."]


def test_byte_chunks_matches_all_file_paths(work_dir: Path):
    sub_dir = work_dir / "sub"
    below_hidden_dir = sub_dir / ".hidden" / "below"
    below_hidden_dir.mkdir(parents=True)
    (sub_dir / "deep").mkdir()
    Path.touch(sub_dir / "z.mario")
    Path.touch(sub_dir / "deep" / "c.mario")
    Path.touch(below_hidden_dir / "d.mario")

    # "z.mario" is both listed explicitly and nested within the listed directory
    fileset = FileSet([sub_dir, sub_dir / "z.mario"])

    for ignore_hidden_dirs in (False, True):
        # Keys use the native path separator, so compare them as paths
        keys = [
            Path(k)
            for k, _ in fileset.byte_chunks(
                relative_to=work_dir, ignore_hidden_dirs=ignore_hidden_dirs
            )
        ]
        assert keys == [
            p.relative_to(work_dir)
            for p in fileset.all_file_paths(ignore_hidden_dirs=ignore_hidden_dirs)
        ]
    assert keys == [Path("sub") / "deep" / "c.mario", Path("sub") / "z.mario"]


def test_hash_files_keys(tmp_path: Path):
    one = Foo.sample(tmp_path, stem="foo-one")
    two = Foo.sample(tmp_path, stem="foo-two")
    three = Foo.sample(tmp_path, stem="foo-three")
    fset = FileSet([one, two, three])
    assert set(fset.hash_files()) == {"one.foo", "two.foo", "three.foo"}
    assert set(fset.hash_files(relative_to=tmp_path / "fo")) == {  # codespell:ignore
        "o-one.foo",
        "o-two.foo",
        "o-three.foo",
    }
    assert set(one.hash_files(relative_to=one.fspath)) == {"."}
    with pytest.raises(FileFormatsNotRelativePathError):
        fset.hash_files(relative_to=tmp_path / "bar")


def test_hash_files_threaded_matches_serial(tmp_path: Path):
    dpath = tmp_path / "dir"
    (dpath / "sub").mkdir(parents=True)
    for i in range(20):
        (dpath / ("sub" if i % 2 else "") / f"{i}.txt").write_bytes(
            os.urandom(random.randint(0, 3 * 8192))
        )
    directory = Directory(dpath)
    serial = directory.hash_files(max_workers=1)
    assert len(serial) == 20
    assert directory.hash_files() == serial
    assert directory.hash_files(max_workers=4) == serial
    assert list(directory.hash_files(max_workers=4)) == list(serial)


def test_metadata_collation1():
    metadata_series = [
        {"a": 1, "b": 2},
        {"a": 1, "b": 3},
        {"a": 1, "b": 2},
    ]
    collated = collate_metadata_series(metadata_series)
    assert collated == {"a": 1, "b": [2, 3, 2]}


def test_metadata_collation2():
    metadata_series = [
        {"a": 1, "b": 2, "c": "foo"},
        {"a": 1, "b": 2, "c": "foo"},
        {"a": 1, "b": 3, "c": "foo"},
    ]
    collated = collate_metadata_series(metadata_series)
    assert collated == {"a": 1, "b": [2, 2, 3], "c": "foo"}
