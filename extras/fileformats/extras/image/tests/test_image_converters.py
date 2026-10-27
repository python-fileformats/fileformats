import pytest
from fileformats.image import Bitmap, Gif, Jpeg, Png, Tiff
from imageio.core.fetching import get_remote_file


@pytest.fixture(scope="session")
def jpg() -> Jpeg:
    return Jpeg(get_remote_file("images/bricks.jpg"))


@pytest.fixture(scope="session")
def png() -> Png:

    return Png(get_remote_file("images/chelsea.png"))


# @pytest.mark.xfail(
#     sys.version_info.minor <= 9,
#     reason="upstream Pydra issue with type-checking 'type' objects",
# )
def test_jpg_to_gif(jpg):
    Gif.convert(jpg)


# @pytest.mark.xfail(
#     sys.version_info.minor <= 9,
#     reason="upstream Pydra issue with type-checking 'type' objects",
# )
def test_png_to_tiff(png):
    Tiff.convert(png)


# @pytest.mark.xfail(
#     sys.version_info.minor <= 9,
#     reason="upstream Pydra issue with type-checking 'type' objects",
# )
def test_png_to_bitmap(png):
    Bitmap.convert(png)
