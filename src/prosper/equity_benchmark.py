"""Explicit D045 fictional equity selection; no real identity resolver/activation.

Original full-response evidence and published observations remain separate from
derived exact value weights. No source section or ticker implies eligibility.
"""

import hashlib
import math
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import Literal

import polars as pl

from prosper import advisory
from prosper import basket as b
from prosper import benchmark_reconciliation as r
from prosper import benchmark_tables as t
from prosper import vanguard as v
from prosper.innovations import fingerprint

VERSION = "synthetic-equity-benchmark-v1"
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class ValueField:
    section: str
    field: str
    currency: str


@dataclass(frozen=True)
class Decision:
    locator: r.Locator
    action: Literal["include", "exclude"]
    reason: str


@dataclass(frozen=True)
class Policy:
    values: tuple[ValueField, ...]
    decisions: tuple[Decision, ...]
    version: str = VERSION


@dataclass(frozen=True)
class Row:
    locator: r.Locator
    row_sha256: str
    role: str
    disposition: str
    reason: str | None
    security_id: str | None
    target: r.Locator | None
    raw_value: str | None
    value_token_kind: str
    value: str | None
    value_currency: str
    raw_percentage: str | None
    percentage_token_kind: str
    published_weight: str | None
    derived_weight: str | None
    issues: tuple[str, ...]


@dataclass(frozen=True)
class Result:
    acquisition: v.Acquisition
    stipulation: r.Stipulation
    policy: Policy
    status: str
    issues: tuple[b.Issue, ...]
    ledger: tuple[Row, ...]
    retained_known_value: str
    retained_unknown_values: tuple[r.Locator, ...]
    excluded_known_usd_value: str
    excluded_unknown_usd_values: tuple[r.Locator, ...]
    equity_value_total: str | None
    benchmark_rows: tuple[b.BenchmarkRow, ...] | None
    input_sha256: str
    canonical_sha256: str
    identity_sha256: str

    @property
    def benchmark_ready(self) -> Literal[False]:
        return False


@dataclass(frozen=True)
class Bridge:
    selection: Result
    portfolio: r.PortfolioContext
    basket: b.BasketResult

    @property
    def benchmark_ready(self) -> Literal[False]:
        return False


def _kind(value: v.JsonValue) -> str:
    return (
        "number"
        if isinstance(value, v.JsonNumber)
        else "string"
        if isinstance(value, str)
        else "null"
        if value is None
        else "other"
    )


def _validate(policy: Policy, stipulation: r.Stipulation) -> None:
    r._validate_rules(stipulation)
    if (
        policy.version != VERSION
        or type(policy.values) is not tuple
        or type(policy.decisions) is not tuple
        or len(policy.values) > v.MAX_ROWS
        or len(policy.decisions) > v.MAX_ROWS
        or len({f.section for f in policy.values}) != len(policy.values)
        or len({d.locator for d in policy.decisions}) != len(policy.decisions)
    ):
        raise r.ReconciliationUnavailable("bounded unique versioned equity policy required")
    for value in policy.values:
        if not r._text(value.section) or not r._text(value.field) or value.currency != "USD":
            raise r.ReconciliationUnavailable("explicit source value field and USD unit required")
    for decision in policy.decisions:
        if (
            not r._text(decision.locator.section)
            or type(decision.locator.index) is not int
            or decision.locator.index < 0
            or decision.action not in ("include", "exclude")
            or not r._text(decision.reason)
        ):
            raise r.ReconciliationUnavailable("located explicit equity decision/reason required")


def _select(
    acquisition: v.Acquisition,
    stipulation: r.Stipulation,
    policy: Policy,
    *,
    estimates: bool = False,
) -> Result:
    """Reprove the full source, then apply explicit synthetic row dispositions."""
    _validate(policy, stipulation)

    def parse(raw: v.JsonValue, unit: str) -> Fraction | float | None:
        if not estimates:
            return r._number(raw, unit)
        if not isinstance(raw, str) or unit not in ("decimal", "percent"):
            return None
        try:
            value = advisory.number(raw, signed=True)
            return value / (100 if unit == "percent" else 1)
        except ValueError:
            return None

    def numeric(text: str) -> Fraction | float:
        return float(text) if estimates else Fraction(text)

    issues: list[b.Issue] = []
    ledger: list[Row] = []
    source, response = acquisition.snapshot, acquisition.response
    source_ok = source is not None and response is not None
    if response is not None:
        replay = v.acquire(
            acquisition.selection,
            collected_at=acquisition.collected_at,
            transport=lambda _: response,
        )
        if r.encoded(replay) != r.encoded(acquisition):
            source_ok = False
            issues.append(b.Issue("acquisition", "snapshot_replay_mismatch"))
    if not source_ok:
        issues.append(b.Issue("acquisition", "snapshot_unavailable", acquisition.issues))
    primary: list[Row] = []
    included: list[b.Security] = []
    known_in: Fraction | float = 0.0 if estimates else Fraction()
    known_out: Fraction | float = 0.0 if estimates else Fraction()
    unknown_in: list[r.Locator] = []
    unknown_out: list[r.Locator] = []
    if source_ok and source is not None:
        effective, known = source.effective_date.isoformat(), source.collected_at.date().isoformat()
        expected = (
            source.raw_sha256,
            source.selection.fund,
            source.selection.effective_date.isoformat()
            if source.selection.effective_date
            else None,
            effective,
            source.collected_at.isoformat(),
        )
        actual = (
            stipulation.raw_sha256,
            stipulation.fund,
            stipulation.requested_date,
            stipulation.effective_date,
            stipulation.collected_at,
        )
        if actual != expected:
            issues.append(b.Issue("stipulation", "source_context_mismatch"))
        if stipulation.fund_assertion.source_sha256 == source.raw_sha256 or not r._evidence(
            stipulation.fund_assertion, effective, known
        ):
            issues.append(b.Issue("fund", "independent_stipulated_fund_assertion_required"))
        cash = stipulation.benchmark_cash
        if (
            cash.unknown_reasons
            or parse(cash.raw, stipulation.benchmark_cash_unit) != 0
            or not r._evidence(cash.evidence, effective, known)
        ):
            issues.append(b.Issue("benchmark_cash", "explicit_zero_benchmark_cash_required"))
        holdings = source.document.get(effective)
        assert isinstance(holdings, v.JsonObject)
        matches = t.bind(
            tuple(name for name, _ in holdings.fields),
            tuple(
                (name, index)
                for name, rows in holdings.fields
                if isinstance(rows, tuple)
                for index in range(len(rows))
            ),
            tuple(rule.section for rule in stipulation.sections),
            tuple((rule.locator.section, rule.locator.index) for rule in stipulation.rows),
            tuple(field.section for field in policy.values),
            tuple(
                (decision.locator.section, decision.locator.index) for decision in policy.decisions
            ),
        )
        source_ordinal = 0
        for section_index, (name, raw_rows) in enumerate(holdings.fields):
            rule_index, value_index = matches.sections[section_index], matches.values[section_index]
            rule = stipulation.sections[rule_index] if rule_index is not None else None
            value_field = policy.values[value_index] if value_index is not None else None
            role = rule.role if rule else "unresolved"
            sec_issues: list[str] = []
            if rule is None or role == "unresolved":
                sec_issues.append("section_relationship_unresolved")
            elif not r._evidence(rule.evidence, effective, known):
                sec_issues.append("section_evidence_stale_or_unknown")
            if not isinstance(raw_rows, tuple):
                sec_issues.append("non_array_section_retained")
                raw_rows = ()
            if role == "empty" and raw_rows:
                sec_issues.append("nonempty_section_declared_empty")
            if raw_rows and value_field is None:
                sec_issues.append("explicit_value_field_required")
            if role == "primary" and value_field is not None and value_field.field != "marketValue":
                sec_issues.append("primary_market_value_field_required")
            issues.extend(b.Issue(name, code) for code in sec_issues)
            for index, raw_row in enumerate(raw_rows):
                loc = r.Locator(name, index)
                rule_index, decision_index = (
                    matches.rows[source_ordinal],
                    matches.decisions[source_ordinal],
                )
                source_ordinal += 1
                rr = stipulation.rows[rule_index] if rule_index is not None else None
                decision = policy.decisions[decision_index] if decision_index is not None else None
                row_issues = list(sec_issues)
                if not isinstance(raw_row, v.JsonObject):
                    row_issues.append("invalid_source_row")
                if rr is None:
                    row_issues.append("row_disposition_missing")
                elif rr.row_sha256 != r.row_identity(raw_row) or not r._evidence(
                    rr.evidence, effective, known
                ):
                    row_issues.append("row_link_or_evidence_stale")
                raw_value = (
                    raw_row.get(value_field.field)
                    if (isinstance(raw_row, v.JsonObject) and value_field)
                    else None
                )
                value = parse(raw_value, "decimal")
                raw_weight = (
                    raw_row.get(rule.weight_field)
                    if (isinstance(raw_row, v.JsonObject) and rule)
                    else None
                )
                weight = parse(raw_weight, rule.unit) if rule else None
                security = rr.security if rr else None
                currency = raw_row.get("currency") if isinstance(raw_row, v.JsonObject) else None
                value_currency = str(currency) if currency is not None else "USD"
                disposition = "unresolved"
                if role == "primary":
                    if rr and rr.target is not None:
                        row_issues.append("primary_cannot_link_another_exposure")
                    if decision is None:
                        row_issues.append("explicit_equity_decision_required")
                    elif decision.action == "exclude":
                        disposition = "excluded"
                        if value is None or value_currency != "USD":
                            unknown_out.append(loc)
                        else:
                            known_out += value
                    else:
                        disposition = "included-equity"
                        if name in ("fixedIncome", "shortTermReserves", "derivatives"):
                            row_issues.append("included_non_equity_section")
                        if value is None:
                            unknown_in.append(loc)
                            row_issues.append("included_value_unknown_or_invalid")
                        else:
                            known_in += value
                            if value < 0:
                                row_issues.append("negative_included_value")
                        if weight is not None and weight < 0:
                            row_issues.append("negative_included_published_weight")
                        if security is None:
                            row_issues.append("included_equity_identity_required")
                        else:
                            if (
                                not security.security_id
                                or not r._text(security.security_id)
                                or security.unknown_reasons
                                or not r._evidence(security.evidence, effective, known)
                            ):
                                row_issues.append("included_equity_identity_unresolved")
                            if security.currency != "USD" or security.asset_type != "stock":
                                row_issues.append("unsupported_included_equity")
                            included.append(security)
                        if isinstance(raw_row, v.JsonObject) and raw_row.get("currency") not in (
                            None,
                            "USD",
                        ):
                            row_issues.append("source_currency_contradiction")
                elif role in ("alternate", "subset"):
                    disposition = "pending-link"
                    if decision is not None:
                        row_issues.append("decision_requires_primary_row")
                    if rr is None or rr.target is None:
                        row_issues.append("explicit_primary_row_link_required")
                row = Row(
                    loc,
                    r.row_identity(raw_row),
                    role,
                    disposition,
                    decision.reason if decision else None,
                    security.security_id if security else None,
                    rr.target if rr else None,
                    str(raw_value) if isinstance(raw_value, str) else None,
                    _kind(raw_value),
                    str(value) if value is not None else None,
                    value_currency,
                    str(raw_weight) if isinstance(raw_weight, str) else None,
                    _kind(raw_weight),
                    str(weight) if weight is not None else None,
                    None,
                    tuple(row_issues),
                )
                ledger.append(row)
                if role == "primary":
                    primary.append(row)
        issues.extend(
            b.Issue(stipulation.sections[index].section, "section_stipulation_not_in_source")
            for index in matches.extra_sections
        )
        issues.extend(
            b.Issue(policy.values[index].section, "value_field_not_in_source")
            for index in matches.extra_values
        )
        issues.extend(
            b.Issue(
                f"{stipulation.rows[index].locator.section}:"
                f"{stipulation.rows[index].locator.index}",
                "row_stipulation_not_in_source",
            )
            for index in matches.extra_rows
        )
        issues.extend(
            b.Issue(
                f"{policy.decisions[index].locator.section}:"
                f"{policy.decisions[index].locator.index}",
                "decision_requires_primary_row",
            )
            for index in t.unmatched(
                tuple((d.locator.section, d.locator.index) for d in policy.decisions),
                tuple((row.locator.section, row.locator.index) for row in primary),
            )
        )
        linkage = t.link(
            tuple(section.section for section in stipulation.sections),
            tuple(
                (
                    row.locator.section,
                    row.target.section if row.target else None,
                    row.target.index if row.target else None,
                    row.disposition == "pending-link",
                )
                for row in ledger
            ),
            tuple((row.locator.section, row.locator.index, not row.issues) for row in primary),
        )
        resolved = []
        for index, row in enumerate(ledger):
            row_issues = list(row.issues)
            if row.disposition == "pending-link":
                target_index = linkage.targets[index]
                if target_index is None or linkage.duplicates[index]:
                    row_issues.append("missing_invalid_or_duplicate_primary_target")
                else:
                    target = primary[target_index]
                    if row.security_id not in (None, target.security_id):
                        row_issues.append("linked_security_mismatch")
                    # Explicit links are attributable assertions, never inferred
                    # by matching prices. Verify their numeric consequences too.
                    if row.value_currency != target.value_currency:
                        row_issues.append("linked_currency_mismatch")
                    values_match = row.value == target.value
                    if row.role == "subset" and row.value is not None and target.value is not None:
                        values_match = 0 <= numeric(row.value) <= numeric(target.value)
                    if not values_match or (
                        row.value is None
                        and (
                            row.raw_value != target.raw_value
                            or row.value_token_kind != target.value_token_kind
                        )
                    ):
                        row_issues.append("linked_value_mismatch")
                    if row.published_weight is not None and target.published_weight is not None:
                        linked_weight, primary_weight = (
                            numeric(row.published_weight),
                            numeric(target.published_weight),
                        )
                        close = estimates and math.isclose(
                            float(linked_weight),
                            float(primary_weight),
                            rel_tol=0,
                            abs_tol=advisory.WEIGHT_TOLERANCE,
                        )
                        if (
                            linked_weight != primary_weight and not close
                            if row.role == "alternate"
                            else linked_weight < 0 or (linked_weight > primary_weight and not close)
                        ):
                            row_issues.append("linked_published_weight_mismatch")
            disposition = (
                f"linked-{row.role}" if row.disposition == "pending-link" else row.disposition
            )
            resolved.append(
                replace(
                    row,
                    disposition="unresolved" if row_issues else disposition,
                    issues=tuple(row_issues),
                )
            )
            issues.extend(
                b.Issue(f"{row.locator.section}:{row.locator.index}", code) for code in row_issues
            )
        ledger = resolved
        for section in stipulation.sections:
            if section.role == "alternate" and section.section not in linkage.complete_sections:
                issues.append(b.Issue(section.section, "alternate_does_not_cover_primary_rows"))
        ids = tuple(security.security_id for security in included)
        if t.duplicate_ids(ids):
            issues.append(b.Issue("equities", "duplicate_included_security"))
        if not included or known_in <= 0:
            issues.append(b.Issue("equities", "positive_retained_equity_total_required"))
        if not issues:
            included_indices = t.included_ordinals(tuple(row.disposition for row in ledger))
            if estimates:
                values = []
                for index in included_indices:
                    text_value = ledger[index].value
                    assert text_value is not None
                    values.append(float(text_value))
                frame = pl.DataFrame(
                    {"value": values},
                    schema={"value": pl.Float64},
                )
                known_in = float(frame.get_column("value").sum())
                weight_frame = frame.select((pl.col("value") / known_in).alias("weight"))
                ratios = weight_frame.get_column("weight").to_list()
                if (
                    not math.isfinite(known_in)
                    or not advisory.unit_sum(tuple(ratios))
                    or any(
                        value > 0 and ratio == 0
                        for value, ratio in zip(frame.get_column("value"), ratios, strict=True)
                    )
                ):
                    issues.append(b.Issue("equities", "unrepresentable_equity_weights"))
                else:
                    by_index = dict(zip(included_indices, ratios, strict=True))
                    ledger = [
                        replace(row, derived_weight=str(by_index[index]))
                        if index in by_index
                        else row
                        for index, row in enumerate(ledger)
                    ]
            else:
                for index in included_indices:
                    row = ledger[index]
                    assert row.value is not None
                    ratio = Fraction(row.value) / Fraction(known_in)
                    if max(len(str(ratio.numerator)), len(str(ratio.denominator))) > 128:
                        issues.append(b.Issue("equities", "exact_ratio_representation_limit"))
                if not issues:
                    ledger = [
                        replace(row, derived_weight=str(Fraction(row.value) / Fraction(known_in)))
                        if row.disposition == "included-equity" and row.value is not None
                        else row
                        for row in ledger
                    ]
    inputs = fingerprint(r.encoded((acquisition, stipulation, policy)))
    status = (
        ("estimated-equity-benchmark" if estimates else "qualified-synthetic-equity-benchmark")
        if source_ok and not issues
        else ("incomplete" if source_ok else "unavailable")
    )
    total = str(known_in) if source_ok and not issues else None
    canonical = fingerprint(r.encoded((tuple(ledger), total, tuple(issues))))
    benchmark_rows = None
    if total is not None:
        derived = []
        for index, row in enumerate(ledger):
            if row.derived_weight is not None:
                rule_index = matches.rows[index]
                assert rule_index is not None
                row_rule = stipulation.rows[rule_index]
                assert row_rule.security is not None
                reported_ratio = (
                    float(row.derived_weight) if estimates else Fraction(row.derived_weight)
                )
                if estimates:
                    weight_text = str(reported_ratio)
                else:
                    legacy_ratio = Fraction(reported_ratio)
                    weight_text = f"{legacy_ratio.numerator}/{legacy_ratio.denominator}"
                evidence = b.Evidence(
                    canonical,
                    f"derived-value-weight:{row.locator.section}:{row.locator.index}",
                    stipulation.effective_date,
                    acquisition.collected_at.date().isoformat(),
                    row_rule.evidence.valid_through,
                )
                derived.append(
                    b.BenchmarkRow(
                        f"{row.locator.section}:{row.locator.index}",
                        row_rule.security,
                        b.Fact(weight_text, evidence),
                        "decimal" if estimates else "exact-ratio",
                    )
                )
        benchmark_rows = tuple(derived)
    identity = fingerprint(
        [
            "advisory-equity-v1" if estimates else VERSION,
            IMPLEMENTATION_SHA256,
            t.IMPLEMENTATION_SHA256,
            t.RUNTIME_VERSION,
            r.IMPLEMENTATION_SHA256,
            b.IMPLEMENTATION_SHA256,
            r.ACQUISITION_SHA256,
            inputs,
            canonical,
            status,
        ]
    )
    return Result(
        acquisition,
        stipulation,
        policy,
        status,
        tuple(issues),
        tuple(ledger),
        str(known_in),
        tuple(unknown_in),
        str(known_out),
        tuple(unknown_out),
        total,
        benchmark_rows,
        inputs,
        canonical,
        identity,
    )


def select(acquisition: v.Acquisition, stipulation: r.Stipulation, policy: Policy) -> Result:
    """Legacy synthetic exact-format selection; retained until the storage bridge."""
    return _select(acquisition, stipulation, policy)


@dataclass(frozen=True)
class EquityEstimate:
    status: str
    issues: tuple[b.Issue, ...]
    ledger: tuple[Row, ...]
    equity_value: float | None
    security_ids: tuple[str, ...]
    weights: tuple[float, ...]
    basket: b.BasketEstimate | None
    version: str = "advisory-equity-v1"


def estimate(
    acquisition: v.Acquisition,
    stipulation: r.Stipulation,
    policy: Policy,
    portfolio: r.PortfolioContext | None = None,
) -> EquityEstimate:
    """Apply existing source decisions, derive Float64 weights, optionally value a sleeve."""
    selected = _select(acquisition, stipulation, policy, estimates=True)
    rows = selected.benchmark_rows
    basket = None
    if rows is not None and portfolio is not None:
        if (
            portfolio.as_of != stipulation.effective_date
            or portfolio.known_at < acquisition.collected_at.date().isoformat()
        ):
            raise r.ReconciliationUnavailable("matching valuation/knowledge context required")
        basket = b.estimate(
            b.BasketInput(
                f"Stipulated {stipulation.fund.ticker} equity-only disclosed-holdings proxy",
                portfolio.as_of,
                portfolio.known_at,
                portfolio.universe,
                portfolio.positions,
                rows,
                portfolio.candidates,
                portfolio.portfolio_cash,
                stipulation.benchmark_cash,
                stipulation.benchmark_cash_unit,
            )
        )
    security_ids = []
    weights = []
    if rows is not None:
        for row in rows:
            assert row.security.security_id is not None and row.weight.raw is not None
            security_ids.append(row.security.security_id)
            weights.append(float(row.weight.raw))
    return EquityEstimate(
        selected.status,
        selected.issues,
        selected.ledger,
        float(selected.equity_value_total) if selected.equity_value_total is not None else None,
        tuple(security_ids),
        tuple(weights),
        basket,
    )


def bridge(result: Result, portfolio: r.PortfolioContext) -> Bridge:
    """Only replay-matching complete synthetic selection can reach consumers."""
    if (
        r.encoded(select(result.acquisition, result.stipulation, result.policy))
        != r.encoded(result)
        or result.benchmark_rows is None
    ):
        raise r.ReconciliationUnavailable("complete replay-matching equity selection required")
    if (
        portfolio.as_of != result.stipulation.effective_date
        or portfolio.known_at < result.acquisition.collected_at.date().isoformat()
    ):
        raise r.ReconciliationUnavailable("matching valuation/knowledge context required")
    data = b.BasketInput(
        f"Stipulated {result.stipulation.fund.ticker} equity-only disclosed-holdings proxy",
        portfolio.as_of,
        portfolio.known_at,
        portfolio.universe,
        portfolio.positions,
        result.benchmark_rows,
        portfolio.candidates,
        portfolio.portfolio_cash,
        result.stipulation.benchmark_cash,
        result.stipulation.benchmark_cash_unit,
    )
    return Bridge(result, portfolio, b.qualify(data))
