from fileformats.testing import MyFormat
import pytest


def test_check_optional_dependency_fail():

    with pytest.raises(
        ImportError, match="The optional dependencies are not installed for 'testing'"
    ):
        MyFormat.sample().dummy_extra()
