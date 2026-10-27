import sys
import typing as ty

import pytest

from fileformats.application import Cdfx__Xml, Zip
from fileformats.core import DataType
from fileformats.core.identification import from_mime, to_mime
from fileformats.generic import DirectoryOf, FileSet
from fileformats.testing import A, B, Classified, MyFormat, U, V, X
from fileformats.vendor.openxmlformats_officedocument.application import (
    Wordprocessingml_Document,
)
from fileformats.vendor.testing.testing import Psi, Theta, VendorClassified, Zeta


def test_mime_roundtrip() -> None:
    for klass in FileSet.all_formats:
        mimetype = klass.mime_type
        assert isinstance(mimetype, str)
        reloaded = from_mime(mimetype)
        assert reloaded is klass


def test_mimelike_roundtrip() -> None:
    for klass in FileSet.all_formats:
        mimetype = klass.mime_like
        assert isinstance(mimetype, str)
        reloaded = from_mime(mimetype)
        assert reloaded is klass


UNION_TYPE = U | V if sys.version_info >= (3, 10) else ty.Union[U, V]


@pytest.mark.xfail(
    reason="Classifier mime-types need to be refactored to match desired new format"
)
@pytest.mark.parametrize(
    ["klass", "expected_mime"],
    [
        [Psi, "testing/vnd.testing.psi"],
        [
            VendorClassified[Zeta, Theta],
            "testing/[vnd.testing.theta..vnd.testing.zeta]+vnd.testing.vendor-classified",
        ],
        [
            Classified[Zeta, Theta],
            "testing/[vnd.testing.theta..vnd.testing.zeta]+classified",
        ],
        [VendorClassified[U, V], "testing/[u..v]+vnd.testing.vendor-classified"],
        [Zip[Classified[U]], "testing/u+classified+zip"],
        [Zip[Classified[U, X]], "testing/[u..v]+classified+zip"],
        [Classified[U, Zip[MyFormat]], "testing/[u..my-format+zip]+classified"],
        [
            Classified[Theta, MyFormat[A, B]],
            "testing/[vnd.testing.theta..[a..b]+my-format]+classified",
        ],
        [
            Wordprocessingml_Document,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        [
            DirectoryOf[Wordprocessingml_Document],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document+directory-of",
        ],
        [Cdfx__Xml, "application/vnd.ms-cdfx+xml"],
        [UNION_TYPE, "testing/u,testing/v"],
    ],
)
def test_compound_mime_roundtrip(klass: ty.Type[DataType], expected_mime: str) -> None:
    assert to_mime(klass, official=False) == expected_mime
    assert from_mime(expected_mime) is klass


def test_vendor_to_mime_roundtrip() -> None:
    assert Psi.mime_like == "testing/vnd.testing.psi"
    assert from_mime("testing/vnd.testing.psi") is Psi


@pytest.mark.xfail(
    reason="Classifier mime-types need to be refactored to match desired new format"
)
def test_vendor_to_mime_classified_rountrip() -> None:
    assert (
        VendorClassified[Zeta, Theta].mime_like
        == "testing/[vnd.testing.theta..vnd.testing.zeta]+vnd.testing.vendor-classified"
    )
    assert (
        from_mime(
            "testing/[vnd.testing.theta..vnd.testing.zeta]+vnd.testing.vendor-classified"
        )
        is VendorClassified[Zeta, Theta]
    )


@pytest.mark.xfail(
    reason="Classifier mime-types need to be refactored to match desired new format"
)
def test_vendor_to_mime_parent_classified_rountrip() -> None:
    assert (
        Classified[Zeta, Theta].mime_like
        == "testing/[vnd.testing.theta..vnd.testing.zeta]+classified"
    )
    assert (
        from_mime("testing/[vnd.testing.theta..vnd.testing.zeta]+classified")
        is Classified[Zeta, Theta]
    )


@pytest.mark.xfail(
    reason="Classifier mime-types need to be refactored to match desired new format"
)
def test_vendor_to_mime_parent_classifiers_rountrip() -> None:
    assert (
        VendorClassified[U, V].mime_like
        == "testing/[u..v]+vnd.testing.vendor-classified"
    )
    assert (
        from_mime("testing/[u..v]+vnd.testing.vendor-classified")
        is VendorClassified[U, V]
    )


@pytest.mark.xfail(
    reason="Classifier mime-types need to be refactored to match desired new format"
)
def test_double_classified_roundtrip1() -> None:
    assert Zip[Classified[U]].mime_like == "testing/u+classified+zip"
    assert from_mime("testing/[[u..v]+classified]+zip") is Zip[Classified[U]]


@pytest.mark.xfail(
    reason="Classifier mime-types need to be refactored to match desired new format"
)
def test_double_classified_roundtrip2() -> None:
    assert Zip[Classified[U, V]].mime_like == "testing/[u..v]+classified+zip"
    assert from_mime("testing/[[u..v]+classified]+zip") is Zip[Classified[U, V]]


def test_vendor_roundtrip() -> None:

    mime = Wordprocessingml_Document.mime_like
    assert Wordprocessingml_Document is from_mime(mime)


def test_vendor_in_container_roundtrip() -> None:

    mime = DirectoryOf[Wordprocessingml_Document].mime_like
    assert DirectoryOf[Wordprocessingml_Document] is from_mime(mime)


def test_native_container_roundtrip() -> None:

    mime = Cdfx__Xml.mime_like
    assert Cdfx__Xml is from_mime(mime)


def test_vendor_only() -> None:
    Sqlite = from_mime("application/vnd.sqlite3")
    assert Sqlite.mime_type == "application/vnd.sqlite3"


def test_mime_format_name_underscores():
    from fileformats.core.exceptions import FormatDefinitionError
    from fileformats.core.identification import (
        from_mime_format_name,
        to_mime_format_name,
    )

    assert to_mime_format_name("Svg__Xml") == "svg+xml"
    assert to_mime_format_name("AmrWb__") == "amr-wb+"
    assert to_mime_format_name("Wordprocessingml_Document") == (
        "wordprocessingml.document"
    )
    assert to_mime_format_name("_3gpdashQoeReport__Xml") == "3gpdash-qoe-report+xml"
    assert from_mime_format_name("svg+xml") == "Svg__Xml"
    assert from_mime_format_name("amr-wb+") == "AmrWb__"
    with pytest.raises(FormatDefinitionError, match="triple underscore"):
        to_mime_format_name("Svg___Xml")


def test_formats_by_mime_format_name_skips_bad_names(caplog):
    from fileformats.core.identification import formats_by_mime_format_name

    class Good__Xml:
        pass

    class Bad___Xml:
        pass

    with caplog.at_level("WARNING", logger="fileformats"):
        pairs = list(formats_by_mime_format_name([Good__Xml, Bad___Xml]))
    assert pairs == [("good+xml", Good__Xml)]
    assert "Bad___Xml" in caplog.text
