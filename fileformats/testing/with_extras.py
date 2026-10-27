from fileformats.core import FileSet, extra


class WithExtra(FileSet):

    ext = ".wextra"

    @extra
    def foo(self, an_arg: int) -> int:  # type: ignore[no-untyped-def]
        return NotImplementedError  # type: ignore[return-value]
