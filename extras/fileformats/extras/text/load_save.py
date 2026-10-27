import typing as ty

from fileformats.core import FileSet, extra_implementation
from fileformats.text import Plain  # , Csv, Tsv

# import pandas as pd


@extra_implementation(FileSet.load)
def load_text_file(text: Plain, **kwargs: ty.Any) -> str:
    return text.raw_contents  # type: ignore[no-any-return]


@extra_implementation(FileSet.save)
def save_text_file(text: Plain, data: str, **kwargs: ty.Any) -> None:
    text.fspath.write_text(data)


# @extra_implementation(FileSet.load)
# def load_csv_file(csv_file: Csv, **kwargs: ty.Any) -> pd.DataFrame:
#     return pd.read_csv(csv_file.fspath, **kwargs)


# @extra_implementation(FileSet.save)
# def save_csv_file(csv_file: Csv, data: pd.DataFrame, **kwargs: ty.Any) -> None:
#     data.to_csv(csv_file.fspath, index=False, **kwargs)


# @extra_implementation(FileSet.load)
# def load_tsv_file(tsv_file: Tsv, **kwargs: ty.Any) -> pd.DataFrame:
#     return pd.read_csv(tsv_file.fspath, sep="\t", **kwargs)


# @extra_implementation(FileSet.save)
# def save_tsv_file(tsv_file: Tsv, data: pd.DataFrame, **kwargs: ty.Any) -> None:
#     data.to_csv(tsv_file.fspath, sep="\t", index=False, **kwargs)
