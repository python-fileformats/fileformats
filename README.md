# FileFormats

[![CI/CD](https://github.com/python-fileformats/fileformats/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/python-fileformats/fileformats/actions/workflows/ci-cd.yml)
[![Codecov](https://codecov.io/gh/python-fileformats/fileformats/branch/main/graph/badge.svg?token=UIS0OGPST7)](https://codecov.io/gh/python-fileformats/fileformats)
![Static Badge](https://img.shields.io/badge/type%20checked-mypy-039dfc)
[![Python Versions](https://img.shields.io/pypi/pyversions/fileformats.svg)](https://pypi.python.org/pypi/fileformats/)
[![Latest Version](https://img.shields.io/pypi/v/fileformats.svg)](https://pypi.python.org/pypi/fileformats/)
[![Documentation Status](https://img.shields.io/badge/docs-latest-brightgreen.svg?style=flat)](https://python-fileformats.github.io/fileformats/)

<img src="./docs/source/_static/images/logo_small.png" alt="Logo Small" style="float: right; width: 100mm">

*Fileformats* provides a library of file-format types implemented as Python classes for
validation, detection, typing and provide hooks for extra functionality and format
conversions. Formats are typically validated/identified by a combination of file extension
and "magic numbers" where applicable. Unlike other file-type packages, *FileFormats*,
supports multi-file data formats ("file sets"), which are often found in scientific
workflows, e.g. with separate header/data files.

*FileFormats* provides a flexible extension framework to add custom identification
routines for exotic file formats, e.g. formats that require inspection of headers to
locate data files, directories containing certain file types, or to peek at metadata
fields to define specific sub-types (e.g. functional MRI DICOM file set). These file-sets
with auxiliary files can be moved, copied and hashed like they are a single file object.

See the [extension template](https://github.com/python-fileformats/fileformats-extension-template)
for instructions on how to design *FileFormats* extensions modules to augment the
standard file-types implemented in the main repository with custom domain/vendor-specific
file-format types (e.g. [fileformats-medimage](https://pypi.org/project/fileformats-medimage/)).

## Notes on MIME-type coverage

Support for all non-vendor standard MIME types (i.e. ones not matching `*/vnd.*` or `*/x-*`) has been
added to *FileFormats* by semi-automatically scraping the
[IANA MIME types](https://www.iana_mime.org/assignments/media-types/media-types.xhtml) website for file
extensions and magic numbers. As such, many of the formats in the library have not been properly
tested on real data and so should be treated with some caution. If you encounter any issues with an implemented file
type, please raise an issue in the [GitHub tracker](https://github.com/python-fileformats/fileformats/issues).

A small selection of vendor-specific types can be found under `fileformats.vendor.*`. Support for additional vendor-specific
formats can be added via plugin (see the
[extension template](https://github.com/python-fileformats/fileformats-extension-template)).

## Installation

*FileFormats* can be installed for Python >= 3.8 from PyPI with

```console
    python3 -m pip fileformats
```

Implementations of methods and converters between select formats that require
external dependencies require the installation of the corresponding "extras" package e.g

```console
    python3 -m pip install fileformats-extras
```

Extension packages exist for for formats not covered by [IANA MIME types] (e.g. NIfTI, R-files, MATLAB files)
and can be installed along with their "extras" package similarly

```console
    $ python3 -m pip install \
      fileformats-medimage \
      fileformats-medimage-extras \
      fileformats-datascience \
      fileformats-datascience-extras
```

## Examples

Using the `WithMagicNumber` mixin class, the `Png` format can be defined concisely as

```python
from fileformats.generic import File
from fileformats.core.mixin import WithMagicNumber


class Png(WithMagicNumber, File):
    binary = True
    ext = ".png"
    iana_mime = "image/png"
    magic_number = b".PNG"
```

Files can then be checked to see whether they are of PNG format by

```python
    png = Png("/path/to/image/file.png")  # Checks the extension and magic number
```

which will raise a `FormatMismatchError` if initialisation or validation fails, or
for a boolean method that checks the validation use `matches`

```python
    if Png.matches(a_path_to_a_file):
        ... handle case ...
```

## Format Identification

There are 2 main functions that can be used for format identification

* `fileformats.core.from_mime`
* `fileformats.core.find_matching`

### `from_mime`

As the name suggests, this function is used to return the FileFormats class corresponding
to a given `MIME <https://www.iana.org/assignments/media-types/media-types.xhtml>`__ string.
All non-vendor official MIME-types are supported. Non-official types can be loaded using
the `application/x-name-of-type` form as long as the name of the type is unique amongst
all installed format types. To avoid name clashes between different extension types, the
"MIME-like" string can be used instead, where informal registries corresponding to the
fileformats extension namespace are used instead, e.g. `medimage/nifti-gz` or `datascience/hdf5`.

### `find_matching`

Given a set of file-system paths, by default, `find_matching` will iterate through all
installed fileformats classes and return all that validate successfully (formats without
any specific constraints are excluded by default). The potential candidate classes can be
restricted by using the `candidates` keyword argument.

## Format Conversion

While not implemented in the main File-formats itself, file-formats provides hooks for
other packages to implement extra behaviour such as format conversion.
The `fileformats-extras <https://github.com/python-fileformats/fileformats-extras>`__
implements a number of converters between standard file-format types, e.g. archive types
to/from generic file/directories, which if installed can be called using the `convert()` method.

```python
    from fileformats.application import Zip
    from fileformats.generic import Directory

    zip_file = Zip.convert(Directory("/path/to/a/directory"))
    extracted = Directory.convert(zip_file)
    copied = extracted.copy_to("/path/to/output")
```

The converters are implemented in the [Pydra](https://pydra.readthedocs.io) dataflow framework, and can be linked into
wider [Pydra](https://pydra.readthedocs.io) workflows by creating a converter task

```python
import pydra
from pydra.tasks.mypackage import MyTask
from fileformats.application import Json, Yaml

wf = pydra.Workflow(name="a_workflow", input_spec=["in_json"])
wf.add(Yaml.get_converter(Json, name="json2yaml", in_file=wf.lzin.in_json))
wf.add(
    MyTask(
        name="my_task",
        in_file=wf.json2yaml.lzout.out_file,
    )
)
...
```

Alternatively, the conversion can be executed outside of a [Pydra](https://pydra.readthedocs.io) workflow with

```python
    json_file = Json("/path/to/file.json")
    yaml_file = Yaml.convert(json_file)
```

## License

This work is licensed under a
[Creative Commons Attribution 4.0 International License](http://creativecommons.org/licenses/by/4.0/)

[![CC0](https://i.creativecommons.org/l/by/4.0/88x31.png)](http://creativecommons.org/licenses/by/4.0/)

## Acknowledgements

The authors acknowledge the facilities and scientific and technical assistance of the
National Imaging Facility, a National Collaborative Research Infrastructure Strategy (NCRIS) capability.
