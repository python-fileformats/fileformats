Typing
======

As formats are represented by classes, *FileFormats* provides a way to specify fine-grain
type annotations for Python functions and workflows that operate on files. To augment this
functionality, FileFormats also provides a number of special datatype classes that can
be used interchangeably with file formats, and the ability to "classify" fileformat types
to specify the data expected to be contained within them. In some cases, classifiers are
used as part of the validation process, in others they are just annotations.

Classifiers
-----------

Classifiable FileFormats classes (i.e. those that inherit the :class:`.WithClassifiers`
mixin), can be classified using the ``[]`` class operator. For example, a zip file can
be classified as containing a PNG image

.. code-block:: python

    >>> from fileformats.application import Zip
    >>> from fileformats.image import Png, Jpeg

    >>> zipped_png_fspath = str(Zip.convert(Png("/path/to/an-image.png")))
    >>> Zip[Png].matches(zipped_png_fspath)
    True
    >>> Zip[Jpeg].matches(zipped_png_fspath)
    False

.. warning::
    Classifiers are currently not supported by Mypy and other
    static type checkers (only dynamic type-checking in Pydra_) because they use a
    custom `__subclasshook__` method to implement the subclassing behaviour and overload
    the `__class_getitem__` method. It is hoped that it will be possible to implement
    a custom Mypy plugin in the future to support this feature.

The types of classes that can be used to classify varies from type to type. For archive
types like :class:`.Zip`, :class:`.Gzip`, take another file format type, others specific
classifier types. Some classifiable types can take multiple classifiers, whereas others can
take one, and the the multiple classifiers can either be ordered or not. In the case of
:class:`.MedicalImage` subclasses, multiple unordered classifiers based on the
`Radlex radiology lexicon <https://radlex.org/>`__ can be used to annotate the contents of
the images

.. code-block:: python

    from fileformats.medimage import NiftiGz, T1Weighted, Brain

    def brain_mask(image: NiftiGz[Brain, T1Weighted]) -> NiftiGz[Brain, Mask]:
        ...

.. note::
    At the time of writing, only a subset of the RadLex lexicon has been implemented.
    It is being expanded as needed.

When classifiable types are converted into MIME-like strings, the classifiers are prepended to
the type name with a '+' separator, e.g.


.. code-block:: python

    to_mime(Zip[Png], official=False) == "image/png+zip"


If there are multiple classifiers, then they are arranged in alphabetic order (unless
they are ordered) and separated by '..' preceding the '+' separator

.. code-block:: python

    to_mime(NiftiGz[T1Weighted, Brain], official=False) == "medimage/brain..t1-weighted+nifti-gz"

Classifiers that are themselves classified types are enclosed in square brackets, and
can be nested to any depth

.. code-block:: python

    to_mime(Zip[Json[InformalSchema]], official=False) == "application/[informal-schema+json]+zip"
    to_mime(Zip[Zip[Json[InformalSchema]]], official=False) == "application/[[informal-schema+json]+zip]+zip"

Typically the classifier types belong to the same subpackage/registry as the
main type, but special classes such as :class:`.application.Zip` and :class:`.application.Gzip`,
can be classified by any file format type. Classifiers from other subpackages/registries
are enclosed in square brackets along with their own namespace, e.g.

.. code-block:: python

    to_mime(Array[TestField], official=False) == "field/[testing/test-field]+array"

All of these forms are converted back into the classified types by ``from_mime``. Other special classifiable types are the
:class:`.generic.DirectoryOf` and :class:`.generic.SetOf` collection types. These can
be used to specify that a "file format" contains a collection of file formats within a
directory or independent files, respectively.

.. code-block:: python

    from fileformats.image import Jpeg, Png
    from fileformats.generic import DirectoryOf, SetOf

    def list_pngs(directory: DirectoryOf[Jpeg]) -> SetOf[Png]:
        return SetOf[Png](Png.convert(j) for j in directory.contents)


Non-file "fields"
-----------------

There are some use cases where input data can contain a mix of file-based and field data.
Therefore, while not file formats, for convenience *FileFormats* also provides
some field datatypes that can be used interchangeably with file format types for some
use cases, particularly MIME type.

* :class:`.field.Integer`
* :class:`.field.Decimal`
* :class:`.field.Boolean`
* :class:`.field.Text`
* :class:`.field.Array`

A common feature they share is the ability to convert them to/from mime-like (see :ref:`Informal ("MIME-like")`)
strings, e.g. ``to_mime(Integer) == "field/integer"``.


The can be converted to and from their corresponding "primitive types", i.e. ``int``,
``float``, ``bool``, ``str`` and ``list``, either by the object inits

.. code-block:: python

    >>> from fileformats.field import Integer
    >>> my_integer = Integer(1)
    >>> int(my_integer)
    1

or the :meth:`.Field.to_primitive` and :meth:`.Field.from_primitive` methods


.. code-block:: python

    >>> from fileformats.field import Field
    >>> field = Field.from_primitive(1)
    >>> repr(field)
    Integer(1)
    >>> field.to_primitive()
    1


The items contained within an :class:`.Array` class can be specified using the square
brackets operator

.. code-block:: python

    from fileformats.field import Array, Integer, Text, Boolean

    def my_func(int_array: Array[Integer], text_array: Array[Text]) -> Array[Boolean]:
        ...

This will validate the type of data contained within can be converted into the specified
item type

.. code-block:: python

    from fileformats.field import Array, Integer

    int_array = Array[Integer]([1, 2, 3])  # PASSES
    bad_int_array = Array[Integer]([1, 2, 3.5])  # FAILS!


Subclass hooks
--------------

Classified types implement the :meth:`.WithClassifiers.__subclasshook__` method, to control
the behaviour of the :func:`isinstance` and :func:`issubclass` functions when they are
passed as arguments. Classified types are considered to be subclasses of the
classifiable type.

.. code-block:: python

    from fileformats.application import Zip
    from fileformats.image import Png

    assert issubclass(Zip[Png], Zip)
    assert isinstance(Zip[Png]("/path/to/zip.zip"), Zip)

Similarly, for types with multiple unordered classifiers, a type with a superset of the
classifiers of another type is a subclass

.. code-block:: python

    from fileformats.medimage import NiftiGz, T1Weighted, Brain

    assert issubclass(NiftiGz[T1Weighted, Brain], NiftiGz[T1Weighted])

This is also the case if the classifiers of the superset type are subclasses of the
classifiers in the subset

.. code-block:: python

    from fileformats.medimage import NiftiGz, T1Weighted, Brain, Mri

    assert issubclass(T1Weighted, Mri)
    assert issubclass(NiftiGz[T1Weighted, Brain], NiftiGz[Mri])

or if the classifiable type itself is a subclass

.. code-block:: python

    from fileformats.medimage import NiftiGz, NiftiGzX, T1Weighted, Brain, Mri

    assert issubclass(NiftiGzX, NiftiGz)
    assert issubclass(NiftiGzX[T1Weighted, Brain], NiftiGz[T1Weighted, Brain])

For ordered classifiers, the classifiers must be in the same order to be considered
a subclass

.. code-block:: python

    from fileformats.testing import R, A, B, C, E

    assert issubclass(E, C)
    assert issubclass(R[A, B, E], R[A, B, C])

.. _Pydra: https://pydra.readthedocs.io
