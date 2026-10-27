MIME types
==========

In addition to simply importing and using a format class in your Python code, format classes
can be loaded from their `MIME type`_ or `MIME-like` type strings. This can be useful for
dynamically loading formats based on user input, or for identifying the format of a file
based on its MIME type.


Official
--------

Namespaces in the main ``fileformats`` package are named after MIME type registries
as defined by the `Internet Assigned Numbering Authority (IANA) <https://www.iana_mime.org/assignments/media-types/media-types.xhtml>`__.
Format class can be converted to and from MIME type strings using the ``to_mime`` and
``from_mime`` functions. If the the ``iana_mime`` attribute
is present in the type class, it should correspond to a formally recognised MIME type
by the , e.g.

.. code-block:: python

    from fileformats.core import to_mime, from_mime
    from fileformats.application import MswordX

    Loaded = from_mime("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert Loaded is MswordX
    assert Loaded.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

Extension formats (see :ref:`Extensions and Extras`) that don't define an
``iana_mime`` attribute in their class dictionary will be assigned a
MIME-type of "application/x-<transformed-class-name>", where *transformed-class-name*
is the name of the format class converted from "PascalCase" to "kebab-case", with
single underscores in the class name converted to "." and double underscores
converted to "+", e.g.

.. code-block::

    >>> Nifti__Gzip_Json.mime_type
    "application/x-nifti+gzip.json"

Classified types are converted from their classifiers rather than their class name
(see :ref:`Classifiers`).

Note that if there are two file-formats with the same class name in different sub-packages
then the ``iana_mime`` attribute will need to be set on at least one of them otherwise an
error will be raised when they are loaded from a MIME type.

.. warning::
    Note that the installation of additional sub-packages may cause detection code to
    break if your code doesn't handle the potential of new formats being added with the same
    class name. Therefore, you may prefer to use "MIME-like" type strings (see below)
    unless IANA compliance is required.


Informal ("MIME-like")
----------------------

To avoid the issue of name clashes between formats in different extension packages
mapping onto the same MIME type it can be preferable when strict MIME-types are not
required to just use the *FileFormats* namespace inplace for the "registry" of the
file-type instead of the generic "application/x-" prefix (it also helps to improve
readability). This is dubbed the "MIME-like" string, and is accessed via the
``mime_like`` class-property.

.. code-block::

    >>> from fileformats.datascience import Hdf5
    >>> from fileformats.medimage import Nifti1
    >>> Hdf5.mime_like
    "datascience/hdf5"
    >>> Nifti1.mime_like
    "medimage/nifti1"

The ``from_mime`` function will resolve both official MIME-type and MIME-like
strings, so it is possible to roundtrip from both.

.. code-block:: python

    from fileformats.core import to_mime, from_mime
    from from fileformats.medimage import DicomSeries

    # Using official-style MIME string
    mime_type = DicomSeries.mime_type
    assert mime_type == "application/x-dicom-series"
    assert from_mime(mime_type) is DicomSeries

    # Using MIME-like string
    mimelike_type = DicomSeries.mime_like
    assert mimelike_type == "medimage/dicom-series"
    assert from_mime(mimelike_type) is DicomSeries


.. _`MIME type`: https://www.iana_mime.org/assignments/media-types/media-types.xhtml
