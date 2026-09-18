import os.path
import tarfile
import tempfile
import typing as ty
import zipfile
from pathlib import Path

from pydra.compose import python

from fileformats.application import Tar, TarGzip, Zip
from fileformats.core import FileSet, converter
from fileformats.core.typing import PathType
from fileformats.core.utils import set_cwd
from fileformats.generic import FsObject

TAR_COMPRESSION_TYPES = ["", "gz", "bz2", "xz"]

TAR_COMPRESSION_ANNOT = (
    str,
    {
        "help": (
            "The type of compression applied to tar file, "
            "', '".join(TAR_COMPRESSION_TYPES)
        ),
        "allowed_values": list(TAR_COMPRESSION_TYPES),
    },
)

ZIP_COMPRESSION_TYPES = {
    "ZIP_STORED": zipfile.ZIP_STORED,
    "ZIP_DEFLATED": zipfile.ZIP_DEFLATED,
    "ZIP_BZIP2": zipfile.ZIP_BZIP2,
    "ZIP_LZMA": zipfile.ZIP_LZMA,
}

ZIP_COMPRESSION_ANNOT = (
    int,
    {
        "help_string": (
            "The type of compression applied to zip file, "
            "', '".join(ZIP_COMPRESSION_TYPES.keys()) + ", "
            "see https://docs.python.org/3/library/zipfile.html#zipfile.ZIP_DEFLATED "
            "for all valid compression types"
        ),
        "allowed_values": ZIP_COMPRESSION_TYPES,

    },
)

Compressed = FileSet.type_var("Compressed")

FilterMethodType = ty.Any
# FIXME: This is a placeholder for the actual type, when pydra supports it properly
# FilterMethodType = ty.Optional[
#     ty.Callable[[tarfile.TarInfo], ty.Optional[tarfile.TarInfo]]
# ]


@converter(source_format=FsObject, target_format=Tar)  # type: ignore[untyped-decorator]
@converter(source_format=FsObject, target_format=TarGzip, compression="gz")  # type: ignore[untyped-decorator]
@converter(source_format=Compressed, target_format=Tar[Compressed])  # type: ignore[untyped-decorator,misc]
@converter(
    source_format=Compressed, target_format=TarGzip[Compressed], compression="gz"  # type: ignore[untyped-decorator,misc]
)
@python.define(outputs={"out_file": Path})  # type: ignore[untyped-decorator]
def create_tar(
    in_file: FsObject,
    out_file: ty.Optional[Path] = None,
    base_dir: ty.Optional[Path] = None,
    filter: FilterMethodType = None,
    compression: ty.Optional[str] = None,
    format: int = tarfile.DEFAULT_FORMAT,
    ignore_zeros: bool = False,
    encoding: str = tarfile.ENCODING,
) -> Path:

    if len(in_file.fspaths) > 1:
        raise NotImplementedError(
            "Can only archive file-sets with single paths currently"
        )

    ext: str
    if not compression:
        compression = ""
        ext = ".tar"
    else:
        ext = ".tar." + compression

    if not out_file:
        out_file = Path(Path(in_file).name + ext)

    if base_dir is None:
        base_dir = Path(in_file).parent

    out_file = out_file.absolute()

    with (
        tarfile.open(  # type: ignore[call-overload]
            name=out_file,
            mode=f"w:{compression}",
            format=format,
            ignore_zeros=ignore_zeros,
            encoding=encoding,
        ) as tfile,
        set_cwd(base_dir),
    ):
        for fspath in in_file.fspaths:
            tfile.add(relative_path(fspath, base_dir), filter=filter)

    return Path(out_file)


@converter(source_format=Tar, target_format=FsObject)  # type: ignore[untyped-decorator]
@converter(source_format=TarGzip, target_format=FsObject)  # type: ignore[untyped-decorator]
@converter(source_format=Tar[Compressed], target_format=Compressed)  # type: ignore[untyped-decorator,misc]
@converter(source_format=TarGzip[Compressed], target_format=Compressed)  # type: ignore[untyped-decorator,misc]
@python.define(outputs={"out_file": Path})  # type: ignore[untyped-decorator]
def extract_tar(
    in_file: FsObject,
    extract_dir: ty.Optional[Path] = None,
    bufsize: int = 10240,
    compression_type: str = "*",
) -> Path:

    if extract_dir is None:
        extract_dir = Path(tempfile.mkdtemp())
    else:
        extract_dir = extract_dir.absolute()
        os.makedirs(extract_dir, exist_ok=True)
    extract_dir = Path(extract_dir)

    if not compression_type:
        compression_type = ""

    with tarfile.open(name=in_file, mode=f"r:{compression_type}") as tfile:  # type: ignore[call-overload]
        tfile.extractall(path=extract_dir)

    extracted = [extract_dir / f for f in os.listdir(extract_dir)]
    if len(extracted) > 1:
        raise NotImplementedError(
            "Can't handle zip files with more than one path currently"
        )
    return extracted[0]


@converter(source_format=FsObject, target_format=Zip)  # type: ignore[untyped-decorator]
@converter(source_format=Compressed, target_format=Zip[Compressed])  # type: ignore[untyped-decorator,misc]
@python.define(outputs={"out_file": Zip})  # type: ignore[untyped-decorator]
def create_zip(
    in_file: FsObject,
    out_file: ty.Optional[Path] = None,
    base_dir: ty.Optional[Path] = None,
    compression: ty.Union[int, str] = zipfile.ZIP_DEFLATED,
    allowZip64: bool = True,
    compresslevel: ty.Optional[ty.Union[int, str]] = None,
    strict_timestamps: bool = True,
) -> Zip:

    compression = parse_zip_compression(compression)
    if isinstance(compresslevel, str):
        compresslevel = int(compresslevel)

    if len(in_file.fspaths) > 1:
        raise NotImplementedError(
            "Can only archive file-sets with single paths currently"
        )

    if out_file is None:  # type: ignore[comparison-overlap]
        out_file = Path(Path(in_file).name + ".zip")

    if base_dir is None:  # type: ignore[comparison-overlap]
        base_dir = Path(in_file).parent

    out_file = out_file.absolute()

    with (
        zipfile.ZipFile(
            out_file,
            mode="w",
            compression=compression,
            allowZip64=allowZip64,
            compresslevel=compresslevel,
            strict_timestamps=strict_timestamps,
        ) as zfile,
        set_cwd(base_dir),
    ):
        for fspath in in_file.fspaths:
            fspath = Path(fspath)
            if fspath.is_dir():
                for dpath, _, files in os.walk(fspath):
                    zfile.write(relative_path(dpath, base_dir))
                    for fname in files:
                        fpath = os.path.join(dpath, fname)
                        zfile.write(relative_path(fpath, base_dir))
            else:
                zfile.write(relative_path(fspath, base_dir))
    return Zip(out_file)


def parse_zip_compression(compression: ty.Union[int, str]) -> int:
    """Resolve a zipfile compression value from either an int constant
    (e.g. zipfile.ZIP_STORED) or its name as a string (e.g. "ZIP_STORED")."""
    if isinstance(compression, str):
        try:
            return ZIP_COMPRESSION_TYPES[compression.upper()]
        except KeyError:
            raise ValueError(
                f"Unrecognised zip compression type {compression!r}, "
                f"must be one of {list(ZIP_COMPRESSION_TYPES)}"
            ) from None
    return compression


@converter(source_format=Zip, target_format=FsObject)  # type: ignore[untyped-decorator]
@converter(source_format=Zip[Compressed], target_format=Compressed)  # type: ignore[untyped-decorator,misc]
@python.define(outputs={"out_file": Path})  # type: ignore[untyped-decorator]
def extract_zip(in_file: Zip, extract_dir: ty.Optional[Path] = None) -> Path:

    if extract_dir is None:
        extract_dir = Path(tempfile.mkdtemp())
    else:
        extract_dir = extract_dir.absolute()
        os.makedirs(extract_dir, exist_ok=True)
    extract_dir = Path(extract_dir)

    with zipfile.ZipFile(in_file) as zfile:
        zfile.extractall(path=extract_dir)

    extracted = [extract_dir / f for f in os.listdir(extract_dir)]
    if len(extracted) > 1:
        raise NotImplementedError(
            "Can't handle zip files with more than one path currently"
        )
    return extracted[0]


def relative_path(path: PathType, base_dir: PathType) -> str:
    path = os.path.abspath(path)
    relpath = os.path.relpath(path, base_dir)
    if ".." in relpath:
        raise RuntimeError(
            f"Cannot add {path} to archive as it is not a "
            f"subdirectory of {base_dir}"
        )
    return relpath
