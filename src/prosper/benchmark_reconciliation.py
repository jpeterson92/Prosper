"""Stipulated full-response reconciliation; no real benchmark activation.

Relationships and identities are attributable inputs, never inferred from equal
values, ticker similarity or section names. Raw acquisition evidence is retained.
"""

import hashlib
import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from prosper import basket as b
from prosper import vanguard as v
from prosper.innovations import fingerprint

VERSION = "benchmark-reconciliation-v1"
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


@dataclass(frozen=True)
class PortfolioContext:
    as_of: str
    known_at: str
    universe: tuple[str, ...]
    positions: tuple[b.Position, ...]
    candidates: tuple[b.Security, ...]
    portfolio_cash: b.Fact


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
    if is_dataclass(value) and not isinstance(value, type):
        return {
            type(value).__name__: [[f.name, encoded(getattr(value, f.name))] for f in fields(value)]
        }
    if isinstance(value, tuple):
        return [encoded(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
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


def _validate_rules(s: Stipulation) -> None:
    if not _hash(s.raw_sha256):
        raise ReconciliationUnavailable("explicit reviewed raw-source binding required")
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
