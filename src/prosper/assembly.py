"""Attributable opening diagnostics; no checkpoint or financial authority."""

import hashlib
import json
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Literal

from prosper.exact import BookValue, ExactValue, ExactValueError, Sign, UnknownValue, calculate
from prosper.fidelity_lots import COLUMNS, MAX_RECORDS, LotInspection, LotObservation

MAX_TEXT = 256
MAX_FINDINGS = 100
VERSION = "assembly-v1"


class AssemblyError(ValueError):
    """Safe validation failure: fixed schema location and code, never input values."""

    def __init__(self, location: str, code: str) -> None:
        self.location = location
        self.code = code
        super().__init__(f"{location}: {code}")


def _require(condition: bool, location: str, code: str = "invalid_value") -> None:
    if not condition:
        raise AssemblyError(location, code)


def _text(value: str, location: str) -> None:
    _require(
        type(value) is str
        and 0 < len(value) <= MAX_TEXT
        and bool(value.strip())
        and all(ord(c) >= 32 for c in value),
        location,
        "bounded_text_required",
    )


def _instant(value: str, location: str) -> datetime:
    _text(value, location)
    try:
        parsed = datetime.fromisoformat(value)
        _require("T" in value and parsed.utcoffset() is not None, location, "aware_time_required")
        return parsed
    except ValueError:
        raise AssemblyError(location, "aware_time_required") from None


def _tuple_of(value: object, kind: type, location: str) -> None:
    _require(type(value) is tuple, location, "immutable_tuple_required")
    assert isinstance(value, tuple)
    _require(len(value) <= MAX_RECORDS, location, "count_limit_exceeded")
    _require(all(type(item) is kind for item in value), location, "unsupported_item")


@dataclass(frozen=True, repr=False)
class Evidence:
    actor: str
    reference: str
    effective_at: str
    recorded_at: str

    def __post_init__(self) -> None:
        _text(self.actor, "evidence.actor")
        _text(self.reference, "evidence.reference")
        _instant(self.effective_at, "evidence.effective_at")
        _instant(self.recorded_at, "evidence.recorded_at")


@dataclass(frozen=True, repr=False)
class Assertion:
    value: str
    evidence: Evidence

    def __post_init__(self) -> None:
        _text(self.value, "assertion.value")
        _require(type(self.evidence) is Evidence, "assertion.evidence")


@dataclass(frozen=True, repr=False)
class AccountScope:
    source_account: str
    profile_ref: str
    account_ref: str
    role: Literal["traded", "monitor", "excluded"]
    evidence: Evidence

    def __post_init__(self) -> None:
        for name in ("source_account", "profile_ref", "account_ref"):
            _text(getattr(self, name), f"account.{name}")
        _require(self.role in ("traded", "monitor", "excluded"), "account.role")
        _require(type(self.evidence) is Evidence, "account.evidence")


@dataclass(frozen=True, repr=False)
class SecurityLink:
    record: int
    security_ref: str
    evidence: Evidence

    def __post_init__(self) -> None:
        _require(
            type(self.record) is int and 2 <= self.record <= MAX_RECORDS + 1, "security.record"
        )
        _text(self.security_ref, "security.security_ref")
        _require(type(self.evidence) is Evidence, "security.evidence")


@dataclass(frozen=True, repr=False)
class NameEvidence:
    name: str
    security_ref: str | None
    evidence: Evidence

    def __post_init__(self) -> None:
        _text(self.name, "name.name")
        if self.security_ref is not None:
            _text(self.security_ref, "name.security_ref")
        _require(type(self.evidence) is Evidence, "name.evidence")


def _amount(value: ExactValue, location: str) -> None:
    _require(type(value) is ExactValue, location, "exact_value_required")
    _require(not value.value.is_signed(), location, "nonnegative_required")


@dataclass(frozen=True, repr=False)
class CashFact:
    account_ref: str
    currency: str
    amount: ExactValue
    evidence: Evidence

    def __post_init__(self) -> None:
        _text(self.account_ref, "cash.account_ref")
        _text(self.currency, "cash.currency")
        _amount(self.amount, "cash.amount")
        _require(type(self.evidence) is Evidence, "cash.evidence")


@dataclass(frozen=True, repr=False)
class CashSelection:
    amount: ExactValue
    evidence: Evidence
    reviewed: bool

    def __post_init__(self) -> None:
        _amount(self.amount, "selection.amount")
        _require(type(self.evidence) is Evidence, "selection.evidence")
        _require(type(self.reviewed) is bool, "selection.reviewed")


@dataclass(frozen=True, repr=False)
class Supplements:
    accounts: tuple[AccountScope, ...] = ()
    securities: tuple[SecurityLink, ...] = ()
    currency: Assertion | None = None
    cutoff: Assertion | None = None
    inclusion: Assertion | None = None
    stock_scope: Assertion | None = None
    basis_assumption: Assertion | None = None
    history: Assertion | None = None
    imported_cash: tuple[CashFact, ...] = ()
    usable_cash: tuple[CashFact, ...] = ()
    commitments: tuple[CashFact, ...] = ()
    selection: CashSelection | None = None
    restrictions: tuple[NameEvidence, ...] = ()
    known_conflicts: tuple[NameEvidence, ...] = ()
    execution_claims: tuple[Assertion, ...] = ()

    def __post_init__(self) -> None:
        for name, kind in (
            ("accounts", AccountScope),
            ("securities", SecurityLink),
            ("imported_cash", CashFact),
            ("usable_cash", CashFact),
            ("commitments", CashFact),
            ("restrictions", NameEvidence),
            ("known_conflicts", NameEvidence),
            ("execution_claims", Assertion),
        ):
            _tuple_of(getattr(self, name), kind, f"supplements.{name}")
        for name in (
            "currency",
            "cutoff",
            "inclusion",
            "stock_scope",
            "basis_assumption",
            "history",
        ):
            _require(
                getattr(self, name) is None or type(getattr(self, name)) is Assertion,
                f"supplements.{name}",
            )
        _require(
            self.selection is None or type(self.selection) is CashSelection, "supplements.selection"
        )


@dataclass(frozen=True)
class Finding:
    scope: Literal["assembly", "wash", "funding", "execution", "dependency"]
    code: str
    record: int | None = None


@dataclass(frozen=True, repr=False)
class Holding:
    observation: LotObservation
    account: AccountScope | None
    security: SecurityLink | None


@dataclass(frozen=True)
class Assessment:
    input_sha256: str
    observation: LotInspection = field(repr=False)
    supplements: Supplements = field(repr=False)
    holdings: tuple[Holding, ...] = field(repr=False)
    source_quantity: BookValue = field(repr=False)
    source_reported_basis: BookValue = field(repr=False)
    source_current_value: BookValue = field(repr=False)
    selected_cash: ExactValue = field(repr=False)
    selection_state: Literal["unset_default_requires_review", "unreviewed", "reviewed"]
    findings: tuple[Finding, ...]
    findings_truncated: bool
    assembly_sufficient: bool

    @property
    def schema_version(self) -> Literal["assembly-v1"]:
        return "assembly-v1"

    @property
    def wash_verification(self) -> Literal["unverified"]:
        return "unverified"

    @property
    def restriction_intent(self) -> Literal["both_sale_and_buy"]:
        return "both_sale_and_buy"

    @property
    def planning_ready(self) -> Literal[False]:
        return False

    @property
    def canonical_checkpoint_ready(self) -> Literal[False]:
        return False


def _identity(value: object) -> object:
    """Serialize *all* retained input evidence, including exact spelling and ordering."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, ExactValue):
        return {"text": value.original_text, "sign": value.sign.value}
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _identity(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_identity(item) for item in value]
    if value is None or type(value) in (str, bool, int):
        return value
    raise AssemblyError("input", "unsupported_identity_value")


def _sum(observations: tuple[LotObservation, ...], name: str) -> BookValue:
    total: BookValue = ExactValue("0", Sign.NONNEGATIVE)
    for item in observations:
        observed = getattr(item, name)
        value: BookValue = (
            observed.value if observed.value is not None else UnknownValue((observed.reason,))
        )
        try:
            total = calculate("add", total, value, field_name=name, sign=Sign.NONNEGATIVE)
        except ExactValueError:
            return UnknownValue(("aggregate_out_of_range",))
    return total


def assess_inputs(inspection: LotInspection, supplements: Supplements) -> Assessment:
    """Assess inspected source output and immutable assertions.

    Account roles and security links are assertions, not verified tax classification.
    Source aggregates cover all observed rows (including monitoring/excluded accounts),
    never NAV. Cash facts are account/currency scoped; commitments are retained without
    subtracting them from an already asserted usable amount. No source file is opened.
    """
    _require(type(inspection) is LotInspection, "inspection", "inspection_required")
    _require(type(supplements) is Supplements, "supplements", "supplements_required")
    _tuple_of(inspection.observations, LotObservation, "inspection.observations")
    # LotInspection is a trusted in-process inspector result, not an input decoder.
    # Refuse inconsistent hand-constructed/replaced observation containers as well.
    _require(
        type(inspection.records) is tuple and len(inspection.records) <= MAX_RECORDS,
        "inspection.records",
        "bounded_records_required",
    )
    findings: list[Finding] = []
    truncated = False
    assembly_failed = False

    def add(
        scope: Literal["assembly", "wash", "funding", "execution", "dependency"],
        code: str,
        record: int | None = None,
    ) -> None:
        nonlocal truncated, assembly_failed
        if scope == "assembly":
            assembly_failed = True
        if len(findings) < MAX_FINDINGS:
            findings.append(Finding(scope, code, record))
        else:
            truncated = True

    if inspection.status == "invalid" or inspection.further_issues or not inspection.raw_sha256:
        add("assembly", "invalid_or_incomplete_inspection")
    if len(inspection.records) != len(inspection.observations) or not inspection.observations:
        add("assembly", "incomplete_observation_coverage")
    expected = {
        "currency": "USD",
        "inclusion": "holdings_at_cutoff_inclusion_asserted",
        "stock_scope": "observed_holdings_stock_scope_asserted",
        "basis_assumption": "source_reported_total_basis_ordinary_opening_assumption",
    }
    for name, required in expected.items():
        asserted = getattr(supplements, name)
        if asserted is None:
            add("assembly", f"{name}_missing")
        elif asserted.value != required:
            add("assembly", f"{name}_unsupported")
    if supplements.cutoff is None:
        add("assembly", "economic_cutoff_missing")
    else:
        try:
            cutoff = _instant(supplements.cutoff.value, "cutoff.value")
            if cutoff != _instant(supplements.cutoff.evidence.effective_at, "cutoff.effective_at"):
                add("assembly", "cutoff_effective_time_conflict")
        except AssemblyError:
            add("assembly", "economic_cutoff_invalid")

    accounts: dict[str, AccountScope] = {}
    for account in supplements.accounts:
        if account.source_account in accounts:
            add("assembly", "duplicate_or_conflicting_account_binding")
        else:
            accounts[account.source_account] = account
    if len({a.profile_ref for a in accounts.values()}) != 1:
        add("assembly", "single_profile_required")
    traded = [a for a in accounts.values() if a.role == "traded"]
    if len(traded) != 1:
        add("assembly", "single_traded_account_required")
    if len({a.account_ref for a in accounts.values()}) != len(accounts):
        add("assembly", "account_binding_alias_conflict")
    securities: dict[int, SecurityLink] = {}
    for security in supplements.securities:
        if security.record in securities:
            add("assembly", "duplicate_or_conflicting_security_link", security.record)
        else:
            securities[security.record] = security
    holdings: list[Holding] = []
    seen: set[int] = set()
    for item in inspection.observations:
        row = item.source_fields
        if (
            type(item.record) is not int
            or item.record in seen
            or not 2 <= item.record <= len(inspection.records) + 1
            or len(row) != len(COLUMNS)
            or row != inspection.records[item.record - 2]
        ):
            add("assembly", "observation_structure_conflict")
            continue
        seen.add(item.record)
        bound_account = accounts.get(row[0])
        linked_security = securities.get(item.record)
        if bound_account is None:
            add("assembly", "account_binding_missing", item.record)
        if linked_security is None:
            add("assembly", "security_identity_missing", item.record)
        if item.quantity.value is None:
            add("assembly", "quantity_unknown", item.record)
        if item.reported_basis.value is None and (
            bound_account is None or bound_account.role == "traded"
        ):
            add("assembly", "required_reported_basis_unknown", item.record)
        holdings.append(Holding(item, bound_account, linked_security))
    if set(securities) - seen:
        add("assembly", "security_link_without_observation")
    if set(accounts) - {h.observation.source_fields[0] for h in holdings}:
        add("assembly", "account_binding_without_observation")

    selected = (
        ExactValue("0", Sign.NONNEGATIVE)
        if supplements.selection is None
        else supplements.selection.amount
    )
    state: Literal["unset_default_requires_review", "unreviewed", "reviewed"] = (
        "unset_default_requires_review"
        if supplements.selection is None
        else "reviewed"
        if supplements.selection.reviewed
        else "unreviewed"
    )
    if state != "reviewed":
        add("funding", "selected_cash_requires_review")
    traded_ref = traded[0].account_ref if len(traded) == 1 else None
    for group in (supplements.imported_cash, supplements.usable_cash, supplements.commitments):
        for fact in group:
            if fact.account_ref != traded_ref or fact.currency != "USD":
                add("funding", "cash_scope_or_currency_unresolved")
    for name in ("imported_cash", "usable_cash"):
        group = getattr(supplements, name)
        amounts: dict[tuple[str, str, datetime], set[str]] = {}
        for fact in group:
            effective = _instant(fact.evidence.effective_at, "cash.effective_at")
            amounts.setdefault((fact.account_ref, fact.currency, effective), set()).add(
                fact.amount.canonical
            )
        if any(len(values) > 1 for values in amounts.values()):
            add("funding", f"{name}_contradictory")
        if len({key[2] for key in amounts}) > 1:
            add("funding", "cash_observations_have_distinct_effective_times")
    usable = [
        f for f in supplements.usable_cash if f.account_ref == traded_ref and f.currency == "USD"
    ]
    if not usable:
        add("funding", "usable_funds_unverified")
    elif supplements.selection is not None:
        matching = [
            fact
            for fact in usable
            if _instant(fact.evidence.effective_at, "cash.effective_at")
            == _instant(supplements.selection.evidence.effective_at, "selection.effective_at")
        ]
        if len(matching) != len(usable):
            add("funding", "usable_funds_and_selection_times_differ")
        if any(selected.value > fact.amount.value for fact in matching):
            add("funding", "selection_exceeds_asserted_usable_funds")
    if supplements.commitments:
        add("funding", "pending_commitments_require_funding_validation")
    add("funding", "trade_funding_validation_not_performed")
    add("wash", "unverified_wash_sale_history")
    if supplements.history is not None:
        add("wash", "history_claim_unverified")
    if any(n.security_ref is None for n in supplements.restrictions + supplements.known_conflicts):
        add("wash", "unresolved_name_references")
    add("wash", "known_conflicts_and_both_leg_restrictions_require_screening")
    add("execution", "confirmation_allocation_and_reconciliation_unverified")
    if supplements.execution_claims:
        add("execution", "manual_execution_claims_unqualified")
    for code in (
        "source_fidelity_and_tax_classification_unqualified",
        "sale_lot_identity_unqualified",
        "quotes_benchmark_risk_and_constraints_not_assessed",
    ):
        add("dependency", code)
    totals = tuple(
        _sum(inspection.observations, name)
        for name in ("quantity", "reported_basis", "current_value")
    )
    if any(
        isinstance(total, UnknownValue) and "aggregate_out_of_range" in total.reasons
        for total in totals
    ):
        add("assembly", "aggregate_out_of_range")
    identity = hashlib.sha256(
        json.dumps(
            [VERSION, _identity(inspection), _identity(supplements)],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
    ).hexdigest()
    return Assessment(
        identity,
        inspection,
        supplements,
        tuple(holdings),
        totals[0],
        totals[1],
        totals[2],
        selected,
        state,
        tuple(findings),
        truncated,
        not assembly_failed and not truncated,
    )
