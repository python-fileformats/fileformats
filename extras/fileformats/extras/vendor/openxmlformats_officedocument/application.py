import typing as ty

try:
    import docx.document
except ImportError:
    docx = None  # type: ignore[assignment]

from fileformats.core import FileSet, extra_implementation
from fileformats.extras.core import check_optional_dependency
from fileformats.vendor.openxmlformats_officedocument.application import (
    Wordprocessingml_Document as MswordX,
)


@extra_implementation(FileSet.load)
def load_docx(doc: MswordX, **kwargs: ty.Any) -> "docx.document.Document":
    check_optional_dependency(docx)
    return docx.Document(str(doc))  # type: ignore[no-any-return]


@extra_implementation(FileSet.save)
def save_docx(doc: MswordX, data: "docx.document.Document", **kwargs: ty.Any) -> None:
    check_optional_dependency(docx)
    if not isinstance(data, docx.document.Document):
        raise TypeError(f"Expected a 'docx.document.Document' object, got {type(data)}")
    data.save(str(doc))
