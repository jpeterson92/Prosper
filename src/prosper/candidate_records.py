"""Explicit inputs for the tiny discrete reference, not investor defaults."""

from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, model_validator

from prosper.advisory import number
from prosper.advisory_records import Fact, ImportSnapshot, Record, Security
from prosper.lot_records import LotSettings
from prosper.record_types import DateText, Identifier, Text


def _amount(value: str) -> str:
    number(value)
    return value


Amount = Annotated[str, AfterValidator(_amount)]
Shares = Annotated[int, Field(ge=1, le=2**53 - 1)]
Bound = Annotated[int, Field(ge=0, le=10000)]
SearchMethod = Literal[
    "complete-cartesian-whole-share-reference", "deterministic-loss-prefix-repair-v1"
]


class OptionalLimit(Record):
    enabled: bool
    value: Amount | None

    @model_validator(mode="after")
    def selected(self) -> Self:
        if self.enabled != (self.value is not None):
            raise ValueError("enabled_limit_requires_value_disabled_requires_none")
        return self


class TaxScenario(Record):
    usable_loss_fraction: Amount
    offset_rate: Amount
    reference: Text

    @model_validator(mode="after")
    def fractions(self) -> Self:
        if number(self.usable_loss_fraction) > 1 or number(self.offset_rate) > 1:
            raise ValueError("scenario_fractions_exceed_one")
        return self


class ExposureLimit(Record):
    level: Literal["security", "sector", "industry"]
    group: Text
    kind: Literal["absolute", "active"]
    maximum: Amount


class CandidateLimits(Record):
    tracking_error: Amount
    max_cost: Amount
    max_orders: Annotated[int, Field(ge=0, le=10000)]
    max_turnover: Amount
    min_order_notional: Amount
    max_order_notional: OptionalLimit
    max_position_weight: Amount
    exposures: tuple[ExposureLimit, ...]
    min_price_loss: OptionalLimit
    max_cost_to_loss: OptionalLimit
    min_scenario_net_value: OptionalLimit
    scenario: TaxScenario | None

    @model_validator(mode="after")
    def controls(self) -> Self:
        if self.min_scenario_net_value.enabled and self.scenario is None:
            raise ValueError("scenario_required_for_value_screen")
        keys = [(v.level, v.group, v.kind) for v in self.exposures]
        if len(set(keys)) != len(keys):
            raise ValueError("duplicate_exposure_limit")
        return self


class CandidateAsset(Record):
    security: Security
    sector: Fact[str]
    industry: Fact[str]


class RiskInput(Record):
    security_ids: tuple[Identifier, ...]
    benchmark_ids: tuple[Identifier, ...]
    benchmark_weights: tuple[float, ...]
    annual_covariance: tuple[tuple[float, ...], ...]
    units: Literal["annualized-simple-return-covariance"]
    annualization_sessions: Annotated[int, Field(ge=1, le=10000)]
    as_of: DateText
    max_age_days: Annotated[int, Field(ge=0, le=36500)]
    reference: Text


class CandidateRequest(Record):
    version: Literal["tiny-candidate-request-v1"] = "tiny-candidate-request-v1"
    method: SearchMethod
    snapshot: ImportSnapshot
    retained_snapshots: tuple[ImportSnapshot, ...]
    history_excluded_ids: tuple[Identifier, ...] = ()
    assets: tuple[CandidateAsset, ...] = Field(min_length=1, max_length=500)
    settings: LotSettings
    risk: RiskInput
    limits: CandidateLimits
    buy_fee_per_security_order: Amount
    buy_premium_bps: Amount
    # Zero bounds are explicit exclusions from the declared search domain.
    sale_bounds: dict[Identifier, Bound] = Field(max_length=2000)
    buy_bounds: dict[Identifier, Bound] = Field(max_length=500)
    max_states: Annotated[int, Field(ge=1, le=100000)]
    max_candidates: Annotated[int, Field(ge=1, le=5)]


class SaleOrder(Record):
    lot_id: Identifier
    shares: Shares


class BuyOrder(Record):
    security_id: Identifier
    shares: Shares


class Orders(Record):
    sales: tuple[SaleOrder, ...] = Field(max_length=2000)
    buys: tuple[BuyOrder, ...] = Field(max_length=500)


class CandidateMetrics(Record):
    price_loss: float
    short_term_loss: float
    long_term_loss: float
    unknown_term_loss: float
    net_proceeds_tax_pnl: float
    modeled_cost: float
    final_cash: float
    final_nav: float
    final_quantities: tuple[float, ...]
    final_weights: tuple[float, ...]
    tracking_error: float
    risk_upper_bound: float
    turnover: float
    order_count: int
    scenario_net_value: float | None


class CandidateCheck(Record):
    orders: Orders
    feasible: bool
    unresolved: bool
    blockers: tuple[Text, ...]
    metrics: CandidateMetrics | None
    warnings: tuple[Text, ...]


class CandidateSearch(Record):
    version: Literal["tiny-candidate-result-v1"] = "tiny-candidate-result-v1"
    inputs: CandidateRequest
    method: SearchMethod
    outcome: Literal[
        "optimal-in-domain",
        "no-feasible-harvest-in-domain",
        "feasible-incumbent",
        "no-candidate",
        "invalid-input",
        "numerical-failure",
    ]
    stopping: Literal[
        "complete",
        "state-limit",
        "cancelled",
        "invalid-input",
        "numerical-failure",
        "proposal-set-exhausted",
    ]
    domain_states: int | None
    evaluated_states: int
    feasible_harvests: int
    unresolved_states: int
    baseline: CandidateCheck
    best: CandidateCheck | None
    candidates: tuple[CandidateCheck, ...] = Field(default=(), max_length=5)
    exclusions: tuple[Text, ...]
    warnings: tuple[Text, ...]
    financial_use_authorized: Literal[False] = False

    @model_validator(mode="after")
    def result_scope(self) -> Self:
        if self.method != self.inputs.method or len(self.candidates) > self.inputs.max_candidates:
            raise ValueError("candidate_method_or_point_count_mismatch")
        if not 0 <= self.unresolved_states <= self.evaluated_states <= self.inputs.max_states:
            raise ValueError("candidate_search_count_mismatch")
        if not 0 <= self.feasible_harvests <= self.evaluated_states:
            raise ValueError("candidate_search_count_mismatch")
        if bool(self.candidates) != (self.best is not None) or (
            self.candidates and self.best != self.candidates[0]
        ):
            raise ValueError("candidate_best_point_mismatch")
        for point in self.candidates:
            if (
                not point.feasible
                or point.unresolved
                or point.metrics is None
                or point.metrics.price_loss <= 0
                or point.blockers
                or len(point.metrics.final_weights) != len(self.inputs.assets)
                or len(point.metrics.final_quantities) != len(self.inputs.assets)
            ):
                raise ValueError("candidate_point_not_checked")
        if self.method == "deterministic-loss-prefix-repair-v1" and (
            self.domain_states is not None
            or self.outcome in ("optimal-in-domain", "no-feasible-harvest-in-domain")
            or self.stopping == "complete"
        ):
            raise ValueError("heuristic_cannot_claim_domain_proof")
        return self
