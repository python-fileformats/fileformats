import json

import pytest
from fileformats.application import Dicom


def test_dicom_metadata():

    dicom = Dicom.sample()

    assert dicom.metadata["EchoTime"] == 2.07


def test_dicom_metadata_sequence_converted_to_list_of_dicts():
    """SQ-VR elements (e.g. ReferencedImageSequence) hold a list of nested Datasets.
    These should be converted to plain lists of dicts, like nested single Datasets
    are, rather than left as unconverted pydicom Sequence/Dataset objects.
    """
    dicom = Dicom.sample()

    sequence = dicom.metadata["ReferencedImageSequence"]
    assert isinstance(sequence, list)
    assert sequence  # sample data actually has entries to convert
    for item in sequence:
        assert isinstance(item, dict)
        assert isinstance(item["ReferencedSOPInstanceUID"], str)


def test_dicom_metadata_is_json_serialisable():
    """The whole metadata dict, including nested sequences, should round-trip
    through JSON (modulo values like PersonName that are deliberately kept as
    richer objects and need `default=str` from the caller)."""
    dicom = Dicom.sample()

    json.dumps(dict(dicom.metadata), default=str)


def test_dicom_metadata_with_specific_tags():

    dicom = Dicom(Dicom.sample(), metadata_keys=["EchoTime"])

    assert dicom.metadata["EchoTime"] == 2.07
    with pytest.raises(KeyError):
        dicom.metadata["PatientName"]
