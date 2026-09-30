API
===

Functions
~~~~~~~~~

There are four main functions that are used to return the file formats from string and
path inputs.

.. autofunction:: fileformats.core.to_mime

.. autofunction:: fileformats.core.from_mime

.. autofunction:: fileformats.core.find_matching

.. autofunction:: fileformats.core.from_paths


Base Classes
~~~~~~~~~~~~

Base classes form the foundation of the fileformats package and are not intended to be
instantiated directly, but rather subclassed to create new file formats. The methods
and properties of these classes are described here.

.. autoclass:: fileformats.core.Classifier
    :members: namespace, type_name

.. autoclass:: fileformats.core.DataType
    :members: all_types, get_converter, matches, mime_type, mime_like, subclasses,

.. autoclass:: fileformats.core.FileSet
    :members: mime_type, mime_like, from_mime, strext, unconstrained, possible_exts, metadata, select_by_ext, matching_exts, convert, get_converter, register_converter, all_formats, standard_formats, hash, hash_files, mock, sample, decomposed_fspaths, from_paths, copy, move

.. autoclass:: fileformats.core.Field
    :members: mime_like, from_mime, to_primitive, from_primitive


Loaded-data annotations
~~~~~~~~~~~~~~~~~~~~~~~

Annotations for data loaded from a file format (see :ref:`Loaded data`)

.. autoclass:: fileformats.core.Loaded

.. autoclass:: fileformats.core.LoadedMarker
    :members: from_hint, accepts

.. autofunction:: fileformats.core.check_loaded


Extra hooks
~~~~~~~~~~~

Decorators for defining and implementing extra hooks (see :ref:`Extras`)

.. autofunction:: fileformats.core.extra

.. autofunction:: fileformats.core.extra_implementation

.. autofunction:: fileformats.core.find_extra_implementation


Generic Classes
~~~~~~~~~~~~~~~

Generic classes representing files and directories can be used as base classes for
specific file formats, as well as in cases where the format of the file is not known
and only general properties are required.

:class:`FsObject` exposes of the properties and methods of the :class:`pathlib.Path` class,
where applicable so it and all subclasses should be able to be duck-typed in place of a
:class:`pathlib.Path` object in most cases.

.. autoclass:: fileformats.generic.FsObject
    :members: __fspath__, __str__, fspath, stem, unconstrained, absolute, anchor, chmod, drive, exists, group, is_dir, is_file, name, owner, parent, parents, parts, root, stat, suffix, suffixes

.. autoclass:: fileformats.generic.File
    :members: open, contents, read_contents, actual_ext, stem, read_bytes

.. autoclass:: fileformats.generic.BinaryFile
    :members: open, read_contents

.. autoclass:: fileformats.generic.UnicodeFile
    :members: open, read_contents, read_text

.. autoclass:: fileformats.generic.Directory
    :members: __div__, fspath, contents, glob, rglob, joinpath, iterdir

.. autoclass:: fileformats.generic.TypedSet
    :members: contents

DirectoryOf and SetOf allow the dynamic creation of classes that represent directories
and sets of files that contain specific file formats.

.. autoclass:: fileformats.generic.DirectoryOf

.. autoclass:: fileformats.generic.SetOf


Fields
------

Fields are used to define non-file data in a what that can be referred to interchangeably
with fileformats, in particular by their MIME-like type (see :ref:`Informal ("MIME-like")`),
which is under the `field` namespace, e.g. `field/integer` or `field/decimal+array`.

.. autoclass:: fileformats.field.Text

.. autoclass:: fileformats.field.Integer

.. autoclass:: fileformats.field.Decimal

.. autoclass:: fileformats.field.Boolean

.. autoclass:: fileformats.field.Array
