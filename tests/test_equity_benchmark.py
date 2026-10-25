"""D045 hand-derived value weights, full evidence, refusals and exact consumers."""

import json
import runpy
import subprocess
import sys
from collections.abc import Callable
from dataclasses import replace
from decimal import localcontext
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import TypeAdapter

from prosper import basket as b
from prosper import benchmark_reconciliation as r
from prosper import equity_benchmark as e
from prosper import industry as i
from prosper import vanguard as v

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/qualify_equity_benchmark.py"
RAW = (ROOT / "examples/synthetic/benchmark/equity-only.json").read_bytes()
DAY = "2000-01-03"
scenario = cast(
    Callable[..., tuple[v.Acquisition, r.Stipulation, e.Policy, r.PortfolioContext]],
    runpy.run_path(str(SCRIPT))["scenario"],
)


def raw_change(change: Callable[[dict[str, Any]], None]) -> bytes:
    data = json.loads(RAW)
    change(data[DAY])
    return json.dumps(data).encode()


def codes(result: e.Result) -> set[str]:
    return {issue.code for issue in result.issues}


def test_hand_derived_two_thirds_one_third_preserves_all_source_unknowns_and_exclusions() -> None:
    acq, stip, policy, portfolio = scenario()
    with localcontext() as context:
        context.prec = 3
        result = e.select(acq, stip, policy)
        bridge = e.bridge(result, portfolio)
    assert result.status == "qualified-synthetic-equity-benchmark" and not result.issues
    assert result.equity_value_total == result.retained_known_value == "90"
    assert result.excluded_known_usd_value == "10"
    assert result.excluded_unknown_usd_values == (r.Locator("shortTermReserves", 1),)
    assert result.retained_unknown_values == ()
    assert len(result.ledger) == 8
    assert sum(row.disposition == "excluded" for row in result.ledger) == 6
    assert [row.derived_weight for row in result.ledger][:2] == ["2/3", "1/3"]
    assert all(row.reason for row in result.ledger)
    assert result.ledger[0].raw_value == "60.00"
    assert result.ledger[0].raw_percentage == "60.0000"
    assert result.ledger[0].percentage_token_kind == "number"
    assert result.ledger[1].raw_percentage == "" and result.ledger[1].published_weight is None
    assert acq.response is not None and acq.response.body == RAW
    assert bridge.basket.weights is not None and bridge.basket.portfolio_nav_usd == "2"
    assert bridge.basket.weights.benchmark == (i.ExactWeight("2", "3"), i.ExactWeight("1", "3"))
    assert bridge.basket.weights.benchmark_cash == i.ExactWeight("0", "1")
    assert bridge.basket.data.benchmark[0].weight.raw == "2/3"
    assert bridge.basket.data.benchmark[0].unit == "exact-ratio"
    assert not result.benchmark_ready and not bridge.benchmark_ready
    # The existing frozen dataclass transport also round-trips exact ratio facts.
    adapter = TypeAdapter(b.BasketInput)
    assert adapter.validate_json(adapter.dump_json(bridge.basket.data)) == bridge.basket.data
    assert b.qualify(bridge.basket.data) == bridge.basket
    assert b.to_industry(bridge.basket) == bridge.basket.weights


def alternate_case() -> tuple[v.Acquisition, r.Stipulation, e.Policy, r.PortfolioContext]:
    data = json.loads(RAW)
    primary = [
        (name, index, row) for name, rows in data[DAY].items() for index, row in enumerate(rows)
    ]
    data[DAY]["shortTermReservesMoneyMarket"] = [
        {"amortizedCost": row["marketValue"], "sourceIndex": index} for _, index, row in primary
    ]
    acq, stip, policy, portfolio = scenario(json.dumps(data).encode())
    stip = replace(
        stip,
        sections=tuple(
            replace(sec, role="alternate") if sec.section == "shortTermReservesMoneyMarket" else sec
            for sec in stip.sections
        ),
        rows=tuple(
            replace(
                row, target=r.Locator(primary[row.locator.index][0], primary[row.locator.index][1])
            )
            if row.locator.section == "shortTermReservesMoneyMarket"
            else row
            for row in stip.rows
        ),
    )
    policy = replace(
        policy,
        values=tuple(
            replace(f, field="amortizedCost") if f.section == "shortTermReservesMoneyMarket" else f
            for f in policy.values
        ),
        decisions=tuple(
            d for d in policy.decisions if d.locator.section != "shortTermReservesMoneyMarket"
        ),
    )
    return acq, stip, policy, portfolio


def test_complete_alternate_links_cover_included_and_excluded_rows_without_double_count() -> None:
    acq, stip, policy, portfolio = alternate_case()
    result = e.select(acq, stip, policy)
    assert result.equity_value_total == "90" and len(result.ledger) == 16
    assert sum(row.disposition == "linked-alternate" for row in result.ledger) == 8
    assert result.excluded_known_usd_value == "10" and len(result.excluded_unknown_usd_values) == 1
    assert e.bridge(result, portfolio).basket.weights is not None


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("missing-value", "included_value_unknown_or_invalid"),
        ("nan", "included_value_unknown_or_invalid"),
        ("infinity", "included_value_unknown_or_invalid"),
        ("negative-value", "negative_included_value"),
        ("negative-percent", "negative_included_published_weight"),
        ("currency", "source_currency_contradiction"),
        ("zero-total", "positive_retained_equity_total_required"),
        ("ratio-bound", "exact_ratio_representation_limit"),
    ],
)
def test_included_source_failures_never_yield_weights(mutation: str, expected: str) -> None:
    def change(data: dict[str, Any]) -> None:
        if mutation == "missing-value":
            data["equity"][0].pop("marketValue")
        elif mutation in ("nan", "infinity"):
            data["equity"][0]["marketValue"] = "NaN" if mutation == "nan" else "Infinity"
        elif mutation == "negative-value":
            data["equity"][0]["marketValue"] = "-1.00"
        elif mutation == "negative-percent":
            data["equity"][0]["percentOfFunds"] = "-1"
        elif mutation == "currency":
            data["equity"][0]["currency"] = "EUR"
        elif mutation == "zero-total":
            data["equity"][0]["marketValue"] = data["equity"][1]["marketValue"] = "0.00"
        else:
            data["equity"][0]["marketValue"] = "9" * 128
            data["equity"][1]["marketValue"] = "1e-40"

    acq, stip, policy, portfolio = scenario(raw_change(change))
    result = e.select(acq, stip, policy)
    assert expected in codes(result)
    assert result.equity_value_total is None and result.benchmark_rows is None
    assert all(row.derived_weight is None for row in result.ledger)
    with pytest.raises(r.ReconciliationUnavailable):
        e.bridge(result, portfolio)


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ("no-decision", "explicit_equity_decision_required"),
        ("extra-decision", "decision_requires_primary_row"),
        ("missing-row", "row_disposition_missing"),
        ("stale-row", "row_link_or_evidence_stale"),
        ("wrong-context", "source_context_mismatch"),
        ("fund-proof", "independent_stipulated_fund_assertion_required"),
        ("stale-section", "section_evidence_stale_or_unknown"),
        ("missing-section", "section_relationship_unresolved"),
        ("unresolved-section", "section_relationship_unresolved"),
        ("missing-field", "explicit_value_field_required"),
        ("wrong-value-field", "primary_market_value_field_required"),
        ("extra-field", "value_field_not_in_source"),
        ("duplicate-id", "duplicate_included_security"),
        ("unknown-identity", "included_equity_identity_required"),
        ("stale-identity", "included_equity_identity_unresolved"),
        ("etf-included", "unsupported_included_equity"),
        ("bond-section-included", "included_non_equity_section"),
        ("empty-retained", "positive_retained_equity_total_required"),
        ("primary-link", "primary_cannot_link_another_exposure"),
        ("cash", "explicit_zero_benchmark_cash_required"),
    ],
)
def test_explicit_source_and_selection_contract_failures(mutation: str, expected: str) -> None:
    acq, stip, policy, _ = scenario()
    first = stip.rows[0]
    if mutation == "no-decision":
        policy = replace(policy, decisions=policy.decisions[1:])
    elif mutation == "extra-decision":
        policy = replace(
            policy,
            decisions=(*policy.decisions, e.Decision(r.Locator("ghost", 0), "exclude", "unmapped")),
        )
    elif mutation == "missing-row":
        stip = replace(stip, rows=stip.rows[1:])
    elif mutation == "stale-row":
        stip = replace(stip, rows=(replace(first, row_sha256="0" * 64), *stip.rows[1:]))
    elif mutation == "wrong-context":
        stip = replace(stip, effective_date="2000-01-02")
    elif mutation == "fund-proof":
        stip = replace(
            stip, fund_assertion=replace(stip.fund_assertion, source_sha256=stip.raw_sha256)
        )
    elif mutation == "stale-section":
        stip = replace(
            stip,
            sections=(
                replace(
                    stip.sections[0],
                    evidence=replace(stip.sections[0].evidence, valid_through="2000-01-02"),
                ),
                *stip.sections[1:],
            ),
        )
    elif mutation == "missing-section":
        stip = replace(stip, sections=stip.sections[1:])
    elif mutation == "unresolved-section":
        stip = replace(
            stip, sections=(replace(stip.sections[0], role="unresolved"), *stip.sections[1:])
        )
    elif mutation == "missing-field":
        policy = replace(policy, values=policy.values[1:])
    elif mutation == "wrong-value-field":
        policy = replace(
            policy, values=(replace(policy.values[0], field="percentOfFunds"), *policy.values[1:])
        )
    elif mutation == "extra-field":
        policy = replace(policy, values=(*policy.values, e.ValueField("ghost", "value", "USD")))
    elif mutation in ("duplicate-id", "unknown-identity", "stale-identity", "etf-included"):
        assert first.security is not None
        security = (
            None
            if mutation == "unknown-identity"
            else stip.rows[1].security
            if mutation == "duplicate-id"
            else replace(first.security, asset_type="etf")
            if mutation == "etf-included"
            else replace(first.security, evidence=replace(first.evidence, recorded="2000-01-05"))
        )
        stip = replace(stip, rows=(replace(first, security=security), *stip.rows[1:]))
    elif mutation == "bond-section-included":
        target = r.Locator("fixedIncome", 0)
        stip = replace(
            stip,
            rows=tuple(
                replace(row, security=first.security) if row.locator == target else row
                for row in stip.rows
            ),
        )
        policy = replace(
            policy,
            decisions=tuple(
                replace(d, action="include") if d.locator == target else d for d in policy.decisions
            ),
        )
    elif mutation == "empty-retained":
        policy = replace(
            policy,
            decisions=tuple(
                replace(d, action="exclude", reason="explicit exclusion") for d in policy.decisions
            ),
        )
    elif mutation == "primary-link":
        stip = replace(stip, rows=(replace(first, target=r.Locator("equity", 1)), *stip.rows[1:]))
    else:
        stip = replace(stip, benchmark_cash=replace(stip.benchmark_cash, raw="0.1"))
    result = e.select(acq, stip, policy)
    assert expected in codes(result) and result.benchmark_rows is None


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "value", "security", "currency"])
def test_alternate_conflicts_cannot_hide_exclusions_or_bad_relationships(mutation: str) -> None:
    acq, stip, policy, _ = alternate_case()
    alternatives = [
        row for row in stip.rows if row.locator.section == "shortTermReservesMoneyMarket"
    ]
    target = alternatives[1]
    if mutation == "duplicate":
        target = replace(target, target=alternatives[0].target)
    elif mutation == "missing":
        target = replace(target, target=None)
    elif mutation == "security":
        target = replace(target, security=stip.rows[0].security)
    else:
        assert acq.response is not None
        data = json.loads(acq.response.body)
        data[DAY]["shortTermReservesMoneyMarket"][1][
            "amortizedCost" if mutation == "value" else "currency"
        ] = "999" if mutation == "value" else "EUR"
        newer, _, _, _ = scenario(json.dumps(data).encode())
        assert newer.snapshot is not None
        updated = newer.snapshot.document.get(DAY)
        assert isinstance(updated, v.JsonObject)
        raw_rows = updated.get("shortTermReservesMoneyMarket")
        assert isinstance(raw_rows, tuple)
        target = replace(target, row_sha256=r.row_identity(raw_rows[1]))
        acq = newer
        stip = replace(stip, raw_sha256=newer.snapshot.raw_sha256)
    stip = replace(
        stip, rows=tuple(target if row.locator == target.locator else row for row in stip.rows)
    )
    result = e.select(acq, stip, policy)
    assert result.issues and result.benchmark_rows is None


def test_zero_included_value_and_explicit_foreign_exclusion_remain_distinct() -> None:
    def change(data: dict[str, Any]) -> None:
        data["equity"][0]["marketValue"] = "0.00"
        data["equity"][2]["currency"] = "EUR"

    acq, stip, policy, portfolio = scenario(raw_change(change))
    result = e.select(acq, stip, policy)
    assert result.equity_value_total == "30"
    assert result.ledger[0].derived_weight == "0"
    assert result.ledger[2].value == "3" and result.ledger[2].value_currency == "EUR"
    assert r.Locator("equity", 2) in result.excluded_unknown_usd_values
    assert result.excluded_known_usd_value == "7"  # USD aggregate never adds EUR 3.
    assert e.bridge(result, portfolio).basket.weights is not None


def test_selected_portfolio_cash_does_not_rescale_the_benchmark() -> None:
    acq, stip, policy, portfolio = scenario()
    result = e.select(acq, stip, policy)
    bridge = e.bridge(
        result, replace(portfolio, portfolio_cash=replace(portfolio.portfolio_cash, raw="2.00"))
    )
    weights = b.to_industry(bridge.basket)
    assert bridge.basket.portfolio_nav_usd == "4"
    assert weights.portfolio_cash == i.ExactWeight("1", "2")
    assert weights.benchmark_cash == i.ExactWeight("0", "1")
    assert weights.benchmark == (i.ExactWeight("2", "3"), i.ExactWeight("1", "3"))


@pytest.mark.parametrize("role", ["subset", "alternate"])
def test_partial_explicit_subset_is_not_added_or_mistaken_for_complete_alternate(
    role: r.Role,
) -> None:
    raw = raw_change(
        lambda data: data.update(
            allocationToUnderlyingFunds=[{"marketValue": "10.00", "percentOfFunds": "10"}]
        )
    )
    acq, stip, policy, _ = scenario(raw)
    section = "allocationToUnderlyingFunds"
    stip = replace(
        stip,
        sections=tuple(replace(s, role=role) if s.section == section else s for s in stip.sections),
        rows=tuple(
            replace(row, target=r.Locator("equity", 0)) if row.locator.section == section else row
            for row in stip.rows
        ),
    )
    policy = replace(
        policy, decisions=tuple(d for d in policy.decisions if d.locator.section != section)
    )
    result = e.select(acq, stip, policy)
    if role == "subset":
        assert result.equity_value_total == "90" and not result.issues
        assert sum(row.disposition == "linked-subset" for row in result.ledger) == 1
    else:
        assert "alternate_does_not_cover_primary_rows" in codes(result)
        assert result.equity_value_total is None


def test_exclusion_does_not_hide_damaged_source_binding_or_incomplete_universe() -> None:
    acq, stip, policy, portfolio = scenario()
    excluded = stip.rows[2]
    changed = replace(
        stip,
        rows=tuple(
            replace(row, row_sha256="0" * 64) if row.locator == excluded.locator else row
            for row in stip.rows
        ),
    )
    blocked = e.select(acq, changed, policy)
    assert "row_link_or_evidence_stale" in codes(blocked) and blocked.benchmark_rows is None
    result = e.select(acq, stip, policy)
    missing = e.bridge(result, replace(portfolio, universe=portfolio.universe[:1]))
    assert missing.basket.weights is None
    assert "required_security_missing_from_order" in {issue.code for issue in missing.basket.issues}


def test_replay_rejects_forgery_wrong_context_failed_acquisition_and_preserves_old_result() -> None:
    acq, stip, policy, portfolio = scenario()
    old = e.select(acq, stip, policy)
    for forged in (replace(old, equity_value_total="91"), replace(old, ledger=old.ledger[:-1])):
        with pytest.raises(r.ReconciliationUnavailable):
            e.bridge(forged, portfolio)
    for context in (
        replace(portfolio, as_of="2000-01-02"),
        replace(portfolio, known_at="2000-01-03"),
    ):
        with pytest.raises(r.ReconciliationUnavailable):
            e.bridge(old, context)
    damaged = replace(acq, snapshot=replace(acq.snapshot, raw_sha256="0" * 64))  # type: ignore[type-var]
    assert "snapshot_replay_mismatch" in codes(e.select(damaged, stip, policy))
    failed = v.acquire(
        acq.selection,
        collected_at=acq.collected_at,
        transport=lambda s: v.Response(404, s.url, "application/json", b"not found"),
    )
    assert e.select(failed, stip, policy).status == "unavailable"
    changed = replace(
        policy,
        decisions=tuple(
            replace(d, reason="new attributable explanation") for d in policy.decisions
        ),
    )
    newer = e.select(acq, stip, changed)
    assert newer.identity_sha256 != old.identity_sha256
    assert (
        e.select(acq, stip, policy) == old and e.bridge(old, portfolio).basket.weights is not None
    )


@pytest.mark.parametrize(
    "mutation", ["version", "duplicate-decision", "duplicate-field", "empty-reason", "currency"]
)
def test_policy_is_bounded_unique_versioned_and_explicit(mutation: str) -> None:
    acq, stip, policy, _ = scenario()
    if mutation == "version":
        policy = replace(policy, version="real-ready")
    elif mutation == "duplicate-decision":
        policy = replace(policy, decisions=(*policy.decisions, policy.decisions[0]))
    elif mutation == "duplicate-field":
        policy = replace(policy, values=(*policy.values, policy.values[0]))
    elif mutation == "empty-reason":
        policy = replace(
            policy, decisions=(replace(policy.decisions[0], reason=""), *policy.decisions[1:])
        )
    else:
        policy = replace(
            policy, values=(replace(policy.values[0], currency="EUR"), *policy.values[1:])
        )
    with pytest.raises(r.ReconciliationUnavailable):
        e.select(acq, stip, policy)


@pytest.mark.parametrize(
    "raw,code",
    [
        ("2/6", "noncanonical_exact_ratio"),
        ("1/0", "invalid_exact_ratio"),
        ("-1/3", "invalid_exact_ratio"),
        ("NaN", "invalid_exact_ratio"),
        (None, "unknown_or_contradictory_ratio"),
    ],
)
def test_exact_ratio_consumer_never_rounds_repairs_or_zero_fills(
    raw: str | None, code: str
) -> None:
    acq, stip, policy, portfolio = scenario()
    data = e.bridge(e.select(acq, stip, policy), portfolio).basket.data
    row = data.benchmark[0]
    changed = replace(
        data, benchmark=(replace(row, weight=replace(row.weight, raw=raw)), *data.benchmark[1:])
    )
    result = b.qualify(changed)
    assert code in {issue.code for issue in result.issues} and result.weights is None


def test_offline_replay_is_byte_identical_across_processes() -> None:
    first = subprocess.check_output([sys.executable, "-I", str(SCRIPT)], cwd=ROOT)
    second = subprocess.check_output([sys.executable, "-I", str(SCRIPT)], cwd=ROOT)
    assert first == second and json.loads(first)["benchmark_ready"] is False
