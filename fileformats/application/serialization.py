import json
import typing as ty
from pathlib import Path

from fileformats.core import (
    DataType,
    FileSet,
    SampleFileGenerator,
    extra_implementation,
)
from fileformats.core.exceptions import FormatMismatchError
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


# JSON only requires the standard library so doesn't need to be in the extras package


@extra_implementation(FileSet.generate_sample_data, overridable=True)
def generate_json_sample_data(
    js: Json,
    generator: SampleFileGenerator,
) -> ty.List[Path]:
    js_file = generator.generate_fspath(file_type=Json)
    with open(js_file, "w") as f:
        json.dump(
            {
                "a": True,
                "b": "two",
                "c": 3,
                "d": [generator.rng.randint(0, 10), generator.rng.random(), 6],
            },
            f,
        )
    return [js_file]


@extra_implementation(FileSet.load, overridable=True)
def load(jsn: Json, **kwargs: ty.Any) -> SerializationType:
    try:
        with jsn.open() as f:
            data: SerializationType = json.load(f, **kwargs)
    except json.JSONDecodeError as e:
        raise FormatMismatchError(f"'{jsn.fspath}' is not a valid JSON file") from e
    return data


@extra_implementation(FileSet.save, overridable=True)
def save(jsn: Json, data: SerializationType, **kwargs: ty.Any) -> None:
    with jsn.open("w") as f:
        json.dump(data, f, **kwargs)
