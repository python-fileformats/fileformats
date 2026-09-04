from fileformats.core.mixin import WithMagicNumber
from fileformats.generic.file import BinaryFile


class Sqlite3Db(WithMagicNumber, BinaryFile):
    """SQLite3 database files."""

    ext = ".sqlite3"
    alternate_exts = (".sqlite", ".db", ".db3")
    # First 16 bytes: "SQLite format 3\0"
    magic_number = b"SQLite format 3\0"
    iana_mime = "application/vnd.sqlite3"
