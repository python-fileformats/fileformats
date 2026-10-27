Extras
======

The functionality in addition to the core validation and detection typically requires
external dependencies and should be put into the separate `extras` project within the
apa Please use an "extra" hook and implement the method in an "extras" package in the
`extension template <https://github.com/python-fileformats/fileformats-extension-template>`__,
to be called fileformats-<yournamespace>-extras.

Hooks and implementations
-------------------------

FileFormats *Extras* enable the creation of hooks in `FileSet` classes using the `@extra`
decorator that can be implemented in separate modules using the `@extra_implementation`
decorator. The "extra methods" typically add additional functionality for accessing and
maninpulating the data within the fileset, i.e. not required for format detection and
validation, and should be implemented in a separate package if they have external
dependencies to keep the main and extension packages dependency free. The
standard place to put these extras-implementations is in the sister "extras" package
named `fileformats-<yournamespace>-extras`, located in the `extras` directory in the
extension package root (see `<https://github.com/python-fileformats/fileformats-extension-template>`__
for further instructions). It is possible to implement extra methods in other modules,
however, the extras package associated with formats namespace will be loaded by default
when a hooked method is accessed.

 Use the `@extra` decorator on a method in the to define an extras method,

 .. code-block:: python

    from typing import Self

    class MyFormat(File):

        ext = ".my"

        @extra
        def my_extra_method(self, index: int, scale: float, save_path: Path) -> Self:
            ...

and then reference that method in the extras package using the `@extra_implementation`

.. code-block:: python

    from some_external_package import load_my_format, save_my_format
    from fileformats.core import extra_implementation
    from fileformats.mypackage import MyFormat

    @extra_implementation(MyFormat.my_extra_method)
    def my_extra_method(
        my_format: MyFormat, index: int scale: float, save_path: Path
    ) -> MyFormat:
        data_array = load_my_format(my_format.fspath)
        data_array[:index] *= scale
        save_my_format(save_path, data_array)
        return MyFormat(save_path)

The first argument to the implementation functions is the instance the method
is executed on, and the types of the remaining arguments and return need to match
the hooked method exactly.

It is possible to provide multiple overloads for subclasses of the format that defines
the hook. Like `functools.singledispacth` (which is used under the hood), the type of
the first argument (not the type of the class the method is referenced from in the decorated)
determines which of the overloaded methods is called


.. code-block:: python

    class MyFormatX(MyFormat):
        ext = ".myx"

    @extra_implementation(MyFormat.my_extra_method)
    def my_extra_method(
        my_format: MyFormat, index: int scale: float, save_path: Path
    ) -> MyFormat:
        ...

    @extra_implementation(MyFormat.my_extra_method)
    def my_extra_method(
        my_format: MyFormatX, index: int scale: float, save_path: Path
    ) -> MyFormatX:
        ...


Wrapping implementations
------------------------

Behaviour that should apply to every implementation of a hook, such as validating
arguments or return values, can be added with the ``wrapper`` argument of ``@extra``.
The wrapper is called with the registered implementation followed by the arguments
the hook was called with, and is responsible for calling the implementation and
returning its result

.. code-block:: python

    def check_index(impl, my_format, index, *args, **kwargs):
        if index < 0:
            raise ValueError(f"index must be non-negative, not {index}")
        return impl(my_format, index, *args, **kwargs)


    class MyFormat(File):

        ext = ".my"

        @extra(wrapper=check_index)
        def my_extra_method(self, index: int, scale: float, save_path: Path) -> Self:
            ...

The body of the hook method is still only called when there is no implementation
registered for the type, and should just raise ``NotImplementedError``. Note that the
wrapper runs before it is known whether an implementation exists, so any checks it
makes will be performed before a missing implementation is reported.

``FileSet.load`` and ``FileSet.save`` use wrappers to check that the data returned by
the ``load`` implementation, and the data passed to ``save``, are of the format's
``loaded_type`` (see below).


Defining loaded types
---------------------

The type of the object returned by ``load`` (and accepted by ``save``) for a format is
declared by its ``loaded_type`` class attribute, which defaults to ``Any``. Since the
format classes shouldn't depend on the packages used to load them, types from optional
dependencies are declared as dotted-path strings, which are only imported (via
``pkgutil.resolve_name``) when they are needed and the package is installed

.. code-block:: python

    class MyFormat(File):

        ext = ".my"
        loaded_type = "some_external_package.MyData"

The ``load`` and ``save`` hooks are annotated with ``Loaded[Self]``, which is resolved
to the ``loaded_type`` of the format an implementation is registered for when its
signature is checked. Implementations therefore need to be annotated with either the
same type (or dotted-path string) or ``Loaded[<format>]``

.. code-block:: python

    @extra_implementation(FileSet.load)
    def load_my_format(my_format: MyFormat, **kwargs: Any) -> "some_external_package.MyData":
        return some_external_package.load(my_format.fspath)


    @extra_implementation(FileSet.save)
    def save_my_format(
        my_format: MyFormat, data: "some_external_package.MyData", **kwargs: Any
    ) -> None:
        some_external_package.save(data, my_format.fspath)

Formats that leave ``loaded_type`` as ``Any`` accept any annotation. If a dotted-path
string can't be imported because the optional package isn't installed, the check is
skipped.

The ``loaded_type`` is also checked at runtime, and a ``TypeError`` is raised if a
``load`` implementation returns an object that isn't an instance of it (the check is
shallow, e.g. only that the object is a ``dict``, not the types of its keys and values).
Make sure the ``loaded_type`` covers everything the format can legitimately load to,
e.g. JSON and YAML documents can be bare scalars as well as mappings and lists.

Hooks of your own can use ``Loaded[Self]`` in the same way to refer to the loaded type
of the format they are implemented for.

Where different implementations of a hook take data loaded from different formats
(e.g. a deidentification recipe that is specific to the format being deidentified),
annotate the hook argument with ``Loaded[FileSet]`` (optionally ``| None``), which
accepts ``Loaded[<format>]`` in the implementations. Callers can then find the format
the implementation for a given type expects with ``find_extra_implementation``

.. code-block:: python

    impl = find_extra_implementation(MedicalImagingData.deidentify, type(image))
    hint = typing.get_type_hints(impl, include_extras=True)["recipe"]
    marker = LoadedMarker.from_hint(hint)
    if marker is None:  # the implementation doesn't take a recipe
        image.deidentify(out_dir)
    else:
        image.deidentify(out_dir, recipe=marker.format(recipe_path).load())

Implementations that ignore an optional argument of the hook should annotate it with
``None``, e.g. ``recipe: None = None``, which is accepted for any argument whose type in
the hook includes ``None``.


Registering converters
----------------------

Converters between two equivalent formats are defined using Pydra_ dataflow engine
`tasks <https://pydra.readthedocs.io/en/latest/components.html>`_. There are two types
of Pydra_ tasks, function tasks, Python functions decorated by ``@pydra.mark.task``, and
shell-command tasks, which wrap command-line tools in Python classes. To register a
Pydra_ task as a converter between two file formats it needs to be decorated with the
``@fileformats.core.converter`` decorator. Like the implementation of extra methods,
converters should be implemented in the sister extras package.

Pydra uses type annotations to define the input and outputs of the tasks. It there is
a input to the task named ``in_file``, and either a single anonymous output or an output
named ``out_file``, and both are format classes, then no arguments need to be passed
to the converter decorator and the conversion source and target formats are determined
automatically. For example,

.. code-block:: python

    from pathlib import Path
    import tempfile
    import pydra.mark
    from fileformats.core import converter
    from .mypackage import MyFormat, MyOtherFormat


    @converter
    @pydra.mark.task
    def convert_my_format(in_file: MyFormat, conversion_argument: int = 2) -> MyOtherFormat:
        data = in_file.load()
        output_path = Path(tempfile.mkdtemp()) / ("out" + MyOtherFormat.ext)
        ... do conversion ...
        return MyOtherFormat.save_new(output_path, data)

defines a converter between ``MyFormat`` and ``MyOtherFormat``, with the converter
argument ``conversion_argument``.

The ``@converter`` decorator registers the class in a class attribute of the target class,
therefore only if module containing the converter methods is imported will the converters
be available. Converter arguments can be passed as keyword-arguments to the
``get_converter`` and ``convert`` methods if required.

Sometimes the source and target formats cannot be automatically determined from the
task signature, and need to be provided as arguments to the ``@converter`` decorator
instead. For example, the converter between raster images using the ``imageio`` package
to do a generic conversion between all image types,

.. code-block:: python

    from pathlib import Path
    import tempfile
    import pydra.mark
    from fileformats.core import converter
    from .raster import RasterImage, Bitmap, Gif, Jpeg, Png, Tiff


    @converter(target_format=Bitmap, output_format=Bitmap)
    @converter(target_format=Gif, output_format=Gif)
    @converter(target_format=Jpeg, output_format=Jpeg)
    @converter(target_format=Png, output_format=Png)
    @converter(target_format=Tiff, output_format=Tiff)
    @python.define(outputs=["out_file"])
    def convert_image(in_file: RasterImage, output_format: type, out_dir: Path | None = None) -> RasterImage:
        data_array = in_file.load()
        if out_dir is None:
            out_dir = Path(tempfile.mkdtemp())
        output_path = out_dir / (in_file.fspath.stem + output_format.ext)
        return output_format.save_new(output_path, data_array)

In this case because we can write the converter in a generic way that allows us to convert
between any image type supported by ``imageio``, we use the ``RasterImage`` base class
for the input and output format, and explicitly set the ``target_format`` of the output
for each of the support output formats. We also pass ``output_format`` as a keyword argument
from the converter decorator to specify the format we want to convert to.

Note that while the ``source_format`` can be a base class of the format to be converted,
the ``target_format`` can't be, since the subclass my have specific characteristics not
captured by transformation to the base class. However, you can attempt to "cast" a
base class to a sub-class simply by providing the base class as an input, since it will
simply iterate over paths in the base class and attempt to validate them.

.. code-block:: python

    >>> sub_format = SubFormat(BaseFormat.convert(another_format))

Shell commands are marked as converters in the same way as function tasks, and existing
ShellCommandTask classes can be registered by calling the converter method on the ShellCommandTask
directly. If required, you can also map the input and output files to ``in_file`` and
``out_file`` via the converter decorator for any converter task and set appropriate
input fields

.. code-block:: python

    from fileformats.yourpackage import YourFormat, YourOtherFormat
    from pydra.tasks.thirdparty import ThirdPartyShellCmd

    converter(
        source_format=YourFormat,
        target_format=YourOtherFormat,
        in_file=your_file,
        out_file=other_file,
        compression="y",
    )(ThirdPartyShellCmd)

If you need to map any of the converter arguments or perform more complex logic, it is
also possible to decorate a generic function that returns an instantiated Pydra_ task,
such as in the ``mrconvert`` converter in the ``fileformats-medimage`` package.

.. code-block:: python

    @converter(source_format=MedicalImage, target_format=Analyze, out_ext=Analyze.ext)
    @converter(
        source_format=MedicalImage, target_format=MrtrixImage, out_ext=MrtrixImage.ext
    )
    @converter(
        source_format=MedicalImage,
        target_format=MrtrixImageHeader,
        out_ext=MrtrixImageHeader.ext,
    )
    def mrconvert(name, out_ext: str):
        """Initiate an MRConvert task with the output file extension set

        Parameters
        ----------
        name : str
            name of the converter task
        out_ext : str
            extension of the output file, used by MRConvert to determine the desired format

        Returns
        -------
        pydra.ShellCommandTask
            the converter task
        """
        return pydra_mrtrix3_utils.MRConvert(name=name, out_file="out" + out_ext)


Since converter tasks rely on Pydra_, which should be added as an "extended" dependency,
they are not loaded by default. However, if there is a package at
``fileformats.<namespace>.converters``, it will be attempted to be imported and throw
a warning if the import fails, when get_converter is called on a format in that
namespace.


.. warning::
    If the converters aren't imported successfully, then you will receive a
    ``FormatConversionError`` error saying there are no converters between FormatA and
    FormatB.


.. _`IANA Media Types`: https://www.iana_mime.org/assignments/media-types/media-types.xhtml
.. _Pydra: https://pydra.readthedocs.io
