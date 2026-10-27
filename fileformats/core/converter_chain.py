"""Generic Pydra workflow used to chain converters together to convert between formats
via intermediate formats when no direct converter is available. Kept separate from
converter_helpers so that Pydra is only imported when a chain is required"""

import typing as ty
from collections import Counter

import attrs
from pydra.compose import workflow

from .converter_helpers import Converter
from .exceptions import FormatConversionError
from .fileset import FileSet


def step_names(chain: ty.Sequence[Converter]) -> list[str]:
    """Names of the nodes for each converter in the chain, i.e. the name of the converter
    task class, suffixed with a counter if the same converter appears more than once

    Parameters
    ----------
    chain : Sequence[Converter]
        the converters in the chain

    Returns
    -------
    list[str]
        names of the nodes for each converter in the chain
    """
    counts: Counter[str] = Counter()
    names = []
    for conv in chain:
        name = type(conv.task).__name__
        counts[name] += 1
        names.append(name if counts[name] == 1 else f"{name}_{counts[name]}")
    return names


def assign_kwargs(
    chain: ty.Sequence[Converter], kwargs: ty.Dict[str, ty.Any]
) -> list[dict[str, ty.Any]]:
    """Assigns keyword arguments to the converters in the chain. Plain keys are applied
    to every converter that has an input of that name, while keys of the form
    "<step-name>.<input>" are only applied to the named step (see `step_names`)

    Parameters
    ----------
    chain : Sequence[Converter]
        the converters in the chain
    kwargs : dict[str, Any]
        the keyword arguments to assign

    Returns
    -------
    list[dict[str, Any]]
        the keyword arguments to apply to each converter in the chain

    Raises
    ------
    FormatConversionError
        if a keyword argument doesn't match an input of any (or the named) converter
    """
    names = step_names(chain)
    assigned: list[dict[str, ty.Any]] = [{} for _ in chain]
    for key, value in kwargs.items():
        if "." in key:
            step_name, field_name = key.split(".", 1)
            if step_name not in names:
                raise FormatConversionError(
                    f"No converter step named {step_name!r} in chain, {names}, to "
                    f"apply {key!r} to"
                )
            indices = [names.index(step_name)]
        else:
            field_name = key
            indices = list(range(len(chain)))
        matched = False
        for i in indices:
            conv = chain[i]
            if field_name != conv.in_file and field_name in attrs.fields_dict(
                type(conv.task)
            ):
                assigned[i][field_name] = value
                matched = True
        if not matched:
            raise FormatConversionError(
                f"{key!r} doesn't match an input of any of the converters in the chain, "
                f"{names}"
            )
    return assigned


@workflow.define(outputs=["out_file"])  # type: ignore[untyped-decorator]
def ConverterChain(
    in_file: FileSet,
    chain: list[Converter],
    converter_kwargs: ty.Optional[dict[str, ty.Any]] = None,
) -> FileSet:
    """Applies a chain of converters in sequence

    Parameters
    ----------
    in_file : FileSet
        the file-set to convert
    chain : list[Converter]
        the converters to apply, in order
    converter_kwargs : dict[str, Any], optional
        keyword arguments to pass to the converters, see `assign_kwargs`

    Returns
    -------
    out_file : FileSet
        the converted file-set
    """
    out_file = in_file
    for conv, name, kwargs in zip(
        chain, step_names(chain), assign_kwargs(chain, converter_kwargs or {})
    ):
        node_outputs = workflow.add(
            attrs.evolve(conv.task, **{conv.in_file: out_file}, **kwargs), name=name
        )
        out_file = getattr(node_outputs, conv.out_file)
    return out_file


# Pydra creates the task class dynamically, so set the module so that it can be
# identified (see Converter.is_chain) and pickled by reference
ConverterChain.__module__ = __name__
