"""The source types of generic converters (i.e. with wildcard classifiers) are
included in `convertible_from()` with their wildcards resolved from the target type"""

import typing as ty

from fileformats.application import Tar, TarGzip, Zip
from fileformats.core import FileSet
from fileformats.generic import Directory, DirectoryOf, SetOf
from fileformats.text import TextFile


def members(datatype: type[FileSet]) -> tuple[type, ...]:
    union = ty.get_args(datatype.convertible_from())[0]
    return ty.get_args(union) or (union,)


def test_convertible_from_generic_container_conversion() -> None:
    """`SetOf[T]` -> `DirectoryOf[T]` is registered on the unclassified `DirectoryOf`,
    so `T` is resolved from the classifier of the target"""
    assert SetOf[TextFile] in members(DirectoryOf[TextFile])
    assert DirectoryOf[TextFile].get_converter(SetOf[TextFile]) is not None


def test_convertible_from_archives() -> None:
    """`Zip[Compressed]` -> `Compressed` etc. can extract any type from an archive"""
    for archive in (Zip, Tar, TarGzip):
        assert archive[TextFile] in members(TextFile)
        assert TextFile.get_converter(archive[TextFile]) is not None


def test_convertible_from_wildcard_source() -> None:
    """`Compressed` -> `Zip[Compressed]` converts a type into an archive of it, so the
    archived type is resolved from the classifier of the target"""
    assert TextFile in members(Zip[TextFile])


def test_convertible_from_has_no_wildcard_types() -> None:
    """Unresolved source types of generic converters (e.g. `SetOf[T]`) can't be
    instantiated, so aren't included for types they can't be resolved from (i.e.
    unclassified ones)"""
    for datatype in (FileSet, Directory, TextFile):
        assert not [
            t
            for t in members(datatype)
            if hasattr(t, "wildcard_classifiers") and t.wildcard_classifiers()
        ]
