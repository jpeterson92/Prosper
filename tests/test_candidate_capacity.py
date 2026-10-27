"""Representative source/accounting checks; no large history generation or fitting."""

import base64
import copy
import hashlib
import importlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

from prosper.advisory_store import AdvisoryStore
from prosper.api_contracts import LotSettingsRequest, Upload
from prosper.benchmark import BenchmarkDiagnostic, BenchmarkImport, BenchmarkReview
from prosper.candidate_records import BuyOrder, CandidateRequest, Orders, SaleOrder
from prosper.candidate_search import METHOD, search
from prosper.candidate_validation import validate
from prosper.candidate_workflow import CandidateStart, prepare
from prosper.modeled_inputs import ModeledDiagnostic, ModeledUpload
from prosper.storage import PersistenceError, RuntimeBoundary
from prosper.workspace import Workspace
from tests.test_candidate_workflow import stub, wait

ROOT = Path(__file__).resolve().parents[1]


def test_hand_derived_sell_buy_with_representative_fees_and_spreads() -> None:
    document = json.loads((ROOT / "examples/synthetic/candidates/tiny-request.json").read_bytes())
    document.update(method=METHOD, buy_fee_per_security_order="1", buy_premium_bps="10")
    document["settings"]["sell_fee_per_isolated_order"]["value"] = "1"
    document["settings"]["sell_discount_bps"]["value"] = "10"
    request = CandidateRequest.model_validate_json(json.dumps(document))
    orders = Orders(
        sales=(SaleOrder(lot_id="lot-a", shares=2),),
        buys=(BuyOrder(security_id="security-fbbb", shares=1),),
    )
    checked = validate(request, orders)
    assert checked.feasible and checked.metrics
    metrics = checked.metrics
    # Direct cash/NAV and diagonal quadratic form, independently of the search.
    assert metrics.price_loss == 4 and metrics.long_term_loss == 4
    assert metrics.final_cash == pytest.approx(20 * 0.999 - 1 - 10 * 1.001 - 1)
    assert metrics.modeled_cost == pytest.approx(2.03)
    assert metrics.final_nav == pytest.approx(22.97)
    assert metrics.final_quantities == (0.5, 1)
    assert metrics.tracking_error == pytest.approx(
        math.sqrt(0.04 * (5 / 22.97 - 0.5) ** 2 + 0.09 * (10 / 22.97 - 0.5) ** 2)
    )
    assert search(request).best == checked
    # Gross sale principal cannot fund two replacement shares after both costs.
    unfunded = validate(
        request,
        orders.model_copy(update={"buys": (BuyOrder(security_id="security-fbbb", shares=2),)}),
    )
    assert "unfunded_final_cash" in unfunded.blockers


def factory(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("candidate_capacity_fixtures")


def test_complete_representative_source_shape_without_a_large_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder = factory(monkeypatch)
    # Only metadata is expanded: this guard never builds/fits a 500-name grid.
    model = builder.load("modeled.json")
    bundle = model["bundle"]
    for key in ("securities", "marks", "classifications"):
        original = bundle[key][0]
        bundle[key] = []
        for i in range(500):
            item = copy.deepcopy(original)
            subject = item["mark"] if key == "marks" else item
            subject["security_id"] = f"S{i:04d}"
            bundle[key].append(item)
    sources, changed = builder.representative_sources(
        ModeledUpload.model_validate_json(json.dumps(model)), builder.Workload()
    )
    snapshot = Upload.model_validate_json(json.dumps(sources["holdings.json"])).snapshot
    raw = base64.b64decode(sources["holdings.json"]["source_base64"])
    assert hashlib.sha256(raw).hexdigest() == snapshot.source_sha256
    assert len(snapshot.securities) == 100 and len(snapshot.lots) == 2000
    assert len({lot.security_id for lot in snapshot.lots}) == 100
    assert len({lot.source_ref for lot in snapshot.lots}) == 2000
    assert snapshot.lots[0].quantity.value == "2.5000"
    assert [lot.total_basis.value for lot in snapshot.lots[:5]] == [
        "30.00",
        "32.50",
        "35.00",
        "37.50",
        "40.00",
    ]
    assert raw.count(b"\n") == 2001
    controls = sources["command.json"]["controls"]
    assert len(controls["sale_bounds"]) == 2000 and set(controls["sale_bounds"].values()) == {2}
    assert len(controls["buy_bounds"]) == 25 and set(controls["buy_bounds"].values()) == {100}
    assert not set(controls["buy_bounds"]) & {lot.security_id for lot in snapshot.lots}
    assert tuple(controls["buy_bounds"]) == changed.bundle.candidate_security_ids
    assert (
        changed.bundle.history
        == ModeledUpload.model_validate_json(json.dumps(model)).bundle.history
    )
    fixture = BenchmarkImport.model_validate_json(json.dumps(sources["benchmark.json"]))
    review = BenchmarkReview.model_validate_json(json.dumps(sources["benchmark-review.json"]))
    benchmark_raw = base64.b64decode(fixture.source_base64)
    assert hashlib.sha256(benchmark_raw).hexdigest() == review.stipulation.raw_sha256
    rows = json.loads(benchmark_raw)["2000-01-03"]["equity"]
    assert len(rows) == len(review.stipulation.rows) == len(review.policy.decisions) == 500
    assert all(row["percentOfFunds"] == "" and row["marketValue"] == "100.00" for row in rows)
    assert len({r.security.security_id for r in review.stipulation.rows if r.security}) == 500


@pytest.mark.parametrize(
    "held,lots,buy", [(0, 1, 1), (2, 0, 1), (2, 2, 0), (4, 1, 2), (2, 1001, 1)]
)
def test_invalid_declared_workload_refuses(
    monkeypatch: pytest.MonkeyPatch, held: int, lots: int, buy: int
) -> None:
    builder = factory(monkeypatch)
    upload = ModeledUpload.model_validate_json(json.dumps(builder.load("modeled.json")))
    with pytest.raises(ValueError, match="explicit_complete_representative_shape_required"):
        builder.representative_sources(upload, builder.Workload(held, lots, buy))


def test_generated_small_sources_actual_diagnostics_retry_and_recovery_without_fitting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder = factory(monkeypatch)
    measure = importlib.import_module("measure_candidate_capacity")
    history, upload = measure.inputs(5)
    sources, upload = builder.representative_sources(upload, builder.Workload(2, 2, 1))
    w = Workspace(AdvisoryStore(RuntimeBoundary(tmp_path / "source")))
    staged = w.stage(Upload.model_validate_json(json.dumps(sources["holdings.json"])))
    w.store.select(staged.id, "holdings", 0)
    w.import_benchmark(BenchmarkImport.model_validate_json(json.dumps(sources["benchmark.json"])))
    benchmark = w.diagnose_benchmark(
        BenchmarkDiagnostic.model_validate_json(
            json.dumps(
                {
                    "run_id": "benchmark",
                    "expected_revision": 1,
                    "as_of": "2026-10-25T23:00:00Z",
                    "review": sources["benchmark-review.json"],
                }
            )
        )
    )
    assert benchmark.outputs["security_ids"] == [s.security_id for s in upload.bundle.securities]
    assert benchmark.outputs["equity_value_total"] == "500.0"
    assert benchmark.outputs["weights"] == [0.2] * 5
    w.store.select_benchmark("benchmark", "benchmark", 1)
    w.configure_lots(
        LotSettingsRequest.model_validate_json(
            json.dumps(
                {
                    "settings": sources["lot-settings.json"],
                    "command_key": "settings",
                    "expected_revision": 2,
                }
            )
        )
    )
    w.import_history(history)
    diagnostic = w.diagnose_inputs(
        ModeledDiagnostic.model_validate_json(
            json.dumps(
                {
                    **upload.model_dump(mode="json"),
                    "run_id": "inputs",
                    "expected_revision": 4,
                    "as_of": "2026-10-25T23:00:00Z",
                }
            )
        )
    )
    assert diagnostic.outputs["software_inputs_complete"], diagnostic.outputs["issues"]
    calls = stub(monkeypatch)
    command = sources["command.json"]
    command["controls"]["method"] = "deterministic-loss-prefix-repair-v1"
    w.start_candidate(CandidateStart.model_validate_json(json.dumps(command)))
    saved = wait(w)
    assert saved.outputs["outcome"] == "unavailable"
    frozen = w.store.candidate_inputs(saved.inputs["candidate_inputs"])
    request, issues = prepare(frozen)
    assert request is not None and not issues
    no_basis_review = request.model_copy(
        update={"snapshot": request.snapshot.model_copy(update={"observations": {}})}
    )
    from prosper.candidate_validation import input_issues

    assert "reported_basis_assumption_unreviewed" in input_issues(no_basis_review)
    assert w.start_candidate(CandidateStart.model_validate_json(json.dumps(command))) == saved
    assert calls == [1]
    report = measure.recover(w.store, tmp_path)
    assert report["identical_result_and_originals"] and report["source_state_preserved"]
    assert report["original_count"] == 9
    assert report["bytes"] > 0

    def refused(_: Any) -> bytes:
        raise PersistenceError("backup_size_limit")

    monkeypatch.setattr(measure, "backup", refused)
    failure = measure.recover(w.store, tmp_path)
    assert failure["bytes"] is None and failure["refusal"] == "backup_size_limit"
    assert failure["original_count"] == 9 and failure["source_state_preserved"]
