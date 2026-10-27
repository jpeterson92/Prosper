"""Hand-derived tiny outcomes and adversarial final-order checks, without fits."""

import copy
import hashlib
import json
import math
from collections.abc import Callable
from decimal import Inexact, localcontext
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from prosper.candidate_records import (
    BuyOrder,
    CandidateRequest,
    CandidateSearch,
    Orders,
    SaleOrder,
)
from prosper.candidate_reference import search
from prosper.candidate_validation import validate

FIXTURE = Path(__file__).resolve().parents[1] / "examples/synthetic/candidates/tiny-request.json"
A, B = "security-faaa", "security-fbbb"


def tiny(edit: Callable[[Any], None] | None = None) -> CandidateRequest:
    document = json.loads(FIXTURE.read_bytes())
    if edit:
        edit(document)
    return CandidateRequest.model_validate_json(json.dumps(document))


def change(*items: tuple[str, object]) -> CandidateRequest:
    def edit(document: Any) -> None:
        for path, value in items:
            keys = path.split(".")
            parent = document
            for key in keys[:-1]:
                parent = parent[int(key)] if isinstance(parent, list) else parent[key]
            if isinstance(parent, list):
                parent[int(keys[-1])] = value
            else:
                parent[keys[-1]] = value

    return tiny(edit)


def orders(sell: int = 2, buy: int = 1) -> Orders:
    return Orders(
        sales=(SaleOrder(lot_id="lot-a", shares=sell),) if sell else (),
        buys=(BuyOrder(security_id=B, shares=buy),) if buy else (),
    )


def test_hand_derived_nine_state_problem_and_fractional_remainder() -> None:
    request = tiny()
    raw = FIXTURE.with_name("tiny-holdings.csv").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == request.snapshot.source_sha256
    feasible = set()
    # Direct independent scalar equations for all nine states; no tested helpers.
    for sold in range(3):
        for bought in range(3):
            cash = 10 * (sold - bought)
            a = (25 - 10 * sold) / 25 - 0.5
            b = 10 * bought / 25 - 0.5
            variance = 0.04 * a * a + 0.09 * b * b
            expected = sold > 0 and cash >= 0 and variance < 0.01
            checked = validate(request, orders(sold, bought))
            assert checked.feasible == expected
            if expected:
                feasible.add((sold, bought))
    assert feasible == {(1, 1), (2, 1)}
    result = search(request)
    assert result.outcome == "optimal-in-domain" and result.stopping == "complete"
    assert result.evaluated_states == result.domain_states == 9
    assert result.feasible_harvests == 2
    assert not result.baseline.feasible
    assert result.baseline.blockers == ("tracking_error_exceeded",)
    assert result.best and result.best.orders == orders()
    m = result.best.metrics
    assert m and m.price_loss == m.long_term_loss == 4
    assert m.short_term_loss == m.unknown_term_loss == m.modeled_cost == 0
    assert m.final_cash == 10 and m.final_nav == 25
    assert m.final_quantities == (0.5, 1)
    assert m.final_weights == (0.2, 0.4)
    assert m.tracking_error == pytest.approx(math.sqrt(0.0045))
    assert m.turnover == 1.2 and m.order_count == 2
    assert not result.financial_use_authorized
    assert CandidateSearch.model_validate_json(result.model_dump_json()) == result


def test_costs_final_nav_cash_target_and_fee_funding() -> None:
    request = change(
        ("settings.sell_fee_per_isolated_order.value", "1"),
        ("buy_fee_per_security_order", "1"),
        ("settings.final_cash_target", dict(enabled=True, amount="8", investor_tolerance="0")),
    )
    checked = validate(request, orders())
    assert checked.feasible and checked.metrics
    m = checked.metrics
    assert m.price_loss == 4 and m.net_proceeds_tax_pnl == -5
    assert m.modeled_cost == 2 and m.final_cash == 8 and m.final_nav == 23
    assert m.final_weights == pytest.approx((5 / 23, 10 / 23))
    assert m.tracking_error == pytest.approx(
        math.sqrt(0.04 * (5 / 23 - 0.5) ** 2 + 0.09 * (10 / 23 - 0.5) ** 2)
    )
    # Sale 20 minus fees 1+1 cannot fund 20 of replacements, even with imported cash.
    denied = validate(request, orders(2, 2))
    assert "unfunded_final_cash" in denied.blockers
    assert "final_cash_target_unmet" in denied.blockers


def test_spread_cost_is_not_objective_reward_or_double_counted() -> None:
    request = change(("settings.sell_discount_bps.value", "100"), ("buy_premium_bps", "200"))
    checked = validate(request, orders())
    assert checked.feasible and checked.metrics
    assert checked.metrics.modeled_cost == pytest.approx(0.4)
    assert checked.metrics.final_cash == pytest.approx(9.6)
    assert checked.metrics.final_nav == pytest.approx(24.6)
    assert checked.metrics.net_proceeds_tax_pnl == pytest.approx(-4.2)
    assert checked.metrics.price_loss == 4


@pytest.mark.parametrize(
    "path,value,blocker",
    [
        ("settings.sell_fee_per_isolated_order.value", "10.0001", "unfunded_final_cash"),
        ("limits.max_cost", "0", "max_cost_exceeded"),
        ("limits.max_orders", 1, "max_orders_exceeded"),
        ("limits.max_turnover", "1.19999999999999999999", "max_turnover_exceeded"),
        ("limits.min_order_notional", "10.0000001", "order_below_min_notional"),
        (
            "limits.max_order_notional",
            dict(enabled=True, value="19.999999"),
            "order_above_max_notional",
        ),
        ("limits.max_position_weight", "0.39999999999999999999999", "position_weight_exceeded"),
        (
            "limits.min_price_loss",
            dict(enabled=True, value="4.000000001"),
            "minimum_price_loss_unmet",
        ),
        (
            "limits.max_cost_to_loss",
            dict(enabled=True, value="0.24999999"),
            "cost_to_loss_exceeded",
        ),
        (
            "settings.final_cash_target",
            dict(enabled=True, amount="8.9999999", investor_tolerance="0"),
            "final_cash_target_unmet",
        ),
    ],
)
def test_strict_economic_limits(path: str, value: object, blocker: str) -> None:
    extra = (("settings.sell_fee_per_isolated_order.value", "1"),)
    checked = validate(change(*extra, (path, value)), orders())
    assert not checked.feasible
    assert any(b.startswith(blocker) for b in checked.blockers)


def test_fees_do_not_hide_per_lot_positive_gain_or_negative_cash() -> None:
    request = change(
        ("snapshot.lots.0.total_basis.value", "24.999999999999999999999"),
        ("settings.sell_fee_per_isolated_order.value", "2"),
    )
    checked = validate(request, orders())
    assert "reference_positive_gain:lot-a" in checked.blockers
    assert checked.metrics and checked.metrics.net_proceeds_tax_pnl < 0
    request = change(("buy_fee_per_security_order", "0.0001"))
    assert "unfunded_final_cash" in validate(request, orders(2, 2)).blockers


def test_multiple_lots_one_security_order_fee_and_identifier_tie() -> None:
    def edit(d: Any) -> None:
        first = d["snapshot"]["lots"][0]
        first["quantity"]["value"], first["total_basis"]["value"] = "1.25", "15"
        second = copy.deepcopy(first)
        second["id"], second["source_ref"] = "lot-z", "tiny-holdings.csv:3"
        d["snapshot"]["lots"].append(second)
        d["sale_bounds"] = {"lot-z": 1, "lot-a": 1}
        d["settings"]["sell_fee_per_isolated_order"]["value"] = "1"
        d["limits"]["tracking_error"] = "1"

    request = tiny(edit)
    combined = Orders(
        sales=(SaleOrder(lot_id="lot-a", shares=1), SaleOrder(lot_id="lot-z", shares=1)), buys=()
    )
    checked = validate(request, combined)
    assert checked.feasible and checked.metrics
    assert checked.metrics.order_count == 1 and checked.metrics.modeled_cost == 1
    assert checked.metrics.price_loss == 4 and checked.metrics.final_cash == 19
    document = json.loads(request.model_dump_json())
    document["limits"]["max_turnover"] = "0.4"
    document["limits"]["max_orders"] = 1
    tied = search(CandidateRequest.model_validate_json(json.dumps(document)))
    assert tied.best and tied.best.orders == orders(1, 0)


def test_no_trade_fewer_order_tie_and_no_feasible_harvest_are_distinct() -> None:
    result = search(change(("limits.tracking_error", "1")))
    assert result.baseline.feasible
    assert result.best and result.best.orders == orders(2, 0)
    result = search(
        change(("snapshot.lots.0.total_basis.value", "20"), ("limits.tracking_error", "1"))
    )
    assert result.outcome == "no-feasible-harvest-in-domain" and result.baseline.feasible
    assert result.best is None


@pytest.mark.parametrize(
    "proposal,blocker",
    [
        (orders(3, 1), "sale_exceeds_supplied_quantity"),
        (
            Orders(sales=(SaleOrder(lot_id="missing", shares=1),), buys=()),
            "unknown_or_excluded_sale_lot",
        ),
        (
            Orders(sales=(), buys=(BuyOrder(security_id="missing", shares=1),)),
            "unknown_or_ineligible_buy",
        ),
        (Orders(sales=orders().sales * 2, buys=()), "duplicate_order_identity"),
        (Orders(sales=orders().sales, buys=orders().buys * 2), "duplicate_order_identity"),
        (orders(2, 3), "buy_outside_declared_domain"),
        (orders(0, 1), "positive_eligible_price_loss_required"),
    ],
)
def test_arbitrary_changed_orders_are_checked(proposal: Orders, blocker: str) -> None:
    checked = validate(tiny(), proposal)
    assert not checked.feasible and any(b.startswith(blocker) for b in checked.blockers)


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "1"])
def test_order_quantities_are_strict_positive_whole_shares(value: object) -> None:
    with pytest.raises(ValidationError):
        SaleOrder.model_validate(dict(lot_id="lot-a", shares=value))


@pytest.mark.parametrize(
    "path,value,blocker",
    [
        ("risk.security_ids", [B, A], "asset_covariance_order_or_duplicate"),
        ("risk.annual_covariance", [[0.04, 0.0], [0.0, -0.09]], "covariance_not_psd"),
        ("risk.annual_covariance", [[0.04, 0.01], [0.0, 0.09]], "covariance_not_finite_symmetric"),
        ("risk.annual_covariance", [[0.04]], "covariance_dimensions"),
        ("risk.benchmark_weights", [0.5], "benchmark_weights_incomplete_or_invalid"),
        ("risk.benchmark_weights", [0.5, 0.4], "benchmark_weights_incomplete_or_invalid"),
        ("risk.benchmark_ids", [A], "benchmark_membership_invalid"),
        ("risk.as_of", "2026-10-22", "risk_date"),
        ("settings.marks.0.day.value", "2026-10-22", "mark_stale_future"),
        ("settings.marks.0.identity", "other", "mark_unknown_or_identity"),
        ("snapshot.lots.0.quantity", dict(value=None, reason="missing"), "held_quantity_unknown"),
        ("snapshot.account_scope", "ira-roth", "supported_taxable_account"),
        ("snapshot.observations.selection_blockers", ["contradiction"], "source_reconciliation"),
        ("settings.cash_budget_reviewed", False, "reviewed_cash_and_funding"),
        (
            "settings.sell_discount_bps",
            dict(value=None, reason="missing"),
            "selling_cost_assumptions_unknown",
        ),
        ("sale_bounds", {}, "sale_domain_must_account"),
        (
            "assets.1.security.identity",
            dict(value=None, reason="missing"),
            "identity_unknown_or_aliased",
        ),
    ],
)
def test_input_refusals_do_not_become_zero_or_feasibility(
    path: str, value: object, blocker: str
) -> None:
    result = search(change((path, value)))
    assert result.outcome == "invalid-input" and result.evaluated_states == 0
    assert not result.baseline.feasible and result.baseline.metrics is None
    assert any(b.startswith(blocker) for b in result.baseline.blockers)


def test_unknown_basis_is_scoped_and_unknown_term_never_becomes_st_or_lt() -> None:
    request = change(
        ("snapshot.lots.0.total_basis", dict(value=None, reason="not supplied")),
        ("limits.tracking_error", "1"),
    )
    assert validate(request, orders(0, 0)).feasible
    assert "sale_basis_unknown:lot-a" in validate(request, orders()).blockers
    request = change(("snapshot.lots.0.term", dict(value=None, reason="unknown")))
    checked = validate(request, orders())
    assert checked.feasible and checked.metrics
    assert checked.metrics.unknown_term_loss == 4
    assert checked.metrics.short_term_loss == checked.metrics.long_term_loss == 0


def test_exposure_limits_unknown_taxonomy_and_strict_active_boundaries() -> None:
    checked = validate(
        change(
            (
                "limits.exposures",
                [
                    dict(
                        level="sector",
                        group="Sector-0",
                        kind="absolute",
                        maximum="0.19999999999999",
                    )
                ],
            ),
        ),
        orders(),
    )
    assert "exposure_limit_exceeded:sector/Sector-0" in checked.blockers
    request = change(("assets.0.sector", dict(value=None, reason="unmapped")))
    assert validate(request, orders()).feasible
    document = json.loads(request.model_dump_json())
    document["limits"]["exposures"] = [
        dict(level="sector", group="Sector-1", kind="absolute", maximum="1")
    ]
    assert (
        "unknown_constrained_taxonomy:sector"
        in validate(CandidateRequest.model_validate_json(json.dumps(document)), orders()).blockers
    )
    request = change(
        ("limits.exposures", [dict(level="security", group=A, kind="active", maximum="0.3")])
    )
    assert validate(request, orders()).feasible
    assert not validate(
        change(
            (
                "limits.exposures",
                [dict(level="security", group=A, kind="active", maximum="0.299999999999999999999")],
            ),
        ),
        orders(),
    ).feasible


def test_scenario_requires_explicit_assumptions_and_known_term() -> None:
    scenario = dict(
        usable_loss_fraction="1", offset_rate="0.3", reference="Fictional assumed offset"
    )
    request = change(
        ("limits.scenario", scenario),
        ("limits.min_scenario_net_value", dict(enabled=True, value="1.2")),
    )
    checked = validate(request, orders())
    assert checked.feasible and checked.metrics and checked.metrics.scenario_net_value == 1.2
    assert (
        "scenario_net_value_unmet"
        in validate(
            change(
                ("limits.scenario", scenario),
                ("limits.min_scenario_net_value", dict(enabled=True, value="1.20000001")),
            ),
            orders(),
        ).blockers
    )
    unknown = dict(value=None, reason="unknown")
    partial = validate(
        change(("snapshot.lots.0.term", unknown), ("limits.scenario", scenario)), orders()
    )
    assert partial.feasible and partial.metrics and partial.metrics.scenario_net_value is None
    assert (
        "unknown_term_cannot_support_tax_scenario"
        in validate(
            change(
                ("snapshot.lots.0.term", unknown),
                ("limits.scenario", scenario),
                ("limits.min_scenario_net_value", dict(enabled=True, value="0")),
            ),
            orders(),
        ).blockers
    )
    with pytest.raises(ValidationError):
        change(("limits.min_scenario_net_value", dict(enabled=True, value="1")))


def test_stopped_search_never_claims_optimum_or_infeasibility() -> None:
    early = search(change(("max_states", 1)))
    assert early.stopping == "state-limit" and early.outcome == "no-candidate"
    incumbent = search(change(("max_states", 5)))
    assert incumbent.stopping == "state-limit" and incumbent.outcome == "feasible-incumbent"
    assert incumbent.best and incumbent.best.orders == orders(1, 1)
    calls = 0

    def cancel() -> bool:
        nonlocal calls
        calls += 1
        return calls > 5

    cancelled = search(tiny(), cancel)
    assert cancelled.stopping == "cancelled" and cancelled.best == incumbent.best
    assert search(tiny(), lambda: True).evaluated_states == 0
    assert search(change(("max_states", 9))).stopping == "complete"


def test_low_caller_decimal_precision_and_traps_do_not_change_results() -> None:
    expected = search(tiny())
    with localcontext() as ctx:
        ctx.prec = 2
        ctx.traps[Inexact] = True
        actual = search(tiny())
    assert actual == expected


def test_search_freezes_inputs_against_callback_mutation() -> None:
    request = tiny()

    def cancel() -> bool:
        request.sale_bounds.clear()
        return False

    assert search(request, cancel) == search(tiny())


@pytest.mark.parametrize("side,security", [("sell", A), ("buy", B), ("both", B)])
def test_manual_restrictions_block_both_legs(side: str, security: str) -> None:
    request = change(
        (
            "settings.manual_restrictions",
            [
                dict(
                    name="Fictional restricted name",
                    identity=dict(
                        value="fictional-identity:" + ("FAAA" if security == A else "FBBB"),
                        reason=None,
                    ),
                    side=side,
                    source_ref="manual:1",
                )
            ],
        )
    )
    checked = validate(request, orders())
    assert not checked.feasible
    assert any("manual_restriction" in b for b in checked.blockers)


@pytest.mark.parametrize(
    "side,pnl,identity",
    [
        ("acquisition", None, "fictional-identity:FAAA"),
        ("sale", None, "fictional-identity:FBBB"),
        ("sale", "-1", "fictional-identity:FBBB"),
    ],
)
def test_retained_household_conflicts_cannot_be_omitted(
    side: str, pnl: str | None, identity: str
) -> None:
    def edit(d: Any) -> None:
        retained = copy.deepcopy(d["snapshot"])
        retained["source_sha256"] = "1" * 64
        retained["source_name"] = "fictional-retained-source.csv"
        context = retained["observations"]["lot_context"]
        context["source_sha256"] = retained["source_sha256"]
        event = dict(
            id="household-event",
            identity=dict(value=identity, reason=None),
            account_ref="fictional-other-account",
            account_scope="ira-roth",
            day=dict(value="2026-10-23", reason=None),
            side=side,
            quantity=dict(value="1", reason=None),
            pnl=dict(value=pnl, reason="Unknown P&L" if pnl is None else None),
            source_ref="fictional-retained-source.csv:2",
        )
        retained["observations"]["screening"]["activities"] = [event]
        context["screening"] = copy.deepcopy(retained["observations"]["screening"])
        d["retained_snapshots"] = [retained]

    checked = validate(tiny(edit), orders())
    assert not checked.feasible
    assert any("conflict:" in b for b in checked.blockers)


def test_embedded_source_screening_cannot_be_erased() -> None:
    def edit(d: Any) -> None:
        del d["snapshot"]["observations"]["screening"]

    assert any(
        "source_screening_omitted_or_changed" in b for b in search(tiny(edit)).baseline.blockers
    )


@pytest.mark.parametrize("status", ["conflict", "unknown"])
def test_same_batch_relationships_are_checked_without_same_id(status: str) -> None:
    relation = dict(
        left="fictional-identity:FAAA",
        right="fictional-identity:FBBB",
        status=status,
        valid_from="2026-01-01",
        valid_through="2026-12-31",
        evidence=dict(
            actor="Fictional reviewer",
            reference="Fictional relation",
            effective_at="2026-01-01",
            recorded_at="2026-01-01T00:00:00Z",
        ),
        rationale="Synthetic screen reference",
    )
    checked = validate(change(("settings.relationships", [relation])), orders())
    assert "same_batch_conflict_or_unresolved:" + A + "/" + B in checked.blockers


def test_same_security_sale_buy_is_never_permitted() -> None:
    request = change(("buy_bounds", {A: 1, B: 2}))
    proposal = Orders(sales=orders().sales, buys=(BuyOrder(security_id=A, shares=1),))
    assert (
        "same_batch_conflict_or_unresolved:" + A + "/" + A in validate(request, proposal).blockers
    )


def test_independent_positions_are_corroboration_not_extra_holdings() -> None:
    account = tiny().snapshot.account_id
    position = dict(
        id="position-a",
        account_id=account,
        security_id=A,
        source_ref="positions.csv:2",
        quantity=dict(value="2.5", reason=None),
    )
    request = change(("snapshot.positions", [position]))
    assert validate(request, orders()).metrics == validate(tiny(), orders()).metrics
    position["quantity"] = dict(value="2.5001", reason=None)
    assert (
        "position_lot_quantity_contradiction:" + A
        in validate(change(("snapshot.positions", [position])), orders()).blockers
    )


def test_known_exclusion_is_accounted_and_cannot_be_sold() -> None:
    def edit(d: Any) -> None:
        security = copy.deepcopy(d["snapshot"]["securities"][0])
        security["id"], security["ticker"] = "excluded", "EXCLUDED"
        security["classification"] = dict(value="unsupported-fund", reason=None)
        security["identity"] = dict(value="fictional-excluded", reason=None)
        d["snapshot"]["securities"].append(security)
        lot = copy.deepcopy(d["snapshot"]["lots"][0])
        lot["id"], lot["security_id"], lot["source_ref"] = (
            "excluded-lot",
            "excluded",
            "tiny-holdings.csv:3",
        )
        d["snapshot"]["lots"].append(lot)
        d["sale_bounds"]["excluded-lot"] = 0

    result = search(tiny(edit))
    assert result.best and result.best.orders == orders()
    assert len(result.exclusions) == 1 and "unsupported-fund" in result.exclusions[0]
    checked = validate(
        tiny(edit), Orders(sales=(SaleOrder(lot_id="excluded-lot", shares=1),), buys=())
    )
    assert "unknown_or_excluded_sale_lot:excluded-lot" in checked.blockers


def test_risk_boundary_and_zero_active_risk_are_distinct() -> None:
    te = validate(tiny(), orders()).metrics
    assert te
    cap = str(te.tracking_error + 1e-15)
    checked = validate(change(("limits.tracking_error", cap)), orders())
    assert "tracking_error_boundary_review_required" in checked.blockers
    request = change(
        ("snapshot.lots.0.quantity.value", "2"),
        ("snapshot.lots.0.total_basis.value", "24"),
        ("limits.tracking_error", "0"),
    )
    checked = validate(request, orders(1, 1))
    assert checked.feasible and checked.metrics
    assert checked.metrics.tracking_error == checked.metrics.risk_upper_bound == 0


def test_zero_psd_covariance_is_valid_and_numerical_failure_is_explicit() -> None:
    checked = validate(
        change(
            ("risk.annual_covariance", [[0.0, 0.0], [0.0, 0.0]]), ("limits.tracking_error", "0")
        ),
        orders(),
    )
    assert checked.feasible and checked.metrics and checked.metrics.tracking_error == 0
    # All input scalars finite; tiny covariance products underflow at the risk boundary.
    result = search(change(("risk.annual_covariance", [[5e-324, 0.0], [0.0, 5e-324]])))
    assert result.outcome == result.stopping == "numerical-failure"
    assert result.best is None


def test_optional_control_enable_states_and_missing_settings_are_not_defaults() -> None:
    with pytest.raises(ValidationError):
        change(("limits.max_cost_to_loss", dict(enabled=False, value="1")))
    with pytest.raises(ValidationError):
        tiny(lambda d: d["limits"].pop("max_orders"))
    with pytest.raises(ValidationError):
        change(("risk.units", "daily-covariance"))
    with pytest.raises(ValidationError):
        change(("limits.unknown_control", True))


def test_objective_rank_does_not_lose_source_differences_in_float64_display() -> None:
    def edit(d: Any) -> None:
        first = d["snapshot"]["lots"][0]
        first["quantity"]["value"] = "1.25"
        first["total_basis"]["value"] = "12500000000000000"
        second = copy.deepcopy(first)
        second["id"], second["source_ref"] = "lot-z", "tiny-holdings.csv:3"
        second["total_basis"]["value"] = "12500000000000000.125"
        d["snapshot"]["lots"].append(second)
        d["sale_bounds"] = {"lot-a": 1, "lot-z": 1}
        d["limits"]["tracking_error"] = "1"
        d["limits"]["max_turnover"] = "0.4"

    request = tiny(edit)
    a = validate(request, orders(1, 0))
    z_orders = Orders(sales=(SaleOrder(lot_id="lot-z", shares=1),), buys=())
    z = validate(request, z_orders)
    assert a.metrics and z.metrics and a.metrics.price_loss == z.metrics.price_loss
    result = search(request)
    assert result.best and result.best.orders == z_orders


def test_forged_solver_quantity_is_rechecked_beyond_schema() -> None:
    forged = SaleOrder.model_construct(lot_id="lot-a", shares=1.5)
    checked = validate(tiny(), Orders.model_construct(sales=(forged,), buys=()))
    assert checked.blockers == ("invalid_whole_share_order",) and not checked.feasible


def test_held_name_cannot_be_dropped_and_zero_benchmark_names_remain() -> None:
    request = change(("risk.benchmark_weights", [1.0, 0.0]))
    assert len(search(request).inputs.assets) == 2

    def edit(d: Any) -> None:
        d["assets"] = [d["assets"][1]]
        d["risk"]["security_ids"] = [B]
        d["risk"]["benchmark_ids"] = [B]
        d["risk"]["benchmark_weights"] = [1.0]
        d["risk"]["annual_covariance"] = [[0.09]]
        d["settings"]["marks"] = [d["settings"]["marks"][1]]

    result = search(tiny(edit))
    assert (
        result.outcome == "invalid-input" and "held_universe_incomplete" in result.baseline.blockers
    )


def test_selected_cash_changes_nav_and_source_cash_is_not_spent() -> None:
    def edit(d: Any) -> None:
        d["snapshot"]["cash"] = [
            dict(
                id="outside-cash",
                account_id=d["snapshot"]["account_id"],
                source_ref="cash.csv:1",
                amount=dict(value="10000", reason=None),
                kind="reported",
                currency="USD",
            )
        ]

    request = tiny(edit)
    assert "unfunded_final_cash" in validate(request, orders(1, 2)).blockers
    doc = json.loads(request.model_dump_json())
    doc["settings"]["cash_to_invest"] = "10"
    funded = validate(CandidateRequest.model_validate_json(json.dumps(doc)), orders(1, 2))
    assert funded.feasible and funded.metrics and funded.metrics.final_nav == 35
    assert funded.metrics.final_cash == 0


def test_unknown_special_event_and_source_locator_ambiguity_refuse_input() -> None:
    def edit(d: Any) -> None:
        unknown = dict(value=None, reason="Event effect unresolved")
        obs = d["snapshot"]["observations"]
        obs["screening"]["unbounded_event"] = unknown
        obs["lot_context"]["screening"]["unbounded_event"] = unknown

    assert "unbounded_or_unknown_event_impact" in search(tiny(edit)).baseline.blockers

    def duplicate(d: Any) -> None:
        lot = copy.deepcopy(d["snapshot"]["lots"][0])
        lot["id"] = "ambiguous"
        d["snapshot"]["lots"].append(lot)
        d["sale_bounds"]["ambiguous"] = 0

    assert "ambiguous_source_lot_locator" in search(tiny(duplicate)).baseline.blockers


def test_current_lot_acquisition_is_screened_even_when_supplied_list_omits_it() -> None:
    checked = validate(change(("snapshot.lots.0.acquired.value", "2026-10-23")), orders())
    assert any("known_acquisition_conflict" in b for b in checked.blockers)


def test_adapter_augmented_activity_superset_is_valid_source_input() -> None:
    def edit(d: Any) -> None:
        d["snapshot"]["observations"]["screening"]["activities"] = [
            dict(
                id="adapter-derived-acquisition",
                identity=dict(value="fictional-identity:FAAA", reason=None),
                account_ref=d["snapshot"]["account_id"],
                account_scope="us-taxable-individual",
                day=dict(value="2000-01-01", reason=None),
                side="acquisition",
                quantity=dict(value=None, reason="Original quantity not reconstructed"),
                pnl=dict(value=None, reason="Not a sale"),
                source_ref="tiny-holdings.csv:2",
            )
        ]

    result = search(tiny(edit))
    assert result.outcome == "optimal-in-domain" and result.best


def test_unavailable_states_prevent_optimum_or_infeasibility_claims() -> None:
    result = search(
        change(("snapshot.lots.0.total_basis", dict(value=None, reason="Missing basis")))
    )
    assert result.stopping == "complete" and result.outcome == "no-candidate"
    assert result.unresolved_states == 6 and result.best is None

    def edit(d: Any) -> None:
        lot = copy.deepcopy(d["snapshot"]["lots"][0])
        lot["id"], lot["source_ref"] = "unknown-basis-lot", "tiny-holdings.csv:3"
        lot["total_basis"] = dict(value=None, reason="Missing basis")
        d["snapshot"]["lots"].append(lot)
        d["sale_bounds"]["unknown-basis-lot"] = 1
        d["limits"]["tracking_error"] = "1"

    result = search(tiny(edit))
    assert result.stopping == "complete" and result.outcome == "feasible-incumbent"
    assert result.best and result.unresolved_states > 0


def test_correlated_covariance_and_cost_changed_exposure_use_final_state() -> None:
    checked = validate(change(("risk.annual_covariance", [[0.04, 0.01], [0.01, 0.09]])), orders())
    assert checked.feasible and checked.metrics
    assert checked.metrics.tracking_error == pytest.approx(math.sqrt(0.0051))
    original = change(("limits.max_position_weight", "0.42"))
    assert validate(original, orders()).feasible
    after_costs = change(
        ("limits.max_position_weight", "0.42"),
        ("settings.sell_fee_per_isolated_order.value", "1"),
        ("buy_fee_per_security_order", "1"),
    )
    assert "position_weight_exceeded:" + B in validate(after_costs, orders()).blockers


def test_tiny_nonzero_final_weight_cannot_underflow_to_zero() -> None:
    request = change(
        ("snapshot.lots.0.quantity.value", "1e-200"), ("settings.cash_to_invest", "1e200")
    )
    checked = validate(request, orders(0, 0))
    assert checked.unresolved and checked.metrics is None
    assert checked.blockers == ("unrepresentable_final_calculation",)


def test_fitted_covariance_one_ulp_symmetry_noise_is_preserved() -> None:
    matrix = [
        [0.014928703917785564, 0.009212907623707776],
        [0.009212907623707774, 0.01605012030066908],
    ]
    request = change(("risk.annual_covariance", matrix))
    checked = validate(request, orders())
    assert checked.feasible and checked.metrics
    assert request.risk.annual_covariance[0][1] != request.risk.annual_covariance[1][0]
    assert checked.metrics.tracking_error == pytest.approx(
        math.sqrt(0.09 * matrix[0][0] + 0.03 * (matrix[0][1] + matrix[1][0]) + 0.01 * matrix[1][1])
    )
