"""Transactional advisory import/run authority, beside unchanged legacy readers.

All source bytes and saved records live in this SQLite file. T019.5 owns its
backup/restore adoption; legacy foundation backups do not include this file.
"""

import hashlib
import json
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from typing import Literal, Self, cast

from pydantic import JsonValue

from prosper.advisory_records import (
    AnalysisRun,
    Finding,
    ImportSnapshot,
    SavedSuggestion,
    encode,
)
from prosper.bundle import MAX_BYTES
from prosper.bundle_schema import Identifier
from prosper.evidence import RuntimeBoundary
from prosper.persistence import RESTORE_MARKER, PersistenceError

DATABASE_NAME = "advisory-v1.sqlite3"
APPLICATION_ID = 0x50524144
SCHEMA_VERSION = 1
_SCHEMA = (
    "CREATE TABLE sources (sha256 TEXT PRIMARY KEY, raw BLOB NOT NULL) STRICT",
    "CREATE TABLE snapshots (id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL "
    "REFERENCES sources(sha256), imported_at TEXT NOT NULL, state TEXT NOT NULL "
    "CHECK(state IN ('staged','selected','rejected')), document TEXT NOT NULL) STRICT",
    "CREATE TABLE state (id INTEGER PRIMARY KEY CHECK(id=1), "
    "revision INTEGER NOT NULL CHECK(revision>=0), "
    "snapshot_id TEXT REFERENCES snapshots(id), settings TEXT NOT NULL, "
    "current_run_id TEXT REFERENCES runs(id)) STRICT",
    "CREATE TABLE commands (key TEXT PRIMARY KEY, payload TEXT NOT NULL, "
    "result TEXT NOT NULL) STRICT",
    "CREATE TABLE runs (id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots(id), "
    "document TEXT NOT NULL) STRICT",
    "CREATE TABLE suggestions (id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), "
    "document TEXT NOT NULL) STRICT",
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _before_commit(connection: sqlite3.Connection) -> None:
    """Fault seam after writes, before commit; no user callback."""


class AdvisoryStore:
    @classmethod
    def existing(cls, runtime: RuntimeBoundary) -> Self:
        result = cls.__new__(cls)
        result.runtime = runtime
        with result._connection():
            pass
        return result

    def __init__(self, runtime: RuntimeBoundary) -> None:
        self.runtime = runtime
        runtime.check()
        try:
            runtime.root.mkdir(parents=True, exist_ok=True)
            self._guard()
            path = runtime.path(DATABASE_NAME)
            try:
                with path.open("xb"):
                    pass
            except FileExistsError:
                fresh = False
            else:
                fresh = True
        except OSError:
            raise PersistenceError("advisory_database_unavailable") from None
        with self._connection(initialize=fresh, write=True) as connection:
            if fresh:
                for statement in _SCHEMA:
                    connection.execute(statement)
                connection.execute("INSERT INTO state VALUES (1,0,NULL,'{}',NULL)")
                connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def _guard(self) -> None:
        if self.runtime.path(RESTORE_MARKER).exists():
            raise PersistenceError("restore_incomplete")
        for suffix in ("", "-journal", "-wal", "-shm"):
            path = self.runtime.path(DATABASE_NAME + suffix)
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise PersistenceError("untrusted_database_file")

    @contextmanager
    def _connection(
        self, *, initialize: bool = False, write: bool = False
    ) -> Iterator[sqlite3.Connection]:
        try:
            self._guard()
            path = self.runtime.path(DATABASE_NAME)
            with closing(
                sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None)
            ) as connection:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA trusted_schema=OFF")
                connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                try:
                    if not initialize:
                        if connection.execute("PRAGMA application_id").fetchone() != (
                            APPLICATION_ID,
                        ) or connection.execute("PRAGMA user_version").fetchone() != (
                            SCHEMA_VERSION,
                        ):
                            raise PersistenceError("incompatible_advisory_schema")
                    yield connection
                    if write:
                        _before_commit(connection)
                    self._guard()
                    connection.commit()
                except BaseException:
                    connection.rollback()
                    raise
        except (OSError, sqlite3.Error):
            raise PersistenceError("advisory_database_unavailable") from None
        except PersistenceError:
            raise
        except (ValueError, TypeError, OverflowError, RecursionError):
            raise PersistenceError("invalid_advisory_record") from None

    def stage(self, snapshot: ImportSnapshot, raw_source: bytes) -> str:
        with self._connection(write=True) as connection:
            document = encode(snapshot)
            # Revalidate nested mutable containers at the persistence boundary.
            snapshot = ImportSnapshot.model_validate_json(document)
            if (
                not isinstance(raw_source, bytes)
                or not 0 < len(raw_source) <= MAX_BYTES
                or hashlib.sha256(raw_source).hexdigest() != snapshot.source_sha256
            ):
                raise PersistenceError("source_checksum_or_size_invalid")
            identity = hashlib.sha256(document.encode()).hexdigest()
            connection.execute(
                "INSERT OR IGNORE INTO sources VALUES (?,?)",
                (snapshot.source_sha256, raw_source),
            )
            retained = connection.execute(
                "SELECT raw FROM sources WHERE sha256=?", (snapshot.source_sha256,)
            ).fetchone()
            if retained != (raw_source,):
                raise PersistenceError("source_unavailable_or_corrupt")
            connection.execute(
                "INSERT OR IGNORE INTO snapshots VALUES (?,?,?,'staged',?)",
                (identity, snapshot.source_sha256, _now(), document),
            )
            return identity

    @staticmethod
    def _snapshot(connection: sqlite3.Connection, identity: str) -> ImportSnapshot:
        row = connection.execute(
            "SELECT document,source_sha256 FROM snapshots WHERE id=?", (identity,)
        ).fetchone()
        if row is None:
            raise PersistenceError("snapshot_missing")
        snapshot = ImportSnapshot.model_validate_json(row[0])
        if snapshot.source_sha256 != row[1]:
            raise PersistenceError("snapshot_source_mismatch")
        return snapshot

    def snapshot(self, identity: str) -> ImportSnapshot:
        with self._connection() as connection:
            return self._snapshot(connection, identity)

    def source(self, identity: str) -> bytes:
        with self._connection() as connection:
            snapshot = self._snapshot(connection, identity)
            return self._source(connection, snapshot.source_sha256)

    @staticmethod
    def _source(connection: sqlite3.Connection, digest: str) -> bytes:
        row = connection.execute("SELECT raw FROM sources WHERE sha256=?", (digest,)).fetchone()
        if row is None or hashlib.sha256(row[0]).hexdigest() != digest:
            raise PersistenceError("source_unavailable_or_corrupt")
        return cast(bytes, row[0])

    def reject(self, identity: str) -> None:
        with self._connection(write=True) as connection:
            self._snapshot(connection, identity)
            state = connection.execute(
                "SELECT state FROM snapshots WHERE id=?", (identity,)
            ).fetchone()
            if state != ("staged",) and state != ("rejected",):
                raise PersistenceError("selected_snapshot_cannot_be_rejected")
            connection.execute("UPDATE snapshots SET state='rejected' WHERE id=?", (identity,))

    @staticmethod
    def _state(connection: sqlite3.Connection) -> dict[str, JsonValue]:
        row = connection.execute(
            "SELECT revision,snapshot_id,settings,current_run_id FROM state WHERE id=1"
        ).fetchone()
        if row is None:
            raise PersistenceError("advisory_state_missing")
        return {
            "revision": row[0],
            "snapshot_id": row[1],
            "settings": json.loads(row[2]),
            "current_run_id": row[3],
        }

    def current(self) -> dict[str, JsonValue]:
        with self._connection() as connection:
            state = self._state(connection)
            if state["snapshot_id"] is not None:
                self._snapshot(connection, cast(str, state["snapshot_id"]))
            return state

    def catalog(self) -> dict[str, JsonValue]:
        """Discover retained records including old imports and historical results."""
        with self._connection() as connection:
            return {
                "snapshots": [
                    dict(zip(("id", "imported_at", "state"), row, strict=True))
                    for row in connection.execute(
                        "SELECT id,imported_at,state FROM snapshots ORDER BY rowid"
                    )
                ],
                "runs": [
                    row[0] for row in connection.execute("SELECT id FROM runs ORDER BY rowid")
                ],
                "suggestions": [
                    row[0]
                    for row in connection.execute("SELECT id FROM suggestions ORDER BY rowid")
                ],
            }

    def select(
        self, identity: str, command_key: str, expected_revision: int
    ) -> dict[str, JsonValue]:
        return self._change("select", identity, command_key, expected_revision)

    def configure(
        self, settings: dict[str, JsonValue], command_key: str, expected_revision: int
    ) -> dict[str, JsonValue]:
        if not isinstance(settings, dict):
            raise PersistenceError("invalid_advisory_record")
        return self._change("settings", settings, command_key, expected_revision)

    def _change(
        self, operation: str, value: JsonValue, key: str, expected: int
    ) -> dict[str, JsonValue]:
        with self._connection(write=True) as connection:
            # Reuse the closed identifier shape without a new key convention.
            from pydantic import TypeAdapter

            TypeAdapter(Identifier).validate_python(key, strict=True)
            if type(expected) is not int or not 0 <= expected < 2**63 - 1:
                raise PersistenceError("invalid_revision")
            payload = encode({"operation": operation, "value": value, "expected": expected})
            prior = connection.execute(
                "SELECT payload,result FROM commands WHERE key=?", (key,)
            ).fetchone()
            if prior is not None:
                if prior[0] != payload:
                    raise PersistenceError("command_key_reused")
                return cast(dict[str, JsonValue], json.loads(prior[1]))
            state = self._state(connection)
            outcome = "stale_revision"
            if expected == state["revision"]:
                if operation == "select":
                    snapshot = self._snapshot(connection, cast(str, value))
                    row = connection.execute(
                        "SELECT state FROM snapshots WHERE id=?", (value,)
                    ).fetchone()
                    current = state["snapshot_id"]
                    old = self._snapshot(connection, cast(str, current)) if current else None
                    if row == ("rejected",):
                        outcome = "preview_rejected"
                    elif old and (old.account_id, old.account_scope) != (
                        snapshot.account_id,
                        snapshot.account_scope,
                    ):
                        outcome = "account_review_required"
                    elif current == value:
                        outcome = "duplicate"
                    else:
                        self._source(connection, snapshot.source_sha256)
                        connection.execute(
                            "UPDATE snapshots SET state='selected' WHERE id=?", (value,)
                        )
                        connection.execute("UPDATE state SET snapshot_id=? WHERE id=1", (value,))
                        outcome = "changed"
                elif state["settings"] == value:
                    outcome = "duplicate"
                else:
                    connection.execute(
                        "UPDATE state SET settings=? WHERE id=1",
                        (encode(cast(dict[str, JsonValue], value)),),
                    )
                    outcome = "changed"
                if outcome == "changed":
                    connection.execute(
                        "UPDATE state SET revision=revision+1,current_run_id=NULL WHERE id=1"
                    )
            result: dict[str, JsonValue] = {
                "outcome": outcome,
                "revision": self._state(connection)["revision"],
            }
            connection.execute(
                "INSERT INTO commands VALUES (?,?,?)", (key, payload, encode(result))
            )
            return result

    @staticmethod
    def _run(connection: sqlite3.Connection, identity: str) -> AnalysisRun:
        row = connection.execute("SELECT document FROM runs WHERE id=?", (identity,)).fetchone()
        if row is None:
            raise PersistenceError("analysis_missing")
        return AnalysisRun.model_validate_json(row[0])

    def run(self, identity: str) -> AnalysisRun:
        with self._connection() as connection:
            return self._run(connection, identity)

    def start_run(
        self,
        identity: str,
        expected_revision: int,
        *,
        inputs: dict[str, JsonValue],
        application_version: str,
        model_version: str,
        as_of: str,
    ) -> AnalysisRun:
        with self._connection(write=True) as connection:
            prior = connection.execute("SELECT id FROM runs WHERE id=?", (identity,)).fetchone()
            if prior:
                saved = self._run(connection, identity)
                if (
                    saved.input_revision,
                    saved.inputs,
                    saved.application_version,
                    saved.model_version,
                    saved.as_of,
                ) != (expected_revision, inputs, application_version, model_version, as_of):
                    raise PersistenceError("analysis_id_reused")
                return saved
            state = self._state(connection)
            if type(expected_revision) is not int or state["revision"] != expected_revision:
                raise PersistenceError("stale_revision")
            if state["snapshot_id"] is None:
                raise PersistenceError("selected_snapshot_required")
            result = AnalysisRun(
                id=identity,
                snapshot_id=cast(str, state["snapshot_id"]),
                input_revision=expected_revision,
                settings=cast(dict[str, JsonValue], state["settings"]),
                inputs=inputs,
                application_version=application_version,
                model_version=model_version,
                as_of=as_of,
                started_at=_now(),
            )
            connection.execute(
                "INSERT INTO runs VALUES (?,?,?)", (identity, result.snapshot_id, encode(result))
            )
            return result

    def complete_run(
        self,
        identity: str,
        *,
        outputs: dict[str, JsonValue],
        status: Literal["complete", "partial", "failed"],
        exclusions: tuple[Finding, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> AnalysisRun:
        with self._connection(write=True) as connection:
            saved = self._run(connection, identity)
            changes = {
                "outputs": outputs,
                "status": status,
                "exclusions": exclusions,
                "warnings": warnings,
            }
            result = saved.model_copy(
                update={**changes, "completed_at": saved.completed_at or _now()}
            )
            result = AnalysisRun.model_validate_json(encode(result))
            if saved.completed_at is not None:
                if result != saved:
                    raise PersistenceError("completed_analysis_is_immutable")
                return saved
            connection.execute("UPDATE runs SET document=? WHERE id=?", (encode(result), identity))
            state = self._state(connection)
            if state["revision"] == result.input_revision and status in ("complete", "partial"):
                # Within a revision, the most recently started run wins, even if
                # workers finish out of order. Compare SQLite insertion order.
                latest = connection.execute(
                    "SELECT id FROM runs ORDER BY rowid DESC LIMIT 1"
                ).fetchone()
                if latest == (identity,):
                    connection.execute("UPDATE state SET current_run_id=? WHERE id=1", (identity,))
            return result

    def save_suggestion(self, suggestion: SavedSuggestion) -> SavedSuggestion:
        with self._connection(write=True) as connection:
            document = encode(suggestion)
            suggestion = SavedSuggestion.model_validate_json(document)
            run = self._run(connection, suggestion.run_id)
            if run.status not in ("complete", "partial"):
                raise PersistenceError("completed_analysis_required")
            prior = connection.execute(
                "SELECT document FROM suggestions WHERE id=?", (suggestion.id,)
            ).fetchone()
            if prior and prior[0] != document:
                raise PersistenceError("saved_suggestion_is_immutable")
            connection.execute(
                "INSERT OR IGNORE INTO suggestions VALUES (?,?,?)",
                (suggestion.id, suggestion.run_id, document),
            )
            return suggestion

    def suggestion(self, identity: str) -> SavedSuggestion:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT document FROM suggestions WHERE id=?", (identity,)
            ).fetchone()
            if row is None:
                raise PersistenceError("suggestion_missing")
            return SavedSuggestion.model_validate_json(row[0])
