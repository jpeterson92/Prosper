"""Explicit fund/date observation and reviewed equity-only proxy records.

Review supplies attributable mappings and section relationships, never guessed
from tickers or values. Selection is separate from fetching and calculation.
"""

import json
from datetime import UTC, date, datetime
from typing import Literal, Self

from pydantic import Field, ValidationInfo, field_validator, model_validator

from prosper import basket as b
from prosper import benchmark_reconciliation as r
from prosper import benchmark_source as sources
from prosper import equity_benchmark as e
from prosper import vanguard as v
from prosper.advisory_records import Digest, Record, Revision
from prosper.benchmark_metadata import MAX_METADATA_BASE64, FundMetadata
from prosper.record_types import DateText, Identifier, Text, Timestamp


class BenchmarkFetch(Record):
    observation_id: Identifier
    ticker: Literal["ITOT", "IVV", "VTI", "VOO"]
    requested_date: DateText | None  # null explicitly requests latest reported


class BenchmarkObservation(Record):
    request: BenchmarkFetch
    collected_at: Timestamp
    status: Literal["pending", "observed", "unavailable"]
    effective_date: DateText | None = None
    source_sha256: Digest | None = None
    http_status: int | None = None
    response_url: str | None = None
    content_type: str | None = None
    body_complete: bool = True
    issues: tuple[str, ...] = ()
    section_counts: dict[str, int] = Field(default_factory=dict)
    request_sha256: Digest
    metadata: FundMetadata | None = None

    @model_validator(mode="after")
    def lifecycle(self) -> Self:
        if self.status == "pending" and any(
            (self.source_sha256, self.http_status, self.effective_date, self.response_url)
        ):
            raise ValueError("pending observation cannot contain a response")
        if self.status == "observed" and (
            self.effective_date is None
            or self.source_sha256 is None
            or self.http_status != 200
            or not self.body_complete
        ):
            raise ValueError("complete observed source required")
        if self.status == "unavailable" and self.effective_date is not None:
            raise ValueError("unavailable observation cannot assert an effective date")
        if self.metadata is not None and (
            self.status != "observed"
            or self.request.ticker != self.metadata.ticker
            or self.effective_date != self.metadata.holdings_date
        ):
            raise ValueError("benchmark_metadata_observation_mismatch")
        return self


class BenchmarkImport(Record):
    request: BenchmarkFetch
    collected_at: Timestamp
    source_base64: str = Field(max_length=2800000, repr=False)
    http_status: int = Field(ge=100, le=599)
    content_type: Text
    response_url: Text
    body_complete: bool

    @field_validator("request", mode="before")
    @classmethod
    def json_request(cls, value: object) -> object:
        return (
            BenchmarkFetch.model_validate_json(json.dumps(value))
            if isinstance(value, dict)
            else value
        )


class BenchmarkReview(Record):
    observation_id: Identifier
    reviewed_at: Timestamp
    stipulation: r.Stipulation
    policy: e.Policy
    metadata_base64: str = Field(max_length=MAX_METADATA_BASE64, repr=False)
    metadata_reference: Text
    metadata_ticker: Literal["ITOT", "IVV", "VTI", "VOO"]
    metadata_port_id: Literal["239724", "239726", "0970", "0968"]
    metadata_cusip: Literal["464287150", "464287200", "922908769", "922908363"]
    metadata_as_of: DateText
    metadata_reviewed: Literal[True]

    @field_validator("stipulation", "policy", mode="before")
    @classmethod
    def json_dataclass(cls, value: object, info: ValidationInfo) -> object:
        # HTTP JSON collections need JSON semantics under strict current records.
        from pydantic import TypeAdapter

        if isinstance(value, dict):
            adapter = TypeAdapter(r.Stipulation if info.field_name == "stipulation" else e.Policy)
            return adapter.validate_json(
                json.dumps(value, allow_nan=False), strict=True, extra="forbid"
            )
        return value


class BenchmarkDiagnostic(Record):
    run_id: Identifier
    expected_revision: Revision
    as_of: Timestamp
    review: BenchmarkReview

    @field_validator("review", mode="before")
    @classmethod
    def json_review(cls, value: object) -> object:
        return (
            BenchmarkReview.model_validate_json(json.dumps(value, allow_nan=False))
            if isinstance(value, dict)
            else value
        )


class BenchmarkSelect(Record):
    run_id: Identifier
    command_key: Identifier
    expected_revision: Revision


class BenchmarkResult(Record):
    kind: Literal["benchmark-proxy-v1"] = "benchmark-proxy-v1"
    label: str = "equity-only disclosed-holdings proxy"
    observation_id: Identifier
    ticker: Literal["ITOT", "IVV", "VTI", "VOO"]
    requested_date: DateText | None
    effective_date: DateText
    collected_at: Timestamp
    reviewed_at: Timestamp
    metadata_reference: Text
    metadata_source_sha256: Digest
    metadata_port_id: str
    metadata_cusip: str
    status: Literal["estimated-equity-benchmark", "incomplete", "unavailable"]
    issues: tuple[b.Issue, ...]
    ledger: tuple[e.Row, ...]
    source_row_count: int
    included_count: int
    excluded_count: int
    linked_count: int
    unresolved_count: int
    retained_known_value: str
    retained_unknown_values: tuple[r.Locator, ...]
    excluded_known_usd_value: str
    excluded_unknown_usd_values: tuple[r.Locator, ...]
    equity_value_total: str | None
    security_ids: tuple[str, ...]
    weights: tuple[float, ...]
    warnings: tuple[str, ...] = (
        "Disclosed equity proxy only; no exact index or full-fund return replication",
        "Exclusions are not cash; published percentages are preserved separately",
        "Collection time does not establish original publication or point-in-time availability",
        "Identity/source review is supplied evidence; "
        "risk/tax qualification and financial use remain separate",
    )

    @model_validator(mode="after")
    def dimensions(self) -> Self:
        if self.source_row_count != len(self.ledger) or len(self.security_ids) != len(self.weights):
            raise ValueError("benchmark output dimensions disagree")
        if self.status == "estimated-equity-benchmark":
            if self.equity_value_total is None or self.issues or not self.security_ids:
                raise ValueError("successful benchmark output required")
        elif self.weights or self.security_ids or self.equity_value_total is not None:
            raise ValueError("incomplete benchmark cannot supply weights")
        return self


def acquisition(observation: BenchmarkObservation, raw: bytes) -> v.Acquisition:
    selection = sources.select_fund(
        observation.request.ticker,
        date.fromisoformat(observation.request.requested_date)
        if observation.request.requested_date
        else None,
    )
    return sources.acquire(
        selection,
        collected_at=datetime.fromisoformat(observation.collected_at),
        transport=lambda _: v.Response(
            observation.http_status or 0,
            observation.response_url or "",
            observation.content_type or "",
            raw,
            observation.body_complete,
        ),
    )


def review_result(
    observation: BenchmarkObservation, raw: bytes, review: BenchmarkReview, metadata_digest: str
) -> BenchmarkResult:
    source = acquisition(observation, raw)
    if source.snapshot is None or observation.status != "observed":
        raise ValueError("observed_benchmark_required")
    expected = (
        observation.request.ticker,
        source.selection.fund.port_id,
        sources.CUSIPS[observation.request.ticker],
    )
    if (review.metadata_ticker, review.metadata_port_id, review.metadata_cusip) != expected:
        raise ValueError("benchmark_metadata_fund_mismatch")
    if review.metadata_as_of != observation.effective_date:
        raise ValueError("benchmark_metadata_date_mismatch")
    stipulation = review.stipulation
    evidence = (
        stipulation.fund_assertion,
        stipulation.benchmark_cash.evidence,
        *(section.evidence for section in stipulation.sections),
        *(row.evidence for row in stipulation.rows),
        *(row.security.evidence for row in stipulation.rows if row.security),
    )
    if any(
        item.source_sha256 not in (metadata_digest, observation.source_sha256) for item in evidence
    ):
        raise ValueError("benchmark_review_evidence_not_retained")
    # The metadata bytes and exact reviewed locator must substantiate the fund,
    # not the holdings request URL. Other reviewed facts retain their own locators.
    if (
        stipulation.fund_assertion.source_sha256 != metadata_digest
        or stipulation.fund_assertion.reference != review.metadata_reference
        or metadata_digest == observation.source_sha256
    ):
        raise ValueError("benchmark_metadata_binding_required")
    reviewed_at = datetime.fromisoformat(review.reviewed_at)
    if reviewed_at < source.collected_at:
        raise ValueError("benchmark_review_before_collection")
    result = e._select(
        source, stipulation, review.policy, known_at=reviewed_at.astimezone(UTC).date().isoformat()
    )
    rows = result.benchmark_rows or ()
    return BenchmarkResult(
        observation_id=review.observation_id,
        ticker=observation.request.ticker,
        requested_date=observation.request.requested_date,
        effective_date=source.snapshot.effective_date.isoformat(),
        collected_at=observation.collected_at,
        reviewed_at=review.reviewed_at,
        metadata_reference=review.metadata_reference,
        metadata_source_sha256=metadata_digest,
        metadata_port_id=review.metadata_port_id,
        metadata_cusip=review.metadata_cusip,
        status=result.status,  # type: ignore[arg-type]
        issues=result.issues,
        ledger=result.ledger,
        source_row_count=len(result.ledger),
        included_count=sum(row.disposition == "included-equity" for row in result.ledger),
        excluded_count=sum(row.disposition == "excluded" for row in result.ledger),
        linked_count=sum(
            row.disposition in ("linked-alternate", "linked-subset") for row in result.ledger
        ),
        unresolved_count=sum(row.disposition == "unresolved" for row in result.ledger),
        retained_known_value=result.retained_known_value,
        retained_unknown_values=result.retained_unknown_values,
        excluded_known_usd_value=result.excluded_known_usd_value,
        excluded_unknown_usd_values=result.excluded_unknown_usd_values,
        equity_value_total=result.equity_value_total,
        security_ids=tuple(str(row.security.security_id) for row in rows),
        weights=tuple(float(row.weight.raw) for row in rows),  # type: ignore[arg-type]
    )
