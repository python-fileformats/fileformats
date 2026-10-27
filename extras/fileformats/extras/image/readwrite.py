import typing as ty


from fileformats.extras.core import check_optional_dependency
from fileformats.core import FileSet, extra_implementation
from fileformats.image.raster import RasterImage

if ty.TYPE_CHECKING:
    import numpy

try:
    import imageio  # noqa: F401
except ImportError:
    imageio = None  # type: ignore


@extra_implementation(FileSet.load)
def read_raster_data(image: RasterImage, **kwargs: ty.Any) -> "numpy.ndarray":
    check_optional_dependency(imageio)

    return imageio.imread(image.fspath)  # type: ignore


@extra_implementation(FileSet.save)
def write_raster_data(
    image: RasterImage, data: "numpy.ndarray", **kwargs: ty.Any
) -> None:
    check_optional_dependency(imageio)

    imageio.imwrite(image.fspath, data, **kwargs)
