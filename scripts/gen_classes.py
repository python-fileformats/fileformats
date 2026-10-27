import json
import re
import shutil
from pathlib import Path

import yaml

from fileformats.core.identification import from_mime_format_name


def generated_classes(
    scraped_json_file: str, editable_yaml_file: str, output_dir: Path
) -> None:

    with open(scraped_json_file) as f:
        scraped_jasn = json.load(f)

    with open(editable_yaml_file) as f:
        editable_yaml = yaml.load(f, Loader=yaml.SafeLoader)

    output_dir = Path(output_dir)
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir()

    for registry, formats in scraped_jasn.items():

        classes = []

        for name, mdata in formats.items():

            if (
                name.startswith("vnd.")
                or "deprecated" in name
                or "obsoleted" in name
                or name == "example"
            ):
                continue

            class_name = from_mime_format_name(name)

            yml = editable_yaml.get(f"{registry}/{name}", {})

            magic_number = yml.get("magic_number")
            magic_number_offset = yml.get("magic_number_offset")
            todo = yml.get("info")
            if todo:
                todo = "TODO: " + todo
            exts = yml.get("ext", [])

            applications = mdata.get("applications")
            additional_info = mdata.get("additional_info")

            desc = "\n\n".join(p for p in (applications, additional_info, todo) if p)
            desc = re.sub(r"\s\s\s+\n?", r"\n    ", desc)

            bases = "WithMagicNumber, BinaryFile" if magic_number else "File"

            code = f"""
class {class_name}({bases}):
    \"\"\"{desc}\"\"\"
    iana_mime = "{registry}/{name}"
"""

            if exts:
                code += f'    ext = "{exts[0]}"\n'
                if len(exts) > 1:
                    code += f"    alternative_exts = {tuple(exts[1:])}\n"
            else:
                code += "    ext = None\n"
            if magic_number:
                code += "    magic_number = "
                if isinstance(magic_number, str):
                    code += f'b"{magic_number}"\n'
                else:
                    code += f'"{hex(magic_number)[2:]}"\n'
                if magic_number_offset:
                    code += f"    magic_number_offset = {magic_number_offset}\n"

            classes.append(code)

        with open(output_dir / (registry + ".py"), "w") as f:
            f.write("from fileformats.generic import File\n")
            f.write("from fileformats.core.mixin import WithMagicNumber\n\n")
            f.write("\n".join(classes))


if __name__ == "__main__":

    import sys

    scraped_json, editable_yaml, output_dir = sys.argv[1:4]

    generated_classes(scraped_json, editable_yaml, Path(output_dir))
