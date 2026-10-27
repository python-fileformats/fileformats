import typing as ty

from fileformats.core import DataType
from fileformats.core.mixin import WithClassifier
from fileformats.core.typing import TypeAlias
from fileformats.generic import UnicodeFile

# JSON/YAML documents can be a bare scalar as well as a mapping or sequence
SerializationType: TypeAlias = ty.Union[
    dict[str, ty.Any], list[ty.Any], str, int, float, bool, None
]


class Schema(DataType):
    """Base class for all serialization schemas (can be used for abstract schemas that
    don't actually have a formal definition)"""

    pass


class JsonSchema(Schema):
    pass


class XmlSchema(Schema):
    pass


class InformalSchema(Schema):
    "Not actually a strict schema, just a set of conventions on how to structure the serialization"


class TextSerialization(WithClassifier, UnicodeFile):
    "Base class for text-based hierarchical data-serialization formats, e.g. JSON, YAML"

    # Classifiers class attrs
    classifiers_attr_name: ty.Optional[str] = "schema"
    schema: ty.Optional[ty.Type[Schema]] = None
    allowed_classifiers: ty.Tuple[ty.Type[Schema], ...] = (Schema,)
    generically_classifiable: bool = True


class Xml(TextSerialization):
    ext: ty.Optional[str] = ".xml"
    allowed_classifiers = (XmlSchema, InformalSchema)


class Json(TextSerialization):
    ext: ty.Optional[str] = ".json"
    allowed_classifiers = (JsonSchema, InformalSchema)
    loaded_type = SerializationType

    # TODO: add validation mechanisms to check class


class Yaml(TextSerialization):
    ext = ".yaml"
    alternate_exts = (".yml",)
    loaded_type = SerializationType


class Toml(TextSerialization):
    ext = ".toml"
