"""Retained-source bindings and policy drafts for the existing review record."""

from datetime import date

from prosper import benchmark_reconciliation as r
from prosper import vanguard as v
from prosper.advisory_records import Digest, Record
from prosper.benchmark import BenchmarkObservation, acquisition
from prosper.benchmark_mapping import PreparedMapping, prepare
from prosper.benchmark_metadata import FundMetadata
from prosper.record_types import DateText, Identifier, Timestamp
from prosper.storage import PersistenceError


class ReviewContextRequest(Record):
    observation_id: Identifier


class ReviewSection(Record):
    section: str
    row_count: int | None
    fields: tuple[str, ...]


class ReviewRow(Record):
    section: str
    index: int
    row_sha256: Digest
    source_name: str | None
    source_ticker: str | None


class BenchmarkReviewContext(Record):
    observation_id: Identifier
    source_sha256: Digest
    ticker: str
    port_id: str
    requested_date: DateText | None
    effective_date: DateText
    collected_at: Timestamp
    sections: tuple[ReviewSection, ...]
    rows: tuple[ReviewRow, ...]
    mapping: PreparedMapping | None
    metadata: FundMetadata | None


def review_context(observation: BenchmarkObservation, raw: bytes) -> BenchmarkReviewContext:
    snapshot = acquisition(observation, raw).snapshot
    if (
        observation.status != "observed"
        or snapshot is None
        or snapshot.raw_sha256 != observation.source_sha256
    ):
        raise PersistenceError("benchmark_source_unavailable")
    holdings = snapshot.document.get(snapshot.effective_date.isoformat())
    if not isinstance(holdings, v.JsonObject):
        raise PersistenceError("benchmark_source_unavailable")
    sections: list[ReviewSection] = []
    rows: list[ReviewRow] = []
    # Ordered structural traversal, not financial tabular aggregation. Keep
    # non-array sections and invalid rows visible; no role or identity is inferred.
    for name, values in holdings.fields:
        fields: dict[str, None] = {}
        if isinstance(values, tuple):
            for index, value in enumerate(values):
                if isinstance(value, v.JsonObject):
                    fields.update(dict.fromkeys(key for key, _ in value.fields))
                    source_name = value.get("holdingName")
                    source_ticker = value.get("ticker")
                else:
                    source_name = source_ticker = None
                rows.append(
                    ReviewRow(
                        section=name,
                        index=index,
                        row_sha256=r.row_identity(value),
                        source_name=source_name if type(source_name) is str else None,
                        source_ticker=source_ticker if type(source_ticker) is str else None,
                    )
                )
        sections.append(
            ReviewSection(
                section=name,
                row_count=len(values) if isinstance(values, tuple) else None,
                fields=tuple(fields),
            )
        )
    return BenchmarkReviewContext(
        observation_id=observation.request.observation_id,
        source_sha256=snapshot.raw_sha256,
        ticker=snapshot.selection.fund.ticker,
        port_id=snapshot.selection.fund.port_id,
        requested_date=(
            date.isoformat(snapshot.selection.effective_date)
            if snapshot.selection.effective_date
            else None
        ),
        effective_date=snapshot.effective_date.isoformat(),
        collected_at=snapshot.collected_at.isoformat(),
        sections=tuple(sections),
        rows=tuple(rows),
        mapping=prepare(snapshot),
        metadata=observation.metadata,
    )
