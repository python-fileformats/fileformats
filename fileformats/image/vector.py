from fileformats.application import InformalSchema, Xml
from fileformats.generic import UnicodeFile

from .base import Image


class VectorImage(Image, UnicodeFile):
    pass


class Svg(InformalSchema):
    pass


class Svg__Xml(VectorImage, Xml):
    ext = ".svg"
    iana_mime = "image/svg+xml"
    schema = Svg  # Set Xml schema attribute
    classifiers_attr_name = None  # disable classifiers inherited from Xml
