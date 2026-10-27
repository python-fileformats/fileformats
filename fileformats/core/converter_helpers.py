import logging
import typing as ty
from abc import ABCMeta

from .classifier import Classifier
from .datatype import DataType
from .exceptions import FormatDefinitionError

if ty.TYPE_CHECKING:
    from pydra.compose.base import Task

    import fileformats.core

    from . import mixin

logger = logging.getLogger("fileformats")

T = ty.TypeVar("T")
DT = ty.TypeVar("DT", bound=DataType)


class SubtypeVar:
    """To handle the case where the target format is a placeholder (type-var) defined by
    by its relationship to the source format, e.g.

    AnyFileFormat = FileSet.type_var("AnyFileFormat")

    @converter
    @python.define  # type: ignore[untyped-decorator]
    def unzip(in_file: Zip[AnyFileFormat], out_file: AnyFileFormat):
        ...
    """

    converters: ty.Dict[ty.Type["fileformats.core.FileSet"], "Converter"] = {}

    @classmethod
    def new(cls, name: str, klass: type) -> "SubtypeVar":
        """Create a new subtype

        Parameters
        ----------
        name : str
            name for the subtype
        klass : ty.Type[DataType]
            the class to sub-type

        Returns
        -------
        SubtypeVar
            a sub-type that is
        """
        return ABCMeta(name, (cls, klass), {"bound": klass})  # type: ignore

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        if issubclass(subclass, SubtypeVar):
            return issubclass(subclass.bound, cls.bound)  # type: ignore
        return type.__subclasscheck__(cls, subclass)

    @classmethod
    def get_converter_defs(
        cls, source_format: ty.Type["mixin.WithClassifiers"], target_format: type
    ) -> ty.List["Converter"]:
        # check to see whether there are converters from a base class of the source
        # format
        available_converters: ty.List[Converter] = []
        # assert isinstance(source_format, WithClassifiers)
        if source_format.is_classified:
            for template_source_format, converter in cls.converters.items():
                if not issubclass(
                    template_source_format.unclassified, source_format.unclassified  # type: ignore
                ):
                    continue
                assert len(template_source_format.wildcard_classifiers()) == 1  # type: ignore
                non_wildcards = template_source_format.non_wildcard_classifiers()  # type: ignore
                if not non_wildcards.issubset(source_format.classifiers):
                    continue
                from_types = tuple(
                    set(source_format.classifiers).difference(non_wildcards)
                )
                if any(issubclass(q, target_format) for q in from_types):
                    available_converters.append(converter)
        return available_converters

    @classmethod
    def register_converter(
        cls,
        source_format: ty.Type["mixin.WithClassifiers"],
        converter: "Converter",
    ) -> None:
        """Registers a converter task within a class attribute. Called by the
        @fileformats.core.converter decorator.

        Parameters
        ----------
        source_format : type
            the source format to register a converter from
        converter : Converter
            The converter object to register

        Raises
        ------
        FormatConversionError
            if there is already a converter registered between the two types
        """
        # Ensure "converters" dict is defined in the target class and not in a superclass
        if len(source_format.wildcard_classifiers()) > 1:
            raise FormatDefinitionError(
                "Cannot register a conversion to a generic type from a type with more "
                f"than one wildcard {source_format} ({list(source_format.wildcard_classifiers())})"
            )
        prev_registered = [
            f
            for f in cls.converters
            if (
                f.unclassified is source_format.unclassified  # type: ignore
                and f.non_wildcard_classifiers()  # type: ignore
                == source_format.non_wildcard_classifiers()
            )
        ]
        assert len(prev_registered) <= 1
        if prev_registered:
            prev_def = cls.converters[prev_registered[0]]
            # task, task_kwargs, _ = converter_spec
            # prev_task, prev_kwargs = prev_tuple
            if converter.task == prev_def.task:
                logger.warning(
                    "Ignoring duplicate registrations of the same converter %s",
                    converter.task,
                )
                return  # actually the same task but just imported twice for some reason
            generic_type = tuple(prev_def.task.wildcard_classifiers())[0]  # type: ignore
            raise FormatDefinitionError(
                f"Cannot register converter from {source_format} to the generic type "
                f"'{generic_type}', {converter.task} "
                f"because there is already one registered, {prev_def.task}"
            )

        cls.converters[source_format] = converter  # type: ignore


class Converter:
    """Specification of a converter task, including the task callable, its arguments and
    the classifiers"""

    task: "Task[ty.Any]"
    classifiers: ty.Tuple[ty.Type[Classifier], ...]
    in_file: str
    out_file: str

    def __init__(
        self,
        task: "Task[T]",
        classifiers: ty.Tuple[ty.Type[Classifier], ...] = (),
        in_file: str = "in_file",
        out_file: str = "out_file",
    ):
        self.task = task
        self.classifiers = classifiers
        self.in_file = in_file
        self.out_file = out_file

    @property
    def is_chain(self) -> bool:
        """Whether the converter chains other converters together to convert via
        intermediate formats"""
        return (
            type(self.task).__name__ == "ConverterChain"
            and type(self.task).__module__ == "fileformats.core.converter_chain"
        )

    def __eq__(self, other: object) -> bool:
        from pydra.utils.hash import hash_function

        return (
            isinstance(other, Converter)
            and self.task == other.task
            and hash_function(self.classifiers) == hash_function(other.classifiers)
            and self.in_file == other.in_file
            and self.out_file == other.out_file
        )
