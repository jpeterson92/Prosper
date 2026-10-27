"""Current market observations and explicit ordered-window requirements."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from prosper.advisory_records import Digest, Fact, Record
from prosper.history_table import HistoryTable, SessionGrid
from prosper.record_types import DateText, Identifier, Text, Timestamp


class NumberFact(Fact[float]):
    pass


class SeriesContext(Record):
    security_id: Identifier
    provider: Text
    dataset: Text
    permission_scope: Text
    provider_symbol: Text
    mapping_start: DateText
    mapping_end: DateText
    currency: Text
    calendar: Text
    timezone: Text
    interval: Text
    adjustment: Text
    action_convention: Text
    repair: Text
    source_schema: Text
    transform_version: Text
    return_convention: Text
    vintage: Text
    coherence: Literal["immutable-vintage", "unverified"]
    coherence_evidence: Text

    @model_validator(mode="after")
    def mapping(self) -> Self:
        if self.mapping_start > self.mapping_end:
            raise ValueError("invalid_mapping_window")
        return self


class Observation(Record):
    security_id: Identifier
    session: DateText
    source_ref: Text
    open: NumberFact
    high: NumberFact
    low: NumberFact
    close: NumberFact
    adjusted_close: NumberFact
    action: Fact[str]


class HistoryBatch(Record):
    version: Literal["advisory-history-v2"] = "advisory-history-v2"
    source_name: Text
    source_sha256: Digest
    collected_at: Timestamp
    validated_at: Timestamp
    contexts: Annotated[tuple[SeriesContext, ...], Field(min_length=1, max_length=5000)]
    sessions: SessionGrid

    @property
    def requested_sessions(self) -> tuple[str, ...]:
        return self.sessions.values

    validation_scope: Literal["requested-interval", "full-window"]
    rows: HistoryTable

    @property
    def observations(self) -> tuple[Observation, ...]:
        """Typed view for small analytical/inspection boundaries; storage is columnar."""
        return tuple(_observation(row) for row in self.rows.frame.iter_rows(named=True))

    findings: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def references(self) -> Self:
        from datetime import UTC, datetime

        if datetime.fromisoformat(self.collected_at) > datetime.fromisoformat(self.validated_at):
            raise ValueError("validation_precedes_collection")
        ids = {s.security_id for s in self.contexts}
        if len(ids) != len(self.contexts):
            raise ValueError("duplicate_series")
        if tuple(sorted(set(self.requested_sessions))) != self.requested_sessions:
            raise ValueError("ordered_unique_sessions_required")
        if (
            self.requested_sessions[-1]
            > datetime.fromisoformat(self.collected_at).astimezone(UTC).date().isoformat()
        ):
            raise ValueError("future_source_session")
        if self.rows.kind != "observations":
            raise ValueError("observation_table_required")
        if any(
            s.mapping_start > self.requested_sessions[0]
            or s.mapping_end < self.requested_sessions[-1]
            for s in self.contexts
        ):
            raise ValueError("mapping_does_not_cover_request")
        if not set(self.rows.frame["security_id"]) <= ids or not set(
            self.rows.frame["session"]
        ) <= set(self.requested_sessions):
            raise ValueError("unexpected_observation")
        return self


class Profile(Record):
    identity: Text
    f: Text
    a3: Text
    kappa: Text


class HistoryRequest(Record):
    series: Annotated[tuple[SeriesContext, ...], Field(min_length=1, max_length=5000)]
    sessions: Annotated[tuple[DateText, ...], Field(min_length=1, max_length=10000)]
    predecessor: DateText
    cutoff: DateText
    known_at: Timestamp
    calendar_evidence: Text
    overlap_sessions: Annotated[int, Field(ge=1, le=100)]
    manual_security_ids: tuple[Identifier, ...] = ()
    profile: Profile | None = None

    @model_validator(mode="after")
    def grid(self) -> Self:
        ids = {s.security_id for s in self.series}
        if len(ids) != len(self.series) or tuple(sorted(set(self.sessions))) != self.sessions:
            raise ValueError("unique_series_and_ordered_sessions_required")
        if not self.predecessor < self.sessions[0] <= self.sessions[-1] == self.cutoff:
            raise ValueError("invalid_window")
        if self.cutoff > self.known_at[:10] or (len(self.sessions) + 1) * len(ids) > 650000:
            raise ValueError("future_or_oversized_window")
        if (
            len(set(self.manual_security_ids)) != len(self.manual_security_ids)
            or not set(self.manual_security_ids) <= ids
        ):
            raise ValueError("manual_names_must_be_unique_required_names")
        if any(
            s.mapping_start > self.predecessor or s.mapping_end < self.cutoff for s in self.series
        ):
            raise ValueError("mapping_does_not_cover_request")
        return self


class Interval(Record):
    security_id: Identifier
    sessions: tuple[DateText, ...]
    reason: Literal["new-name", "leading", "interior", "tail", "manual", "coherence"]


class HistoryIssue(Record):
    security_id: Identifier
    session: DateText | None
    code: Text
    reason: Text


class Cell(Record):
    security_id: Identifier
    session: DateText
    source_sha256: Digest | None
    source_ref: Text | None
    observation: Observation | None
    total_return: float | None


class Alignment(Record):
    request: HistoryRequest
    rows: HistoryTable
    issues: tuple[HistoryIssue, ...]
    intervals: tuple[Interval, ...]
    complete: bool
    required_sources: tuple[Digest, ...]
    validated_at: dict[str, str]

    @model_validator(mode="after")
    def dimensions(self) -> Self:
        import polars as pl

        frame = self.rows.frame
        expected = (
            pl.DataFrame({"session": self.request.sessions})
            .join(
                pl.DataFrame({"security_id": [s.security_id for s in self.request.series]}),
                how="cross",
            )
            .select("security_id", "session")
        )
        if self.rows.kind != "alignment" or not frame.select("security_id", "session").equals(
            expected
        ):
            raise ValueError("alignment_grid_order_or_cardinality_invalid")
        if self.complete != (not self.issues and frame["total_return"].null_count() == 0):
            raise ValueError("alignment_status_invalid")
        if not set(frame["source_sha256"].drop_nulls()) <= set(self.required_sources):
            raise ValueError("alignment_sources_missing")
        return self

    @property
    def cells(self) -> tuple[Cell, ...]:
        """Materialize only when a consumer needs typed individual observations."""
        return tuple(
            Cell(
                security_id=row["security_id"],
                session=row["session"],
                source_sha256=row["source_sha256"],
                source_ref=row["source_ref"],
                observation=_observation(row) if row["source_ref"] is not None else None,
                total_return=row["total_return"],
            )
            for row in self.rows.frame.iter_rows(named=True)
        )


def _observation(row: dict[str, object]) -> Observation:
    return Observation.model_validate_json(
        __import__("json").dumps(
            {
                **{name: row[name] for name in ("security_id", "session", "source_ref")},
                **{
                    name: {"value": row[name], "reason": row[name + "_reason"]}
                    for name in ("open", "high", "low", "close", "adjusted_close", "action")
                },
            }
        )
    )
