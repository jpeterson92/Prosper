"""Read-only inspection of retained source facts, before financial review.

Small ordered Python traversal preserves JSON token types and nested values;
there is no tabular aggregation or financial calculation in this view.
"""

import json
from typing import Literal

from pydantic import Field

from prosper import blackrock
from prosper import vanguard as v
from prosper.advisory_records import Record
from prosper.benchmark import BenchmarkObservation, acquisition
from prosper.storage import PersistenceError


class SourceCell(Record):
    name: str
    kind: Literal["string", "number", "null", "boolean", "object", "array"]
    value: str
    origin: Literal["source", "adapter"] = "source"


class SourceRow(Record):
    section: str
    index: int
    source_ref: str | None
    cells: tuple[SourceCell, ...]
    issues: tuple[str, ...]


class SourceIssueGroup(Record):
    code: str
    occurrences: int
    affected_rows: int
    details: tuple[str, ...]


class BenchmarkSourcePage(Record):
    rows_available: bool
    section_counts: dict[str, int]
    issue_groups: tuple[SourceIssueGroup, ...]
    total_rows: int | None
    matched_rows: int | None
    offset: int
    limit: int
    rows: tuple[SourceRow, ...]


class BenchmarkRowsRequest(Record):
    observation_id: str = Field(min_length=1, max_length=200)
    section: str = Field(default="", max_length=200)
    query: str = Field(default="", max_length=200)
    issue: str = Field(default="", max_length=200)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


def _json(value: v.JsonValue) -> str:
    if isinstance(value, v.JsonNumber):
        return str(value)
    if isinstance(value, v.JsonObject):
        return "{" + ",".join(json.dumps(k) + ":" + _json(x) for k, x in value.fields) + "}"
    if isinstance(value, tuple):
        return "[" + ",".join(_json(x) for x in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def _cell(name: str, value: v.JsonValue, *, adapter: bool = False) -> SourceCell:
    kind: Literal["string", "number", "null", "boolean", "object", "array"]
    if isinstance(value, v.JsonNumber):
        kind = "number"
    elif isinstance(value, str):
        kind = "string"
    elif value is None:
        kind = "null"
    elif isinstance(value, bool):
        kind = "boolean"
    elif isinstance(value, v.JsonObject):
        kind = "object"
    else:
        kind = "array"
    return SourceCell(
        name=name,
        kind=kind,
        value=str(value) if isinstance(value, str) else _json(value),
        origin="adapter" if adapter else "source",
    )


def source_page(
    observation: BenchmarkObservation,
    raw: bytes | None,
    *,
    section: str = "",
    query: str = "",
    issue: str = "",
    offset: int = 0,
    limit: int = 50,
) -> BenchmarkSourcePage:
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError("invalid_source_page")
    snapshot = None
    if observation.status == "observed":
        if raw is None:
            raise PersistenceError("benchmark_source_unavailable")
        snapshot = acquisition(observation, raw).snapshot
        if snapshot is None or snapshot.raw_sha256 != observation.source_sha256:
            raise PersistenceError("benchmark_source_unavailable")
    counts = {s.name: len(s.rows) for s in snapshot.sections} if snapshot else {}
    # A section issue retains its original detail; unknown-weight row locations
    # come from the adapter's explicit unknown list, never a zero-filled value.
    details: dict[str, list[str]] = {}
    located: dict[tuple[str, int], list[str]] = {}
    affected: dict[str, set[tuple[str, int]]] = {}
    for detail in observation.issues:
        code, *parts = detail.split(":")
        details.setdefault(code, []).append(detail)
        affected.setdefault(code, set())
        if len(parts) >= 2 and parts[0] in counts and parts[1].isdigit():
            key = (parts[0], int(parts[1]))
            if key[1] < counts[key[0]]:
                located.setdefault(key, []).append(detail)
                affected[code].add(key)
    if snapshot:
        for s in snapshot.sections:
            detail = f"unknown_weights:{s.name}"
            if detail in observation.issues:
                for index in s.unknown_weight_rows:
                    key = (s.name, index)
                    located.setdefault(key, []).append(detail)
                    affected["unknown_weights"].add(key)
    groups = tuple(
        SourceIssueGroup(
            code=code,
            occurrences=len(values),
            affected_rows=len(affected[code]),
            details=tuple(values),
        )
        for code, values in details.items()
    )
    matched = 0
    rows: list[SourceRow] = []
    needle = query.casefold()
    if snapshot:
        csv_source = isinstance(snapshot.selection, blackrock.Selection)
        columns = set(blackrock.COLUMNS) | set(blackrock.ALTERNATE_COLUMNS)
        for s in snapshot.sections:
            if section and s.name != section:
                continue
            for index, value in enumerate(s.rows):
                key = (s.name, index)
                row_issues = tuple(located.get(key, ()))
                if issue and (key not in affected.get(issue, set())):
                    continue
                fields = value.fields if isinstance(value, v.JsonObject) else (("(row)", value),)
                if needle and not any(
                    needle in name.casefold()
                    or needle in _json(cell).casefold()
                    or (isinstance(cell, str) and needle in cell.casefold())
                    for name, cell in fields
                    if not csv_source or name in columns
                ):
                    continue
                if offset <= matched < offset + limit:
                    ref = (
                        value.get("source_ref")
                        if csv_source and isinstance(value, v.JsonObject)
                        else None
                    )
                    rows.append(
                        SourceRow(
                            section=s.name,
                            index=index,
                            source_ref=ref if isinstance(ref, str) else None,
                            cells=tuple(
                                _cell(name, cell, adapter=csv_source and name not in columns)
                                for name, cell in fields
                            ),
                            issues=row_issues,
                        )
                    )
                matched += 1
    return BenchmarkSourcePage(
        rows_available=snapshot is not None,
        section_counts=counts,
        issue_groups=groups,
        total_rows=sum(counts.values()) if snapshot else None,
        matched_rows=matched if snapshot else None,
        offset=offset,
        limit=limit,
        rows=tuple(rows),
    )
