import typing as ty

from fileformats.core.mixin import WithMagicNumber
from fileformats.generic import BinaryFile

if ty.TYPE_CHECKING:
    import pydicom


class Dicom(WithMagicNumber, BinaryFile):

    iana_mime = "application/dicom"
    magic_number = b"DICM"
    magic_number_offset = 128
    binary = True

    alternate_exts = (".dcm",)  # dcm is recommended not required
    loaded_type = "pydicom.FileDataset"

    @classmethod
    def pydicom_to_dict(
        cls, dcm: "pydicom.Dataset", omit: ty.Collection[str] = ("PixelData",)
    ) -> ty.Dict[str, ty.Any]:
        """Convert a pydicom Dataset to a dictionary.

        Parameters
        ----------
        dcm : pydicom.Dataset
            The pydicom Dataset to convert.
        omit : Collection[str], optional
            A collection of keys to omit from the dictionary, by default ("PixelData",)

        Returns
        -------
        Dict[str, Any]
            The dictionary representation of the pydicom Dataset
        """
        import pydicom.datadict
        import pydicom.dataelem
        import pydicom.dataset
        import pydicom.multival
        import pydicom.sequence
        import pydicom.uid
        import pydicom.valuerep

        dct: ty.Dict[str, ty.Any] = {}
        for elem in dcm.values():
            # RawDataElement objects are not yet decoded; zero-length ones have value=None.
            # Force conversion to DataElement by fetching via __getitem__.
            if isinstance(elem, pydicom.dataelem.RawDataElement):
                elem = dcm[elem.tag]  # type: ignore[attr-defined]
            key = pydicom.datadict.keyword_for_tag(elem.tag)  # type: ignore[attr-defined]
            if not key:
                key = elem.tag.json_key  # type: ignore[attr-defined]
            if key not in omit:
                value = elem.value  # type: ignore[attr-defined]
                # Sequence (SQ) elements hold a list of nested Datasets. Checked before
                # MultiValue since in some pydicom versions Sequence subclasses it, and
                # we want the per-item dict conversion below rather than the str() one.
                if isinstance(value, pydicom.sequence.Sequence):
                    value = [cls.pydicom_to_dict(item, omit) for item in value]
                elif isinstance(value, pydicom.multival.MultiValue):
                    value = [str(v).rstrip() for v in value]
                elif isinstance(value, pydicom.uid.UID):
                    value = str(value)
                elif isinstance(value, bytes):
                    value = value.decode(errors="ignore").rstrip()
                elif isinstance(value, pydicom.dataset.Dataset):
                    value = cls.pydicom_to_dict(value, omit)
                elif isinstance(value, pydicom.valuerep.IS):
                    value = int(value)
                elif isinstance(value, pydicom.valuerep.DSfloat):
                    value = float(value)
                elif isinstance(value, str):
                    value = value.rstrip()
                # Reconstruct stripped to remove DICOM even-length space padding,
                # while preserving component access (family_name, given_name, etc.)
                elif isinstance(value, pydicom.valuerep.PersonName):
                    value = pydicom.valuerep.PersonName(str(value).rstrip())
                dct[key] = value
        return dct
