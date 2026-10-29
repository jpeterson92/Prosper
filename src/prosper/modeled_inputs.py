"""Complete retained-union input diagnostics, without provider or risk acceptance."""

import math
from datetime import UTC, date, datetime
from typing import Annotated, Literal, Self

import polars as pl
from pydantic import ConfigDict, Field, field_validator, model_validator, with_config
from typing_extensions import TypedDict

from prosper.advisory import decimal_value, number, supplied_sum
from prosper.advisory_records import (
    DecimalFact,
    Digest,
    Fact,
    Finding,
    ImportSnapshot,
    Lot,
    Position,
    Record,
)
from prosper.benchmark import BenchmarkResult
from prosper.benchmark_drift import weights_at
from prosper.history import Alignment, HistoryRequest, Profile
from prosper.lot_records import LotSettings, Mark
from prosper.modeled_sleeve import ModeledSleeve, excludable, history_codes
from prosper.record_types import DateText, Identifier, Text, Timestamp


class SourceFact(Record):
    source_sha256: Digest
    source_ref: Text
    provider: Text
    dataset: Text
    permission_scope: Text
    effective: DateText
    valid_through: DateText
    recorded_at: Timestamp

    @model_validator(mode="after")
    def window(self) -> Self:
        if self.effective > self.valid_through:
            raise ValueError("invalid_source_fact_window")
        return self


class SecurityInput(Record):
    security_id: Identifier
    identity: Fact[str]
    classification: Fact[str]
    currency: Text
    evidence: SourceFact


class MarkInput(Record):
    mark: Mark
    evidence: SourceFact


class ClassificationInput(Record):
    security_id: Identifier
    sector: Fact[str]
    industry: Fact[str]
    evidence: SourceFact


@with_config(ConfigDict(extra="forbid", strict=True))
class RiskOverrides(TypedDict, total=False):
    """Explicit expert choices; the fit boundary still enforces supported R1 settings."""

    model: Profile
    lookback_sessions: Annotated[int, Field(ge=1, le=10000)]
    minimum_history_sessions: Annotated[int, Field(ge=1, le=10000)]
    horizon_sessions: Annotated[int, Field(ge=1, le=10000)]
    annualization_sessions: Annotated[int, Field(ge=1, le=10000)]
    require_full_window_validation: bool


class RiskEstimatorSettings(Record):
    model: Profile | None = Field(
        default_factory=lambda: Profile(identity="R1", f="0.25", a3="0.17", kappa="10000")
    )
    lookback_sessions: Annotated[int, Field(ge=1, le=10000)] = 1260
    minimum_history_sessions: Annotated[int, Field(ge=1, le=10000)] = 1260
    horizon_sessions: Annotated[int, Field(ge=1, le=10000)] = 21
    annualization_sessions: Annotated[int, Field(ge=1, le=10000)] = 252
    require_full_window_validation: bool = True


def standard_risk_settings() -> dict[str, object]:
    settings = RiskEstimatorSettings()
    return {key: getattr(settings, key) for key in RiskEstimatorSettings.model_fields}


class RiskPreset(Record):
    identity: Literal["standard-r1-v1"] = "standard-r1-v1"
    overrides: RiskOverrides = Field(default_factory=lambda: RiskOverrides())


class InputCoverageSettings(Record):
    max_mark_age_days: Annotated[int, Field(ge=0, le=36500)]
    max_snapshot_age_days: Annotated[int, Field(ge=0, le=36500)]
    max_benchmark_age_days: Annotated[int, Field(ge=0, le=36500)]
    max_history_age_days: Annotated[int, Field(ge=0, le=36500)]
    maximum_universe_size: Annotated[int, Field(ge=1, le=5000)]
    short_history_policy: Literal["block"]


class InputProfile(RiskEstimatorSettings, InputCoverageSettings):
    preset: RiskPreset | None = None
    variant: Literal["idr-dcc-nl"] = "idr-dcc-nl"
    model_reference: Text = "Standard R1 v1; exploratory IDR-DCC-NL; unqualified"

    @model_validator(mode="after")
    def preset_matches(self) -> Self:
        if self.preset is not None:
            expected = standard_risk_settings()
            expected.update(self.preset.overrides)
            if any(getattr(self, key) != value for key, value in expected.items()):
                raise ValueError("risk_preset_effective_settings_mismatch")
        return self


LimitName = Literal[
    "tracking_error",
    "max_orders",
    "turnover",
    "min_trade_notional",
    "max_trade_notional",
    "max_position_weight",
    "sector_exposure",
    "industry_exposure",
]
LIMIT_NAMES = (
    "tracking_error",
    "max_orders",
    "turnover",
    "min_trade_notional",
    "max_trade_notional",
    "max_position_weight",
    "sector_exposure",
    "industry_exposure",
)


class InvestorControl(Record):
    name: LimitName
    enabled: bool
    value: DecimalFact
    unit: Literal["decimal-weight", "USD", "orders", "annualized-decimal-volatility"]
    reference: Text
    group: Text | None = None
    kind: Literal["absolute", "active"] | None = None

    @model_validator(mode="after")
    def disabled(self) -> Self:
        if not self.enabled and self.value.value is not None:
            raise ValueError("disabled_control_cannot_supply_value")
        return self


class InputAssemblyBinding(Record):
    input_revision: Annotated[int, Field(ge=0, lt=2**63 - 1)]
    snapshot_id: Digest
    benchmark_run_id: Identifier
    history_batch_ids: tuple[Digest, ...] = Field(min_length=1, max_length=500)
    fact_run_id: Identifier | None
    source_declarations: tuple[SourceFact, ...]
    prepared_at: Timestamp

    @model_validator(mode="after")
    def source_keys(self) -> Self:
        if len(set(self.history_batch_ids)) != len(self.history_batch_ids) or len(
            {s.source_sha256 for s in self.source_declarations}
        ) != len(self.source_declarations):
            raise ValueError("duplicate_assembly_source")
        return self


class ModeledBundle(Record):
    version: Literal["modeled-inputs-v1"] = "modeled-inputs-v1"
    analysis_date: DateText
    candidate_security_ids: tuple[Identifier, ...]
    securities: tuple[SecurityInput, ...]
    marks: tuple[MarkInput, ...]
    taxonomy_name: Text
    taxonomy_version: Text
    classifications: tuple[ClassificationInput, ...]
    history: HistoryRequest
    profile: InputProfile
    investor_controls: tuple[InvestorControl, ...]
    assembly: InputAssemblyBinding | None = None

    @model_validator(mode="after")
    def cardinality(self) -> Self:
        groups = (
            self.candidate_security_ids,
            tuple(s.security_id for s in self.securities),
            tuple(m.mark.security_id for m in self.marks),
            tuple(c.security_id for c in self.classifications),
            tuple(c.name for c in self.investor_controls),
        )
        if any(len(set(group)) != len(group) for group in groups):
            raise ValueError("duplicate_modeled_input_key")
        return self


class InputSource(Record):
    sha256: Digest
    source_base64: str = Field(max_length=2800000, repr=False)


class ModeledUpload(Record):
    bundle: ModeledBundle
    sources: tuple[InputSource, ...]

    @field_validator("bundle", "sources", mode="before")
    @classmethod
    def json_fields(cls, value: object, info: object) -> object:
        import json

        from pydantic import TypeAdapter

        # No scalar coercion; HTTP arrays use JSON collection semantics.
        if isinstance(value, (dict, list)):
            name = getattr(info, "field_name", None)
            if name == "bundle":
                return ModeledBundle.model_validate_json(json.dumps(value, allow_nan=False))
            return TypeAdapter(tuple[InputSource, ...]).validate_json(
                json.dumps(value), strict=True
            )
        return value


class ModeledDiagnostic(ModeledUpload):
    run_id: Identifier
    expected_revision: Annotated[int, Field(ge=0, lt=2**63 - 1)]
    as_of: Timestamp


class RiskPresetRequest(Record):
    upload: ModeledUpload
    overrides: RiskOverrides = Field(default_factory=lambda: RiskOverrides())


def prepare_risk_preset(request: RiskPresetRequest) -> ModeledUpload:
    """Materialize estimator settings only; never create sessions, sources or limits."""
    bundle = request.upload.bundle
    if bundle.history.profile is not None and bundle.history.profile != bundle.profile.model:
        raise ValueError("model_profile_missing_or_mismatch")
    selection = RiskPreset(overrides=request.overrides)
    settings = standard_risk_settings()
    settings.update(request.overrides)
    profile = InputProfile.model_validate(
        {
            **{key: getattr(bundle.profile, key) for key in InputProfile.model_fields},
            **settings,
            "preset": selection,
            "model_reference": "Standard R1 v1; exploratory IDR-DCC-NL; unqualified",
        }
    )
    return request.upload.model_copy(
        update={
            "bundle": bundle.model_copy(
                update={
                    "profile": profile,
                    "history": bundle.history.model_copy(update={"profile": profile.model}),
                }
            )
        }
    )


IssueScope = Literal[
    "universe",
    "identity",
    "marks",
    "history",
    "taxonomy",
    "profile",
    "settings",
    "source",
    "benchmark",
]


class InputIssue(Record):
    scope: IssueScope
    security_id: Identifier | None = None
    locator: Text
    code: Text
    reason: Text


class Member(Record):
    security_id: Identifier
    roles: tuple[Literal["held", "benchmark", "candidate"], ...]
    locators: tuple[Text, ...]
    held_quantity: float | None
    benchmark_weight: float | None
    mark: float | None
    sector: str | None
    industry: str | None


class ModeledResult(Record):
    kind: Literal["modeled-inputs-v1"] = "modeled-inputs-v1"
    input_revision: Annotated[int, Field(ge=0, lt=2**63 - 1)]
    members: tuple[Member, ...]
    security_ids: tuple[Identifier, ...]
    sessions: tuple[DateText, ...]
    return_cell_count: Annotated[int, Field(ge=0)]
    unavailable_return_count: Annotated[int, Field(ge=0)]
    exclusions: tuple[Finding, ...]
    sleeve: ModeledSleeve | None = None
    issues: tuple[InputIssue, ...]
    required_sources: tuple[Digest, ...]
    software_inputs_complete: bool
    innovation_inputs_available: bool
    risk_available: Literal[False] = False
    financial_use_authorized: Literal[False] = False
    warnings: tuple[Text, ...] = (
        "Unqualified supplied-input diagnostics; "
        "no provider, investor profile or financial acceptance",
        "Complete input coverage does not establish calibrated risk or validated suggestions",
        "Excluded holdings and untouched account cash are outside the modeled sleeve",
    )

    @model_validator(mode="after")
    def dimensions(self) -> Self:
        if self.security_ids != tuple(m.security_id for m in self.members):
            raise ValueError("input_member_order_mismatch")
        if (
            self.return_cell_count != len(self.sessions) * len(self.members)
            or self.unavailable_return_count > self.return_cell_count
        ):
            raise ValueError("input_grid_dimensions_mismatch")
        if self.software_inputs_complete != (not self.issues):
            raise ValueError("input_status_mismatch")
        return self


class FrozenModeledInputs(Record):
    bundle: ModeledBundle
    benchmark: BenchmarkResult | None
    benchmark_run_id: Identifier | None
    lot_settings: LotSettings | None
    alignment: Alignment | None
    source_alignment: Alignment | None
    sleeve: ModeledSleeve
    available_sources: tuple[Digest, ...]
    retained_sources: tuple[Digest, ...]
    benchmark_sources: tuple[Digest, ...]

    @model_validator(mode="after")
    def sleeve_links(self) -> Self:
        decisions = self.sleeve.decisions
        if self.sleeve.excluded_ids and any(
            e.source_sha256 not in self.available_sources for e in self.sleeve.history_evidence
        ):
            raise ValueError("history_exclusion_evidence_unavailable")
        original_ids = tuple(d.security_id for d in decisions)
        if original_ids != tuple(sorted(set(original_ids))):
            raise ValueError("history_sleeve_decision_order_invalid")
        if self.source_alignment:
            original = self.source_alignment
            if original.request != history_request(self.bundle, original_ids):
                raise ValueError("history_sleeve_source_request_mismatch")
            codes_by_id = history_codes(original, self.sleeve.history_evidence)
            for decision in decisions:
                codes = codes_by_id.get(decision.security_id, ())
                if decision.issue_codes != codes or decision.excluded and not excludable(codes):
                    raise ValueError("history_sleeve_reason_mismatch")
        elif any(d.excluded or d.issue_codes for d in decisions):
            raise ValueError("history_sleeve_source_alignment_required")
        if self.alignment:
            retained = self.sleeve.retained_ids
            if self.source_alignment is None or self.alignment.request != history_request(
                self.bundle, retained
            ):
                raise ValueError("history_sleeve_retained_request_mismatch")
            expected = self.source_alignment.rows.frame.filter(
                pl.col("security_id").is_in(retained)
            )
            if not self.alignment.rows.frame.equals(expected):
                raise ValueError("history_sleeve_projection_mismatch")
        elif self.source_alignment and self.sleeve.retained_ids:
            raise ValueError("history_sleeve_projection_missing")
        return self


def union(
    snapshot: ImportSnapshot,
    benchmark: BenchmarkResult | None,
    bundle: ModeledBundle,
    excluded_ids: frozenset[str] = frozenset(),
) -> tuple[tuple[str, ...], dict[str, list[str]], tuple[Finding, ...]]:
    """Keep unknown/zero/fractional held names; exclude only explicit known classes."""
    securities = {s.id: s for s in snapshot.securities}
    roles: dict[str, list[str]] = {}
    exclusions = list(snapshot.exclusions)
    rows: list[Lot | Position] = [*snapshot.lots, *snapshot.positions]
    for row in rows:
        security = securities[row.security_id]
        if row.security_id in snapshot.excluded_stock_ids:
            exclusions.append(
                Finding(
                    code="holding_mapping_excluded",
                    locator=row.source_ref,
                    reason=(
                        "Explicit holdings mapping exclusion; "
                        "original facts and restrictions retained"
                    ),
                )
            )
        elif row.security_id in snapshot.cash_security_ids:
            exclusions.append(
                Finding(
                    code="user_cash_treatment",
                    locator=row.source_ref,
                    reason=f"{row.security_id}: user cash treatment; no modeled funding",
                )
            )
        elif security.classification.value not in (None, "us-domestic-common-equity"):
            exclusions.append(
                Finding(
                    code="excluded_held_class",
                    locator=row.source_ref,
                    reason=f"{row.security_id}: {security.classification.value}",
                )
            )
        else:
            roles.setdefault(row.security_id, []).append("held")
    if benchmark:
        for sid in benchmark.security_ids:
            roles.setdefault(sid, []).append("benchmark")
    for sid in bundle.candidate_security_ids:
        if sid not in snapshot.cash_security_ids | snapshot.excluded_stock_ids:
            roles.setdefault(sid, []).append("candidate")
    for sid in excluded_ids:
        roles.pop(sid, None)
    return tuple(sorted(roles)), roles, tuple(exclusions)


def history_request(bundle: ModeledBundle, ids: tuple[str, ...]) -> HistoryRequest | None:
    by_id = {c.security_id: c for c in bundle.history.series}
    series = tuple(by_id[sid] for sid in ids if sid in by_id)
    if not series:
        return None
    return bundle.history.model_copy(
        update={
            "series": series,
            "manual_security_ids": tuple(
                sid for sid in bundle.history.manual_security_ids if sid in ids
            ),
        }
    )


def evaluate(
    snapshot: ImportSnapshot,
    benchmark: BenchmarkResult | None,
    settings: LotSettings | None,
    bundle: ModeledBundle,
    alignment: Alignment | None,
    as_of: str,
    available_sources: frozenset[str],
    benchmark_sources: tuple[str, ...] = (),
    input_revision: int = 0,
    sleeve: ModeledSleeve | None = None,
) -> ModeledResult:
    ids, roles, exclusions = union(
        snapshot, benchmark, bundle, sleeve.excluded_ids if sleeve else frozenset()
    )
    if sleeve:
        exclusions += tuple(
            Finding(
                code="history_excluded",
                locator=f"history/{d.security_id}",
                reason="; ".join(d.issue_codes),
            )
            for d in sleeve.decisions
            if d.excluded
        )
    issues: list[InputIssue] = []
    used: set[str] = {snapshot.source_sha256}
    used.update(benchmark_sources)

    def issue(
        scope: IssueScope, code: str, locator: str, reason: str, sid: str | None = None
    ) -> None:
        issues.append(
            InputIssue(scope=scope, code=code, locator=locator, reason=reason, security_id=sid)
        )

    def fact(source: SourceFact, scope: IssueScope, sid: str) -> None:
        used.add(source.source_sha256)
        if source.source_sha256 not in available_sources:
            issue(
                "source",
                "source_unavailable",
                source.source_ref,
                "Required original source is unavailable",
                sid,
            )
        if not source.effective <= bundle.analysis_date <= source.valid_through:
            issue(
                scope,
                "source_date_outside_window",
                source.source_ref,
                "Source assertion does not cover analysis date",
                sid,
            )
        if datetime.fromisoformat(source.recorded_at) > datetime.fromisoformat(as_of):
            issue(
                scope,
                "future_source_knowledge",
                source.source_ref,
                "Source assertion was recorded after analysis",
                sid,
            )

    def stale(day: str, maximum: int) -> bool:
        delta = (date.fromisoformat(bundle.analysis_date) - date.fromisoformat(day[:10])).days
        return delta < 0 or delta > maximum

    for digest in ({snapshot.source_sha256} | set(benchmark_sources)) - available_sources:
        issue(
            "source",
            "selected_source_unavailable",
            digest,
            "Original selected snapshot or benchmark source is unavailable",
        )

    if bundle.analysis_date > datetime.fromisoformat(as_of).astimezone(UTC).date().isoformat():
        issue(
            "profile",
            "future_analysis_date",
            "analysis_date",
            "Analysis date follows saved knowledge time",
        )
    if not ids:
        issue(
            "universe",
            "empty_modeled_union",
            "universe",
            "At least one retained security is required",
        )
    if benchmark is None:
        issue(
            "benchmark",
            "selected_benchmark_required",
            "settings/benchmark_run_id",
            "Select a reviewed benchmark explicitly",
        )
    elif benchmark.status != "estimated-equity-benchmark":
        issue(
            "benchmark",
            "selected_benchmark_incomplete",
            "settings/benchmark_run_id",
            "Selected benchmark cannot supply a complete retained universe and weights",
        )
    elif stale(benchmark.effective_date, bundle.profile.max_benchmark_age_days):
        issue(
            "benchmark",
            "stale_benchmark",
            "benchmark/effective_date",
            "Benchmark exceeds supplied age or is future dated",
        )
    if stale(snapshot.source_as_of, bundle.profile.max_snapshot_age_days):
        issue(
            "profile",
            "stale_snapshot",
            "snapshot/source_as_of",
            "Snapshot exceeds supplied age or is future dated",
        )
    if len(ids) > bundle.profile.maximum_universe_size:
        issue(
            "profile",
            "universe_capacity_exceeded",
            "profile/maximum_universe_size",
            "Full union retained; supplied capacity is exceeded",
        )
    if (
        len(bundle.history.sessions) != bundle.profile.lookback_sessions
        or len(bundle.history.sessions) < bundle.profile.minimum_history_sessions
    ):
        issue(
            "profile",
            "history_length_mismatch",
            "profile/lookback_sessions",
            "Required sessions must match explicit lookback and minimum history",
        )
    if stale(bundle.history.cutoff, bundle.profile.max_history_age_days):
        issue(
            "history",
            "stale_history_cutoff",
            "history/cutoff",
            "History cutoff exceeds supplied age or is future dated",
        )
    if bundle.profile.model is None or bundle.history.profile != bundle.profile.model:
        issue(
            "profile",
            "model_profile_missing_or_mismatch",
            "profile/model",
            "Use one explicit matching IDR profile",
        )
    if datetime.fromisoformat(bundle.history.known_at) > datetime.fromisoformat(as_of):
        issue(
            "history",
            "history_knowledge_after_analysis",
            "history/known_at",
            "History knowledge follows saved analysis",
        )
    if settings is None:
        issue(
            "settings",
            "lot_settings_required",
            "settings/lot_opportunities",
            "Explicit costs, funding and cash settings are required",
        )
    else:
        if settings.analysis_date != bundle.analysis_date:
            issue(
                "settings",
                "settings_date_mismatch",
                "settings/analysis_date",
                "Lot settings and input analysis dates differ",
            )
        if not settings.cash_budget_reviewed or settings.funding_assumption.value is None:
            issue(
                "settings",
                "funding_or_cash_unreviewed",
                "settings/funding",
                "Reviewed selected cash and funding assumptions are required",
            )
        if (
            settings.sell_fee_per_isolated_order.value is None
            or settings.sell_discount_bps.value is None
        ):
            issue(
                "settings", "costs_unknown", "settings/costs", "Explicit selling costs are required"
            )
    controls: dict[str, InvestorControl] = {c.name: c for c in bundle.investor_controls}
    units = {
        "tracking_error": "annualized-decimal-volatility",
        "max_orders": "orders",
        "min_trade_notional": "USD",
        "max_trade_notional": "USD",
    }
    for name in LIMIT_NAMES:
        control = controls.get(name)
        if control is None or (control.enabled and control.value.value is None):
            issue(
                "settings",
                "investor_control_unspecified",
                f"controls/{name}",
                "Supply enabled value or explicitly disable this control",
            )
        elif control.unit != units.get(name, "decimal-weight"):
            issue(
                "settings",
                "investor_control_unit_mismatch",
                f"controls/{name}",
                "Control units must match its declared meaning",
            )
        elif (
            control.enabled
            and name == "max_orders"
            and (
                decimal_value(control.value.value or "0")
                != decimal_value(control.value.value or "0").to_integral_value()
            )
        ):
            issue(
                "settings",
                "integer_order_limit_required",
                f"controls/{name}",
                "Order count must be an integer",
            )
        elif (
            control.enabled
            and name in ("sector_exposure", "industry_exposure")
            and (control.group is None or control.kind is None)
        ):
            issue(
                "settings",
                "exposure_group_unspecified",
                f"controls/{name}",
                "Enabled exposure limit needs its explicit group and absolute/active meaning",
            )
    securities = {s.security_id: s for s in bundle.securities}
    marks = {m.mark.security_id: m for m in bundle.marks}
    taxonomy = {c.security_id: c for c in bundle.classifications}
    holdings = {s.id: s for s in snapshot.securities}
    contexts = {c.security_id: c for c in bundle.history.series}
    quantities: dict[str, float | None] = {}
    all_holdings: list[Lot | Position] = [*snapshot.lots, *snapshot.positions]

    def quantity_number(value: str | None) -> float | None:
        try:
            return number(value) if value is not None else None
        except ValueError:
            return None

    def grouped_supplied(
        rows: tuple[Lot, ...] | tuple[Position, ...],
    ) -> dict[str, list[str | None]]:
        frame = pl.DataFrame(
            {
                "security_id": [row.security_id for row in rows],
                "quantity": [row.quantity.value for row in rows],
            },
            schema={"security_id": pl.String, "quantity": pl.String},
        )
        return {
            sid: values
            for sid, values in frame.group_by("security_id").agg(pl.col("quantity")).iter_rows()
        }

    lots_by_id, positions_by_id = (
        grouped_supplied(snapshot.lots),
        grouped_supplied(snapshot.positions),
    )
    for sid in set(lots_by_id) & set(positions_by_id) & set(ids):
        lots, positions = lots_by_id[sid], positions_by_id[sid]
        if any(value is None for value in (*lots, *positions)):
            issue(
                "universe",
                "position_reconciliation_unknown",
                "holdings/positions",
                "Supplied lot/independent position quantities cannot be reconciled",
                sid,
            )
        elif supplied_sum(tuple(v for v in lots if v is not None)) != supplied_sum(
            tuple(v for v in positions if v is not None)
        ):
            issue(
                "universe",
                "position_quantity_conflict",
                "holdings/positions",
                "Supplied independent position differs from supplied lot quantity",
                sid,
            )
    raw_rows = [row for row in snapshot.lots] + [
        row
        for row in snapshot.positions
        if row.security_id not in {lot.security_id for lot in snapshot.lots}
    ]
    if raw_rows:
        frame = pl.DataFrame(
            {
                "security_id": [r.security_id for r in raw_rows],
                "quantity": [quantity_number(r.quantity.value) for r in raw_rows],
            },
            schema={"security_id": pl.String, "quantity": pl.Float64},
        )
        grouped = frame.group_by("security_id").agg(
            pl.col("quantity").sum(), pl.col("quantity").null_count().alias("unknown")
        )
        quantities = {
            sid: None if unknown or not math.isfinite(qty) else qty
            for sid, qty, unknown in grouped.iter_rows()
        }
    estimated_weights = weights_at(
        benchmark,
        alignment,
        bundle.analysis_date,
        retained_ids=tuple(s for s in benchmark.security_ids if s in ids)
        if benchmark and sleeve
        else None,
    )
    for weight_issue in estimated_weights.issues:
        issue(
            "benchmark",
            weight_issue.code,
            weight_issue.locator,
            weight_issue.reason,
            weight_issue.security_id,
        )
    weights = estimated_weights.weights
    hierarchy: dict[str, str] = {}
    members = []
    for sid in ids:
        identity = securities.get(sid)
        if identity is None:
            issue(
                "identity",
                "security_mapping_missing",
                "securities",
                "Reviewed security mapping is required",
                sid,
            )
        else:
            fact(identity.evidence, "identity", sid)
            if (
                identity.identity.value is None
                or identity.classification.value != "us-domestic-common-equity"
                or identity.currency != "USD"
            ):
                issue(
                    "identity",
                    "unsupported_or_unknown_security",
                    identity.evidence.source_ref,
                    "Supported mapped USD ordinary equity required",
                    sid,
                )
            held = holdings.get(sid)
            if held:
                if held.identity.value is None or held.identity.value != identity.identity.value:
                    issue(
                        "identity",
                        "held_identity_unresolved_or_conflicting",
                        held.source_ref,
                        "Held identity must match reviewed canonical mapping",
                        sid,
                    )
                if held.classification.value not in (None, identity.classification.value):
                    issue(
                        "identity",
                        "held_classification_conflict",
                        held.source_ref,
                        "Held and reviewed classifications disagree",
                        sid,
                    )
        if "held" in roles[sid] and quantities.get(sid) is None:
            issue(
                "universe",
                "held_quantity_unknown",
                "holdings",
                "Required held quantity is unknown",
                sid,
            )
        marked = marks.get(sid)
        price = None
        if marked is None:
            issue(
                "marks",
                "mark_missing",
                "marks",
                "Reference mark required for every retained name",
                sid,
            )
        else:
            fact(marked.evidence, "marks", sid)
            mark = marked.mark
            price = float(mark.price.value) if mark.price.value is not None else None
            if price is None or not math.isfinite(price) or price <= 0 or mark.day.value is None:
                issue(
                    "marks",
                    "mark_unknown_or_invalid",
                    mark.source_ref,
                    "Positive finite mark and actual mark date required",
                    sid,
                )
                price = None
            elif stale(mark.day.value, bundle.profile.max_mark_age_days):
                issue(
                    "marks",
                    "mark_stale_or_future",
                    mark.source_ref,
                    "Mark exceeds supplied age or is future dated",
                    sid,
                )
            if identity is None or mark.identity != identity.identity.value:
                issue(
                    "marks",
                    "mark_identity_mismatch",
                    mark.source_ref,
                    "Mark identity does not match reviewed security",
                    sid,
                )
            if settings:
                old = next((m for m in settings.marks if m.security_id == sid), None)
                if old is not None and old != mark:
                    issue(
                        "marks",
                        "lot_mark_conflict",
                        mark.source_ref,
                        "Lot and modeled-input marks disagree; review new settings explicitly",
                        sid,
                    )
        classified = taxonomy.get(sid)
        sector, industry = None, None
        if classified is None:
            issue(
                "taxonomy",
                "classification_missing",
                "classifications",
                "Attributable sector/industry mapping required",
                sid,
            )
        else:
            fact(classified.evidence, "taxonomy", sid)
            sector, industry = classified.sector.value, classified.industry.value
            if sector is None or industry is None:
                issue(
                    "taxonomy",
                    "classification_unknown",
                    classified.evidence.source_ref,
                    "Unknown groups cannot become zero exposure",
                    sid,
                )
            elif industry in hierarchy and hierarchy[industry] != sector:
                issue(
                    "taxonomy",
                    "hierarchy_conflict",
                    classified.evidence.source_ref,
                    "One industry maps to contradictory sectors",
                    sid,
                )
            else:
                hierarchy[industry or ""] = sector or ""
        context = contexts.get(sid)
        if context is None:
            issue(
                "history",
                "series_context_missing",
                "history/series",
                "Complete union requires this name's history context",
                sid,
            )
        members.append(
            Member(
                security_id=sid,
                roles=tuple(
                    role for role in ("held", "benchmark", "candidate") if role in roles[sid]
                ),
                locators=tuple(row.source_ref for row in all_holdings if row.security_id == sid),
                held_quantity=quantities.get(sid) if "held" in roles[sid] else 0.0,
                benchmark_weight=weights.get(sid, 0.0) if weights is not None else None,
                mark=price,
                sector=sector,
                industry=industry,
            )
        )
    by_cell = (
        {
            (day, sid): value
            for day, sid, value in alignment.rows.frame.select(
                "session", "security_id", "total_return"
            ).iter_rows()
        }
        if alignment
        else {}
    )
    if alignment:
        used.update(alignment.required_sources)
        for digest in set(alignment.required_sources) - available_sources:
            issue(
                "source",
                "source_unavailable",
                digest,
                "History review evidence is unavailable or corrupt",
            )
        for error in alignment.issues:
            issue(
                "history",
                error.code,
                f"history/{error.session or 'window'}",
                error.reason,
                error.security_id,
            )
        if bundle.profile.require_full_window_validation:
            for sid in ids:
                if sid not in alignment.validated_at:
                    issue(
                        "history",
                        "full_window_validation_missing",
                        "history/validated_at",
                        "Required full-window validation is absent",
                        sid,
                    )
    for sid in ids:
        if alignment is None or any(
            (day, sid) not in by_cell or by_cell[day, sid] is None
            for day in bundle.history.sessions
        ):
            issue(
                "history",
                "required_history_incomplete",
                "history/grid",
                "Required sessions are missing or unusable",
                sid,
            )
    unavailable_count = sum(
        by_cell.get((day, sid)) is None for day in bundle.history.sessions for sid in ids
    )
    from prosper.risk_inputs import conventions_available

    innovation_ready = bool(
        alignment
        and tuple(c.security_id for c in alignment.request.series) == ids
        and conventions_available(alignment)
    )
    if not innovation_ready:
        issue(
            "history",
            "idr_conventions_unqualified",
            "history/conventions",
            "Complete compatible total-return/OHLC inputs and explicit profile required; "
            "no model fallback",
        )
    return ModeledResult(
        input_revision=input_revision,
        members=tuple(members),
        security_ids=ids,
        sessions=bundle.history.sessions,
        return_cell_count=len(bundle.history.sessions) * len(ids),
        unavailable_return_count=unavailable_count,
        exclusions=exclusions,
        sleeve=sleeve,
        issues=tuple(issues),
        required_sources=tuple(sorted(used)),
        software_inputs_complete=not issues,
        innovation_inputs_available=innovation_ready
        and not any(i.scope in ("history", "profile") for i in issues),
        warnings=ModeledResult.model_fields["warnings"].default
        + ((estimated_weights.warning,) if estimated_weights.warning else ())
        + (sleeve.warnings if sleeve else ()),
    )
