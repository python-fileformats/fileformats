from fileformats.application import Document, Zip


class Wordprocessingml_Document(Zip, Document):
    ext = ".docx"
    loaded_type = "docx.document.Document"


class Wordprocessingml_Template(Zip, Document):
    ext = ".dotx"
