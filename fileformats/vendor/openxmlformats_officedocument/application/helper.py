from fileformats.application import Xml


class Drawingml_Chart__Xml(Xml):
    ext = ".chart"
    mime = "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"


class Drawingml_Diagram__Xml(Xml):
    ext = ".diagram"
    mime = "application/vnd.openxmlformats-officedocument.drawingml.diagram+xml"


class Wordprocessingml_Footnotes__Xml(Xml):
    ext = ".footnotes"
    mime = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"
    )


class Wordprocessingml_Endnotes__Xml(Xml):
    ext = ".endnotes"
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"


class Wordprocessingml_Header__Xml(Xml):
    ext = ".header"
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"


class Wordprocessingml_Footer__Xml(Xml):
    ext = ".footer"
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"


class Wordprocessingml_Comments__Xml(Xml):
    ext = ".comments"
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"


class Presentationml_Slide__Xml(Xml):
    ext = ".sldx"
    mime = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"


class Presentationml_SlideLayout__Xml(Xml):
    ext = ".sldlayout"
    mime = (
        "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"
    )


class Presentationml_SlideMaster__Xml(Xml):
    ext = ".sldmaster"
    mime = (
        "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"
    )


class Presentationml_NotesSlide__Xml(Xml):
    ext = ".sldnotes"
    mime = "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"


class Presentationml_HandoutMaster__Xml(Xml):
    ext = ".handoutmaster"
    mime = (
        "application/vnd.openxmlformats-officedocument.presentationml.handoutMaster+xml"
    )


class Presentationml_NotesMaster__Xml(Xml):
    ext = ".notesmaster"
    mime = (
        "application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"
    )


class Theme__Xml(Xml):
    ext = ".thmx"
    mime = "application/vnd.openxmlformats-officedocument.theme+xml"


class ThemeOverride__Xml(Xml):
    ext = ".thmoverride"
    mime = "application/vnd.openxmlformats-officedocument.themeOverride+xml"


class VmlDrawing(Xml):
    ext = ".vml"
    mime = "application/vnd.openxmlformats-officedocument.vmlDrawing"
