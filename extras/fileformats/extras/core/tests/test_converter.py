import typing as ty
from pathlib import Path

import attrs
import pytest
from pydra.compose import python, shell

from conftest import write_test_file
from fileformats.application import Tar, TarGzip, Zip
from fileformats.core import ConvertibleToMarker, converter
from fileformats.core.exceptions import FormatConversionError
from fileformats.generic import File, FileSet
from fileformats.testing import (
    AnotherConcreteClass,
    Bar,
    Baz,
    ConcreteClass,
    ConvertibleToFile,
    Foo,
    Qux,
)


@converter
@python.define(outputs={"out_file": Bar})  # type: ignore[untyped-decorator]
def FooBarConverter(in_file: Foo):
    return Bar(write_test_file(Path.cwd() / "bar.bar", in_file.raw_contents))


@converter(out_file="out")
@python.define(outputs={"out": Bar})  # type: ignore[untyped-decorator]
def BazBarConverter(in_file: Baz):
    assert in_file
    return Bar(write_test_file(Path.cwd() / "bar.bar", in_file.raw_contents))


@converter(source_format=Foo, target_format=Qux)
@shell.define
class FooQuxConverter(shell.Task["FooQuxConverter.Outputs"]):

    in_file: File = shell.arg(help="the input file", argstr="")
    executable = "cp"

    class Outputs(shell.Outputs):
        out_file: File = shell.outarg(
            help="output file",
            argstr="",
            position=-1,
            path_template="out.qux",
        )


def test_get_converter_functask(work_dir):

    fspath = work_dir / "test.foo"
    write_test_file(fspath)
    assert attrs.asdict(Bar.get_converter(Foo).task) == attrs.asdict(FooBarConverter())


def test_get_converter_shellcmd(work_dir):

    fspath = work_dir / "test.foo"
    write_test_file(fspath)
    assert attrs.asdict(Qux.get_converter(Foo).task) == attrs.asdict(FooQuxConverter())


def test_get_converter_fail(work_dir):

    fspath = work_dir / "test.foo"
    write_test_file(fspath)
    with pytest.raises(FormatConversionError):
        Baz.get_converter(Foo)


def test_convert_functask(work_dir):

    fspath = work_dir / "test.foo"
    write_test_file(fspath)
    foo = Foo(fspath)
    bar = Bar.convert(foo)
    assert type(bar) is Bar
    assert bar.raw_contents == foo.raw_contents


def test_convert_shellcmd(work_dir):

    fspath = work_dir / "test.foo"
    write_test_file(fspath)
    foo = Foo(fspath)
    qux = Qux.convert(foo)
    assert type(qux) is Qux
    assert qux.raw_contents == foo.raw_contents


def test_convert_mapped_conversion(work_dir):

    fspath = work_dir / "test.baz"
    write_test_file(fspath)
    baz = Baz(fspath)
    bar = Bar.convert(baz)
    assert type(bar) is Bar
    assert bar.raw_contents == baz.raw_contents


def archives_of(klass: type[FileSet]) -> tuple[type[FileSet], ...]:
    """The archive types that any type can be extracted from by the generic converters
    from archives, e.g. `Zip[Compressed]` -> `Compressed`"""
    return (TarGzip[klass], Tar[klass], Zip[klass])


def split_convertible_from(
    klass: type[FileSet], **kwargs: ty.Any
) -> tuple[tuple[type[FileSet], ...], tuple[type[FileSet], ...]]:
    """Splits the types that `klass` is convertible from into the generic ones (i.e.
    the source types of generic converters with their wildcards resolved to `klass`,
    e.g. `Zip[klass]`) and the rest. Which generic converters are registered depends
    on the other tests that have been run (e.g. the classifier tests), so the generic
    ones can only be checked for the archive types"""
    hint = klass.convertible_from(**kwargs)
    assert ConvertibleToMarker.from_hint(hint) == ConvertibleToMarker(klass)
    members = ty.get_args(ty.get_args(hint)[0]) or (ty.get_args(hint)[0],)
    generic = tuple(
        t for t in members if klass in getattr(t, "classifiers", ()) and t is not klass
    )
    return tuple(t for t in members if t not in generic), generic


@pytest.mark.parametrize(
    ["klass", "convertible_from"],
    [
        [Bar, Bar | Baz | Foo],
        [Qux, Foo | Qux],
        [Foo, Foo],
        [Baz, Baz],
        [
            ConvertibleToFile,
            AnotherConcreteClass | ConcreteClass | ConvertibleToFile,
        ],
    ],
)
def test_convertible_from(klass: type[FileSet], convertible_from: type[FileSet]):
    direct, generic = split_convertible_from(klass)
    assert set(direct) == set(ty.get_args(convertible_from) or (convertible_from,))
    assert set(archives_of(klass)).issubset(generic)
