from fileformats.vendor.openxmlformats_officedocument.application import (
    Wordprocessingml_Document,
)


class MsWord_Document_MacroEnabled_12(Wordprocessingml_Document):
    ext = ".docm"
    mime = "application/vnd.ms-word.document.macroEnabled.12"


class MsWord_Template_MacroEnabled_12(Wordprocessingml_Document):
    ext = ".dotm"
    mime = "application/vnd.ms-word.template.macroEnabled.12"
