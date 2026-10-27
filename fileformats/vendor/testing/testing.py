from fileformats.core import Classifier, DataType, __version__
from fileformats.core.mixin import WithClassifiers


class VendorClassified(WithClassifiers, DataType):
    classifiers_attr_name = "classifiers"
    classifiers = ()
    allowed_classifiers = (Classifier,)
    generically_classifiable = False


class Psi(DataType):
    pass


class Zeta(Classifier):
    pass


class Theta(Classifier):
    pass


__all__ = ["VendorClassified", "Psi", "Zeta", "Theta", "__version__"]
