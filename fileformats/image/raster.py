import typing  # noqa: F401
import typing as ty

from fileformats.core import validated_property
from fileformats.core.exceptions import FormatMismatchError
from fileformats.core.mixin import WithMagicNumber
from fileformats.core.typing import TypeAlias
from fileformats.generic import BinaryFile

from .base import Image

if ty.TYPE_CHECKING:
    import numpy.typing  # noqa: F401


DataArrayType: TypeAlias = (
    ty.Any
)  # In Python < 3.9 this is probmematic "numpy.typing.NDArray[typing.Union[numpy.floating[typing.Any], numpy.integer[typing.Any]]]"


class RasterImage(Image, BinaryFile):
    # iana_mime = None
    binary = True


class Bitmap(WithMagicNumber, RasterImage):
    ext = ".bmp"
    magic_number = b"BM"
    iana_mime = "image/bmp"
    alternative_exts = (".dib",)


class Gif(WithMagicNumber, RasterImage):
    ext = ".gif"
    iana_mime = "image/gif"
    magic_number = b"GIF8"


class Png(WithMagicNumber, RasterImage):
    ext = ".png"
    iana_mime = "image/png"
    magic_number = "89504E470D0A1A0A"


class Jpeg(WithMagicNumber, RasterImage):
    ext = ".jpg"
    alternate_exts = (".jpeg", ".jpe", ".jfif", ".jif")
    iana_mime = "image/jpeg"
    magic_number = "ffd8ffe0"


# Add alias for image/jpg
Jpg = Jpeg


class Tiff(RasterImage):

    ext = ".tiff"
    iana_mime = "image/tiff"

    magic_number_le = "49492A00"
    magic_number_be = "4D4D002A"

    @validated_property
    def endianness(self) -> str:
        read_magic = self.read_contents(len(self.magic_number_le) // 2)
        assert isinstance(read_magic, bytes)
        if read_magic == bytes.fromhex(self.magic_number_le):
            endianness = "little"
        elif read_magic == bytes.fromhex(self.magic_number_be):
            endianness = "big"
        else:
            read_magic_str = bytes.hex(read_magic)
            raise FormatMismatchError(
                f"Magic number of file '{read_magic_str}' doesn't match either the "
                f"little-endian '{self.magic_number_le}' and big-endian "
                f"'{self.magic_number_be}'"
            )
        return endianness


class Cr2(RasterImage):
    """Canon RAW image format (a TIFF-based container used by Canon cameras)."""

    ext = ".CR2"
    iana_mime = "image/x-canon-cr2"  # not an official IANA type, but the de facto
    # identifier used by shared-mime-info, ExifTool, etc.
