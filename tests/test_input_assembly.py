"""Selected-source assembly, EOD provenance and the existing frozen-input consumer."""

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import DATABASE_NAME
from prosper.api_contracts import LotSettingsRequest
from prosper.candidate_validation import FinalValidator
from prosper.candidate_workflow import FrozenCandidate, prepare
from prosper.input_assembly import InputAssemblyRequest, assemble, context
from prosper.modeled_inputs import InputCoverageSettings, ModeledDiagnostic
from prosper.storage import PersistenceError
from prosper.workspace import Workspace
from tests.test_candidate_workflow import command, load, seed, service


def request(w: Workspace, **changes: Any) -> InputAssemblyRequest:
    modeled = load("modeled.json")["bundle"]
    history = modeled["history"]
    raw = {
        "expected_revision": w.store.current()["revision"],
        "analysis_date": modeled["analysis_date"],
        "as_of": "2026-10-25T23:00:00Z",
        "history": {
            key: value
            for key, value in history.items()
            if key not in ("series", "profile", "manual_security_ids")
        },
        "coverage_settings": {
            key: modeled["profile"][key] for key in InputCoverageSettings.model_fields
        },
        "investor_controls": modeled["investor_controls"],
        "fact_run_id": "inputs",
    }
    raw["history"]["batch_ids"] = [c.id for c in context(w).history_options]
    raw.update(changes)
    return InputAssemblyRequest.model_validate_json(json.dumps(raw))


def test_eod_marks_are_observed_prices_not_old_marks_or_funding(tmp_path: Path) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    before = w.store.current()
    result = assemble(w, request(w))
    assert result.upload and result.coverage
    bundle = result.upload.bundle
    assert bundle.profile.preset and bundle.profile.preset.identity == "standard-r1-v1"
    assert bundle.profile.lookback_sessions == 1260
    assert result.candidate_security_ids == ("security-faaa", "security-fbbb")
    assert bundle.candidate_security_ids == result.candidate_security_ids
    assert [m.mark.price.value for m in bundle.marks] == [
        "125.49071432455037",
        "136.97476960887897",
    ]
    assert {i.code for i in result.issues} == {"lot_mark_conflict"}
    assert bundle.investor_controls == request(w).investor_controls
    for marked in bundle.marks:
        assert marked.mark.day.value == "2026-10-23"
        assert marked.evidence.effective == marked.evidence.valid_through == "2026-10-23"
        assert marked.evidence.source_ref == marked.mark.source_ref
        assert w.store.source_bytes(marked.evidence.source_sha256)
    assert w.store.current() == before
    assert assemble(w, request(w)) == result


@pytest.mark.parametrize("wrong_date", [False, True])
def test_supplied_marks_cannot_contradict_the_selected_close_or_eod_date(
    tmp_path: Path, wrong_date: bool
) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    original = assemble(w, request(w))
    assert original.upload
    supplied = original.upload.bundle.marks[0].model_dump(mode="json")
    if wrong_date:
        supplied["mark"]["day"]["value"] = "2026-10-22"
    else:
        supplied["mark"]["price"]["value"] = "10"
    changed = assemble(w, request(w, marks=[supplied]))
    assert changed.upload is None
    expected = "eod_supplied_mark_date_mismatch" if wrong_date else "eod_source_mark_conflict"
    assert expected in {i.code for i in changed.issues}


def test_explicit_mark_review_save_candidate_preparation_and_recovery(tmp_path: Path) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    first = assemble(w, request(w))
    assert first.upload
    # Resolve the reached conflict through the existing explicit settings action.
    old = load("lot-settings.json")
    old["marks"] = [m.mark.model_dump(mode="json") for m in first.upload.bundle.marks]
    w.configure_lots(
        LotSettingsRequest.model_validate_json(
            json.dumps({"settings": old, "command_key": "review-eod", "expected_revision": 4})
        )
    )
    with pytest.raises(PersistenceError, match="stale_revision"):
        w.preview_inputs(first.upload)
    prepared = assemble(w, request(w))
    assert prepared.upload and prepared.coverage and prepared.coverage.software_inputs_complete
    command_body = {
        **prepared.upload.model_dump(mode="json"),
        "run_id": "assembled",
        "expected_revision": 5,
        "as_of": "2026-10-25T23:00:00Z",
    }
    diagnostic = ModeledDiagnostic.model_validate_json(json.dumps(command_body))
    saved = w.diagnose_inputs(diagnostic)
    assert w.diagnose_inputs(diagnostic) == saved
    frozen = w.store.modeled_inputs(saved.inputs["modeled_inputs"])
    selected_history = request(w).history
    assert selected_history and frozen.bundle.assembly
    assert frozen.bundle.assembly.history_batch_ids == selected_history.batch_ids
    controls = command().controls.model_dump(mode="json")
    controls["buy_bounds"]["security-faaa"] = 0
    candidate_command = command(input_run_id="assembled", expected_revision=5, controls=controls)
    candidate = FrozenCandidate(
        command=candidate_command,
        modeled=frozen,
        coverage=prepared.coverage,
        snapshot=w.store.snapshot(saved.snapshot_id),
        retained_snapshots=(),
        required_sources=frozen.retained_sources,
    )
    candidate_request, issues = prepare(candidate)
    assert candidate_request and not issues, issues
    assert candidate_request.settings.cash_to_invest == "0"
    assert not FinalValidator(candidate_request).issues
    target = service(tmp_path / "restored")
    restore(target.store, backup(w.store))
    assert target.store.run(saved.id) == saved
    assert target.store.modeled_inputs(saved.inputs["modeled_inputs"]) == frozen
    w.store.clear_history_cache("clear", 5)
    assert w.diagnose_inputs(diagnostic) == saved
    with pytest.raises(PersistenceError, match="stale_revision"):
        w.preview_inputs(prepared.upload)


def test_no_fact_run_requires_explicit_taxonomy_and_source_facts(tmp_path: Path) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    absent = assemble(w, request(w, fact_run_id=None))
    assert absent.upload is None and "taxonomy_declaration_required" in {
        i.code for i in absent.issues
    }
    result = assemble(
        w, request(w, fact_run_id=None, taxonomy={"name": "Declared taxonomy", "version": "2026"})
    )
    assert result.upload and result.coverage and not result.coverage.software_inputs_complete
    assert not result.upload.bundle.securities and not result.upload.bundle.classifications
    assert "security_mapping_missing" in {i.code for i in result.issues}


def test_source_bound_held_identity_needs_no_per_security_reentry(tmp_path: Path) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    snapshot = w.store.snapshot(str(w.store.current()["snapshot_id"]))
    declaration = {
        "source_sha256": snapshot.source_sha256,
        "source_ref": "Explicit source declaration",
        "provider": "Fixture owner",
        "dataset": "Original normalized holdings",
        "permission_scope": "Fictional test inputs",
        "effective": "2026-10-23",
        "valid_through": "2026-10-23",
        "recorded_at": "2026-10-24T00:00:00Z",
    }
    prepared = assemble(
        w,
        request(
            w,
            fact_run_id=None,
            taxonomy={"name": "Declared source framework", "version": "1"},
            source_declarations=[declaration],
        ),
    )
    assert prepared.upload
    held = prepared.upload.bundle.securities[0]
    assert held.identity == snapshot.securities[0].identity
    assert held.classification == snapshot.securities[0].classification
    assert held.evidence.source_sha256 == snapshot.source_sha256
    assert held.evidence.source_ref == snapshot.securities[0].source_ref
    assert (
        prepared.upload.bundle.assembly
        and prepared.upload.bundle.assembly.source_declarations[0].source_ref
        == declaration["source_ref"]
    )


def test_dated_ivv_policy_populates_benchmark_identities_from_original_rows(tmp_path: Path) -> None:
    import base64
    import hashlib
    import zlib
    from datetime import UTC, datetime

    import polars as pl

    from prosper.api_contracts import HistoryUpload
    from prosper.benchmark import BenchmarkResult
    from prosper.history_table import HistoryTable, SessionGrid
    from tests.test_holdings_mapping import seed as ivv_seed

    w = ivv_seed(tmp_path / "ivv", cash=False)
    benchmark = BenchmarkResult.model_validate_json(json.dumps(w.store.run("benchmark").outputs))
    template = HistoryUpload.model_validate_json(json.dumps(load("history.json")))
    batch = template.parts[0].batch
    days = tuple(d for d in batch.requested_sessions if d <= benchmark.effective_date)
    frames, contexts = [], []
    for i, sid in enumerate(benchmark.security_ids):
        original = batch.contexts[i % len(batch.contexts)]
        contexts.append(
            original.model_copy(update={"security_id": sid, "provider_symbol": f"fixture-{i}"})
        )
        frames.append(
            batch.rows.frame.filter(
                (pl.col("security_id") == original.security_id) & pl.col("session").is_in(days)
            ).with_columns(pl.lit(sid).alias("security_id"))
        )
    frame = pl.concat(frames)
    source = frame.write_json().encode()
    updated = batch.model_copy(
        update={
            "contexts": tuple(contexts),
            "sessions": SessionGrid.pack(days),
            "rows": HistoryTable.pack(frame, "observations"),
            "source_sha256": hashlib.sha256(source).hexdigest(),
        }
    )
    part = template.parts[0].model_copy(
        update={
            "batch": updated,
            "source_zlib_base64": base64.b64encode(zlib.compress(source)).decode(),
        }
    )
    imported = template.model_copy(
        update={
            "parts": (part,),
            "part_count": 1,
            "command_key": "ivv-history",
            "expected_revision": 2,
        }
    )
    w.import_history(HistoryUpload.model_validate_json(imported.model_dump_json()))
    choices = context(w)
    observation = w.store.benchmark_observation(benchmark.observation_id)
    data = {
        "expected_revision": choices.input_revision,
        "analysis_date": benchmark.effective_date,
        "as_of": datetime.now(UTC).isoformat(),
        "history": {
            "batch_ids": [choices.history_options[0].id],
            "sessions": days[1:],
            "predecessor": days[0],
            "cutoff": days[-1],
            "known_at": batch.validated_at,
            "calendar_evidence": "Explicit fictional all-day grid",
            "overlap_sessions": 1,
        },
        "coverage_settings": {
            k: load("modeled.json")["bundle"]["profile"][k]
            for k in InputCoverageSettings.model_fields
        },
        "investor_controls": load("modeled.json")["bundle"]["investor_controls"],
        "taxonomy": {"name": "Unresolved fixture framework", "version": "1"},
        "source_declarations": [
            {
                "source_sha256": observation.source_sha256,
                "source_ref": "Declared issuer evidence",
                "provider": "BlackRock iShares",
                "dataset": "Original holdings",
                "permission_scope": "Fictional test inputs",
                "effective": benchmark.effective_date,
                "valid_through": benchmark.effective_date,
                "recorded_at": "2026-10-25T00:00:00Z",
            }
        ],
    }
    result = assemble(w, InputAssemblyRequest.model_validate_json(json.dumps(data)))
    assert result.upload and result.coverage and not result.coverage.software_inputs_complete
    facts = {s.security_id: s for s in result.upload.bundle.securities}
    assert set(benchmark.security_ids) <= set(facts)
    assert all(
        facts[s].identity.value == s
        and facts[s].evidence.source_sha256 == observation.source_sha256
        for s in benchmark.security_ids
    )
    assert result.candidate_security_ids == benchmark.security_ids


@pytest.mark.parametrize("field", ["history", "coverage_settings", "investor_controls"])
def test_missing_declarations_are_located_without_example_defaults(
    tmp_path: Path, field: str
) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    result = assemble(w, request(w, **{field: [] if field == "investor_controls" else None}))
    assert any(i.scope in ("history", "settings") for i in result.issues)
    assert result.coverage is None or not result.coverage.software_inputs_complete


@pytest.mark.parametrize(
    "problem", ["missing", "corrupt", "time", "context", "cutoff", "benchmark-time"]
)
def test_selected_history_has_no_cache_or_date_fallback(tmp_path: Path, problem: str) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    raw = request(w).model_dump(mode="json")
    if problem == "missing":
        raw["history"]["batch_ids"] = ["0" * 64]
    elif problem == "corrupt":
        digest = context(w).history_options[0].source_sha256
        with sqlite3.connect(w.store.runtime.path(DATABASE_NAME)) as connection:
            connection.execute(
                "UPDATE sources SET zlib_bytes=? WHERE sha256=?", (b"corrupt", digest)
            )
    elif problem == "time":
        raw["history"]["known_at"] = "2026-10-23T22:00:00Z"
    elif problem == "context":
        c = context(w).history_options[0].contexts[0].model_dump(mode="json")
        c["provider_symbol"] = "GUESSED"
        raw["history"]["series_choices"] = [c]
    elif problem == "benchmark-time":
        raw["as_of"] = "2026-10-22T00:00:00Z"
    else:
        raw["analysis_date"] = "2026-10-24"
    result = assemble(w, InputAssemblyRequest.model_validate_json(json.dumps(raw)))
    assert result.upload is None and result.issues
    if problem == "benchmark-time":
        assert "benchmark_knowledge_after_analysis" in {i.code for i in result.issues}


def test_conflicting_identity_and_mid_preparation_state_change_refuse(tmp_path: Path) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    raw = request(w).model_dump(mode="json")
    identity = load("modeled.json")["bundle"]["securities"][0]
    identity["identity"]["value"] = "contradictory"
    raw["securities"] = [identity]
    conflict = assemble(w, InputAssemblyRequest.model_validate_json(json.dumps(raw)))
    assert conflict.upload is None and "selected_identity_conflict" in {
        i.code for i in conflict.issues
    }
    current = w.store.current
    calls = 0

    def changing() -> Any:
        nonlocal calls
        calls += 1
        result = current()
        if calls > 1:
            result["revision"] = 99
        return result

    prepared_request = request(w)
    with (
        patch.object(w.store, "current", side_effect=changing),
        pytest.raises(PersistenceError, match="stale_revision"),
    ):
        assemble(w, prepared_request)


@pytest.mark.parametrize("ambiguous", [False, True])
def test_explicit_source_choice_survives_newer_cache_and_conflicts_are_not_selected(
    tmp_path: Path, ambiguous: bool
) -> None:
    import base64
    import hashlib
    import zlib

    import polars as pl

    from prosper.api_contracts import HistoryUpload
    from prosper.history_table import HistoryTable

    w = service(tmp_path / "runtime")
    seed(w)
    old = context(w).history_options[0]
    original = w.store.history_batches()[0]
    data = HistoryUpload.model_validate_json(json.dumps(load("history.json")))
    if ambiguous:
        batch = original.model_copy(
            update={
                "contexts": tuple(
                    c.model_copy(update={"provider_symbol": "EXPLICIT-ALIAS"})
                    if c.security_id == "security-faaa"
                    else c
                    for c in original.contexts
                )
            }
        )
        part = data.parts[0].model_copy(update={"batch": batch})
    else:
        frame = original.rows.frame.with_columns(
            pl.when(
                (pl.col("security_id") == "security-faaa") & (pl.col("session") == "2026-10-23")
            )
            .then(pl.col("close") + 1)
            .otherwise(pl.col("close"))
            .alias("close")
        )
        raw = frame.write_json().encode()
        batch = original.model_copy(
            update={
                "rows": HistoryTable.pack(frame, "observations"),
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "collected_at": "2026-10-24T00:00:00Z",
                "validated_at": "2026-10-24T00:00:00Z",
            }
        )
        part = data.parts[0].model_copy(
            update={
                "batch": batch,
                "source_zlib_base64": base64.b64encode(zlib.compress(raw)).decode(),
            }
        )
    incoming = data.model_copy(
        update={
            "parts": (part,),
            "part_count": 1,
            "command_key": "additional-source",
            "expected_revision": 4,
        }
    )
    w.import_history(HistoryUpload.model_validate_json(incoming.model_dump_json()))
    raw_request = request(w).model_dump(mode="json")
    raw_request["history"]["known_at"] = "2026-10-25T00:00:00Z"
    both = assemble(w, InputAssemblyRequest.model_validate_json(json.dumps(raw_request)))
    expected = (
        "history_context_ambiguous_or_missing"
        if ambiguous
        else "selected_history_unavailable_or_conflicting"
    )
    assert expected in {i.code for i in both.issues}
    raw_request["history"]["batch_ids"] = [old.id]
    selected = assemble(w, InputAssemblyRequest.model_validate_json(json.dumps(raw_request)))
    assert selected.upload
    assert selected.upload.bundle.marks[0].mark.price.value == "125.49071432455037"
    assert selected.upload.bundle.marks[0].evidence.source_sha256 == old.source_sha256
    if ambiguous:
        raw_request["history"]["batch_ids"] = [o.id for o in context(w).history_options]
        raw_request["history"]["series_choices"] = [
            next(c for c in original.contexts if c.security_id == "security-faaa").model_dump(
                mode="json"
            )
        ]
        resolved = assemble(w, InputAssemblyRequest.model_validate_json(json.dumps(raw_request)))
        assert resolved.upload and "history_context_ambiguous_or_missing" not in {
            i.code for i in resolved.issues
        }
