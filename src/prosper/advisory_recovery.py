"""Current SQLite backup and atomic clean-workspace restore, without migrations."""

import base64
import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from pydantic import JsonValue, TypeAdapter

from prosper.advisory_records import AnalysisRun, ImportSnapshot, encode
from prosper.advisory_store import (
    _SCHEMA,
    APPLICATION_ID,
    SCHEMA_VERSION,
    AdvisoryStore,
)
from prosper.api_contracts import CommandResponse, CurrentResponse
from prosper.benchmark import BenchmarkDiagnostic, BenchmarkObservation, BenchmarkResult
from prosper.candidate_workflow import (
    MODEL,
    CandidateOutput,
    CandidateProgress,
    check_output_links,
)
from prosper.lot_opportunities import LotResult, ScreeningInputs
from prosper.lot_records import LotDiagnosticRequest, LotSettings
from prosper.modeled_inputs import ModeledBundle, ModeledResult
from prosper.record_types import Timestamp
from prosper.source_blob import unpack as unpack_source
from prosper.storage import PersistenceError
from prosper.worksheets import _read as read_worksheet_record

MAX_BACKUP_BYTES = 64 * 1024 * 1024
TABLES = (
    "sources",
    "snapshots",
    "history_parts",
    "history_batches",
    "input_records",
    "input_sources",
    "benchmark_observations",
    "runs",
    "run_sources",
    "worksheets",
    "commands",
    "state",
)


def _validate(connection: sqlite3.Connection) -> None:
    if connection.execute("PRAGMA application_id").fetchone() != (
        APPLICATION_ID,
    ) or connection.execute("PRAGMA user_version").fetchone() != (SCHEMA_VERSION,):
        raise PersistenceError("incompatible_advisory_schema")
    expected = {sql.split()[2]: sql for sql in _SCHEMA}
    actual = dict(connection.execute("SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL"))
    if actual != expected:
        raise PersistenceError("incompatible_advisory_schema")
    if (
        connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]
        or connection.execute("PRAGMA foreign_key_check").fetchall()
    ):
        raise PersistenceError("corrupt_advisory_backup")
    states = connection.execute("SELECT id FROM state").fetchall()
    if states != [(1,)]:
        raise PersistenceError("advisory_state_missing")
    state = CurrentResponse.model_validate(AdvisoryStore._state(connection))
    encode(state.settings)
    for digest, size, encoded in connection.execute(
        "SELECT sha256,original_size,zlib_bytes FROM sources"
    ):
        unpack_source(digest, size, encoded)
    for identity, digest, imported, _, document in connection.execute("SELECT * FROM snapshots"):
        snapshot = ImportSnapshot.model_validate_json(document)
        if snapshot.holding_preparation is not None:
            AdvisoryStore._snapshot(connection, identity)
        TypeAdapter(Timestamp).validate_python(imported)
        if (
            hashlib.sha256(encode(snapshot).encode()).hexdigest() != identity
            or snapshot.source_sha256 != digest
        ):
            raise PersistenceError("corrupt_advisory_backup")
    for identity, snapshot_id, document in connection.execute("SELECT * FROM runs"):
        run = AnalysisRun.model_validate_json(document)
        encode(run)
        if (run.id, run.snapshot_id) != (identity, snapshot_id):
            raise PersistenceError("corrupt_advisory_backup")
        if run.model_version == MODEL:
            frozen_candidate = AdvisoryStore._candidate_inputs(
                connection, run.inputs["candidate_inputs"]
            )
            candidate_command = frozen_candidate.command
            source_run = AdvisoryStore._run(connection, candidate_command.input_run_id)
            if (
                (
                    candidate_command.run_id,
                    candidate_command.expected_revision,
                    candidate_command.as_of,
                )
                != (run.id, run.input_revision, run.as_of)
                or run.inputs["candidate_command"] != candidate_command.model_dump(mode="json")
                or frozen_candidate.snapshot != AdvisoryStore._snapshot(connection, run.snapshot_id)
                or source_run.input_revision != run.input_revision
                or AdvisoryStore._modeled_inputs(connection, source_run.inputs["modeled_inputs"])
                != frozen_candidate.modeled
                or source_run.outputs != frozen_candidate.coverage.model_dump(mode="json")
            ):
                raise PersistenceError("corrupt_advisory_backup")
            expected_sources = tuple(
                sorted(
                    set(frozen_candidate.modeled.retained_sources)
                    | {
                        s.source_sha256
                        for s in (frozen_candidate.snapshot, *frozen_candidate.retained_snapshots)
                    }
                )
            )
            actual_sources = tuple(
                r[0]
                for r in connection.execute(
                    "SELECT source_sha256 FROM run_sources WHERE run_id=? ORDER BY source_sha256",
                    (identity,),
                )
            )
            if (
                frozen_candidate.required_sources != expected_sources
                or actual_sources != expected_sources
            ):
                raise PersistenceError("required_run_sources_missing")
            for snapshot in frozen_candidate.retained_snapshots:
                key = hashlib.sha256(encode(snapshot).encode()).hexdigest()
                if AdvisoryStore._snapshot(connection, key) != snapshot:
                    raise PersistenceError("corrupt_advisory_backup")
            if run.status != "running":
                candidate_output = CandidateOutput.model_validate_json(json.dumps(run.outputs))
                check_output_links(frozen_candidate, candidate_output)
                if candidate_output.search is not None and (
                    candidate_output.search.inputs.snapshot != frozen_candidate.snapshot
                    or candidate_output.search.inputs.retained_snapshots
                    != frozen_candidate.retained_snapshots
                ):
                    raise PersistenceError("corrupt_advisory_backup")
            else:
                CandidateProgress.model_validate_json(json.dumps(run.outputs))
        if run.model_version == "modeled-inputs-v1":
            frozen = AdvisoryStore._modeled_inputs(connection, run.inputs["modeled_inputs"])
            modeled_request = cast(dict[str, JsonValue], run.inputs["modeled_request"])
            bundle = ModeledBundle.model_validate_json(json.dumps(modeled_request["bundle"]))
            binding = bundle.assembly
            if binding and (
                binding.snapshot_id != run.snapshot_id
                or binding.input_revision != run.input_revision
                or binding.benchmark_run_id != frozen.benchmark_run_id
                or datetime.fromisoformat(binding.prepared_at) > datetime.fromisoformat(run.as_of)
            ):
                raise PersistenceError("corrupt_advisory_backup")
            if bundle != frozen.bundle or (
                modeled_request["run_id"],
                modeled_request["expected_revision"],
                modeled_request["as_of"],
            ) != (run.id, run.input_revision, run.as_of):
                raise PersistenceError("corrupt_advisory_backup")
            retained = tuple(
                row[0]
                for row in connection.execute(
                    "SELECT source_sha256 FROM run_sources WHERE run_id=? ORDER BY source_sha256",
                    (identity,),
                )
            )
            if retained != frozen.retained_sources:
                raise PersistenceError("required_run_sources_missing")
            if frozen.benchmark_run_id:
                selected = AdvisoryStore._run(connection, frozen.benchmark_run_id)
                if (
                    selected.model_version != "benchmark-proxy-v1"
                    or frozen.benchmark is None
                    or selected.outputs != frozen.benchmark.model_dump(mode="json")
                ):
                    raise PersistenceError("corrupt_advisory_backup")
            if run.status == "partial":
                modeled_result = ModeledResult.model_validate_json(json.dumps(run.outputs))
                if (
                    modeled_result.sleeve != frozen.sleeve
                    or modeled_result.security_ids != frozen.sleeve.retained_ids
                ):
                    raise PersistenceError("corrupt_advisory_backup")
        if run.model_version == "benchmark-proxy-v1":
            request = run.inputs["benchmark_request"]
            if not isinstance(request, dict) or not isinstance(request.get("review"), dict):
                raise PersistenceError("corrupt_advisory_backup")
            review = cast(dict[str, JsonValue], request["review"])
            observation = AdvisoryStore._benchmark_observation(
                connection, str(review["observation_id"])
            )
            required = tuple(
                sorted({str(review["metadata_sha256"]), str(observation.source_sha256)})
            )
            retained = tuple(
                row[0]
                for row in connection.execute(
                    "SELECT source_sha256 FROM run_sources WHERE run_id=? ORDER BY source_sha256",
                    (identity,),
                )
            )
            if retained != required:
                raise PersistenceError("required_run_sources_missing")
            typed_review = {k: v for k, v in review.items() if k != "metadata_sha256"}
            typed_review["metadata_base64"] = base64.b64encode(
                AdvisoryStore._source(connection, str(review["metadata_sha256"]))
            ).decode()
            typed_request = {**request, "review": typed_review}
            command = BenchmarkDiagnostic.model_validate_json(json.dumps(typed_request))
            if (command.run_id, command.expected_revision, command.as_of) != (
                run.id,
                run.input_revision,
                run.as_of,
            ):
                raise PersistenceError("corrupt_advisory_backup")
            if run.status == "partial":
                result = BenchmarkResult.model_validate_json(json.dumps(run.outputs))
                if result.observation_id != observation.request.observation_id:
                    raise PersistenceError("corrupt_advisory_backup")
        if "alignment_ref" in run.inputs:
            aligned = AdvisoryStore._alignment(connection, str(run.inputs["alignment_ref"]))
            if aligned.request.model_dump(mode="json") != run.inputs["history_request"]:
                raise PersistenceError("corrupt_advisory_backup")
            retained = tuple(
                row[0]
                for row in connection.execute(
                    "SELECT source_sha256 FROM run_sources WHERE run_id=? ORDER BY source_sha256",
                    (identity,),
                )
            )
            if retained != aligned.required_sources:
                raise PersistenceError("required_run_sources_missing")
        if "screening_inputs" in run.inputs:
            inputs = ScreeningInputs.model_validate_json(json.dumps(run.inputs["screening_inputs"]))
            LotDiagnosticRequest.model_validate_json(json.dumps(run.inputs["lot_request"]))
            LotSettings.model_validate_json(json.dumps(run.settings["lot_opportunities"]))
            retained = tuple(
                row[0]
                for row in connection.execute(
                    "SELECT source_sha256 FROM run_sources WHERE run_id=? ORDER BY source_sha256",
                    (identity,),
                )
            )
            if inputs.sources != retained:
                raise PersistenceError("required_run_sources_missing")
            if run.status in ("complete", "partial"):
                LotResult.model_validate_json(json.dumps(run.outputs))
    for (identity,) in connection.execute("SELECT id FROM input_records"):
        alignment = AdvisoryStore._alignment(connection, identity)
        owned = tuple(
            row[0]
            for row in connection.execute(
                "SELECT source_sha256 FROM input_sources WHERE input_id=? ORDER BY source_sha256",
                (identity,),
            )
        )
        if owned != alignment.required_sources:
            raise PersistenceError("required_input_sources_missing")
        for digest in owned:
            AdvisoryStore._source(connection, digest)
    from prosper.history_upload import MAX_ORIGINALS, MAX_PARTS, MAX_ROWS, read_part

    pending = pending_rows = pending_bytes = 0
    for table in ("history_parts", "history_batches"):
        for (identity,) in connection.execute(f"SELECT id FROM {table}"):
            batch, original = read_part(connection, identity)
            if table == "history_parts":
                pending += 1
                pending_rows += batch.rows.row_count
                pending_bytes += len(original)
    if pending > MAX_PARTS or pending_rows > MAX_ROWS or pending_bytes > MAX_ORIGINALS:
        raise PersistenceError("pending_history_budget_exceeded")
    for identity, digest, document in connection.execute("SELECT * FROM benchmark_observations"):
        observation = BenchmarkObservation.model_validate_json(document)
        if observation.request.observation_id != identity or observation.source_sha256 != digest:
            raise PersistenceError("corrupt_advisory_backup")
        if observation.metadata is not None:
            AdvisoryStore._benchmark_observation(connection, identity)
    if "benchmark_run_id" in state.settings:
        AdvisoryStore._checked_benchmark(connection, str(state.settings["benchmark_run_id"]))
    for (identity,) in connection.execute("SELECT id FROM worksheets"):
        encode(read_worksheet_record(connection, identity))
    for _, payload, result in connection.execute("SELECT * FROM commands"):
        encode(json.loads(payload))
        CommandResponse.model_validate_json(result)
    if state.current_run_id:
        run = AdvisoryStore._run(connection, state.current_run_id)
        if (run.snapshot_id, run.input_revision) != (
            state.snapshot_id,
            state.revision,
        ) or run.status not in ("complete", "partial"):
            raise PersistenceError("corrupt_advisory_backup")


@contextmanager
def _scratch(store: AdvisoryStore) -> Iterator[Path]:
    store.runtime.check()
    store._guard()
    with TemporaryDirectory(prefix="advisory-recovery-", dir=store.runtime.root) as directory:
        yield Path(directory) / "snapshot.sqlite3"


def backup(store: AdvisoryStore) -> bytes:
    """SQLite's backup API observes one read transaction including source BLOBs."""
    try:
        with _scratch(store) as path:
            with store._connection() as source, closing(sqlite3.connect(path)) as target:
                source.backup(target)
                # Cache deletion leaves free pages. Compact only the scratch
                # snapshot; the source database and every retained row stay put.
                target.execute("VACUUM")
                _validate(target)
            if path.stat().st_size > MAX_BACKUP_BYTES:
                raise PersistenceError("backup_size_limit")
            return path.read_bytes()
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, RecursionError) as error:
        if isinstance(error, PersistenceError):
            raise
        raise PersistenceError("advisory_backup_failed") from None


def restore(store: AdvisoryStore, raw: bytes) -> dict[str, JsonValue]:
    """Validate offline, then copy all current rows under one destination writer.

    A failed or killed writer rolls back. A receipt makes an identical upload retry
    safe even after later work. Existing user work is never replaced by restore.
    """
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BACKUP_BYTES:
        raise PersistenceError("backup_size_limit")
    digest = hashlib.sha256(raw).hexdigest()
    key = "restore:" + digest
    try:
        with _scratch(store) as path:
            path.write_bytes(raw)
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as source:
                source.execute("PRAGMA trusted_schema=OFF")
                _validate(source)
                with store._connection(write=True) as target:
                    prior = target.execute(
                        "SELECT result FROM commands WHERE key=?", (key,)
                    ).fetchone()
                    if prior:
                        return cast(dict[str, JsonValue], json.loads(prior[0]))
                    if any(
                        target.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                        for table in TABLES[:-1]
                    ) or AdvisoryStore._state(target) != {
                        "revision": 0,
                        "snapshot_id": None,
                        "settings": {},
                        "current_run_id": None,
                    }:
                        raise PersistenceError("restore_requires_empty_workspace")
                    target.execute("DELETE FROM state")
                    for table in TABLES:
                        for row in source.execute(f"SELECT * FROM {table} ORDER BY rowid"):
                            target.execute(
                                f"INSERT INTO {table} VALUES ({','.join('?' for _ in row)})", row
                            )
                    result: dict[str, JsonValue] = {
                        "outcome": "restored",
                        "revision": AdvisoryStore._state(target)["revision"],
                    }
                    target.execute(
                        "INSERT INTO commands VALUES (?,?,?)",
                        (key, encode({"restore_sha256": digest}), encode(result)),
                    )
                    return result
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, RecursionError) as error:
        if isinstance(error, PersistenceError):
            raise
        raise PersistenceError("invalid_advisory_backup") from None
