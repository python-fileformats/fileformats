from fileformats.core.mixin import WithMagicNumber
from fileformats.generic import BinaryFile

from .core import __version__  # noqa


class Audio(BinaryFile):
    "Base class for audio file formats"


# Compressed formats
class Mpeg(Audio):
    ext = ".mp3"
    alternate_exts = (".mp1", ".mp2")
    iana_mime = "audio/mpeg"


class Mp4(WithMagicNumber, Audio):
    ext = ".mp4"
    iana_mime = "audio/mp4"
    magic_number = "6674797069736F6D"


class Aac(Audio):
    ext = ".aac"
    alternate_exts = (".adts", ".loas", ".ass")
    iana_mime = "audio/aac"


class Wav(Audio):
    ext = ".wav"
    iana_mime = "audio/wav"


class _1dInterleavedParityfec(Audio):
    """"""

    iana_mime = "audio/1d-interleaved-parityfec"
    ext = None


class _32kadpcm(Audio):
    """"""

    iana_mime = "audio/32kadpcm"
    ext = ".726"


class _3gpp(Audio):
    """The type "audio/3gpp" MAY be used for
    files containing audio but no visual
    presentation.  Files served under
    this type MUST NOT contain any
    visual material. (Note that 3GPP
    timed text is visually presented
    and is considered to be visual
    material).

    TODO: None.  However, the file-type box
    must occur first in the file, and
    MUST contain a 3GPP brand in its
    compatible brands list."""

    iana_mime = "audio/3gpp"
    ext = ".3gp"
    alternate_exts = (".3gpp",)


class _3gpp2(Audio):
    """Multi-media

    The type "audio/3gpp2" MAY be used for files containing audio but
        no visual presentation.  Files served under this type MUST NOT
        contain any visual material.  (Note that 3GPP timed text is
        visually presented and is considered visual material).

        TODO: None.  However, the file-type box must occur first in the file,
        and MUST contain a 3GPP2 brand in its compatible brands list."""

    iana_mime = "audio/3gpp2"
    ext = None


class Ac3(WithMagicNumber, Audio):
    """Multichannel audio compression of audio and audio for video."""

    iana_mime = "audio/ac3"
    ext = None
    magic_number = "0B77"


class Amr(Audio):
    """This media type is used in numerous applications needing 	transport or storage of encoded voice.  Some examples include; 	Voice over IP, streaming media, voice messaging, and voice 	recording on digital cameras."""

    iana_mime = "audio/AMR"
    ext = ".amr"
    alternate_exts = (".AMR",)


class AmrWb(Audio):
    """"""

    iana_mime = "audio/AMR-WB"
    ext = ".awb"
    alternate_exts = (".AWB",)


class AmrWb__(Audio):
    """This MIME type is not applicable for file storage.
    Instead, file storage of AMR-WB+ encoded audio is
    specified within the 3GPP-defined ISO-based multimedia
    file format defined in 3GPP TS 26.244; see reference
    [14] of RFC 4352.  This file format has the MIME types
    "audio/3GPP" or "video/3GPP" as defined by RFC 3839
    [15].

    This media type is used in numerous applications needing 	transport or storage of
    encoded voice.  Some examples include; 	Voice over IP, streaming media, voice
    messaging, and voice 	recording on digital cameras."""

    iana_mime = "audio/amr-wb+"
    ext = None


class Aptx(Audio):
    """"""

    iana_mime = "audio/aptx"
    ext = None


class Asc(Audio):
    """MPEG 4 Audio servers and terminals that support
    audio/mpeg4-generic RTP streams for mode rtp-midi."""

    iana_mime = "audio/asc"
    ext = None


class AtracAdvancedLossless(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/ATRAC-ADVANCED-LOSSLESS"
    ext = ".aal"
    alternate_exts = (".aa3", ".omg")


class AtracX(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/ATRAC-X"
    ext = ".atx"
    alternate_exts = (".aa3", ".omg")


class Atrac3(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/ATRAC3"
    ext = ".at3"
    alternate_exts = (".aa3", ".omg")


class Basic(Audio):
    """"""

    iana_mime = "audio/basic"
    ext = None


class Bv16(Audio):
    """"""

    iana_mime = "audio/BV16"
    ext = None


class Bv32(Audio):
    """"""

    iana_mime = "audio/BV32"
    ext = None


class Clearmode(Audio):
    """"""

    iana_mime = "audio/clearmode"
    ext = None


class Cn(Audio):
    """"""

    iana_mime = "audio/CN"
    ext = None


class Dat12(Audio):
    """"""

    iana_mime = "audio/DAT12"
    ext = None


class Dls(WithMagicNumber, Audio):
    """Multi-media"""

    iana_mime = "audio/dls"
    ext = ".dls"
    magic_number = "444c5320"
    magic_number_offset = 8


class DsrEs201108(Audio):
    """"""

    iana_mime = "audio/dsr-es201108"
    ext = None


class DsrEs202050(Audio):
    """"""

    iana_mime = "audio/dsr-es202050"
    ext = None


class DsrEs202211(Audio):
    """"""

    iana_mime = "audio/dsr-es202211"
    ext = None


class DsrEs202212(Audio):
    """"""

    iana_mime = "audio/dsr-es202212"
    ext = None


class Dv(Audio):
    """Audio and video streaming and
    conferencing tools."""

    iana_mime = "audio/DV"
    ext = None


class Dvi4(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/DVI4"
    ext = None


class Eac3(WithMagicNumber, Audio):
    """Multichannel audio compression of audio, and audio for video."""

    iana_mime = "audio/eac3"
    ext = None
    magic_number = "0b77"


class Encaprtp(Audio):
    """"""

    iana_mime = "audio/encaprtp"
    ext = None


class Evrc(WithMagicNumber, Audio):
    """It is expected that many VoIP applications (as well as mobile
        applications) will use this type.

    The following information applies for storage format only."""

    iana_mime = "audio/EVRC"
    ext = ".evc"
    alternate_exts = ("EVC",)
    magic_number = b"#!EVRC\n"


class EvrcQcp(WithMagicNumber, Audio):
    """no"""

    iana_mime = "audio/EVRC-QCP"
    ext = ".qcp"
    alternate_exts = (".QCP",)
    magic_number = b"RIFF"


class Evrc0(Audio):
    """It is expected that many VoIP applications (as well as mobile
    applications) will use this type."""

    iana_mime = "audio/EVRC0"
    ext = None


class Evrc1(Audio):
    """It is expected that many VoIP applications (as well as mobile
    applications) will use this type."""

    iana_mime = "audio/EVRC1"
    ext = None


class Evrcb(WithMagicNumber, Audio):
    """It is expected that many VoIP applications (as well as mobile applications) will use this type.

    The following information applies for the storage format only."""

    iana_mime = "audio/EVRCB"
    ext = ".evb"
    alternate_exts = (".EVB",)
    magic_number = b"#!EVRC-B\n"


class Evrcb0(Audio):
    """It is expected that many VoIP applications (as well as mobile applications) will use this type."""

    iana_mime = "audio/EVRCB0"
    ext = None


class Evrcb1(Audio):
    """It is expected that many VoIP applications (as well as mobile
    applications) will use this type."""

    iana_mime = "audio/EVRCB1"
    ext = None


class Evrcnw(WithMagicNumber, Audio):
    """It is expected that many VoIP applications (as well as mobile
    applications) will use this type."""

    iana_mime = "audio/EVRCNW"
    ext = ".enw"
    alternate_exts = (".ENW",)
    magic_number = b"#!EVRCNW\n"


class Evrcnw0(Audio):
    """It is expected that many VoIP applications (as well as mobile
    applications) will use this type."""

    iana_mime = "audio/EVRCNW0"
    ext = None


class Evrcnw1(Audio):
    """It is expected that many VoIP applications (as well as mobile
    applications) will use this type."""

    iana_mime = "audio/EVRCNW1"
    ext = None


class Evrcwb(WithMagicNumber, Audio):
    """It is expected that many VoIP applications (as well as mobile applications) will use this type."""

    iana_mime = "audio/EVRCWB"
    ext = ".evw"
    alternate_exts = (".EVW",)
    magic_number = b"#!EVCWB\n"


class Evrcwb0(Audio):
    """It is expected that many VoIP applications (as well as mobile applications) will use this type."""

    iana_mime = "audio/EVRCWB0"
    ext = None


class Evrcwb1(Audio):
    """It is expected that many VoIP applications (as well as mobile applications) will use this type."""

    iana_mime = "audio/EVRCWB1"
    ext = None


class Evs(Audio):
    """"""

    iana_mime = "audio/EVS"
    ext = ".3gp"
    alternate_exts = (".3gpp",)


class Flexfec(Audio):
    """Multimedia applications that want to improve resiliency against packet loss by sending redundant data in addition to the source media."""

    iana_mime = "audio/flexfec"
    ext = None


class Fwdred(Audio):
    """It is expected that real-time audio/video, text streaming, and
    conferencing tools/applications that want protection against
    losses of a large number of consecutive frames will be interested
    in using this type."""

    iana_mime = "audio/fwdred"
    ext = None


class G711_0(WithMagicNumber, Audio):
    """
    TODO: #!G7110A\\n or #!G7110M\\n (for A-law or MU-law
    encodings respectively, see Section 6)."""

    iana_mime = "audio/G711-0"
    ext = None
    magic_number = b"#!G7110A\n"


class G719(Audio):
    """Real-time audio applications
    like Voice over IP and teleconference, and multi-media streaming."""

    iana_mime = "audio/G719"
    ext = None


class G7221(Audio):
    """Audio and Video streaming and conferencing applications."""

    iana_mime = "audio/G7221"
    ext = None


class G722(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/G722"
    ext = None


class G723(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/G723"
    ext = None


class G726_16(Audio):
    """"""

    iana_mime = "audio/G726-16"
    ext = None


class G726_24(Audio):
    """"""

    iana_mime = "audio/G726-24"
    ext = None


class G726_32(Audio):
    """"""

    iana_mime = "audio/G726-32"
    ext = None


class G726_40(Audio):
    """"""

    iana_mime = "audio/G726-40"
    ext = None


class G728(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/G728"
    ext = None


class G729(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/G729"
    ext = None


class G7291(Audio):
    """"""

    iana_mime = "audio/G7291"
    ext = None


class G729d(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/G729D"
    ext = None


class G729e(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/G729E"
    ext = None


class Gsm(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/GSM"
    ext = None


class GsmEfr(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/GSM-EFR"
    ext = None


class GsmHr_08(Audio):
    """"""

    iana_mime = "audio/GSM-HR-08"
    ext = None


class Ilbc(Audio):
    """"""

    iana_mime = "audio/iLBC"
    ext = ".lbc"
    alternate_exts = (".LBC",)


class IpMrV2_5(Audio):
    """"""

    iana_mime = "audio/ip-mr_v2.5"
    ext = None


class L8(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/L8"
    ext = None


class L16(Audio):
    """The public domain "sox" and "rateconv" programs accept this 	type."""

    iana_mime = "audio/L16"
    ext = ".WAV"
    alternate_exts = (".L16",)


class L20(Audio):
    """"""

    iana_mime = "audio/L20"
    ext = None


class L24(Audio):
    """"""

    iana_mime = "audio/L24"
    ext = None


class Lpc(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/LPC"
    ext = None


class Melp(Audio):
    """"""

    iana_mime = "audio/MELP"
    ext = None


class Melp600(Audio):
    """"""

    iana_mime = "audio/MELP600"
    ext = None


class Melp1200(Audio):
    """"""

    iana_mime = "audio/MELP1200"
    ext = None


class Melp2400(Audio):
    """"""

    iana_mime = "audio/MELP2400"
    ext = None


class Mhas(Audio):
    """

    TODO: Receivers can search for the following syncword within the binary data stream: mpeghAudioStreamPacket() 0xC001A5 (24bit sequence).
    """

    iana_mime = "audio/mhas"
    ext = ".mhas"


class MobileXmf(Audio):
    """"""

    iana_mime = "audio/mobile-xmf"
    ext = ".mxmf"


class Mpa(Audio):
    """"""

    iana_mime = "audio/MPA"
    ext = None


class Mp4aLatm(Audio):
    """"""

    iana_mime = "audio/MP4A-LATM"
    ext = None


class MpaRobust(Audio):
    """Audio streaming tools (transmitting and receiving)"""

    iana_mime = "audio/mpa-robust"
    ext = None


class Mpeg4Generic(Audio):
    """"""

    iana_mime = "audio/mpeg4-generic"
    ext = None


class Ogg(WithMagicNumber, Audio):
    """"""

    iana_mime = "audio/ogg"
    ext = ".oga"
    alternate_exts = (".ogg", ".spx", ".opus")
    magic_number = b"OggS"


class Opus(Audio):
    """Any application that requires the transport of speech or audio
    data can use this media type.  Some examples are, but not limited
    to, audio and video conferencing, Voice over IP, and media
    streaming."""

    iana_mime = "audio/opus"
    ext = None


class Parityfec(Audio):
    """"""

    iana_mime = "audio/parityfec"
    ext = None


class Pcma(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/PCMA"
    ext = None


class PcmaWb(Audio):
    """Audio and video conferencing
    tools."""

    iana_mime = "audio/PCMA-WB"
    ext = None


class Pcmu(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/PCMU"
    ext = None


class PcmuWb(Audio):
    """Audio and video conferencing
    tools."""

    iana_mime = "audio/PCMU-WB"
    ext = None


class Prs_Sid(WithMagicNumber, Audio):
    """The data is a binary memory chunk from a Commodore 64 with an attached
    header. The header contains metadata such as composer, year of
    publication
    etc. The binary chunk is being interpreted as CSG 6510 microprocessor
    instruction bytecodes attached to a Commodore 64 chipset.

       TODO: first 4 bytes are 0x50534944 - "PSID" or 0x52534944 - "RSID\" """

    iana_mime = "audio/prs.sid"
    ext = ".sid"
    alternate_exts = (".psid",)
    magic_number = b"PSID"


class Qcelp(Audio):
    """"""

    iana_mime = "audio/QCELP"
    ext = None


class Raptorfec(Audio):
    """Real-time multimedia applications like video streaming, audio streaming, and video conferencing."""

    iana_mime = "audio/raptorfec"
    ext = None


class Red(Audio):
    """"""

    iana_mime = "audio/RED"
    ext = None


class RtpEncAescm128(Audio):
    """"""

    iana_mime = "audio/rtp-enc-aescm128"
    ext = None


class Rtploopback(Audio):
    """"""

    iana_mime = "audio/rtploopback"
    ext = None


class RtpMidi(Audio):
    """Audio content-creation hardware, such as MIDI controller piano
    keyboards and MIDI audio synthesizers.  Audio content-creation
    software, such as music sequencers, digital audio workstations,
    and soft synthesizers.  Computer operating systems, for network
    support of MIDI Application Programmer Interfaces.  Content
    distribution servers and terminals may use this media type for
    low bitrate music coding."""

    iana_mime = "audio/rtp-midi"
    ext = None


class Rtx(Audio):
    """"""

    iana_mime = "audio/rtx"
    ext = None


class Scip(Audio):
    """"""

    iana_mime = "audio/scip"
    ext = None


class Smv(WithMagicNumber, Audio):
    """The following information applies to storage format only."""

    iana_mime = "audio/SMV"
    ext = ".smv"
    alternate_exts = (".SMV",)
    magic_number = b"#!SMV\n"


class Smv0(Audio):
    """"""

    iana_mime = "audio/SMV0"
    ext = None


class SmvQcp(WithMagicNumber, Audio):
    """no"""

    iana_mime = "audio/SMV-QCP"
    ext = ".qcp"
    alternate_exts = (".QCP",)
    magic_number = b"RIFF"


class Sofa(WithMagicNumber, Audio):
    """

    TODO: as with HDF5"""

    iana_mime = "audio/sofa"
    ext = ".sofa"
    magic_number = "894844460d0a1a0a"


class SpMidi(Audio):
    """"""

    iana_mime = "audio/sp-midi"
    ext = ".mid"


class Speex(Audio):
    """Audio streaming and conferencing applications."""

    iana_mime = "audio/speex"
    ext = None


class T140c(Audio):
    """This type is only defined for transfer
    via RTP."""

    iana_mime = "audio/t140c"
    ext = None


class T38(Audio):
    """"""

    iana_mime = "audio/t38"
    ext = None


class TelephoneEvent(Audio):
    """"""

    iana_mime = "audio/telephone-event"
    ext = None


class Tetra_acelp(Audio):
    """"""

    iana_mime = "audio/TETRA_ACELP"
    ext = None


class Tetra_acelp_bb(Audio):
    """"""

    iana_mime = "audio/TETRA_ACELP_BB"
    ext = None


class Tone(Audio):
    """"""

    iana_mime = "audio/tone"
    ext = None


class Tsvcis(Audio):
    """"""

    iana_mime = "audio/TSVCIS"
    ext = None


class Uemclip(Audio):
    """Audio and video streaming and
    conferencing tools."""

    iana_mime = "audio/UEMCLIP"
    ext = None


class Ulpfec(Audio):
    """Multimedia applications that seek to improve resiliency to loss by sending additional data with the media stream."""

    iana_mime = "audio/ulpfec"
    ext = None


class Usac(Audio):
    """Unified Speech and Audio Coding (USAC) audio is device, platform, and vendor neutral and is supported by a wide range of encoders and decoders/players, for example for Multimedia, HLS Audio-Only Streams - IETF HTTP Live Streaming, SHOUTcast/Icecast2 Audio Streams."""

    iana_mime = "audio/usac"
    ext = ".loas"
    alternate_exts = (".xhe",)


class Vdvi(Audio):
    """Audio and video streaming and conferencing tools."""

    iana_mime = "audio/VDVI"
    ext = None


class VmrWb(Audio):
    """"""

    iana_mime = "audio/VMR-WB"
    ext = None


class Vorbis(Audio):
    """"""

    iana_mime = "audio/vorbis"
    ext = None


class VorbisConfig(Audio):
    """"""

    iana_mime = "audio/vorbis-config"
    ext = None


__all__ = [
    "Audio",
    "Mpeg",
    "Mp4",
    "Aac",
    "Wav",
    "_1dInterleavedParityfec",
    "_32kadpcm",
    "_3gpp",
    "_3gpp2",
    "Ac3",
    "Amr",
    "AmrWb",
    "AmrWb__",
    "Aptx",
    "Asc",
    "AtracAdvancedLossless",
    "AtracX",
    "Atrac3",
    "Basic",
    "Bv16",
    "Bv32",
    "Clearmode",
    "Cn",
    "Dat12",
    "Dls",
    "DsrEs201108",
    "DsrEs202050",
    "DsrEs202211",
    "DsrEs202212",
    "Dv",
    "Dvi4",
    "Eac3",
    "Encaprtp",
    "Evrc",
    "EvrcQcp",
    "Evrc0",
    "Evrc1",
    "Evrcb",
    "Evrcb0",
    "Evrcb1",
    "Evrcnw",
    "Evrcnw0",
    "Evrcnw1",
    "Evrcwb",
    "Evrcwb0",
    "Evrcwb1",
    "Evs",
    "Flexfec",
    "Fwdred",
    "G711_0",
    "G719",
    "G7221",
    "G722",
    "G723",
    "G726_16",
    "G726_24",
    "G726_32",
    "G726_40",
    "G728",
    "G729",
    "G7291",
    "G729d",
    "G729e",
    "Gsm",
    "GsmEfr",
    "GsmHr_08",
    "Ilbc",
    "IpMrV2_5",
    "L8",
    "L16",
    "L20",
    "L24",
    "Lpc",
    "Melp",
    "Melp600",
    "Melp1200",
    "Melp2400",
    "Mhas",
    "MobileXmf",
    "Mpa",
    "Mp4aLatm",
    "MpaRobust",
    "Mpeg4Generic",
    "Ogg",
    "Opus",
    "Parityfec",
    "Pcma",
    "PcmaWb",
    "Pcmu",
    "PcmuWb",
    "Prs_Sid",
    "Qcelp",
    "Raptorfec",
    "Red",
    "RtpEncAescm128",
    "Rtploopback",
    "RtpMidi",
    "Rtx",
    "Scip",
    "Smv",
    "Smv0",
    "SmvQcp",
    "Sofa",
    "SpMidi",
    "Speex",
    "T140c",
    "T38",
    "TelephoneEvent",
    "Tetra_acelp",
    "Tetra_acelp_bb",
    "Tone",
    "Tsvcis",
    "Uemclip",
    "Ulpfec",
    "Usac",
    "Vdvi",
    "VmrWb",
    "Vorbis",
    "VorbisConfig",
]
