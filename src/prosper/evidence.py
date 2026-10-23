"""Bounded immutable input files, not an import commit or recovery service.

Path checks assume no hostile concurrent directory replacement. No ACL or
power-loss durability guarantee is provided. All reparse/symlink aliases fail.
"""

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Literal, Self
from uuid import uuid4

from prosper.bundle import MAX_BYTES

STORAGE_VERSION = "evidence-bytes-v1"
_OBJECTS = f"{STORAGE_VERSION}/objects"
_STAGING = f"{STORAGE_VERSION}/staging"


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
    source_root: Path
    mode: Literal["synthetic", "private"]

    def __post_init__(self) -> None:
        self.check()

    def check(self) -> None:
        try:
            if self.mode not in ("synthetic", "private"):
                raise EvidenceError("invalid_runtime_mode")
            for path in (self.root, self.source_root):
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
            if not self.source_root.is_dir():
                raise EvidenceError("source_directory_required")
            if self.root.exists() and not self.root.is_dir():
                raise EvidenceError("directory_required")
            root = self.root.resolve()
            source = self.source_root.resolve()
            if self.mode == "private":
                if root.is_relative_to(source) or source.is_relative_to(root):
                    raise EvidenceError("private_source_overlap")
            elif not root.is_relative_to(source / ".local") or root == source / ".local":
                raise EvidenceError("synthetic_local_subtree_required")
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


@dataclass(frozen=True)
class EvidenceReceipt:
    raw_sha256: str
    byte_length: int
    relative_reference: str
    storage_version: str = STORAGE_VERSION

    def __post_init__(self) -> None:
        self.check()

    def check(self) -> None:
        if self.storage_version != STORAGE_VERSION:
            raise EvidenceError("unsupported_evidence_version")
        if not isinstance(self.raw_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", self.raw_sha256
        ):
            raise EvidenceError("invalid_digest")
        if type(self.byte_length) is not int or not 0 <= self.byte_length <= MAX_BYTES:
            raise EvidenceError("invalid_byte_length")
        if self.relative_reference != f"{_OBJECTS}/{self.raw_sha256}.bin":
            raise EvidenceError("invalid_reference")


def _read_file(path: Path) -> bytes:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise EvidenceError("untrusted_file_type_or_links")
    if info.st_size > MAX_BYTES:
        raise EvidenceError("evidence_size_exceeded")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise EvidenceError("untrusted_file_type_or_links")
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise EvidenceError("evidence_size_exceeded")
    return raw


def _write_staged(path: Path, raw: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _publish(staged: Path, final: Path) -> None:
    # Same runtime/volume. link never replaces an existing name. No copy fallback.
    os.link(staged, final)
    staged.unlink()


class EvidenceStore:
    @classmethod
    def existing(cls, runtime: RuntimeBoundary) -> Self:
        """Read adapter without directory creation; never initialize missing state."""
        runtime.check()
        if not runtime.root.is_dir():
            raise EvidenceError("runtime_missing")
        result = cls.__new__(cls)
        result.runtime = runtime
        return result

    def __init__(self, runtime: RuntimeBoundary) -> None:
        self.runtime = runtime
        try:
            for reference in (_OBJECTS, _STAGING):
                path = runtime.path(reference)
                path.mkdir(parents=True, exist_ok=True)
                runtime.path(reference)
                if not path.is_dir():
                    raise EvidenceError("directory_required")
        except OSError:
            raise EvidenceError("runtime_initialization_failed") from None

    def read(self, receipt: EvidenceReceipt) -> bytes:
        if not isinstance(receipt, EvidenceReceipt):
            raise EvidenceError("receipt_required")
        receipt.check()
        path = self.runtime.path(receipt.relative_reference)
        try:
            raw = _read_file(path)
        except FileNotFoundError:
            raise EvidenceError("evidence_missing") from None
        except OSError:
            raise EvidenceError("evidence_read_failed") from None
        if len(raw) != receipt.byte_length or hashlib.sha256(raw).hexdigest() != receipt.raw_sha256:
            raise EvidenceError("evidence_identity_mismatch")
        return raw

    def publish(self, raw: bytes) -> EvidenceReceipt:
        if not isinstance(raw, bytes):
            raise EvidenceError("byte_payload_required")
        if len(raw) > MAX_BYTES:
            raise EvidenceError("evidence_size_exceeded")
        digest = hashlib.sha256(raw).hexdigest()
        receipt = EvidenceReceipt(digest, len(raw), f"{_OBJECTS}/{digest}.bin")
        final = self.runtime.path(receipt.relative_reference)
        try:
            if final.exists():
                if self.read(receipt) != raw:
                    raise EvidenceError("evidence_identity_mismatch")
                return receipt
            staged = self.runtime.path(f"{_STAGING}/{uuid4().hex}.part")
            _write_staged(staged, raw)
            # Also detect an incomplete/corrupt staging write before publication.
            self.runtime.path(staged.relative_to(self.runtime.root).as_posix())
            if _read_file(staged) != raw:
                raise EvidenceError("staging_identity_mismatch")
            self.runtime.path(receipt.relative_reference)
            try:
                _publish(staged, final)
            except FileExistsError:
                # Another complete publisher may have won. Keep our staging file.
                pass
            if self.read(receipt) != raw:
                raise EvidenceError("evidence_identity_mismatch")
            return receipt
        except OSError:
            # Retain staged evidence for later recovery; never remove final files.
            raise EvidenceError("evidence_publication_failed") from None
