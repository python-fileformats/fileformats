import json
import re
from pathlib import Path

from fileformats.core.identification import from_mime_format_name

PKG_DIR = Path(__file__).parent.parent / "fileformats"


def addin_descriptions(scraped_json_file: str) -> None:

    with open(scraped_json_file) as f:
        scraped_jasn = json.load(f)

    for registry, formats in scraped_jasn.items():

        mod_name = "misc" if registry == "application" else registry

        subpkg_path = PKG_DIR / mod_name

        if not subpkg_path.exists():
            continue

        for mod_path in subpkg_path.iterdir():

            if mod_path.is_dir():
                continue

            with open(mod_path) as f:
                code = f.read()

            for name, mdata in formats.items():

                if (
                    name.startswith("vnd.")
                    or "deprecated" in name
                    or "obsoleted" in name
                    or name == "example"
                ):
                    continue

                class_name = from_mime_format_name(name)

                applications = mdata.get("applications")
                if applications and applications.lower() in ("none", "n/a"):
                    applications = None
                additional_info = mdata.get("additional_info")
                if additional_info and additional_info.lower() in (
                    "none",
                    "none.",
                    "n/a",
                ):
                    additional_info = None

                desc = "\n\n".join(p for p in (applications, additional_info) if p)
                desc = re.sub(r"\s\s\s+\n?", r"\n    ", desc)

                code = re.sub(
                    f"class {class_name}" + r'\((.*)\):\n    """',
                    f"class {class_name}" + r'(\1):\n    """' + desc + "\n\n    ",
                    code,
                    flags=re.MULTILINE,
                )

            with open(mod_path, "w") as f:
                f.write(code)


if __name__ == "__main__":

    import sys

    scraped_json = sys.argv[1]

    addin_descriptions(scraped_json)
