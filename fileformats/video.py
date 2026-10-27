from fileformats.generic import BinaryFile

from .core import __version__  # noqa
from .core.mixin import WithMagicNumber


class Video(BinaryFile):
    "Base class for audio file formats"

    binary = True
    # iana_mime = None
    pass


class Mp4(Video):
    """"""

    iana_mime = "video/mp4"
    ext = ".mp4"
    alternate_exts = (".mpg4",)


class Webm(Video):
    ext = ".webm"
    iana_mime = "video/webm"


class Quicktime(Video):
    ext = ".mov"
    alternate_exts = (".qt",)
    iana_mime = "video/quicktime"


class Ogg(WithMagicNumber, Video):
    """"""

    iana_mime = "video/ogg"
    ext = ".ogv"
    magic_number = b"OggS"


class _1dInterleavedParityfec(Video):
    """"""

    iana_mime = "video/1d-interleaved-parityfec"
    ext = None


class _3gpp(Video):
    """

    TODO: None.  However, the file-type box
    must occur first in the file, and
    MUST contain a 3GPP brand in its
    compatible brands list."""

    iana_mime = "video/3gpp"
    ext = ".3gp"
    alternate_exts = (".3gpp",)


class _3gpp2(Video):
    """Multi-media

    TODO: the file-type box must occur first in the file
    and MUST contain a 3GPP2 brand in its compatible brands list."""

    iana_mime = "video/3gpp2"
    ext = None


class _3gppTt(Video):
    """"""

    iana_mime = "video/3gpp-tt"
    ext = None


class Av1(Video):
    """"""

    iana_mime = "video/AV1"
    ext = None


class Bmpeg(Video):
    """"""

    iana_mime = "video/BMPEG"
    ext = None


class Bt656(Video):
    """"""

    iana_mime = "video/BT656"
    ext = None


class Celb(Video):
    """"""

    iana_mime = "video/CelB"
    ext = None


class Dv(Video):
    """Audio and video streaming and
    conferencing tools."""

    iana_mime = "video/DV"
    ext = None


class Encaprtp(Video):
    """"""

    iana_mime = "video/encaprtp"
    ext = None


class Example(Video):
    """"""

    iana_mime = "video/example"
    ext = None


class Ffv1(Video):
    """Any application that requires the transport of  lossless video can use this media type. Some examples are, but not limited to, screen  recording, scientific imaging, and digital video preservation."""

    iana_mime = "video/FFV1"
    ext = None


class Flexfec(Video):
    """Multimedia applications that want to improve resiliency against packet loss by sending redundant data in addition to the source media."""

    iana_mime = "video/flexfec"
    ext = None


class H261(Video):
    """Audio and video streaming and conferencing applications."""

    iana_mime = "video/H261"
    ext = None


class H263(Video):
    """"""

    iana_mime = "video/H263"
    ext = None


class H263_1998(Video):
    """"""

    iana_mime = "video/H263-1998"
    ext = None


class H263_2000(Video):
    """"""

    iana_mime = "video/H263-2000"
    ext = None


class H264(Video):
    """"""

    iana_mime = "video/H264"
    ext = None


class H264Rcdo(Video):
    """"""

    iana_mime = "video/H264-RCDO"
    ext = None


class H264Svc(Video):
    """"""

    iana_mime = "video/H264-SVC"
    ext = None


class H265(Video):
    """"""

    iana_mime = "video/H265"
    ext = None


class H266(Video):
    """Any application that relies
    on VVC-based video services over RTP"""

    iana_mime = "video/H266"
    ext = None


class Iso_Segment(Video):
    """"""

    iana_mime = "video/iso.segment"
    ext = ".m4s"


class Jpeg(Video):
    """"""

    iana_mime = "video/JPEG"
    ext = None


class Jpeg2000(Video):
    """video streaming and communication"""

    iana_mime = "video/jpeg2000"
    ext = None


class Jxsv(Video):
    """Any application that transmits video over RTP (like SMPTE ST
    2110)."""

    iana_mime = "video/jxsv"
    ext = None


class Mj2(WithMagicNumber, Video):
    """"""

    iana_mime = "video/mj2"
    ext = ".mj2"
    alternate_exts = (".mjp2",)
    magic_number = "0000000C6A5020200D0A870A"


class Mp1s(Video):
    """"""

    iana_mime = "video/MP1S"
    ext = None


class Mp2p(Video):
    """"""

    iana_mime = "video/MP2P"
    ext = None


class Mp2t(Video):
    """"""

    iana_mime = "video/MP2T"
    ext = None


class Mp4vEs(Video):
    """"""

    iana_mime = "video/MP4V-ES"
    ext = None


class Mpv(Video):
    """"""

    iana_mime = "video/MPV"
    ext = None


class Mpeg4Generic(Video):
    """"""

    iana_mime = "video/mpeg4-generic"
    ext = None


class Nv(Video):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "video/nv"
    ext = None


class Parityfec(Video):
    """"""

    iana_mime = "video/parityfec"
    ext = None


class Pointer(Video):
    """"""

    iana_mime = "video/pointer"
    ext = None


class Raptorfec(Video):
    """Real-time multimedia applications like video streaming, audio streaming, and video conferencing."""

    iana_mime = "video/raptorfec"
    ext = None


class Raw(Video):
    """"""

    iana_mime = "video/raw"
    ext = None


class RtpEncAescm128(Video):
    """"""

    iana_mime = "video/rtp-enc-aescm128"
    ext = None


class Rtploopback(Video):
    """"""

    iana_mime = "video/rtploopback"
    ext = None


class Rtx(Video):
    """"""

    iana_mime = "video/rtx"
    ext = None


class Scip(Video):
    """"""

    iana_mime = "video/scip"
    ext = None


class Smpte291(Video):
    """Devices that stream real-time professional video, especially those that interoperate with legacy serial digital interfaces (SDI)."""

    iana_mime = "video/smpte291"
    ext = None


class Smpte292m(Video):
    """"""

    iana_mime = "video/SMPTE292M"
    ext = None


class Ulpfec(Video):
    """Multimedia applications that seek to improve resiliency to loss by sending additional data with the media stream."""

    iana_mime = "video/ulpfec"
    ext = None


class Vc1(Video):
    """Multimedia streaming and conferencing tools."""

    iana_mime = "video/vc1"
    ext = None


class Vc2(Video):
    """Video Communication."""

    iana_mime = "video/vc2"
    ext = None


class Vp8(Video):
    """"""

    iana_mime = "video/VP8"
    ext = None


class Vp9(Video):
    """"""

    iana_mime = "video/VP9"
    ext = None


__all__ = [
    "Video",
    "Mp4",
    "Webm",
    "Quicktime",
    "Ogg",
    "_1dInterleavedParityfec",
    "_3gpp",
    "_3gpp2",
    "_3gppTt",
    "Av1",
    "Bmpeg",
    "Bt656",
    "Celb",
    "Dv",
    "Encaprtp",
    "Example",
    "Ffv1",
    "Flexfec",
    "H261",
    "H263",
    "H263_1998",
    "H263_2000",
    "H264",
    "H264Rcdo",
    "H264Svc",
    "H265",
    "H266",
    "Iso_Segment",
    "Jpeg",
    "Jpeg2000",
    "Jxsv",
    "Mj2",
    "Mp1s",
    "Mp2p",
    "Mp2t",
    "Mp4vEs",
    "Mpv",
    "Mpeg4Generic",
    "Nv",
    "Parityfec",
    "Pointer",
    "Raptorfec",
    "Raw",
    "RtpEncAescm128",
    "Rtploopback",
    "Rtx",
    "Scip",
    "Smpte291",
    "Smpte292m",
    "Ulpfec",
    "Vc1",
    "Vc2",
    "Vp8",
    "Vp9",
]
