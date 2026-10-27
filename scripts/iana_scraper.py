import json
import sys
import typing as ty
from warnings import warn

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Define the URL to scrape
IANA_URL = "https://www.iana.org/assignments/media-types/media-types.xhtml"

NONE_TYPES = ("none", "n/a", "")


def extract_info_from_subtype_template(
    name: str, registry: str, text: str
) -> ty.Mapping[str, str]:
    mime_info = {}

    def add_mime_info(key: ty.Optional[str], value: str) -> str:
        if key is not None:
            value = value.strip() if value else value
            if "magic number" in key:
                if value.lower() in NONE_TYPES:
                    value = "None"
                mime_info["magic_number"] = value
            elif "file extension" in key:
                if value.lower() in NONE_TYPES:
                    value = ""
                elif not value.startswith("."):
                    value = "." + value
                mime_info["ext"] = value
            elif "additional information" in key:
                mime_info["additional_info"] = value
            elif "applications that use this media type" in key:
                mime_info["applications"] = value
            value = ""
        return value

    lines = text.strip().split("\n")
    key = None
    value = ""
    for line in lines:
        if ":" in line:
            value = add_mime_info(key, value)
            key, line = line.split(":", 1)
            key = key.strip().lower()
        value += line + " "
    add_mime_info(key, value)
    return mime_info


def get_subtype_templates() -> ty.Dict[str, ty.Dict[str, ty.Dict[str, ty.Any]]]:
    # Send a GET request to the URL
    response = requests.get(IANA_URL)

    subtype_templates: ty.Dict[str, ty.Dict[str, ty.Dict[str, ty.Any]]] = {}

    # Parse the HTML content of the response
    soup = BeautifulSoup(response.content, "html.parser")

    registries = [a.text for a in soup.find("ul").find_all("a")]

    not_covered = []

    for registry in tqdm(registries):

        if registry == "example":
            continue

        subtype_templates[registry] = {}

        table = soup.find("table", {"id": f"table-{registry}"})
        for row in tqdm(table.find("tbody").find_all("tr")):
            cells = row.find_all("td")
            subtype_name = cells[0].text
            try:
                anchor = cells[1].find("a")
            except Exception:
                not_covered.append(f"{registry}/{subtype_name}")
                continue
            if anchor is None:
                not_covered.append(f"{registry}/{subtype_name}")
                continue
            subtype_href = anchor["href"]
            subtype_url = IANA_URL[: IANA_URL.rindex("/") + 1] + subtype_href
            # Send a GET request to the URL
            response = requests.get(subtype_url)
            # Check if the request was successful
            if response.status_code == 200:
                subtype_templates[registry][subtype_name] = dict(
                    extract_info_from_subtype_template(
                        registry, subtype_name, response.text
                    )
                )
            else:
                # If the request was not successful, return an error message
                warn(
                    f"Failed to retrieve page for {subtype_name}: {response.status_code}"
                )

        print("\n".join(not_covered))

    return subtype_templates


if __name__ == "__main__":

    output_file = sys.argv[1]

    templates = get_subtype_templates()

    with open(output_file, "w") as f:
        json.dump(templates, f, indent=" " * 4)
