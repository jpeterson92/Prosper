"""Exact tiny comparisons, deliberate misses and independent final financial checks."""

import importlib
import json
import math
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from prosper.candidate_records import BuyOrder, CandidateRequest, CandidateSearch, Orders, SaleOrder
from prosper.candidate_reference import search as enumerate_all
from prosper.candidate_search import METHOD, search
from prosper.candidate_validation import FinalValidator, input_issues, validate

ROOT = Path(__file__).resolve().parents[1]


def tiny(**changes: Any) -> CandidateRequest:
    d = json.loads((ROOT / "examples/synthetic/candidates/tiny-request.json").read_bytes())
    d.update(method=METHOD, **changes)
    return CandidateRequest.model_validate_json(json.dumps(d))


def test_matches_tiny_loss_winner_and_retains_lower_risk_tradeoff() -> None:
    result = search(tiny())
    reference = enumerate_all(
        tiny().model_copy(update={"method": "complete-cartesian-whole-share-reference"})
    )
    assert result.best == reference.best
    assert result.outcome == "feasible-incumbent" and result.stopping == "proposal-set-exhausted"
    assert result.domain_states is None
    assert result.best and result.best.metrics and result.best.metrics.price_loss == 4
    assert [c.metrics.price_loss for c in result.candidates if c.metrics] == [4, 2]
    assert (
        result.candidates[1].metrics
        and result.best.metrics.tracking_error > result.candidates[1].metrics.tracking_error
    )
    for point in result.candidates:
        assert validate(result.inputs, point.orders) == point
    assert search(tiny()) == result


def test_deliberate_prefix_quantity_miss_never_claims_optimality() -> None:
    d = json.loads(tiny().model_dump_json())
    d["snapshot"]["lots"][0]["quantity"]["value"] = "3"
    d["snapshot"]["lots"][0]["total_basis"]["value"] = "36"
    d["sale_bounds"]["lot-a"] = 3
    d["limits"]["tracking_error"] = "0.065"
    request = CandidateRequest.model_validate_json(json.dumps(d))
    result = search(request)
    reference = enumerate_all(
        request.model_copy(update={"method": "complete-cartesian-whole-share-reference"})
    )
    assert result.best and result.best.metrics and result.best.metrics.price_loss == 2
    assert reference.best and reference.best.metrics and reference.best.metrics.price_loss == 4
    assert reference.best.orders.sales == (SaleOrder(lot_id="lot-a", shares=2),)
    assert result.outcome == "feasible-incumbent" and reference.outcome == "optimal-in-domain"
    assert any("no optimality gap" in s for s in result.warnings)


def test_no_candidate_is_not_proved_infeasible() -> None:
    d = json.loads(tiny().model_dump_json())
    d["snapshot"]["lots"][0]["total_basis"] = {"value": None, "reason": "Unknown basis"}
    result = search(CandidateRequest.model_validate_json(json.dumps(d)))
    assert result.best is None and result.outcome == "no-candidate"
    assert result.stopping == "proposal-set-exhausted"


def test_explicit_state_candidate_budgets_and_cancel() -> None:
    stopped = search(tiny(max_states=1))
    assert stopped.stopping == "state-limit" and stopped.evaluated_states == 1
    assert len(search(tiny(max_candidates=1)).candidates) == 1
    cancelled = search(tiny(), lambda: True)
    assert cancelled.stopping == "cancelled" and cancelled.evaluated_states == 0
    assert cancelled.best is None


def test_final_validator_freezes_input_and_inspects_covariance_only_once() -> None:
    request = tiny()
    with patch("prosper.candidate_validation.input_issues", wraps=input_issues) as inspect:
        validator = FinalValidator(request)
        request.sale_bounds.clear()
        good = Orders(
            sales=(SaleOrder(lot_id="lot-a", shares=2),),
            buys=(BuyOrder(security_id="security-fbbb", shares=1),),
        )
        assert validator.check(good).feasible
        assert not validator.check(
            Orders(sales=good.sales, buys=(BuyOrder(security_id="security-fbbb", shares=3),))
        ).feasible
        assert inspect.call_count == 1


def test_larger_complete_inventory_and_reference_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    factory = importlib.import_module("measure_candidate_search")
    request = factory.problem(20, max_states=3)
    assert len(request.assets) == 20 and len(request.snapshot.lots) == 60
    result = search(request)
    assert len(result.inputs.risk.security_ids) == 20 and len(result.inputs.sale_bounds) == 60
    assert result.evaluated_states == 3 and result.best
    assert result.best.feasible
    assert result.best.metrics
    active = [weight - 1 / 20 for weight in result.best.metrics.final_weights]
    variance = 0.04 * math.fsum(a * a for a in active) + 0.01 * math.fsum(active) ** 2
    assert result.best.metrics.tracking_error == pytest.approx(
        math.sqrt(variance), rel=1e-12, abs=1e-14
    )
    refused = enumerate_all(
        request.model_copy(update={"method": "complete-cartesian-whole-share-reference"})
    )
    assert refused.outcome == "invalid-input"
    assert "tiny_domain_dimension_limit" in refused.baseline.blockers


def test_restrictions_and_fees_are_not_relaxed_to_improve_yield() -> None:
    d = json.loads(tiny().model_dump_json())
    d["settings"]["manual_restrictions"] = [
        dict(
            name="restricted",
            identity=dict(value="fictional-identity:FAAA", reason=None),
            side="both",
            source_ref="manual:1",
        )
    ]
    assert search(CandidateRequest.model_validate_json(json.dumps(d))).best is None
    d = json.loads(tiny().model_dump_json())
    d["settings"]["sell_fee_per_isolated_order"]["value"] = "21"
    result = search(CandidateRequest.model_validate_json(json.dumps(d)))
    assert result.best is None and result.outcome == "no-candidate"


def test_callback_cannot_change_frozen_search_bounds() -> None:
    request = tiny()

    def callback() -> bool:
        request.buy_bounds.clear()
        return False

    assert search(request, callback) == search(tiny())


def test_wrong_method_is_rejected() -> None:
    with pytest.raises(ValueError, match="explicit_heuristic_method_required"):
        search(tiny().model_copy(update={"method": "complete-cartesian-whole-share-reference"}))


def test_saved_heuristic_cannot_be_relabelled_as_an_optimum() -> None:
    document = search(tiny()).model_dump(mode="json")
    document["outcome"] = "optimal-in-domain"
    with pytest.raises(ValidationError, match="heuristic_cannot_claim_domain_proof"):
        CandidateSearch.model_validate_json(json.dumps(document))
