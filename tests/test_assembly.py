"""Independent source/rational expectations, not financial or broker qualification."""

from dataclasses import FrozenInstanceError, replace
from decimal import localcontext
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest

from prosper.assembly import (
    MAX_FINDINGS,
    AccountScope,
    AssemblyError,
    Assertion,
    Assessment,
    CashFact,
    CashSelection,
    Evidence,
    NameEvidence,
    SecurityLink,
    Supplements,
    assess_inputs,
)
from prosper.exact import ExactValue, Sign, UnknownValue
from prosper.fidelity_lots import MAX_RECORDS, LotInspection, Observed, inspect_combined_lots

FIXTURES = Path(__file__).resolve().parents[1] / "examples/synthetic/fidelity"
TIME = "2026-10-23T16:00:00-04:00"
EVIDENCE = Evidence("fictional-actor", "fictional-reference", TIME, "2026-10-24T01:00:00Z")


def observation(name: str = "combined-stocks") -> LotInspection:
    return inspect_combined_lots((FIXTURES / f"{name}.csv").read_bytes())


def assertion(value: str) -> Assertion:
    return Assertion(value, EVIDENCE)


def opening() -> Supplements:
    observed = observation()
    return Supplements(
        accounts=(
            AccountScope("000SYNTH001", "profile", "traded", "traded", EVIDENCE),
            AccountScope("000SYNTH002", "profile", "other", "monitor", EVIDENCE),
            AccountScope("000SYNTH003", "profile", "ira", "monitor", EVIDENCE),
        ),
        securities=tuple(
            SecurityLink(o.record, o.source_fields[2], EVIDENCE) for o in observed.observations
        ),
        currency=assertion("USD"),
        cutoff=assertion(TIME),
        inclusion=assertion("holdings_at_cutoff_inclusion_asserted"),
        stock_scope=assertion("observed_holdings_stock_scope_asserted"),
        basis_assumption=assertion("source_reported_total_basis_ordinary_opening_assumption"),
    )


def assess(supplements: Supplements | None = None, name: str = "combined-stocks") -> Assessment:
    return assess_inputs(observation(name), opening() if supplements is None else supplements)


def codes(result: Assessment, scope: str | None = None) -> set[str]:
    return {f.code for f in result.findings if scope is None or f.scope == scope}


def cash(amount: str, account: str = "traded", currency: str = "USD") -> CashFact:
    return CashFact(account, currency, ExactValue(amount, Sign.NONNEGATIVE), EVIDENCE)


def selection(amount: str, reviewed: bool = True) -> CashSelection:
    return CashSelection(ExactValue(amount, Sign.NONNEGATIVE), EVIDENCE, reviewed)


def test_a01_observations_only_do_not_infer_supplements() -> None:
    observed = observation()
    result = assess_inputs(observed, Supplements())
    assert result.observation is observed
    assert all(
        h.observation is o for h, o in zip(result.holdings, observed.observations, strict=True)
    )
    assert not result.assembly_sufficient
    assert {
        "account_binding_missing",
        "currency_missing",
        "economic_cutoff_missing",
        "security_identity_missing",
    } <= codes(result, "assembly")
    assert {f.record for f in result.findings if f.code == "security_identity_missing"} == set(
        range(2, 10)
    )


def test_a02_attributable_opening_facts_resolve_only_assembly() -> None:
    inputs = opening()
    result = assess(inputs)
    assert result.assembly_sufficient and codes(result, "assembly") == set()
    assert result.supplements is inputs
    assert result.holdings[0].account is inputs.accounts[0]
    assert result.holdings[0].security is inputs.securities[0]
    assert result.supplements.cutoff is not None
    assert result.supplements.cutoff.evidence.recorded_at == "2026-10-24T01:00:00Z"
    assert "source_fidelity_and_tax_classification_unqualified" in codes(result, "dependency")
    assert "sale_lot_identity_unqualified" in codes(result, "dependency")
    assert not result.planning_ready and not result.canonical_checkpoint_ready


def test_a03_independent_rational_totals_and_identical_lots_retained() -> None:
    with localcontext() as context:
        context.prec = 2
        result = assess()
    for value, expected in (
        (result.source_quantity, "49.125"),
        (result.source_reported_basis, "3604.00"),
        (result.source_current_value, "3653.75"),
    ):
        assert isinstance(value, ExactValue)
        assert Fraction(value.canonical) == Fraction(expected)
    lots = result.holdings
    assert len(lots) == 8
    assert lots[1].observation.source_fields[7:] == lots[2].observation.source_fields[7:]
    assert lots[1].observation.source_record != lots[2].observation.source_record
    assert lots[4].observation.quantity.value is not None
    assert lots[4].observation.quantity.value.original_text == "0.125"


def test_a04_reported_basis_and_unknown_term_are_not_recomputed() -> None:
    result = assess()
    lot = result.holdings[3].observation
    assert lot.reported_basis.value is not None and lot.average_basis.value is not None
    assert lot.reported_basis.value.original_text == "100.00"
    assert Fraction(lot.average_basis.value.canonical) * 3 == Fraction("99.99")
    # Unknown term alone does not exclude a known-basis observation from assembly.
    raw = (FIXTURES / "combined-stocks.csv").read_bytes().replace(b",Long,", b",Unknown,")
    observed = inspect_combined_lots(raw)
    altered = assess_inputs(observed, opening())
    assert altered.assembly_sufficient
    assert altered.holdings[0].observation.source_fields[8] == "Unknown"


def test_a05_optional_cash_history_positions_missing_keep_scoped_gaps() -> None:
    result = assess()
    assert result.assembly_sufficient
    assert result.supplements.imported_cash == ()
    assert "unverified_wash_sale_history" in codes(result, "wash")
    assert "usable_funds_unverified" in codes(result, "funding")
    assert "confirmation_allocation_and_reconciliation_unverified" in codes(result, "execution")
    assert result.wash_verification == "unverified"
    assert not result.planning_ready and not result.canonical_checkpoint_ready


def test_a06_unset_and_reviewed_zero_are_distinguishable() -> None:
    unset, reviewed = assess(), assess(replace(opening(), selection=selection("0.00")))
    assert unset.selected_cash.canonical == reviewed.selected_cash.canonical == "0"
    assert unset.selection_state == "unset_default_requires_review"
    assert reviewed.selection_state == "reviewed"
    assert unset.input_sha256 != reviewed.input_sha256
    assert unset.supplements.imported_cash == reviewed.supplements.imported_cash == ()
    assert "selected_cash_requires_review" not in codes(reviewed, "funding")
    unreviewed = assess(replace(opening(), selection=selection("0", False)))
    assert unreviewed.selection_state == "unreviewed"
    assert "selected_cash_requires_review" in codes(unreviewed, "funding")


def test_a07_partial_cash_is_separate_evidence_not_nav_or_buying_power() -> None:
    result = assess(
        replace(opening(), imported_cash=(cash("10000.00"),), selection=selection("3000"))
    )
    assert result.supplements.imported_cash[0].amount.original_text == "10000.00"
    assert result.selected_cash.canonical == "3000"
    assert result.observation.raw_sha256 == observation().raw_sha256
    assert result.assembly_sufficient
    assert "usable_funds_unverified" in codes(result, "funding")
    # This boundary intentionally emits source totals only, with no sleeve/NAV diagnostic.
    assert not hasattr(result, "nav")


def test_a08_contradictions_commitments_retained_without_double_subtraction() -> None:
    result = assess(
        replace(
            opening(),
            selection=selection("3000"),
            imported_cash=(cash("10000"), cash("9000")),
            usable_cash=(cash("2000"),),
            commitments=(cash("700"),),
        )
    )
    assert {
        "selection_exceeds_asserted_usable_funds",
        "imported_cash_contradictory",
        "pending_commitments_require_funding_validation",
    } <= codes(result, "funding")
    assert result.supplements.commitments[0].amount.canonical == "700"
    assert len(result.supplements.imported_cash) == 2
    assert result.assembly_sufficient  # separate from funding sufficiency
    enough = assess(
        replace(
            opening(),
            selection=selection("3000"),
            usable_cash=(cash("3500"),),
            commitments=(cash("700"),),
        )
    )
    assert "selection_exceeds_asserted_usable_funds" not in codes(enough)
    assert "pending_commitments_require_funding_validation" in codes(enough)


def test_a09_missing_or_asserted_complete_history_never_clears_known_conflicts() -> None:
    conflict = NameEvidence("known fictional conflict", "FAAA", EVIDENCE)
    result = assess(
        replace(
            opening(),
            history=assertion("claimed_complete"),
            known_conflicts=(conflict,),
            restrictions=(
                NameEvidence("resolved fictional name", "FBBB", EVIDENCE),
                NameEvidence("ambiguous fictional alias", None, EVIDENCE),
            ),
        )
    )
    assert result.supplements.known_conflicts == (conflict,)
    assert result.restriction_intent == "both_sale_and_buy"
    assert result.wash_verification == "unverified"
    assert {
        "unverified_wash_sale_history",
        "history_claim_unverified",
        "unresolved_name_references",
    } <= codes(result, "wash")
    assert assess().wash_verification == "unverified"  # empty manual list clears nothing


@pytest.mark.parametrize(
    "fixture",
    [
        "repeated-reference",
        "conflicting-reference",
        "schema-drift",
        "malformed-row",
        "missing-basis",
    ],
)
def test_a10_invalid_or_incomplete_inspection_stays_insufficient(fixture: str) -> None:
    result = assess(name=fixture)
    assert not result.assembly_sufficient and codes(result, "assembly")
    assert not result.planning_ready and not result.canonical_checkpoint_ready
    if fixture == "missing-basis":
        assert isinstance(result.source_reported_basis, UnknownValue)
        assert "required_reported_basis_unknown" in codes(result)


def test_a10_inconsistent_supplements_and_replaced_observations_fail() -> None:
    base = opening()
    contradictory = replace(
        base, securities=base.securities + (SecurityLink(2, "contradiction", EVIDENCE),)
    )
    assert "duplicate_or_conflicting_security_link" in codes(assess(contradictory))
    changed = replace(
        base, accounts=base.accounts + (replace(base.accounts[0], account_ref="other"),)
    )
    assert not assess(changed).assembly_sufficient
    assert not assess(replace(base, currency=assertion("EUR"))).assembly_sufficient
    assert not assess(
        replace(base, cutoff=assertion("2026-10-23T17:00:00-04:00"))
    ).assembly_sufficient
    assert not assess(replace(base, securities=base.securities[1:])).assembly_sufficient
    observed = observation()
    for altered in (
        replace(observed, observations=observed.observations[:1]),
        replace(observed, input_truncated=True),
        replace(observed, further_issues=True),
        replace(observed, observations=(replace(observed.observations[0], record=3),)),
    ):
        assert not assess_inputs(altered, base).assembly_sufficient


def test_a11_identity_covers_each_immutable_input_and_retains_provenance_order() -> None:
    base = opening()
    result = assess(base)
    assert result.input_sha256 == assess(base).input_sha256
    variants = (
        replace(base, selection=selection("1")),
        replace(base, restrictions=(NameEvidence("fictional", "FAAA", EVIDENCE),)),
        replace(base, cutoff=assertion("2026-10-24T16:00:00-04:00")),
        replace(base, accounts=tuple(reversed(base.accounts))),
        replace(base, currency=Assertion("USD", replace(EVIDENCE, reference="other-reference"))),
    )
    identities = {result.input_sha256} | {assess(v).input_sha256 for v in variants}
    assert len(identities) == len(variants) + 1
    with pytest.raises(FrozenInstanceError):
        result.assembly_sufficient = True  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        base.accounts[0].role = "traded"  # type: ignore[misc]


def test_a12_manual_claim_is_retained_unqualified_not_actual_execution() -> None:
    claim = assertion("fictional worksheet says sold five shares")
    result = assess(replace(opening(), execution_claims=(claim,)))
    assert result.assembly_sufficient
    assert result.supplements.execution_claims == (claim,)
    assert "manual_execution_claims_unqualified" in codes(result, "execution")
    assert "confirmation_allocation_and_reconciliation_unverified" in codes(result, "execution")


def test_privacy_strict_validation_limits_and_truncation() -> None:
    sentinel = "PRIVATE_SENTINEL"
    result = assess(replace(opening(), history=assertion(sentinel)))
    for item in (
        result,
        result.supplements,
        result.supplements.history,
        EVIDENCE,
        result.holdings,
        result.findings,
    ):
        assert sentinel not in repr(item)
        assert "000SYNTH" not in repr(item)
    with pytest.raises(AssemblyError) as error:
        Assertion(sentinel * 30, EVIDENCE)
    assert sentinel not in str(error.value)
    with pytest.raises(AssemblyError, match="aware_time_required"):
        Evidence("actor", "ref", "not-an-instant", TIME)
    with pytest.raises(AssemblyError):
        Evidence("actor", "ref", "2026-10-23T12:00:00", TIME)
    with pytest.raises(AssemblyError, match="immutable_tuple_required"):
        Supplements(accounts=cast(tuple[AccountScope, ...], []))
    with pytest.raises(AssemblyError, match="nonnegative_required"):
        CashSelection(ExactValue("-1", Sign.SIGNED), EVIDENCE, True)
    with pytest.raises(AssemblyError, match="count_limit_exceeded"):
        Supplements(restrictions=(NameEvidence("fictional", None, EVIDENCE),) * (MAX_RECORDS + 1))
    huge = replace(opening(), securities=opening().securities[:1] * (MAX_FINDINGS + 1))
    limited = assess(huge)
    assert len(limited.findings) == MAX_FINDINGS
    assert limited.findings_truncated and not limited.assembly_sufficient


def test_cash_scope_aliases_unknown_and_unsupported_assertions() -> None:
    assert "cash_scope_or_currency_unresolved" in codes(
        assess(
            replace(opening(), usable_cash=(cash("9000", "other"), cash("9000", currency="EUR")))
        )
    )
    aliases = opening().accounts[:2] + (replace(opening().accounts[2], account_ref="other"),)
    assert not assess(replace(opening(), accounts=aliases)).assembly_sufficient
    assert not assess(
        replace(opening(), cutoff=assertion("fictional bad cutoff"))
    ).assembly_sufficient
    assert not assess(replace(opening(), stock_scope=assertion("unknown"))).assembly_sufficient
    known_and_unknown = replace(
        opening(), usable_cash=(cash("2000"), cash("5000")), selection=selection("3000")
    )
    assert "usable_cash_contradictory" in codes(assess(known_and_unknown))


def test_exact_aggregate_overflow_and_unknown_quantity_do_not_promote_partial_totals() -> None:
    observed = observation()
    maximum = ExactValue("9999999999999999999999999999", Sign.NONNEGATIVE)
    changed = tuple(
        replace(o, quantity=Observed("fictional-large", maximum, None))
        for o in observed.observations
    )
    result = assess_inputs(replace(observed, observations=changed), opening())
    assert isinstance(result.source_quantity, UnknownValue)
    assert result.source_quantity.reasons == ("aggregate_out_of_range",)
    assert not result.assembly_sufficient
    unknown = replace(
        observed.observations[0], quantity=Observed("--", None, "source_value_unknown")
    )
    result = assess_inputs(
        replace(observed, observations=(unknown,) + observed.observations[1:]),
        opening(),
    )
    assert isinstance(result.source_quantity, UnknownValue)
    assert not result.assembly_sufficient
    assert "quantity_unknown" in codes(result)


def test_bad_typed_inputs_fail_safely_without_coercion_or_paths() -> None:
    with pytest.raises(AssemblyError, match="inspection_required"):
        assess_inputs(cast(LotInspection, None), opening())
    with pytest.raises(AssemblyError, match="invalid_value"):
        SecurityLink(cast(int, True), "fictional", EVIDENCE)
    with pytest.raises(AssemblyError, match="exact_value_required"):
        CashSelection(cast(ExactValue, "PRIVATE_SENTINEL"), EVIDENCE, True)
    with pytest.raises(AssemblyError, match="invalid_value"):
        CashSelection(ExactValue("0", Sign.NONNEGATIVE), EVIDENCE, cast(bool, 1))


def test_cash_facts_at_different_times_are_not_invented_same_time_contradictions() -> None:
    old = replace(EVIDENCE, effective_at="2026-10-22T16:00:00-04:00")
    result = assess(
        replace(
            opening(),
            selection=selection("3000"),
            imported_cash=(cash("10000"), replace(cash("9000"), evidence=old)),
            usable_cash=(replace(cash("2000"), evidence=old),),
        )
    )
    assert "imported_cash_contradictory" not in codes(result)
    assert "cash_observations_have_distinct_effective_times" in codes(result)
    assert "usable_funds_and_selection_times_differ" in codes(result)
    assert "selection_exceeds_asserted_usable_funds" not in codes(result)
