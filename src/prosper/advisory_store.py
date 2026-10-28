"""Transactional current advisory authority, including original source bytes."""

import hashlib
import json
import os
import sqlite3
import stat
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, Self, cast

if TYPE_CHECKING:
    from prosper.benchmark_metadata import FundMetadata
    from prosper.candidate_workflow import FrozenCandidate
    from prosper.cash_treatment import CashTreatmentRequest
    from prosper.history import Alignment
    from prosper.modeled_inputs import FrozenModeledInputs

from pydantic import JsonValue

from prosper.advisory_records import (
    AnalysisRun,
    Fact,
    Finding,
    ImportSnapshot,
    encode,
)
from prosper.benchmark import BenchmarkFetch, BenchmarkObservation, BenchmarkResult
from prosper.history import HistoryBatch
from prosper.record_types import Identifier
from prosper.source_blob import MAX_SOURCE_BYTES as SOURCE_MAX_BYTES
from prosper.source_blob import pack as pack_source
from prosper.source_blob import unpack as unpack_source
from prosper.storage import MAX_BYTES, RESTORE_MARKER, PersistenceError, RuntimeBoundary

DATABASE_NAME = "advisory-v1.sqlite3"
APPLICATION_ID = 0x50524144
SCHEMA_VERSION = 13
_SCHEMA = (
    "CREATE TABLE sources (sha256 TEXT PRIMARY KEY, original_size INTEGER NOT NULL "
    "CHECK(original_size>0 AND original_size<=16777216), zlib_bytes BLOB NOT NULL) STRICT",
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
    "CREATE TABLE worksheets (id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), "
    "document TEXT NOT NULL) STRICT",
    "CREATE TABLE input_records (id TEXT PRIMARY KEY, document TEXT NOT NULL) STRICT",
    "CREATE TABLE input_sources (input_id TEXT NOT NULL REFERENCES input_records(id), "
    "source_sha256 TEXT NOT NULL REFERENCES sources(sha256), "
    "PRIMARY KEY(input_id,source_sha256)) STRICT",
    "CREATE TABLE history_batches (id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL "
    "REFERENCES sources(sha256), document TEXT NOT NULL) STRICT",
    "CREATE TABLE history_parts (id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL "
    "REFERENCES sources(sha256), document TEXT NOT NULL) STRICT",
    "CREATE TABLE run_sources (run_id TEXT NOT NULL REFERENCES runs(id), "
    "source_sha256 TEXT NOT NULL REFERENCES sources(sha256), "
    "PRIMARY KEY(run_id,source_sha256)) STRICT",
    "CREATE TABLE benchmark_observations (id TEXT PRIMARY KEY, "
    "source_sha256 TEXT REFERENCES sources(sha256), document TEXT NOT NULL) STRICT",
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
            if not path.exists() and runtime.path("checkpoints-v1.sqlite3").exists():
                raise PersistenceError("fresh_advisory_runtime_required")
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
            for attempt in range(3):
                path = self.runtime.path(DATABASE_NAME + suffix)
                try:
                    info = path.lstat()
                except FileNotFoundError:
                    break
                if stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    break
                # Windows can stat a SQLite sidecar already pending deletion
                # with zero links. Recheck the guarded path; never accept that
                # metadata, hardlinks, redirects or an untrusted main DB.
                if (
                    os.name == "nt"
                    and suffix
                    and stat.S_ISREG(info.st_mode)
                    and info.st_nlink == 0
                    and attempt < 2
                ):
                    time.sleep(0.001)
                    continue
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
            self._retain_source(connection, snapshot.source_sha256, raw_source)
            connection.execute(
                "INSERT OR IGNORE INTO snapshots VALUES (?,?,?,'staged',?)",
                (identity, snapshot.source_sha256, _now(), document),
            )
            self._snapshot(connection, identity)
            return identity

    def retain_alignment(self, alignment: "Alignment") -> str:
        from prosper.history import Alignment

        if not isinstance(alignment, Alignment):
            raise ValueError("alignment_required")
        document = encode(alignment)
        identity = hashlib.sha256(document.encode()).hexdigest()
        with self._connection(write=True) as connection:
            for digest in alignment.required_sources:
                self._source(connection, digest)
            connection.execute(
                "INSERT OR IGNORE INTO input_records VALUES (?,?)", (identity, document)
            )
            for digest in alignment.required_sources:
                connection.execute(
                    "INSERT OR IGNORE INTO input_sources VALUES (?,?)", (identity, digest)
                )
            self._alignment(connection, identity)
        return identity

    @staticmethod
    def _alignment(connection: sqlite3.Connection, identity: str) -> "Alignment":
        from prosper.history import Alignment

        row = connection.execute(
            "SELECT document FROM input_records WHERE id=?", (identity,)
        ).fetchone()
        if row is None or hashlib.sha256(row[0].encode()).hexdigest() != identity:
            raise PersistenceError("immutable_input_missing_or_corrupt")
        return Alignment.model_validate_json(row[0])

    def alignment(self, identity: str) -> "Alignment":
        with self._connection() as connection:
            return self._alignment(connection, identity)

    def freeze_modeled(self, frozen: "FrozenModeledInputs") -> dict[str, JsonValue]:
        from prosper.modeled_inputs import FrozenModeledInputs

        if not isinstance(frozen, FrozenModeledInputs):
            raise ValueError("modeled_inputs_required")
        result = frozen.model_dump(mode="json", exclude={"alignment"})
        result["alignment_ref"] = (
            self.retain_alignment(frozen.alignment) if frozen.alignment else None
        )
        return cast(dict[str, JsonValue], result)

    @classmethod
    def _modeled_inputs(
        cls, connection: sqlite3.Connection, value: JsonValue
    ) -> "FrozenModeledInputs":
        from prosper.modeled_inputs import FrozenModeledInputs

        if not isinstance(value, dict):
            raise PersistenceError("immutable_input_reference_invalid")
        values = dict(value)
        if "alignment_ref" not in values:
            raise PersistenceError("unsupported_modeled_input_format")
        reference = values.pop("alignment_ref")
        values["alignment"] = (
            cast(JsonValue, cls._alignment(connection, str(reference)).model_dump(mode="json"))
            if reference
            else None
        )
        return FrozenModeledInputs.model_validate_json(json.dumps(values))

    def modeled_inputs(self, value: JsonValue) -> "FrozenModeledInputs":
        with self._connection() as connection:
            return self._modeled_inputs(connection, value)

    @classmethod
    def _candidate_inputs(
        cls, connection: sqlite3.Connection, value: JsonValue
    ) -> "FrozenCandidate":
        from prosper.candidate_workflow import FrozenCandidate

        if not isinstance(value, dict):
            raise PersistenceError("immutable_input_reference_invalid")
        values = dict(value)
        reference = values.pop("modeled_input_run_id")
        command = values.get("command")
        if not isinstance(command, dict) or command.get("input_run_id") != reference:
            raise PersistenceError("candidate_input_run_mismatch")
        source_run = cls._run(connection, str(reference))
        values["modeled"] = cls._modeled_inputs(
            connection, source_run.inputs["modeled_inputs"]
        ).model_dump(mode="json")
        values["coverage"] = source_run.outputs
        return FrozenCandidate.model_validate_json(json.dumps(values))

    def candidate_inputs(self, value: JsonValue) -> "FrozenCandidate":
        with self._connection() as connection:
            return self._candidate_inputs(connection, value)

    def history_batches(self) -> tuple[HistoryBatch, ...]:
        with self._connection() as connection:
            result = []
            for identity, digest, document in connection.execute(
                "SELECT id,source_sha256,document FROM history_batches ORDER BY rowid"
            ):
                batch = HistoryBatch.model_validate_json(document)
                if (
                    hashlib.sha256(encode(batch).encode()).hexdigest() != identity
                    or batch.source_sha256 != digest
                ):
                    raise PersistenceError("corrupt_history_batch")
                result.append(batch)
            return tuple(result)

    @staticmethod
    def _benchmark_observation(
        connection: sqlite3.Connection, identity: str
    ) -> BenchmarkObservation:
        row = connection.execute(
            "SELECT source_sha256,document FROM benchmark_observations WHERE id=?", (identity,)
        ).fetchone()
        if row is None:
            raise PersistenceError("benchmark_observation_missing")
        observation = BenchmarkObservation.model_validate_json(row[1])
        if observation.request.observation_id != identity or observation.source_sha256 != row[0]:
            raise PersistenceError("corrupt_benchmark_observation")
        if observation.metadata is not None:
            from prosper import vanguard as v
            from prosper.benchmark_metadata import inspect_metadata

            metadata = observation.metadata
            try:
                checked = inspect_metadata(
                    observation,
                    v.Response(
                        200,
                        metadata.response_url,
                        metadata.content_type,
                        AdvisoryStore._source(connection, metadata.source_sha256),
                    ),
                    datetime.fromisoformat(metadata.collected_at),
                )
                if checked != metadata:
                    raise ValueError("metadata_binding_mismatch")
            except ValueError:
                raise PersistenceError("corrupt_benchmark_metadata") from None
        return observation

    def benchmark_observation(self, identity: str) -> BenchmarkObservation:
        with self._connection() as connection:
            return self._benchmark_observation(connection, identity)

    def attach_benchmark_metadata(
        self, identity: str, metadata: "FundMetadata", raw: bytes
    ) -> BenchmarkObservation:
        from prosper import vanguard as v
        from prosper.benchmark_metadata import inspect_metadata

        with self._connection(write=True) as connection:
            observation = self._benchmark_observation(connection, identity)
            if observation.metadata is not None:
                if observation.metadata.source_sha256 != metadata.source_sha256:
                    raise PersistenceError("benchmark_metadata_already_bound")
                return observation
            checked = inspect_metadata(
                observation,
                v.Response(200, metadata.response_url, metadata.content_type, raw),
                datetime.fromisoformat(metadata.collected_at),
            )
            if checked != metadata:
                raise PersistenceError("corrupt_benchmark_metadata")
            self._retain_source(connection, metadata.source_sha256, raw)
            updated = observation.model_copy(update={"metadata": metadata})
            connection.execute(
                "UPDATE benchmark_observations SET document=? WHERE id=?",
                (encode(updated), identity),
            )
            return updated

    def begin_benchmark(
        self,
        request: BenchmarkFetch,
        request_digest: str | None = None,
        collected_at: str | None = None,
    ) -> tuple[BenchmarkObservation, bool]:
        """Reserve before the GET; lost/interrupted attempts never refetch on retry."""
        request_digest = request_digest or hashlib.sha256(encode(request).encode()).hexdigest()
        with self._connection(write=True) as connection:
            if connection.execute(
                "SELECT id FROM benchmark_observations WHERE id=?", (request.observation_id,)
            ).fetchone():
                prior = self._benchmark_observation(connection, request.observation_id)
                if prior.request != request or prior.request_sha256 != request_digest:
                    raise PersistenceError("command_key_reused")
                return prior, False
            observation = BenchmarkObservation(
                request=request,
                collected_at=collected_at or _now(),
                status="pending",
                request_sha256=request_digest,
            )
            connection.execute(
                "INSERT INTO benchmark_observations VALUES (?,NULL,?)",
                (request.observation_id, encode(observation)),
            )
            return observation, True

    def finish_benchmark(
        self, observation: BenchmarkObservation, raw: bytes | None
    ) -> BenchmarkObservation:
        with self._connection(write=True) as connection:
            prior = self._benchmark_observation(connection, observation.request.observation_id)
            if prior.request != observation.request or prior.status != "pending":
                raise PersistenceError("benchmark_observation_already_completed")
            if raw is not None:
                self._retain_source(connection, observation.source_sha256, raw)
            elif observation.source_sha256 is not None:
                raise PersistenceError("source_unavailable_or_corrupt")
            connection.execute(
                "UPDATE benchmark_observations SET source_sha256=?,document=? WHERE id=?",
                (
                    observation.source_sha256,
                    encode(observation),
                    observation.request.observation_id,
                ),
            )
            return observation

    @staticmethod
    def _retain_source(connection: sqlite3.Connection, digest: str | None, raw: bytes) -> None:
        if not 0 < len(raw) <= SOURCE_MAX_BYTES or hashlib.sha256(raw).hexdigest() != digest:
            raise PersistenceError("source_checksum_or_size_invalid")
        size, encoded = pack_source(raw)
        connection.execute("INSERT OR IGNORE INTO sources VALUES (?,?,?)", (digest, size, encoded))
        if AdvisoryStore._source(connection, str(digest)) != raw:
            raise PersistenceError("source_unavailable_or_corrupt")

    def retain_source(self, raw: bytes) -> str:
        digest = hashlib.sha256(raw).hexdigest()
        with self._connection(write=True) as connection:
            self._retain_source(connection, digest, raw)
        return digest

    def source_bytes(self, digest: str) -> bytes:
        with self._connection() as connection:
            return self._source(connection, digest)

    def selected_snapshots(self) -> tuple[ImportSnapshot, ...]:
        """Previously selected source facts remain available for conflict screening."""
        with self._connection() as connection:
            return tuple(
                self._snapshot(connection, row[0])
                for row in connection.execute(
                    "SELECT id FROM snapshots WHERE state='selected' ORDER BY rowid"
                )
            )

    def clear_history_cache(self, key: str, expected: int) -> dict[str, JsonValue]:
        # Cache is rebuildable; original inputs used by saved runs remain required.
        from pydantic import TypeAdapter

        TypeAdapter(Identifier).validate_python(key, strict=True)
        payload = encode({"clear_history_cache": True, "expected": expected})
        with self._connection(write=True) as connection:
            prior = connection.execute(
                "SELECT payload,result FROM commands WHERE key=?", (key,)
            ).fetchone()
            if prior:
                if prior[0] != payload:
                    raise PersistenceError("command_key_reused")
                return cast(dict[str, JsonValue], json.loads(prior[1]))
            outcome = "stale_revision"
            if type(expected) is int and self._state(connection)["revision"] == expected:
                connection.execute("DELETE FROM history_batches")
                connection.execute(
                    "DELETE FROM sources WHERE sha256 NOT IN "
                    "(SELECT source_sha256 FROM snapshots UNION "
                    "SELECT source_sha256 FROM run_sources UNION "
                    "SELECT source_sha256 FROM input_sources UNION "
                    "SELECT source_sha256 FROM history_parts UNION "
                    "SELECT source_sha256 FROM benchmark_observations "
                    "WHERE source_sha256 IS NOT NULL UNION "
                    "SELECT json_extract(document,'$.metadata.source_sha256') "
                    "FROM benchmark_observations "
                    "WHERE json_extract(document,'$.metadata.source_sha256') IS NOT NULL)"
                )
                connection.execute(
                    "UPDATE state SET revision=revision+1,current_run_id=NULL WHERE id=1"
                )
                outcome = "changed"
            result: dict[str, JsonValue] = {
                "outcome": outcome,
                "revision": self._state(connection)["revision"],
            }
            connection.execute(
                "INSERT INTO commands VALUES (?,?,?)", (key, payload, encode(result))
            )
            return result

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
        preparation = snapshot.holding_preparation
        if preparation is not None:
            original_row = connection.execute(
                "SELECT document FROM snapshots WHERE id=?", (preparation.source_snapshot_id,)
            ).fetchone()
            if (
                original_row is None
                or hashlib.sha256(original_row[0].encode()).hexdigest()
                != preparation.source_snapshot_id
            ):
                raise PersistenceError("holding_preparation_source_missing_or_corrupt")
            original = ImportSnapshot.model_validate_json(original_row[0])
            if original.holding_preparation is not None or (
                original.source_sha256,
                original.account_id,
                original.source_as_of,
            ) != (snapshot.source_sha256, snapshot.account_id, snapshot.source_as_of):
                raise PersistenceError("holding_preparation_binding_invalid")
            source_securities = {s.id: s for s in original.securities}
            aliases = {r.source.id: r.security_id for r in preparation.rows}
            mapped = {r.source.id for r in preparation.rows if r.disposition == "mapped"}
            expected_securities = tuple(
                s.model_copy(
                    update={"id": aliases[s.id], "identity": Fact[str](value=aliases[s.id])}
                )
                if s.id in mapped
                else s
                for s in original.securities
            )
            if (
                snapshot.securities != expected_securities
                or any(source_securities.get(r.source.id) != r.source for r in preparation.rows)
                or set(aliases)
                != {r.security_id for r in original.lots}
                | {r.security_id for r in original.positions}
                or snapshot.lots
                != tuple(
                    r.model_copy(update={"security_id": aliases[r.security_id]})
                    for r in original.lots
                )
                or snapshot.positions
                != tuple(
                    r.model_copy(update={"security_id": aliases[r.security_id]})
                    for r in original.positions
                )
                or snapshot.cash != original.cash
            ):
                raise PersistenceError("holding_preparation_binding_invalid")
            benchmark = AdvisoryStore._checked_benchmark(connection, preparation.benchmark_run_id)
            result = BenchmarkResult.model_validate_json(json.dumps(benchmark.outputs))
            observed = AdvisoryStore._benchmark_observation(connection, result.observation_id)
            if (observed.source_sha256, result.metadata_source_sha256, result.effective_date) != (
                preparation.benchmark_source_sha256,
                preparation.metadata_source_sha256,
                preparation.benchmark_date,
            ):
                raise PersistenceError("holding_preparation_binding_invalid")
            for mapping in preparation.rows:
                if mapping.disposition == "mapped" and not any(
                    r.locator.section == "holdings"
                    and r.locator.index == mapping.benchmark_index
                    and r.disposition == "included-equity"
                    and r.security_id == mapping.security_id
                    for r in result.ledger
                ):
                    raise PersistenceError("holding_preparation_binding_invalid")
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
        row = connection.execute(
            "SELECT original_size,zlib_bytes FROM sources WHERE sha256=?", (digest,)
        ).fetchone()
        if row is None:
            raise PersistenceError("source_unavailable_or_corrupt")
        return unpack_source(digest, row[0], row[1])

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
                "worksheets": [
                    row[0] for row in connection.execute("SELECT id FROM worksheets ORDER BY rowid")
                ],
                "benchmarks": [
                    self._benchmark_observation(connection, row[0]).model_dump(mode="json")
                    for row in connection.execute(
                        "SELECT id FROM benchmark_observations ORDER BY rowid"
                    )
                ],
                "pending_history_parts": [
                    row[0]
                    for row in connection.execute("SELECT id FROM history_parts ORDER BY rowid")
                ],
            }

    def select(
        self, identity: str, command_key: str, expected_revision: int
    ) -> dict[str, JsonValue]:
        return self._change("select", identity, command_key, expected_revision)

    def treat_cash(self, command: "CashTreatmentRequest") -> dict[str, JsonValue]:
        return self._change(
            "cash-treatment",
            command.model_dump(mode="json", exclude={"command_key", "expected_revision"}),
            command.command_key,
            command.expected_revision,
        )

    def configure(
        self, settings: dict[str, JsonValue], command_key: str, expected_revision: int
    ) -> dict[str, JsonValue]:
        if not isinstance(settings, dict):
            raise PersistenceError("invalid_advisory_record")
        return self._change("settings", settings, command_key, expected_revision)

    @staticmethod
    def _checked_benchmark(connection: sqlite3.Connection, identity: str) -> AnalysisRun:
        run = AdvisoryStore._run(connection, identity)
        if run.model_version != "benchmark-proxy-v1" or run.status != "partial":
            raise PersistenceError("benchmark_selection_unavailable")
        result = BenchmarkResult.model_validate_json(json.dumps(run.outputs))
        if result.status != "estimated-equity-benchmark":
            raise PersistenceError("benchmark_selection_unavailable")
        observation = AdvisoryStore._benchmark_observation(connection, result.observation_id)
        required = tuple(sorted({str(observation.source_sha256), result.metadata_source_sha256}))
        retained = tuple(
            row[0]
            for row in connection.execute(
                "SELECT source_sha256 FROM run_sources WHERE run_id=? ORDER BY source_sha256",
                (identity,),
            )
        )
        if retained != required:
            raise PersistenceError("required_run_sources_missing")
        for digest in retained:
            AdvisoryStore._source(connection, digest)
        return run

    def select_benchmark(self, identity: str, key: str, expected: int) -> dict[str, JsonValue]:
        return self._change("benchmark", identity, key, expected)

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
                if operation == "cash-treatment":
                    from prosper.cash_treatment import apply

                    supplied = cast(dict[str, JsonValue], value)
                    if supplied["snapshot_id"] != state["snapshot_id"]:
                        raise PersistenceError("cash_treatment_snapshot_changed")
                    snapshot = self._snapshot(connection, str(supplied["snapshot_id"]))
                    self._source(connection, snapshot.source_sha256)
                    try:
                        updated = apply(
                            snapshot,
                            str(supplied["security_id"]),
                            cast(str | None, supplied["kind"]),
                            _now(),
                        )
                    except ValueError:
                        raise PersistenceError("cash_treatment_invalid") from None
                    if updated == snapshot:
                        outcome = "duplicate"
                    else:
                        document = encode(updated)
                        identity = hashlib.sha256(document.encode()).hexdigest()
                        connection.execute(
                            "INSERT OR IGNORE INTO snapshots VALUES (?,?,?,'selected',?)",
                            (identity, updated.source_sha256, _now(), document),
                        )
                        connection.execute(
                            "UPDATE snapshots SET state='selected' WHERE id=?", (identity,)
                        )
                        connection.execute("UPDATE state SET snapshot_id=? WHERE id=1", (identity,))
                        outcome = "changed"
                elif operation == "benchmark":
                    self._checked_benchmark(connection, str(value))
                    settings = cast(dict[str, JsonValue], state["settings"])
                    if settings.get("benchmark_run_id") == value:
                        outcome = "duplicate"
                    else:
                        connection.execute(
                            "UPDATE state SET settings=? WHERE id=1",
                            (encode({**settings, "benchmark_run_id": value}),),
                        )
                        outcome = "changed"
                elif operation == "select":
                    snapshot = self._snapshot(connection, cast(str, value))
                    row = connection.execute(
                        "SELECT state FROM snapshots WHERE id=?", (value,)
                    ).fetchone()
                    current = state["snapshot_id"]
                    old = self._snapshot(connection, cast(str, current)) if current else None
                    preparation = snapshot.holding_preparation
                    if preparation is not None and (
                        cast(dict[str, JsonValue], state["settings"]).get("benchmark_run_id")
                        != preparation.benchmark_run_id
                        or current not in (preparation.source_snapshot_id, value)
                    ):
                        outcome = "prepared_snapshot_stale"
                    elif row == ("rejected",):
                        outcome = "preview_rejected"
                    elif snapshot.observations.get("selection_blockers"):
                        outcome = "preview_blocked"
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
                    settings = cast(dict[str, JsonValue], value)
                    if "benchmark_run_id" in settings:
                        if not isinstance(settings["benchmark_run_id"], str):
                            raise PersistenceError("benchmark_selection_unavailable")
                        self._checked_benchmark(connection, settings["benchmark_run_id"])
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
        source_ids: tuple[str, ...] = (),
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
                retained_sources = tuple(
                    row[0]
                    for row in connection.execute(
                        "SELECT source_sha256 FROM run_sources "
                        "WHERE run_id=? ORDER BY source_sha256",
                        (identity,),
                    )
                )
                if retained_sources != tuple(sorted(set(source_ids))):
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
            for digest in sorted(set(source_ids)):
                self._source(connection, digest)
                connection.execute("INSERT INTO run_sources VALUES (?,?)", (identity, digest))
            return result

    def complete_run(
        self,
        identity: str,
        *,
        outputs: dict[str, JsonValue],
        status: Literal["complete", "partial", "failed"],
        exclusions: tuple[Finding, ...] = (),
        warnings: tuple[str, ...] = (),
        candidate_claim: str | None = None,
    ) -> AnalysisRun:
        with self._connection(write=True) as connection:
            saved = self._run(connection, identity)
            if candidate_claim is not None and saved.completed_at is None:
                if saved.outputs.get("claim") != candidate_claim:
                    return saved
                state = self._state(connection)
                stopped = (
                    "cancelled"
                    if saved.outputs.get("cancel_requested") is True
                    else ("stale" if state["revision"] != saved.input_revision else None)
                )
                if stopped:
                    from prosper.candidate_workflow import CandidateOutput

                    outputs = CandidateOutput.model_validate(
                        dict(outcome=stopped, issues=(stopped,), risk=None, search=None)
                    ).model_dump(mode="json")
                    status = "failed"
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
