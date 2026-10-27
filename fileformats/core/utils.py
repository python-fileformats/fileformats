import importlib
import inspect
import itertools
import logging
import os
import pkgutil
import sys
import types
import typing as ty
import urllib.error
import urllib.request
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import fileformats.core
import fileformats.vendor
from fileformats.core.exceptions import FormatDefinitionError

from .typing import FspathsInputType

logger = logging.getLogger("fileformats")


if sys.version_info >= (3, 10):
    UNION_TYPES = (ty.Union, types.UnionType)
else:
    UNION_TYPES = (ty.Union,)


_excluded_subpackages = set(
    [
        "core",
        "testing",
        "vendor.testing",
        "serialization",
        "archive",
        "document",
        "conftest",
    ]
)

T = ty.TypeVar("T")


def include_testing_package(flag: bool = True) -> None:
    """Include testing package in list of sub-packages. Typically set in conftest.py
    or similar when setting up unittesting. Must be set globally before any methods are
    called within the package as member classes are cached.

    Parameters
    ----------
    flag : bool
        whether to include the testing package or not
    """
    if flag:
        _excluded_subpackages.remove("testing")
    else:
        _excluded_subpackages.add("testing")


def subpackages(
    exclude: ty.Iterable[str] = _excluded_subpackages,
) -> ty.Generator[ModuleType, None, None]:
    """Iterates over all subpackages within the fileformats namespace

    Parameters
    ----------
    exclude : ty.Sequence[str], optional
        whether to include the testing subpackage, by default ["core", "testing"]

    Yields
    ------
    module
        all modules within the package
    """
    for mod_info in itertools.chain(
        pkgutil.iter_modules(
            fileformats.__path__, prefix=fileformats.__package__ + "."
        ),
    ):
        if mod_info.name.split(".")[-1] in exclude:
            continue
        yield importlib.import_module(mod_info.name)
    for vnd_info in pkgutil.iter_modules(
        fileformats.vendor.__path__,
        prefix=fileformats.vendor.__package__ + ".",
    ):
        vnd_pkg = importlib.import_module(vnd_info.name)
        for mod_info in pkgutil.iter_modules(
            vnd_pkg.__path__,
            prefix=vnd_info.name + ".",
        ):
            if ".".join(mod_info.name.split(".")[-3:-1]) in exclude:
                continue
            yield importlib.import_module(mod_info.name)


@contextmanager
def set_cwd(path: Path) -> ty.Generator[Path, None, None]:
    """Sets the current working directory to `path` and back to original
    working directory on exit

    Parameters
    ----------
    path : str
        The file system path to set as the current working directory
    """
    pwd = os.getcwd()
    os.chdir(path)
    try:
        yield path
    finally:
        os.chdir(pwd)


def fspaths_converter(fspaths: FspathsInputType) -> ty.FrozenSet[Path]:
    """Ensures fs-paths are a set of pathlib.Path"""
    import fileformats.core

    if isinstance(fspaths, fileformats.core.FileSet):
        fspaths = fspaths.fspaths
    elif isinstance(fspaths, (str, os.PathLike)):
        fspaths = [Path(fspaths)]
    return frozenset(_resolve_windows_path(Path(p).absolute()) for p in fspaths)


# Cache of drive-letter → UNC root (None if not a mapped network drive)
_windows_drive_unc_cache: ty.Dict[str, ty.Optional[str]] = {}


def _resolve_windows_path(path: Path) -> Path:
    """On Windows, resolve mapped-drive paths to their ``\\\\?\\UNC\\`` form.

    Python 3.11+ can prefix absolute paths with ``\\\\?\\`` (the extended-length
    path prefix).  For local drives this is harmless, but for mapped network
    drives ``\\\\?\\DRIVE:\\...`` bypasses the Windows drive-substitution table
    so ``stat`` / ``is_file`` fail.  Converting to ``\\\\?\\UNC\\server\\share\\...``
    preserves long-path support while keeping the path stat-able.

    For paths that are already UNC (``\\\\server\\...`` or ``\\\\?\\UNC\\...``),
    non-drive paths, and non-Windows platforms the path is returned unchanged.
    """
    import platform
    import subprocess as sp

    if platform.system() != "Windows":
        return path

    path_str = str(path)

    # Determine drive letter and remainder, noting whether \\?\ prefix is present
    if path_str.startswith("\\\\?\\") and not path_str.startswith("\\\\?\\UNC\\"):
        # e.g. \\?\T:\Clinical Scans\foo.dcm
        drive = path_str[4:6].upper()  # "T:"
        remainder = path_str[6:]  # \Clinical Scans\foo.dcm
        has_long_prefix = True
    elif len(path_str) >= 2 and path_str[1] == ":" and path_str[0].isalpha():
        # e.g. T:\Clinical Scans\foo.dcm
        drive = path_str[:2].upper()
        remainder = path_str[2:]
        has_long_prefix = False
    else:
        return path

    if drive not in _windows_drive_unc_cache:
        result = sp.run(["net", "use", drive], capture_output=True, text=True)
        unc: ty.Optional[str] = None
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.strip().split(None, 2)
                # "net use" output has a "Remote name" line with the UNC path
                if len(parts) == 3 and parts[2].startswith("\\\\"):
                    unc = parts[2].strip()
                    break
        _windows_drive_unc_cache[drive] = unc

    unc_root = _windows_drive_unc_cache[drive]
    if unc_root is None:
        return path

    # Convert \\server\share to \\?\UNC\server\share to preserve long-path support,
    # then append the remainder (e.g. \Clinical Scans\foo.dcm)
    if has_long_prefix:
        return Path("\\\\?\\UNC\\" + unc_root.lstrip("\\") + remainder)
    return Path(unc_root + remainder)


def add_exc_note(e: Exception, note: str) -> Exception:
    """Adds a note to an exception in a Python <3.11 compatible way

    Parameters
    ----------
    e : Exception
        the exception to add the note to
    note : str
        the note to add

    Returns
    -------
    Exception
        returns the exception again
    """
    if hasattr(e, "add_note"):
        e.add_note(note)
    else:
        e.args = (e.args[0] + "\n" + note,)
    return e


def matching_source(
    task1: ty.Callable[..., ty.Any], task2: ty.Callable[..., ty.Any]
) -> bool:
    """Checks to see if the tasks share the same source code but are just getting reimported
    for some unknown reason"""
    mod1 = inspect.getmodule(task1)
    mod2 = inspect.getmodule(task2)
    assert mod1 and mod2
    return inspect.getsource(mod1) == inspect.getsource(mod2)


def check_package_exists_on_pypi(package_name: str, timeout: int = 5) -> bool:
    """Check if a package exists on PyPI

    Parameters
    ----------
    package_name : str
        the name of the package to check for

    Returns
    -------
    bool
        whether the package exists on PyPI or not
    """
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        urllib.request.urlopen(url, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        else:
            raise
    return True


class ExtrasModule:
    def __init__(self, imported: bool, pkg: ty.Optional[str], pypi: ty.Optional[str]):
        self.imported = imported
        self.pkg = pkg
        self.pypi = pypi

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(pkg={self.pkg}, pypi={self.pypi}, "
            f"imported={self.imported})"
        )


def import_extras_module(klass: ty.Type["fileformats.core.DataType"]) -> ExtrasModule:
    """Attempt to load extras module corresponding to the provided class's module

    Parameters
    ----------
    klass : ty.Type
        the class to load the extras module for

    Returns
    -------
    imported : bool
        whether the module was imported or not
    sub_pkg : str
        the name of the sub-package that was attempted to be loaded
    """
    from .identification import BUNDLED_EXTRAS_NAMESPACES

    # Check for Mock class
    try:
        klass = klass.TRUE_CLASS  # type: ignore
    except AttributeError:
        pass
    try:
        if klass.vendor:
            sub_pkg = f"vendor.{klass.vendor}.{klass.namespace}"
        else:
            sub_pkg = klass.namespace
    except FormatDefinitionError:
        logger.debug(
            "There is no 'extras' module for classes not within the 'fileformats' package, "
            "not %s in %s",
            klass.__name__,
            klass.__module__,
        )
        return ExtrasModule(True, None, None)
    extras_pkg = "fileformats.extras." + sub_pkg.replace("-", "_")
    if sub_pkg in BUNDLED_EXTRAS_NAMESPACES:
        extras_pypi = "fileformats-extras"
    elif klass.vendor:
        extras_pypi = f"fileformats-{klass.vendor}-extras"
    else:
        extras_pypi = f"fileformats-{klass.namespace}-extras"
    try:
        importlib.import_module(extras_pkg)
    except ModuleNotFoundError as e:
        # The missing module can be a parent of the extras package rather than the
        # package itself, e.g. importing "fileformats.extras.vendor.<vendor>.<namespace>"
        # when there is no "fileformats.extras.vendor.<vendor>" sub-package at all.
        # Errors raised from *within* the extras module are still propagated
        if not e.name or not (
            extras_pkg == e.name or extras_pkg.startswith(e.name + ".")
        ):
            raise
        extras_imported = False
    else:
        extras_imported = True
    return ExtrasModule(extras_imported, extras_pkg, extras_pypi)


TypeType = ty.TypeVar("TypeType", bound=ty.Type[ty.Any])


def is_optional(type_: ty.Union[TypeType, ty.Type[ty.Optional[TypeType]]]) -> bool:
    """Checks if a type is an Optional type

    Parameters
    ----------
    type_ : ty.Type
        the type to check
    allowed : bool
        whether Optional types are allowed or not

    Returns
    -------
    bool
        whether the type is an Optional type or not
    """
    return is_union(type_) and type(None) in ty.get_args(type_)


def get_optional_type(
    type_: ty.Union[TypeType, ty.Type[ty.Optional[TypeType]]], allowed: bool = True
) -> TypeType:
    """Checks if a type is an Optional type

    Parameters
    ----------
    type_ : ty.Type
        the type to check
    allowed : bool
        whether Optional types are allowed or not

    Returns
    -------
    bool
        whether the type is an Optional type or not
    """
    if not is_union(type_):
        return type_  # type: ignore[return-value]
    if not allowed:
        raise FormatDefinitionError(
            f"Optional types are not allowed in content_type definitions ({type_}) "
            "in this context"
        )
    args = ty.get_args(type_)
    if len(args) != 2 and None in args:
        raise FormatDefinitionError(
            "Only Optional types are allowed in content_type definitions, "
            f"not {type_}"
        )
    return args[0] if args[0] is not None else args[1]  # type: ignore[no-any-return]


def is_union(type_: type, args: ty.Optional[ty.List[type]] = None) -> bool:
    """Checks whether a type is a Union, in either ty.Union[T, U] or T | U form

    Parameters
    ----------
    type_ : type
        the type to check
    args : list[type], optional
        required arguments of the union to check, by default (None) any args will match

    Returns
    -------
    is_union : bool
        whether the type is a Union type
    """
    if ty.get_origin(type_) in UNION_TYPES:
        if args is not None:
            return list(ty.get_args(type_)) == args
        return True
    return False


def collate_metadata_series(
    metadata_series: list[ty.Mapping[str, ty.Any]],
) -> ty.Mapping[str, ty.Any]:
    """Collates metadata across a series, returning a dictionary where each key is a
    metadata field and the value is either a single value (if the field is the same
    across all items in the series) or a list of values (if the field varies across
    items in the series). This can be used to identify which fields are consistent
    across the series and which fields vary, which can be useful for selecting
    appropriate metadata fields for deidentification.

    Parameters
    ----------
    metadata_series : list[dict[str, Any]]
        A list of metadata dictionaries to collate

    Returns
    -------
    dict[str, Any]
        A dictionary where each key is a metadata field and the value is either a single
        value (if the field is the same across all items in the series) or a list of
        values (if the field varies across items in the series)
    """
    collated: dict[str, ty.Any] = {}
    key_repeats: ty.Counter[str] = Counter()
    varying_keys = set()
    for metadata in metadata_series:
        for key, val in metadata.items():
            try:
                prev_val = collated[key]
            except KeyError:
                collated[key] = (
                    val  # Insert initial value (should only happen on first iter)
                )
                key_repeats.update([key])
            else:
                if key in varying_keys:
                    collated[key].append(val)
                # Check whether the value is the same as the values in the previous
                # images in the series
                elif val != prev_val:
                    collated[key] = [prev_val] * key_repeats[key] + [val]
                    varying_keys.add(key)
                else:
                    key_repeats.update([key])
    return collated
