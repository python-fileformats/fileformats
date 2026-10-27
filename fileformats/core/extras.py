import functools
import importlib
import inspect
import logging
import os
import shutil
import tempfile
import types
import typing as ty
import urllib.error
from itertools import zip_longest
from pathlib import Path
from typing import Annotated, Self

import fileformats.core
from fileformats.core.typing import TypeAlias

from .converter_helpers import Converter, SubtypeVar
from .datatype import DataType
from .exceptions import (
    FileFormatsClashingExtrasImplementationError,
    FileFormatsExtrasNotImplementedError,
    FormatConversionError,
)
from .loaded import LoadedMarker, resolve_loaded_type
from .utils import add_exc_note, check_package_exists_on_pypi, import_extras_module

logger = logging.getLogger("fileformats")

if ty.TYPE_CHECKING:
    from pydra.compose.base import Task

T = ty.TypeVar("T")
ExtraImplementation = ty.TypeVar("ExtraImplementation", bound=ty.Callable[..., ty.Any])
ExtraMethod = ty.TypeVar("ExtraMethod", bound=ty.Callable[..., ty.Any])
# Called as `wrapper(implementation, obj, *args, **kwargs)`
ExtraWrapper: TypeAlias = ty.Callable[..., ty.Any]


@ty.overload
def extra(method: ExtraMethod) -> ExtraMethod: ...


@ty.overload
def extra(*, wrapper: ExtraWrapper) -> ty.Callable[[ExtraMethod], ExtraMethod]: ...


def extra(
    method: ty.Optional[ExtraMethod] = None,
    *,
    wrapper: ty.Optional[ExtraWrapper] = None,
) -> ty.Union[ExtraMethod, ty.Callable[[ExtraMethod], ExtraMethod]]:
    """A decorator which uses singledispatch to facilitate the registering of
    "extra" functionality in external packages (e.g. "fileformats-extras")

    Parameters
    ----------
    method : Callable
        the method to define as an extra hook. Its signature is what implementations
        are checked against and its body is only called if there is no implementation
        registered for the type (so it should just raise NotImplementedError)
    wrapper : Callable, optional
        a function wrapped around every call to the registered implementations, e.g.
        to validate arguments or return values. It is called as
        ``wrapper(implementation, obj, *args, **kwargs)`` and is responsible for
        calling ``implementation(obj, *args, **kwargs)`` and returning its result
    """
    if method is None:

        def extra_decorator(method: ExtraMethod) -> ExtraMethod:
            return extra(method, wrapper=wrapper)  # type: ignore[call-overload, no-any-return]

        return extra_decorator

    dispatch_method: ty.Callable[..., ty.Any] = functools.singledispatch(method)

    @functools.wraps(method)
    def decorated_extra(obj: DataType, *args: ty.Any, **kwargs: ty.Any) -> ty.Any:
        cls = type(obj)
        extras = []
        for tp in cls.referenced_types():  # type: ignore[attr-defined]
            extras.append(import_extras_module(tp))
        if dispatch_method.dispatch(cls) is dispatch_method.dispatch(object):  # type: ignore[attr-defined]
            # Nothing registered for the type yet, so try the extras modules of its base
            # classes, e.g. for a format subclassing one from another namespace
            _import_base_extras_modules(cls)
        try:
            if wrapper is None:
                return dispatch_method(obj, *args, **kwargs)
            return wrapper(dispatch_method, obj, *args, **kwargs)
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
                elif xtra.pkg:
                    msg += (
                        f'. The "{xtra.pkg}" extras module is installed but doesn\'t '
                        "register an implementation, which can happen when it is out of "
                        'date with respect to the installed "fileformats" package, so '
                        "try upgrading it (e.g. "
                        f"'pip install --upgrade {xtra.pypi}') and check again"
                    )
            raise FileFormatsExtrasNotImplementedError(msg) from None

    # Store single dispatch method on the decorated function so we can register
    # implementations to it later
    decorated_extra._dispatch = dispatch_method  # type: ignore[attr-defined]
    return decorated_extra  # type: ignore[return-value]


def staged_out_dir(
    implementation: ty.Callable[..., ty.Any],
    obj: ty.Any,
    out_dir: "os.PathLike[str] | str",
    *args: ty.Any,
    **kwargs: ty.Any,
) -> ty.Any:
    """A wrapper for extra methods that write a fileset to the `out_dir` passed as
    their first argument (e.g. ``@extra(wrapper=staged_out_dir)``), which passes the
    implementations a hidden staging directory alongside `out_dir` instead, and only
    moves its contents into `out_dir` once they have returned. That way, only complete
    output ends up in `out_dir`, and implementations are free to copy files there and
    modify them in place.

    The implementations need to return a fileset within the `out_dir` they are passed,
    which is returned relocated to the requested `out_dir`. Any existing files in
    `out_dir` are left in place, but a FileExistsError is raised, before anything is
    moved, if the output would overwrite any of them.
    """
    out_dir = Path(out_dir).absolute()
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(dir=out_dir.parent, prefix=f".staging-{out_dir.name}-")
    )
    try:
        output = implementation(obj, staging_dir, *args, **kwargs)
        try:
            rel_fspaths = [
                p.absolute().relative_to(staging_dir) for p in output.fspaths
            ]
        except ValueError:
            raise RuntimeError(
                f"The {getattr(implementation, '__name__', implementation)!r} "
                f"implementation for {type(obj)} didn't write its output to the "
                f"'out_dir' it was passed: {output.fspaths}"
            ) from None
        entries = sorted(staging_dir.iterdir())
        if existing := [e.name for e in entries if (out_dir / e.name).exists()]:
            raise FileExistsError(
                f"Cannot write the output for {obj} into {out_dir} as {existing} "
                "already exist(s) there"
            )
        out_dir.mkdir(exist_ok=True)
        for entry in entries:
            os.replace(entry, out_dir / entry.name)
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
    return type(output)([out_dir / p for p in rel_fspaths])


def _import_base_extras_modules(datatype: ty.Type[DataType]) -> None:
    """Import the extras modules of the base classes of `datatype`, which may contain
    implementations it inherits (e.g. if it subclasses a format from another namespace
    or is defined outside of fileformats packages)"""
    for base in datatype.__mro__[1:]:
        if inspect.isclass(base) and issubclass(base, DataType):
            import_extras_module(base)


def find_extra_implementation(
    method: ty.Callable[..., ty.Any], datatype: ty.Type[DataType]
) -> ty.Optional[ty.Callable[..., ty.Any]]:
    """Find the implementation of an extra method that would be called for the given
    type, importing any extras modules that could contain it first

    Parameters
    ----------
    method : Callable
        the extra method, e.g. ``FileSet.load``
    datatype : type[DataType]
        the type to find the implementation for

    Returns
    -------
    Callable or None
        the registered implementation (which may be registered for a base class of
        `datatype`), or None if there isn't one
    """
    try:
        dispatch_method = method._dispatch  # type: ignore[attr-defined]
    except AttributeError:
        raise ValueError(f"{method} has not been defined as an extra method")
    for tp in datatype.referenced_types():  # type: ignore[attr-defined]
        import_extras_module(tp)
    _import_base_extras_modules(datatype)
    implementation: ty.Callable[..., ty.Any] = dispatch_method.dispatch(datatype)
    if implementation is dispatch_method.dispatch(object):
        return None
    return implementation


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
        if isinstance(dispatched_type, str):
            dispatched_type = eval(dispatched_type, implementation.__globals__)
        differences = []

        def resolve_loaded_self(tp: ty.Any) -> ty.Any:
            """Substitute `Loaded[Self]` in the method signature with the `loaded_type`
            of the type the implementation is registered for. Dotted-path strings
            (e.g. "pydicom.FileDataset") are left as is so they can be matched against
            identical string annotations without importing the optional dependency"""
            marker = LoadedMarker.from_hint(tp)
            if marker is not None and marker.format is Self:  # type: ignore[comparison-overlap]
                return dispatched_type.loaded_type
            return tp

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

            # Compare `Loaded[X]` hints by their loaded types
            if ty.get_origin(mtype) is Annotated:
                mtype = ty.get_args(mtype)[0]
            if ty.get_origin(ftype) is Annotated:
                ftype = ty.get_args(ftype)[0]

            if mtype is ty.Any:
                return True

            if isinstance(mtype, str) and not isinstance(ftype, str):
                try:
                    mtype = eval(mtype, implementation.__globals__)
                except Exception:
                    # a dotted-path `loaded_type` not imported into the module
                    mtype = resolve_loaded_type(mtype)
                    if mtype is ty.Any:
                        return True
            elif isinstance(ftype, str) and not isinstance(mtype, str):
                try:
                    ftype = eval(ftype, implementation.__globals__)
                except Exception:
                    return False

            if mtype == ftype:  # type: ignore[comparison-overlap]
                return True

            # Annotating an optional argument with `None` in an implementation is the
            # standard way to signify that the implementation ignores it
            if ftype is None or ftype is type(None):
                return type(None) in ty.get_args(mtype)

            # A union in the implementation matches if each of its members matches a
            # member of the method's union (or the method's type if it isn't a union),
            # i.e. implementations can accept a subset of what the method accepts, e.g.
            # `Loaded[X] | Loaded[Y] | None` for `Loaded[FileSet] | None`
            if ty.get_origin(ftype) in (ty.Union, types.UnionType):
                margs = (
                    ty.get_args(mtype)
                    if ty.get_origin(mtype) in (ty.Union, types.UnionType)
                    else (mtype,)
                )
                return all(
                    any(type_match(mt, ft) for mt in margs) for ft in ty.get_args(ftype)
                )

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
                mkwargs_type = resolve_loaded_self(mkwargs.annotation)
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
            mtype = resolve_loaded_self(mparam.annotation)
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
        mreturn = resolve_loaded_self(msig.return_annotation)
        if not type_match(mreturn, fsig.return_annotation):
            differences.append(
                f"return type: {mreturn!r} vs {fsig.return_annotation!r}"
            )
            if isinstance(mreturn, str) and not isinstance(fsig.return_annotation, str):
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
        # Register against the dispatched type explicitly, as otherwise singledispatch
        # evaluates all the annotations of the implementation with get_type_hints()
        # (on Python < 3.14), which fails for types from optional dependencies that are
        # only imported when type-checking (e.g. "numpy.ndarray")
        dispatch_method.register(dispatched_type, implementation)
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
