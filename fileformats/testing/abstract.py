from abc import abstractproperty

from fileformats.generic import File


class AbstractFile(File):
    """Base class for all medical imaging data including pre-image raw data and
    associated data"""

    @abstractproperty
    def a_property(self) -> str:
        raise NotImplementedError


class AbstractSubclass(AbstractFile):
    pass


class ConcreteClass(AbstractFile):
    @property
    def a_property(self) -> str:
        return "Concrete implementation of a_property"


class AnotherConcreteClass(AbstractSubclass):
    @property
    def a_property(self) -> str:
        return "Another concrete implementation of a_property"


class ConvertibleToFile(File):
    """A class that can be converted from a file"""

    pass
