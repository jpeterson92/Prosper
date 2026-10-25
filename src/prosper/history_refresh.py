"""Deterministic offline fictional refresh; no network, scheduler or real-provider policy.

An explicitly declared immutable fixture vintage permits exact-context reuse.
Changed overlap/action facts cause one full selected-window refetch per security.
No short overlap proves older history unchanged for a real provider. Raw bodies,
attempts, exact derived returns and scoped successes are required recovery inputs.
"""

import json
import re
from fractions import Fraction
from typing import Annotated, Literal, Protocol, Self

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    ValidationError,
    model_serializer,
    model_validator,
)

from prosper import history as h
from prosper.evidence import EvidenceError
from prosper.exact import ExactValue, Sign
from prosper.history_coordination import history_writer
from prosper.history_registry import Dependency, HistoryRegistry


class RefreshError(EvidenceError):
    """Stable refusal codes, without raw provider payloads or paths."""


class Calendar(h.Closed):
    sessions: Annotated[tuple[h.Text, ...], Field(min_length=1, max_length=10000)]
    predecessor: h.Text

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if tuple(sorted(set(self.sessions))) != self.sessions:
            raise ValueError("ordered_calendar_required")
        for day in (self.predecessor, *self.sessions):
            h._day(day)
        if self.predecessor >= self.sessions[0]:
            raise ValueError("calendar_predecessor_required")
        return self


class Policy(h.Closed):
    format: Literal["fictional-immutable-vintage-policy-v1"] = (
        "fictional-immutable-vintage-policy-v1"
    )
    endpoints: Literal["inclusive"] = "inclusive"
    overlap_sessions: Annotated[int, Field(strict=True, ge=1, le=20)]
    permission_valid_until: h.Text

    @model_validator(mode="after")
    def time(self) -> Self:
        h._instant(self.permission_valid_until)
        return self


class Request(h.Closed):
    selection: h.Selection
    calendar: Calendar
    policy: Policy
    cache_ids: Annotated[tuple[h.Text, ...], Field(max_length=100)] = ()
    mode: Literal["requested", "manual"] = "requested"
    manual_security_ids: tuple[h.Text, ...] = ()

    @model_validator(mode="after")
    def scope(self) -> Self:
        sessions = self.calendar.sessions
        chosen = self.selection.sessions
        if chosen[0] not in sessions or chosen[-1] not in sessions:
            raise ValueError("selection_outside_calendar")
        if sessions[sessions.index(chosen[0]) : sessions.index(chosen[-1]) + 1] != chosen:
            raise ValueError("incomplete_selected_calendar")
        names = {s.security_id for s in self.selection.series}
        if (
            len(set(self.cache_ids)) != len(self.cache_ids)
            or len(set(self.manual_security_ids)) != len(self.manual_security_ids)
            or not set(self.manual_security_ids) <= names
            or (self.mode == "requested" and self.manual_security_ids)
            or (self.mode == "manual" and not self.manual_security_ids)
        ):
            raise ValueError("explicit_unique_refresh_scope_required")
        return self


class Range(h.Closed):
    security_id: h.Text
    sessions: tuple[h.Text, ...]  # inclusive, including preceding/overlap observations
    reason: Literal["gap", "manual", "revision"]


class Body(h.Closed):
    format: Literal["fictional-history-response-v1"] = "fictional-history-response-v1"
    context: h.SeriesContext
    start: h.Text
    end: h.Text
    outcome: Literal["complete", "partial", "empty", "failed"]
    reason: h.Text | None = None
    observations: Annotated[tuple[h.Observation, ...], Field(max_length=10000)]


class Provider(Protocol):
    def fetch(self, request: Range) -> bytes:
        """Return a local fictional Body as original bytes; no live adapter is selected."""


class DerivedReturn(h.Closed):
    security_id: h.Text
    session: h.Text
    predecessor: h.Text
    numerator: h.Text
    denominator: h.Text

    @model_validator(mode="after")
    def exact_ratio(self) -> Self:
        try:
            value = Fraction(int(self.numerator), int(self.denominator))
        except (ValueError, ZeroDivisionError):
            raise ValueError("canonical_return_fraction_required") from None
        if str(value.numerator) != self.numerator or str(value.denominator) != self.denominator:
            raise ValueError("canonical_return_fraction_required")
        return self


class Freshness(h.Closed):
    security_id: h.Text
    last_successful_refresh: h.Text | None = None
    last_successful_broader_validation: h.Text | None = None
    broader_sessions: tuple[h.Text, ...] = ()

    @model_validator(mode="after")
    def explicit_times(self) -> Self:
        for time in (self.last_successful_refresh, self.last_successful_broader_validation):
            if time is not None:
                h._instant(time)
        if (self.last_successful_broader_validation is None) != (not self.broader_sessions):
            raise ValueError("broader_scope_required")
        return self


class Attempt(h.Closed):
    request: Range
    raw: h.RawReference | None
    outcome: h.Text
    changed_overlap: bool = False


class Record(h.Closed):
    format: Literal["synthetic-history-refresh-v1", "synthetic-history-refresh-v2"] = (
        "synthetic-history-refresh-v1"
    )
    request: Request
    snapshot: h.RawReference
    attempts: Annotated[tuple[Attempt, ...], Field(max_length=1000)]
    events: tuple[h.Text, ...]
    returns: tuple[DerivedReturn, ...]
    freshness: tuple[Freshness, ...]
    complete: bool
    scheduled_validation: Literal["Off / Never", "explicit-fictional-dispatch"] = "Off / Never"
    dispatch_event: h.Text | None = None

    @model_serializer(mode="wrap")
    def versioned_trigger(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        document: dict[str, object] = handler(self)
        if self.format == "synthetic-history-refresh-v1":
            document.pop("dispatch_event", None)
        return document

    @model_validator(mode="after")
    def scoped_evidence(self) -> Self:
        legacy = self.format == "synthetic-history-refresh-v1"
        if legacy != (self.dispatch_event is None) or legacy != (
            self.scheduled_validation == "Off / Never"
        ):
            raise ValueError("incompatible_refresh_trigger")
        if tuple(f.security_id for f in self.freshness) != tuple(
            s.security_id for s in self.request.selection.series
        ):
            raise ValueError("ordered_freshness_scope_required")
        for fresh in self.freshness:
            if any(
                time is not None and time > self.request.selection.known_at
                for time in (
                    fresh.last_successful_refresh,
                    fresh.last_successful_broader_validation,
                )
            ):
                raise ValueError("future_refresh_evidence")
            if tuple(sorted(set(fresh.broader_sessions))) != fresh.broader_sessions:
                raise ValueError("invalid_broader_calendar")
            # Historical broader evidence can cover more dates than this request.
            for day in fresh.broader_sessions:
                h._day(day)
        return self


def _bytes(record: h.Closed) -> bytes:
    return json.dumps(
        record.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()


def _previous(request: Request, day: str) -> str:
    index = request.calendar.sessions.index(day)
    return request.calendar.sessions[index - 1] if index else request.calendar.predecessor


def _range(
    request: Request,
    security: str,
    first: str,
    last: str,
    reason: Literal["gap", "manual", "revision"],
) -> Range:
    grid = (request.calendar.predecessor, *request.calendar.sessions)
    start = max(0, grid.index(first) - request.policy.overlap_sessions)
    return Range(security_id=security, sessions=grid[start : grid.index(last) + 1], reason=reason)


def plan(request: Request, usable: set[tuple[str, str]]) -> tuple[Range, ...]:
    """Pure request planner; only explicit calendar positions determine adjacency."""
    result: list[Range] = []
    selected = request.selection.sessions
    for series in request.selection.series:
        security = series.security_id
        if security in request.manual_security_ids:
            result.append(_range(request, security, selected[0], selected[-1], "manual"))
            continue
        gaps = [i for i, day in enumerate(selected) if (security, day) not in usable]
        groups: list[list[int]] = []
        for index in gaps:
            if groups and groups[-1][-1] + 1 == index:
                groups[-1].append(index)
            else:
                groups.append([index])
        result.extend(
            _range(request, security, selected[g[0]], selected[g[-1]], "gap") for g in groups
        )
    if len(result) > 500:
        raise RefreshError("refresh_request_limit")
    return tuple(result)


def _record(registry: HistoryRegistry, dependency: Dependency) -> Record:
    if dependency.format != "synthetic-history-dependency-v2" or not dependency.supporting:
        raise RefreshError("refresh_record_required")
    matches: list[Record] = []
    for item in dependency.supporting:
        raw = registry.history.evidence.read(item.receipt())
        try:
            candidate = Record.model_validate_json(raw)
        except (ValidationError, ValueError):
            continue
        if _bytes(candidate) != raw:
            raise RefreshError("noncanonical_refresh_record")
        matches.append(candidate)
    if len(matches) != 1:
        raise RefreshError("refresh_record_required")
    record = matches[0]
    frozen = registry.history.read(dependency.manifest.receipt(), expected=dependency.selection)
    required = {x.reference for x in dependency.supporting}
    if (
        record.snapshot != dependency.manifest
        or record.request.selection != dependency.selection
        or record.complete != frozen.manifest.coverage.complete
        or any(a.raw is not None and a.raw.reference not in required for a in record.attempts)
    ):
        raise RefreshError("refresh_record_binding_mismatch")
    rows = {(r.security_id, r.session): r for r in frozen.manifest.envelope.observations}
    if len(record.returns) != len(rows) or {
        (r.security_id, r.session) for r in record.returns
    } != set(rows):
        raise RefreshError("refresh_return_binding_mismatch")
    source_map = {s.source_id: s for s in frozen.manifest.envelope.sources}
    for derived in record.returns:
        row = rows[(derived.security_id, derived.session)]
        source = source_map[row.source_id]
        body = _body(registry.history.evidence.read(source.raw.receipt()))
        originals = {r.session: r for r in body.observations}
        previous = _previous(record.request, row.session)
        if (
            body.context != source.context
            or previous not in originals
            or row.session not in originals
        ):
            raise RefreshError("refresh_source_binding_mismatch")
        source_row = originals[row.session]
        if _facts(source_row) != _facts(row) or source_row.source_row != row.source_row:
            raise RefreshError("refresh_source_binding_mismatch")
        current, prior = row.adjusted_close.text, originals[previous].adjusted_close.text
        if current is None or prior is None or Fraction(prior) <= 0:
            raise RefreshError("refresh_return_binding_mismatch")
        expected = Fraction(current) / Fraction(prior) - 1
        if (
            derived.predecessor != previous
            or Fraction(int(derived.numerator), int(derived.denominator)) != expected
        ):
            raise RefreshError("refresh_return_binding_mismatch")
    return record


def replay(registry: HistoryRegistry, operation_id: str) -> Record:
    with history_writer(registry.runtime):
        with registry._connection() as connection:
            connection.execute("BEGIN")
            entries, _ = registry._entries(connection)
            for entry in entries:
                if entry.dependency_id == operation_id:
                    return _record(registry, entry)
    raise RefreshError("refresh_record_missing")


def _step(name: str) -> None:
    """Fault injection at durable response/snapshot/registry boundaries."""


def refresh(
    registry: HistoryRegistry, operation_id: str, request: Request, provider: Provider
) -> Record:
    """One append-only idempotent operation, with fail-fast competing writers.

    A new explicit operation ID is required to retry a recorded failed attempt.
    Completed operation replay makes zero provider calls, including after restore.
    """
    request = _validate_request(operation_id, request)
    with history_writer(registry.runtime):
        return _refresh_locked(registry, operation_id, request, provider)


def _validate_request(operation_id: str, request: Request) -> Request:
    # Validate unchecked model copies and IDs before any provider call or evidence write.
    request = Request.model_validate_json(_bytes(request))
    supported = {
        "adjustment": "fixture-adjusted-close-v1",
        "repair": "none",
        "source_schema": "fictional-history-response-v1",
        "transform_version": "exact-ratio-v1",
        "return_convention": "close-to-close-fraction",
        "return_transform_version": "fixture-adjusted-close-ratio-v1",
    }
    if any(
        getattr(context, key) != value
        for context in request.selection.series
        for key, value in supported.items()
    ):
        raise RefreshError("refresh_unsupported_transform")
    if not isinstance(operation_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", operation_id
    ):
        raise RefreshError("invalid_refresh_operation_id")
    if request.selection.known_at > request.policy.permission_valid_until:
        raise RefreshError("refresh_permission_expired")
    return request


def _refresh_locked(
    registry: HistoryRegistry,
    operation_id: str,
    request: Request,
    provider: Provider,
    *,
    dispatch_event: str | None = None,
) -> Record:
    """Caller holds the shared writer guard; dispatch and manual paths use one core."""
    request = _validate_request(operation_id, request)
    with registry._connection() as connection:
        connection.execute("BEGIN")
        proof = registry._proof(connection)
    entries = {e.dependency_id: e for e in proof.dependencies}
    if operation_id in entries:
        record = _record(registry, entries[operation_id])
        if record.request != request or record.dispatch_event != dispatch_event:
            raise RefreshError("refresh_operation_conflict")
        return record
    if operation_id in request.cache_ids:
        raise RefreshError("refresh_self_dependency")
    contexts = {s.security_id: s for s in request.selection.series}
    rows: dict[tuple[str, str], h.Observation] = {}
    sources: dict[str, h.Source] = {}
    derived: dict[tuple[str, str], DerivedReturn] = {}
    times = {s: Freshness(security_id=s) for s in contexts}
    events: list[str] = []
    conflicts: set[tuple[str, str]] = set()
    comparison_rows: dict[tuple[str, str], h.Observation] = {}
    rebuild_names: set[str] = set()
    for cache_id in request.cache_ids:
        if cache_id not in entries:
            raise RefreshError("refresh_cache_missing")
        prior = _record(registry, entries[cache_id])
        snapshot = registry.history.read(entries[cache_id].manifest.receipt())
        data = snapshot.manifest.envelope
        if data.selection.known_at > request.selection.known_at:
            raise RefreshError("refresh_cache_from_future")
        prior_returns = {(r.security_id, r.session): r for r in prior.returns}
        eligible = {(c.security_id, c.session) for c in snapshot.manifest.coverage.usable}
        for cached_source in data.sources:
            sources[cached_source.source_id] = cached_source
            if cached_source.context != contexts.get(cached_source.context.security_id):
                continue
            body = _body(registry.history.evidence.read(cached_source.raw.receipt()))
            for observed in body.observations:
                key = (observed.security_id, observed.session)
                if key in comparison_rows and _facts(observed) != _facts(comparison_rows[key]):
                    rebuild_names.add(observed.security_id)
                comparison_rows[key] = observed
        for row in data.observations:
            key = (row.security_id, row.session)
            cached_source = next(s for s in data.sources if s.source_id == row.source_id)
            context = cached_source.context
            if row.security_id not in contexts or row.session not in request.selection.sessions:
                continue
            if (
                context != contexts[row.security_id]
                or data.selection.known_at > request.selection.known_at
            ):
                events.append(f"{row.security_id}:incompatible_cache_rebuild")
                continue
            if (
                cached_source.outcome != "complete"
                or key not in eligible
                or key not in prior_returns
                or row.return_from_session != _previous(request, row.session)
            ):
                continue
            if key in rows and _facts(rows[key]) != _facts(row):
                conflicts.add(key)
                continue
            rows[key] = row
            derived[key] = prior_returns[key]
        for fresh in prior.freshness:
            if fresh.security_id in contexts and any(
                s == contexts[fresh.security_id] for s in data.selection.series
            ):
                old = times[fresh.security_id]
                if (fresh.last_successful_refresh or "") > (old.last_successful_refresh or ""):
                    times[fresh.security_id] = fresh
    for key in conflicts:
        rebuild_names.add(key[0])
    for key in list(rows):
        if key[0] not in rebuild_names:
            continue
        rows.pop(key, None)
        derived.pop(key, None)
        events.append(f"{key[0]}:conflicting_cache_rebuild")
    attempts: list[Attempt] = []
    support: dict[str, h.RawReference] = {}
    blocked: set[str] = set()
    calls = plan(request, set(rows))
    by_security = {s: [c for c in calls if c.security_id == s] for s in contexts}
    for security, ranges in by_security.items():
        if not ranges:
            continue
        full = security in request.manual_security_ids or not any(k[0] == security for k in rows)
        pending_rows: dict[tuple[str, str], h.Observation] = {}
        pending_returns: dict[tuple[str, str], DerivedReturn] = {}
        failed = False
        revised = False
        for interval in ranges:
            accepted, returns, source, attempt = _fetch(
                registry, request, interval, provider, comparison_rows | pending_rows
            )
            attempts.append(attempt)
            if attempt.raw:
                support[attempt.raw.reference] = attempt.raw
            if source is not None:
                sources[source.source_id] = source
            if attempt.outcome != "complete":
                failed = True
            revised = revised or attempt.changed_overlap
            for key, row in accepted.items():
                if key in rows and _facts(rows[key]) != _facts(row):
                    revised = True
            pending_rows.update(accepted)
            pending_returns.update(returns)
        if revised and not full:
            events.append(f"{security}:overlap_or_action_changed_full_revalidation")
            interval = _range(
                request,
                security,
                request.selection.sessions[0],
                request.selection.sessions[-1],
                "revision",
            )
            accepted, returns, source, attempt = _fetch(registry, request, interval, provider)
            attempts.append(attempt)
            if attempt.raw:
                support[attempt.raw.reference] = attempt.raw
            if source is not None:
                sources[source.source_id] = source
            pending_rows, pending_returns = accepted, returns
            failed, full = attempt.outcome != "complete", True
        if full:
            for key in list(rows):
                if key[0] == security:
                    del rows[key]
                    derived.pop(key, None)
        rows.update(pending_rows)
        derived.update(pending_returns)
        needed = {(security, d) for d in request.selection.sessions}
        if failed or not needed <= set(rows):
            blocked.add(security)
        else:
            old = times[security]
            # A gap request covering the whole selected window is also broader validation.
            covered = {
                d
                for a in attempts
                if a.request.security_id == security and a.outcome == "complete"
                for d in a.request.sessions
            }
            broader = full or set(request.selection.sessions) <= covered
            times[security] = Freshness(
                security_id=security,
                last_successful_refresh=request.selection.known_at,
                last_successful_broader_validation=request.selection.known_at
                if broader
                else old.last_successful_broader_validation,
                broader_sessions=request.selection.sessions if broader else old.broader_sessions,
            )
    order = [
        (s.security_id, d) for s in request.selection.series for d in request.selection.sessions
    ]
    used = {row.source_id for row in rows.values()}
    envelope = h.Envelope(
        selection=request.selection,
        sources=tuple(sources[s] for s in sorted(used)),
        observations=tuple(rows[k] for k in order if k in rows),
        diagnostics=tuple(f"{s}:refresh_incomplete" for s in sorted(blocked)),
    )
    frozen = registry.history._publish(envelope)
    _step("snapshot_published")
    record = Record(
        format="synthetic-history-refresh-v2" if dispatch_event else "synthetic-history-refresh-v1",
        scheduled_validation="explicit-fictional-dispatch" if dispatch_event else "Off / Never",
        dispatch_event=dispatch_event,
        request=request,
        snapshot=h.RawReference.from_receipt(frozen.receipt),
        attempts=tuple(attempts),
        events=tuple(dict.fromkeys(events)),
        returns=tuple(derived[k] for k in order if k in derived),
        freshness=tuple(times[s.security_id] for s in request.selection.series),
        complete=frozen.manifest.coverage.complete,
    )
    raw_record = h.RawReference.from_receipt(registry.history.evidence.publish(_bytes(record)))
    support[raw_record.reference] = raw_record
    dependency = Dependency(
        format="synthetic-history-dependency-v2",
        dependency_id=operation_id,
        manifest=record.snapshot,
        selection=request.selection,
        supporting=tuple(support[k] for k in sorted(support)),
    )
    _step("record_published")
    registry._register(dependency)
    _step("operation_committed")
    return record


def _facts(row: h.Observation) -> dict[str, object]:
    # Equal numeric spellings do not imply a revision; exact lexemes remain in source rows.
    result: dict[str, object] = {"return_from_session": row.return_from_session}
    for field in (
        "open",
        "high",
        "low",
        "close",
        "adjusted_close",
        "dividend",
        "split_ratio",
        "total_return",
    ):
        fact: h.Fact = getattr(row, field)
        result[field] = (
            Fraction(fact.text) if fact.text is not None else ("unknown", fact.unknown_reason)
        )
    return result


def _body(raw: bytes) -> Body:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result = dict(pairs)
        if len(result) != len(pairs):
            raise RefreshError("duplicate_response_fields")
        return result

    json.loads(raw, object_pairs_hook=unique)
    return Body.model_validate_json(raw)


def _fetch(
    registry: HistoryRegistry,
    request: Request,
    interval: Range,
    provider: Provider,
    cached: dict[tuple[str, str], h.Observation] | None = None,
) -> tuple[
    dict[tuple[str, str], h.Observation],
    dict[tuple[str, str], DerivedReturn],
    h.Source | None,
    Attempt,
]:
    raw_ref: h.RawReference | None = None
    try:
        try:
            raw = provider.fetch(interval)
        except Exception:
            return {}, {}, None, Attempt(request=interval, raw=None, outcome="transport_failed")
        if not isinstance(raw, bytes):
            raise RefreshError("response_bytes_required")
        raw_ref = h.RawReference.from_receipt(registry.history.evidence.publish(raw))
        _step("response_retained")
        body = _body(raw)
        context = next(s for s in request.selection.series if s.security_id == interval.security_id)
        if (
            body.context != context
            or body.start != interval.sessions[0]
            or body.end != interval.sessions[-1]
        ):
            raise RefreshError("response_identity_or_boundary")
        if (body.outcome == "complete" and body.reason is not None) or (
            body.outcome != "complete" and body.reason is None
        ):
            raise RefreshError("response_outcome_reason")
        if body.outcome in ("failed", "empty"):
            return {}, {}, None, Attempt(request=interval, raw=raw_ref, outcome=body.outcome)
        source_id = "refresh-" + raw_ref.sha256
        source = h.Source(
            source_id=source_id,
            context=context,
            raw=raw_ref,
            validated_at=request.selection.known_at,
            outcome=body.outcome,
            reason=body.reason,
        )
        all_rows = {row.session: row for row in body.observations}
        if len(all_rows) != len(body.observations) or any(
            row.security_id != interval.security_id
            or row.source_id != "provider"
            or row.session not in interval.sessions
            for row in body.observations
        ):
            raise RefreshError("response_duplicate_or_outside_range")
        changed = any(
            (row.security_id, row.session) in (cached or {})
            and _facts(row) != _facts((cached or {})[(row.security_id, row.session)])
            for row in body.observations
        )
        accepted: dict[tuple[str, str], h.Observation] = {}
        returns: dict[tuple[str, str], DerivedReturn] = {}
        for row in body.observations:
            if row.session not in request.selection.sessions:
                continue  # Predecessor evidence is retained, not a selected observation.
            previous = _previous(request, row.session)
            if previous not in all_rows or row.return_from_session != previous:
                continue
            probe = h.Envelope(
                selection=request.selection,
                sources=(source,),
                observations=(row.model_copy(update={"source_id": source_id}),),
            )
            if not h.coverage(probe).usable:
                continue
            current, prior = row.adjusted_close.text, all_rows[previous].adjusted_close.text
            if current is None or prior is None or Fraction(prior) <= 0:
                continue
            ExactValue(prior, Sign.POSITIVE)
            value = Fraction(current) / Fraction(prior) - 1
            if row.total_return.text is None or Fraction(row.total_return.text) != value:
                continue
            key = (row.security_id, row.session)
            accepted[key] = row.model_copy(update={"source_id": source_id})
            returns[key] = DerivedReturn(
                security_id=row.security_id,
                session=row.session,
                predecessor=previous,
                numerator=str(value.numerator),
                denominator=str(value.denominator),
            )
        expected = {d for d in interval.sessions[1:] if d in request.selection.sessions}
        complete = (
            body.outcome == "complete"
            and set(all_rows) == set(interval.sessions)
            and expected <= {d for _, d in accepted}
        )
        return (
            accepted,
            returns,
            source,
            Attempt(
                request=interval,
                raw=raw_ref,
                outcome="complete" if complete else "incomplete",
                changed_overlap=changed,
            ),
        )
    except RefreshError:
        return {}, {}, None, Attempt(request=interval, raw=raw_ref, outcome="invalid_response")
    except EvidenceError:
        raise
    except (ValidationError, ValueError, TypeError, ZeroDivisionError, OverflowError):
        return {}, {}, None, Attempt(request=interval, raw=raw_ref, outcome="invalid_response")
