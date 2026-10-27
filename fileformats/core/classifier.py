import typing as ty

from .decorators import classproperty
from .exceptions import FormatDefinitionError


class Classifier:
    """Base class for all file-format "classifiers", including datatypes and abstract
    types"""

    @classproperty  # type: ignore[arg-type]
    def type_name(cls) -> str:
        """Name of type to be used in __repr__. Defined here so it can be overridden"""
        return cls.__name__  # type: ignore

    @classproperty  # type: ignore[arg-type]
    def namespace(cls) -> ty.Optional[str]:
        """The "namespace" the format belongs to under the "fileformats" umbrella
        namespace"""
        module_parts = cls.__module__.split(".")
        if module_parts[0] != "fileformats":
            raise FormatDefinitionError(
                f"Cannot determine namespace for {cls} format as it is not in the "
                "fileformats namespace package"
            )
        namespace = module_parts[1]
        if namespace == "vendor":
            if len(module_parts) < 4:
                raise FormatDefinitionError(
                    f"Cannot determine namespace for vendor-specific format, {cls} it needs "
                    "to be in a subpackage of the form `fileformats.vendor.<vendor-name>.<namespace>`,"
                    f"found `{'.'.join(module_parts)}`"
                )
            namespace = module_parts[3]
        return namespace.replace("_", "-")

    @classproperty
    def vendor(cls) -> ty.Optional[str]:
        module_parts = cls.__module__.split(".")
        if module_parts[0] != "fileformats" or module_parts[1] != "vendor":
            return None
        return module_parts[2].replace("_", "-")

    @classmethod
    def _mime_format_name(
        cls, namespace: ty.Optional[str] = None, vendor: ty.Optional[str] = None
    ) -> str:
        """The format part of the MIME-like string of the class (i.e. after the "/").

        Parameters
        ----------
        namespace : str, optional
            the namespace of the MIME-like string the name is part of, which is used by
            classified types to determine whether their classifiers need to include
            their namespace (see `WithClassifiers._mime_format_name`)
        vendor : str, optional
            the vendor of the MIME-like string the name is part of
        """
        from .identification import to_mime_format_name

        return to_mime_format_name(cls.__name__)

    @classmethod
    def _resolvable_in(cls, namespace: str, vendor: ty.Optional[str]) -> bool:
        """Whether the class can be referred to by name alone within a MIME-like string
        of the given namespace and vendor, i.e. whether it will be found when the string
        is parsed by `DataType.from_mime` without its namespace being included"""
        if cls.namespace == namespace and cls.vendor == vendor:
            return True
        # Classes in the parent namespace (e.g. "medimage" for "medimage-fsl") are
        # also searched
        return (
            not cls.vendor
            and "-" in namespace
            and cls.namespace == namespace.split("-")[0]
        )

    def dummy(self) -> float:

        i: int = 0

        return i
