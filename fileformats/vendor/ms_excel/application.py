from fileformats.application import Spreadsheet, Zip


class Sheet_MacroEnabled_12(Zip, Spreadsheet):
    ext = ".xlsm"
    mime = "application/vnd.ms-excel.sheet.macroEnabled.12"


class Template_MacroEnabled_12(Zip, Spreadsheet):
    ext = ".xltm"
    mime = "application/vnd.ms-excel.template.macroEnabled.12"


class Binary_MacroEnabled_12(Zip, Spreadsheet):
    ext = ".xlsb"
    mime = "application/vnd.ms-excel.sheet.binary.macroEnabled.12"
