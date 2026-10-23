"""Exact immutable synthetic checkpoints, not active imports or recovery.

Canonical JSON is authoritative TEXT, including explicit null/reason pairs.
Original bytes reconstruct source spelling/quantum. No SQL book arithmetic.
"""

import re
import sqlite3
import stat
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from prosper.bundle import ParsedBundle, parse_bundle
from prosper.bundle_schema import CANONICALIZATION_VERSION
from prosper.checkpoint import Inspection, ValidatedCheckpoint, inspect_checkpoint
from prosper.evidence import EvidenceReceipt, EvidenceStore

STORAGE_VERSION = "checkpoint-sqlite-v1"
DATABASE_NAME = "checkpoints-v1.sqlite3"
APPLICATION_ID = 0x50525350
SCHEMA_VERSION = 2
_COLUMNS = (
    "raw_sha256",
    "canonical_sha256",
    "canonical_text",
    "schema_version",
    "semantics_version",
    "canonicalization_version",
    "storage_version",
    "source_id",
    "source_version",
    "bundle_id",
    "profile_id",
    "effective_at",
    "recorded_at",
    "evidence_version",
    "evidence_length",
    "evidence_reference",
    "inspection_version",
)
_SCHEMA = """CREATE TABLE checkpoints (
    sequence INTEGER PRIMARY KEY,
    raw_sha256 TEXT NOT NULL UNIQUE,
    canonical_sha256 TEXT NOT NULL,
    canonical_text TEXT NOT NULL CHECK(json_valid(canonical_text)),
    schema_version TEXT NOT NULL,
    semantics_version TEXT NOT NULL,
    canonicalization_version TEXT NOT NULL,
    storage_version TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_version TEXT NOT NULL,
    bundle_id TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    evidence_version TEXT NOT NULL,
    evidence_length INTEGER NOT NULL CHECK(evidence_length >= 0),
    evidence_reference TEXT NOT NULL,
    inspection_version TEXT NOT NULL
) STRICT"""
_PREVIEW_SCHEMA = """CREATE TABLE import_previews (
    raw_sha256 TEXT PRIMARY KEY NOT NULL,
    recorded_at TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('staged', 'rejected')),
    rejected_at TEXT,
    evidence_version TEXT NOT NULL,
    evidence_length INTEGER NOT NULL CHECK(evidence_length >= 0),
    evidence_reference TEXT NOT NULL,
    preview_version TEXT NOT NULL,
    CHECK((state = 'staged' AND rejected_at IS NULL) OR
          (state = 'rejected' AND rejected_at IS NOT NULL))
) STRICT"""


class PersistenceError(ValueError):
    """Coded non-ready state without source payload, paths or SQL/OS details."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class StoredCheckpoint:
    sequence: int
    recorded_at: str
    receipt: EvidenceReceipt
    inspection: Inspection


def _inspect(raw: bytes) -> Inspection:
    result = parse_bundle(raw)
    if result.parsed is None:
        raise PersistenceError("stored_input_invalid")
    inspection = inspect_checkpoint(result.parsed)
    if inspection.validated is None:
        raise PersistenceError("checkpoint_not_validated")
    return inspection


def _values(
    source: ParsedBundle, receipt: EvidenceReceipt, recorded: str, inspection_version: str
) -> tuple[str | int, ...]:
    meta = source.document.metadata
    return (
        source.raw_sha256,
        source.canonical_sha256,
        source.canonical_bytes.decode("utf-8"),
        meta.schema_version,
        meta.semantics_version,
        CANONICALIZATION_VERSION,
        STORAGE_VERSION,
        meta.source_id,
        meta.source_version,
        meta.bundle_id,
        meta.profile_id,
        meta.cutoff,
        recorded,
        receipt.storage_version,
        receipt.byte_length,
        receipt.relative_reference,
        inspection_version,
    )


def _before_commit(connection: sqlite3.Connection) -> None:
    """Fault-injection seam after real INSERTs; no application hook or side effect."""


def _before_upgrade_commit(connection: sqlite3.Connection) -> None:
    """Fault-injection seam for the single known version-one upgrade."""


def _check_recorded_time(value: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value)
        if (
            moment.tzinfo != UTC
            or moment.isoformat(timespec="microseconds").replace("+00:00", "Z") != value
        ):
            raise ValueError()
    except ValueError:
        raise PersistenceError("stored_recorded_time_invalid") from None
    return moment


class CheckpointStore:
    """Short-lived connections; repeated identical raw input reuses its first row.

    New raw versions append even for an existing source ID; storing a version
    does not accept a correction or select it as the active portfolio.
    """

    def __init__(self, evidence: EvidenceStore) -> None:
        self.evidence = evidence
        self._guard_paths()
        path = evidence.runtime.path(DATABASE_NAME)
        try:
            # Only initialize a file this operation created exclusively. Existing
            # empty/foreign/incompatible databases are never silently initialized.
            try:
                with path.open("xb"):
                    pass
            except FileExistsError:
                fresh = False
            else:
                fresh = True
            with closing(self._connect()) as connection:
                if fresh:
                    connection.execute("BEGIN IMMEDIATE")
                    try:
                        connection.execute(_SCHEMA)
                        connection.execute(_PREVIEW_SCHEMA)
                        connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                        connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                        self._guard_paths()
                        connection.commit()
                    except BaseException:
                        connection.rollback()
                        raise
                else:
                    # Inspect and upgrade under the same lock. Never repair an
                    # altered schema or initialize an existing empty database.
                    connection.execute("BEGIN IMMEDIATE")
                    try:
                        if connection.execute("PRAGMA user_version").fetchone() == (1,):
                            self._check_schema(connection, version=1)
                            connection.execute(_PREVIEW_SCHEMA)
                            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                            _before_upgrade_commit(connection)
                        self._check_schema(connection)
                        self._guard_paths()
                        connection.commit()
                    except BaseException:
                        connection.rollback()
                        raise
                self._check_schema(connection)
        except (OSError, sqlite3.Error):
            raise PersistenceError("database_initialization_failed") from None

    def _guard_paths(self) -> None:
        for suffix in ("", "-journal", "-wal", "-shm"):
            path = self.evidence.runtime.path(DATABASE_NAME + suffix)
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            except OSError:
                raise PersistenceError("database_path_unavailable") from None
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise PersistenceError("untrusted_database_file")

    def _connect(self) -> sqlite3.Connection:
        self._guard_paths()
        path = self.evidence.runtime.path(DATABASE_NAME)
        connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None)
        try:
            connection.execute("PRAGMA trusted_schema=OFF")
        except BaseException:
            connection.close()
            raise
        return connection

    @staticmethod
    def _check_schema(connection: sqlite3.Connection, *, version: int = SCHEMA_VERSION) -> None:
        expected = [("table", "checkpoints", _SCHEMA)]
        if version == SCHEMA_VERSION:
            expected.append(("table", "import_previews", _PREVIEW_SCHEMA))
        if (
            connection.execute("PRAGMA application_id").fetchone() != (APPLICATION_ID,)
            or connection.execute("PRAGMA user_version").fetchone() != (version,)
            or connection.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE name NOT GLOB 'sqlite_*' ORDER BY name"
            ).fetchall()
            != expected
        ):
            raise PersistenceError("incompatible_database_schema")

    def _load(self, row: tuple[object, ...]) -> StoredCheckpoint:
        if len(row) != len(_COLUMNS) + 1 or type(row[0]) is not int or row[0] < 1:
            raise PersistenceError("stored_metadata_mismatch")
        if any(not isinstance(row[i], str) for i in range(1, len(row)) if i != 15):
            raise PersistenceError("stored_metadata_mismatch")
        if type(row[15]) is not int:
            raise PersistenceError("stored_metadata_mismatch")
        recorded = cast(str, row[13])
        _check_recorded_time(recorded)
        receipt = EvidenceReceipt(
            cast(str, row[1]), row[15], cast(str, row[16]), cast(str, row[14])
        )
        inspection = _inspect(self.evidence.read(receipt))
        expected = _values(inspection.source, receipt, recorded, inspection.version)
        if row[1:] != expected:
            raise PersistenceError("stored_metadata_mismatch")
        return StoredCheckpoint(row[0], recorded, receipt, inspection)

    def get(self, raw_sha256: str) -> StoredCheckpoint:
        if not isinstance(raw_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", raw_sha256):
            raise PersistenceError("invalid_checkpoint_identity")
        try:
            with closing(self._connect()) as connection:
                self._check_schema(connection)
                row = connection.execute(
                    "SELECT * FROM checkpoints WHERE raw_sha256=?", (raw_sha256,)
                ).fetchone()
                if row is None:
                    raise PersistenceError("checkpoint_missing")
                return self._load(cast(tuple[object, ...], row))
        except sqlite3.Error:
            raise PersistenceError("database_read_failed") from None

    def list_ids(self) -> tuple[str, ...]:
        """Storage inventory only; callers use get() to obtain verified content."""
        try:
            with closing(self._connect()) as connection:
                self._check_schema(connection)
                return tuple(
                    cast(str, row[0])
                    for row in connection.execute(
                        "SELECT raw_sha256 FROM checkpoints ORDER BY sequence"
                    )
                )
        except sqlite3.Error:
            raise PersistenceError("database_read_failed") from None

    def append(
        self, checkpoint: ValidatedCheckpoint, receipt: EvidenceReceipt | None = None
    ) -> StoredCheckpoint:
        if not isinstance(checkpoint, ValidatedCheckpoint):
            raise PersistenceError("validated_checkpoint_required")
        inspection = _inspect(checkpoint.source.raw_bytes)
        if inspection.validated != checkpoint:
            raise PersistenceError("checkpoint_identity_mismatch")
        if receipt is not None and self.evidence.read(receipt) != checkpoint.source.raw_bytes:
            raise PersistenceError("evidence_checkpoint_mismatch")
        try:
            with closing(self._connect()) as connection:
                self._check_schema(connection)
                connection.execute("BEGIN IMMEDIATE")
                try:
                    existing = connection.execute(
                        "SELECT * FROM checkpoints WHERE raw_sha256=?",
                        (checkpoint.source.raw_sha256,),
                    ).fetchone()
                    if existing is not None:
                        stored = self._load(cast(tuple[object, ...], existing))
                    else:
                        if receipt is None:
                            receipt = self.evidence.publish(checkpoint.source.raw_bytes)
                        if self.evidence.read(receipt) != checkpoint.source.raw_bytes:
                            raise PersistenceError("evidence_checkpoint_mismatch")
                        recorded = (
                            datetime.now(UTC)
                            .isoformat(timespec="microseconds")
                            .replace("+00:00", "Z")
                        )
                        columns = ",".join(_COLUMNS)
                        placeholders = ",".join("?" for _ in _COLUMNS)
                        connection.execute(
                            f"INSERT INTO checkpoints ({columns}) VALUES ({placeholders})",
                            _values(inspection.source, receipt, recorded, inspection.version),
                        )
                        row = connection.execute(
                            "SELECT * FROM checkpoints WHERE raw_sha256=?", (receipt.raw_sha256,)
                        ).fetchone()
                        stored = self._load(cast(tuple[object, ...], row))
                        _before_commit(connection)
                    self._guard_paths()
                    self.evidence.read(stored.receipt)
                    connection.commit()
                    return stored
                except BaseException:
                    connection.rollback()
                    raise
        except sqlite3.Error:
            raise PersistenceError("database_append_failed") from None
