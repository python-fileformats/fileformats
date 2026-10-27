import os
from pathlib import Path
import time
from fileformats.core.decorators import (
    mtime_cached_property,
    enough_time_has_elapsed_given_mtime_resolution,
)
from fileformats.generic import UnicodeFile


class MtimeTestFile(UnicodeFile):

    flag: int

    @mtime_cached_property
    def cached_prop(self):
        return self.flag


def test_mtime_cached_property(tmp_path: Path):
    fspath = tmp_path / "file_1.txt"
    fspath.write_text("hello")

    file = MtimeTestFile(fspath)
    time.sleep(
        2
    )  # ensure enough time has elapsed since file creation/modification for mtime to increment

    file.flag = 0
    assert file.cached_prop == 0
    file.flag = 1
    assert file.cached_prop == 0
    fspath.write_text("world")
    assert file.cached_prop == 1


def test_enough_time_has_elapsed_given_mtime_resolution():
    assert enough_time_has_elapsed_given_mtime_resolution(
        [("", 110), ("", 220), ("", 300)], int(3e9)  # need to make it high for windows
    )


def test_not_enough_time_has_elapsed_given_mtime_resolution():
    assert not enough_time_has_elapsed_given_mtime_resolution(
        [("", 110), ("", 220), ("", 300)], 301
    )


class MtimeBaseFile(UnicodeFile):

    @mtime_cached_property
    def order(self) -> str:
        return "base"


class MtimeSubFile(MtimeBaseFile):

    @mtime_cached_property
    def order(self) -> str:
        return "sub:" + MtimeBaseFile.order.__get__(self)


def test_mtime_cached_property_override_has_its_own_cache(tmp_path: Path):
    """An override and the base property it calls cache separately. Filling the
    base cache first, as a reader of the base implementation does, must not make
    the override return the base value"""
    fspath = tmp_path / "file.txt"
    fspath.write_text("hello")
    past = time.time() - 10  # old enough for the cache to be used
    os.utime(fspath, (past, past))

    file = MtimeSubFile(fspath)
    assert MtimeBaseFile.order.__get__(file) == "base"
    assert file.order == "sub:base"
    assert MtimeBaseFile.order.__get__(file) == "base"
