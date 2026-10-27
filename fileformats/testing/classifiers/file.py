import typing as ty
from fileformats.core import DataType, FileSet
from fileformats.generic import UnicodeFile
from fileformats.field import Singular
from fileformats.core.mixin import (
    WithClassifiers,
    WithOrderedClassifiers,
    WithClassifier,
)


class FileClassifier(DataType):
    pass


class A(FileClassifier):
    pass


class B(FileClassifier):
    pass


class C(FileClassifier):
    pass


class D(FileClassifier):
    pass


class E(C):
    pass


class F(WithClassifiers, UnicodeFile):
    classifiers_attr_name = "content_types"
    content_types = ()
    ext = ".f"


class G(F):
    ext = ".g"


class H(WithClassifiers, UnicodeFile):
    classifiers_attr_name = "content_types"
    content_types = ()
    ext = ".h"

    allowed_classifiers = (A, B, C)


class J(H):
    ext = ".j"


class K(WithOrderedClassifiers, UnicodeFile):

    ext = ".k"
    classifiers_attr_name = "new_classifiers_attr"
    new_classifiers_attr = ()


class L(WithOrderedClassifiers, UnicodeFile):

    ext = ".l"
    classifiers_attr_name = "new_classifiers_attr"
    new_classifiers_attr = ()


class M(WithClassifier, UnicodeFile):
    classifiers_attr_name = "content_types"
    content_types: ty.Optional[ty.Tuple[ty.Type[FileSet], ...]] = (
        None  # Should be None not ()
    )
    ext = ".m"


class N(WithClassifiers, UnicodeFile):
    classifiers_attr_name = "content_types"
    content_types: ty.Optional[ty.Tuple[ty.Type[FileSet], ...]] = ()
    ext = ".n"


class TestField(Singular[ty.Any, str]):

    value: ty.Any
    primitive = str


class P(WithClassifiers, UnicodeFile):
    ext = ".p"
    classifiers_attr_name = "content_types"
    content_types = ()


class Q(WithClassifiers, UnicodeFile):
    ext = ".z"
    classifiers_attr_name = "new_classifiers_attr"
    # MISSING default value for "new_classifiers_attr"


class R(WithOrderedClassifiers, UnicodeFile):

    ext = ".r"
    classifiers_attr_name = "new_classifiers_attr"
    new_classifiers_attr = ()
