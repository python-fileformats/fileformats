.. _home:

FileFormats
===========
.. image:: https://github.com/python-fileformats/fileformats/actions/workflows/ci-cd.yml/badge.svg
   :target: https://github.com/python-fileformats/fileformats/actions/workflows/ci-cd.yml
.. image:: https://codecov.io/gh/python-fileformats/fileformats/branch/main/graph/badge.svg?token=UIS0OGPST7
   :target: https://codecov.io/gh/python-fileformats/fileformats
.. image:: https://img.shields.io/pypi/pyversions/fileformats.svg
   :target: https://pypi.python.org/pypi/fileformats/
   :alt: Supported Python versions
.. image:: https://img.shields.io/pypi/v/fileformats.svg
   :target: https://pypi.python.org/pypi/fileformats/
   :alt: Latest Version
.. image:: https://img.shields.io/github/stars/python-fileformats/fileformats?label=GitHub
   :alt: GitHub stars
   :target: https://github.com/python-fileformats/fileformats


*Fileformats* is a Python library for file-type detection/validation, MIME-type lookup and file handling.
It contains a collection format classes that each correspond to a different file formats.
The format classes also provide hooks for methods to read and manipulate the data contained in the files to
facilitate the writing of duck-typed code. Unlike other Python packages, multi-file data
formats, e.g. with separate header/data files or directories containing specific files,
are supported, and can be handled just like single file types.

File-format types are typically identified by a combination of file extensions
and "magic numbers", where applicable. In these cases new formats can be defined in just
a few lines. However, for more exotic file formats like
`MRtrix Image Header <https://mrtrix.readthedocs.io/en/dev/getting_started/image_data.html#mrtrix-image-formats>`__,
which requires inspection of headers to locate other members of the "file set",
*FileFormats* provides a framework to add custom detection methods.

Extensions and Extras
---------------------

The main *FileFormats* package covers all file-types with registered MIME types (see
`IANA MIME-types`_). Additional, domain-specific formats can be added via *FileFormats* **extension**
framework, such as `fileformats-medimage <https://pypi.org/project/fileformats-medimage>`__
for medical imaging data, and `fileformats-datascience <https://pypi.org/project/fileformats-datascience>`__
for formats commonly found in datascience. These extension packages are understandably
not comprehensive, but expected to grow as new use cases are found and new formats added
(see :ref:`Extensions`).

The main *FileFormats* and its extension packages don't have any external dependencies.
Extra functionality that requires external dependencies, such as libraries to read and
write the file data, are implemented in separate **extras** packages (see :ref:`Extras`),
e.g. `fileformats-extras <https://pypi.org/project/fileformats-extras/>`__,
`fileformats-medimage-extras <https://pypi.org/project/fileformats-medimage-extras/>`__),
to keep the base packages for format detection and file handling extremely
light-weight.


Installation
------------

*FileFormats* can be installed for Python >=3.8 using *pip*

.. code-block:: console

    $ python3 -m pip install fileformats

Extension packages can be installed similarly

.. code-block:: bash

    $ python3 -m pip install fileformats-medimage fileformats-datascience

These installations have no dependencies and provide basic format detection and
file handling functionality. However, for metadata inspection and format conversion methods
that require external dependencies, you will need install the ``fileformats-extras`` package.

.. code-block:: console

    $ python3 -m pip install fileformats-extras


and likewise for the extension packages

.. code-block:: bash

    $ python3 -m pip install fileformats-medimage-extras fileformats-datascience-extras

.. note::
   See the :ref:`Extensions` and :ref:`Extras` for instructions on how to implement your
   own extensions and extras, respectively.


License
-------

This work is licensed under a
`Creative Commons Attribution 4.0 International License <http://creativecommons.org/licenses/by/4.0/>`_

.. image:: https://i.creativecommons.org/l/by/4.0/88x31.png
  :target: http://creativecommons.org/licenses/by/4.0/
  :alt: Creative Commons Attribution 4.0 International License


.. toctree::
    :maxdepth: 2
    :hidden:

    quick_start
    detection
    file_handling
    mime
    read_write
    typing
    api

.. toctree::
   :maxdepth: 2
   :caption: Available Types
   :hidden:

   reference/application
   reference/audio
   reference/image
   reference/model
   reference/text
   reference/video
   reference/datascience
   reference/medimage

.. toctree::
   :maxdepth: 2
   :caption: Developer Guide
   :hidden:

   developer/extensions
   developer/extras


.. _Pydra: https://pydra.readthedocs.io
.. _Fastr: https://gitlab.com/radiology/infrastructure/fastr
.. _`IANA MIME-types`: https://www.iana.org/assignments/media-types/media-types.xhtml
