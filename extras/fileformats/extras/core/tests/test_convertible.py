import inspect
import typing as ty

import pytest
from test_converter import archives_of, split_convertible_from

from fileformats.core import (
    ConvertibleTo,
    ConvertibleToMarker,
    LoadedMarker,
    from_mime,
    to_mime,
)
from fileformats.core.exceptions import FormatRecognitionError
from fileformats.image import Png, RasterImage
from fileformats.testing import Bar, Baz, Foo, Qux


def test_convertible_to_hint():
    hint = ConvertibleTo[Bar]
    assert ty.get_origin(hint) is ty.Annotated
    direct, generic = split_convertible_from(Bar)
    assert set(direct) == {Bar, Baz, Foo}
    assert set(archives_of(Bar)).issubset(generic)
    marker = ConvertibleToMarker.from_hint(hint)
    assert marker == ConvertibleToMarker(Bar)
    assert marker.format is Bar
    assert hint == Bar.convertible_from()
    assert marker.hint() == hint
    assert marker.resolve() == ty.get_args(hint)[0]
    assert LoadedMarker.from_hint(hint) is None


def test_convertible_no_converters():
    hint = ConvertibleTo[Baz]
    # Only generic converters (e.g. from archives) can convert to Baz
    direct, generic = split_convertible_from(Baz)
    assert direct == (Baz,)
    assert set(archives_of(Baz)).issubset(generic)
    assert ConvertibleToMarker.from_hint(hint).format is Baz


def test_convertible_in_signature():
    def func(in_file: ConvertibleTo[Bar] | None = None) -> Foo:
        raise NotImplementedError

    sig = inspect.signature(func, eval_str=True)
    in_marker = ConvertibleToMarker.from_hint(sig.parameters["in_file"].annotation)
    assert in_marker.format is Bar
    assert ConvertibleToMarker.from_hint(sig.return_annotation) is None


def test_convertible_requires_format():
    with pytest.raises(TypeError, match="requires a FileSet subclass"):
        ConvertibleTo[int]
    with pytest.raises(TypeError, match="requires a FileSet subclass"):
        ConvertibleTo[Foo | Bar]
    with pytest.raises(TypeError, match="only for annotations"):
        ConvertibleTo()  # type: ignore[operator]


@pytest.mark.parametrize(
    ["make_hint", "mime"],
    [
        [lambda: ConvertibleTo[Bar], "testing/bar+convertible-to"],
        [lambda: ConvertibleTo[Foo], "testing/foo+convertible-to"],
        [lambda: ConvertibleTo[Baz], "testing/baz+convertible-to"],
        [lambda: ConvertibleTo[Bar] | None, "testing/bar+convertible-to?"],
        [lambda: list[ConvertibleTo[Bar]], "testing/bar+convertible-to+list-of"],
        [lambda: ConvertibleTo[Bar] | Qux, "testing/bar+convertible-to|testing/qux"],
    ],
)
def test_convertible_mime_roundtrip(make_hint: ty.Callable[[], ty.Any], mime: str):
    # The hints are created in the test, rather than when the parameters are collected,
    # as the types they evaluate to depend on the converters that have been registered
    # by then (e.g. generic converters registered by other test modules)
    hint = make_hint()
    assert to_mime(hint, official=False) == mime
    assert from_mime(mime) == hint


def test_convertible_mime_official():
    with pytest.raises(TypeError, match="official"):
        to_mime(ConvertibleTo[Bar])


def test_convertible_mime_not_format():
    with pytest.raises(FormatRecognitionError):
        from_mime("testing/not-a-format+convertible-to")


def test_convertible_sorted_by_specificity():
    """Subclasses come before their base classes so that the first type in the union
    that matches a file-set is the most specific one"""
    for hint in (Bar.convertible_from(), Png.convertible_from()):
        args = ty.get_args(ty.get_args(hint)[0])
        assert len(args) > 1
        for i, tp in enumerate(args):
            assert not any(issubclass(later, tp) for later in args[i + 1 :])
    assert split_convertible_from(Png)[0] == (Png, RasterImage)
    by_name = split_convertible_from(Bar, union_sort_key=lambda t: t.__name__)[0]
    assert by_name == (Bar, Baz, Foo)
