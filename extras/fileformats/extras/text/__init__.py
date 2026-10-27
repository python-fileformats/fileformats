from pathlib import Path

from fileformats.core import FileSet, extra_implementation
from fileformats.core.sampling import SampleFileGenerator
from fileformats.text import TextFile

from . import load_save


@extra_implementation(FileSet.generate_sample_data)
def text_file_generate_sample_data_with_extra(
    text_file: TextFile,
    generator: SampleFileGenerator,
) -> list[Path]:
    # Generate sample data by writing some text to the file
    return [generator.generate(TextFile, fill=10)]


__all__ = ["load_save", "text_file_generate_sample_data_with_extra"]
