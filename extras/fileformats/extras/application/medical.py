import sys
import typing as ty

from pathlib import Path

from fileformats.application import Dicom
from fileformats.core import FileSet, SampleFileGenerator, extra_implementation
from fileformats.core.fileset import indirect_safe
from fileformats.extras.core import check_optional_dependency

try:
    import pydicom.tag
except ImportError:
    pydicom = None  # type: ignore[assignment]
try:
    import medimages4tests.dummy.dicom.mri.t1w.siemens.skyra.syngo_d13c
except ImportError:
    medimages4tests = None  # type: ignore[assignment]

if sys.version_info <= (3, 11):
    from typing_extensions import TypeAlias
else:
    from typing import TypeAlias

TagListType: TypeAlias = ty.Union[
    ty.List[int],
    ty.List[str],
    ty.List[ty.Tuple[int, int]],
    ty.List["pydicom.tag.BaseTag"],
]


@extra_implementation(FileSet.read_metadata)
@indirect_safe
def dicom_read_metadata(
    dicom: Dicom,
    metadata_keys: ty.Optional[TagListType] = None,
    **kwargs: ty.Any,
) -> ty.Mapping[str, ty.Any]:
    check_optional_dependency(pydicom)
    # read from a stream rather than the path so this also works inside archives
    with dicom.open("rb") as f:
        dcm = pydicom.dcmread(f, specific_tags=metadata_keys, stop_before_pixels=True)
    return Dicom.pydicom_to_dict(dcm)


@extra_implementation(FileSet.generate_sample_data)
def dicom_generate_sample_data(
    dicom: Dicom,
    generator: SampleFileGenerator,
) -> ty.List[Path]:
    check_optional_dependency(medimages4tests)
    return next(
        medimages4tests.dummy.dicom.mri.t1w.siemens.skyra.syngo_d13c.get_image(
            out_dir=generator.dest_dir
        ).iterdir()
    )


@extra_implementation(FileSet.load)
def dicom_load(
    dicom: Dicom,
    specific_tags: ty.Optional[TagListType] = None,
    **kwargs: ty.Any,
) -> "pydicom.FileDataset":
    check_optional_dependency(pydicom)
    return pydicom.dcmread(dicom.fspath, specific_tags=specific_tags)


@extra_implementation(FileSet.save)
def dicom_save(
    dicom: Dicom,
    data: "pydicom.FileDataset",
    write_like_original: bool = False,
    **kwargs: ty.Any,
) -> None:
    check_optional_dependency(pydicom)
    pydicom.dcmwrite(dicom.fspath, data, write_like_original=write_like_original)
    pydicom.dcmwrite(dicom.fspath, data, write_like_original=write_like_original)
