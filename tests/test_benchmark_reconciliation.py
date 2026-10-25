"""Independent full/partial source sums and explicitly stipulated row relationships."""

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, date, datetime
from fractions import Fraction
from pathlib import Path

import pytest

from prosper import basket as b
from prosper import benchmark_reconciliation as r
from prosper import vanguard as v

ROOT = Path(__file__).resolve().parents[1]
RAW = (ROOT / "examples/synthetic/benchmark/full-response.json").read_bytes()
DAY = "2000-01-03"
NOW = datetime(2000, 1, 4, 12, tzinfo=UTC)
SELECTION = v.select_fund("VTI", date.fromisoformat(DAY))


def scenario(raw: bytes = RAW) -> tuple[v.Acquisition, r.Stipulation, r.PortfolioContext]:
    acquisition = v.acquire(
        SELECTION,
        collected_at=NOW,
        transport=lambda s: v.Response(200, s.url, "application/json", raw),
    )
    snapshot = acquisition.snapshot
    assert snapshot is not None
    e = b.Evidence(
        hashlib.sha256(b"independent fictional identity and relationship assertions").hexdigest(),
        "stipulated fixture assertion",
        DAY,
        "2000-01-04",
        DAY,
    )
    sections = tuple(
        r.SectionRule(
            s.name, "primary" if s.name == "equity" else "empty", "percentOfFunds", "percent", e
        )
        for s in snapshot.sections
    )
    rules = tuple(
        r.RowRule(
            r.Locator(s.name, index),
            r.row_identity(row),
            b.Security(f"FICTIONAL-{index}", "USD", "stock", e) if s.name == "equity" else None,
            None,
            e,
        )
        for s in snapshot.sections
        for index, row in enumerate(s.rows)
    )
    stipulation = r.Stipulation(
        snapshot.raw_sha256,
        SELECTION.fund,
        DAY,
        DAY,
        NOW.isoformat(),
        e,
        sections,
        rules,
        b.Fact("0.00", e),
        "percent",
    )
    securities = tuple(b.Security(f"FICTIONAL-{index}", "USD", "stock", e) for index in range(2))
    context = r.PortfolioContext(
        DAY,
        "2000-01-04",
        ("FICTIONAL-0", "FICTIONAL-1"),
        tuple(
            b.Position(f"P{j}", s, b.Fact("1.00", e), b.Fact("1.00", e))
            for j, s in enumerate(securities)
        ),
        (),
        b.Fact("0.00", e),
    )
    return acquisition, stipulation, context


def altered_section(name: str, rows: object) -> bytes:
    data = json.loads(RAW)
    data[DAY][name] = rows
    return json.dumps(data).encode()


def relationships(
    s: r.Stipulation, section: str, role: r.Role, targets: tuple[int, ...]
) -> r.Stipulation:
    return replace(
        s,
        sections=tuple(
            replace(rule, role=role) if rule.section == section else rule for rule in s.sections
        ),
        rows=tuple(
            replace(row, target=r.Locator("equity", targets[row.locator.index]))
            if row.locator.section == section
            else row
            for row in s.rows
        ),
    )


def codes(result: r.Reconciliation) -> set[str]:
    return {issue.code for issue in result.issues}


def test_original_rows_raw_tokens_typed_snapshot_and_exact_basket_bridge() -> None:
    acq, stip, context = scenario()
    result = r.reconcile(acq, stip)
    assert result.status == "qualified-synthetic-reconciliation"
    assert result.economic_total == "1" and result.residual == "0"
    assert result.primary_known_weight_sum == "1" and result.primary_unknown_rows == ()
    assert len(result.ledger) == 2 and len(result.sections) == 7
    assert result.ledger[0].raw_weight == "60.0000"
    assert result.ledger[0].token_kind == "number"
    assert all(row.disposition == "included-primary" for row in result.ledger)
    assert result.acquisition.response is not None and result.acquisition.response.body == RAW
    assert result.upstream_issues == acq.issues
    bridged = r.bridge(result, context)
    assert bridged.reconciliation is result and bridged.portfolio is context
    assert bridged.basket.weights is not None
    assert bridged.basket.weights.benchmark[0].numerator == "3"  # type: ignore[union-attr]
    assert bridged.basket.weights.benchmark[0].denominator == "5"  # type: ignore[union-attr]
    assert bridged.basket.portfolio_nav_usd == "2"
    assert bridged.basket.data.benchmark[0].weight.raw == "60.0000"
    assert not result.benchmark_ready and not bridged.benchmark_ready


def test_explicit_alternate_is_not_another_hundred_percent() -> None:
    rows = json.loads(RAW)[DAY]["equity"]
    acq, stip, context = scenario(altered_section("allocationToUnderlyingFunds", rows))
    stip = relationships(stip, "allocationToUnderlyingFunds", "alternate", (0, 1))
    result = r.reconcile(acq, stip)
    assert result.status == "qualified-synthetic-reconciliation"
    assert result.economic_total == result.primary_known_weight_sum == "1"
    assert len(result.ledger) == 4
    assert (
        sum(
            Fraction(section.known_weight_sum)
            for section in result.sections
            if section.known_weight_sum is not None
        )
        == 2
    )
    assert [row.disposition for row in result.ledger][-2:] == ["linked-alternate"] * 2
    assert r.bridge(result, context).basket.weights is not None
    unresolved = r.reconcile(
        acq,
        replace(
            stip,
            sections=tuple(
                replace(s, role="unresolved") if s.section == "allocationToUnderlyingFunds" else s
                for s in stip.sections
            ),
        ),
    )
    assert unresolved.economic_total is None and unresolved.benchmark_rows is None
    assert "section_relationship_unresolved" in codes(unresolved)


def test_explicit_ten_percent_subset_is_not_added_to_primary() -> None:
    acq, stip, _ = scenario(
        altered_section("formattedFundOfFundsHoldings", [{"percentOfFunds": 10}])
    )
    stip = relationships(stip, "formattedFundOfFundsHoldings", "subset", (0,))
    result = r.reconcile(acq, stip)
    assert result.economic_total == "1" and len(result.ledger) == 3
    assert result.ledger[-1].disposition == "linked-subset"
    assert result.ledger[-1].weight == "1/10"


@pytest.mark.parametrize(
    "raw,known,total,residual",
    [
        (RAW.replace(b'"percentOfFunds":40', b'"percentOfFunds":null'), "3/5", None, None),
        (
            RAW.replace(b'"percentOfFunds":40', b'"percentOfFunds":39.854'),
            "49927/50000",
            "49927/50000",
            "73/50000",
        ),
        (
            RAW.replace(b'"percentOfFunds":40', b'"percentOfFunds":41'),
            "101/100",
            "101/100",
            "-1/100",
        ),
    ],
)
def test_unknown_and_nonunit_primary_totals_never_normalize(
    raw: bytes, known: str, total: str | None, residual: str | None
) -> None:
    acq, stip, context = scenario(raw)
    result = r.reconcile(acq, stip)
    assert result.primary_known_weight_sum == known
    assert result.economic_total == total and result.residual == residual
    assert result.benchmark_rows is None and result.status == "incomplete"
    assert result.acquisition.response is not None and result.acquisition.response.body == raw
    if total is None:
        assert result.primary_unknown_rows == (r.Locator("equity", 1),)
    with pytest.raises(r.ReconciliationUnavailable):
        r.bridge(result, context)


@pytest.mark.parametrize("section", ["shortTermReserves", "derivatives", "fixedIncome"])
def test_nonstock_rows_cannot_be_excluded_even_if_equities_total_one(section: str) -> None:
    acq, stip, _ = scenario(
        altered_section(section, [{"percentOfFunds": -0.125, "sourceDetail": "preserve"}])
    )
    stip = relationships(stip, section, "subset", (0,))
    result = r.reconcile(acq, stip)
    assert "unsupported_nonstock_section" in codes(result)
    assert result.primary_known_weight_sum == "1" and result.economic_total is None
    assert len(result.ledger) == 3 and result.ledger[-1].weight == "-1/800"
    assert result.benchmark_rows is None


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("missing-link", "explicit_primary_row_link_required"),
        ("wrong-target", "missing_invalid_or_duplicate_primary_target"),
        ("duplicate-target", "missing_invalid_or_duplicate_primary_target"),
        ("weight-mismatch", "linked_weight_mismatch"),
        ("subset-too-large", "linked_weight_mismatch"),
        ("partial-alternate", "alternate_does_not_cover_primary_rows"),
        ("security-mismatch", "linked_security_mismatch"),
    ],
)
def test_relationship_evidence_does_not_override_numeric_or_identity_contradictions(
    mutation: str, code: str
) -> None:
    rows = json.loads(RAW)[DAY]["equity"]
    if mutation == "weight-mismatch":
        rows[1]["percentOfFunds"] = 39
    if mutation == "subset-too-large":
        rows[0]["percentOfFunds"] = 61
    if mutation == "partial-alternate":
        rows = rows[:1]
    acq, stip, _ = scenario(altered_section("allocationToUnderlyingFunds", rows))
    stip = relationships(
        stip,
        "allocationToUnderlyingFunds",
        "subset" if mutation == "subset-too-large" else "alternate",
        tuple(range(len(rows))),
    )
    altered = list(stip.rows)
    index = next(
        j for j, row in enumerate(altered) if row.locator.section == "allocationToUnderlyingFunds"
    )
    if mutation == "missing-link":
        altered[index] = replace(altered[index], target=None)
    if mutation == "wrong-target":
        altered[index] = replace(altered[index], target=r.Locator("equity", 99))
    if mutation == "duplicate-target":
        altered[index + 1] = replace(altered[index + 1], target=r.Locator("equity", 0))
    if mutation == "security-mismatch":
        security = stip.rows[0].security
        assert security is not None
        altered[index] = replace(
            altered[index], security=replace(security, security_id="FICTIONAL-WRONG")
        )
    result = r.reconcile(acq, replace(stip, rows=tuple(altered)))
    assert code in codes(result) and result.economic_total is None


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("fund", "source_context_mismatch"),
        ("date", "source_context_mismatch"),
        ("collection", "source_context_mismatch"),
        ("source", "source_context_mismatch"),
        ("stale-row", "row_link_or_evidence_stale"),
        ("missing-row", "row_disposition_missing"),
        ("stale-evidence", "row_link_or_evidence_stale"),
        ("fund-no-independent", "independent_stipulated_fund_assertion_required"),
        ("duplicate-security", "duplicate_primary_security"),
        ("currency", "unsupported_security"),
    ],
)
def test_stale_context_or_row_assertions_retain_failures(mutation: str, code: str) -> None:
    acq, stip, _ = scenario()
    if mutation == "fund":
        stip = replace(stip, fund=v.Fund("VOO", "0968"))
    if mutation == "date":
        stip = replace(stip, effective_date="2000-01-02")
    if mutation == "collection":
        stip = replace(stip, collected_at="2000-01-04T13:00:00+00:00")
    if mutation == "source":
        stip = replace(stip, raw_sha256="b" * 64)
    if mutation == "stale-row":
        stip = replace(stip, rows=(replace(stip.rows[0], row_sha256="b" * 64), *stip.rows[1:]))
    if mutation == "missing-row":
        stip = replace(stip, rows=stip.rows[1:])
    if mutation == "stale-evidence":
        stip = replace(
            stip,
            rows=(
                replace(
                    stip.rows[0],
                    evidence=replace(stip.rows[0].evidence, valid_through="2000-01-02"),
                ),
                *stip.rows[1:],
            ),
        )
    if mutation == "fund-no-independent":
        stip = replace(
            stip, fund_assertion=replace(stip.fund_assertion, source_sha256=stip.raw_sha256)
        )
    if mutation == "duplicate-security":
        stip = replace(
            stip, rows=(stip.rows[0], replace(stip.rows[1], security=stip.rows[0].security))
        )
    if mutation == "currency":
        security = stip.rows[0].security
        assert security is not None
        stip = replace(
            stip,
            rows=(
                replace(stip.rows[0], security=replace(security, currency="EUR")),
                *stip.rows[1:],
            ),
        )
    result = r.reconcile(acq, stip)
    assert code in codes(result) and result.benchmark_rows is None
    assert result.acquisition is acq and len(result.ledger) == 2


def test_unknown_extra_and_nonarray_sections_are_not_hidden_by_acquisition_section_index() -> None:
    for raw in (
        altered_section("newExposure", [{"percentOfFunds": 5}]),
        altered_section("unexpectedObject", {"percentOfFunds": 5}),
    ):
        acq, stip, _ = scenario(raw)
        result = r.reconcile(acq, stip)
        assert result.economic_total is None and result.benchmark_rows is None
        assert result.upstream_issues == acq.issues and result.upstream_issues
        assert len(result.sections) == 8
        assert result.acquisition.response is not None and result.acquisition.response.body == raw
        if b"unexpectedObject" in raw:
            summary = result.sections[-1]
            assert summary.known_weight_sum is None
            assert "non_array_section_retained" in summary.issues
        else:
            assert len(result.ledger) == 3


@pytest.mark.parametrize("mutation", ["body", "snapshot", "typed-number", "issues"])
def test_acquisition_snapshot_must_replay_including_json_token_types(mutation: str) -> None:
    acq, stip, _ = scenario()
    assert acq.response is not None and acq.snapshot is not None
    snapshot = acq.snapshot
    if mutation == "body":
        acq = replace(acq, response=replace(acq.response, body=RAW.replace(b"60.0000", b"59.0000")))
    if mutation == "snapshot":
        acq = replace(acq, snapshot=replace(snapshot, raw_sha256="b" * 64))
    if mutation == "issues":
        acq = replace(acq, issues=("forged",))
    if mutation == "typed-number":
        first_section = snapshot.sections[0]
        first = first_section.rows[0]
        assert isinstance(first, v.JsonObject)
        altered = v.JsonObject(
            tuple(
                (key, str(value) if key == "percentOfFunds" else value)
                for key, value in first.fields
            )
        )
        acq = replace(
            acq,
            snapshot=replace(
                snapshot,
                sections=(
                    replace(first_section, rows=(altered, *first_section.rows[1:])),
                    *snapshot.sections[1:],
                ),
            ),
        )
    result = r.reconcile(acq, stip)
    assert result.status == "unavailable" and not result.ledger
    assert "snapshot_replay_mismatch" in codes(result)


@pytest.mark.parametrize("status,complete", [(404, True), (200, False), (429, True)])
def test_failed_or_partial_acquisitions_are_unavailable_not_empty_baskets(
    status: int, complete: bool
) -> None:
    _, stip, _ = scenario()
    acq = v.acquire(
        SELECTION,
        collected_at=NOW,
        transport=lambda s: v.Response(status, s.url, "application/json", RAW, complete),
    )
    result = r.reconcile(acq, stip)
    assert result.status == "unavailable" and result.primary_known_weight_sum is None
    assert result.economic_total is None and result.benchmark_rows is None
    assert result.acquisition.response is not None and result.acquisition.response.body == RAW
    assert result.upstream_issues == acq.issues


def test_bridge_requires_separate_complete_portfolio_and_replay_matching_report() -> None:
    acq, stip, context = scenario()
    result = r.reconcile(acq, stip)
    with pytest.raises(r.ReconciliationUnavailable):
        r.bridge(replace(result, identity_sha256="b" * 64), context)
    with pytest.raises(r.ReconciliationUnavailable):
        r.bridge(result, replace(context, as_of="2000-01-02"))
    missing_cash = replace(
        context,
        portfolio_cash=replace(
            context.portfolio_cash, raw=None, unknown_reasons=("cash selection missing",)
        ),
    )
    bridged = r.bridge(result, missing_cash)
    assert bridged.basket.weights is None
    assert bridged.reconciliation is result and not bridged.benchmark_ready


def test_lexemes_and_independent_relationship_evidence_change_full_identity() -> None:
    acq, stip, _ = scenario()
    first = r.reconcile(acq, stip)
    acq2, stip2, _ = scenario(RAW.replace(b"60.0000", b"60"))
    changed = r.reconcile(acq2, stip2)
    assert first.economic_total == changed.economic_total == "1"
    assert first.canonical_sha256 == changed.canonical_sha256
    assert first.identity_sha256 != changed.identity_sha256
    assert r.reconcile(acq, stip) == first
    assert r.row_identity(v.JsonNumber("60")) != r.row_identity("60")


def test_fresh_process_runtime_only_replay() -> None:
    command = [sys.executable, "-I", str(ROOT / "scripts/qualify_benchmark_reconciliation.py")]
    first = subprocess.check_output(command, cwd=ROOT)
    assert first == subprocess.check_output(command, cwd=ROOT)
    assert json.loads(first)["benchmark_ready"] is False
    assert b'"included-primary"' in first and b'"linked-alternate"' in first


@pytest.mark.parametrize(
    "value", ["1e999999999999999999999", "Infinity", "-Infinity", "NaN", "", True]
)
def test_bad_weight_tokens_are_retained_as_unknown_without_crashing(value: object) -> None:
    rows = json.loads(RAW)[DAY]["equity"]
    rows[0]["percentOfFunds"] = value
    acq, stip, _ = scenario(altered_section("equity", rows))
    result = r.reconcile(acq, stip)
    assert result.primary_known_weight_sum == "2/5"
    assert result.economic_total is None and result.benchmark_rows is None
    assert "unknown_weight" in codes(result)


def test_exponent_token_stays_original_and_basket_reports_unsupported_source_spelling() -> None:
    raw = RAW.replace(b"60.0000", b"6.00000e1")
    acq, stip, context = scenario(raw)
    result = r.reconcile(acq, stip)
    assert result.economic_total == "1" and result.ledger[0].raw_weight == "6.00000e1"
    bridge = r.bridge(result, context)
    assert bridge.basket.weights is None
    assert any(issue.code == "fixed_point_required" for issue in bridge.basket.issues)
    assert bridge.reconciliation.acquisition.response is not None
    assert bridge.reconciliation.acquisition.response.body == raw


def test_unlocated_proof_or_rule_without_matching_source_is_not_consumed() -> None:
    acq, stip, _ = scenario()
    for changed in (
        replace(
            stip, sections=(*stip.sections, replace(stip.sections[0], section="not-in-source"))
        ),
        replace(stip, rows=(*stip.rows, replace(stip.rows[0], locator=r.Locator("equity", 99)))),
    ):
        result = r.reconcile(acq, changed)
        assert result.economic_total is None and result.benchmark_rows is None
        assert any("not_in_source" in code for code in codes(result))


def test_section_and_cash_evidence_must_cover_source_dates_and_currency() -> None:
    acq, stip, _ = scenario()
    for changed in (
        replace(
            stip,
            sections=(
                replace(
                    stip.sections[0],
                    evidence=replace(stip.sections[0].evidence, recorded="2000-01-05"),
                ),
                *stip.sections[1:],
            ),
        ),
        replace(
            stip,
            benchmark_cash=replace(
                stip.benchmark_cash, raw=None, unknown_reasons=("cash unknown",)
            ),
        ),
    ):
        result = r.reconcile(acq, changed)
        assert result.economic_total is None and result.benchmark_rows is None
    rows = json.loads(RAW)[DAY]["equity"]
    rows[0]["currency"] = "EUR"
    other, rules, _ = scenario(altered_section("equity", rows))
    assert "source_currency_contradiction" in codes(r.reconcile(other, rules))


@pytest.mark.parametrize("kind", ["scope", "duplicate-row", "duplicate-section", "unit"])
def test_malformed_or_ambiguous_stipulations_are_rejected(kind: str) -> None:
    acq, stip, _ = scenario()
    if kind == "scope":
        stip = replace(stip, scope="real-qualified")
    if kind == "duplicate-row":
        stip = replace(stip, rows=(*stip.rows, stip.rows[0]))
    if kind == "duplicate-section":
        stip = replace(stip, sections=(*stip.sections, stip.sections[0]))
    if kind == "unit":
        stip = replace(
            stip, sections=(replace(stip.sections[0], unit="assumed"), *stip.sections[1:])
        )
    with pytest.raises(r.ReconciliationUnavailable):
        r.reconcile(acq, stip)
