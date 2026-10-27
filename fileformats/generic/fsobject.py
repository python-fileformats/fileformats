import os
import sys
import typing as ty
from pathlib import Path

from fileformats.core.decorators import classproperty, validated_property
from fileformats.core.exceptions import FormatMismatchError
from fileformats.core.fileset import FileSet


class FsObject(FileSet, os.PathLike):  # type: ignore
    "Generic file-system object, can be either a file or a directory"

    @validated_property
    def fspath(self) -> Path:
        if len(self.fspaths) > 1:
            fspaths = [str(f) for f in self.fspaths]
            raise FormatMismatchError(
                f"More than one fspath ({fspaths}) provided to FsObject, "
                f"primary path is ambiguous"
            )
        return next(iter(self.fspaths))

    def __str__(self) -> str:
        """Renders the file path as a string so it can be used in templating e.g.
        ``f'cp {fs_object} /tmp'``
        """
        return str(self.fspath)

    def __fspath__(self) -> str:
        """Render to string, so can be treated as any other file-system path, i.e. passed
        to functions like file 'open'"""
        return str(self)

    @property
    def stem(self) -> str:
        return self.fspath.with_suffix("").name

    @classproperty  # type: ignore[arg-type]
    def unconstrained(cls) -> bool:
        """Whether the file-format is unconstrained by extension, magic number or another
        constraint"""
        # We have to subtract `fspath` from required properties as we defined unconstrained
        # file-sets as ones that have more constraints than simply existing
        return not (len(list(cls.validated_properties())) - 1)

    def absolute(self) -> Path:
        return self.fspath

    @property
    def anchor(self) -> str:
        return self.fspath.anchor

    def chmod(self, mode: int, *, follow_symlinks: bool = True) -> None:
        self.fspath.chmod(mode, follow_symlinks=follow_symlinks)  # type: ignore

    @property
    def drive(self) -> str:
        return self.fspath.drive

    def exists(self) -> bool:
        return True

    def group(self) -> ty.Optional[str]:
        if sys.platform == "win32":
            return None
        return self.fspath.group()

    def is_dir(self) -> bool:
        return self.fspath.is_dir()

    def is_file(self) -> bool:
        return self.fspath.is_file()

    @property
    def name(self) -> str:
        return self.fspath.name

    def owner(self) -> ty.Optional[str]:
        if sys.platform == "win32":
            return None
        return self.fspath.owner()

    @property
    def parts(self) -> ty.Tuple[str, ...]:
        return self.fspath.parts

    @property
    def root(self) -> str:
        return self.fspath.root

    def stat(self, follow_symlinks: bool = True) -> os.stat_result:
        return self.fspath.stat(follow_symlinks=follow_symlinks)  # type: ignore

    @property
    def suffix(self) -> str:
        return self.fspath.suffix

    @property
    def suffixes(self) -> ty.List[str]:
        return self.fspath.suffixes
