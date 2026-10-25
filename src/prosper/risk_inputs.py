"""Immutable fictional basket/history/taxonomy-to-IDR input qualification.

Only the named no-action/raw-equals-adjusted construction is supported. Real
benchmark activation, quote feeds, action transforms and fitted risk are gated
elsewhere. Frozen evidence is distinct from synthetic numerical qualification.
"""

import hashlib
import json
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, ValidationError

from prosper import basket as b
from prosper import history as h
from prosper import history_refresh as f
from prosper import industry as i
from prosper import innovations as n
from prosper.evidence import EvidenceError
from prosper.history_coordination import history_writer
from prosper.history_registry import Dependency, HistoryRegistry

VERSION: Literal["synthetic-risk-inputs-v1"] = "synthetic-risk-inputs-v1"
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]


class RiskInputError(EvidenceError):
    """Stable refusal code, without supplied payloads or local paths."""


class Request(h.Closed):
    history_id: Identifier
    basket: h.RawReference
    taxonomy: h.RawReference
    profile: h.RawReference
    limits: h.RawReference
    sources: Annotated[tuple[h.RawReference, ...], Field(max_length=996)]
    construction: str = "fictional-no-action-raw-equals-adjusted-v1"
    variant: str = "idr"
    units: str = "decimal"


class Issue(h.Closed):
    location: h.Text
    code: h.Text


class Record(h.Closed):
    format: Literal["synthetic-risk-inputs-v1"] = VERSION
    request: Request
    history: h.RawReference
    issues: tuple[Issue, ...]
    basket: b.BasketResult | None
    exposures: tuple[i.Exposure, ...]
    innovation: n.InnovationResult | None
    input_sha256: h.Text
    synthetic_ready: bool
    financial_ready: Literal[False] = False
    limit_results: tuple[i.LimitResult, ...] = ()


def _bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _json(raw: bytes) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value = dict(pairs)
        if len(value) != len(pairs):
            raise RiskInputError("duplicate_source_fields")
        return value

    def nonfinite(value: str) -> object:
        raise RiskInputError("nonfinite_source_json")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)


def _decode[T](history: h.HistoryStore, reference: h.RawReference, adapter: TypeAdapter[T]) -> T:
    raw = history.evidence.read(reference.receipt())
    original = _json(raw)
    value = adapter.validate_json(raw, strict=True)
    # Dataclass adapters can ignore extra fields; exact structural equality refuses that loss.
    if _json(adapter.dump_json(value)) != original:
        raise RiskInputError("source_schema_loss")
    return value


def _pointer(value: object, reference: str) -> object:
    for part in reference.split("/"):
        if isinstance(value, dict):
            value = value[part]
        elif isinstance(value, list) and part.isdigit():
            value = value[int(part)]
        else:
            raise KeyError(reference)
    return value


def _assessment(
    registry: HistoryRegistry, request: Request, entries: dict[str, Dependency]
) -> Record:
    if request.history_id not in entries:
        raise RiskInputError("risk_history_dependency_missing")
    history_entry = entries[request.history_id]
    refresh = f._record(registry, history_entry)
    frozen = registry.history.read(
        history_entry.manifest.receipt(), expected=history_entry.selection
    )
    selection = frozen.manifest.envelope.selection
    issues: list[Issue] = []

    def issue(location: str, code: str) -> None:
        issues.append(Issue(location=location, code=code))

    if not frozen.manifest.coverage.complete or not refresh.complete:
        issue("history", "incomplete_frozen_history")
    if (
        request.construction != "fictional-no-action-raw-equals-adjusted-v1"
        or request.variant != "idr"
        or request.units != "decimal"
    ):
        issue("settings", "unsupported_synthetic_construction")
    input_sha256 = hashlib.sha256(
        _bytes(
            {
                "request": request.model_dump(mode="json"),
                "history": history_entry.manifest.model_dump(mode="json"),
                "implementations": [
                    VERSION,
                    IMPLEMENTATION_SHA256,
                    b.IMPLEMENTATION_SHA256,
                    i.IMPLEMENTATION_SHA256,
                    n.IMPLEMENTATION_SHA256,
                ],
            }
        )
    ).hexdigest()
    source_documents: dict[str, object] = {}
    if len({s.sha256 for s in request.sources}) != len(request.sources):
        issue("sources", "duplicate_source_identity")
    for index, reference in enumerate(request.sources):
        raw = registry.history.evidence.read(reference.receipt())
        try:
            source_documents[reference.sha256] = _json(raw)
        except (ValueError, TypeError, UnicodeError):
            issue(f"sources/{index}", "invalid_source_document")
    try:
        data = _decode(registry.history, request.basket, TypeAdapter(b.BasketInput))
        taxonomy = _decode(registry.history, request.taxonomy, TypeAdapter(i.Taxonomy))
        profile = _decode(registry.history, request.profile, TypeAdapter(n.InnovationProfile))
        limits = _decode(registry.history, request.limits, TypeAdapter(tuple[i.ExposureLimit, ...]))
    except (ValueError, TypeError, UnicodeError):
        issue("artifacts", "invalid_source_schema")
        return Record(
            request=request,
            history=history_entry.manifest,
            issues=tuple(issues),
            basket=None,
            exposures=(),
            innovation=None,
            input_sha256=input_sha256,
            synthetic_ready=False,
        )

    def claim(location: str, evidence: b.Evidence, expected: object) -> None:
        if evidence.source_sha256 not in source_documents:
            issue(location, "source_evidence_missing")
            return
        try:
            actual = _pointer(source_documents[evidence.source_sha256], evidence.reference)
            if actual != _json(_bytes(expected)):
                issue(location, "source_claim_mismatch")
        except (KeyError, IndexError, TypeError, ValueError):
            issue(location, "source_locator_missing")

    def fact(location: str, value: b.Fact, **extra: object) -> None:
        expected = asdict(value)
        expected.pop("evidence")
        expected.update(
            {
                "effective": value.evidence.effective,
                "recorded": value.evidence.recorded,
                "valid_through": value.evidence.valid_through,
                "evidence_unknown_reasons": value.evidence.unknown_reasons,
                **extra,
            }
        )
        claim(location, value.evidence, expected)

    def security(location: str, value: b.Security) -> None:
        expected = asdict(value)
        expected.pop("evidence")
        expected.update(
            {
                "effective": value.evidence.effective,
                "recorded": value.evidence.recorded,
                "valid_through": value.evidence.valid_through,
                "evidence_unknown_reasons": value.evidence.unknown_reasons,
            }
        )
        claim(location, value.evidence, expected)

    for index, position in enumerate(data.positions):
        security(f"positions/{index}/security", position.security)
        fact(f"positions/{index}/quantity", position.quantity, unit="shares")
        fact(f"positions/{index}/mark", position.reference_mark, unit="USD", kind="reference-close")
    for index, benchmark_row in enumerate(data.benchmark):
        security(f"benchmark/{index}/security", benchmark_row.security)
        fact(f"benchmark/{index}/weight", benchmark_row.weight, unit=benchmark_row.unit)
    for index, candidate in enumerate(data.candidates):
        security(f"candidates/{index}", candidate)
    fact("portfolio_cash", data.portfolio_cash, unit="USD", scope="selected-residual")
    fact("benchmark_cash", data.benchmark_cash, unit=data.benchmark_cash_unit)
    taxonomy_source = source_documents.get(taxonomy.source_sha256)
    if taxonomy_source is None:
        issue("taxonomy", "source_evidence_missing")
    else:
        try:
            expected_taxonomy = {
                "name": taxonomy.name,
                "version": taxonomy.version,
                "as_of": taxonomy.as_of,
                "hierarchy": taxonomy.hierarchy,
                "records": [
                    {k: v for k, v in asdict(row).items() if k != "evidence"}
                    for row in taxonomy.records
                ],
            }
            if _pointer(taxonomy_source, "taxonomy") != _json(_bytes(expected_taxonomy)):
                issue("taxonomy", "source_claim_mismatch")
            for classification in taxonomy.records:
                if _pointer(taxonomy_source, classification.evidence) != _json(
                    _bytes({k: v for k, v in asdict(classification).items() if k != "evidence"})
                ):
                    issue(f"taxonomy/{classification.security_id}", "source_claim_mismatch")
                if classification.recorded > selection.known_at[:10]:
                    issue(f"taxonomy/{classification.security_id}", "future_classification")
                if (
                    classification.sector is None
                    or classification.industry is None
                    or classification.unknown_reasons
                ):
                    issue(f"taxonomy/{classification.security_id}", "unknown_classification")
        except (KeyError, IndexError, TypeError, ValueError):
            issue("taxonomy", "source_locator_missing")
    ids = tuple(s.security_id for s in selection.series)
    if data.universe != ids:
        issue("universe", "basket_history_order_or_coverage")
    if tuple(row.security_id for row in taxonomy.records) != ids:
        issue("taxonomy", "complete_ordered_taxonomy_required")
    if (
        data.as_of != selection.cutoff
        or data.known_at > selection.known_at[:10]
        or selection.sessions[-1] != selection.cutoff
    ):
        issue("cutoffs", "valuation_history_knowledge_mismatch")
    if profile.identity != "R1":
        issue("profile", "unsupported_profile")
    common = selection.series[0]
    for series in selection.series:
        fields = (
            "provider",
            "dataset",
            "permission_scope",
            "currency",
            "calendar",
            "timezone",
            "interval",
            "adjustment",
            "repair",
            "source_schema",
            "transform_version",
            "library_version",
            "return_convention",
            "return_transform_version",
            "vintage",
        )
        if (
            any(getattr(series, key) != getattr(common, key) for key in fields)
            or series.currency != "USD"
            or series.timezone != "UTC"
        ):
            issue(f"history/{series.security_id}", "incompatible_series_context")
    by_key = {(row.security_id, row.session): row for row in frozen.manifest.envelope.observations}
    for index, position in enumerate(data.positions):
        key = (position.security.security_id or "", selection.cutoff)
        mark_row = by_key.get(key)
        if mark_row is None or position.reference_mark.raw is None or mark_row.close.text is None:
            issue(f"positions/{index}/mark", "closing_mark_missing")
        else:
            try:
                if Fraction(position.reference_mark.raw) != Fraction(mark_row.close.text):
                    issue(f"positions/{index}/mark", "closing_mark_history_mismatch")
            except (ValueError, ZeroDivisionError):
                issue(f"positions/{index}/mark", "invalid_closing_mark")
    analytical: list[n.OHLCRow] = []
    for day in selection.sessions:
        for security_id in ids:
            history_row = by_key.get((security_id, day))
            if history_row is None:
                issue(f"grid/{security_id}/{day}", "missing_observation")
                continue
            try:
                if (
                    history_row.dividend.text is None
                    or history_row.split_ratio.text is None
                    or Fraction(history_row.dividend.text) != 0
                    or Fraction(history_row.split_ratio.text) != 1
                ):
                    raise ValueError("unsupported action")
                if (
                    history_row.close.text is None
                    or history_row.adjusted_close.text is None
                    or Fraction(history_row.close.text) != Fraction(history_row.adjusted_close.text)
                ):
                    raise ValueError("incompatible prices")
                source = next(
                    s
                    for s in frozen.manifest.envelope.sources
                    if s.source_id == history_row.source_id
                )
                body = f._body(registry.history.evidence.read(source.raw.receipt()))
                previous = next(
                    p for p in body.observations if p.session == history_row.return_from_session
                )
                if (
                    previous.dividend.text is None
                    or previous.split_ratio.text is None
                    or Fraction(previous.dividend.text) != 0
                    or Fraction(previous.split_ratio.text) != 1
                ):
                    raise ValueError("unsupported predecessor action")
                if (
                    previous.close.text is None
                    or previous.adjusted_close.text is None
                    or Fraction(previous.close.text) != Fraction(previous.adjusted_close.text)
                ):
                    raise ValueError("incompatible predecessor")
                if (
                    history_row.total_return.text is None
                    or Fraction(history_row.total_return.text)
                    != Fraction(history_row.close.text) / Fraction(previous.close.text) - 1
                ):
                    raise ValueError("incompatible return")
                if (
                    history_row.total_return.text is None
                    or history_row.open.text is None
                    or history_row.high.text is None
                    or history_row.low.text is None
                    or history_row.close.text is None
                ):
                    raise ValueError("unknown OHLC")
                analytical.append(
                    n.OHLCRow(
                        day,
                        security_id,
                        history_row.total_return.text,
                        history_row.open.text,
                        history_row.high.text,
                        history_row.low.text,
                        history_row.close.text,
                        "none",
                        source.raw.sha256,
                        source.context.vintage,
                        source.context.vintage,
                        source.context.vintage,
                        "synthetic-compatible-total-return-and-raw-ohlc",
                    )
                )
            except (ValueError, TypeError, ZeroDivisionError, StopIteration):
                issue(f"grid/{security_id}/{day}", "unsupported_or_unknown_action_alignment")
    basket_result = None
    exposures: tuple[i.Exposure, ...] = ()
    limit_results: tuple[i.LimitResult, ...] = ()
    try:
        basket_result = b.qualify(data)
        for finding in basket_result.issues:
            issue(f"basket/{finding.location}", finding.code)
        if basket_result.weights is not None:
            diagnostic = i.diagnose(b.to_industry(basket_result), taxonomy, limits, None)
            exposures = diagnostic.exposures
            limit_results = diagnostic.limit_results
            # No covariance is supplied: exposure diagnostics are deliberately not fitted risk.
            for diagnostic_issue in diagnostic.issues:
                if diagnostic_issue != "covariance:missing":
                    issue("industry", diagnostic_issue)
    except (b.BasketUnavailable, i.IndustryUnavailable, ValueError):
        issue("basket_or_taxonomy", "invalid_stipulated_input")
    innovation = None
    if not issues:
        context = n.InnovationContext(
            ids,
            selection.sessions,
            selection.cutoff,
            common.calendar,
            common.timezone,
            common.vintage,
            input_sha256,
            request.construction,
        )
        innovation = n.transform_ohlc(context, tuple(analytical), profile=profile)
        if innovation.status != "ready":
            issue("innovation", "unusable_synthetic_innovations")
        for innovation_issue in innovation.issues:
            issue(
                f"innovation/{innovation_issue.security_id or 'context'}/"
                f"{innovation_issue.session or 'settings'}",
                innovation_issue.code,
            )
    return Record(
        request=request,
        history=history_entry.manifest,
        issues=tuple(issues),
        basket=basket_result,
        exposures=exposures,
        innovation=innovation,
        input_sha256=input_sha256,
        synthetic_ready=not issues,
        limit_results=limit_results,
    )


def _record(registry: HistoryRegistry, entry: Dependency, entries: dict[str, Dependency]) -> Record:
    candidates: list[Record] = []
    for reference in entry.supporting:
        raw = registry.history.evidence.read(reference.receipt())
        try:
            document = _json(raw)
        except (ValueError, TypeError, UnicodeError):
            continue
        if not isinstance(document, dict) or document.get("format") != VERSION:
            continue
        try:
            record = Record.model_validate_json(raw)
        except (ValidationError, ValueError, TypeError):
            raise RiskInputError("invalid_risk_input_record") from None
        if _bytes(record.model_dump(mode="json")) != raw:
            raise RiskInputError("noncanonical_risk_input_record")
        candidates.append(record)
    if len(candidates) != 1:
        raise RiskInputError("risk_input_record_missing")
    record = candidates[0]
    required = {
        reference.reference: reference
        for reference in (
            record.request.basket,
            record.request.taxonomy,
            record.request.profile,
            record.request.limits,
            *record.request.sources,
        )
    }
    supporting = {reference.reference: reference for reference in entry.supporting}
    if any(supporting.get(key) != value for key, value in required.items()):
        raise RiskInputError("risk_required_source_omitted")
    expected = _assessment(registry, record.request, entries)
    if (
        record.history != entry.manifest
        or entries[record.request.history_id].selection != entry.selection
        or _bytes(record.model_dump(mode="json")) != _bytes(expected.model_dump(mode="json"))
    ):
        raise RiskInputError("risk_input_replay_mismatch")
    return record


def verify_dependencies(registry: HistoryRegistry, entries: dict[str, Dependency]) -> None:
    """Recompute registered assembly consumers under the caller's writer guard."""
    for entry in entries.values():
        for reference in entry.supporting:
            raw = registry.history.evidence.read(reference.receipt())
            try:
                document = _json(raw)
            except (ValueError, TypeError, UnicodeError):
                continue
            if isinstance(document, dict) and document.get("format") == VERSION:
                _record(registry, entry, entries)
                break


def _step(name: str) -> None:
    """Fault injection at actual immutable publication/registration boundaries."""


def publish(registry: HistoryRegistry, assembly_id: str, request: Request) -> Record:
    request = Request.model_validate_json(request.model_dump_json())
    TypeAdapter(Identifier).validate_python(assembly_id, strict=True)
    with history_writer(registry.runtime):
        with registry._connection() as connection:
            connection.execute("BEGIN")
            entries = {e.dependency_id: e for e in registry._proof(connection).dependencies}
        if assembly_id in entries:
            record = _record(registry, entries[assembly_id], entries)
            if record.request != request:
                raise RiskInputError("risk_assembly_conflict")
            return record
        if assembly_id == request.history_id:
            raise RiskInputError("risk_self_dependency")
        record = _assessment(registry, request, entries)
        _step("assembly_verified")
        support = {
            reference.reference: reference
            for reference in (
                request.basket,
                request.taxonomy,
                request.profile,
                request.limits,
                *request.sources,
            )
        }
        retained = h.RawReference.from_receipt(
            registry.history.evidence.publish(_bytes(record.model_dump(mode="json")))
        )
        support[retained.reference] = retained
        _step("record_published")
        registry._register(
            Dependency(
                format="synthetic-history-dependency-v2",
                dependency_id=assembly_id,
                manifest=record.history,
                selection=entries[request.history_id].selection,
                supporting=tuple(support[k] for k in sorted(support)),
            )
        )
        _step("assembly_registered")
        return record


def replay(registry: HistoryRegistry, assembly_id: str) -> Record:
    with history_writer(registry.runtime):
        with registry._connection() as connection:
            connection.execute("BEGIN")
            entries = {e.dependency_id: e for e in registry._proof(connection).dependencies}
        if assembly_id not in entries:
            raise RiskInputError("risk_assembly_missing")
        return _record(registry, entries[assembly_id], entries)
