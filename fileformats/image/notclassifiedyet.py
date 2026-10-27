import typing as ty

from fileformats.core.mixin import WithMagicNumber
from fileformats.generic import BinaryFile

from .base import Image


class Aces(WithMagicNumber, BinaryFile, Image):
    """

    TODO: or 76 2F 31 01 02 04 00 00 The attribute acesImageContainerFlag has value 1"""

    iana_mime = "image/aces"
    ext = ".exr"
    magic_number = "762f310102000000"


class Apng(WithMagicNumber, BinaryFile, Image):
    """"""

    iana_mime = "image/apng"
    ext = ".apng"
    magic_number = "89504e470d0a1a0a"


class Avci(Image, BinaryFile):
    """"""

    iana_mime = "image/avci"
    ext = ".avci"


class Avcs(Image, BinaryFile):
    """"""

    iana_mime = "image/avcs"
    ext = ".avcs"


class Avif(Image, BinaryFile):
    """"""

    iana_mime = "image/avif"
    ext = ".avif"
    alternative_exts = (".heif", ".heifs", ".hif")


class Cgm(Image, BinaryFile):
    """"""

    iana_mime = "image/cgm"
    ext = None


class DicomRle(Image, BinaryFile):
    """"""

    iana_mime = "image/dicom-rle"
    ext = ".drle"


class Dpx(WithMagicNumber, BinaryFile, Image):
    """

    TODO: 0x53445058 (most-significant byte first
    file) or 58 50"""

    iana_mime = "image/dpx"
    ext = ".dpx"
    magic_number = "53445058"


class Emf(Image, BinaryFile):
    """Office productivity applications; clip art applications; desktop
    publishing applications; some web browsers (e.g., Internet
    Explorer).

    TODO: 0x01000000 (little-endian DWORD 0x00000001), corresponding to
    the EMR_HEADER Type field.
    The next field (EMR_HEADER Size) should be at least 88 (little-
    endian DWORD 0x00000050)."""

    iana_mime = "image/emf"
    ext = ".emf"


class Fits(WithMagicNumber, BinaryFile, Image):
    """There are many astronomical image viewing and data reduction

    A FITS file described with the media type "image/fits" SHOULD have a PHDU with
    positive integer values for the NAXIS and NAXISn keywords, and hence SHOULD contain
    at least one pixel. Files with 4 or more non-degenerate axes (NAXISn>1) SHOULD be
    described as "application/fits", not as "image/fits". (In rare cases it may be
    appropriate to describe a NULL image -- a dataless container for FITS keywords,
    with NAXIS=0 or NAXISn=0 -- or an image with 4+ non- degenerate axes as "image/fits"
    but this usage is discouraged because such files may confuse simple image viewer
    applications.)  FITS files declared as "image/fits" MAY also have one or more
    conforming XHDUs following their PHDUs. These extension HDUs MAY contain standard,
    non-linear, world coordinate system (WCS) information in the form of tables or images.
    The extension HDUs MAY also contain other, non-standard metadata pertaining to the
    image in the PHDU in the forms of keywords and tables.  A FITS file described with
    the media type "image/fits" SHOULD be principally intended to communicate the single
    data array in the PHDU. This means that "image/fits" SHOULD NOT be applied to FITS
    files containing MEF (multi-exposure-frame) mosaic images. Also, random groups files
    MUST be described as "application/fits" and not as "image/fits".  A FITS file described
    with the media type "image/fits" is also valid as a file of media type "application/fits".
    The choice of classification depends on the context and intended usage.

        TODO: "SIMPLE = T"  Jeff Uphoff of the National Radio Astronomy Observatory (NRAO)
        has contributed database entries for the magic number file which is used by the
        Unix "file" command. Magic number files with these entries are distributed with a
        variety of Unix-like operating systems. In addition to recognizing a FITS file using
        the string given above, the Uphoff entries also recognize the data type of the
        pixels in the PHDU.
    """

    iana_mime = "image/fits"
    ext = ".fits"
    alternative_exts = (".fit", ".fts", None)
    magic_number = b"SIMPLE = T"


class G3fax(Image, BinaryFile):
    """"""

    iana_mime = "image/g3fax"
    ext: ty.Optional[str] = None


class Heic(Image, BinaryFile):
    """"""

    iana_mime = "image/heic"
    ext = ".heic"


class HeicSequence(Image, BinaryFile):
    """"""

    iana_mime = "image/heic-sequence"
    ext = ".heics"


class Heif(Image, BinaryFile):
    """"""

    iana_mime = "image/heif"
    ext = ".heif"


class HeifSequence(Image, BinaryFile):
    """"""

    iana_mime = "image/heif-sequence"
    ext = ".heifs"


class Hej2k(Image, BinaryFile):
    """"""

    iana_mime = "image/hej2k"
    ext = ".hej2"


class Hsj2(Image, BinaryFile):
    """"""

    iana_mime = "image/hsj2"
    ext = ".hsj2"


class J2c(WithMagicNumber, BinaryFile, Image):
    """"""

    iana_mime = "image/j2c"
    ext = ".j2c"
    alternative_exts = (".J2C", ".j2k", ".J2K")
    magic_number = "ff4fff51"


class Jls(Image, BinaryFile):
    """"""

    iana_mime = "image/jls"
    ext = ".jls"


class Jp2(WithMagicNumber, BinaryFile, Image):
    """"""

    iana_mime = "image/jp2"
    ext = ".jp2"
    alternative_exts = (".jpg2",)
    magic_number = "0000000c6a5020200d0a870a"


class Jph(Image, BinaryFile):
    """

    TODO: See Section 4.4 of RFC 3745"""

    iana_mime = "image/jph"
    ext = ".jph"


class Jphc(WithMagicNumber, BinaryFile, Image):
    """"""

    iana_mime = "image/jphc"
    ext = ".jhc"
    magic_number = "ff4fff51"


class Jpm(WithMagicNumber, BinaryFile, Image):
    """"""

    iana_mime = "image/jpm"
    ext = ".jpm"
    alternative_exts = (".jpgm",)
    magic_number = "0000000c6a5020200d0a870a"


class Jpx(WithMagicNumber, BinaryFile, Image):
    """"""

    iana_mime = "image/jpx"
    ext = ".jpf"
    magic_number = "0000000c6a5020200d0a870a"


class Jxr(WithMagicNumber, BinaryFile, Image):
    """Imaging, fax, messaging and multimedia.

    TODO: Data begins with a FILE_HEADER( ) data structure, which begins  with a
    FIXED_FILE_HEADER_II_2BYTES field equal to 0x4949, followed by a
    FIXED_FILE_HEADER_0XBC_BYTE field equal to 0xBC, followed by a FILE_VERSION_ID which
    is equal to 1 for the current version of the Recommendation and International
    Standard (with other values reserved for future use, as modified in additional
    parts or amendments, by ITU-T or ISO/IEC).  Within the payload data, JPEG XR
    IMAGE_HEADER( ) data structures begin with a GDI_SIGNATURE, which is a 64-bit
    syntax element that has the value 0x574D50484F544F00 that corresponds to "WMPHOTO"
    using the UTF-8 character set encoding specified in Annex D of ISO/IEC 10646,
    followed by a byte equal to 0.
    """

    iana_mime = "image/jxr"
    ext = ".jxr"
    magic_number = "4949bc"


class Jxra(Image, BinaryFile):
    """"""

    iana_mime = "image/jxrA"
    ext = ".jxra"


class Jxrs(Image, BinaryFile):
    """"""

    iana_mime = "image/jxrS"
    ext = ".jxrs"


class Jxs(WithMagicNumber, BinaryFile, Image):
    """"""

    iana_mime = "image/jxs"
    ext = ".jxs"
    magic_number = "0000000c4a5853200d0a870a"


class Jxsc(WithMagicNumber, BinaryFile, Image):
    """"""

    iana_mime = "image/jxsc"
    ext = ".jxsc"
    magic_number = "ff10ff50"


class Jxsi(Image, BinaryFile):
    """"""

    iana_mime = "image/jxsi"
    ext = ".jxsi"


class Jxss(Image, BinaryFile):
    """"""

    iana_mime = "image/jxss"
    ext = ".jxss"


class Ktx(WithMagicNumber, BinaryFile, Image):
    """Currently only etcpack. It is anticipated it will be widely used by applications
    built on top of the OpenGL family of standards, OpenGL, OpenGL ES and WebGL, as the
    means of delivering texture data."""

    iana_mime = "image/ktx"
    ext = ".ktx"
    magic_number = "ab4b5458203131bb0d0a1a0a"


class Ktx2(WithMagicNumber, BinaryFile, Image):
    """"""

    iana_mime = "image/ktx2"
    ext = ".ktx2"
    magic_number = "ab4b5458203230bb0d0a1a0a"


class Naplps(Image, BinaryFile):
    """"""

    iana_mime = "image/naplps"
    ext = None


class Prs_Btif(Image, BinaryFile):
    """

    TODO: Since BTIF files are an extension of TIFF 6.0, the magic numbers
    are exactly the same as for TIFF 6.0.  The BTIF file
    specification does not introduce any unique magic numbers
    besides what's already present in TIFF 6.0.  (See attached
    specification)"""

    iana_mime = "image/prs.btif"
    ext = ".btif"
    alternative_exts = (".btf",)


class Prs_Pti(Image, BinaryFile):
    """"""

    iana_mime = "image/prs.pti"
    ext = ".pti"


class PwgRaster(WithMagicNumber, BinaryFile, Image):
    """"""

    iana_mime = "image/pwg-raster"
    ext = None
    magic_number = "52615332"


class Svg__Xml(Image, BinaryFile):
    """SVG is used by Web browsers, often in conjunction with HTML; by mobile phones and
    digital cameras, as a format for interchange of graphical assets in desk top publishing,
    for industrial process visualization, display signage, and many other applications
    which require scalable static or interactive graphical capability.

    TODO: Note that the extension ".svgz" is used as an alias for ".svg.gz" [rfc1952]
    i.e. octet streams of type image/svg+xml subsequently compressed with gzip.
    """

    iana_mime = "image/svg+xml"
    ext = ".svg"


class T38(Image, BinaryFile):
    """"""

    iana_mime = "image/t38"
    ext = ".T38"


class TiffFx(Image, BinaryFile):
    """"""

    iana_mime = "image/tiff-fx"
    ext = ".TFX"


class Webp(WithMagicNumber, BinaryFile, Image):
    """Applications that are used to display and process images, especially when smaller
    image file sizes are important.

    TODO: The first 4 bytes are 0x52, 0x49, 0x46, 0x46 ('RIFF'), followed by 4 bytes
    for the RIFF chunk size. The next 7 bytes are 0x57, 0x45, 0x42, 0x50, 0x56, 0x50, 0x38 ('WEBPVP8').
    """

    iana_mime = "image/webp"
    ext = ".webp"
    magic_number = "52494646"


class Wmf(WithMagicNumber, BinaryFile, Image):
    """Office productivity applications; clip art applications; desktop
    publishing applications; some web browsers (e.g., Internet
    Explorer).

    TODO: (little-endian DWORD 0x9AC6CDD7)"""

    iana_mime = "image/wmf"
    ext = ".wmf"
    magic_number = "d7cdc69a"
