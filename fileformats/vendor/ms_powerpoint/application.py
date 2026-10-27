from fileformats.application import Presentation, Zip


class MsPowerPoint_Presentation_MacroEnabled_12(Zip, Presentation):
    ext = ".pptm"
    mime = "application/vnd.ms-powerpoint.presentation.macroEnabled.12"


class MsPowerPoint_Template_MacroEnabled_12(Zip, Presentation):
    ext = ".potm"
    mime = "application/vnd.ms-powerpoint.template.macroEnabled.12"


class MsPowerPoint_Slideshow_MacroEnabled_12(Zip, Presentation):
    ext = ".ppsm"
    mime = "application/vnd.ms-powerpoint.slideshow.macroEnabled.12"
