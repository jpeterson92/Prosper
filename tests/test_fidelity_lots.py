"""Source observation tests, not Fidelity stock export or financial qualification."""

import csv
import hashlib
import io
import json
from dataclasses import FrozenInstanceError
from decimal import localcontext
from fractions import Fraction
from pathlib import Path

import pytest

from prosper.fidelity_lots import (
    BLOCKERS,
    COLUMNS,
    MAX_BYTES,
    MAX_FIELD,
    MAX_ISSUES,
    MAX_RECORDS,
    LotInspection,
    inspect_combined_lots,
)

FIXTURES = Path(__file__).resolve().parents[1] / "examples/synthetic/fidelity"


def fixture(name: str = "combined-stocks") -> bytes:
    return (FIXTURES / f"{name}.csv").read_bytes()


def inspect(raw: bytes | None = None) -> LotInspection:
    return inspect_combined_lots(fixture() if raw is None else raw)


def rows() -> list[list[str]]:
    return list(csv.reader(io.StringIO(fixture().decode("utf-8-sig"))))


def encode(records: list[list[str]]) -> bytes:
    out = io.StringIO(newline="")
    csv.writer(out, lineterminator="\r\n").writerows(records)
    return out.getvalue().encode("utf-8-sig")


def codes(result: LotInspection) -> set[str]:
    return {issue.code for issue in result.issues}


def test_baseline_preserves_every_field_and_exact_independent_totals() -> None:
    result = inspect()
    assert result.status == "observed_unqualified" and result.issues == ()
    assert result.header == COLUMNS
    assert result.raw_sha256 == hashlib.sha256(fixture()).hexdigest()
    assert [list(row) for row in result.records] == rows()[1:]
    assert len(result.observations) == 8
    assert not result.planning_ready and not result.canonical_checkpoint_ready
    assert result.blocking_reasons == BLOCKERS
    assert result.format_version == "fidelity-combined-lots-observation-v1"
    totals = [Fraction(), Fraction(), Fraction(), Fraction()]
    for observation in result.observations:
        assert observation.source_fields == result.records[observation.record - 2]
        for i, measure in enumerate(
            (
                observation.quantity,
                observation.reported_basis,
                observation.current_value,
                observation.display_gain_loss,
            )
        ):
            assert measure.value is not None and measure.reason is None
            totals[i] += Fraction(measure.value.canonical)
    assert totals == [Fraction("49.125"), Fraction("3604"), Fraction("3653.75"), Fraction("49.75")]
    assert result.observations[0].acquired.value == "2024-05-15"
    assert result.observations[0].quantity.value is not None
    assert result.observations[0].quantity.value.original_text == "10.000"
    assert result.observations[0].quantity.value.source_quantum.as_tuple().exponent == -3
    assert result.observations[0].display_gain_percent.value is not None
    assert result.observations[0].display_gain_percent.value.canonical == "-20"
    assert '"A"' in result.observations[0].source_fields[3]
    # Source locators and labels are not converted to durable lot/security/profile IDs.
    assert result.observations[1].source_fields[7:] == result.observations[2].source_fields[7:]
    assert result.observations[1].source_record != result.observations[2].source_record


def test_rounding_and_unknowns_are_preserved_without_invention() -> None:
    base = inspect().observations[3]
    assert base.reported_basis.value is not None and base.average_basis.value is not None
    assert base.reported_basis.value.canonical == "100"
    assert Fraction(base.average_basis.value.canonical) * 3 == Fraction("99.99")
    result = inspect(fixture("missing-basis"))
    assert result.status == "observed_unqualified"
    missing = result.observations[4]
    assert missing.reported_basis.value is None
    assert missing.reported_basis.reason == "source_value_missing"
    assert missing.average_basis.reason == "source_value_unknown"
    assert missing.display_gain_loss.reason == "source_value_unknown"
    assert missing.acquired.value is None and missing.acquired.source_text == ""
    assert missing.source_fields[8] == "Unknown"
    assert not result.canonical_checkpoint_ready


@pytest.mark.parametrize(
    "name,code,count",
    [
        ("repeated-reference", "duplicate_source_reference", 9),
        ("conflicting-reference", "conflicting_source_reference", 9),
        ("schema-drift", "unsupported_header", 8),
        ("malformed-row", "record_width", 8),
    ],
)
def test_adverse_fixtures_refused_with_all_parsed_raw_rows_retained(
    name: str, code: str, count: int
) -> None:
    result = inspect(fixture(name))
    assert result.status == "invalid" and code in codes(result)
    assert len(result.records) == count
    assert result.raw_sha256 == hashlib.sha256(fixture(name)).hexdigest()
    assert not result.planning_ready


@pytest.mark.parametrize(
    "column,value,code",
    [
        (12, "1,00.000", "unsupported_numeric_format"),
        (12, "1e3", "unsupported_numeric_format"),
        (12, "NaN", "unsupported_numeric_format"),
        (14, "-$1.00", "negative_sign_forbidden"),
        (14, "$1.0000000000001", "fractional_digits_exceeded"),
        (9, "=1+2", "unsupported_numeric_format"),
        (7, "Feb-30-2026", "unsupported_acquired_date"),
        (7, "Oct-01-0000", "unsupported_acquired_date"),
        (4, "../source.csv", "source_basename_required"),
        (5, "0", "source_record_required"),
        (5, "6.0", "source_record_required"),
        (0, "", "missing_metadata"),
    ],
)
def test_unsupported_cells_are_located_and_do_not_echo_values(
    column: int, value: str, code: str
) -> None:
    data = rows()
    data[1][column] = value
    result = inspect(encode(data))
    assert result.status == "invalid"
    assert any(
        issue.code == code and issue.record == 2 and issue.column == COLUMNS[column]
        for issue in result.issues
    )
    assert result.records[0][column] == value
    assert not value or value not in repr(result.issues) or value == "0"


def test_untrusted_text_is_retained_without_interpreting_identity_or_term() -> None:
    data = rows()[:2]
    data[1][1] = '=HYPERLINK("https://invalid.example")'
    data[1][3] = "<script>not executable</script>\nsecond line"
    data[1][8] = "Long does not prove tax eligibility"
    result = inspect(encode(data))
    assert result.status == "observed_unqualified"
    assert result.records[0] == tuple(data[1])
    assert result.observations[0].record == 2 and result.observations[0].source_record == 6
    assert "invalid.example" not in repr(result)
    assert "not executable" not in repr(result.observations[0])
    assert not result.canonical_checkpoint_ready


def test_source_metadata_conflict_not_hidden_by_account_scoping() -> None:
    data = rows()[:3]
    data[2][0] = "ANOTHER-SYNTHETIC-ACCOUNT"
    assert "source_file_metadata_conflict" in codes(inspect(encode(data)))


@pytest.mark.parametrize(
    "raw,code",
    [
        (b"", "unsupported_header"),
        (b"\xff", "invalid_utf8"),
        (b"x" * (MAX_BYTES + 1), "byte_limit_exceeded"),
        (encode([list(COLUMNS)]), "no_lot_records"),
        (encode([list(COLUMNS)]) + b'"unfinished', "malformed_csv"),
    ],
    ids=["empty", "encoding", "bytes", "header-only", "unterminated"],
)
def test_closed_transport_refusals(raw: bytes, code: str) -> None:
    assert inspect(raw).status == "invalid" and code in codes(inspect(raw))


def test_work_limits_and_truncation_are_explicit() -> None:
    data = rows()[:2]
    data[1][3] = "x" * (MAX_FIELD + 1)
    assert "unsupported_field" in codes(inspect(encode(data)))
    data = [
        list(COLUMNS),
        [
            "A",
            "A",
            "S",
            "S",
            "x",
            "1",
            "t",
            "Jan-1-2026",
            "Short",
            "$0",
            "0%",
            "$1",
            "1",
            "$1",
            "$1",
        ],
    ]
    many = inspect(encode([data[0]] + [data[1]] * (MAX_RECORDS + 1)))
    assert many.input_truncated and len(many.records) == MAX_RECORDS
    repeated = inspect(encode([data[0]] + [data[1]] * (MAX_ISSUES + 2)))
    assert repeated.further_issues and len(repeated.issues) == MAX_ISSUES


def test_inspection_immutability_and_decimal_context_independence() -> None:
    result = inspect()
    attribute = "records"
    with pytest.raises(FrozenInstanceError):
        setattr(result, attribute, ())
    with localcontext() as context:
        context.prec = 2
        assert inspect() == result
    # Fixture manifest is a separate expectation artifact, not a generated parser oracle.
    manifest = json.loads((FIXTURES / "fixture-manifest.json").read_text(encoding="utf-8"))
    assert len(result.observations) == manifest["baseline"]["records"]


def test_zero_grouped_quantity_and_opaque_download_time_are_not_reinterpreted() -> None:
    data = rows()[:2]
    data[1][12] = "1,000.125"
    data[1][14] = "$0.00"
    data[1][6] = "Unqualified collection timestamp, not economic cutoff"
    result = inspect(encode(data))
    assert result.status == "observed_unqualified"
    lot = result.observations[0]
    assert lot.quantity.value is not None and lot.quantity.value.canonical == "1000.125"
    assert lot.reported_basis.value is not None and lot.reported_basis.value.canonical == "0"
    assert lot.reported_basis.reason is None
    assert "snapshot_boundary_unknown" in result.blocking_reasons
    assert "currency_unqualified" in result.blocking_reasons


def test_byte_identity_distinguishes_transport_changes_without_changing_cell_text() -> None:
    raw = fixture()
    changed = raw.removeprefix(b"\xef\xbb\xbf").replace(b"\r\n", b"\n")
    original, alternate = inspect(raw), inspect(changed)
    assert original.raw_sha256 != alternate.raw_sha256
    assert original.observations == alternate.observations
    assert original.records == alternate.records
    assert alternate.status == "observed_unqualified"
