"""Durable synthetic preview/rejection, shared by the atomic import service."""

import hashlib
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from prosper.bundle import MAX_BYTES, Issue, ParseResult, parse_bundle
from prosper.checkpoint import Inspection, inspect_checkpoint
from prosper.evidence import EvidenceReceipt
from prosper.persistence import CheckpointStore, PersistenceError, _check_recorded_time

PREVIEW_VERSION = "synthetic-preview-v1"


class PreviewError(PersistenceError):
    """Safe error code and bounded input issues, without source payload or paths."""

    def __init__(self, code: str, issues: tuple[Issue, ...] = ()) -> None:
        self.issues = issues
        super().__init__(code)


@dataclass(frozen=True)
class ImportPreview:
    receipt: EvidenceReceipt
    recorded_at: str
    state: Literal["staged", "rejected", "committed"]
    rejected_at: str | None
    parsing: ParseResult
    inspection: Inspection | None
    version: str = PREVIEW_VERSION


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _before_preview_commit(connection: sqlite3.Connection) -> None:
    """Fault-injection seam after real preview INSERT/UPDATE, before commit."""


class PreviewService:
    """One staged identity per original byte hash. Rejection never revives it.

    Uses the checkpoint repository's guarded connection/schema boundary; does
    not append checkpoints. Readiness is reconstructed from verified evidence,
    not accepted from callers or trusted from cached diagnostic JSON.
    """

    def __init__(self, store: CheckpointStore) -> None:
        self.store = store

    @staticmethod
    def _identity(identity: str) -> None:
        if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{64}", identity):
            raise PreviewError("invalid_preview_identity")

    def _load(self, row: tuple[object, ...]) -> ImportPreview:
        if (
            len(row) != 8
            or any(not isinstance(row[i], str) for i in (0, 1, 2, 4, 6, 7))
            or type(row[5]) is not int
            or row[7] != PREVIEW_VERSION
            or row[2] not in ("staged", "rejected", "committed")
        ):
            raise PreviewError("stored_preview_metadata_mismatch")
        recorded = cast(str, row[1])
        started = _check_recorded_time(recorded)
        rejected = row[3]
        if row[2] in ("staged", "committed"):
            if rejected is not None:
                raise PreviewError("stored_preview_transition_invalid")
        elif not isinstance(rejected, str) or _check_recorded_time(rejected) < started:
            raise PreviewError("stored_preview_transition_invalid")
        receipt = EvidenceReceipt(cast(str, row[0]), row[5], cast(str, row[6]), cast(str, row[4]))
        raw = self.store.evidence.read(receipt)
        parsing = parse_bundle(raw)
        inspection = inspect_checkpoint(parsing.parsed) if parsing.parsed is not None else None
        return ImportPreview(
            receipt,
            recorded,
            row[2],
            rejected,
            parsing,
            inspection,
        )

    def _row(self, connection: sqlite3.Connection, identity: str) -> ImportPreview:
        row = connection.execute(
            "SELECT * FROM import_previews WHERE raw_sha256=?", (identity,)
        ).fetchone()
        if row is None:
            raise PreviewError("preview_missing")
        result = self._load(cast(tuple[object, ...], row))
        if result.state == "committed":
            activation = connection.execute(
                "SELECT generation FROM import_activations WHERE raw_sha256=?", (identity,)
            ).fetchone()
            checkpoint = connection.execute(
                "SELECT * FROM checkpoints WHERE raw_sha256=?", (identity,)
            ).fetchone()
            if activation is None or checkpoint is None:
                raise PreviewError("stored_preview_transition_invalid")
            self.store._load(cast(tuple[object, ...], checkpoint))
        return result

    def get(self, identity: str) -> ImportPreview:
        self._identity(identity)
        try:
            with closing(self.store._connect()) as connection:
                self.store._check_schema(connection)
                return self._row(connection, identity)
        except sqlite3.Error:
            raise PreviewError("preview_read_failed") from None

    def stage(self, raw: bytes) -> ImportPreview:
        # Fail before hashing/publication for unbounded or non-byte payloads.
        if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
            raise PreviewError("preview_input_rejected", parse_bundle(raw).issues)
        identity = hashlib.sha256(raw).hexdigest()
        return self._write(identity, raw)

    def reject(self, identity: str) -> ImportPreview:
        self._identity(identity)
        return self._write(identity, None)

    def _write(self, identity: str, raw: bytes | None) -> ImportPreview:
        try:
            with closing(self.store._connect()) as connection:
                self.store._check_schema(connection)
                connection.execute("BEGIN IMMEDIATE")
                try:
                    existing = connection.execute(
                        "SELECT * FROM import_previews WHERE raw_sha256=?", (identity,)
                    ).fetchone()
                    if existing is None:
                        if raw is None:
                            raise PreviewError("preview_missing")
                        checkpoint = connection.execute(
                            "SELECT * FROM checkpoints WHERE raw_sha256=?", (identity,)
                        ).fetchone()
                        if checkpoint is not None:
                            # New staging cannot silently repair evidence that
                            # an existing immutable checkpoint already requires.
                            self.store._load(cast(tuple[object, ...], checkpoint))
                        receipt = self.store.evidence.publish(raw)
                        connection.execute(
                            "INSERT INTO import_previews VALUES (?, ?, 'staged', NULL, ?, ?, ?, ?)",
                            (
                                identity,
                                _now(),
                                receipt.storage_version,
                                receipt.byte_length,
                                receipt.relative_reference,
                                PREVIEW_VERSION,
                            ),
                        )
                    else:
                        prior = self._load(cast(tuple[object, ...], existing))
                        if raw is None and prior.state == "committed":
                            raise PreviewError("committed_preview_cannot_reject")
                        if raw is None and prior.state == "staged":
                            connection.execute(
                                "UPDATE import_previews SET state='rejected', rejected_at=? "
                                "WHERE raw_sha256=?",
                                (_now(), identity),
                            )
                    _before_preview_commit(connection)
                    result = self._row(connection, identity)
                    self.store._guard_paths()
                    connection.commit()
                    return result
                except BaseException:
                    connection.rollback()
                    raise
        except sqlite3.Error:
            raise PreviewError("preview_write_failed") from None
