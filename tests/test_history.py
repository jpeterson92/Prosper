"""Current retained history: independent returns, conservative coverage and recovery."""

import base64
import bz2
import hashlib
import json
import sqlite3
import subprocess
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

import prosper.advisory_store as storage
from prosper.advisory_records import Fact, encode
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import AdvisoryStore
from prosper.api_contracts import (
    HistoryDiagnosticRequest,
    HistoryPart,
    HistoryPlanRequest,
    HistoryUpload,
    Upload,
)
from prosper.history import HistoryBatch, NumberFact
from prosper.history_refresh import align
from prosper.history_table import HistoryTable, SessionGrid, decompress
from prosper.risk_inputs import assemble
from prosper.storage import PersistenceError, RuntimeBoundary
from prosper.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples/synthetic/history"


def upload() -> HistoryUpload:
    return HistoryUpload.model_validate_json((FIXTURES / "current-refresh.json").read_bytes())


def request() -> HistoryPlanRequest:
    return HistoryPlanRequest.model_validate_json((FIXTURES / "current-request.json").read_bytes())


def workspace(root: Path) -> Workspace:
    result = Workspace(AdvisoryStore(RuntimeBoundary(root)))
    preview = result.stage(
        Upload.model_validate_json(
            (ROOT / "examples/synthetic/advisory-workspace.json").read_bytes()
        )
    )
    result.store.select(preview.id, "select", 0)
    return result


def changed(batch: HistoryBatch, **changes: object) -> HistoryBatch:
    from prosper.history_table import SessionGrid, observations

    if "observations" in changes:
        rows = changes.pop("observations")
        assert isinstance(rows, tuple)
        changes["rows"] = observations(rows)
    if "requested_sessions" in changes:
        days = changes.pop("requested_sessions")
        assert isinstance(days, tuple)
        changes["sessions"] = SessionGrid.pack(days)
    return HistoryBatch.model_validate_json(encode(batch.model_copy(update=changes)))


def test_ordered_full_union_returns_have_independent_arithmetic_and_no_fill() -> None:
    aligned = align(request().request, (upload().parts[0].batch,))
    assert aligned.complete and aligned.intervals == ()
    assert [(c.session, c.security_id) for c in aligned.cells] == [
        (d, s) for d in request().request.sessions for s in ("security-b", "security-a")
    ]
    # B: 200/200-1, 220/200-1, 198/220-1; A: 110/100-1,99/110-1,99/99-1.
    assert [c.total_return for c in aligned.cells] == pytest.approx(
        [0, 0.1, 0.1, -0.1, -0.1, 0], abs=1e-15
    )
    innovation = assemble(aligned)
    assert innovation is not None and not innovation.issues
    assert len(aligned.required_sources) == 1


@pytest.mark.parametrize("index,reason", [(0, "leading"), (1, "interior"), (3, "tail")])
def test_gap_plans_include_qualified_overlap_and_explicit_predecessor(
    index: int, reason: str
) -> None:
    batch = upload().parts[0].batch
    days = batch.requested_sessions
    batch = changed(
        batch,
        observations=tuple(
            row
            for row in batch.observations
            if not (row.security_id == "security-a" and row.session == days[index])
        ),
    )
    aligned = align(request().request, (batch,))
    gap = next(i for i in aligned.intervals if i.security_id == "security-a")
    assert gap.reason == reason and gap.sessions == days[max(0, index - 1) : index + 1]
    assert not aligned.complete and any(c.total_return is None for c in aligned.cells)
    assert len(aligned.cells) == 6 and assemble(aligned) is None


def test_new_names_manual_scope_and_missing_calendar_sessions_are_explicit() -> None:
    r = request().request
    empty = align(r, ())
    assert all(i.reason == "new-name" for i in empty.intervals)
    assert len(empty.cells) == 6 and all(c.total_return is None for c in empty.cells)
    manual = align(
        r.model_copy(update={"manual_security_ids": ("security-a",)}), (upload().parts[0].batch,)
    )
    assert [(i.security_id, i.reason) for i in manual.intervals] == [("security-a", "manual")]
    assert manual.intervals[0].sessions == (r.predecessor, *r.sessions)
    assert not empty.validated_at and manual.validated_at


@pytest.mark.parametrize(
    "field,value",
    [
        ("currency", "EUR"),
        ("vintage", "new-vintage"),
        ("provider_symbol", "different"),
        ("adjustment", "price-only"),
        ("return_convention", "price-return"),
        ("repair", "automatic"),
        ("provider", "other"),
    ],
)
def test_changed_context_never_silently_reuses_observations(field: str, value: str) -> None:
    r = request().request
    context = r.series[0].model_copy(update={field: value})
    aligned = align(
        r.model_copy(update={"series": (context, *r.series[1:])}), (upload().parts[0].batch,)
    )
    assert not aligned.complete and assemble(aligned) is None
    assert all(c.observation is None for c in aligned.cells if c.security_id == context.security_id)


def test_unknown_or_invalid_cells_keep_source_facts_and_block_dependent_input() -> None:
    batch = upload().parts[0].batch
    row = batch.observations[0]
    unknown = row.model_copy(
        update={"close": NumberFact(value=None, reason="provider omitted close")}
    )
    aligned = align(
        request().request, (changed(batch, observations=(unknown, *batch.observations[1:])),)
    )
    assert any(
        i.code == "unknown_observation" and "provider omitted" in i.reason for i in aligned.issues
    )
    assert any(
        c.observation and c.observation.close.reason == "provider omitted close"
        for c in aligned.cells
    )
    assert not aligned.complete and assemble(aligned) is None
    bad = row.model_copy(update={"low": NumberFact(value=1e9)})
    aligned = align(
        request().request, (changed(batch, observations=(bad, *batch.observations[1:])),)
    )
    assert any(i.code == "invalid_ohlc" for i in aligned.issues)


def test_mixed_revision_requires_full_window_and_full_validation_resolves_it() -> None:
    original = upload().parts[0].batch
    row = next(
        r
        for r in original.observations
        if r.security_id == "security-a" and r.session == original.requested_sessions[-1]
    )
    revised = row.model_copy(update={"adjusted_close": NumberFact(value=98.0)})
    tail = changed(
        original,
        observations=(revised,),
        requested_sessions=original.requested_sessions[-2:],
        validation_scope="requested-interval",
        collected_at="2026-10-24T01:00:00Z",
        validated_at="2026-10-24T01:00:00Z",
    )
    aligned = align(request().request, (original, tail))
    assert any(i.reason == "coherence" and i.security_id == "security-a" for i in aligned.intervals)
    assert not aligned.complete and all(
        c.total_return is None for c in aligned.cells if c.security_id == "security-a"
    )
    full = changed(
        original,
        observations=tuple(revised if r == row else r for r in original.observations),
        collected_at="2026-10-24T02:00:00Z",
        validated_at="2026-10-24T02:00:00Z",
    )
    recovered = align(request().request, (original, tail, full))
    assert recovered.complete and recovered.validated_at["security-a"] == full.validated_at
    # A revised adjusted close with unchanged raw close is not a qualified IDR input.
    assert assemble(recovered) is None


def test_unverified_tail_cannot_establish_coherence_or_full_validation() -> None:
    batch = upload().parts[0].batch
    contexts = tuple(c.model_copy(update={"coherence": "unverified"}) for c in batch.contexts)
    r = request().request.model_copy(update={"series": contexts})
    tail = changed(batch, contexts=contexts, validation_scope="requested-interval")
    partial = align(r, (tail,))
    assert not partial.complete and not partial.validated_at
    assert all(i.reason == "coherence" for i in partial.intervals)
    assert align(r, (changed(tail, validation_scope="full-window"),)).complete


def test_refresh_retry_saved_inputs_cache_clear_and_current_recovery(tmp_path: Path) -> None:
    w = workspace(tmp_path / "source")
    u = upload()
    assert w.import_history(u) == {"outcome": "changed", "revision": 2}
    assert w.import_history(u) == {"outcome": "changed", "revision": 2}
    command = HistoryDiagnosticRequest(
        request=request().request,
        run_id="history-run",
        expected_revision=2,
        as_of="2026-10-25T00:00:00Z",
    )
    saved = w.diagnose_history(command)
    assert saved.outputs["coverage_complete"] is True and saved.outputs["financial_metrics"] is None
    assert w.diagnose_history(command) == saved
    assert w.store.clear_history_cache("clear", 2)["revision"] == 3
    assert w.store.history_batches() == ()
    assert w.store.run(saved.id) == saved and w.diagnose_history(command) == saved
    assert not w.plan_history(request().request).complete
    with w.store._connection() as connection:
        assert w.store._source(connection, u.parts[0].batch.source_sha256) == zlib.decompress(
            base64.b64decode(u.parts[0].source_zlib_base64)
        )
    target = AdvisoryStore(RuntimeBoundary(tmp_path / "restored"))
    restore(target, backup(w.store))
    assert target.run(saved.id) == saved
    with target._connection() as connection:
        assert target._source(connection, u.parts[0].batch.source_sha256) == zlib.decompress(
            base64.b64decode(u.parts[0].source_zlib_base64)
        )


def test_corruption_does_not_fallback_or_hide_saved_output(tmp_path: Path) -> None:
    w = workspace(tmp_path / "source")
    w.import_history(upload())
    saved = w.diagnose_history(
        HistoryDiagnosticRequest(
            request=request().request,
            run_id="saved",
            expected_revision=2,
            as_of="2026-10-25T00:00:00Z",
        )
    )
    with closing(sqlite3.connect(w.store.runtime.path(storage.DATABASE_NAME))) as connection:
        connection.execute(
            "UPDATE sources SET zlib_bytes=x'00' WHERE sha256=?",
            (upload().parts[0].batch.source_sha256,),
        )
        connection.commit()
    assert not w.plan_history(request().request).complete
    assert w.store.run(saved.id) == saved
    with pytest.raises(PersistenceError):
        backup(w.store)


def test_failed_and_killed_refresh_roll_back_and_retry_safely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = workspace(tmp_path / "source")

    def fail(connection: sqlite3.Connection) -> None:
        raise PersistenceError("injected")

    monkeypatch.setattr(storage, "_before_commit", fail)
    with pytest.raises(PersistenceError, match="injected"):
        w.import_history(upload())
    monkeypatch.undo()
    assert w.store.current()["revision"] == 1 and w.store.history_batches() == ()
    code = """
import os,sys
from pathlib import Path
import prosper.advisory_store as storage
from prosper.advisory_store import AdvisoryStore
from prosper.storage import RuntimeBoundary
from prosper.api_contracts import HistoryUpload
from prosper.workspace import Workspace
root=Path(sys.argv[1]); target=Path(sys.argv[2])
w=Workspace(AdvisoryStore.existing(RuntimeBoundary(target)))
storage._before_commit=lambda connection:os._exit(29)
w.import_history(HistoryUpload.model_validate_json((root/'examples/synthetic/history/current-refresh.json').read_bytes()))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(ROOT), str(w.store.runtime.root)],
        capture_output=True,
    )
    assert result.returncode == 29 and result.stdout == result.stderr == b""
    assert w.store.current()["revision"] == 1 and w.store.history_batches() == ()
    assert w.import_history(upload())["revision"] == 2


def test_competing_refresh_writers_preserve_one_current_revision(tmp_path: Path) -> None:
    w = workspace(tmp_path / "source")
    first = upload()
    second = first.model_copy(update={"command_key": "other"})
    with ThreadPoolExecutor(2) as workers:
        results = list(workers.map(w.import_history, (first, second)))
    assert sorted(str(r["outcome"]) for r in results) == ["changed", "stale_revision"]
    assert w.store.current()["revision"] == 2 and len(w.store.history_batches()) == 1


def test_current_schema_refuses_old_schema_without_repair(tmp_path: Path) -> None:
    w = workspace(tmp_path / "source")
    path = w.store.runtime.path(storage.DATABASE_NAME)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA user_version=1")
    with pytest.raises(PersistenceError, match="incompatible_advisory_schema"):
        AdvisoryStore.existing(w.store.runtime)


def test_interrupted_history_run_keeps_inputs_across_cache_loss_and_stale_resume(
    tmp_path: Path,
) -> None:
    w = workspace(tmp_path / "source")
    w.import_history(upload())
    code = """
import os,sys
from pathlib import Path
import prosper.workspace as module
from prosper.advisory_store import AdvisoryStore
from prosper.storage import RuntimeBoundary
from prosper.api_contracts import HistoryDiagnosticRequest,HistoryPlanRequest
from prosper.workspace import Workspace
root=Path(sys.argv[1]); target=Path(sys.argv[2])
request=HistoryPlanRequest.model_validate_json((root/'examples/synthetic/history/current-request.json').read_bytes()).request
module.conventions_available=lambda alignment:os._exit(30)
Workspace(AdvisoryStore.existing(RuntimeBoundary(target))).diagnose_history(HistoryDiagnosticRequest(request=request,run_id='interrupted-history',expected_revision=2,as_of='2026-10-25T00:00:00Z'))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(ROOT), str(w.store.runtime.root)],
        capture_output=True,
    )
    assert result.returncode == 30 and result.stdout == result.stderr == b""
    frozen = w.store.run("interrupted-history")
    assert frozen.status == "running"
    w.store.clear_history_cache("clear", 2)
    resumed = w.diagnose_history(
        HistoryDiagnosticRequest(
            request=request().request, run_id=frozen.id, expected_revision=2, as_of=frozen.as_of
        )
    )
    assert resumed.status == "partial" and resumed.inputs == frozen.inputs
    assert resumed.outputs["coverage_complete"] is True
    assert w.store.current()["current_run_id"] is None


def test_corrupt_cache_record_is_refused_without_an_empty_history_fallback(tmp_path: Path) -> None:
    w = workspace(tmp_path / "source")
    w.import_history(upload())
    with closing(sqlite3.connect(w.store.runtime.path(storage.DATABASE_NAME))) as connection:
        batch = (
            upload()
            .parts[0]
            .batch.model_copy(update={"source_name": "changed without changing record identity"})
        )
        connection.execute("UPDATE history_batches SET document=?", (encode(batch),))
        connection.commit()
    with pytest.raises(PersistenceError, match="corrupt_history_batch"):
        w.plan_history(request().request)
    assert w.store.current()["revision"] == 2


def test_analysis_known_at_cannot_include_future_information(tmp_path: Path) -> None:
    w = workspace(tmp_path / "source")
    with pytest.raises(PersistenceError, match="history_knowledge_after_analysis"):
        w.diagnose_history(
            HistoryDiagnosticRequest(
                request=request().request,
                run_id="future",
                expected_revision=1,
                as_of="2026-10-24T00:00:00Z",
            )
        )
    assert w.store.catalog()["runs"] == []


@pytest.mark.parametrize("classification", [None, "adr-foreign"])
def test_only_known_excluded_holdings_can_leave_the_required_history_union(
    tmp_path: Path,
    classification: str | None,
) -> None:
    w = workspace(tmp_path / "source")
    state = w.store.current()
    snapshot = w.store.snapshot(str(state["snapshot_id"]))
    security = snapshot.securities[0].model_copy(
        update={
            "id": "held-extra",
            "classification": Fact[str](
                value=classification, reason="unknown" if classification is None else None
            ),
        }
    )
    replacement = snapshot.model_copy(
        update={
            "securities": (security,),
            "lots": tuple(
                lot.model_copy(update={"security_id": "held-extra"}) for lot in snapshot.lots
            ),
            "positions": tuple(
                p.model_copy(update={"security_id": "held-extra"}) for p in snapshot.positions
            ),
            # Arbitrary observation data must never exclude an unknown class from risk inputs.
            "observations": {"excluded_security_ids": ["held-extra"]},
        }
    )
    identity = w.store.stage(replacement, w.store.source(str(state["snapshot_id"])))
    w.store.select(identity, "replace", 1)
    command = HistoryDiagnosticRequest(
        request=request().request, run_id="scope", expected_revision=2, as_of="2026-10-25T00:00:00Z"
    )
    if classification is None:
        with pytest.raises(PersistenceError, match="required_held_security_missing"):
            w.diagnose_history(command)
        assert w.store.catalog()["runs"] == []
    else:
        assert w.diagnose_history(command).status == "partial"


def test_killed_restore_of_required_history_is_atomic_and_retryable(tmp_path: Path) -> None:
    w = workspace(tmp_path / "source")
    w.import_history(upload())
    saved = w.diagnose_history(
        HistoryDiagnosticRequest(
            request=request().request,
            run_id="required-history",
            expected_revision=2,
            as_of="2026-10-25T00:00:00Z",
        )
    )
    path = tmp_path / "current.sqlite3"
    path.write_bytes(backup(w.store))
    target = AdvisoryStore(RuntimeBoundary(tmp_path / "target"))
    code = """
import os,sys
from pathlib import Path
import prosper.advisory_store as module
from prosper.advisory_store import AdvisoryStore
from prosper.advisory_recovery import restore
from prosper.storage import RuntimeBoundary
s=AdvisoryStore.existing(RuntimeBoundary(Path(sys.argv[1])))
module._before_commit=lambda connection:os._exit(31)
restore(s,Path(sys.argv[3]).read_bytes())
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(target.runtime.root), str(ROOT), str(path)],
        capture_output=True,
    )
    assert result.returncode == 31 and result.stdout == result.stderr == b""
    assert target.current()["snapshot_id"] is None and target.history_batches() == ()
    restore(target, path.read_bytes())
    assert target.run(saved.id) == saved
    assert target.history_batches() == w.store.history_batches()


def second_part() -> HistoryPart:
    original = upload().parts[0]
    raw = b"Fictional second reviewed original source"
    frame = original.batch.rows.frame.filter(pl.col("security_id") == "security-b")
    batch = original.batch.model_copy(
        update={
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "rows": HistoryTable.pack(frame, "observations"),
            "contexts": tuple(c for c in original.batch.contexts if c.security_id == "security-b"),
        }
    )
    return HistoryPart(
        batch=batch, source_zlib_base64=base64.b64encode(zlib.compress(raw)).decode()
    )


def multipart() -> HistoryUpload:
    original = upload().parts[0]
    first = original.model_copy(
        update={
            "batch": original.batch.model_copy(
                update={
                    "contexts": tuple(
                        c for c in original.batch.contexts if c.security_id == "security-a"
                    ),
                    "rows": HistoryTable.pack(
                        original.batch.rows.frame.filter(pl.col("security_id") == "security-a"),
                        "observations",
                    ),
                }
            )
        }
    )
    return HistoryUpload(
        parts=(first, second_part()),
        part_count=2,
        command_key="multipart",
        expected_revision=1,
    )


@pytest.mark.parametrize("kind", ["missing", "duplicate", "corrupt", "contradictory"])
def test_manifest_or_any_bad_original_refuses_without_partial_activation(
    tmp_path: Path, kind: str
) -> None:
    w = workspace(tmp_path / "source")
    values = multipart().model_dump(mode="json")
    if kind == "missing":
        values["parts"].pop()
    if kind == "duplicate":
        values["parts"][1] = values["parts"][0]
    if kind == "corrupt":
        values["parts"][1]["source_zlib_base64"] = base64.b64encode(
            zlib.compress(b"altered original")
        ).decode()
    if kind == "contradictory":
        first = multipart().parts[0].batch
        values["parts"][1]["batch"] = first.model_copy(
            update={
                "source_sha256": second_part().batch.source_sha256,
                "rows": HistoryTable.pack(
                    first.rows.frame.with_columns((pl.col("close") + 1).alias("close")),
                    "observations",
                ),
            }
        ).model_dump(mode="json")
    with pytest.raises((ValueError, PersistenceError)):
        w.import_history(HistoryUpload.model_validate_json(json.dumps(values)))
    assert w.store.current()["revision"] == 1 and not w.store.history_batches()
    with w.store._connection() as connection:
        assert connection.execute("SELECT count(*) FROM sources").fetchone() == (1,)


def test_atomic_multipart_failure_retry_and_contradictions_are_honest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = workspace(tmp_path / "source")

    def fail(connection: sqlite3.Connection) -> None:
        raise PersistenceError("injected_multipart")

    monkeypatch.setattr(storage, "_before_commit", fail)
    with pytest.raises(PersistenceError, match="injected_multipart"):
        w.import_history(multipart())
    monkeypatch.undo()
    assert not w.store.history_batches() and w.store.current()["revision"] == 1
    result = w.import_history(multipart())
    assert result == {"outcome": "changed", "revision": 2}
    assert w.import_history(multipart()) == result
    assert len(w.store.history_batches()) == 2
    aligned = w.plan_history(request().request)
    assert aligned.complete and not aligned.issues
    assert aligned.rows.row_count == 6 and len(aligned.required_sources) == 2
    # Every reviewed original part is retained in the one accepted activation.
    assert (
        w.store.source_bytes(second_part().batch.source_sha256)
        == b"Fictional second reviewed original source"
    )


def test_saved_inputs_deduplicate_cache_independent_and_detect_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = workspace(tmp_path / "source")
    w.import_history(upload())
    command = HistoryDiagnosticRequest(
        request=request().request, run_id="first", expected_revision=2, as_of="2026-10-25T00:00:00Z"
    )
    first = w.diagnose_history(command)
    second = w.diagnose_history(command.model_copy(update={"run_id": "second"}))
    assert first.inputs["alignment_ref"] == second.inputs["alignment_ref"]
    assert (
        "history_alignment" not in first.inputs
        and "returns" not in first.outputs
        and "innovation" not in first.outputs
    )
    with w.store._connection() as connection:
        assert connection.execute("SELECT count(*) FROM input_records").fetchone() == (1,)
    w.store.clear_history_cache("clear", 2)
    monkeypatch.setattr(
        "prosper.workspace.align", lambda *args: pytest.fail("recalculated saved inputs")
    )
    assert w.diagnose_history(command) == first
    target = AdvisoryStore(RuntimeBoundary(tmp_path / "target"))
    restore(target, backup(w.store))
    assert target.run(first.id) == first
    assert target.alignment(str(first.inputs["alignment_ref"])) == w.store.alignment(
        str(first.inputs["alignment_ref"])
    )
    with closing(sqlite3.connect(w.store.runtime.path(storage.DATABASE_NAME))) as connection:
        connection.execute("UPDATE input_records SET document='{}'")
        connection.commit()
    assert w.store.run(first.id) == first
    with pytest.raises(PersistenceError, match="immutable_input_missing_or_corrupt"):
        backup(w.store)


@pytest.mark.parametrize(
    "kind", ["cardinality", "duplicate", "unknown", "nonfinite", "boolean", "date", "columns"]
)
def test_column_payload_cannot_hide_bad_cardinality_unknowns_or_numbers(kind: str) -> None:
    table = upload().parts[0].batch.rows
    columns = table.frame.to_dict(as_series=False)
    if kind == "cardinality":
        columns["open"].pop()
    if kind == "duplicate":
        for name in columns:
            columns[name][1] = columns[name][0]
    if kind == "unknown":
        columns["close"][0] = None
    if kind == "nonfinite":
        columns["open"][0] = float("inf")
    if kind == "boolean":
        columns["open"][0] = True
    if kind == "date":
        columns["session"][0] = "2026-02-30"
    if kind == "columns":
        columns["extra"] = [None] * table.row_count
    data = base64.b64encode(bz2.compress(json.dumps(columns).encode())).decode()
    with pytest.raises(ValueError):
        HistoryTable(kind="observations", row_count=table.row_count, data=data)


def test_bounded_decompression_and_explicit_calendar_count() -> None:
    compressed = zlib.compress(b"x" * 1024)
    for raw in (compressed, compressed[:-1], compressed + b"trailing", compressed + compressed):
        with pytest.raises(ValueError):
            decompress(raw, 100)
    assert decompress(compressed, 1024) == b"x" * 1024
    grid = SessionGrid.pack(("2026-10-20", "2026-10-21"))
    with pytest.raises(ValidationError):
        SessionGrid.model_validate_json(encode(grid.model_copy(update={"count": 1})))


def test_complete_window_is_not_inferred_from_a_full_validation_label() -> None:
    original = upload().parts[0].batch
    frame = original.rows.frame.slice(1)
    partial = original.model_copy(update={"rows": HistoryTable.pack(frame, "observations")})
    result = align(request().request, (partial,))
    assert not result.complete and result.rows.row_count == 6
    assert any(i.code == "missing_observation" for i in result.issues)


def test_immutable_input_owns_sources_before_a_run_can_start(tmp_path: Path) -> None:
    w = workspace(tmp_path / "source")
    w.import_history(upload())
    aligned = w.plan_history(request().request)
    identity = w.store.retain_alignment(aligned)
    w.store.clear_history_cache("clear", 2)
    assert w.store.alignment(identity) == aligned
    assert w.store.source_bytes(aligned.required_sources[0])
    assert backup(w.store)
    with closing(sqlite3.connect(w.store.runtime.path(storage.DATABASE_NAME))) as connection:
        connection.execute("DELETE FROM input_sources")
        connection.commit()
    with pytest.raises(PersistenceError, match="required_input_sources_missing"):
        backup(w.store)


def test_dictionary_logical_size_and_manifest_work_are_bounded_before_materializing() -> None:
    frame = upload().parts[0].batch.rows.frame
    columns = {name: {"value": frame[name][0]} for name in frame.columns}
    columns["source_ref"] = {"value": "x" * 4096}
    data = base64.b64encode(bz2.compress(json.dumps(columns).encode())).decode()
    with pytest.raises(ValueError, match="history_logical_text_size_limit"):
        HistoryTable(kind="observations", row_count=650000, data=data)
    values = multipart().model_dump(mode="json")
    for part in values["parts"]:
        part["batch"]["rows"]["row_count"] = 400000
    with pytest.raises(ValueError, match="history_observation_budget_exceeded"):
        HistoryUpload.model_validate_json(json.dumps(values))


def test_interrupted_diagnostic_cannot_recompute_after_required_original_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = workspace(tmp_path / "source")
    w.import_history(upload())
    command = HistoryDiagnosticRequest(
        request=request().request,
        run_id="interrupted-original",
        expected_revision=2,
        as_of="2026-10-25T00:00:00Z",
    )

    def interrupt(alignment: object) -> bool:
        raise RuntimeError("interrupted before output")

    monkeypatch.setattr("prosper.workspace.conventions_available", interrupt)
    with pytest.raises(RuntimeError, match="interrupted before output"):
        w.diagnose_history(command)
    monkeypatch.undo()
    assert w.store.run(command.run_id).status == "running"
    with closing(sqlite3.connect(w.store.runtime.path(storage.DATABASE_NAME))) as connection:
        connection.execute(
            "UPDATE sources SET zlib_bytes=x'00' WHERE sha256=?",
            (upload().parts[0].batch.source_sha256,),
        )
        connection.commit()
    with pytest.raises(PersistenceError, match="source_unavailable_or_corrupt"):
        w.diagnose_history(command)
    assert w.store.run(command.run_id).status == "running"


def test_other_window_original_is_not_a_required_input_for_this_window() -> None:
    r = request().request
    contexts = tuple(c.model_copy(update={"mapping_start": "2020-01-01"}) for c in r.series)
    r = r.model_copy(update={"series": contexts})
    original = changed(upload().parts[0].batch, contexts=contexts)
    other = changed(
        original,
        requested_sessions=("2026-10-19",),
        observations=tuple(
            row.model_copy(update={"session": "2026-10-19"})
            for row in original.observations
            if row.session == r.predecessor
        ),
        source_sha256="e" * 64,
        validation_scope="requested-interval",
    )
    result = align(r, (original, other), frozenset({other.source_sha256}))
    assert result.complete and result.required_sources == (original.source_sha256,)
    assert result.rows.row_count == len(r.sessions) * len(r.series)
