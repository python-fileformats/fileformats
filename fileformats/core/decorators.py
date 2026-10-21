import time
import typing as ty
from pathlib import Path
from threading import RLock

import fileformats.core

from .fs_mount_identifier import FsMountIdentifier

PropReturn = ty.TypeVar("PropReturn")


__all__ = ["mtime_cached_property", "classproperty"]


class mtime_cached_property:
    """A property that is cached until the mtimes of the files in the fileset are changed"""

    def __init__(self, func: ty.Callable[..., ty.Any]):
        self.func = func
        self.__doc__ = func.__doc__
        self.lock = RLock()
        # Keyed by the qualified name, so an override in a subclass and the base
        # property it calls (Base.prop.__get__(obj)) cache separately. With the
        # bare name they shared one slot, and whichever ran first served both.
        self._cache_name = f"_{func.__qualname__}_mtime_cache"

    def __get__(
        self,
        instance: ty.Optional["fileformats.core.FileSet"],
        owner: ty.Optional[ty.Type["fileformats.core.FileSet"]] = None,
    ) -> ty.Any:
        if instance is None:  # if accessing property from class not instance
            return self
        assert isinstance(instance, fileformats.core.FileSet), (
            "Cannot use mtime_cached_property instance with "
            f"{type(instance).__name__!r} object, only FileSet objects."
        )
        try:
            mtimes, value = instance.__dict__[self._cache_name]
        except KeyError:
            pass
        else:
            if (
                instance.mtimes == mtimes
                and enough_time_has_elapsed_given_mtime_resolution(mtimes)
            ):
                return value
            else:
                del instance.__dict__[self._cache_name]
        with self.lock:
            # check if another thread filled cache while we awaited lock
            try:
                mtimes, value = instance.__dict__[self._cache_name]
            except KeyError:
                pass
            else:
                if (
                    instance.mtimes == mtimes
                    and enough_time_has_elapsed_given_mtime_resolution(mtimes)
                ):
                    return value
            value = self.func(instance)
            instance.__dict__[self._cache_name] = (instance.mtimes, value)
        return value


# def classproperty(meth: ty.Callable[..., PropReturn]) -> PropReturn:
#     """Access a @classmethod like a @property."""
#     # mypy doesn't understand class properties yet: https://github.com/python/mypy/issues/2563
#     return classmethod(property(meth))  # type: ignore


def validated_property(meth: ty.Callable[..., PropReturn]) -> PropReturn:
    """A property that is checked during validation of a FileSet"""
    prop = property(meth)
    prop.fget.__annotations__[VALIDATED_PROPERTY_FLAG] = True
    return prop  # type: ignore


class classproperty(object):  # type: ignore[no-redef]  # noqa
    def __init__(self, f: ty.Callable[[ty.Any], ty.Any]):
        self.f = f

    def __get__(self, obj: ty.Any, owner: ty.Any) -> ty.Any:
        return self.f(owner)


def enough_time_has_elapsed_given_mtime_resolution(
    mtimes: ty.Iterable[ty.Tuple[Path, ty.Union[int, float]]],
    current_time: ty.Optional[int] = None,
) -> bool:
    """Determines whether enough time has elapsed since the the last of the cached mtimes
    to be sure that changes in mtimes will be detected given the resolution of the mtimes
    on the file system. For example, on systems with a mtime resolution of a second,
    a change in mtime may not be detected if the cache is re-read within a second and
    the file is modified in the intervening period (probably only likely during tests).
    So this function guesses the resolution of the mtimes by the
    minimum number of trailing zeros in the mtimes and then checks if enough time has
    passed to be sure that any changes in mtimes will be detected.

    This may result in false negatives for systems with low mtime resolutions, but
    this will just result in (presumably minor) performance hit via unnecessary cache
    invalidations.

    Parameters
    ----------
    mtimes : Iterable[tuple[Path, int]]
        the path-mtime pairs in nanoseconds to guess the resolution of

    Returns
    -------
    bool
        whether enough time has elapsed since the lagiven the guessed resolution of the mtimes
    """
    if current_time is None:
        current_time = time.time_ns()
    for fspath, mtime in mtimes:
        mtime_resolution = FsMountIdentifier.get_mtime_resolution(fspath)
        if current_time - mtime <= mtime_resolution:
            return False
    return True


VALIDATED_PROPERTY_FLAG = "_validated_property"
