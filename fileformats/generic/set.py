import itertools
import typing as ty
from pathlib import Path

from fileformats.core import FileSet
from fileformats.core.collection import TypedCollection
from fileformats.core.mixin import WithClassifiers


class TypedSet(TypedCollection):
    """List of specific file types (similar to the contents of a directory but not
    enclosed in one)"""

    MAX_REPR_PATHS = 3

    @property
    def content_fspaths(self) -> ty.Iterable[Path]:
        return self.fspaths

    def __repr__(self) -> str:
        paths_repr = (
            "'"
            + "', '".join(str(p) for p in sorted(self.fspaths)[: self.MAX_REPR_PATHS])
            + "'"
        )
        if len(self.fspaths) > self.MAX_REPR_PATHS:
            paths_repr += ", ..."
        return f"{self.type_name}({paths_repr})"

    def required_paths(self) -> ty.FrozenSet[Path]:
        # Use the unsorted (and uncached) contents, as sub-classes may sort them in ways
        # that are expensive to compute (e.g. DicomSeries reads the header of every file
        # to sort by SOPInstanceUID), and the order doesn't matter here
        contents = TypedCollection.contents.func(self)
        return frozenset(itertools.chain(*(c.required_paths() for c in contents)))


class SetOf(WithClassifiers, TypedSet):  # type: ignore[misc]
    # WithClassifiers-required class attrs
    classifiers_attr_name = "content_types"
    allowed_classifiers = (FileSet,)
    allow_optional_classifiers = True
    generically_classifiable = True
