from fileformats.core.mixin import WithMagicNumber
from fileformats.generic import BinaryFile

from .base import Text


class CacheManifest(WithMagicNumber, Text, BinaryFile):
    """"""

    iana_mime = "text/cache-manifest"
    ext = ".appcache"
    alternate_exts = ('"manifest"',)
    magic_number = b"CACHE MANIFEST"
