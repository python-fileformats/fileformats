import inspect
from pathlib import Path
import typing as ty

import pytest

from fileformats.application import Dicom, Json
from fileformats.application.serialization import SerializationType
from fileformats.core import (
    FileSet,
    Loaded,
    LoadedMarker,
    check_loaded,
    extra,
    extra_implementation,
    find_extra_implementation,
)
from fileformats.core.loaded import resolve_loaded_type


class DeidSpec(Json):
    pass


def test_loaded_annotation() -> None:
    hint = Loaded[Json]
    assert ty.get_origin(hint) is ty.Annotated
    assert ty.get_args(hint)[0] == Json.loaded_type
    assert LoadedMarker.from_hint(hint) == LoadedMarker(Json)


def test_loaded_from_signature() -> None:
    def deidentify(spec: Loaded[DeidSpec]) -> None:
        pass

    hint = inspect.signature(deidentify, eval_str=True).parameters["spec"].annotation
    marker = LoadedMarker.from_hint(hint)
    assert marker is not None and marker.format is DeidSpec
    assert marker.accepts(DeidSpec) and not marker.accepts(Json)


def test_loaded_from_hint_other() -> None:
    assert LoadedMarker.from_hint(int) is None
    assert LoadedMarker.from_hint(ty.Annotated[int, "x"]) is None


def test_loaded_self() -> None:
    hint = Loaded[ty.Self]  # type: ignore[misc]
    assert ty.get_args(hint)[0] is ty.Any
    marker = LoadedMarker.from_hint(hint)
    assert marker is not None and marker.format is ty.Self  # type: ignore[comparison-overlap]


def test_loaded_requires_fileset() -> None:
    with pytest.raises(TypeError, match="requires a FileSet subclass"):
        Loaded[int]
    with pytest.raises(TypeError, match="only for annotations"):
        Loaded()  # type: ignore[operator]


def test_resolve_loaded_type() -> None:
    assert resolve_loaded_type(str) is str
    assert resolve_loaded_type("not_a_real_package.Thing") is ty.Any
    pydicom = pytest.importorskip("pydicom")
    assert resolve_loaded_type(Dicom.loaded_type) is pydicom.FileDataset


def test_check_loaded() -> None:
    check_loaded(Json, {"a": 1})
    check_loaded(Json, [1])
    check_loaded(FileSet, object())  # unconstrained
    check_loaded(Json, "a")  # scalar documents are valid JSON
    check_loaded(Json, None)
    with pytest.raises(TypeError, match="Expected data loaded from Json"):
        check_loaded(Json, {1, 2})


def test_loaded_type_drift_load() -> None:
    with pytest.raises(TypeError, match="return type"):

        @extra_implementation(FileSet.load)
        def load(spec: DeidSpec, **kwargs: ty.Any) -> str:
            raise NotImplementedError


def test_loaded_self_matches_loaded_format() -> None:
    """An implementation may annotate with either the loaded type or `Loaded[X]`"""

    class Spec(Json):
        pass

    @extra_implementation(FileSet.load)
    def load(spec: Spec, **kwargs: ty.Any) -> Loaded[Spec]:
        raise NotImplementedError

    @extra_implementation(FileSet.save)
    def save(spec: Spec, data: SerializationType, **kwargs: ty.Any) -> None:
        raise NotImplementedError


def test_loaded_type_drift_save() -> None:
    with pytest.raises(TypeError, match="Type of 'data' arg"):

        @extra_implementation(FileSet.save)
        def save(spec: DeidSpec, data: str, **kwargs: ty.Any) -> None:
            raise NotImplementedError


def test_save_checks_loaded_type(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="Expected data loaded from Json"):
        Json.new(tmp_path / "a.json", {1, 2})
    json_file = Json.new(tmp_path / "b.json", {"a": 1})
    assert json_file.load() == {"a": 1}


def test_load_checks_loaded_type(tmp_path: Path) -> None:
    class BadLoad(Json):
        pass

    @extra_implementation(FileSet.load)
    def load(bad: BadLoad, **kwargs: ty.Any) -> Loaded[BadLoad]:
        return {1, 2}

    fspath = tmp_path / "bad.json"
    fspath.write_text("{}")
    with pytest.raises(TypeError, match="Expected data loaded from BadLoad") as e:
        BadLoad(fspath).load()
    assert any("test_load_checks_loaded_type" in n for n in e.value.__notes__)


def test_load_scalar_json(tmp_path: Path) -> None:
    fspath = tmp_path / "scalar.json"
    fspath.write_text('"hello"')
    assert Json(fspath).load() == "hello"


def test_loaded_from_optional_hint() -> None:
    assert LoadedMarker.from_hint(Loaded[Json] | None) == LoadedMarker(Json)
    assert LoadedMarker.from_hint(ty.Optional[Loaded[Json]]) == LoadedMarker(Json)
    assert LoadedMarker.from_hint(Loaded[Json] | int) is None
    assert LoadedMarker.from_hint(int | None) is None


class Recipient(FileSet):
    @extra
    def apply(self, recipe: Loaded[FileSet] | None = None) -> None:
        raise NotImplementedError


class RecipientSub(Recipient):
    pass


def test_loaded_fileset_accepts_loaded_format() -> None:
    @extra_implementation(Recipient.apply)
    def apply(recipient: RecipientSub, recipe: Loaded[Json] | None = None) -> None:
        pass

    impl = find_extra_implementation(Recipient.apply, RecipientSub)
    assert impl is apply
    hint = ty.get_type_hints(impl, include_extras=True)["recipe"]
    marker = LoadedMarker.from_hint(hint)
    assert marker is not None and marker.format is Json


def test_loaded_all_from_hint() -> None:
    assert LoadedMarker.all_from_hint(Loaded[DeidSpec] | Loaded[Json] | None) == [
        LoadedMarker(DeidSpec),
        LoadedMarker(Json),
    ]
    assert LoadedMarker.all_from_hint(Loaded[Json]) == [LoadedMarker(Json)]
    assert LoadedMarker.all_from_hint(Loaded[Json] | None) == [LoadedMarker(Json)]
    assert LoadedMarker.all_from_hint(Loaded[Json] | int) is None
    assert LoadedMarker.all_from_hint(int | None) is None
    assert LoadedMarker.all_from_hint(None) is None


class RecipientUnionSub(Recipient):
    pass


def test_loaded_union_accepted_by_signature_check() -> None:
    """An implementation can accept a union of loaded formats where the extra method
    accepts `Loaded[FileSet] | None`"""

    @extra_implementation(Recipient.apply)
    def apply(
        recipient: RecipientUnionSub,
        recipe: Loaded[DeidSpec] | Loaded[Json] | None = None,
    ) -> None:
        pass

    impl = find_extra_implementation(Recipient.apply, RecipientUnionSub)
    assert impl is apply
    hint = ty.get_type_hints(impl, include_extras=True)["recipe"]
    assert [m.format for m in LoadedMarker.all_from_hint(hint)] == [DeidSpec, Json]


class Numeric(FileSet):
    @extra
    def scale(self, factor: int | float | None = None) -> None:
        raise NotImplementedError


class NumericSub(Numeric):
    pass


class NumericBadSub(Numeric):
    pass


def test_union_subset_accepted_by_signature_check() -> None:
    @extra_implementation(Numeric.scale)
    def scale(numeric: NumericSub, factor: int | None = None) -> None:
        pass

    assert find_extra_implementation(Numeric.scale, NumericSub) is scale


def test_union_not_accepted_by_method_rejected() -> None:
    """Each member of a union in the implementation must be accepted by the method"""
    with pytest.raises(TypeError, match="Arguments differ"):

        @extra_implementation(Numeric.scale)
        def scale(numeric: NumericBadSub, factor: int | str | None = None) -> None:
            pass
