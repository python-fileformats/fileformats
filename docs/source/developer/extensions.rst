Extensions
==========

*FileFormats* has been designed so that file-formats specified by standard features,
such as file extension and magic number can be implemented in a few lines, while
still being flexible enough handle any weird whacky file formats used in obscure domains.

Format classes not covered by `IANA Media Types`_ should be implemented in a separate
*FileFormats* extension packages. New extension packages can be conveniently created from
the FileFormats extension template, `<https://github.com/python-fileformats/fileformats-medimage>`_,
including CI/CD workflows.

Extension packages add a new unique format namespace under the ``fileformats`` namespace package.
For example, the `FileFormats Medimage Extension <https://github.com/python-fileformats/fileformats-medimage>`__
implements a range of file formats used in medical imaging research under the
``fileformats.medimage`` namespace.

Extension packages shouldn't have any external dependencies (i.e. except the base `fileformats`
package). Additional functionality that requires external dependencies should be implemented in a
"extras" package (see :ref:`Extras`).


Basic formats
-------------

In the simplest case of a file format identified by its extension alone, you only need
to inherit from the ``fileformats.generic.File`` class and set the ``ext`` attr, e.g

.. code-block:: python

    from fileformats.generic import File

    class MyFileFormat(File):
        ext = ".my"


Likewise if the format you are defining is a directory containing one or more files of
a given type you can just inherit from the ``fileformats.generic.Directory`` class and
set the ``content_types`` attributes

.. code-block:: python

    from fileformats.generic import Directory
    from fileformats.text import Markdown, Html


    class MyDirFormat(File):
        content_types = (Markdown, Html)


Standard mixins
---------------

If the format is a binary file with a magic number (identifying byte string at start of
file), you can use the ``fileformats.core.mixin.WithMagicNumber`` mixin. For files with
magic numbers you will also need to set the ``binary`` attr to True.

.. code-block:: python

    from fileformats.generic import File
    from fileformats.core.mixin import WithMagicNumber


    class MyBinaryFormat1(WithMagicNumber, File):
        ext = ".myb1"
        binary = True
        magic_number = "98E3F12200AA"  # Unicode strings are interpreted as hex


    class MyBinaryFormat2(WithMagicNumber, File):
        ext = ".myb2"
        binary = True
        magic_number = b"MYB2"  # Byte strings are not converted


Formats will contain metadata in a separate header file can be defined using
the :class:`.WithSeparateHeader` mixin.

.. code-block:: python

   from fileformats.generic import File
   from fileformats.core.mixin import WithSeparateHeader


    class MyHeaderFormat(File):
        ext = ".hdr"

        def load(self):
            return dict(ln.split(":") for ln in self.raw_contents.splitlines())

    class MyFormatWithHeader(WithSeparateHeader, File):
        ext = ".myh"
        header_type = MyHeaderFormat


The header file can be accessed from an instantiated file object via the ``header``
property. If the header format implements the ``load`` method, then it is assumed to
return a dictionary containing metadata for the file-set.

.. code-block:: python

    >>> my_file = MyFormatWithHeader("/path/to/a/file.myh")
    >>> my_file.header
    MyHeaderFormat(fspaths={"/path/to/a/file.hdr"})
    >>> my_file.metadata["experiment-id"]  # load experiment ID from header file
    '0001'


Similar to :class:`.WithSeparateHeader`, :class:`.WithSideCars` can be used to define a format that
contains some metadata within the main file, and additional metadata in a separate
"side-car" file. It can be used the same as :class:`.WithSeparateHeader`, however, the
type of the primary file that reads the metadata from the binary file with ``read_metadata()``
must also be defined in ``primary_type``


.. warning::

   Mixin classes in the ``fileformats.core.mixin`` package must come first in the
   method resolution order of the types bases, so that they can override methods in
   ``FileSet`` if need be.


Mixin classes
~~~~~~~~~~~~~

.. autoclass:: fileformats.core.mixin.WithMagicNumber

.. autoclass:: fileformats.core.mixin.WithMagicVersion

.. autoclass:: fileformats.core.mixin.WithAdjacentFiles

.. autoclass:: fileformats.core.mixin.WithSeparateHeader

.. autoclass:: fileformats.core.mixin.WithSideCars

.. autoclass:: fileformats.core.mixin.WithClassifiers



Custom format patterns
----------------------

While the standard mixin classes should cover the large majority standard formats, in
the wild-west of science data formats you are likely to need to design custom validators
for your format. This is done by adding a property to the class using the
`fileformats.core.validated_property` decorator. Validated properties should check the
validity of an aspect of the file, and raise a `FormatMismatchError` if the file does
not match the expected pattern.

To detect the presence of associated files, you can use the `select_by_ext` method of
the file object, which selects a single file from a list of file paths that matches
given extension, raising a FormatMismatchError if either no files or multiple files are found.

Take for example the `GIS shapefile structure <https://www.earthdatascience.org/courses/earth-analytics/spatial-data-r/shapefile-structure/>`_,
it is a file-set consisting of 3 to 6 files differentiated by their extensions. To
implement this class we use the ``@validated_property`` decorator. We inherit from the :class:`.WithAdjacentFiles`
mixin so that neighbouring files (i.e. files with the same stem but different extension)
are included when the class is instantiated with just the primary ".shp" file.

.. code-block:: python

    from fileformats.generic import File
    from fileformats.application import Xml
    from fileformats.mixin import WithAdjacentFiles
    from fileformats.core import mark, validated_property

    class GisShapeIndex(File):
        "the file that indexes the geometry."
        ext = ".shx"


    class GisShapeFeatures(File):
        "the file that stores feature attributes in a tabular format"
        ext = ".dbf"


    class WellKnownText(File):
        """the file that contains information on projection format including the
        coordinate system and projection information. It is a plain text file
        describing the projection using well-known text (WKT) format."""
        ext = ".prj"


    class GisShapeSpatialIndexN(File):
        "the files that are a spatial index of the features."
        ext = ".shn"


    class GisShapeSpatialIndexB(File):
        "the files that are a spatial index of the features."
        ext = ".shb"


    class GisShapeGeoSpatialMetadata(Xml):
        "the file that is the geospatial metadata in XML format"
        ext = ".shp.xml"


    class GisShape(WithAdjacentFiles, File):

        ext = ".shp"  # the main file that will be mapped to fspath

        @validated_property
        def index_file(self):
            return GisShapeIndex(self.select_by_ext(GisShapeIndex))

        @validated_property
        def features_file(self):
            return GisShapeFeatures(self.select_by_ext(GisShapeFeatures))

        @validated_property
        def project_file(self):
            return WellKnownText(self.select_by_ext(WellKnownText), allow_none=True)

        @validated_property
        def spatial_index_n_file(self):
            return GisShapeSpatialIndexN(
               self.select_by_ext(GisShapeSpatialIndexN), allow_none=True
            )

        @validated_property
        def spatial_index_n_file(self):
            return GisShapeSpatialIndexB(
               self.select_by_ext(GisShapeSpatialIndexB), allow_none=True
            )

        @validated_property
        def geospatial_metadata_file(self):
            return GisShapeGeoSpatialMetadata(
               self.select_by_ext(GisShapeGeoSpatialMetadata), allow_none=True
            )

Properties that appear in ``fspaths`` attribute of the object are considered to be
"required paths", and are copied along side the main path in the ``copy_to`` method
even when the ``trim`` argument is set to True.

After the required properties have been deeper checks can be by using the ``check``
decorator. Take the :class:`fileformats.image.Tiff` class

.. code-block:: python


    class Tiff(RasterImage):

       ext = ".tiff"
       iana_mime = "image/tiff"

       magic_number_le = "49492A00"
       magic_number_be = "4D4D002A"

       @property
       def endianness(self):
          read_magic = self.read_contents(len(self.magic_number_le) // 2)
          if read_magic == bytes.fromhex(self.magic_number_le):
                endianness = "little"
          elif read_magic == bytes.fromhex(self.magic_number_be):
                endianness = "big"
          else:
                read_magic_str = bytes.hex(read_magic)
                raise FormatMismatchError(
                   f"Magic number of file '{read_magic_str}' doesn't match either the "
                   f"little-endian '{self.magic_number_le}' and big-endian "
                   f"'{self.magic_number_be}'"
                )
          return endianness

The :class:`.Tiff` format class needs to check two different magic numbers, one for big endian
files and another one for little endian files. Therefore we can't just use the
:class:`.WithMagicNumber` mixin and have to roll our own.


.. _`IANA Media Types`: https://www.iana_mime.org/assignments/media-types/media-types.xhtml
.. _Pydra: https://pydra.readthedocs.io
