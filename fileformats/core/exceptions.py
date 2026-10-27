class FileFormatsError(Exception):
    "Base exception class"


class FormatDefinitionError(FileFormatsError):
    "When the file-formats class hasn't been properly defined"


class FormatMismatchError(TypeError, FileFormatsError):
    "Provided paths/values do not match the specified file format"


class UnsatisfiableCopyModeError(FileFormatsError):
    "Error copying files"


class FormatConversionError(FileFormatsError):
    "No converters exist between formats"


class FormatRecognitionError(KeyError, FileFormatsError):
    "Did not find a format class corresponding to a MIME, or MIME-like, type string"


class UnconstrainedExtensionException(FileFormatsError):
    "Did not find a format class corresponding to a MIME, or MIME-like, type string"


class FileFormatsExtrasError(FileFormatsError):
    """If there is an "extra" hook in the datatype class but no methods have been
    registered on it"""


class FileFormatsExtrasPkgUninstalledError(FileFormatsExtrasError):
    """If there is an "extra" hook in the datatype class and a extras package on PyPI
    but it hasn't been installed"""


class FileFormatsExtrasPkgNotCheckedError(FileFormatsExtrasError):
    """If there is an "extra" hook in the datatype class and a extras package on PyPI
    but it hasn't been installed"""


class FileFormatsClashingExtrasImplementationError(FileFormatsExtrasError):
    """If there is an "extra" hook in the datatype class but no methods have been
    registered on it"""


class FileFormatsExtrasNotImplementedError(FileFormatsExtrasError, NotImplementedError):
    """If there is an "extra" hook in the datatype class but no methods have been
    registered on it"""


class FileFormatsNotRelativePathError(FileFormatsError, ValueError):
    """If a relative path operation is attempted on a non-relative path"""
