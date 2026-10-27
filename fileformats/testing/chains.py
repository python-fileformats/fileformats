"""Formats used to test chaining of converters through intermediate formats"""

from fileformats.text import Plain


class ChainSrc(Plain):
    ext = ".chsrc"


class ChainMid(Plain):
    ext = ".chmid"


class ChainDst(Plain):
    ext = ".chdst"


class CycleA(Plain):
    ext = ".cyca"


class CycleB(Plain):
    ext = ".cycb"


class CycleC(Plain):
    ext = ".cycc"


class AmbiguousSrc(Plain):
    ext = ".ambsrc"


class AmbiguousMid1(Plain):
    ext = ".ambmid1"


class AmbiguousMid2(Plain):
    ext = ".ambmid2"


class AmbiguousDst(Plain):
    ext = ".ambdst"
