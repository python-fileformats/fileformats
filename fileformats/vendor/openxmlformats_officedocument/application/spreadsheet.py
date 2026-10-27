from fileformats.application import Spreadsheet, Zip


class Spreadsheetml_Sheet(Zip, Spreadsheet):
    ext = ".xlsx"
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Spreadsheetml_Template(Zip, Spreadsheet):
    ext = ".xltx"
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.template"
