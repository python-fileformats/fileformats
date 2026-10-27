import sys
import typing as ty
import pytest
from fileformats.generic import Directory, DirectoryOf, SetOf
from fileformats.testing import MyFormatGz, YourFormat, EncodedText
from fileformats.core.exceptions import FormatMismatchError


def test_sample_directory():
    assert isinstance(Directory.sample(), Directory)


def test_sample_directory_of():
    sample = DirectoryOf[MyFormatGz].sample()
    assert isinstance(sample, DirectoryOf[MyFormatGz])
    assert all(isinstance(c, MyFormatGz) for c in sample.contents)


def test_sample_set_of():
    sample = SetOf[MyFormatGz].sample()
    assert isinstance(sample, SetOf)
    assert all(isinstance(c, MyFormatGz) for c in sample.contents)


def test_directory_optional_contents(tmp_path):
    my_format = MyFormatGz.sample(dest_dir=tmp_path)
    sample_dir = DirectoryOf[MyFormatGz](tmp_path)
    EncodedText.sample(dest_dir=tmp_path)
    assert sample_dir.contents == [my_format]

    with pytest.raises(
        FormatMismatchError, match="Did not find the required content types"
    ):
        DirectoryOf[MyFormatGz, YourFormat](sample_dir)

    optional_dir = DirectoryOf[MyFormatGz, ty.Optional[YourFormat]](sample_dir)
    assert optional_dir.contents == [my_format]

    your_format = YourFormat.sample(dest_dir=tmp_path)
    optional_dir = DirectoryOf[MyFormatGz, ty.Optional[YourFormat]](sample_dir)
    assert optional_dir.contents == [my_format, your_format]

    required_dir = DirectoryOf[MyFormatGz, YourFormat](sample_dir)
    assert required_dir.contents == [my_format, your_format]


def test_set_optional_contents():
    my_format = MyFormatGz.sample()
    your_format = YourFormat.sample()

    sample_set = SetOf[MyFormatGz, YourFormat](my_format, your_format)
    assert sample_set.contents == [my_format, your_format]
    assert set(sample_set.required_paths()) == {my_format.fspath, your_format.fspath}

    sample_set = SetOf[MyFormatGz](my_format, your_format)
    assert list(sample_set.required_paths()) == [my_format.fspath]

    with pytest.raises(
        FormatMismatchError, match="Did not find the required content types"
    ):
        SetOf[MyFormatGz, YourFormat](my_format)

    sample_set = SetOf[MyFormatGz, ty.Optional[YourFormat]](my_format)
    assert sample_set.contents == [my_format]
    assert list(sample_set.required_paths()) == [my_format.fspath]

    sample_set = SetOf[MyFormatGz, ty.Optional[YourFormat]](my_format, your_format)
    assert sample_set.contents == [my_format, your_format]
    assert set(sample_set.required_paths()) == {my_format.fspath, your_format.fspath}

    sample_set = SetOf[ty.Optional[MyFormatGz]](my_format)
    assert sample_set.contents == [my_format]
    assert list(sample_set.required_paths()) == [my_format.fspath]


@pytest.mark.skipif(sys.version_info < (3, 10), reason="requires python3.10 or higher")
def test_directory_optional_contents_pep604(tmp_path):
    my_format = MyFormatGz.sample(dest_dir=tmp_path)
    sample_dir = DirectoryOf[MyFormatGz](tmp_path)
    EncodedText.sample(dest_dir=tmp_path)
    assert sample_dir.contents == [my_format]

    optional_dir = DirectoryOf[MyFormatGz, ty.Optional[YourFormat]](sample_dir)
    assert optional_dir.contents == [my_format]

    your_format = YourFormat.sample(dest_dir=tmp_path)
    optional_dir = DirectoryOf[MyFormatGz, ty.Optional[YourFormat]](sample_dir)
    assert optional_dir.contents == [my_format, your_format]


@pytest.mark.skipif(sys.version_info < (3, 10), reason="requires python3.10 or higher")
def test_set_optional_contents_pep604():
    my_format = MyFormatGz.sample()
    your_format = YourFormat.sample()

    sample_set = SetOf[MyFormatGz, ty.Optional[YourFormat]](my_format)
    assert sample_set.contents == [my_format]
    assert list(sample_set.required_paths()) == [my_format.fspath]

    sample_set = SetOf[MyFormatGz, ty.Optional[YourFormat]](my_format, your_format)
    assert sample_set.contents == [my_format, your_format]
    assert set(sample_set.required_paths()) == {my_format.fspath, your_format.fspath}

    sample_set = SetOf[ty.Optional[MyFormatGz]](my_format)
    assert sample_set.contents == [my_format]
    assert list(sample_set.required_paths()) == [my_format.fspath]
