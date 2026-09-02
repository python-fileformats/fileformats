import typing as ty
import pytest
import time
from fileformats.core import FileSet, FileSetMetadata, extra_implementation
from fileformats.generic import BinaryFile


class FileWithMetadata(BinaryFile):
    ext = ".mf"


@extra_implementation(FileSet.read_metadata)
def aformat_read_metadata(
    mf: FileWithMetadata,
    selected_keys: ty.Optional[ty.Collection[str]] = None,
    **kwargs: ty.Any,
) -> ty.Mapping[str, ty.Any]:
    with open(mf) as f:
        metadata = f.read()
    dct = dict(ln.split(":") for ln in metadata.splitlines())
    if selected_keys:
        dct = {k: v for k, v in dct.items() if k in selected_keys}
    return dct


@pytest.fixture
def file_with_metadata_fspath(tmp_path):
    metadata = {
        "a": 1,
        "b": 2,
        "c": 3,
        "d": 4,
        "e": 5,
    }
    fspath = tmp_path / "metadata-file.mf"
    with open(fspath, "w") as f:
        f.write("\n".join("{}:{}".format(*t) for t in metadata.items()))
    return fspath


def test_metadata(file_with_metadata_fspath):
    file_with_metadata = FileWithMetadata(file_with_metadata_fspath)
    assert file_with_metadata.metadata["a"] == "1"
    assert sorted(file_with_metadata.metadata) == ["a", "b", "c", "d", "e"]


def test_select_metadata(file_with_metadata_fspath):
    file_with_metadata = FileWithMetadata(
        file_with_metadata_fspath, selected_keys=["a", "b", "c"]
    )
    assert file_with_metadata.metadata["a"] == "1"
    assert sorted(file_with_metadata.metadata) == ["a", "b", "c"]


def test_explicit_metadata(file_with_metadata_fspath):
    file_with_metadata = FileWithMetadata(
        file_with_metadata_fspath,
        metadata={
            "a": 1,
            "b": 2,
            "c": 3,
        },
    )
    # Check that we use the explicitly provided metadata and not one from the file
    # contents
    assert sorted(file_with_metadata.metadata) == ["a", "b", "c"]
    # add new metadata line to check and check that it isn't reloaded
    with open(file_with_metadata, "a") as f:
        f.write("\nf:6")
    assert sorted(file_with_metadata.metadata) == ["a", "b", "c"]


def test_metadata_reload(file_with_metadata_fspath):
    file_with_metadata = FileWithMetadata(file_with_metadata_fspath)
    assert sorted(file_with_metadata.metadata) == ["a", "b", "c", "d", "e"]
    # add new metadata line to check and check that it is reloaded
    time.sleep(2)
    with open(file_with_metadata, "a") as f:
        f.write("\nf:6")
    assert sorted(file_with_metadata.metadata) == ["a", "b", "c", "d", "e", "f"]


# ── overlay: values set on the object ───────────────────────────────────────


def test_metadata_is_mutable_mapping(file_with_metadata_fspath):
    mf = FileWithMetadata(file_with_metadata_fspath)
    assert isinstance(mf.metadata, FileSetMetadata)
    assert isinstance(mf.metadata, ty.MutableMapping)


def test_metadata_setitem_persists_after_read(file_with_metadata_fspath):
    mf = FileWithMetadata(file_with_metadata_fspath)
    # trigger a load first, so the overlay is written *after* the loaded layer exists
    assert mf.metadata["a"] == "1"
    mf.metadata["injected"] = "yes"
    assert mf.metadata["injected"] == "yes"
    assert mf.metadata.get("injected") == "yes"
    assert "injected" in mf.metadata
    assert sorted(mf.metadata) == ["a", "b", "c", "d", "e", "injected"]
    assert mf.metadata.as_dict()["injected"] == "yes"


def test_metadata_overlay_overrides_loaded(file_with_metadata_fspath):
    mf = FileWithMetadata(file_with_metadata_fspath)
    assert mf.metadata["a"] == "1"
    mf.metadata["a"] = "overridden"
    assert mf.metadata["a"] == "overridden"
    assert dict(mf.metadata)["a"] == "overridden"
    # the key is not duplicated in iteration
    assert sorted(mf.metadata) == ["a", "b", "c", "d", "e"]


def test_metadata_overlay_survives_reload(file_with_metadata_fspath):
    mf = FileWithMetadata(file_with_metadata_fspath)
    assert sorted(mf.metadata) == ["a", "b", "c", "d", "e"]
    mf.metadata["a"] = "overridden"
    mf.metadata["injected"] = "yes"
    # change the file so the loaded layer is invalidated and re-read
    time.sleep(2)
    with open(mf, "a") as f:
        f.write("\nf:6")
    assert mf.metadata["f"] == "6"  # loaded layer picked up the new key
    assert mf.metadata["a"] == "overridden"  # overlay still wins
    assert mf.metadata["injected"] == "yes"  # overlay survived the reload


def test_metadata_delitem_only_touches_overlay(file_with_metadata_fspath):
    mf = FileWithMetadata(file_with_metadata_fspath)
    mf.metadata["injected"] = "yes"
    del mf.metadata["injected"]
    assert "injected" not in mf.metadata
    # a key that only exists in the loaded layer can't be deleted
    with pytest.raises(KeyError):
        del mf.metadata["a"]
    assert mf.metadata["a"] == "1"


def test_explicit_metadata_is_still_settable(file_with_metadata_fspath):
    mf = FileWithMetadata(file_with_metadata_fspath, metadata={"a": 1, "b": 2, "c": 3})
    assert sorted(mf.metadata) == ["a", "b", "c"]
    mf.metadata["d"] = 4
    mf.metadata["a"] = "overridden"
    assert mf.metadata["a"] == "overridden"
    assert sorted(mf.metadata) == ["a", "b", "c", "d"]
    # the file is still never read
    with open(mf, "a") as f:
        f.write("\nf:6")
    assert "f" not in mf.metadata


def test_metadata_len_and_contains(file_with_metadata_fspath):
    mf = FileWithMetadata(file_with_metadata_fspath)
    assert len(mf.metadata) == 5
    mf.metadata["injected"] = "yes"
    assert len(mf.metadata) == 6
    mf.metadata["a"] = "overridden"  # already a loaded key -> no length change
    assert len(mf.metadata) == 6
    assert "a" in mf.metadata and "injected" in mf.metadata
    assert "missing" not in mf.metadata


def test_metadata_equality_with_plain_dict(file_with_metadata_fspath):
    mf = FileWithMetadata(file_with_metadata_fspath, metadata={"a": 1, "b": 2})
    assert mf.metadata == {"a": 1, "b": 2}
    mf.metadata["a"] = 99
    assert mf.metadata == {"a": 99, "b": 2}
