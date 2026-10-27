import typing as ty

from fileformats.core import FileSet
from fileformats.core.mixin import WithClassifier, WithMagicNumber
from fileformats.generic import BinaryFile


class Archive(BinaryFile):
    "Base class for compressed archives"

    archived_type: ty.Optional[ty.Type[FileSet]] = None


class WithArchiveClassifiers(WithClassifier):
    "Base class for compressed archives"

    classifiers_attr_name = "archived_type"
    allowed_classifiers = (FileSet,)
    generically_classifiable = True


# Compressed formats
class BaseZip(WithMagicNumber, Archive):
    ext = ".zip"
    magic_number = "504B0304"


class BaseBzip(WithMagicNumber, Archive):
    ext = ".bzip"
    magic_number = "425a"


class BaseGzip(WithMagicNumber, Archive):
    ext = ".gz"
    magic_number = "1F8B08"


class BaseTar(WithMagicNumber, Archive):
    ext = ".tar"
    magic_number = "7573746172"
    magic_number_offset = 257


class BaseTarGzip(WithMagicNumber, Archive):
    # FIXME: Should capture the relationship to Gzip and Tar somehow, but a bit
    # tricky to get it right
    ext = ".tar.gz"
    magic_number = "1F8B08"
    alternate_exts = (".tgz",)


class Zip(WithArchiveClassifiers, BaseZip):
    iana_mime = "application/zip"


class Bzip(WithArchiveClassifiers, BaseBzip):
    iana_mime = "application/bzip"


class Gzip(WithArchiveClassifiers, BaseGzip):
    iana_mime = "application/gzip"


class Tar(WithArchiveClassifiers, BaseTar):
    iana_mime = "application/x-tar"


class TarGzip(WithArchiveClassifiers, BaseTarGzip):
    iana_mime = "application/x-tar+gzip"
