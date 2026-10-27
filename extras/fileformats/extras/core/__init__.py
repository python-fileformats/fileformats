"""Only required to hold the automatically generated version for the "core" extras"""

import typing as ty
import types
import inspect
from ._version import __version__


def check_optional_dependency(module: ty.Optional[types.ModuleType]) -> None:
    if module is None:
        frame = inspect.currentframe()
        while frame:
            # Find the frame where the decorated_extra method was called
            if frame.f_code.co_name == "decorated_extra":
                extras_module = frame.f_locals["extras"][0].pkg.split(".")[-1]
                break
            frame = frame.f_back
        raise ImportError(
            f"The optional dependencies are not installed for '{extras_module}', please include when "
            f"installing fileformats-extras, e.g. `pip install 'fileformats-extras[{extras_module}]'`"
        )


__all__ = ["__version__"]
