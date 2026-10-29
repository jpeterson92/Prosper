"""Full-union expectations, located unknowns, frozen inputs and original-source recovery."""

import json
import sqlite3
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import DATABASE_NAME, AdvisoryStore
from prosper.api_contracts import HistoryUpload, LotSettingsRequest, Upload
from prosper.benchmark import BenchmarkDiagnostic, BenchmarkImport, BenchmarkReview
from prosper.modeled_inputs import (
    InputProfile,
    ModeledDiagnostic,
    ModeledUpload,
    RiskPresetRequest,
    prepare_risk_preset,
)
from prosper.storage import PersistenceError, RuntimeBoundary
from prosper.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "examples/synthetic/modeled-inputs"


def service(path: Path) -> Workspace:
    return Workspace(AdvisoryStore(RuntimeBoundary(path)))


def upload() -> ModeledUpload:
    return ModeledUpload.model_validate_json((FOLDER / "current.json").read_bytes())


def seed(workspace: Workspace) -> None:
    staged = workspace.stage(
        Upload.model_validate_json(
            (ROOT / "examples/synthetic/advisory-workspace.json").read_bytes()
        )
    )
    workspace.store.select(staged.id, "snapshot", 0)
    benchmark = FOLDER
    workspace.import_benchmark(
        BenchmarkImport.model_validate_json((benchmark / "benchmark.json").read_bytes())
    )
    workspace.diagnose_benchmark(
        BenchmarkDiagnostic(
            run_id="benchmark",
            expected_revision=1,
            as_of="2026-10-25T22:00:00Z",
            review=BenchmarkReview.model_validate_json(
                (benchmark / "benchmark-review.json").read_bytes()
            ),
        )
    )
    workspace.store.select_benchmark("benchmark", "benchmark-choice", 1)
    settings = json.loads((FOLDER / "lot-settings.json").read_bytes())
    workspace.configure_lots(
        LotSettingsRequest.model_validate_json(
            json.dumps(
                {"settings": settings, "command_key": "lot-settings", "expected_revision": 2}
            )
        )
    )
    history = json.loads((FOLDER / "history.json").read_bytes())
    history["expected_revision"] = 3
    workspace.import_history(HistoryUpload.model_validate_json(json.dumps(history)))


def command(
    raw: ModeledUpload | None = None, identity: str = "inputs", revision: int = 4
) -> ModeledDiagnostic:
    value = (raw or upload()).model_dump(mode="json")
    return ModeledDiagnostic.model_validate_json(
        json.dumps(
            {
                **value,
                "run_id": identity,
                "expected_revision": revision,
                "as_of": "2026-10-25T22:00:00Z",
            }
        )
    )


def test_standard_r1_preserves_facts_and_blocks_short_history(tmp_path: Path) -> None:
    original = upload()
    prepared = prepare_risk_preset(RiskPresetRequest(upload=original))
    profile = prepared.bundle.profile
    assert profile.preset and profile.preset.identity == "standard-r1-v1"
    assert profile.preset.overrides == {}
    assert profile.model and profile.model.model_dump() == {
        "identity": "R1",
        "f": "0.25",
        "a3": "0.17",
        "kappa": "10000",
    }
    assert (profile.lookback_sessions, profile.minimum_history_sessions) == (1260, 1260)
    assert (profile.horizon_sessions, profile.annualization_sessions) == (21, 252)
    assert profile.require_full_window_validation
    # Every source fact/calendar/cutoff/session/limit is identical. Only declared
    # estimator settings (including their matching history profile) are prepared.
    assert prepared.sources == original.sources
    assert prepared.bundle.model_dump(exclude={"profile", "history"}) == original.bundle.model_dump(
        exclude={"profile", "history"}
    )
    assert prepared.bundle.history.model_dump(
        exclude={"profile"}
    ) == original.bundle.history.model_dump(exclude={"profile"})
    for key in (
        "max_mark_age_days",
        "max_snapshot_age_days",
        "max_benchmark_age_days",
        "max_history_age_days",
        "maximum_universe_size",
        "short_history_policy",
    ):
        assert getattr(profile, key) == getattr(original.bundle.profile, key)
    workspace = service(tmp_path / "runtime")
    seed(workspace)
    result = workspace.preview_inputs(prepared)
    assert "history_length_mismatch" in {issue.code for issue in result.issues}
    assert len(result.sessions) == 3 and len(result.security_ids) == 5
    assert not result.software_inputs_complete and not result.risk_available


@pytest.mark.parametrize("overrides", [{}, {"horizon_sessions": 1}, {"horizon_sessions": 21}])
def test_preset_and_explicit_overrides_survive_retry_reopen_recovery(
    tmp_path: Path, overrides: dict[str, int]
) -> None:
    prepared = prepare_risk_preset(
        RiskPresetRequest.model_validate_json(
            json.dumps({"upload": upload().model_dump(mode="json"), "overrides": overrides})
        )
    )
    workspace = service(tmp_path / "runtime")
    seed(workspace)
    request = command(prepared)
    saved = workspace.diagnose_inputs(request)
    assert workspace.diagnose_inputs(request) == saved
    frozen = workspace.store.modeled_inputs(saved.inputs["modeled_inputs"])
    assert frozen.bundle.profile == prepared.bundle.profile
    assert frozen.bundle.profile.preset and frozen.bundle.profile.preset.overrides == overrides
    assert service(tmp_path / "runtime").store.run(saved.id) == saved
    target = service(tmp_path / "restored")
    restore(target.store, backup(workspace.store))
    assert target.store.run(saved.id) == saved
    assert (
        target.store.modeled_inputs(saved.inputs["modeled_inputs"]).bundle.profile
        == prepared.bundle.profile
    )
    document = prepared.bundle.profile.model_dump(mode="json")
    document["horizon_sessions"] = 7
    with pytest.raises(ValueError, match="risk_preset_effective_settings_mismatch"):
        InputProfile.model_validate_json(json.dumps(document))


@pytest.mark.parametrize(
    "overrides",
    [
        {"horizon_sessions": 0},
        {"horizon_sessions": "1"},
        {"horizon_sessions": True},
        {"model": None},
        {"lookback_sessions": None},
        {"tracking_error": "1"},
        {"require_full_window_validation": "false"},
    ],
)
def test_invalid_risk_overrides_are_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        RiskPresetRequest.model_validate_json(
            json.dumps({"upload": upload().model_dump(mode="json"), "overrides": overrides})
        )


def test_preset_refuses_contradictory_history_profile() -> None:
    document = upload().model_dump(mode="json")
    document["bundle"]["history"]["profile"]["f"] = "0.5"
    with pytest.raises(ValueError, match="model_profile_missing_or_mismatch"):
        prepare_risk_preset(RiskPresetRequest.model_validate_json(json.dumps({"upload": document})))


def test_complete_union_order_values_and_saved_original_input_recovery(tmp_path: Path) -> None:
    workspace = service(tmp_path / "runtime")
    seed(workspace)
    preview = workspace.preview_inputs(upload())
    assert preview.software_inputs_complete, preview.issues
    assert preview.security_ids == (
        "FICTIONAL-0",
        "FICTIONAL-1",
        "security-a",
        "security-b",
        "security-c",
    )
    assert preview.return_cell_count == 15 and preview.unavailable_return_count == 0
    # Lot and independent position both say 12.5; they are not two exposures.
    assert preview.members[2].held_quantity == 12.5 and preview.members[2].mark == 12
    # Source values 60/30; adjusted-close endpoints independently imply these
    # later-date values. This avoids reusing the daily compounding algorithm.
    alpha, beta = 60 * 198 / 200, 30 * 208 / 210
    assert preview.members[0].benchmark_weight == pytest.approx(alpha / (alpha + beta))
    assert preview.members[1].benchmark_weight == pytest.approx(beta / (alpha + beta))
    assert any("2026-10-20 to 2026-10-23" in warning for warning in preview.warnings)
    assert preview.members[4].roles == ("candidate",)
    assert preview.innovation_inputs_available and not preview.risk_available
    saved = workspace.diagnose_inputs(command())
    frozen = workspace.store.modeled_inputs(saved.inputs["modeled_inputs"])
    assert frozen.benchmark and frozen.benchmark.weights == pytest.approx((2 / 3, 1 / 3))
    assert frozen.benchmark.effective_date == "2026-10-20"
    assert saved.outputs["software_inputs_complete"] is True
    assert "source_base64" not in json.dumps(saved.inputs)
    assert workspace.diagnose_inputs(command()) == saved
    workspace.store.clear_history_cache("clear", 4)
    assert service(tmp_path / "runtime").store.run(saved.id) == saved
    target = service(tmp_path / "restored")
    restore(target.store, backup(workspace.store))
    assert target.store.run(saved.id) == saved
    assert target.diagnose_inputs(command()) == saved
    assert not target.preview_inputs(upload()).software_inputs_complete


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("mark", "mark_missing"),
        ("stale", "mark_stale_or_future"),
        ("identity", "held_identity_unresolved_or_conflicting"),
        ("taxonomy", "classification_unknown"),
        ("series", "series_context_missing"),
        ("conventions", "idr_conventions_unqualified"),
        ("capacity", "universe_capacity_exceeded"),
        ("controls", "investor_control_unspecified"),
        ("profile", "model_profile_missing_or_mismatch"),
        ("sources", "source_unavailable"),
    ],
)
def test_missing_or_conflicting_fact_blocks_affected_input_without_dropping_name(
    tmp_path: Path, mutation: str, code: str
) -> None:
    workspace = service(tmp_path / "runtime")
    seed(workspace)
    document: dict[str, Any] = json.loads(upload().model_dump_json())
    bundle = document["bundle"]
    if mutation == "mark":
        bundle["marks"].pop()
    elif mutation == "stale":
        bundle["marks"][0]["mark"]["day"]["value"] = "2000-01-03"
    elif mutation == "identity":
        bundle["securities"][2]["identity"]["value"] = "contradiction"
    elif mutation == "taxonomy":
        bundle["classifications"][0]["industry"] = {
            "value": None,
            "reason": "Unresolved supplied mapping",
        }
    elif mutation == "series":
        bundle["history"]["series"].pop(0)
    elif mutation == "conventions":
        bundle["history"]["series"][0]["adjustment"] = "total-return-adjusted"
    elif mutation == "capacity":
        bundle["profile"]["maximum_universe_size"] = 2
    elif mutation == "controls":
        bundle["investor_controls"].pop()
    elif mutation == "profile":
        bundle["profile"]["model"] = None
    else:
        document["sources"] = []
    changed = ModeledUpload.model_validate_json(json.dumps(document))
    result = workspace.preview_inputs(changed)
    assert not result.software_inputs_complete and code in {i.code for i in result.issues}
    assert len(result.security_ids) == 5 and result.return_cell_count == 15
    saved = workspace.diagnose_inputs(command(changed))
    assert (
        saved.outputs["software_inputs_complete"] is False
        and saved.outputs["risk_available"] is False
    )


def test_interrupted_inputs_resume_frozen_grid_after_cache_and_settings_change(
    tmp_path: Path,
) -> None:
    workspace = service(tmp_path / "runtime")
    seed(workspace)
    with patch.object(workspace.store, "complete_run", side_effect=RuntimeError("interrupted")):
        with pytest.raises(RuntimeError):
            workspace.diagnose_inputs(command())
    assert workspace.store.run("inputs").status == "running"
    workspace.store.clear_history_cache("clear", 4)
    resumed = service(tmp_path / "runtime").diagnose_inputs(command())
    assert resumed.outputs["software_inputs_complete"] is True
    assert workspace.store.current()["current_run_id"] is None
    changed = command(identity="inputs").model_copy(update={"as_of": "2026-10-25T23:00:00Z"})
    with pytest.raises(PersistenceError, match="analysis_id_reused"):
        workspace.diagnose_inputs(changed)


def test_missing_benchmark_and_unknown_holdings_are_preserved_as_blockers(tmp_path: Path) -> None:
    workspace = service(tmp_path / "runtime")
    staged = workspace.stage(
        Upload.model_validate_json(
            (ROOT / "examples/synthetic/advisory-workspace.json").read_bytes()
        )
    )
    workspace.store.select(staged.id, "snapshot", 0)
    result = workspace.preview_inputs(upload())
    assert "security-a" in result.security_ids
    assert {
        "selected_benchmark_required",
        "lot_settings_required",
        "required_history_incomplete",
    } <= {i.code for i in result.issues}


def test_required_input_source_loss_blocks_backup_without_hiding_saved_output(
    tmp_path: Path,
) -> None:
    workspace = service(tmp_path / "runtime")
    seed(workspace)
    saved = workspace.diagnose_inputs(command())
    digest = upload().sources[0].sha256
    with sqlite3.connect(workspace.store.runtime.path(DATABASE_NAME)) as connection:
        connection.execute("UPDATE sources SET zlib_bytes=? WHERE sha256=?", (b"damaged", digest))
    assert workspace.store.run(saved.id) == saved
    with pytest.raises(PersistenceError, match="source_unavailable_or_corrupt"):
        backup(workspace.store)


def test_changed_full_window_source_creates_new_inputs_without_rewriting_old_result(
    tmp_path: Path,
) -> None:
    import base64
    import hashlib

    workspace = service(tmp_path / "runtime")
    seed(workspace)
    old = workspace.diagnose_inputs(command())
    history = json.loads((FOLDER / "history.json").read_bytes())
    import zlib

    from prosper.history_table import observations

    history["parts"][0]["batch"]["validated_at"] = "2026-10-25T01:00:00Z"
    batch = HistoryUpload.model_validate_json(json.dumps(history)).parts[0].batch
    rows = tuple(
        row.model_copy(
            update={
                "close": row.close.model_copy(update={"value": float(row.close.value or 0) - 1}),
                "adjusted_close": row.adjusted_close.model_copy(
                    update={"value": float(row.adjusted_close.value or 0) - 1}
                ),
            }
        )
        if row.security_id == "security-c" and row.session == "2026-10-23"
        else row
        for row in batch.observations
    )
    table = observations(rows)
    raw = json.dumps([row.model_dump(mode="json") for row in rows]).encode()
    history["parts"][0]["batch"]["rows"] = table.model_dump(mode="json")
    history["parts"][0]["batch"]["source_sha256"] = hashlib.sha256(raw).hexdigest()
    history["parts"][0]["source_zlib_base64"] = base64.b64encode(zlib.compress(raw)).decode()
    history["command_key"] = "changed-history"
    history["expected_revision"] = 4
    workspace.import_history(HistoryUpload.model_validate_json(json.dumps(history)))
    data = upload().model_dump(mode="json")
    data["bundle"]["history"]["known_at"] = "2026-10-25T02:00:00Z"
    changed = ModeledUpload.model_validate_json(json.dumps(data))
    current = workspace.diagnose_inputs(command(changed, "new-inputs", 5))
    assert isinstance(current.inputs["modeled_inputs"], dict)
    assert isinstance(old.inputs["modeled_inputs"], dict)
    assert (
        dict(current.inputs["modeled_inputs"])["alignment_ref"]
        != dict(old.inputs["modeled_inputs"])["alignment_ref"]
    )
    assert workspace.store.run(old.id) == old


def test_more_than_500_names_are_retained_even_when_coverage_and_capacity_fail(
    tmp_path: Path,
) -> None:
    workspace = service(tmp_path / "runtime")
    seed(workspace)
    data = upload().model_dump(mode="json")
    data["bundle"]["candidate_security_ids"] = [f"candidate-{i:04}" for i in range(600)]
    result = workspace.preview_inputs(ModeledUpload.model_validate_json(json.dumps(data)))
    assert len(result.security_ids) == 603
    assert result.return_cell_count == 3 * 603
    assert not result.software_inputs_complete


def test_supplied_position_disagreement_and_unrepresentable_quantity_block_coverage(
    tmp_path: Path,
) -> None:
    from prosper.advisory_records import DecimalFact
    from prosper.modeled_inputs import evaluate

    workspace = service(tmp_path / "runtime")
    seed(workspace)
    run = workspace.diagnose_inputs(command())

    frozen = workspace.store.modeled_inputs(run.inputs["modeled_inputs"])
    snapshot = workspace.store.snapshot(run.snapshot_id)
    changed = snapshot.model_copy(
        update={
            "positions": (
                snapshot.positions[0].model_copy(
                    update={"quantity": DecimalFact(value="12.5000000000000000000000001")}
                ),
            )
        }
    )
    result = evaluate(
        changed,
        frozen.benchmark,
        frozen.lot_settings,
        frozen.bundle,
        frozen.alignment,
        run.as_of,
        frozenset(frozen.available_sources),
        frozen.benchmark_sources,
        4,
    )
    assert "position_quantity_conflict" in {i.code for i in result.issues}
    tiny = snapshot.model_copy(
        update={
            "lots": (
                snapshot.lots[0].model_copy(update={"quantity": DecimalFact(value="1e-512")}),
            ),
            "positions": (),
        }
    )
    result = evaluate(
        tiny,
        frozen.benchmark,
        frozen.lot_settings,
        frozen.bundle,
        frozen.alignment,
        run.as_of,
        frozenset(frozen.available_sources),
        frozen.benchmark_sources,
        4,
    )
    assert "held_quantity_unknown" in {i.code for i in result.issues}
    assert next(m for m in result.members if m.security_id == "security-a").held_quantity is None


def test_decimal_supplied_sum_retains_small_addend_across_full_supported_range() -> None:
    from decimal import Context, Decimal, localcontext

    from prosper.advisory import supplied_sum

    total = supplied_sum(("1e308", "1e-512"))
    with localcontext(Context(prec=1000)):
        assert total - Decimal("1e308") == Decimal("1e-512")


def test_reserved_future_revision_cannot_capture_earlier_inputs(tmp_path: Path) -> None:
    workspace = service(tmp_path / "runtime")
    seed(workspace)
    prepare = workspace._prepare_inputs

    def concurrent_edit(raw: ModeledUpload, as_of: str) -> Any:
        prepared = prepare(raw, as_of)
        workspace.store.clear_history_cache("other-window", 4)
        return prepared

    with patch.object(workspace, "_prepare_inputs", side_effect=concurrent_edit):
        with pytest.raises(PersistenceError, match="stale_revision"):
            workspace.diagnose_inputs(command(revision=5))
    with pytest.raises(PersistenceError, match="analysis_missing"):
        workspace.store.run("inputs")


def test_excluded_held_class_cannot_reenter_as_conflicting_candidate_and_bad_benchmark_is_unknown(
    tmp_path: Path,
) -> None:
    from prosper.advisory_records import Fact
    from prosper.benchmark import BenchmarkResult
    from prosper.modeled_inputs import evaluate

    workspace = service(tmp_path / "runtime")
    seed(workspace)
    saved = workspace.diagnose_inputs(command())
    frozen = workspace.store.modeled_inputs(saved.inputs["modeled_inputs"])
    snapshot = workspace.store.snapshot(saved.snapshot_id)
    changed = snapshot.model_copy(
        update={
            "securities": (
                snapshot.securities[0].model_copy(
                    update={"classification": Fact[str](value="ETF")}
                ),
            )
        }
    )
    bundle = frozen.bundle.model_copy(
        update={"candidate_security_ids": (*frozen.bundle.candidate_security_ids, "security-a")}
    )
    result = evaluate(
        changed,
        frozen.benchmark,
        frozen.lot_settings,
        bundle,
        frozen.alignment,
        saved.as_of,
        frozenset(frozen.available_sources),
        frozen.benchmark_sources,
        4,
    )
    assert "held_classification_conflict" in {i.code for i in result.issues}
    assert not result.software_inputs_complete
    assert frozen.benchmark is not None
    bad = frozen.benchmark.model_dump(mode="json")
    bad.update(status="incomplete", equity_value_total=None, security_ids=[], weights=[])
    result = evaluate(
        snapshot,
        BenchmarkResult.model_validate_json(json.dumps(bad)),
        frozen.lot_settings,
        frozen.bundle,
        frozen.alignment,
        saved.as_of,
        frozenset(frozen.available_sources),
        frozen.benchmark_sources,
        4,
    )
    assert "selected_benchmark_incomplete" in {i.code for i in result.issues}
    assert all(member.benchmark_weight is None for member in result.members)
