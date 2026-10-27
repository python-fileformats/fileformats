import os
import typing as ty
from pathlib import Path

import pytest

from fileformats.core import (
    FileSet,
    extra,
    extra_implementation,
    staged_out_dir,
    validated_property,
)
from fileformats.core.exceptions import FormatMismatchError
from fileformats.generic import Directory, File


class Leaf(File):
    ext = ".leaf"


class Inner(Directory):
    @validated_property
    def leaves(self) -> ty.List[Leaf]:
        found = [Leaf(p) for p in sorted(self.fspath.glob("*.leaf"))]
        if not found:
            raise FormatMismatchError(f"No leaves in {self.fspath}")
        return found


class Outer(Directory):
    @validated_property
    def inners(self) -> ty.Dict[str, Inner]:
        return {p.name: Inner(p) for p in sorted(self.fspath.glob("inner*"))}

    @validated_property
    def top_leaf(self) -> Leaf:
        return Leaf(self.fspath / "top.leaf")


class WithExternal(Directory):
    @validated_property
    def external(self) -> Leaf:
        return Leaf(self.fspath.parent / "external.leaf")


def _make_outer(root: Path) -> Outer:
    outer = root / "outer"
    for inner in ("inner1", "inner2"):
        (outer / inner).mkdir(parents=True)
        (outer / inner / "a.leaf").write_text("original")
        (outer / inner / "notes.txt").write_text("notes")
    (outer / "top.leaf").write_text("original")
    (outer / ".hidden").write_text("hidden")
    return Outer(outer)


def _contents(fileset: FileSet, root: Path) -> ty.Dict[str, str]:
    # Keys use "/" separators on all platforms (incl. Windows)
    return {
        p.relative_to(root).as_posix(): p.read_text() for p in fileset.all_file_paths()
    }


def _modify(nested: FileSet, dest_dir: Path) -> ty.Optional[FileSet]:
    """Writes modified copies of Leaf files, and leaves the rest to be copied"""
    if isinstance(nested, Leaf):
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / nested.fspath.name
        dest.write_text("modified")
        return Leaf(dest)
    if isinstance(nested, Inner):
        return nested.map_nested(dest_dir, _modify)
    return None


def test_nested_filesets_within_dicts_and_lists(tmp_path: Path) -> None:
    outer = _make_outer(tmp_path)
    direct = outer.nested_filesets(recursive=False)
    assert [type(n).__name__ for n in direct] == ["Inner", "Inner", "Leaf"]
    assert [type(n).__name__ for n in outer.nested_filesets()] == [
        "Inner",
        "Leaf",
        "Inner",
        "Leaf",
        "Leaf",
    ]


def test_map_nested(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    mapped = _make_outer(tmp_path / "in").map_nested(out_dir, _modify)

    assert isinstance(mapped, Outer)
    assert mapped.fspath == out_dir / "outer"
    assert _contents(mapped, out_dir) == {
        "outer/.hidden": "hidden",
        "outer/inner1/a.leaf": "modified",
        "outer/inner1/notes.txt": "notes",
        "outer/inner2/a.leaf": "modified",
        "outer/inner2/notes.txt": "notes",
        "outer/top.leaf": "modified",
    }


def test_map_nested_none_copies_unchanged(tmp_path: Path) -> None:
    outer = _make_outer(tmp_path / "in")
    mapped = outer.map_nested(tmp_path / "out", lambda nested, dest_dir: None)
    assert _contents(mapped, tmp_path / "out") == _contents(outer, tmp_path / "in")


def test_map_nested_skips_external(tmp_path: Path) -> None:
    (tmp_path / "in" / "dir").mkdir(parents=True)
    (tmp_path / "in" / "dir" / "own.txt").write_text("own")
    (tmp_path / "in" / "external.leaf").write_text("external")
    called = []

    def func(nested: FileSet, dest_dir: Path) -> None:
        called.append(nested)

    with pytest.raises(FileNotFoundError, match="external.leaf"):
        # the copy doesn't include the external file, so isn't a valid WithExternal
        WithExternal(tmp_path / "in" / "dir").map_nested(tmp_path / "out", func)
    assert called == []
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["dir"]
    assert not (tmp_path / "out" / "external.leaf").exists()


def test_map_nested_checks_layout(tmp_path: Path) -> None:
    def rename(nested: FileSet, dest_dir: Path) -> ty.Optional[FileSet]:
        if isinstance(nested, Leaf) and nested.fspath.name == "top.leaf":
            dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / "renamed.leaf").write_text("modified")
            return Leaf(dest_dir / "renamed.leaf")
        return None

    with pytest.raises(FileNotFoundError, match="top.leaf"):
        _make_outer(tmp_path / "in").map_nested(tmp_path / "out", rename)


class Staged(File):
    ext = ".staged"

    @extra(wrapper=staged_out_dir)
    def write_copy(self, out_dir: "os.PathLike[str]", fail: bool = False) -> "Staged":
        raise NotImplementedError


@extra_implementation(Staged.write_copy)
def staged_write_copy(
    staged: Staged, out_dir: "os.PathLike[str]", fail: bool = False
) -> Staged:
    out_path = Path(out_dir) / staged.fspath.name
    out_path.write_text("written")
    if fail:
        raise RuntimeError("failed")
    return Staged(out_path)


def test_staged_out_dir(tmp_path: Path) -> None:
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "a.staged").write_text("original")
    out_dir = tmp_path / "out"
    written = Staged(tmp_path / "in" / "a.staged").write_copy(out_dir)

    assert written.fspath == out_dir / "a.staged"
    assert written.fspath.read_text() == "written"
    # the staging directory is cleaned up
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in", "out"]


def test_staged_out_dir_failure_leaves_nothing(tmp_path: Path) -> None:
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "a.staged").write_text("original")
    out_dir = tmp_path / "out"
    with pytest.raises(RuntimeError, match="failed"):
        Staged(tmp_path / "in" / "a.staged").write_copy(out_dir, fail=True)
    assert not out_dir.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in"]


def test_staged_out_dir_wont_overwrite(tmp_path: Path) -> None:
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "a.staged").write_text("original")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "a.staged").write_text("existing")
    with pytest.raises(FileExistsError):
        Staged(tmp_path / "in" / "a.staged").write_copy(out_dir)
    assert (out_dir / "a.staged").read_text() == "existing"
