"""Stipulated synthetic full-response reconciliation; no real benchmark activation.

Relationships and identities are attributable inputs, never inferred from equal
values, ticker similarity or section names. Raw acquisition evidence is retained.
"""

import hashlib
import re
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Literal

from prosper import basket as b
from prosper import benchmark_tables as t
from prosper import vanguard as v
from prosper.innovations import fingerprint

VERSION = "synthetic-benchmark-reconciliation-v1"
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
ACQUISITION_SHA256 = hashlib.sha256(Path(v.__file__).read_bytes()).hexdigest()
Role = Literal["primary", "alternate", "subset", "empty", "unresolved"]


class ReconciliationUnavailable(ValueError):
    """Malformed stipulation or attempted consumption of an unqualified report."""


@dataclass(frozen=True, order=True)
class Locator:
    section: str
    index: int


@dataclass(frozen=True)
class SectionRule:
    section: str
    role: Role
    weight_field: str
    unit: str
    evidence: b.Evidence


@dataclass(frozen=True)
class RowRule:
    locator: Locator
    row_sha256: str
    security: b.Security | None
    target: Locator | None
    evidence: b.Evidence


@dataclass(frozen=True)
class Stipulation:
    raw_sha256: str
    fund: v.Fund
    requested_date: str | None
    effective_date: str
    collected_at: str
    fund_assertion: b.Evidence
    sections: tuple[SectionRule, ...]
    rows: tuple[RowRule, ...]
    benchmark_cash: b.Fact
    benchmark_cash_unit: str
    scope: str = "explicitly-stipulated-synthetic"


@dataclass(frozen=True)
class RowDisposition:
    locator: Locator
    row_sha256: str
    role: str
    raw_weight: str | None
    token_kind: str
    weight: str | None
    security_id: str | None
    target: Locator | None
    disposition: str
    issues: tuple[str, ...]


@dataclass(frozen=True)
class SectionSummary:
    section: str
    role: str
    row_count: int
    known_weight_sum: str | None
    unknown_weight_indexes: tuple[int, ...]
    issues: tuple[str, ...]


@dataclass(frozen=True)
class Reconciliation:
    status: str
    acquisition: v.Acquisition = field(repr=False)
    stipulation: Stipulation
    upstream_issues: tuple[str, ...]
    issues: tuple[b.Issue, ...]
    ledger: tuple[RowDisposition, ...]
    sections: tuple[SectionSummary, ...]
    primary_known_weight_sum: str | None
    primary_unknown_rows: tuple[Locator, ...]
    economic_total: str | None
    residual: str | None
    benchmark_rows: tuple[b.BenchmarkRow, ...] | None
    input_sha256: str
    canonical_sha256: str
    identity_sha256: str

    @property
    def benchmark_ready(self) -> Literal[False]:
        return False


@dataclass(frozen=True)
class PortfolioContext:
    as_of: str
    known_at: str
    universe: tuple[str, ...]
    positions: tuple[b.Position, ...]
    candidates: tuple[b.Security, ...]
    portfolio_cash: b.Fact


@dataclass(frozen=True)
class BasketBridge:
    reconciliation: Reconciliation
    portfolio: PortfolioContext
    basket: b.BasketResult

    @property
    def benchmark_ready(self) -> Literal[False]:
        return False


def encoded(value: object) -> object:
    """Typed replay identity, including JSON number versus string distinctions.

    Bytes remain in the result's acquisition; reports identify them by hash/size.
    """
    if isinstance(value, v.JsonNumber):
        return {"json_number": str(value)}
    if isinstance(value, bytes):
        return {"bytes_sha256": hashlib.sha256(value).hexdigest(), "length": len(value)}
    if isinstance(value, (date, datetime)):
        return {type(value).__name__: value.isoformat()}
    if isinstance(value, Fraction):
        return {"fraction": str(value)}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            type(value).__name__: [[f.name, encoded(getattr(value, f.name))] for f in fields(value)]
        }
    if isinstance(value, tuple):
        return [encoded(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise ReconciliationUnavailable("unsupported mutable or untyped evidence")


def row_identity(row: v.JsonValue) -> str:
    return fingerprint(encoded(row))


def _text(value: str) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= 256
        and bool(value.strip())
        and all(ord(c) >= 32 for c in value)
    )


def _hash(value: str) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _evidence(e: b.Evidence, effective: str, known: str) -> bool:
    if (
        not _hash(e.source_sha256)
        or not _text(e.reference)
        or type(e.unknown_reasons) is not tuple
        or any(not _text(r) for r in e.unknown_reasons)
    ):
        raise ReconciliationUnavailable("bounded immutable attributable evidence required")
    if e.unknown_reasons or e.effective is None or e.recorded is None or e.valid_through is None:
        return False
    try:
        days = tuple(
            date.fromisoformat(s)
            for s in (e.effective, e.recorded, e.valid_through, effective, known)
        )
    except ValueError:
        return False
    return (
        tuple(d.isoformat() for d in days)
        == (e.effective, e.recorded, e.valid_through, effective, known)
        and days[0] <= days[3] <= days[2]
        and days[1] <= days[4]
    )


def _number(raw: v.JsonValue, unit: str) -> Fraction | None:
    if (
        not isinstance(raw, str)
        or len(raw) > 128
        or re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", raw) is None
    ):
        return None
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError, OverflowError):
        return None
    if (
        not value.is_finite()
        or abs(int(value.as_tuple().exponent)) > 40
        or unit not in ("decimal", "percent")
    ):
        return None
    return Fraction(value) / (100 if unit == "percent" else 1)


def _validate_rules(s: Stipulation) -> None:
    if s.scope != "explicitly-stipulated-synthetic" or not _hash(s.raw_sha256):
        raise ReconciliationUnavailable("explicit synthetic raw-source binding required")
    if (
        type(s.sections) is not tuple
        or type(s.rows) is not tuple
        or len(s.sections) > v.MAX_ROWS
        or len(s.rows) > v.MAX_ROWS
    ):
        raise ReconciliationUnavailable("bounded immutable stipulations required")
    if len({r.section for r in s.sections}) != len(s.sections) or len(
        {r.locator for r in s.rows}
    ) != len(s.rows):
        raise ReconciliationUnavailable("unique section and row stipulations required")
    for section in s.sections:
        if (
            not _text(section.section)
            or section.role not in ("primary", "alternate", "subset", "empty", "unresolved")
            or not _text(section.weight_field)
            or section.unit not in ("decimal", "percent")
        ):
            raise ReconciliationUnavailable(
                "explicit section role, weight field and units required"
            )
    for row in s.rows:
        for loc in (row.locator, row.target):
            if loc is not None and (
                not _text(loc.section) or type(loc.index) is not int or loc.index < 0
            ):
                raise ReconciliationUnavailable("explicit original row locator required")
        if not _hash(row.row_sha256):
            raise ReconciliationUnavailable("typed source row identity required")


def reconcile(acquisition: v.Acquisition, stipulation: Stipulation) -> Reconciliation:
    """Reconcile all original sections/rows without network or inferred policies."""
    _validate_rules(stipulation)
    issues: list[b.Issue] = []
    ledger: list[RowDisposition] = []
    sections: list[SectionSummary] = []
    primary: list[tuple[Locator, b.BenchmarkRow, Fraction]] = []
    unknown_primary: list[Locator] = []
    primary_known = Fraction()
    total: Fraction | None = None
    source = acquisition.snapshot
    response = acquisition.response
    source_ok = source is not None and response is not None
    if response is not None:
        replay = v.acquire(
            acquisition.selection,
            collected_at=acquisition.collected_at,
            transport=lambda _: response,
        )
        if encoded(replay) != encoded(acquisition):
            issues.append(b.Issue("acquisition", "snapshot_replay_mismatch"))
            source_ok = False
    if source is None or response is None:
        issues.append(b.Issue("acquisition", "snapshot_unavailable", acquisition.issues))
    if source_ok and source is not None:
        expected = (
            source.raw_sha256,
            source.selection.fund,
            source.selection.effective_date.isoformat()
            if source.selection.effective_date
            else None,
            source.effective_date.isoformat(),
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
    if source_ok and source is not None:
        effective, known = source.effective_date.isoformat(), source.collected_at.date().isoformat()
        if stipulation.fund_assertion.source_sha256 == source.raw_sha256 or not _evidence(
            stipulation.fund_assertion, effective, known
        ):
            issues.append(b.Issue("fund", "independent_stipulated_fund_assertion_required"))
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
        )
        source_ordinal = 0
        for section_index, (name, raw_rows) in enumerate(holdings.fields):
            rule_index = matches.sections[section_index]
            rule = stipulation.sections[rule_index] if rule_index is not None else None
            role = rule.role if rule else "unresolved"
            sec_issues: list[str] = []
            if rule is None or role == "unresolved":
                sec_issues.append("section_relationship_unresolved")
            elif not _evidence(rule.evidence, effective, known):
                sec_issues.append("section_evidence_stale_or_unknown")
            if not isinstance(raw_rows, tuple):
                sec_issues.append("non_array_section_retained")
                raw_rows = ()  # Not interpreted as exposure; original value is retained.
            if role == "empty" and raw_rows:
                sec_issues.append("nonempty_section_declared_empty")
            if name in ("fixedIncome", "shortTermReserves", "derivatives") and raw_rows:
                sec_issues.append("unsupported_nonstock_section")
            known_sum = (
                Fraction() if rule and "non_array_section_retained" not in sec_issues else None
            )
            unknown: list[int] = []
            for index, raw_row in enumerate(raw_rows):
                locator = Locator(name, index)
                rule_index = matches.rows[source_ordinal]
                source_ordinal += 1
                rr = stipulation.rows[rule_index] if rule_index is not None else None
                row_issues = list(sec_issues)
                raw_weight = (
                    raw_row.get(rule.weight_field)
                    if isinstance(raw_row, v.JsonObject) and rule
                    else None
                )
                weight = _number(raw_weight, rule.unit) if rule else None
                kind = (
                    "number"
                    if isinstance(raw_weight, v.JsonNumber)
                    else "string"
                    if isinstance(raw_weight, str)
                    else "null"
                    if raw_weight is None
                    else "other"
                )
                if weight is None:
                    unknown.append(index)
                    row_issues.append("unknown_weight")
                elif known_sum is not None:
                    known_sum += weight
                    if weight < 0:
                        row_issues.append("negative_weight")
                if not isinstance(raw_row, v.JsonObject):
                    row_issues.append("invalid_source_row")
                if rr is None:
                    row_issues.append("row_disposition_missing")
                elif rr.row_sha256 != row_identity(raw_row) or not _evidence(
                    rr.evidence, effective, known
                ):
                    row_issues.append("row_link_or_evidence_stale")
                security = rr.security if rr else None
                if security is not None:
                    if (
                        not security.security_id
                        or security.unknown_reasons
                        or not _evidence(security.evidence, effective, known)
                    ):
                        row_issues.append("security_identity_unresolved")
                    if security.currency != "USD" or security.asset_type != "stock":
                        row_issues.append("unsupported_security")
                    if isinstance(raw_row, v.JsonObject) and raw_row.get("currency") not in (
                        None,
                        "USD",
                    ):
                        row_issues.append("source_currency_contradiction")
                if role == "primary":
                    if weight is not None:
                        primary_known += weight
                    else:
                        unknown_primary.append(locator)
                    if security is None:
                        row_issues.append("primary_identity_required")
                    if rr is not None and rr.target is not None:
                        row_issues.append("primary_cannot_link_another_exposure")
                    if (
                        not row_issues
                        and rr is not None
                        and security is not None
                        and rule is not None
                        and isinstance(raw_weight, str)
                        and weight is not None
                    ):
                        evidence = b.Evidence(
                            source.raw_sha256,
                            f"{name}:{index}:{rule.weight_field}",
                            effective,
                            known,
                            rr.evidence.valid_through,
                        )
                        primary.append(
                            (
                                locator,
                                b.BenchmarkRow(
                                    f"{name}:{index}",
                                    security,
                                    b.Fact(str(raw_weight), evidence),
                                    rule.unit,
                                ),
                                weight,
                            )
                        )
                if role in ("alternate", "subset") and (rr is None or rr.target is None):
                    row_issues.append("explicit_primary_row_link_required")
                disposition = (
                    "included-primary"
                    if role == "primary" and not row_issues
                    else "pending-link"
                    if role in ("alternate", "subset") and not row_issues
                    else "unresolved"
                )
                ledger.append(
                    RowDisposition(
                        locator,
                        row_identity(raw_row),
                        role,
                        str(raw_weight) if isinstance(raw_weight, str) else None,
                        kind,
                        str(weight) if weight is not None else None,
                        security.security_id if security else None,
                        rr.target if rr else None,
                        disposition,
                        tuple(row_issues),
                    )
                )
            sections.append(
                SectionSummary(
                    name,
                    role,
                    len(raw_rows),
                    str(known_sum) if known_sum is not None else None,
                    tuple(unknown),
                    tuple(sec_issues),
                )
            )
            issues.extend(b.Issue(name, code) for code in sec_issues)
        issues.extend(
            b.Issue(stipulation.sections[index].section, "section_stipulation_not_in_source")
            for index in matches.extra_sections
        )
        issues.extend(
            b.Issue(
                f"{stipulation.rows[index].locator.section}:"
                f"{stipulation.rows[index].locator.index}",
                "row_stipulation_not_in_source",
            )
            for index in matches.extra_rows
        )
        linkage = t.link(
            tuple(section.section for section in sections),
            tuple(
                (
                    row.locator.section,
                    row.target.section if row.target else None,
                    row.target.index if row.target else None,
                    row.disposition == "pending-link",
                )
                for row in ledger
            ),
            tuple((loc.section, loc.index, True) for loc, _, _ in primary),
        )
        resolved_ledger = []
        for index, row in enumerate(ledger):
            row_issues = list(row.issues)
            if row.disposition == "pending-link":
                target_index = linkage.targets[index]
                if target_index is None or linkage.duplicates[index]:
                    row_issues.append("missing_invalid_or_duplicate_primary_target")
                else:
                    _, stock, weight = primary[target_index]
                    actual_weight = Fraction(row.weight) if row.weight is not None else None
                    if row.security_id not in (None, stock.security.security_id):
                        row_issues.append("linked_security_mismatch")
                    if (
                        actual_weight is None
                        or (row.role == "alternate" and actual_weight != weight)
                        or (row.role == "subset" and not 0 <= actual_weight <= weight)
                    ):
                        row_issues.append("linked_weight_mismatch")
            disposition = (
                f"linked-{row.role}"
                if row.disposition == "pending-link" and not row_issues
                else row.disposition
            )
            if row_issues:
                disposition = "unresolved"
            resolved_ledger.append(
                RowDisposition(
                    row.locator,
                    row.row_sha256,
                    row.role,
                    row.raw_weight,
                    row.token_kind,
                    row.weight,
                    row.security_id,
                    row.target,
                    disposition,
                    tuple(row_issues),
                )
            )
            issues.extend(
                b.Issue(f"{row.locator.section}:{row.locator.index}", code) for code in row_issues
            )
        ledger = resolved_ledger
        for sec in sections:
            if sec.role == "alternate" and sec.section not in linkage.complete_sections:
                issues.append(b.Issue(sec.section, "alternate_does_not_cover_primary_rows"))
        if not primary:
            issues.append(b.Issue("primary", "complete_primary_exposures_required"))
        security_ids = tuple(row.security.security_id for _, row, _ in primary)
        if t.duplicate_ids(security_ids):
            issues.append(b.Issue("primary", "duplicate_primary_security"))
        cash = stipulation.benchmark_cash
        cash_weight = _number(cash.raw, stipulation.benchmark_cash_unit)
        if (
            cash.raw is None
            or cash.unknown_reasons
            or cash_weight is None
            or cash_weight < 0
            or not _evidence(cash.evidence, effective, known)
        ):
            issues.append(
                b.Issue(
                    "benchmark_cash",
                    "explicit_valid_nonnegative_cash_required",
                    cash.unknown_reasons,
                )
            )
        if (
            not issues
            and not unknown_primary
            and cash_weight is not None
            and not cash.unknown_reasons
        ):
            total = primary_known + cash_weight
            if total != 1:
                issues.append(b.Issue("primary", "non_unit_economic_total"))
    canonical = fingerprint(
        encoded(
            (
                stipulation.fund,
                stipulation.effective_date,
                tuple(
                    (
                        row.locator,
                        row.role,
                        row.weight,
                        row.security_id,
                        row.target,
                        row.disposition,
                        row.issues,
                    )
                    for row in ledger
                ),
                tuple(sections),
                str(total) if total is not None else None,
                tuple(issues),
            )
        )
    )
    inputs = fingerprint(encoded((acquisition, stipulation)))
    status = (
        "qualified-synthetic-reconciliation"
        if source_ok and not issues
        else "incomplete"
        if source_ok
        else "unavailable"
    )
    rows = (
        tuple(row for _, row, _ in primary)
        if status == "qualified-synthetic-reconciliation"
        else None
    )
    identity = fingerprint(
        [
            VERSION,
            IMPLEMENTATION_SHA256,
            t.IMPLEMENTATION_SHA256,
            t.RUNTIME_VERSION,
            b.IMPLEMENTATION_SHA256,
            v.ADAPTER_VERSION,
            ACQUISITION_SHA256,
            inputs,
            canonical,
            status,
        ]
    )
    return Reconciliation(
        status,
        acquisition,
        stipulation,
        acquisition.issues,
        tuple(issues),
        tuple(ledger),
        tuple(sections),
        str(primary_known) if source_ok and any(s.role == "primary" for s in sections) else None,
        tuple(unknown_primary),
        str(total) if total is not None else None,
        str(1 - total) if total is not None else None,
        rows,
        inputs,
        canonical,
        identity,
    )


def bridge(result: Reconciliation, portfolio: PortfolioContext) -> BasketBridge:
    """Consume only replay-matching complete synthetic results; never fetch/activate."""
    if (
        encoded(reconcile(result.acquisition, result.stipulation)) != encoded(result)
        or result.benchmark_rows is None
    ):
        raise ReconciliationUnavailable("complete replay-matching reconciliation required")
    if (
        portfolio.as_of != result.stipulation.effective_date
        or portfolio.known_at < result.acquisition.collected_at.date().isoformat()
    ):
        raise ReconciliationUnavailable("explicit matching valuation/knowledge context required")
    data = b.BasketInput(
        f"Stipulated {result.stipulation.fund.ticker} full-holdings proxy",
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
    return BasketBridge(result, portfolio, b.qualify(data))
