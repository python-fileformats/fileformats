import json
import re
import typing as ty

import yaml


def generate_manual_edit_spec(scraped_json: str, editable_yaml: str) -> None:

    with open(scraped_json) as f:
        jsn = json.load(f)

    yml: ty.Dict[str, ty.Any] = {}

    for registry, formats in jsn.items():
        for name, mdata in formats.items():
            present = {
                k: k in mdata and mdata[k] and "n/a" not in mdata[k].lower()
                for k in ("magic_number", "ext")
            }

            if any(present.values()):
                dct = yml[f"{registry}/{name}"] = {}

                if present["magic_number"]:
                    dct["magic_number"] = mdata["magic_number"]
                    dct["magic_number_offset"] = 0

                if present["ext"]:
                    ext = re.sub(r"\([\)]+\)", "", mdata["ext"])
                    ext = ext.strip()
                    dct["ext"] = re.split(r"([ ,]+|,? or |,? and )", ext)

    with open(editable_yaml, "w") as f:
        yaml.dump(yml, f)


if __name__ == "__main__":

    import sys

    scraped_json, editable_yaml = sys.argv[1:3]

    generate_manual_edit_spec(scraped_json, editable_yaml)
