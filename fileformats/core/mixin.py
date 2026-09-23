import io
import logging
import re
import typing as ty
from pathlib import Path

import fileformats.core

from .classifier import Classifier
from .converter_helpers import Converter, SubtypeVar
from .datatype import DataType
from .decorators import classproperty, validated_property
from .exceptions import (
    FileFormatsExtrasError,
    FormatDefinitionError,
    FormatMismatchError,
    FormatRecognitionError,
)
from .identification import to_mime_format_name
from .utils import get_optional_type

logger = logging.getLogger("fileformats")

T = ty.TypeVar("T")


class WithMagicNumber:
    """Mixin class for Files with magic numbers at the start of their
    contents.

    Class Attrs
    -----------
    magic_number : str or bytes
        the magic number/string to search for at the start of the file. If a unicode
        string then it is interpreted as the byte code in hex, if a bytes object, then
        it is treated as the byte string directly.
    binary : bool
        if the file-format is a binary type then this flag needs to be set in order to
        read the contents properly
    magic_number_offset : int, optional
        the offset in bytes from the start of the file that the magic number is stored
    """

    magic_number_offset = 0
    binary: bool
    magic_number: ty.Union[str, bytes]

    def _validate_magic_number(
            self,
            fh: io.IOBase,
            magic_number: ty.Union[str, bytes],
            magic_number_offset: int = 0,
            binary: bool = True
    ) -> None:
        if binary and isinstance(magic_number, str):
            try:
                magic_bytes = bytes.fromhex(magic_number)
            except ValueError:
                raise FormatDefinitionError(
                    f"Magic number of file {type(self)} is not a valid hex string"
                )
        else:
            assert isinstance(magic_number, bytes)
            magic_bytes = magic_number

        if magic_number_offset:
            fh.seek(magic_number_offset, (io.SEEK_SET if magic_number_offset >= 0 else io.SEEK_END))
        size = len(magic_bytes)
        read_magic_number = fh.read(size) if size else fh.read()

        if read_magic_number != magic_bytes:
            read_magic: ty.Union[str, bytes]
            ref_magic: ty.Union[str, bytes]
            if binary and isinstance(magic_number, str):
                read_magic = '"' + bytes.hex(read_magic_number) + '"'
                ref_magic = '"' + magic_number + '"'
            else:
                read_magic = read_magic_number
                assert isinstance(magic_number, bytes)
                ref_magic = magic_number
            raise FormatMismatchError(
                f"Magic number of file {read_magic!r} doesn't match expected "
                f"{ref_magic!r}"
            )

    @validated_property
    def _check_magic_number(self) -> None:
        with self.open("rb" if getattr(self, "binary", True) else "r") as fh:
            self._validate_magic_number(
                fh=fh,
                magic_number=self.magic_number,
                binary=getattr(self, "binary", True),
                magic_number_offset=self.magic_number_offset,
            )


class WithMagicVersion:
    """Mixin class for Files with version numbers embedded within "magic numbers"
    the start of their contents.

    Class Attrs
    -----------
    magic_pattern : bytes
        the magic number/string to search for at the start of the file
    magic_pattern_offset : int, optional
        the offset in bytes from the start of the file that the magic pattern is read from
    magic_pattern_maxlength : int, optional
        the maximum length of the pattern, i.e. the length of the byte-string that will
        be read from the file, by default it will be the length of the magic_pattern
        string (which will probably be longer than the string it matches due to the
        special characters in the regex)
    """

    binary: bool
    magic_pattern: bytes
    magic_pattern_offset = 0
    magic_pattern_maxlength: ty.Optional[int] = None

    @validated_property
    def version(self) -> ty.Union[str, ty.Tuple[str, ...]]:
        read_length = (
            self.magic_pattern_maxlength
            if self.magic_pattern_maxlength
            else len(self.magic_pattern)
        )
        read_bytes = self.read_contents(read_length, offset=self.magic_pattern_offset)  # type: ignore[attr-defined]
        match = re.match(self.magic_pattern, read_bytes)
        if not match:
            raise FormatMismatchError(
                f"Byte-string of length {read_length} at {self.magic_pattern_offset} "
                f"({read_bytes!r}), doesn't match expected pattern, {self.magic_pattern!r}"
            )
        version: ty.Tuple[str, ...] = tuple(b.decode("utf-8") for b in match.groups())
        if not version:
            raise FormatDefinitionError(
                f"No version patterns found in magic pattern of {type(self).__name__} "
                f"class, {self.magic_pattern!r}"
            )
        if len(version) == 1:
            return version[0]
        return version


class WithAdjacentFiles:
    """
    If only the main fspath is provided to the __init__ of the class, this mixin
    automatically includes any "adjacent files", i.e. any files with the same stem but
    different extensions

    Note that WithAdjacentFiles must come before the primary type in the method-resolution
    order of the class so it can override the '_additional_paths' method in

        class MyFileFormatWithSeparateHeader(WithSeparateHeader, MyFileFormat):

            header_type = MyHeaderType
    """

    fspaths: ty.FrozenSet[Path]

    def _additional_fspaths(self) -> None:
        if len(self.fspaths) == 1:
            self.fspaths |= self.get_adjacent_files()
            trim = True
        else:
            trim = False
        if trim:
            self.trim_paths()  # type: ignore[attr-defined]

    def get_adjacent_files(self) -> ty.Set[Path]:
        stem = self.stem  # type: ignore[attr-defined]
        adjacents = set()
        for sibling in self.fspath.parent.iterdir():  # type: ignore[attr-defined]
            if (
                sibling != self.fspath  # type: ignore[attr-defined]
                and sibling.is_file()
                and sibling.name.startswith(stem + ".")
            ):
                adjacents.add(sibling)
        return adjacents


class WithSeparateHeader(WithAdjacentFiles):
    """Mixin class for Files with metadata stored in separate header files (typically
    with the same file stem but differing extension)

    Note that WithSeparateHeader must come before the primary type in the method-resolution
    order of the class

        class MyFileFormatWithSeparateHeader(WithSeparateHeader, MyFileFormat):

            header_type = MyHeaderType

    Class Attrs
    -----------
    header_type : type
        the file-format of the header file
    """

    header_type: ty.Type["fileformats.core.FileSet"]

    @classproperty  # type: ignore[arg-type]
    def nested_types(cls) -> ty.Tuple[ty.Type[Classifier], ...]:
        return (cls.header_type,)

    @validated_property
    def header(self) -> "fileformats.core.FileSet":
        return self.header_type(self.select_by_ext(self.header_type))  # type: ignore[attr-defined]

    def read_metadata(self, **kwargs: ty.Any) -> ty.Mapping[str, ty.Any]:
        header: ty.Dict[str, ty.Any] = self.header.load()
        return header


class WithSideCars(WithAdjacentFiles):
    """Mixin class for Files with a "side-car" file that augments the inline metadata
    (typically with the same file stem but differing extension).

    Note that WithSideCars must come before the primary type in the method-resolution
    order of the class methods, e.g.

        class MyFileFormatWithSideCars(WithSideCars, MyFileFormat):

            primary_type = MyFileFormat
            side_car_types = (MySideCarType,)

    Class Attrs
    -----------
    primary_type : type
        the file-format of the primary file (used to read the inline metadata), can be
        the base class that implements 'read_metadata'
    side_car_types : tuple[type, ...]
        the file-formats of the expected side-car files
    """

    primary_type: ty.Type["fileformats.core.FileSet"]
    side_car_types: ty.Tuple[ty.Type["fileformats.core.FileSet"], ...]

    @validated_property
    def side_cars(self) -> ty.Tuple["fileformats.core.FileSet", ...]:
        return tuple(tp(self.select_by_ext(tp)) for tp in self.side_car_types)  # type: ignore[attr-defined]

    def read_metadata(self, **kwargs: ty.Any) -> ty.Mapping[str, ty.Any]:
        try:
            metadata: ty.Dict[str, ty.Any] = dict(self.primary_type.read_metadata(self, **kwargs))  # type: ignore[arg-type]
        except FileFormatsExtrasError:
            metadata = {}
        for side_car in self.side_cars:
            try:
                side_car_metadata: ty.Dict[str, ty.Any] = side_car.load()
            except AttributeError:
                continue
            if not isinstance(side_car_metadata, dict):
                raise TypeError(
                    f"`load` method of side-car type {type(side_car)} must return a "
                    f"dictionary, not {type(side_car_metadata)!r}"
                )
            side_car_class_name: str = to_mime_format_name(type(side_car).__name__)
            metadata[side_car_class_name] = side_car_metadata
        return metadata

    @classproperty  # type: ignore[arg-type]
    def nested_types(cls) -> ty.Tuple[ty.Type[Classifier], ...]:
        return cls.side_car_types


class WithClassifiers:
    """Mixin class for adding the ability to qualify the format class to designate the
    type of information stored within the format, e.g. ``DirectoryOf[Png, Gif]`` for a
    directory containing PNG and GIF files, ``Zip[DataFile]`` for a zipped data file,
    ``Array[Integer]`` for an array containing integers, or DicomDir[T1w, Brain] for a
    T1-weighted MRI scan of the brain in DICOM format.

        class MyFormatWithClassifiers(WithClassifiers, BinaryFile):

            ext = ".myf


        def my_func(file: MyFormatWithClassifiers[Integer]):
            ...

    A unique class will be returned (i.e. multiple calls with the same arguments will
    return the same class)

    Class Attrs
    -----------
    classifiers_attr_name : str, optional
        an attribute name to store the classifiers at within the classified class. This
        should be used if you need to reference the ``classifiers`` attribute directly
        in any validation/other methods (i.e. in most cases), to handle the case of
        diamond inheritance between two classes that can be classified.
        A default value should also be set in the unclassified base for this attribute,
        which is either ``()`` if ``multiple_classifiers`` is true and ``None`` otherwise
    <classifiers-attr-name> : tuple[type, ...] or None, optional
        pass a default value to the attribute referenced by 'classifiers_attr_name'
    allowed_classifiers : tuple[type,...], optional
        the allowable types (+ subclasses) for the content types. If None all types
        are allowed
    multiple_classifiers: bool, optional
        whether multiple classifiers can be provided (true) or just a single classifier (false)
    allow_optional_classifiers: bool, optional
        whether Optional classifiers are allowed in the classifier set. Optional classifiers are
        classifiers that are wrapped in typing.Optional[], indicating that the classifier
        may or may not be present in the format
    exclusive_classifiers: tuple[ty.Type[Classifier], ...], optional
        a set of classifiers that are exclusive, i.e. only one classifier from each
        by default empty.
    ordered_classifiers: bool, optional
        whether the order of the classifiers matters (true) or not (false). If false,
    genericly_classified: bool, optional
        whether the class can be classified by classifiers in any namespace (true) or just the
        namespace it belongs to (false). If true, then the namespace of the genericly
        classified class is omitted from the "mime-like" string. Note that the
        class' name therefore needs to be globally unique amongst all other genericly
        classified classes and so it should be used sparingly, i.e., highly generic
        formats that are unambiguous across all namespaces, such as "directory", "zip",
        "gzip", "json", "yaml", etc...
    """

    # classifiers set in the current class
    classifiers: ty.Tuple[ty.Type[DataType], ...] = ()
    _classified_subtypes: ty.Dict[
        ty.Tuple[ty.Type[Classifier], ...], ty.Type[DataType]
    ] = {}
    # dict of previously created classified subtypes. If an existing class with matching
    # classifiers has been created it is returned instead of creating a new type. This
    # ensures that ``assert MyFormat[Qualifier] is MyFormat[Qualifier]``

    # Default values for class attrs
    multiple_classifiers = True
    allowed_classifiers: ty.Optional[ty.Tuple[ty.Type[Classifier], ...]] = None
    allow_optional_classifiers = False
    exclusive_classifiers: ty.Tuple[ty.Type[Classifier], ...] = ()
    ordered_classifiers = False
    generically_classifiable = False

    def _validate_class(self) -> ty.Union[bool, None]:
        validated: ty.Union[bool, None] = super()._validate_class()  # type: ignore
        if validated is None:
            if self.wildcard_classifiers():
                raise FormatDefinitionError(
                    f"Can instantiate {type(self)} class as it has wildcard classifiers "
                    "and therefore should only be used for converter specifications"
                )
        return validated

    @classproperty  # type: ignore[arg-type]
    def is_classified(cls) -> bool:
        return "unclassified" in cls.__dict__

    @classproperty  # type: ignore[arg-type]
    def nested_types(cls) -> ty.Tuple[ty.Type[Classifier], ...]:
        return cls.classifiers

    @classmethod
    def wildcard_classifiers(
        cls, classifiers: ty.Optional[ty.Sequence[ty.Type[Classifier]]] = None
    ) -> ty.FrozenSet[ty.Type[SubtypeVar]]:
        if classifiers is None:
            classifiers = cls.classifiers if cls.is_classified else ()
        return frozenset(
            t for t in classifiers if issubclass(get_optional_type(t), SubtypeVar)  # type: ignore[misc]
        )

    @classmethod
    def non_wildcard_classifiers(
        cls, classifiers: ty.Optional[ty.Collection[ty.Type[Classifier]]] = None
    ) -> ty.FrozenSet[ty.Type[Classifier]]:
        if classifiers is None:
            classifiers = cls.classifiers if cls.is_classified else ()
        assert classifiers is not None
        return frozenset(
            q for q in classifiers if not issubclass(get_optional_type(q), SubtypeVar)
        )

    @classmethod
    def __class_getitem__(
        cls,
        classifiers: ty.Union[ty.Collection[ty.Type[Classifier]], ty.Type[Classifier]],
    ) -> ty.Type[DataType]:
        """Set the content types for a newly created dynamically type"""
        if isinstance(classifiers, ty.Iterable):
            classifiers_tuple = tuple(classifiers)
        else:
            classifiers_tuple = (classifiers,)
        classifiers_to_check = tuple(
            get_optional_type(c, cls.allow_optional_classifiers)
            for c in classifiers_tuple
        )

        if cls.allowed_classifiers:
            not_allowed = [
                q
                for q in classifiers_to_check
                if not any(issubclass(q, t) for t in cls.allowed_classifiers)
            ]
            if not_allowed:
                raise FormatDefinitionError(
                    f"Invalid content types provided to {cls} (must be subclasses of "
                    f"{cls.allowed_classifiers}): {not_allowed}"
                )
        # Sort content types if order isn't important
        if cls.multiple_classifiers:
            if not cls.ordered_classifiers:
                # Check for duplicate classifiers in the multiple list
                if len(classifiers_to_check) > 1:
                    # Sort the classifiers into categories and ensure that there aren't more
                    # than one type for each category. Otherwise, if the classifier doesn't
                    # belong to a category, check to see that there aren't multiple sub-classes
                    # in the classifier set
                    repetitions: ty.Dict[
                        ty.Type[Classifier], ty.List[ty.Type[Classifier]]
                    ] = {
                        c: [] for c in cls.exclusive_classifiers + classifiers_to_check
                    }
                    for classifier in classifiers_to_check:
                        for exc_classifier in repetitions:
                            if issubclass(
                                origin_type(classifier), origin_type(exc_classifier)
                            ):
                                repetitions[exc_classifier].append(classifier)
                    repeated = [t for t in repetitions.items() if len(t[1]) > 1]
                    if repeated:
                        raise FormatDefinitionError(
                            "Cannot have more than one occurrence of a classifier "
                            f"or subclasses for {cls} class when "
                            f"{cls.__name__}.ordered_classifiers is false:\n"
                            + "\n".join(
                                f"{k!r}: " + ", ".join(repr(x) for x in v)
                                for k, v in repeated
                            )
                        )
                classifiers_tuple = tuple(
                    sorted(
                        set(classifiers_tuple),
                        key=lambda x: get_optional_type(x).__name__,
                    )
                )
        else:
            if len(classifiers_tuple) > 1:
                raise FormatDefinitionError(
                    f"Multiple classifiers not permitted for {cls} types, provided: "
                    f"({classifiers_tuple})"
                )
        # Make sure that the "classified" dictionary is present in this class not super
        # classes
        if "_classified_subtypes" not in cls.__dict__:
            cls._classified_subtypes = {}
        try:
            # Load previously created type so we can do ``assert MyType[Integer] is MyType[Integer]``
            classified = cls._classified_subtypes[classifiers_tuple]
        except KeyError:
            if not hasattr(cls, "classifiers_attr_name"):
                raise FormatDefinitionError(
                    f"{cls} needs to define the 'classifiers_attr_name' class attribute "
                    "with the name of the (different) class attribute to hold the "
                    "classified types"
                )
            if cls.classifiers_attr_name is None:
                raise FormatDefinitionError(
                    f"Inherited classifiers have been disabled in {cls} (by setting "
                    f'"classifiers_attr_name)" to None)'
                )
            try:
                classifiers_attr = getattr(cls, cls.classifiers_attr_name)
            except AttributeError:
                raise FormatDefinitionError(
                    f"Default value for classifiers attribute "
                    f"'{cls.classifiers_attr_name}' needs to be set in {cls}"
                )
            else:
                if classifiers_attr:
                    raise FormatDefinitionError(
                        f"Default value for classifiers attribute "
                        f"'{cls.classifiers_attr_name}' needs to be set in {cls}"
                    )
            class_attrs = {
                "unclassified": cls,
                "classifiers": classifiers_tuple,
            }
            class_attrs[cls.classifiers_attr_name] = (
                classifiers_tuple if cls.multiple_classifiers else classifiers_tuple[0]
            )
            classifier_names = [
                get_optional_type(t).__name__ for t in classifiers_tuple
            ]
            if not cls.ordered_classifiers:
                classifier_names.sort()
            classified = type(
                f"{'__'.join(classifier_names)}___{cls.__name__}",
                (cls,),
                class_attrs,
            )
            classified.__module__ = cls.__module__
            cls._classified_subtypes[classifiers_tuple] = classified
        return classified

    @classmethod
    def get_converter_defs(cls, source_format: type) -> ty.List[Converter]:
        """Search the registered converters to find an appropriate task and associated
        key-word args to perform the conversion between source and target formats

        Parameters
        ----------
        source_format : type(FileSet)
            the source format to convert from
        """
        from fileformats.core import FileSet

        # Try to see if a converter has been defined to the exact type
        available_converters: ty.List[Converter] = super().get_converter_defs(  # type: ignore[misc, type-arg]
            source_format
        )
        # Failing that, see if there is a generic conversion between the container type
        # the source format (or subclass of) defined with matching wildcards in the source
        # and target formats
        if not available_converters and cls.is_classified:
            converters_dict = FileSet.get_converters_dict(
                cls.unclassified  # type: ignore[attr-defined]
            )  # pylint: disable=no-member
            for template_source_format, converter in converters_dict.items():
                if converter.classifiers:  # was defined with wildcard classifiers
                    # Attempt conversion from generic type to template match
                    if issubclass(template_source_format, SubtypeVar):
                        assert tuple(
                            cls.wildcard_classifiers(converter.classifiers)
                        ) == (template_source_format,)
                        non_wildcards = cls.non_wildcard_classifiers(
                            converter.classifiers
                        )
                        to_match = tuple(set(cls.classifiers).difference(non_wildcards))
                        if len(to_match) > 1:
                            wildcard_match = False
                        else:
                            wildcard_match = issubclass(source_format, to_match[0])
                    # Attempt template to template conversion match
                    elif getattr(source_format, "is_classified", False) and issubclass(
                        source_format.unclassified, template_source_format.unclassified  # type: ignore[attr-defined]
                    ):
                        assert cls.wildcard_classifiers(
                            converter.classifiers
                        ) == cls.wildcard_classifiers(
                            template_source_format.classifiers  # type: ignore[attr-defined]
                        )
                        if cls.ordered_classifiers:
                            if len(cls.classifiers) != len(
                                converter.classifiers
                            ) or len(
                                source_format.classifiers  # type: ignore[attr-defined]
                            ) != len(
                                template_source_format.classifiers  # type: ignore[attr-defined]
                            ):
                                wildcard_match = False
                            else:
                                wildcard_map = {}
                                for actual, template in zip(
                                    source_format.classifiers,  # type: ignore[attr-defined]
                                    template_source_format.classifiers,  # type: ignore[attr-defined]
                                ):
                                    if issubclass(template, SubtypeVar):
                                        wildcard_map[template] = actual
                                wildcard_match = True
                                for actual, template in zip(
                                    cls.classifiers, converter.classifiers
                                ):
                                    if issubclass(template, SubtypeVar):
                                        try:
                                            reference = wildcard_map[template]
                                        except KeyError:
                                            wildcard_match = False
                                            break
                                        else:
                                            if not issubclass(actual, reference):
                                                wildcard_match = False
                                                break
                                    elif not issubclass(actual, template):
                                        wildcard_match = False
                                        break
                        else:
                            non_wildcards = cls.non_wildcard_classifiers(
                                converter.classifiers
                            )
                            src_non_wildcards = cls.non_wildcard_classifiers(
                                template_source_format.classifiers  # type: ignore[attr-defined]
                            )
                            if not non_wildcards.issubset(
                                set(cls.classifiers)
                            ) or not src_non_wildcards.issubset(
                                set(source_format.classifiers)  # type: ignore[attr-defined]
                            ):
                                wildcard_match = False
                            else:
                                to_match = set(cls.classifiers).difference(
                                    non_wildcards
                                )
                                from_types = set(source_format.classifiers).difference(  # type: ignore[attr-defined]
                                    src_non_wildcards
                                )
                                wildcard_match = to_match.issubset(from_types)
                    else:
                        wildcard_match = False
                    if wildcard_match:
                        available_converters.append(converter)
        return available_converters

    @classmethod
    def __subclasshook__(cls, subclass: type) -> bool:
        """Overload the behaviour of 'issubclass' so that classified classes are considered
        to be subclasses of each other if they contain a super-set of classifiers"""
        if type.__subclasscheck__(cls, subclass):
            return True
        # Check to see whether the unclassified types are equivalent
        if (
            not cls.is_classified
            or not getattr(subclass, "is_classified", False)
            or not issubclass(subclass.unclassified, cls.unclassified)  # type: ignore[attr-defined]
        ):
            return False
        if cls.ordered_classifiers:
            assert subclass.ordered_classifiers  # type: ignore[attr-defined]
            if len(subclass.classifiers) != len(cls.classifiers):  # type: ignore[attr-defined]
                is_subclass = False
            else:
                is_subclass = all(
                    issubclass(q, s)
                    for q, s in zip(subclass.classifiers, cls.classifiers)  # type: ignore[attr-defined]
                )
        else:
            assert not subclass.ordered_classifiers  # type: ignore[attr-defined]
            if set(subclass.classifiers).issuperset(cls.classifiers):  # type: ignore[attr-defined]
                is_subclass = True
            else:
                # Check for sub-classes of classifiers
                is_subclass = all(
                    any(issubclass(q, s) for q in subclass.classifiers)  # type: ignore[attr-defined]
                    for s in cls.classifiers
                )
        return is_subclass

    @classmethod
    def register_converter(
        cls,
        source_format: ty.Type["fileformats.core.FileSet"],
        converter: Converter,
    ) -> None:
        """Registers a converter task within a class attribute. Called by the @fileformats.converter
        decorator.

        Parameters
        ----------
        source_format : type
            the source format to register a converter from
        converter_spec
            a tuple consisting of a `task_spec` callable that resolves to a Pydra task
            and a dictionary of keyword arguments to be passed to the task spec at
            initialisation time

        Raises
        ------
        FormatConversionError
            if there is already a converter registered between the two types
        """
        # Ensure "converters" dict is defined in the target class and not in a superclass
        if cls.wildcard_classifiers():
            if issubclass(source_format, SubtypeVar):
                if len(cls.wildcard_classifiers()) > 1:
                    raise FormatDefinitionError(
                        "Can only have one wildcard qualifier when registering a converter "
                        f"to {cls} from a generic type, found {cls.wildcard_classifiers()}"
                    )
            elif not source_format.is_classified:  # type: ignore[attr-defined]
                raise FormatDefinitionError(
                    "Can only use wildcard classifiers when registering a converter "
                    f"from a generic type or similarly classified type, not {source_format}"
                )
            else:
                source_wildcard_classifiers = source_format.wildcard_classifiers()  # type: ignore[attr-defined]
                if cls.wildcard_classifiers() != source_wildcard_classifiers:
                    raise FormatDefinitionError(
                        f"Mismatching wildcards between source format, {source_format} "
                        f"({list(source_wildcard_classifiers)}), and target "
                        f"{cls} ({cls.wildcard_classifiers()})"
                    )
                prev_registered = [
                    f
                    for f in cls.converters  # type: ignore[attr-defined]
                    if (
                        issubclass(source_format.unclassified, f.unclassified)  # type: ignore[attr-defined]
                        and f.non_wildcard_classifiers()
                        == source_format.non_wildcard_classifiers()  # type: ignore[attr-defined]
                    )
                ]
                assert len(prev_registered) <= 1
                prev = prev_registered[0] if prev_registered else None
                if prev:
                    prev_converter = cls.converters[prev]  # type: ignore[attr-defined]
                    # task, task_kwargs = converter_spec
                    # prev_task, prev_kwargs, prev_classifiers = prev_tuple
                    if converter == prev_converter:
                        logger.warning(
                            "Ignoring duplicate registrations of the same converter %s",
                            converter.task,
                        )
                        return  # actually the same task but just imported twice for some reason
                    prev_unclassified = prev.unclassified
                    unclassified = cls.unclassified  # type: ignore[attr-defined]
                    raise FormatDefinitionError(
                        f"Cannot register converter from {prev_unclassified} "
                        f"to {unclassified} with non-wildcard classifiers "
                        f"{list(prev.non_wildcard_classifiers())}, {converter.task}, "
                        f"because there is already one registered, {prev_converter.task}"
                    )
            converters_dict = cls.unclassified.get_converters_dict()  # type: ignore[attr-defined]
            converter.classifiers = cls.classifiers
            converters_dict[source_format] = converter
        else:
            super().register_converter(source_format, converter)  # type: ignore[misc]

    @classproperty  # type: ignore[arg-type]
    def namespace(cls) -> ty.Optional[str]:
        """The "namespace" the format belongs to under the "fileformats" umbrella
        namespace"""
        namespace: ty.Optional[str]
        if cls.is_classified:
            namespaces: ty.Collection[str] = set(
                t.namespace for t in cls.classifiers if t.namespace
            )
            if not cls.generically_classifiable:
                namespaces.add(cls.unclassified.namespace)  # type: ignore[attr-defined]
            if len(namespaces) == 1:
                return next(iter(namespaces))
            else:
                # Handle subpackage namespaces and parent, e.g. medimage & medimage-fsl
                namespaces = sorted(namespaces)
                if (
                    len(namespaces) == 2
                    and namespaces[1].split("-")[0] == namespaces[0]
                ):
                    return namespaces[1]
                msg = (
                    "Cannot create reversible MIME type for because did not find a "
                    f"common namespace between all classifiers {list(cls.classifiers)}"
                )
                if not cls.generically_classifiable:
                    msg += f" and (non genericly classified) base class {cls.unclassified}"  # type: ignore[attr-defined]
                raise FormatRecognitionError(msg + f", found:\n{list(namespaces)}")
        else:
            try:
                namespace = super().namespace  # type: ignore[misc]
            except AttributeError:
                namespace = None
        return namespace

    @classproperty
    def vendor(cls) -> ty.Optional[str]:
        """The "vendor" the format belongs to under the "fileformats" umbrella
        namespace"""
        vendor: ty.Optional[str]
        if cls.is_classified:
            vendors: ty.Collection[str] = set(
                t.vendor for t in cls.classifiers if t.vendor
            )
            if cls.unclassified.vendor:  # type: ignore[attr-defined]
                vendors.add(cls.unclassified.vendor)  # type: ignore[attr-defined]
            if not vendors:
                return None
            if len(vendors) == 1:
                return next(iter(vendors))
            msg = (
                "Cannot create reversible MIME type for because did not find a "
                f"common vendor between all classifiers {list(cls.classifiers)}"
            )
            raise FormatRecognitionError(msg + f", found:\n{list(vendors)}")
        else:
            vendor = super().vendor  # type: ignore[misc]
        return vendor

    @classproperty  # type: ignore[arg-type]
    def type_name(cls) -> str:
        """Name of type including classifiers to be used in __repr__"""
        unclassified: str
        if not cls.is_classified:
            return cls.__name__  # type: ignore[no-any-return, attr-defined]
        unclassified = cls.unclassified.__name__  # type: ignore[attr-defined]
        return (
            unclassified + "[" + ", ".join(t.type_name for t in cls.classifiers) + "]"
        )


class WithClassifier(WithClassifiers):

    multiple_classifiers = False


class WithOrderedClassifiers(WithClassifiers):

    ordered_classifiers = True


def origin_type(tp: type) -> type:
    """Get the origin type of a possibly generic type"""
    origin: ty.Optional[type] = ty.get_origin(tp)
    if origin is None:
        return tp
    return origin  # type: ignore[no-any-return]
