import tempfile
from pathlib import Path

import pytest
from pydra.compose import python

from fileformats.core import converter
from fileformats.core.converter_chain import ConverterChain
from fileformats.core.exceptions import FormatConversionError
from fileformats.testing import (
    AmbiguousDst,
    AmbiguousMid1,
    AmbiguousMid2,
    AmbiguousSrc,
    ChainDst,
    ChainMid,
    ChainSrc,
    CycleA,
    CycleB,
    CycleC,
)
from fileformats.text import Plain


def _append_step(in_file: Plain, step: str, ext: str) -> Path:
    out_file = Path(tempfile.mkdtemp()) / (in_file.stem + ext)
    out_file.write_text(in_file.read_text() + f"|{step}")
    return out_file


@converter
@python.define(outputs=["out_file"])  # type: ignore[untyped-decorator]
def src2mid(in_file: ChainSrc, tag: str = "mid") -> ChainMid:
    return ChainMid(_append_step(in_file, tag, ".chmid"))


@converter
@python.define(outputs=["out_file"])  # type: ignore[untyped-decorator]
def mid2dst(in_file: ChainMid, tag: str = "dst", upper: bool = False) -> ChainDst:
    out_file = ChainDst(_append_step(in_file, tag, ".chdst"))
    if upper:
        out_file.write_text(out_file.read_text().upper())
    return out_file


@converter
@python.define(outputs=["out_file"])  # type: ignore[untyped-decorator]
def a2b(in_file: CycleA) -> CycleB:
    return CycleB(_append_step(in_file, "b", ".cycb"))


@converter
@python.define(outputs=["out_file"])  # type: ignore[untyped-decorator]
def b2a(in_file: CycleB) -> CycleA:
    return CycleA(_append_step(in_file, "a", ".cyca"))


@converter
@python.define(outputs=["out_file"])  # type: ignore[untyped-decorator]
def b2c(in_file: CycleB) -> CycleC:
    return CycleC(_append_step(in_file, "c", ".cycc"))


@converter
@python.define(outputs=["out_file"])  # type: ignore[untyped-decorator]
def amb_src2mid1(in_file: AmbiguousSrc) -> AmbiguousMid1:
    return AmbiguousMid1(_append_step(in_file, "mid1", ".ambmid1"))


@converter
@python.define(outputs=["out_file"])  # type: ignore[untyped-decorator]
def amb_src2mid2(in_file: AmbiguousSrc) -> AmbiguousMid2:
    return AmbiguousMid2(_append_step(in_file, "mid2", ".ambmid2"))


@converter
@python.define(outputs=["out_file"])  # type: ignore[untyped-decorator]
def amb_mid12dst(in_file: AmbiguousMid1) -> AmbiguousDst:
    return AmbiguousDst(_append_step(in_file, "dst", ".ambdst"))


@converter
@python.define(outputs=["out_file"])  # type: ignore[untyped-decorator]
def amb_mid22dst(in_file: AmbiguousMid2) -> AmbiguousDst:
    return AmbiguousDst(_append_step(in_file, "dst", ".ambdst"))


def test_direct_converter_not_chained():
    conv = ChainMid.get_converter(ChainSrc)
    assert isinstance(conv.task, src2mid)


def test_chained_converter(tmp_path: Path):
    src_path = tmp_path / "file.chsrc"
    src_path.write_text("src")

    dst = ChainDst.convert(ChainSrc(src_path))

    assert isinstance(dst, ChainDst)
    assert dst.read_text() == "src|mid|dst"


def test_chained_converter_with_cycle(tmp_path: Path):
    src_path = tmp_path / "file.cyca"
    src_path.write_text("a")

    c = CycleC.convert(CycleA(src_path))

    assert c.read_text() == "a|b|c"


def test_chained_converter_not_found_with_cycle():
    with pytest.raises(FormatConversionError, match="Could not find converter"):
        CycleC.get_converter(ChainSrc)


def test_chained_converter_cached():
    conv = ChainDst.get_converter(ChainSrc)

    assert isinstance(conv.task, ConverterChain)
    assert [type(c.task) for c in conv.task.chain] == [src2mid, mid2dst]
    assert ChainDst.get_converter(ChainSrc) is conv


def test_chained_converter_disallowed():
    # Ensure chain is cached so that it is checked that cached chains aren't returned
    ChainDst.get_converter(ChainSrc)
    with pytest.raises(FormatConversionError, match="Could not find converter"):
        ChainDst.get_converter(ChainSrc, allow_chains=False)
    assert ChainMid.get_converter(ChainSrc, allow_chains=False) is not None


def test_chained_converter_ambiguous_picks_alphabetical(tmp_path: Path):
    src_path = tmp_path / "file.ambsrc"
    src_path.write_text("src")

    conv = AmbiguousDst.get_converter(AmbiguousSrc)
    dst = AmbiguousDst.convert(AmbiguousSrc(src_path))

    assert [type(c.task) for c in conv.task.chain] == [amb_src2mid1, amb_mid12dst]
    assert dst.read_text() == "src|mid1|dst"


def test_chained_converter_kwargs_applied_to_all_matching(tmp_path: Path):
    src_path = tmp_path / "file.chsrc"
    src_path.write_text("src")

    dst = ChainDst.convert(ChainSrc(src_path), tag="x", upper=True)

    assert dst.read_text() == "SRC|X|X"


def test_chained_converter_kwargs_for_named_step(tmp_path: Path):
    src_path = tmp_path / "file.chsrc"
    src_path.write_text("src")

    dst = ChainDst.convert(ChainSrc(src_path), **{"src2mid.tag": "x"})

    assert dst.read_text() == "src|x|dst"


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"unknown": 1}, "doesn't match an input"),
        ({"mid2dst.unknown": 1}, "doesn't match an input"),
        ({"unknown_step.tag": "x"}, "No converter step named 'unknown_step'"),
    ],
)
def test_chained_converter_kwargs_fail(tmp_path: Path, kwargs, match):
    src_path = tmp_path / "file.chsrc"
    src_path.write_text("src")

    with pytest.raises(FormatConversionError, match=match):
        ChainDst.convert(ChainSrc(src_path), **kwargs)
