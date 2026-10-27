from fileformats.application import Presentation, Zip


class Presentationml_Presentation(Zip, Presentation):
    ext = ".pptx"


class Presentationml_Template(Zip, Presentation):
    ext = ".potx"


class Presentationml_Slideshow(Zip, Presentation):
    ext = ".ppsx"
