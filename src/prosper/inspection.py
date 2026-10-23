"""Bounded recovery observations. No report authorizes repair or deletion.

Existing databases are opened read-only, with normal SQLite WAL/journal rules.
SQLite may manage its own shared-memory sidecar. Payloads are never initialized,
upgraded, published, renamed or removed. Hostile path replacement is unqualified.
"""

import hashlib
import json
import os
import re
import sqlite3
import stat
from contextlib import closing
from dataclasses import dataclass, replace
from typing import Literal

from prosper.bundle import MAX_BYTES
from prosper.evidence import (
    STORAGE_VERSION,
    EvidenceError,
    EvidenceReceipt,
    EvidenceStore,
    RuntimeBoundary,
)
from prosper.persistence import DATABASE_NAME, RESTORE_MARKER, CheckpointStore, PersistenceError
from prosper.recovery import (
    MANIFEST_NAME,
    MAX_DATABASE_BYTES,
    MAX_MANIFEST_BYTES,
    StateSummary,
    _manifest,
    _references_connection,
    _verify_connection,
)

type ArtifactRole = Literal["runtime", "backup", "interrupted_restore"]
MAX_ENTRIES = 25_000
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_ROWS = 50_000
_SIDECARS = tuple(DATABASE_NAME + suffix for suffix in ("-journal", "-wal", "-shm"))
_TABLES = ("checkpoints", "import_previews", "import_activations", "import_commands")


@dataclass(frozen=True, order=True)
class Finding:
    reference: str
    code: str


@dataclass(frozen=True)
class FileObservation:
    reference: str
    kind: str
    classification: str
    byte_length: int | None = None
    sha256: str | None = None
    file_identity: tuple[int, int] | None = None
    links: int | None = None
    required: bool | None = None


@dataclass(frozen=True)
class DatabaseObservation:
    reference: str
    status: str
    snapshot_sha256: str | None = None
    required: tuple[EvidenceReceipt, ...] | None = None
    state: StateSummary | None = None


@dataclass(frozen=True)
class RecoveryInspection:
    role: ArtifactRole
    status: Literal["verified", "non_ready"]
    databases: tuple[DatabaseObservation, ...]
    files: tuple[FileObservation, ...]
    findings: tuple[Finding, ...]
    planning_ready: Literal[False] = False


def _stamp(info: os.stat_result) -> tuple[int, ...]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_nlink, info.st_mtime_ns, info.st_mode)


def _step(name: str) -> None:
    """Test seam at actual snapshot/inventory boundaries; no application callback."""


class _Inventory:
    def __init__(self, boundary: RuntimeBoundary) -> None:
        self.boundary = boundary
        self.files: dict[str, FileObservation] = {}
        self.findings: set[Finding] = set()
        self.stamps: dict[str, tuple[int, ...]] = {}
        self.entries = 0
        self.bytes = 0

    def issue(self, reference: str, code: str) -> None:
        self.findings.add(Finding(reference, code))

    def scan(self, reference: str, level: str, role: ArtifactRole) -> None:
        path = self.boundary.root if not reference else self.boundary.path(reference)
        self.stamps[reference] = _stamp(path.lstat())
        # Limit enumeration before sorting; never recurse into an unknown directory.
        with os.scandir(path) as listing:
            names = []
            for entry in listing:
                self.entries += 1
                if self.entries > MAX_ENTRIES:
                    raise EvidenceError("inspection_entry_limit")
                names.append(entry.name)
        for name in sorted(names):
            relative = f"{reference}/{name}" if reference else name
            try:
                if len(relative) > 256:
                    raise EvidenceError("invalid_reference")
                child = self.boundary.path(relative)
            except EvidenceError as error:
                # Do not echo arbitrary/untrusted filenames in a diagnostic.
                self.issue(reference or ".", "unsafe_entry_" + error.code)
                continue
            info = child.lstat()
            self.stamps[relative] = _stamp(info)
            directory = None
            kind = None
            limit = MAX_BYTES
            if level == "root":
                if name == STORAGE_VERSION:
                    directory = "evidence"
                elif name == "restore-work" and not reference and role != "backup":
                    directory = "root_work"
                elif name == DATABASE_NAME:
                    kind, limit = "database", MAX_DATABASE_BYTES
                elif name in _SIDECARS:
                    kind, limit = "sidecar", MAX_DATABASE_BYTES
                elif name in (MANIFEST_NAME, "manifest.part"):
                    kind, limit = "manifest", MAX_MANIFEST_BYTES
                elif name == RESTORE_MARKER:
                    kind, limit = "restore_marker", 64
            elif level == "evidence" and name in ("objects", "staging"):
                directory = name
            elif level == "objects" and re.fullmatch(r"[0-9a-f]{64}\.bin", name):
                kind = "object"
            elif level == "staging" and re.fullmatch(r"[0-9a-f]{32}\.part", name):
                kind = "staging"
            if directory is not None and stat.S_ISDIR(info.st_mode):
                # Work can contain one known runtime layout, never nested work.
                self.scan(
                    relative,
                    "root" if directory == "root_work" else directory,
                    "runtime" if directory == "root_work" else role,
                )
                if directory == "root_work" and any(
                    key.startswith(relative + "/") for key in self.stamps
                ):
                    self.issue(relative, "retained_restore_work")
            elif kind is not None and stat.S_ISREG(info.st_mode):
                self.files[relative] = self.read(relative, kind, info, limit)
            else:
                self.issue(relative, "unknown_or_wrong_type")
                self.files[relative] = FileObservation(relative, "unknown", "unresolved")

    def read(self, reference: str, kind: str, info: os.stat_result, limit: int) -> FileObservation:
        self.bytes += info.st_size
        if info.st_size > limit or self.bytes > MAX_TOTAL_BYTES:
            raise EvidenceError("inspection_byte_limit")
        if kind == "sidecar" and reference.endswith("-shm"):
            # SQLite read locks alter shared memory even during read-only SQL.
            # It is engine coordination, not authoritative payload/hash evidence.
            return FileObservation(
                reference,
                kind,
                "engine_shared_memory",
                info.st_size,
                None,
                (info.st_dev, info.st_ino),
                info.st_nlink,
            )
        digest = hashlib.sha256()
        length = 0
        with self.boundary.path(reference).open("rb") as stream:
            if _stamp(os.fstat(stream.fileno())) != _stamp(info):
                raise EvidenceError("inventory_changed")
            while chunk := stream.read(min(1024 * 1024, limit + 1 - length)):
                length += len(chunk)
                if length > limit:
                    raise EvidenceError("inspection_byte_limit")
                digest.update(chunk)
            if _stamp(os.fstat(stream.fileno())) != _stamp(info) or length != info.st_size:
                raise EvidenceError("inventory_changed")
        return FileObservation(
            reference,
            kind,
            "observed",
            length,
            digest.hexdigest(),
            (info.st_dev, info.st_ino),
            info.st_nlink,
        )

    def stable(self) -> None:
        for reference, stamp in self.stamps.items():
            try:
                path = self.boundary.path(reference) if reference else self.boundary.root
                current = _stamp(path.lstat())
                if reference.endswith(DATABASE_NAME + "-shm"):
                    # Keep identity/type/link guards; ignore normal reader-lock writes.
                    same = all(current[i] == stamp[i] for i in (0, 1, 3, 5))
                    same = same and current[2] <= MAX_DATABASE_BYTES
                else:
                    same = current == stamp
                if not same:
                    self.issue(reference or ".", "inventory_changed")
            except (OSError, EvidenceError):
                self.issue(reference or ".", "inventory_changed")


def _snapshot(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    total = 0
    for table in _TABLES:
        count = connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        total += count
        if total > MAX_ROWS:
            raise EvidenceError("inspection_row_limit")
        digest.update(table.encode())
        for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1, 2"):
            digest.update(json.dumps(row, ensure_ascii=True, separators=(",", ":")).encode())
            digest.update(b"\n")
    return digest.hexdigest()


def _database(inventory: _Inventory, prefix: str) -> DatabaseObservation:
    reference = prefix + DATABASE_NAME
    node = inventory.files.get(reference)
    if node is None:
        inventory.issue(reference, "database_missing")
        return DatabaseObservation(reference, "database_missing")
    if node.kind != "database" or node.links != 1:
        inventory.issue(reference, "untrusted_database")
        return DatabaseObservation(reference, "untrusted_database")
    for name in _SIDECARS:
        item = inventory.files.get(prefix + name)
        if item is not None and (item.kind != "sidecar" or item.links != 1):
            inventory.issue(prefix + name, "untrusted_database_sidecar")
            return DatabaseObservation(reference, "untrusted_database_sidecar")
    observed = DatabaseObservation(reference, "database_unverified")
    try:
        # Guard every engine-owned path before SQLite can follow a sidecar.
        for name in (DATABASE_NAME, *_SIDECARS):
            guarded = inventory.boundary.path(prefix + name)
            if guarded.exists():
                info = guarded.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise EvidenceError("untrusted_database_path")
        path = inventory.boundary.path(reference)
        with closing(
            sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, isolation_level=None, timeout=0.1)
        ) as connection:
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA query_only=ON")
            before = connection.execute("PRAGMA data_version").fetchone()
            connection.execute("BEGIN")
            pages = connection.execute("PRAGMA page_count").fetchone()[0]
            size = connection.execute("PRAGMA page_size").fetchone()[0]
            if pages * size > MAX_DATABASE_BYTES:
                raise EvidenceError("inspection_byte_limit")
            required = _references_connection(connection)
            identity = _snapshot(connection)
            observed = DatabaseObservation(reference, "references_observed", identity, required)
            _step("snapshot_read")
            root = (
                inventory.boundary.root.joinpath(*prefix.rstrip("/").split("/"))
                if prefix
                else inventory.boundary.root
            )
            area = RuntimeBoundary(root, inventory.boundary.source_root, inventory.boundary.mode)
            state, verified = _verify_connection(
                CheckpointStore.existing(EvidenceStore.existing(area)), connection
            )
            if required != verified:
                raise EvidenceError("reference_mismatch")
            observed = replace(observed, status="verified", state=state)
            connection.rollback()
            if before != connection.execute("PRAGMA data_version").fetchone():
                inventory.issue(reference, "snapshot_changed")
    except (EvidenceError, PersistenceError) as error:
        inventory.issue(reference, error.code)
        observed = replace(observed, status=error.code)
    except (OSError, sqlite3.Error):
        inventory.issue(reference, "database_unreadable")
        observed = replace(observed, status="database_unreadable")
    return observed


def _classify(inventory: _Inventory, databases: list[DatabaseObservation]) -> None:
    areas = {database.reference.removesuffix(DATABASE_NAME): database for database in databases}
    for reference, node in list(inventory.files.items()):
        if node.kind not in ("object", "staging"):
            if node.links is not None and node.links != 1:
                inventory.issue(reference, "unexplained_links")
            continue
        prefix = reference.split(STORAGE_VERSION + "/", 1)[0]
        database = areas.get(prefix)
        required = None if database is None else database.required
        expected = (
            None
            if required is None
            else next((r for r in required if prefix + r.relative_reference == reference), None)
        )
        is_required = None if required is None else expected is not None
        classification = "unreferenced_staging" if node.kind == "staging" else "reference_unknown"
        if node.kind == "object":
            if node.sha256 != reference.rsplit("/", 1)[-1].removesuffix(".bin"):
                classification = "corrupt_object"
                inventory.issue(reference, classification)
            elif expected is not None and node.byte_length != expected.byte_length:
                classification = "corrupt_required_object"
                inventory.issue(reference, classification)
            else:
                classification = (
                    "required_verified"
                    if is_required
                    else ("unreferenced_object" if is_required is False else "reference_unknown")
                )
        if node.links != 1:
            aliases = [
                other
                for other in inventory.files.values()
                if other.file_identity == node.file_identity
            ]
            objects = [other for other in aliases if other.kind == "object"]
            local = (
                node.file_identity is not None
                and node.file_identity[1] != 0
                and len(aliases) == node.links
                and len(objects) == 1
                and all(
                    other.kind in ("object", "staging")
                    and other.sha256 == node.sha256
                    and other.links == node.links
                    and other.reference.startswith(prefix + STORAGE_VERSION + "/")
                    for other in aliases
                )
                and objects[0].sha256 == objects[0].reference.rsplit("/", 1)[-1][:-4]
                and classification not in ("corrupt_object", "corrupt_required_object")
            )
            if (
                local
                and required is not None
                and any(
                    prefix + receipt.relative_reference == objects[0].reference
                    and receipt.byte_length != objects[0].byte_length
                    for receipt in required
                )
            ):
                local = False
            classification = "local_publication_alias" if local else "unexplained_links"
            inventory.issue(reference, classification)
        inventory.files[reference] = replace(
            node, classification=classification, required=is_required
        )
    for prefix, database in areas.items():
        if database.required is not None:
            for receipt in database.required:
                reference = prefix + receipt.relative_reference
                if reference not in inventory.files:
                    inventory.issue(reference, "required_evidence_missing")
                else:
                    node = inventory.files[reference]
                    if node.sha256 != receipt.raw_sha256 or node.byte_length != receipt.byte_length:
                        inventory.issue(reference, "required_evidence_mismatch")


def _backup(inventory: _Inventory, databases: list[DatabaseObservation]) -> None:
    try:
        manifest = _manifest(inventory.boundary)
        for item in (manifest.database, *manifest.evidence):
            observed = inventory.files.get(item.reference)
            if observed is None or (observed.sha256, observed.byte_length, observed.links) != (
                item.sha256,
                item.byte_length,
                1,
            ):
                raise EvidenceError("backup_identity_mismatch")
        root = databases[0]
        expected = tuple(
            EvidenceReceipt(item.sha256, item.byte_length, item.reference)
            for item in manifest.evidence
        )
        if root.status != "verified" or root.required != expected or root.state != manifest.state:
            raise EvidenceError("backup_state_mismatch")
    except (EvidenceError, PersistenceError) as error:
        inventory.issue(MANIFEST_NAME, error.code)
    except (OSError, ValueError):
        inventory.issue(MANIFEST_NAME, "backup_manifest_unreadable")


def inspect_recovery(boundary: RuntimeBoundary, role: ArtifactRole) -> RecoveryInspection:
    """Inspect only the explicit role; findings are never a cleanup capability.

    Status verified means a compatible complete application artifact at the
    observed snapshot, not investment readiness or a promise of unchanged state.
    """
    if role not in ("runtime", "backup", "interrupted_restore"):
        raise EvidenceError("invalid_artifact_role")
    inventory = _Inventory(boundary)
    databases: list[DatabaseObservation] = []
    try:
        boundary.check()
        if not boundary.root.is_dir():
            raise EvidenceError("runtime_missing")
        inventory.scan("", "root", role)
        _step("inventory_read")
        databases.append(_database(inventory, ""))
        if role == "interrupted_restore":
            inventory.issue(RESTORE_MARKER, "unbound_restore_requires_verified_recovery")
            if boundary.path("restore-work").is_dir():
                databases.append(_database(inventory, "restore-work/"))
        elif role == "backup":
            _backup(inventory, databases)
        elif MANIFEST_NAME in inventory.files or "manifest.part" in inventory.files:
            inventory.issue(MANIFEST_NAME, "artifact_role_mismatch")
        if RESTORE_MARKER in inventory.files:
            inventory.issue(RESTORE_MARKER, "restore_incomplete")
        _classify(inventory, databases)
        _step("inspection_verified")
        inventory.stable()
    except (EvidenceError, PersistenceError) as error:
        inventory.issue(".", error.code)
    except (OSError, sqlite3.Error):
        inventory.issue(".", "inspection_unavailable")
    return RecoveryInspection(
        role,
        "non_ready" if inventory.findings else "verified",
        tuple(databases),
        tuple(inventory.files[k] for k in sorted(inventory.files)),
        tuple(sorted(inventory.findings)),
    )
