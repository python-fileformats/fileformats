import importlib
import pkgutil

import pytest

import fileformats
from fileformats.core import from_mime
from fileformats.text import Html, Markdown

NAMESPACES = sorted(
    m.name for m in pkgutil.iter_modules(fileformats.__path__) if m.ispkg
)


@pytest.mark.parametrize("namespace", NAMESPACES)
def test_all_names_are_defined(namespace: str) -> None:
    """Names listed in a namespace's __all__ can actually be imported from it"""
    module = importlib.import_module(f"fileformats.{namespace}")
    missing = [n for n in getattr(module, "__all__", []) if not hasattr(module, n)]
    assert not missing


@pytest.mark.parametrize(
    "mime,klass", [("text/html", Html), ("text/markdown", Markdown)]
)
def test_text_formats_from_mime(mime: str, klass: type) -> None:
    assert from_mime(mime) is klass
