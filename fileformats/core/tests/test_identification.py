import itertools
import typing as ty
from collections import Counter
from pathlib import Path

import pytest

import fileformats.text
from fileformats.application import Json, Yaml, Zip
from fileformats.core import FileSet, find_matching, from_mime, from_paths, to_mime
from fileformats.core.exceptions import FormatRecognitionError
from fileformats.generic import File, SetOf
from fileformats.testing import Bar, Foo
from fileformats.text import Plain, TextFile


def test_format_detection(work_dir) -> None:
    text_file = work_dir / "text.txt"

    with open(text_file, "w") as f:
        f.write("sample text")

    detected = find_matching(text_file, standard_only=True)
    assert sorted(detected, key=lambda f: f.mime_like) == [
        fileformats.text.Prs_Fallenstein_Rst,
        fileformats.text.Prs_Prop_Logic,
        fileformats.text.TextFile,
    ]


def test_to_from_mime_roundtrip() -> None:
    mime_str = to_mime(Foo, official=False)
    assert isinstance(mime_str, str)
    assert from_mime(mime_str) == Foo


def test_to_from_list_mime_roundtrip() -> None:
    mime_str = to_mime(list[Foo], official=False)
    assert isinstance(mime_str, str)
    assert from_mime(mime_str) == list[Foo]


def test_to_from_tuple_mime_roundtrip() -> None:
    mime_str = to_mime(tuple[Foo], official=False)
    assert isinstance(mime_str, str)
    assert from_mime(mime_str) == tuple[Foo]


def test_to_from_union_mime_roundtrip() -> None:
    mime_str = to_mime(Foo | Bar, official=False)
    assert isinstance(mime_str, str)
    assert from_mime(mime_str) == Foo | Bar


def test_to_from_list_union_mime_roundtrip() -> None:
    mime_str = to_mime(list[Foo | Bar], official=False)
    assert isinstance(mime_str, str)
    assert from_mime(mime_str) == list[Foo | Bar]


def test_to_from_mime_optional_roundtrip() -> None:
    mime_str = to_mime(Foo | None, official=False)
    assert isinstance(mime_str, str)
    assert mime_str.endswith("?")
    assert from_mime(mime_str) == Foo | None


def test_official_mime_fail() -> None:
    with pytest.raises(TypeError, match="as it is not a proper file-type"):
        to_mime(ty.List[Foo], official=True)


def test_repr() -> None:
    for frmt in FileSet.all_formats:
        assert repr(frmt.mock("/a/path")).startswith(f"{frmt.__name__}(")


def test_set_repr_trunc() -> None:
    a = Path("/a/path").absolute()
    b = Path("/b/path").absolute()
    c = Path("/c/path").absolute()
    d = Path("/d/path").absolute()
    assert (
        repr(SetOf[File].mock(a, b, c, d)) == f"SetOf[File]('{a}', '{b}', '{c}', ...)"
    )


def test_from_paths(tmp_path) -> None:
    filesets = []
    filesets.append(Json.sample(tmp_path, seed=1))
    filesets.append(Json.sample(tmp_path, seed=2))
    filesets.append(Json.sample(tmp_path, seed=3))
    filesets.append(Yaml.sample(tmp_path, seed=1))
    filesets.append(Yaml.sample(tmp_path, seed=2))
    filesets.append(Zip.sample(tmp_path))
    filesets.append(Foo.sample(tmp_path, seed=1))
    filesets.append(Foo.sample(tmp_path, seed=2))
    filesets.append(Foo.sample(tmp_path, seed=3))
    filesets.append(Bar.sample(tmp_path))
    filesets.append(TextFile.sample(tmp_path))

    fspaths = list(itertools.chain(*(f.fspaths for f in filesets)))

    detected = from_paths(fspaths, Json, Yaml, Zip, Foo, Bar, TextFile)

    assert set(detected) == set(filesets)

    count = Counter(type(f) for f in detected)

    assert count[Json] == 3
    assert count[Zip] == 1
    assert count[Yaml] == 2
    assert count[Foo] == 3
    assert count[Bar] == 1
    assert count[TextFile] == 1

    # redetect, but use a plain text file instead of TextFile
    detected = from_paths(fspaths, Json, Yaml, Zip, Foo, Bar, Plain)

    count = Counter(type(f) for f in detected)

    assert count[Plain] == 1

    with pytest.raises(
        FormatRecognitionError, match="were not recognised by any of the candidate"
    ):
        from_paths(fspaths, Json, Yaml, Zip, Foo, Bar)

    from_paths(fspaths, Json, Yaml, Zip, Foo, Bar, ignore=r".*\.txt")
