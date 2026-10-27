import pytest

from fileformats.application import Bzip, Gzip, Tar, TarGzip, Zip
from fileformats.core.identification import to_mime


def test_circular_import_between_text_and_application():
    from fileformats.text import Plain  # noqa


@pytest.mark.parametrize(
    "cls, expected",
    [
        (Zip, "application/zip"),
        (Bzip, "application/bzip"),
        (Gzip, "application/gzip"),
        (Tar, "application/x-tar"),
        (TarGzip, "application/x-tar+gzip"),
    ],
)
def test_iana_mime_type(cls, expected):
    assert to_mime(cls) == expected
