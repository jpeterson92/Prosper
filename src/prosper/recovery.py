"""Versioned consistent backups and isolated restore of the synthetic foundation.

Only manifest-complete backups qualify. Restore publishes the verified database
last; failed work is retained, never cleaned up here. Hashes detect corruption,
not malicious replacement. RuntimeBoundary's path/race/ACL limitations apply.
"""

import hashlib
import json
import os
import re
import sqlite3
import stat
import sys
from contextlib import closing
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from prosper.bundle import MAX_BYTES
from prosper.evidence import (
    STORAGE_VERSION,
    EvidenceError,
    EvidenceReceipt,
    EvidenceStore,
    RuntimeBoundary,
    _publish,
    _write_staged,
)
from prosper.imports import ImportService, _decode
from prosper.persistence import (
    DATABASE_NAME,
    RESTORE_MARKER,
    SCHEMA_VERSION,
    CheckpointStore,
    PersistenceError,
    _check_recorded_time,
)
from prosper.previews import _now

MANIFEST_NAME = "backup-manifest-v1.json"
MAX_DATABASE_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_OBJECTS = 10_000
type Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type Count = Annotated[int, Field(ge=0, le=2**63 - 1)]


class RecoveryError(PersistenceError):
    """Stable non-ready code without local paths, financial payloads or SQL text."""


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class BackupFile(_Closed):
    reference: str
    sha256: Digest
    byte_length: Count


class StateSummary(_Closed):
    checkpoints: Count
    previews: Count
    commands: Count
    generation: Count


class BackupManifest(_Closed):
    format: Literal["prosper-foundation-backup-v1"] = "prosper-foundation-backup-v1"
    application: Literal["prosper-local"] = "prosper-local"
    application_version: str
    implementation_sha256: Digest
    candidate_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]
    schema_version: int
    created_at: str
    database: BackupFile
    evidence: Annotated[tuple[BackupFile, ...], Field(max_length=MAX_OBJECTS)]
    state: StateSummary
    excluded: Literal["caches-and-unreferenced-files"] = "caches-and-unreferenced-files"


def implementation_identity() -> str:
    """Hash actual installed Python sources and runtime dependency versions.

    The candidate label is caller provenance; this fingerprint independently
    identifies the implementation. No Git subprocess or checkout is required.
    """
    package = Path(__file__).parent
    identity = {
        "sources": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(package.glob("*.py"))
        },
        "versions": {
            name: version(name) for name in ("prosper-local", "pydantic", "pydantic-core")
        },
        "python": list(sys.version_info[:2]),
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def _separate(first: RuntimeBoundary, second: RuntimeBoundary) -> None:
    first.check()
    second.check()
    a, b = first.root.resolve(), second.root.resolve()
    if a.is_relative_to(b) or b.is_relative_to(a) or first.mode != second.mode:
        raise RecoveryError("recovery_boundary_overlap_or_mode")


def _reserve(destination: RuntimeBoundary) -> None:
    destination.check()
    try:
        destination.root.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise RecoveryError("destination_exists") from None
    destination.check()


def _file(boundary: RuntimeBoundary, reference: str, limit: int) -> BackupFile:
    path = boundary.path(reference)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RecoveryError("untrusted_backup_file")
    if info.st_size > limit:
        raise RecoveryError("backup_size_exceeded")
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise RecoveryError("untrusted_backup_file")
        while chunk := stream.read(min(1024 * 1024, limit + 1 - length)):
            length += len(chunk)
            if length > limit:
                raise RecoveryError("backup_size_exceeded")
            digest.update(chunk)
    return BackupFile(reference=reference, sha256=digest.hexdigest(), byte_length=length)


def _copy(source: RuntimeBoundary, target: RuntimeBoundary, item: BackupFile, limit: int) -> None:
    if _file(source, item.reference, limit) != item:
        raise RecoveryError("backup_identity_mismatch")
    destination = target.path(item.reference)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.path(item.reference).open("rb") as incoming, destination.open("xb") as outgoing:
        length = 0
        while chunk := incoming.read(min(1024 * 1024, limit + 1 - length)):
            length += len(chunk)
            if length > limit:
                raise RecoveryError("backup_size_exceeded")
            outgoing.write(chunk)
        outgoing.flush()
        os.fsync(outgoing.fileno())
    if _file(target, item.reference, limit) != item:
        raise RecoveryError("backup_identity_mismatch")


def _receipt(item: BackupFile) -> EvidenceReceipt:
    return EvidenceReceipt(item.sha256, item.byte_length, item.reference)


def _verify_state(store: CheckpointStore) -> tuple[StateSummary, tuple[EvidenceReceipt, ...]]:
    """Reconstruct every row, including inactive checkpoints and failed commands."""
    service = ImportService(store)
    receipts: dict[str, EvidenceReceipt] = {}
    with closing(store._connect()) as connection:
        connection.execute("BEGIN")
        store._check_schema(connection)
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise RecoveryError("backup_database_corrupt")
        checkpoints = connection.execute("SELECT * FROM checkpoints ORDER BY sequence").fetchall()
        previews = connection.execute(
            "SELECT * FROM import_previews ORDER BY raw_sha256"
        ).fetchall()
        for row in checkpoints:
            receipt = store._load(cast(tuple[object, ...], row)).receipt
            receipts[receipt.relative_reference] = receipt
        for row in previews:
            receipt = service.previews._row(connection, row[0]).receipt
            prior = receipts.get(receipt.relative_reference, receipt)
            if prior != receipt:
                raise RecoveryError("backup_reference_mismatch")
            receipts[receipt.relative_reference] = receipt
        history = service._history(connection)
        commands = connection.execute("SELECT * FROM import_commands").fetchall()
        for row in commands:
            command = _decode(cast(tuple[object, ...], row))
            preview = service.previews._row(connection, command.preview_sha256)
            if (
                command.generation > len(history)
                or _check_recorded_time(command.recorded_at)
                < _check_recorded_time(preview.recorded_at)
                or (
                    command.activation_generation is not None
                    and history[command.activation_generation - 1].receipt.raw_sha256
                    != command.preview_sha256
                )
            ):
                raise RecoveryError("backup_command_relation_invalid")
        if len(receipts) > MAX_OBJECTS:
            raise RecoveryError("backup_size_exceeded")
        return (
            StateSummary(
                checkpoints=len(checkpoints),
                previews=len(previews),
                commands=len(commands),
                generation=len(history),
            ),
            tuple(receipts[key] for key in sorted(receipts)),
        )


def _references(boundary: RuntimeBoundary) -> tuple[EvidenceReceipt, ...]:
    """Read reference metadata from a snapshot, without opening any evidence paths."""
    database = boundary.path(DATABASE_NAME)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA trusted_schema=OFF")
        CheckpointStore._check_schema(connection)
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise RecoveryError("backup_database_corrupt")
        rows = connection.execute(
            "SELECT raw_sha256, evidence_length, evidence_reference, evidence_version "
            "FROM checkpoints UNION "
            "SELECT raw_sha256, evidence_length, evidence_reference, evidence_version "
            "FROM import_previews LIMIT ?",
            (MAX_OBJECTS + 1,),
        ).fetchall()
        if len(rows) > MAX_OBJECTS:
            raise RecoveryError("backup_size_exceeded")
        receipts = tuple(EvidenceReceipt(*row) for row in rows)
        if len({item.relative_reference for item in receipts}) != len(receipts):
            raise RecoveryError("backup_reference_mismatch")
        return tuple(sorted(receipts, key=lambda item: item.relative_reference))


def _step(name: str) -> None:
    """Fault-injection seam for actual completed backup/restore boundaries."""


def backup(
    store: CheckpointStore, destination: RuntimeBoundary, *, candidate_id: str
) -> BackupManifest:
    """Create a new backup; only a complete manifest marks it usable."""
    try:
        if (
            not isinstance(candidate_id, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", candidate_id) is None
        ):
            raise RecoveryError("invalid_candidate_identity")
        _separate(store.evidence.runtime, destination)
        _reserve(destination)
        snapshot = destination.path(DATABASE_NAME)
        with snapshot.open("xb"):
            pass
        with closing(store._connect()) as source, closing(sqlite3.connect(snapshot)) as target:
            store._check_schema(source)
            source.backup(target)
        _file(destination, DATABASE_NAME, MAX_DATABASE_BYTES)
        _step("backup_snapshot")
        references = _references(destination)
        for receipt in references:
            raw = store.evidence.read(receipt)
            path = destination.path(receipt.relative_reference)
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_staged(path, raw)
        _step("backup_evidence")
        verified = CheckpointStore(EvidenceStore(destination))
        state, verified_references = _verify_state(verified)
        if references != verified_references:
            raise RecoveryError("backup_reference_mismatch")
        manifest = BackupManifest(
            application_version=version("prosper-local"),
            implementation_sha256=implementation_identity(),
            candidate_id=candidate_id,
            schema_version=SCHEMA_VERSION,
            created_at=_now(),
            database=_file(destination, DATABASE_NAME, MAX_DATABASE_BYTES),
            evidence=tuple(
                _file(destination, receipt.relative_reference, MAX_BYTES) for receipt in references
            ),
            state=state,
        )
        payload = manifest.model_dump_json().encode()
        if len(payload) > MAX_MANIFEST_BYTES:
            raise RecoveryError("backup_size_exceeded")
        staged = destination.path("manifest.part")
        _write_staged(staged, payload)
        _step("backup_verified")
        _publish(staged, destination.path(MANIFEST_NAME))
        return manifest
    except RecoveryError:
        raise
    except (OSError, sqlite3.Error, EvidenceError, PersistenceError, ValidationError):
        raise RecoveryError("backup_failed") from None


def _manifest(source: RuntimeBoundary) -> BackupManifest:
    _file(source, MANIFEST_NAME, MAX_MANIFEST_BYTES)

    # Validate exact JSON syntax, including duplicate keys, before closed-model validation.
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        values = dict(pairs)
        if len(values) != len(pairs):
            raise RecoveryError("backup_manifest_invalid")
        return values

    with source.path(MANIFEST_NAME).open("rb") as stream:
        payload = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(payload) > MAX_MANIFEST_BYTES:
        raise RecoveryError("backup_size_exceeded")
    json.loads(payload, object_pairs_hook=unique)
    manifest = BackupManifest.model_validate_json(payload)
    _check_recorded_time(manifest.created_at)
    if (
        manifest.schema_version != SCHEMA_VERSION
        or manifest.application_version != version("prosper-local")
        or manifest.implementation_sha256 != implementation_identity()
        or manifest.database.reference != DATABASE_NAME
        or manifest.database.byte_length > MAX_DATABASE_BYTES
    ):
        raise RecoveryError("incompatible_backup")
    receipts = tuple(_receipt(item) for item in manifest.evidence)
    if tuple(sorted({r.relative_reference for r in receipts})) != tuple(
        r.relative_reference for r in receipts
    ):
        raise RecoveryError("backup_manifest_invalid")
    return manifest


def restore(source: RuntimeBoundary, destination: RuntimeBoundary) -> BackupManifest:
    """Restore to a new runtime, publishing its database only after full verification.

    No source database is opened for mutation. Failed/interrupted destination
    files remain for inspection and a retry must choose a different empty root.
    """
    try:
        _separate(source, destination)
        manifest = _manifest(source)
        _reserve(destination)
        _write_staged(destination.path(RESTORE_MARKER), b"isolated-restore-v1\n")
        work = RuntimeBoundary(
            destination.path("restore-work"), destination.source_root, destination.mode
        )
        work.root.mkdir()
        _copy(source, work, manifest.database, MAX_DATABASE_BYTES)
        for item in manifest.evidence:
            _copy(source, work, item, MAX_BYTES)
        _step("restore_copied")
        # Refuse old/incompatible schemas before CheckpointStore can upgrade anything.
        references = _references(work)
        if references != tuple(_receipt(item) for item in manifest.evidence):
            raise RecoveryError("backup_reference_mismatch")
        state, verified_references = _verify_state(CheckpointStore(EvidenceStore(work)))
        if state != manifest.state or references != verified_references:
            raise RecoveryError("backup_state_mismatch")
        if _file(work, DATABASE_NAME, MAX_DATABASE_BYTES) != manifest.database:
            raise RecoveryError("backup_identity_mismatch")
        _step("restore_verified")
        # The reserved destination is ours. Evidence first; no database can be
        # opened there until every required immutable object has been verified.
        work.path(STORAGE_VERSION).rename(destination.path(STORAGE_VERSION))
        _step("restore_evidence_published")
        staged = work.path(DATABASE_NAME)
        with staged.open("r+b") as stream:
            os.fsync(stream.fileno())
        os.link(staged, destination.path(DATABASE_NAME))
        _step("restore_database_linked")
        # An interruption before unlink leaves a multiply linked, non-ready DB.
        # The marker still blocks opening until publication is complete.
        staged.unlink()
        _step("restore_database_published")
        destination.path(RESTORE_MARKER).unlink()
        return manifest
    except RecoveryError:
        raise
    except (OSError, sqlite3.Error, EvidenceError, PersistenceError, ValidationError, ValueError):
        raise RecoveryError("restore_failed") from None
