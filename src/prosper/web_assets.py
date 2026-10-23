"""Bounded immutable trusted build assets; never a general filesystem server."""

import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

MAX_ASSET_BYTES = 2 * 1024 * 1024
MAX_BUILD_BYTES = 8 * 1024 * 1024
MAX_ASSETS = 32
CONTENT_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


def _plain(path: Path, *, directory: bool = False) -> os.stat_result:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or (
        os.name == "nt" and info.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise ValueError("redirected_asset")
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("asset_directory_required")
    elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("plain_asset_required")
    return info


@dataclass(frozen=True)
class WebAssets:
    files: Mapping[str, tuple[bytes, str]]

    @classmethod
    def load(cls, root: Path) -> "WebAssets":
        if not root.is_absolute() or ".." in root.parts or str(root).startswith("\\\\"):
            raise ValueError("absolute_local_build_required")
        for part in (*reversed(root.parents), root):
            _plain(part, directory=True)
        _plain(root / "assets", directory=True)
        candidates = [("/", root / "index.html", "text/html")]
        for path in (root / "assets").iterdir():
            if len(candidates) >= MAX_ASSETS:
                raise ValueError("asset_count_limit")
            # Only direct Vite-style asset names; maps, JSON, data and subtrees stay private.
            if not re.fullmatch(r"[A-Za-z0-9_-]+\.(js|css)", path.name):
                raise ValueError("unsupported_build_asset")
            candidates.append(
                (
                    f"/assets/{path.name}",
                    path,
                    "text/javascript" if path.suffix == ".js" else "text/css",
                )
            )
        if not 1 < len(candidates) <= MAX_ASSETS:
            raise ValueError("asset_count_limit")
        files: dict[str, tuple[bytes, str]] = {}
        total = 0
        for route, path, media in candidates:
            before = _plain(path)
            if before.st_size > MAX_ASSET_BYTES:
                raise ValueError("asset_size_limit")
            with path.open("rb") as stream:
                opened = os.fstat(stream.fileno())
                data = stream.read(MAX_ASSET_BYTES + 1)
                after = os.fstat(stream.fileno())
            current = _plain(path)

            def identity(s: os.stat_result) -> tuple[int, int, int, int, int]:
                return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_nlink

            if not identity(before) == identity(opened) == identity(after) == identity(current):
                raise ValueError("asset_changed")
            total += len(data)
            if len(data) != before.st_size or total > MAX_BUILD_BYTES:
                raise ValueError("build_size_limit")
            files[route] = (data, media)
        return cls(MappingProxyType(files))
