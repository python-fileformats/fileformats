from pathlib import Path

from fileformats.application import Json, Yaml

SAMPLE_JSON = (
    """{"a": "string field", "alist": [0, 1, 2, 3, 4, 5], """
    """"anesteddict": {"x": null, "y": [], "z": 42.0}}"""
)

SAMPLE_YAML = """a: string field
alist:
- 0
- 1
- 2
- 3
- 4
- 5
anesteddict:
  x: null
  y: []
  z: 42.0
"""


def test_json_to_yaml(tmp_path: Path):
    in_file = tmp_path / "test.json"
    with open(in_file, "w") as f:
        f.write(SAMPLE_JSON)
    jsn = Json(in_file)
    yml = Yaml.convert(jsn, out_dir=tmp_path)
    assert yml.raw_contents == SAMPLE_YAML


def test_yaml_to_json(tmp_path: Path):
    in_file = tmp_path / "test.yaml"
    with open(in_file, "w") as f:
        f.write(SAMPLE_YAML)
    yml = Yaml(in_file)
    jsn = Json.convert(yml, out_dir=tmp_path)
    assert jsn.raw_contents == SAMPLE_JSON
