
Read, write and convert
=======================

In addition to the basic features of validation and path handling, it is possible to
implement methods to interact with the data of file format objects via "extras hooks".
Such features are added to selected format classes on a needs basis (pull requests
welcome 😊, see :ref:`Extras`), so are by no means comprehensive, and
are provided "as-is".

Since these features typically rely on a range of external libraries, they are kept in
separate *extras* packages (e.g.
`fileformats-extras <https://pypi.org/project/fileformats-extras/>`__,
`fileformats-medimage-extras <https://pypi.org/project/fileformats-medimage-extras/>`__),
which need to be installed separately.


Metadata
--------

If there has been an extras overload registered for the ``read_metadata`` method,
then metadata associated with the fileset can be accessed via the ``metadata`` property,
e.g.

.. code-block:: python

    >>> dicom.metadata["SeriesDescription"]
    "localizer"

Formats the ``WithSeparateHeader`` and ``WithSideCars`` mixin classes will attempt the
side car if a metadata reader is implemented (e.g. JSON) and merge that with any header
information read from the primary file.


Reading and writing
-------------------

Formats that have a natural in-memory representation can be read into and written from
Python objects with the ``load`` and ``save`` methods. These are extras hooks, so the
implementations live in the extras packages rather than the format classes, and you
will need to install the extras package for the format (see `Supported formats`_),
otherwise you will get an error saying there is no implementation for the format.

Loading
~~~~~~~

``load`` reads the contents of the file-set into an object of a type that makes sense
for the format, e.g. a dictionary for JSON or a ``pydicom.FileDataset`` for DICOM

.. code-block:: python

    >>> from fileformats.application import Json
    >>> Json("/path/to/file.json").load()
    {'a': 1}

Any keyword arguments are passed on to the underlying reader (e.g. ``json.load``).

Since ``load`` is defined on the format classes, objects can be duck-typed in calling
functions/methods. For example, both ``Yaml`` and ``Json`` load to the same types, so a
function can accept either

.. code-block:: python

    from fileformats.application import Json, Yaml
    from fileformats.application.serialization import SerializationType

    def read_serialisation(serialized: Json | Yaml) -> SerializationType:
        return serialized.load()

Saving
~~~~~~

``save`` overwrites the contents of an existing file-set with new data, while the ``new``
classmethod creates a new file-set at the given path from the data

.. code-block:: python

    >>> json_file = Json.new("/path/to/new.json", {"a": 1})
    >>> json_file.save([1, 2, 3])
    >>> json_file.load()
    [1, 2, 3]

As with ``load``, any keyword arguments are passed on to the underlying writer (e.g.
``json.dump``).

Loaded types
~~~~~~~~~~~~

The type of the object returned by ``load``, and accepted by ``save`` and ``new``, is
given by the ``loaded_type`` class attribute of the format. Data passed to ``save`` (or
``new``) is checked against it, as is the data returned by the ``load`` implementations,
and a ``TypeError`` is raised if it doesn't match, e.g.

.. code-block:: python

    >>> Json.loaded_type
    dict[str, typing.Any] | list[typing.Any] | str | int | float | bool | None
    >>> Json.new("/path/to/file.json", {1, 2})
    TypeError: Expected data loaded from Json (dict | list | str | int | float | bool | NoneType), got set

Types from optional dependencies are given as dotted-path strings (e.g.
``"pydicom.FileDataset"``) so the format classes don't depend on them.

Supported formats
~~~~~~~~~~~~~~~~~

The following formats (and their subclasses) currently implement ``load`` and ``save``
in the `fileformats-extras <https://pypi.org/project/fileformats-extras/>`__ package.
The optional dependencies needed are installed with the extra given in brackets, e.g.
``pip install fileformats-extras[application]``.

.. list-table::
    :header-rows: 1

    * - Format
      - Loaded type
      - Install
    * - ``fileformats.application.Json``, ``fileformats.application.Yaml``
      - ``dict | list | str | int | float | bool | None``
      - ``fileformats-extras[application]``
    * - ``fileformats.application.Dicom``
      - ``pydicom.FileDataset``
      - ``fileformats-extras[application]``
    * - ``fileformats.image.RasterImage`` (e.g. ``Png``, ``Jpeg``, ``Gif``, ``Bitmap``, ``Tiff``)
      - ``numpy.ndarray``
      - ``fileformats-extras[image]``
    * - ``fileformats.text.Plain`` (e.g. ``TextFile``)
      - ``str``
      - ``fileformats-extras``
    * - ``fileformats.vendor.openxmlformats_officedocument.application.Wordprocessingml_Document``
      - ``docx.document.Document``
      - ``fileformats-extras[vnd_openxmlformats]``

Other extension packages (e.g. ``fileformats-medimage-extras``) implement ``load`` and
``save`` for their own formats. Pull requests adding implementations for other formats
are welcome (see :ref:`Extras`).

Loaded data
~~~~~~~~~~~

Functions that take data loaded from a file format, rather than the file itself, can
annotate it with ``Loaded[<format>]``. At runtime this evaluates to
``Annotated[<format>.loaded_type, LoadedMarker(<format>)]``, so it is equivalent to the
loaded type for anything that ignores the ``Annotated`` metadata (static type checkers
treat it as ``Any``), while tools that inspect signatures can recover the format the
data should be loaded from

.. code-block:: python

    import inspect
    from fileformats.core import Loaded, LoadedMarker
    from fileformats.application import Yaml

    def deidentify(spec: Loaded[Yaml]) -> None:
        ...

    hint = inspect.signature(deidentify, eval_str=True).parameters["spec"].annotation
    spec_format = LoadedMarker.from_hint(hint).format  # -> Yaml
    spec = spec_format("/path/to/spec.yaml").load()

Note that the ``Annotated`` metadata is stripped unless the hints are retrieved with
``typing.get_type_hints(..., include_extras=True)`` or
``inspect.signature(..., eval_str=True)``.


Converters
----------

Several conversion methods are available between equivalent file-formats in the standard
classes. For example, archive types such as ``Zip`` can be converted into and generic
file/directories using the ``convert`` classmethod of the target format to convert to

.. code-block:: python

    from fileformats.application import Zip
    from fileformats.generic import Directory

    # Example round trip from directory to zip file
    zip_file = Zip.convert(Directory("/path/to/a/directory"))
    extracted = Directory.convert(zip_file)

The converters are implemented in the Pydra_ dataflow framework, and can be linked into
wider Pydra_ workflows by accessing the underlying converter task with the ``get_converter``
classmethod

.. code-block:: python

    import pydra
    from pydra.tasks.mypackage import MyTask
    from fileformats.image import Gif, Png

    wf = pydra.Workflow(name="a_workflow", input_spec=["in_gif"])
    wf.add(
        Png.get_converter(Gif, name="gif2png", in_file=wf.lzin.in_gif)
    )
    wf.add(
        MyTask(
            name="my_task",
            in_file=wf.gif2png.lzout.out_file,
        )
    )
    ...



.. _Pydra: https://pydra.readthedocs.io
.. _Analyze: https://en.wikipedia.org/wiki/Analyze_(imaging_software)
