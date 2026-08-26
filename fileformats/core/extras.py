import functools
import importlib
import inspect
import logging
import sys
import typing as ty
import urllib.error
from itertools import zip_longest

import fileformats.core
from fileformats.core.typing import TypeAlias

from .converter_helpers import Converter, SubtypeVar
from .datatype import DataType
from .exceptions import (
    FileFormatsClashingExtrasImplementationError,
    FileFormatsExtrasNotImplementedError,
    FormatConversionError,
)
from .utils import add_exc_note, check_package_exists_on_pypi, import_extras_module

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

logger = logging.getLogger("fileformats")

if ty.TYPE_CHECKING:
    from pydra.compose.base import Task

T = ty.TypeVar("T")
ExtraImplementation = ty.TypeVar("ExtraImplementation", bound=ty.Callable[..., ty.Any])
ExtraMethod = ty.TypeVar("ExtraMethod", bound=ty.Callable[..., ty.Any])


def extra(method: ExtraMethod) -> "ExtraMethod":
    """A decorator which uses singledispatch to facilitate the registering of
    "extra" functionality in external packages (e.g. "fileformats-extras")"""

    dispatch_method: ty.Callable[..., ty.Any] = functools.singledispatch(method)

    @functools.wraps(method)
    def decorated_extra(obj: DataType, *args: ty.Any, **kwargs: ty.Any) -> ty.Any:
        cls = type(obj)
        extras = []
        for tp in cls.referenced_types():  # type: ignore[attr-defined]
            extras.append(import_extras_module(tp))
        try:
            return dispatch_method(obj, *args, **kwargs)
        except NotImplementedError:
            msg = f"No implementation for {method.__name__!r} extra for {cls.__name__} types"
            for xtra in extras:
                if not xtra.imported:
                    try:
                        if xtra.pypi and check_package_exists_on_pypi(xtra.pypi):
                            msg += (
                                f'. An "extras" package exists on PyPI ({xtra.pypi}), '
                                "which may contain an implementation, try installing it "
                                f"(e.g. 'pip install {xtra.pypi}') and check again"
                            )
                    except urllib.error.URLError:
                        msg += (
                            '. Was not able to check whether an "extras" package '
                            f"({xtra.pypi}) exists on PyPI or not"
                        )
            raise FileFormatsExtrasNotImplementedError(msg) from None

    # Store single dispatch method on the decorated function so we can register
    # implementations to it later
    decorated_extra._dispatch = dispatch_method  # type: ignore[attr-defined]
    return decorated_extra  # type: ignore[return-value]


def extra_implementation(
    method: ExtraMethod,
) -> ty.Callable[[ExtraImplementation], ExtraImplementation]:
    """A decorator which uses singledispatch to facilitate the registering of
    "extra" functionality in external packages (e.g. "fileformats-extras")"""
    try:
        dispatch_method = method._dispatch  # type: ignore[attr-defined]
    except AttributeError:
        raise ValueError(
            f"{method} has not been defined as an extra method, so cannot register "
            "an implementation"
        )

    def extra_implementation_decorator(
        implementation: ExtraImplementation,
    ) -> ExtraImplementation:
        msig = inspect.signature(method)
        fsig = inspect.signature(implementation)
        msig_args = list(msig.parameters.values())[1:]
        fsig_args = list(fsig.parameters.values())[1:]
        dispatched_type = list(fsig.parameters.values())[0].annotation
        differences = []

        def type_match(mtype: ty.Union[str, type], ftype: ty.Union[str, type]) -> bool:
            """Check if the types match between the method and function annotations,
            allowing for string annotations and `Self`

            Parameters
            ----------
            mtype : Union[str, type]
                the type of the method argument
            ftype : Union[str, type]
                the type of the function argument
            """

            if isinstance(mtype, str) and not isinstance(ftype, str):
                mtype = eval(mtype, implementation.__globals__)

            if mtype is ty.Any or mtype == ftype:  # type: ignore[comparison-overlap]
                return True

            morigin = ty.get_origin(mtype)
            forigin = ty.get_origin(ftype)

            if morigin is not None or forigin is not None:
                # Reduce to the concrete origin classes for a subclass
                # comparison, e.g. `dict` for both `dict` and
                # `ty.Dict[str, int]`, falling back to the annotation itself
                # if it isn't a parameterised generic (e.g. a bare `dict`
                # being matched against `ty.Mapping[str, int]`)
                mcls = morigin if morigin is not None else mtype
                fcls = forigin if forigin is not None else ftype
                if inspect.isclass(mcls) and inspect.isclass(fcls):
                    if not issubclass(fcls, mcls):
                        return False
                elif mcls != fcls:
                    # origins that aren't classes, e.g. typing.Union,
                    # typing.Literal, etc.
                    return False
                margs = ty.get_args(mtype)
                fargs = ty.get_args(ftype)
                if margs and fargs:
                    return all(
                        type_match(mt, ft) for mt, ft in zip_longest(margs, fargs)
                    )
                return True

            return (
                mtype is ty.Any  # type: ignore[comparison-overlap]
                or mtype == ftype
                or (
                    mtype is Self and issubclass(ftype, dispatched_type)  # type: ignore[comparison-overlap, arg-type]
                )
                or inspect.isclass(ftype)
                and (
                    (inspect.isclass(mtype) and issubclass(ftype, mtype))
                    or (mtype is Self and issubclass(ftype, dispatched_type))  # type: ignore[comparison-overlap, arg-type]
                )
            )

        mhas_kwargs = msig_args and msig_args[-1].kind == inspect.Parameter.VAR_KEYWORD
        fhas_kwargs = fsig_args and fsig_args[-1].kind == inspect.Parameter.VAR_KEYWORD
        if mhas_kwargs:
            mkwargs = msig_args.pop()
            if fhas_kwargs:
                fkwargs = fsig_args.pop()
                mkwargs_type = mkwargs.annotation
                fkwargs_type = fkwargs.annotation
                if not type_match(mkwargs_type, fkwargs_type):
                    differences.append(
                        f"Type of keyword args: {mkwargs_type!r} vs {fkwargs_type!r}"
                    )
                    if isinstance(mkwargs_type, str) and not isinstance(
                        fkwargs_type, str
                    ):
                        differences.append(
                            "Note that the type of keyword args is annotated using a "
                            "string so the implementing method also needs to be a "
                            f'string, i.e. "{mkwargs_type}" instead of {fkwargs_type}'
                        )
            else:
                differences.append("variable keywords vs non-variable keywords")
        elif fhas_kwargs:
            differences.append("non-variable keywords vs variable keywords")
            fsig_args.pop()

        for i, (mparam, fparam) in enumerate(zip_longest(msig_args, fsig_args)):
            if mparam is None:
                if not mhas_kwargs:
                    differences.append(
                        f"found additional argument, {fparam.name!r}, at position {i}"
                    )
                continue
            if fparam is None:
                if mparam.default is mparam.empty:
                    differences.append(
                        f"override missing required argument {mparam.name!r}"
                    )
                continue
            mname = mparam.name
            fname = fparam.name
            mtype = mparam.annotation
            ftype = fparam.annotation
            if mname != fname:
                differences.append(
                    f"name of parameter at position {i}: {mname!r} vs {fname!r}"
                )
            elif not type_match(mtype, ftype):
                differences.append(f"Type of {mname!r} arg: {mtype!r} vs {ftype!r}")
                if isinstance(mtype, str) and not isinstance(ftype, str):
                    differences.append(
                        f"Note that the type of {mname!r} is annotated using a string so the "
                        "implementing method also needs to be a string, i.e. "
                        f'"{ftype}" instead of {ftype}'
                    )
        if not type_match(msig.return_annotation, fsig.return_annotation):
            differences.append(
                f"return type: {msig.return_annotation!r} vs {fsig.return_annotation!r}"
            )
            if isinstance(msig.return_annotation, str) and not isinstance(
                fsig.return_annotation, str
            ):
                differences.append(
                    "Note that the return type of is annotated using a string so the "
                    "implementing method also needs to be a string, i.e. "
                    f'"{fsig.return_annotation}" instead of {fsig.return_annotation}'
                )

        if differences:
            raise TypeError(
                f"Arguments differ between the signature of the extras hook method "
                f"{method} and the implementing function {implementation}:\n"
                + "\n".join(differences)
            )
        # If there is already an implementation registered determine whether to override or
        # not based on whether the implementation is from an extras module.
        if already_registered := dispatch_method.registry.get(dispatched_type):
            already_in_extras = already_registered.__module__.startswith(
                "fileformats.extras"
            )
            if implementation.__module__.startswith("fileformats.extras"):
                if already_in_extras:
                    raise FileFormatsClashingExtrasImplementationError(
                        f"An implementation for {method} extra for {dispatched_type} already "
                        f"exists from an extras module {already_registered.__module__}, "
                        f"overriding it with {implementation} from an extras module, "
                        "this should not be happening, please report "
                        "this to the developers"
                    )
                else:
                    logger.debug(
                        "Silently ignoring internal implementation of %s extra for %s in favor of "
                        "externally defined %s",
                        method,
                        dispatched_type,
                        implementation,
                    )
                return implementation
            else:
                if already_in_extras:
                    logger.debug(
                        "Silently ignoring implementation of %s extra for %s from extras module in favor of "
                        "externally defined %s",
                        method,
                        dispatched_type,
                        implementation,
                    )
                else:
                    raise FileFormatsClashingExtrasImplementationError(
                        f"An external implementation for {method} extra for {dispatched_type} already "
                        f"exists, overriding it with {implementation}: {dispatch_method.registry}"
                    )
        dispatch_method.register(implementation)
        return implementation

    return extra_implementation_decorator


WrappedTask = ty.TypeVar("WrappedTask", bound=ty.Callable[..., ty.Any])
FormatType: TypeAlias = ty.Union[ty.Type["fileformats.core.FileSet"], SubtypeVar, None]


def converter(
    task_type: ty.Optional[ty.Type["Task[T]"]] = None,
    source_format: FormatType = None,
    target_format: FormatType = None,
    in_file: str = "in_file",
    out_file: str = "out_file",
    **converter_kwargs: ty.Any,
) -> ty.Union[
    ty.Type["Task[T]"], ty.Callable[[ty.Type["Task[T]"]], ty.Type["Task[T]"]]
]:
    """Decorator that registers a task as a converter between a source and target format
    pair

    Parameters
    ----------
    task_type : pydra.compose.base.Task, optional
        the Pydra task to register as a converter, if provided the decorator is assumed
        to wrap the task spec directly, otherwise a wrapping decorator is returned instead
    source_format: type, optional
        file-format type to convert from, detected from type of "in_file" by default
    target_format: type, optional
        file-format type to convert to, detected from type of "out_file" by default None
    in_file : str, optional
        name of the input to be considered the "in_file", by default "in_file"
    out_file : _type_, optional
        name of the output to be considered the "out_file",
        by default "out_file" and "out" and will be tried in that order
    **converter_kwargs
        keyword arguments passed on to the converter task
    """

    try:
        import attrs
    except ImportError as e:
        add_exc_note(
            e,
            "To use the 'converter' decorator you need to have the 'attrs' package "
            "installed, this should be installed with Pydra by default",
        )
        raise e
    if "out_file_" in converter_kwargs:
        converter_kwargs["out_file"] = converter_kwargs.pop("out_file_")
    if "in_file_" in converter_kwargs:
        converter_kwargs["in_file"] = converter_kwargs.pop("in_file_")

    def decorator(
        task_type: ty.Type["Task[T]"],
    ) -> ty.Type["Task[T]"]:
        out_file_local = out_file
        source: FormatType
        target: FormatType
        if source_format is None:
            inputs_dict = attrs.fields_dict(task_type)
            source = inputs_dict[in_file].type
        else:
            source = source_format
        if target_format is None:
            outputs_dict = attrs.fields_dict(task_type.Outputs)
            try:
                target = outputs_dict[out_file].type
            except KeyError:
                # If there isn't an 'out_file' field but there is only one output field
                # with the default name of 'out' use that instead
                if out_file == "out_file" and list(outputs_dict.keys()) == ["out"]:
                    out_file_local = "out"
                    target = outputs_dict["out"].type
                else:
                    raise
        else:
            target = target_format
        # Handle string annotations
        if isinstance(source, str) or isinstance(target, str):
            module_dict = importlib.import_module(task_type.__module__).__dict__
            if isinstance(source, str):
                source = eval(source, module_dict)
            if isinstance(target, str):
                target = eval(target, module_dict)
        assert inspect.isclass(source) and inspect.isclass(target)
        if not issubclass(target, fileformats.core.FileSet):
            raise FormatConversionError(
                f"Target file format '{target.__name__}' is not of subtype of "
                "fileformats.core.FileSet"
            )

        target.register_converter(
            source_format=source,
            converter=Converter(
                task_type(**converter_kwargs), in_file=in_file, out_file=out_file_local
            ),
        )
        return task_type

    return decorator if task_type is None else decorator(task_type)
