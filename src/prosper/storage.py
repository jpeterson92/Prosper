"""Guarded local runtime paths and safe error codes for current SQLite services.

Path checks assume no hostile concurrent directory replacement. No ACL or
power-loss durability guarantee is provided. All reparse/symlink aliases fail.
"""

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

MAX_BYTES = 2 * 1024 * 1024
RESTORE_MARKER = "restore-in-progress"


class EvidenceError(ValueError):
    """Stable code only; never include paths, supplied bytes or OS error text."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _parts(reference: str) -> tuple[str, ...]:
    if not isinstance(reference, str) or not reference:
        raise EvidenceError("invalid_reference")
    parts = tuple(reference.split("/"))
    if any(
        not re.fullmatch(r"[A-Za-z0-9_.-]+", part)
        or part in (".", "..")
        or part.endswith(".")
        or PureWindowsPath(part).is_reserved()
        for part in parts
    ):
        raise EvidenceError("invalid_reference")
    return parts


def _chain(path: Path) -> None:
    """Inspect existing components without resolving through redirects."""
    for component in (*reversed(path.parents), path):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or (
            info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
            if os.name == "nt"
            else False
        ):
            raise EvidenceError("redirected_path")
        if component != path and not stat.S_ISDIR(info.st_mode):
            raise EvidenceError("directory_required")


@dataclass(frozen=True)
class RuntimeBoundary:
    root: Path
    protected_roots: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        self.check()

    def check(self) -> None:
        try:
            for path in (self.root, *self.protected_roots):
                if (
                    not isinstance(path, Path)
                    or not path.is_absolute()
                    or ".." in path.parts
                    or str(path).startswith("\\\\")
                    or any(
                        part.endswith((".", " "))
                        or PureWindowsPath(part).is_reserved()
                        or ":" in part
                        for part in path.parts[1:]
                    )
                ):
                    raise EvidenceError("absolute_local_path_required")
                _chain(path)
            if self.root.exists() and not self.root.is_dir():
                raise EvidenceError("directory_required")
            root = self.root.resolve()
            for protected in self.protected_roots:
                if not protected.is_dir():
                    raise EvidenceError("protected_directory_required")
                resolved = protected.resolve()
                if root.is_relative_to(resolved) or resolved.is_relative_to(root):
                    raise EvidenceError("protected_runtime_overlap")
        except OSError:
            raise EvidenceError("runtime_path_unavailable") from None

    def path(self, reference: str) -> Path:
        """Reusable guard for adapter-owned relative files, including future SQLite."""
        parts = _parts(reference)
        self.check()
        path = self.root.joinpath(*parts)
        try:
            _chain(path)
        except OSError:
            raise EvidenceError("runtime_path_unavailable") from None
        return path


class PersistenceError(EvidenceError):
    """Stable storage refusal code, without source payloads or OS paths."""
