"""Typed source context and explicit inputs for conditional lot diagnostics."""

from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from prosper.advisory import decimal_value
from prosper.advisory_records import DecimalFact, Digest, Fact, Record, Revision, Security
from prosper.record_types import DateText, Identifier, Text, Timestamp


class Evidence(Record):
    actor: Text
    reference: Text
    effective_at: DateText
    recorded_at: Timestamp


class Account(Record):
    source_account: Text
    account_id: Identifier
    alias: Text
    role: Literal["traded-taxable", "household-taxable", "spouse", "ira-roth", "scope-unresolved"]
    evidence: Evidence


class SecurityMapping(Record):
    source_account: Text
    symbol: Text
    security: Security
    evidence: Evidence


class Activity(Record):
    id: Identifier
    identity: Fact[str]
    account_ref: Text
    account_scope: Text
    day: Fact[DateText]
    side: Literal["acquisition", "sale"]
    quantity: DecimalFact
    pnl: Fact[str]
    source_ref: Text

    @model_validator(mode="after")
    def signed_pnl(self) -> Self:
        if self.pnl.value is not None:
            decimal_value(self.pnl.value, signed=True)
        return self


class Relationship(Record):
    left: Text
    right: Text
    status: Literal["conflict", "distinct", "unknown"]
    valid_from: DateText
    valid_through: DateText
    evidence: Evidence
    rationale: Text

    @model_validator(mode="after")
    def dates(self) -> Self:
        if self.valid_from > self.valid_through:
            raise ValueError("invalid_relationship_window")
        return self


class Restriction(Record):
    name: Text
    identity: Fact[str]
    start: DateText | None = None
    end: DateText | None = None
    side: Literal["both", "sell", "buy"] = "both"
    source_ref: Text

    @model_validator(mode="after")
    def dates(self) -> Self:
        if self.start and self.end and self.start > self.end:
            raise ValueError("invalid_restriction_window")
        return self


class ScreeningFacts(Record):
    activities: tuple[Activity, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    restrictions: tuple[Restriction, ...] = ()
    basis_disputes: tuple[Text, ...] = ()
    unbounded_event: Fact[bool]


class IndependentPosition(Record):
    security_id: Identifier
    quantity: DecimalFact
    source_ref: Text


class FidelityContext(Record):
    version: Literal["fidelity-lot-context-v1"]
    source_sha256: Digest
    source_as_of: DateText
    currency: Literal["USD"]
    accounts: Annotated[tuple[Account, ...], Field(min_length=1, max_length=100)]
    mappings: Annotated[tuple[SecurityMapping, ...], Field(max_length=10000)]
    source_coverage: Fact[str]
    reported_basis_assumption: Fact[bool]
    evidence: Evidence
    screening: ScreeningFacts
    independent_positions: tuple[IndependentPosition, ...] = ()

    @model_validator(mode="after")
    def keys(self) -> Self:
        if sum(a.role == "traded-taxable" for a in self.accounts) != 1:
            raise ValueError("exactly_one_traded_taxable_account_required")
        if len({a.source_account for a in self.accounts}) != len(self.accounts):
            raise ValueError("duplicate_account_mapping")
        if len({(m.source_account, m.symbol) for m in self.mappings}) != len(self.mappings):
            raise ValueError("duplicate_source_security_mapping")
        securities: dict[str, Security] = {}
        for mapping in self.mappings:
            security = mapping.security
            old = securities.get(security.id)
            if old and (old.identity, old.classification, old.currency) != (
                security.identity,
                security.classification,
                security.currency,
            ):
                raise ValueError("contradictory_canonical_security")
            securities[security.id] = security
        if len({p.security_id for p in self.independent_positions}) != len(
            self.independent_positions
        ):
            raise ValueError("duplicate_independent_position")
        return self


class Mark(Record):
    security_id: Identifier
    identity: Text
    price: DecimalFact
    day: Fact[DateText]
    source_ref: Text
    currency: Literal["USD"]


class FinalCashTarget(Record):
    enabled: bool
    amount: str | None
    investor_tolerance: str | None

    @model_validator(mode="after")
    def target(self) -> Self:
        if self.enabled:
            if self.amount is None or self.investor_tolerance is None:
                raise ValueError("enabled_cash_target_requires_amount_and_investor_tolerance")
            decimal_value(self.amount)
            decimal_value(self.investor_tolerance)
        elif self.amount is not None or self.investor_tolerance is not None:
            raise ValueError("disabled_cash_target_has_no_amount_or_tolerance")
        return self


class LotSettings(Record):
    analysis_date: DateText
    max_mark_age_days: Annotated[int, Field(ge=0, le=36500)]
    max_snapshot_age_days: Annotated[int, Field(ge=0, le=36500)]
    marks: tuple[Mark, ...]
    sell_fee_per_isolated_order: DecimalFact
    sell_discount_bps: DecimalFact
    cash_to_invest: str
    cash_budget_reviewed: bool
    final_cash_target: FinalCashTarget
    funding_assumption: Fact[str]
    history_coverage: Fact[str]
    manual_restrictions: tuple[Restriction, ...] = ()
    supplied_activity: tuple[Activity, ...] = ()
    relationships: tuple[Relationship, ...] = ()

    @model_validator(mode="after")
    def values(self) -> Self:
        decimal_value(self.cash_to_invest)
        if (
            self.sell_discount_bps.value is not None
            and decimal_value(self.sell_discount_bps.value) > 10000
        ):
            raise ValueError("sell_discount_cannot_exceed_mark")
        if len({m.security_id for m in self.marks}) != len(self.marks):
            raise ValueError("duplicate_mark")
        return self


class LotDiagnosticRequest(Record):
    run_id: Identifier
    expected_revision: Revision
    as_of: Timestamp
    sale_quantities: dict[Identifier, Annotated[int, Field(ge=1, le=2**53 - 1)]] = Field(
        default_factory=dict
    )
    replacement_security_ids: tuple[Identifier, ...] = ()

    @field_validator("replacement_security_ids", mode="before")
    @classmethod
    def json_ids(cls, value: object) -> object:
        # FastAPI already decoded JSON; collection semantics may accept arrays,
        # while strict element validation still rejects coerced scalar identities.
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def unique_buys(self) -> Self:
        if len(set(self.replacement_security_ids)) != len(self.replacement_security_ids):
            raise ValueError("duplicate_replacement_security")
        return self
