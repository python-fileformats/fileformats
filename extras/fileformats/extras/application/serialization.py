import json
import tempfile
import typing as ty
from pathlib import Path

import yaml
from pydra.compose import python

from fileformats.application import Json, TextSerialization, Yaml
from fileformats.application.serialization import SerializationType
from fileformats.core import (
    FileSet,
    SampleFileGenerator,
    converter,
    extra_implementation,
)
from fileformats.core.exceptions import FormatMismatchError


@converter(target_format=Json, output_format=Json)  # type: ignore[untyped-decorator]
@converter(target_format=Yaml, output_format=Yaml)  # type: ignore[untyped-decorator]
@python.define(outputs={"out_file": TextSerialization})  # type: ignore[untyped-decorator]
def convert_data_serialization(
    in_file: TextSerialization,
    output_format: ty.Type[TextSerialization],
    out_dir: ty.Optional[Path] = None,
) -> TextSerialization:
    dct = in_file.load()
    if out_dir is None:
        out_dir = Path(tempfile.mkdtemp())
    output_path = out_dir / (
        in_file.fspath.stem + (output_format.ext if output_format.ext else "")
    )
    return output_format.new(output_path, dct)


@extra_implementation(FileSet.load)
def yaml_load(yml: Yaml, **kwargs: ty.Any) -> SerializationType:
    with open(yml.fspath) as f:
        data = yaml.load(f, Loader=yaml.Loader)
    return data  # type: ignore[no-any-return]


@extra_implementation(FileSet.save)
def yaml_save(
    yml: Yaml,
    data: SerializationType,
    **kwargs: ty.Any,
) -> None:
    with open(yml.fspath, "w") as f:
        yaml.dump(data, f, **kwargs)


@extra_implementation(FileSet.generate_sample_data)
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


@extra_implementation(FileSet.generate_sample_data)
def generate_yaml_sample_data(
    yml: Yaml,
    generator: SampleFileGenerator,
) -> ty.List[Path]:
    yml_file = generator.generate_fspath(file_type=Yaml)
    with open(yml_file, "w") as f:
        f.write(
            f"""# Generated sample YAML file by FileFormats
a: True
b: two
c: 3
d:
- {generator.rng.randint(0, 10)}
- {generator.rng.random()}
- 6
"""
        )
    return [yml_file]


@extra_implementation(FileSet.load)
def load(jsn: Json, **kwargs: ty.Any) -> SerializationType:
    try:
        with jsn.open() as f:
            data: SerializationType = json.load(f, **kwargs)
    except json.JSONDecodeError as e:
        raise FormatMismatchError(f"'{jsn.fspath}' is not a valid JSON file") from e
    return data


@extra_implementation(FileSet.save)
def save(jsn: Json, data: SerializationType, **kwargs: ty.Any) -> None:
    with jsn.open("w") as f:
        json.dump(data, f, **kwargs)
