"""Declared combined-file observations, never an authoritative checkpoint or tax model."""

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from prosper.exact import ExactValue, ExactValueError, Sign

FORMAT_VERSION: Literal["fidelity-combined-lots-observation-v1"] = (
    "fidelity-combined-lots-observation-v1"
)
MAX_BYTES = 2 * 1024 * 1024
MAX_RECORDS = 10_000
MAX_FIELD = 4096
MAX_ISSUES = 100
COLUMNS = (
    "Account number",
    "Account name",
    "Symbol",
    "Security description",
    "Source file",
    "Source CSV row",
    "Source download date",
    "Acquired",
    "Term",
    "$ Total gain/loss",
    "% Total gain/loss",
    "Current value",
    "Quantity",
    "Average cost basis",
    "Cost basis total",
)
BLOCKERS = (
    "source_exports_unverified",
    "account_profile_unqualified",
    "security_identity_unqualified",
    "currency_unqualified",
    "lot_identity_not_durable",
    "basis_adjustments_unqualified",
    "holding_evidence_unqualified",
    "snapshot_boundary_unknown",
    "independent_positions_missing",
    "cash_missing",
    "activity_coverage_missing",
    "execution_evidence_missing",
    "reported_financial_values_unreconciled",
)
_NUMBER = r"(?:[0-9]+|[1-9][0-9]{0,2}(?:,[0-9]{3})+)(?:\.[0-9]+)?"
_MONTHS = {
    month: index
    for index, month in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
        1,
    )
}


@dataclass(frozen=True)
class Observed[T]:
    source_text: str = field(repr=False)
    value: T | None = field(repr=False)
    reason: str | None


@dataclass(frozen=True)
class LotIssue:
    code: str
    record: int | None = None
    column: str | None = None


@dataclass(frozen=True)
class LotObservation:
    record: int
    source_record: int | None
    source_fields: tuple[str, ...] = field(repr=False)
    acquired: Observed[str] = field(repr=False)
    quantity: Observed[ExactValue] = field(repr=False)
    reported_basis: Observed[ExactValue] = field(repr=False)
    average_basis: Observed[ExactValue] = field(repr=False)
    current_value: Observed[ExactValue] = field(repr=False)
    display_gain_loss: Observed[ExactValue] = field(repr=False)
    display_gain_percent: Observed[ExactValue] = field(repr=False)


@dataclass(frozen=True)
class LotInspection:
    raw_sha256: str | None
    header: tuple[str, ...] = field(repr=False)
    records: tuple[tuple[str, ...], ...] = field(repr=False)
    observations: tuple[LotObservation, ...] = field(repr=False)
    issues: tuple[LotIssue, ...]
    further_issues: bool
    input_truncated: bool

    @property
    def format_version(self) -> Literal["fidelity-combined-lots-observation-v1"]:
        return FORMAT_VERSION

    @property
    def status(self) -> Literal["observed_unqualified", "invalid"]:
        return "invalid" if self.issues or self.input_truncated else "observed_unqualified"

    @property
    def planning_ready(self) -> Literal[False]:
        return False

    @property
    def canonical_checkpoint_ready(self) -> Literal[False]:
        return False

    @property
    def blocking_reasons(self) -> tuple[str, ...]:
        return BLOCKERS


def _missing(raw: str) -> str | None:
    if raw == "":
        return "source_value_missing"
    if raw == "--":
        return "source_value_unknown"
    return None


def _numeric(
    raw: str, kind: Literal["money", "quantity", "percent"], sign: Sign
) -> tuple[Observed[ExactValue], str | None]:
    if reason := _missing(raw):
        return Observed(raw, None, reason), None
    pattern = {"money": rf"[+-]?\${_NUMBER}", "quantity": _NUMBER, "percent": rf"[+-]?{_NUMBER}%"}
    if re.fullmatch(pattern[kind], raw, re.ASCII) is None:
        return Observed(raw, None, "unsupported_numeric_format"), "unsupported_numeric_format"
    token = raw.replace("$", "").replace(",", "").removesuffix("%").removeprefix("+")
    try:
        return Observed(raw, ExactValue(token, sign), None), None
    except ExactValueError as error:
        return Observed(raw, None, error.code), error.code


def _acquired(raw: str) -> tuple[Observed[str], str | None]:
    if reason := _missing(raw):
        return Observed(raw, None, reason), None
    match = re.fullmatch(r"([A-Za-z]{3})-([0-9]{1,2})-([0-9]{4})", raw, re.ASCII)
    if match is not None:
        month = _MONTHS.get(match[1].lower())
        if month is not None:
            try:
                return Observed(
                    raw, date(int(match[3]), month, int(match[2])).isoformat(), None
                ), None
            except ValueError:
                pass
    return Observed(raw, None, "unsupported_acquired_date"), "unsupported_acquired_date"


def inspect_combined_lots(raw: bytes) -> LotInspection:
    """Inspect source bytes, with no file access or state mutation.

    Percentage values are display percentage points; dollar signs do not prove USD.
    Original bytes stay with the caller; bounded raw records remain in the result.
    """
    issues: list[LotIssue] = []
    more = False
    truncated = False
    header: tuple[str, ...] = ()
    records: list[tuple[str, ...]] = []
    observations: list[LotObservation] = []
    digest = hashlib.sha256(raw).hexdigest() if len(raw) <= MAX_BYTES else None

    def issue(code: str, record: int | None = None, column: str | None = None) -> None:
        nonlocal more
        if len(issues) < MAX_ISSUES:
            issues.append(LotIssue(code, record, column))
        else:
            more = True

    def result() -> LotInspection:
        return LotInspection(
            digest,
            header,
            tuple(records),
            tuple(observations),
            tuple(issues),
            more,
            truncated,
        )

    if len(raw) > MAX_BYTES:
        issue("byte_limit_exceeded")
        return result()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        issue("invalid_utf8")
        return result()

    seen: dict[tuple[str, str, int], tuple[str, ...]] = {}
    source_metadata: dict[str, tuple[str, ...]] = {}
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = tuple(next(reader, ()))
        if header != COLUMNS:
            issue("unsupported_header", 1)
        for record, fields in enumerate(reader, 2):
            if len(records) == MAX_RECORDS:
                issue("record_limit_exceeded", record)
                truncated = True
                break
            row = tuple(fields)
            records.append(row)
            if any(len(cell) > MAX_FIELD or "\x00" in cell for cell in row):
                issue("unsupported_field", record)
                continue
            if len(row) != len(COLUMNS):
                issue("record_width", record)
                continue
            if header != COLUMNS:
                continue
            for column in range(7):
                if not row[column].strip():
                    issue("missing_metadata", record, COLUMNS[column])
            if row[4] in (".", "..") or any(c in row[4] for c in ("/", "\\", ":")):
                issue("source_basename_required", record, COLUMNS[4])
            source_record = (
                int(row[5]) if re.fullmatch(r"[1-9][0-9]{0,8}", row[5], re.ASCII) else None
            )
            if source_record is None:
                issue("source_record_required", record, COLUMNS[5])
            else:
                key = (row[0], row[4], source_record)
                if previous := seen.get(key):
                    issue(
                        "duplicate_source_reference"
                        if previous == row
                        else "conflicting_source_reference",
                        record,
                    )
                else:
                    seen[key] = row
            metadata = row[:4] + (row[6],)
            if row[4] in source_metadata and source_metadata[row[4]] != metadata:
                issue("source_file_metadata_conflict", record)
            else:
                source_metadata[row[4]] = metadata
            acquired, error = _acquired(row[7])
            if error:
                issue(error, record, COLUMNS[7])
            numbers: dict[int, Observed[ExactValue]] = {}
            numeric_specs: tuple[tuple[int, Literal["money", "quantity", "percent"], Sign], ...] = (
                (9, "money", Sign.SIGNED),
                (10, "percent", Sign.SIGNED),
                (11, "money", Sign.NONNEGATIVE),
                (12, "quantity", Sign.NONNEGATIVE),
                (13, "money", Sign.NONNEGATIVE),
                (14, "money", Sign.NONNEGATIVE),
            )
            for column, kind, sign in numeric_specs:
                value, error = _numeric(row[column], kind, sign)
                numbers[column] = value
                if error:
                    issue(error, record, COLUMNS[column])
            observations.append(
                LotObservation(
                    record,
                    source_record,
                    row,
                    acquired,
                    numbers[12],
                    numbers[14],
                    numbers[13],
                    numbers[11],
                    numbers[9],
                    numbers[10],
                )
            )
    except csv.Error:
        issue("malformed_csv", len(records) + 2)
        truncated = True
    if header == COLUMNS and not records:
        issue("no_lot_records")
    return result()
