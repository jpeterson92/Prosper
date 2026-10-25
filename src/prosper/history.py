"""Closed fictional history records and immutable publication, without acquisition.

Coverage is stipulated-calendar engineering evidence, never financial readiness.
The separate child runtime has no foundation database, cleanup or recovery API.
EvidenceStore's local-filesystem/no-hostile-path-replacement limitations apply.
"""

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from prosper.bundle import MAX_BYTES
from prosper.evidence import EvidenceError, EvidenceReceipt, EvidenceStore, RuntimeBoundary
from prosper.exact import ExactValue, ExactValueError, Sign
from prosper.history_coordination import history_writer

VERSION: Literal["synthetic-history-v1"] = "synthetic-history-v1"
Text = Annotated[str, Field(min_length=1, max_length=1024)]


class HistoryError(ValueError):
    """Stable code without paths, source payloads or validation input echoes."""


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _day(value: str) -> str:
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("iso_date_required")
    return value


def _instant(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if not value.endswith("Z") or parsed.utcoffset() is None:
        raise ValueError("utc_instant_required")
    # One spelling makes chronological string comparisons unambiguous.
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("utc_second_precision_required")
    return value


class SeriesContext(Closed):
    security_id: Text
    provider: Text
    dataset: Text
    permission_scope: Text
    provider_symbol: Text
    mapping_start: Text
    mapping_end: Text
    currency: Text
    calendar: Text
    timezone: Text
    interval: Text
    adjustment: Text
    repair: Text
    source_schema: Text
    transform_version: Text
    library_version: Text
    return_convention: Text
    return_transform_version: Text
    vintage: Text
    captured_at: Text

    @model_validator(mode="after")
    def dates(self) -> Self:
        _day(self.mapping_start)
        _day(self.mapping_end)
        _instant(self.captured_at)
        if self.mapping_start > self.mapping_end:
            raise ValueError("invalid_mapping_window")
        return self


class Selection(Closed):
    series: Annotated[tuple[SeriesContext, ...], Field(min_length=1, max_length=1000)]
    sessions: Annotated[tuple[Text, ...], Field(min_length=1, max_length=10000)]
    cutoff: Text
    known_at: Text
    calendar_evidence: Text

    @model_validator(mode="after")
    def grid(self) -> Self:
        _day(self.cutoff)
        _instant(self.known_at)
        if len({s.security_id for s in self.series}) != len(self.series):
            raise ValueError("duplicate_series")
        if tuple(sorted(set(self.sessions))) != self.sessions:
            raise ValueError("ordered_unique_sessions_required")
        for session in self.sessions:
            _day(session)
        if self.sessions[-1] > self.cutoff or self.cutoff > self.known_at[:10]:
            raise ValueError("invalid_cutoff")
        if len(self.sessions) * len(self.series) > 10000:
            raise ValueError("grid_size_exceeded")
        for series in self.series:
            if series.captured_at > self.known_at:
                raise ValueError("future_capture")
            if (
                not series.mapping_start
                <= self.sessions[0]
                <= self.sessions[-1]
                <= series.mapping_end
            ):
                raise ValueError("mapping_does_not_cover_selection")
        return self


class RawReference(Closed):
    sha256: Text
    byte_length: int
    reference: Text
    storage_version: Text

    @classmethod
    def from_receipt(cls, receipt: EvidenceReceipt) -> Self:
        return cls(
            sha256=receipt.raw_sha256,
            byte_length=receipt.byte_length,
            reference=receipt.relative_reference,
            storage_version=receipt.storage_version,
        )

    def receipt(self) -> EvidenceReceipt:
        return EvidenceReceipt(self.sha256, self.byte_length, self.reference, self.storage_version)

    @model_validator(mode="after")
    def identity(self) -> Self:
        self.receipt()
        return self


class Source(Closed):
    source_id: Text
    context: SeriesContext
    raw: RawReference
    validated_at: Text
    outcome: Literal["complete", "partial", "empty", "failed"]
    reason: Text | None = None

    @model_validator(mode="after")
    def outcome_reason(self) -> Self:
        _instant(self.validated_at)
        if self.validated_at < self.context.captured_at:
            raise ValueError("validation_precedes_capture")
        if self.outcome != "complete" and self.reason is None:
            raise ValueError("source_reason_required")
        return self


class Fact(Closed):
    text: Text | None = None
    unknown_reason: Text | None = None

    @model_validator(mode="after")
    def knowledge(self) -> Self:
        if (self.text is None) == (self.unknown_reason is None):
            raise ValueError("exact_text_or_unknown_reason_required")
        return self


class Observation(Closed):
    security_id: Text
    session: Text
    source_id: Text
    source_row: Text
    open: Fact
    high: Fact
    low: Fact
    close: Fact
    adjusted_close: Fact
    dividend: Fact
    split_ratio: Fact
    total_return: Fact
    return_from_session: Text | None

    @model_validator(mode="after")
    def dates(self) -> Self:
        _day(self.session)
        if self.return_from_session is not None:
            _day(self.return_from_session)
        return self


class Envelope(Closed):
    selection: Selection
    sources: Annotated[tuple[Source, ...], Field(max_length=10000)]
    observations: Annotated[tuple[Observation, ...], Field(max_length=10000)]
    diagnostics: Annotated[tuple[Text, ...], Field(max_length=1000)] = ()

    @model_validator(mode="after")
    def references(self) -> Self:
        sources = {s.source_id: s for s in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("duplicate_source_id")
        contexts = {s.security_id: s for s in self.selection.series}
        for source in self.sources:
            if contexts.get(source.context.security_id) != source.context:
                raise ValueError("incompatible_source_context")
            if source.validated_at > self.selection.known_at:
                raise ValueError("future_validation")
        for row in self.observations:
            if row.source_id not in sources:
                raise ValueError("missing_source_reference")
        return self


class Cell(Closed):
    security_id: Text
    session: Text


class Issue(Closed):
    location: Text
    code: Text
    reason: Text | None = None


class Coverage(Closed):
    requested: tuple[Cell, ...]
    received: tuple[Cell, ...]
    usable: tuple[Cell, ...]
    issues: tuple[Issue, ...]
    complete: bool


def coverage(data: Envelope) -> Coverage:
    """Account for every row; no sorting/merging/filling of source observations."""
    requested = tuple(
        Cell(security_id=s.security_id, session=d)
        for s in data.selection.series
        for d in data.selection.sessions
    )
    expected = {(c.security_id, c.session) for c in requested}
    counts = Counter((r.security_id, r.session) for r in data.observations)
    sources = {s.source_id: s for s in data.sources}
    issues: list[Issue] = []
    received: set[tuple[str, str]] = set()
    usable: set[tuple[str, str]] = set()

    def issue(location: str, code: str, reason: str | None = None) -> None:
        issues.append(Issue(location=location, code=code, reason=reason))

    for j, source in enumerate(data.sources):
        if source.outcome != "complete" or source.reason is not None:
            issue(f"sources/{j}", f"source_{source.outcome}", source.reason)
    for j, diagnostic in enumerate(data.diagnostics):
        issue(f"diagnostics/{j}", "retained_diagnostic", diagnostic)
    for j, row in enumerate(data.observations):
        key = (row.security_id, row.session)
        location = f"observations/{j}"
        before = len(issues)
        if key not in expected:
            issue(location, "outside_selected_grid")
        else:
            received.add(key)
        if counts[key] > 1:
            issue(location, "duplicate_observation")
        source = sources[row.source_id]
        if source.context.security_id != row.security_id:
            issue(location, "source_security_mismatch")
        if source.outcome in ("failed", "empty"):
            issue(location, "unusable_source_outcome", source.reason)
        values: dict[str, ExactValue] = {}
        for name, sign in (
            ("open", Sign.POSITIVE),
            ("high", Sign.POSITIVE),
            ("low", Sign.POSITIVE),
            ("close", Sign.POSITIVE),
            ("adjusted_close", Sign.POSITIVE),
            ("dividend", Sign.NONNEGATIVE),
            ("split_ratio", Sign.POSITIVE),
            ("total_return", Sign.SIGNED),
        ):
            fact: Fact = getattr(row, name)
            if fact.text is None:
                issue(f"{location}/{name}", "unknown_fact", fact.unknown_reason)
            else:
                try:
                    values[name] = ExactValue(fact.text, sign)
                except ExactValueError as exc:
                    issue(f"{location}/{name}", "unsupported_decimal", exc.code)
        if all(n in values for n in ("open", "high", "low", "close")):
            if not (
                values["low"].value
                <= min(values["open"].value, values["close"].value)
                <= max(values["open"].value, values["close"].value)
                <= values["high"].value
            ):
                issue(location, "contradictory_ohlc")
        if row.return_from_session is None or row.return_from_session >= row.session:
            issue(location, "invalid_return_boundary")
        if "total_return" in values and values["total_return"].value < -1:
            issue(location, "return_below_minus_one")
        if len(issues) == before:
            usable.add(key)
    for cell in requested:
        if (cell.security_id, cell.session) not in received:
            issue(f"grid/{cell.security_id}/{cell.session}", "missing_observation")
    return Coverage(
        requested=requested,
        received=tuple(c for c in requested if (c.security_id, c.session) in received),
        usable=tuple(c for c in requested if (c.security_id, c.session) in usable),
        issues=tuple(issues),
        complete=not issues and usable == expected,
    )


class Manifest(Closed):
    schema_version: Literal["synthetic-history-v1"] = VERSION
    envelope: Envelope
    coverage: Coverage

    @model_validator(mode="after")
    def derived_coverage(self) -> Self:
        if self.coverage != coverage(self.envelope):
            raise ValueError("coverage_mismatch")
        return self


def canonical_bytes(manifest: Manifest) -> bytes:
    return json.dumps(
        manifest.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


@dataclass(frozen=True)
class FrozenHistory:
    receipt: EvidenceReceipt
    manifest: Manifest

    @property
    def snapshot_sha256(self) -> str:
        return self.receipt.raw_sha256


class HistoryStore:
    """Explicit synthetic-only runtime, with all objects beneath a child namespace.

    Receipt return is the publication boundary; raw orphan/staging objects are
    never snapshots. No catalog, activation pointer, automatic repair or pruning.
    Readers require the externally retained receipt, verifying all dependencies.
    """

    def __init__(self, runtime: RuntimeBoundary, *, existing: bool = False) -> None:
        runtime.check()
        if runtime.mode != "synthetic":
            raise HistoryError("synthetic_history_only")
        self.runtime = runtime
        self._check_ready()
        isolated = RuntimeBoundary(runtime.path(VERSION), runtime.source_root, runtime.mode)
        self.evidence = EvidenceStore.existing(isolated) if existing else EvidenceStore(isolated)

    def _check_ready(self) -> None:
        if self.runtime.path("history-restore-in-progress").exists():
            raise HistoryError("history_restore_in_progress")

    def retain(self, raw: bytes) -> RawReference:
        self._check_ready()
        with history_writer(self.evidence.runtime, create=True):
            return RawReference.from_receipt(self.evidence.publish(raw))

    def publish(self, data: Envelope) -> FrozenHistory:
        self._check_ready()
        with history_writer(self.evidence.runtime, create=True):
            return self._publish(data)

    def _publish(self, data: Envelope) -> FrozenHistory:
        if not isinstance(data, Envelope):
            raise HistoryError("history_envelope_required")
        # Revalidate even instances built through Pydantic's unchecked copy APIs.
        try:
            data = Envelope.model_validate_json(data.model_dump_json())
        except (ValidationError, EvidenceError, ValueError):
            raise HistoryError("invalid_history_envelope") from None
        for source in data.sources:
            self.evidence.read(source.raw.receipt())
        manifest = Manifest(envelope=data, coverage=coverage(data))
        raw = canonical_bytes(manifest)
        receipt = self.evidence.publish(raw)
        return self.read(receipt)

    def read(self, receipt: EvidenceReceipt, *, expected: Selection | None = None) -> FrozenHistory:
        self._check_ready()
        raw = self.evidence.read(receipt)
        if len(raw) > MAX_BYTES:
            raise HistoryError("manifest_size_exceeded")
        try:
            manifest = Manifest.model_validate_json(raw)
        except (ValidationError, EvidenceError, ValueError, RecursionError):
            raise HistoryError("invalid_history_manifest") from None
        if canonical_bytes(manifest) != raw:
            raise HistoryError("noncanonical_history_manifest")
        if expected is not None and manifest.envelope.selection != expected:
            raise HistoryError("incompatible_history_selection")
        for source in manifest.envelope.sources:
            self.evidence.read(source.raw.receipt())
        if hashlib.sha256(raw).hexdigest() != receipt.raw_sha256:
            raise HistoryError("manifest_identity_mismatch")
        return FrozenHistory(receipt, manifest)
