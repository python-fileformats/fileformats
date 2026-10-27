import typing as ty
from pathlib import Path

import pytest

from fileformats.generic import DirectoryOf, SetOf
from fileformats.text import TextFile


@pytest.fixture
def file_names() -> ty.List[str]:
    return ["file1.txt", "file2.txt", "file3.txt"]


@pytest.fixture
def files_dir(file_names: ty.List[str], tmp_path: Path) -> Path:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    for fname in file_names:
        (out_dir / fname).write_text(fname)
    return out_dir


@pytest.fixture
def test_files(files_dir: Path, file_names: ty.List[str]) -> ty.List[Path]:
    return [files_dir / n for n in file_names]


def test_list_dir_contents(
    files_dir: Path, test_files: ty.List[Path], tmp_path: Path
) -> None:
    text_set = SetOf[TextFile].convert(DirectoryOf[TextFile](files_dir))  # type: ignore[misc]
    assert sorted(t.name for t in text_set.contents) == sorted(
        f.name for f in test_files
    )


def test_put_contents_in_dir(
    file_names: ty.List[str], test_files: ty.List[Path], tmp_path: Path
) -> None:
    text_dir = DirectoryOf[TextFile].convert(SetOf[TextFile](test_files))  # type: ignore[misc]
    assert sorted(t.name for t in text_dir.contents) == file_names
