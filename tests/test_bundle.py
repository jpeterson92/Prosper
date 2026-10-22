"""Synthetic parser boundary expectations; no reconciliation or tax acceptance."""

import copy
import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from prosper.bundle import (
    MAX_ARRAY,
    MAX_BYTES,
    MAX_DEPTH,
    MAX_ISSUES,
    MAX_MEMBERS,
    MAX_RECORDS,
    MAX_TEXT,
    ParsedBundle,
    ParseResult,
    parse_bundle,
)

FIXTURES = Path(__file__).resolve().parents[1] / "examples/synthetic"
type Document = dict[str, Any]


def fixture(name: str = "F001") -> Document:
    document: Document = json.loads((FIXTURES / f"{name}.json").read_bytes())
    return document


def encode(document: Document) -> bytes:
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


def parsed(document: Document) -> ParsedBundle:
    result = parse_bundle(encode(document))
    assert result.parsed is not None, result.issues
    assert result.issues == () and not result.further_issues
    return result.parsed


def rejected(raw: bytes, code: str, path: tuple[str | int, ...] | None = None) -> ParseResult:
    result = parse_bundle(raw)
    assert result.parsed is None
    assert any(
        issue.code == code and (path is None or issue.path == path) for issue in result.issues
    )
    return result


def test_complete_fixtures_preserve_values_and_explicit_prior_unknowns() -> None:
    current = parsed(fixture()).document
    assert current.metadata.bundle_id == "F001"
    assert current.metadata.cutoff == "2026-10-22T16:00:00-04:00"
    assert current.metadata.source_timezone == "America/New_York"
    assert current.metadata.included_activity_ids == ("BUY-001",)
    assert [
        position.quantity.value.canonical
        for position in current.positions
        if position.quantity.value is not None
    ] == ["12", "5"]
    assert [lot.id for lot in current.lots] == ["LOT-A-OLD", "LOT-A-NEW", "LOT-B-OLD"]
    assert [lot.basis.value.canonical for lot in current.lots if lot.basis.value is not None] == [
        "1000",
        "181",
        "1000",
    ]
    assert current.cash[0].settled.value is not None
    assert current.cash[0].settled.value.canonical == "319"
    assert current.activity[0].cash_movement.value is not None
    assert current.activity[0].cash_movement.value.canonical == "-181"
    assert current.activity[0].fees.value is not None
    assert current.activity[0].fees.value.canonical == "1"
    assert current.lots[1].basis_quantum.value is not None
    assert current.lots[1].basis_quantum.value.canonical == "0.01"
    prior = parsed(fixture("F000")).document
    assert prior.metadata.bundle_id == "F000"
    assert prior.metadata.cutoff == "2026-10-20T16:00:00-04:00"
    assert not prior.activity and len(prior.lots) == 2
    assert prior.cash[0].settled.value is not None
    assert prior.cash[0].settled.value.canonical == "500"
    assert prior.cash[0].available.value is None
    assert prior.cash[0].available.reason == "not_stipulated"


@pytest.mark.parametrize("variant", ["F002", "F003", "F004", "F009", "dangling_reference"])
def test_parsing_does_not_claim_semantic_validation(variant: str) -> None:
    document = fixture()
    if variant == "F002":
        document["metadata"]["inclusion"] = {"value": None, "reason": "inclusion_unproven"}
    elif variant == "F003":
        document["lots"][0]["quantity"]["value"] = "11"
    elif variant == "F004":
        document["lots"][1]["basis"] = {"value": None, "reason": "source_missing"}
    elif variant == "F009":
        document["coverage"][0]["status"] = "unknown"
        document["coverage"][0]["evidence"] = {"value": None, "reason": "household_unknown"}
    else:
        document["lots"][0]["security_id"] = "NONEXISTENT-SECURITY"
    receipt = parsed(document)
    assert receipt.status == "parsed_unvalidated"
    assert not hasattr(receipt, "committable") and not hasattr(receipt, "planning_ready")
    if variant == "F004":
        assert receipt.document.lots[1].basis.value is None
        assert receipt.document.lots[1].basis.reason == "source_missing"


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("0.1000000000001", "fractional_digits_exceeded"),
        ("1e2", "fixed_point_required"),
        ("NaN", "fixed_point_required"),
        ("Infinity", "fixed_point_required"),
        ("-1", "negative_sign_forbidden"),
        ("-0", "negative_sign_forbidden"),
        ("10000000000000000000000000000", "significant_digits_exceeded"),
        (0.1, "decimal_string_required"),
        (1, "decimal_string_required"),
        (True, "decimal_string_required"),
        (False, "decimal_string_required"),
    ],
)
def test_invalid_exact_fields_are_located(value: object, code: str) -> None:
    document = fixture()
    document["lots"][1]["basis"]["value"] = value
    rejected(encode(document), code, ("lots", 1, "basis", "value"))


@pytest.mark.parametrize("value", [None, "", "  "])
def test_missing_value_requires_reason(value: str | None) -> None:
    document = fixture()
    document["lots"][1]["basis"] = {"value": None, "reason": value}
    result = parse_bundle(encode(document))
    assert result.parsed is None and result.issues
    assert result.issues[0].path[:3] == ("lots", 1, "basis")


def test_ambiguous_known_reason_and_missing_pair_keys_fail() -> None:
    for pair in (
        {"value": "181", "reason": "source_missing"},
        {"value": None},
        {"reason": "missing"},
    ):
        document = fixture()
        document["lots"][1]["basis"] = pair
        result = parse_bundle(encode(document))
        assert result.parsed is None
        assert any(issue.path[:3] == ("lots", 1, "basis") for issue in result.issues)


@pytest.mark.parametrize("value", [False, "true", 1, None])
def test_fictional_flag_is_literal_boolean_true(value: object) -> None:
    document = fixture()
    document["metadata"]["fictional"] = value
    rejected(encode(document), "fictional_flag_required", ("metadata", "fictional"))


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", "v999"), ("semantics_version", "event-replay-v1")],
)
def test_unknown_versions_fail(field: str, value: str) -> None:
    document = fixture()
    document["metadata"][field] = value
    rejected(encode(document), "literal_error", ("metadata", field))


@pytest.mark.parametrize("value", ["2026-02-30", "20261021", "2026-10-21T00:00:00Z", 20261021])
def test_trade_dates_remain_strict_calendar_dates(value: object) -> None:
    document = fixture()
    document["activity"][0]["trade_date"]["value"] = value
    result = parse_bundle(encode(document))
    assert result.parsed is None
    assert result.issues[0].path == ("activity", 0, "trade_date", "value")


@pytest.mark.parametrize(
    "value",
    [
        "2026-10-22",
        "2026-10-22T16:00:00",
        "2026-10-22T16:00:00+01:60",
        "2026-02-30T16:00:00-04:00",
        "2026-10-22T25:00:00Z",
    ],
)
def test_invalid_cutoff_offsets_and_timestamps(value: str) -> None:
    document = fixture()
    document["metadata"]["cutoff"] = value
    result = parse_bundle(encode(document))
    assert result.parsed is None and result.issues[0].path == ("metadata", "cutoff")


@pytest.mark.parametrize("raw", [b"[]", b"null", b"1", b'"text"'])
def test_non_object_root(raw: bytes) -> None:
    rejected(raw, "object_root_required")


@pytest.mark.parametrize("raw", [b"", b"{", b"{} {}", b"{} trailing", b'{"x": [1,]}'])
def test_invalid_json(raw: bytes) -> None:
    result = rejected(raw, "invalid_json")
    assert result.issues[0].offset is not None


def test_encoding_unicode_and_bom() -> None:
    rejected(b'{"x":"\xff"}', "invalid_utf8")
    rejected(b"\xef\xbb\xbf{}", "utf8_bom_forbidden")
    rejected(b'{"x":"\\ud800"}', "invalid_unicode_scalar", ("x",))
    rejected(b'{"\\ud800": 1}', "invalid_unicode_scalar", ())
    document = fixture()
    document["accounts"][0]["alias"] = "Fictional \U0001f4bc account"
    assert parsed(document).document.accounts[0].alias == "Fictional \U0001f4bc account"


@pytest.mark.parametrize("token", [b"NaN", b"Infinity", b"-Infinity"])
def test_nonfinite_json_extensions_reject_with_location(token: bytes) -> None:
    raw = encode(fixture()).replace(b'"value": "181"', b'"value": ' + token)
    rejected(raw, "json_nonfinite_forbidden", ("lots", 1, "basis", "value"))


def test_very_long_json_number_is_not_materialized_as_int_or_float() -> None:
    raw = encode(fixture()).replace(b'"value": "181"', b'"value": ' + b"9" * 10000)
    rejected(raw, "decimal_string_required", ("lots", 1, "basis", "value"))


@pytest.mark.parametrize(
    ("raw", "location"),
    [
        (b'{"a":1,"a":2}', ("a",)),
        (b'{"a":1,"\\u0061":2}', ("a",)),
        (
            b'{"lots":[{"basis":{"value":"1","value":"2","reason":null}}]}',
            ("lots", 0, "basis", "value"),
        ),
    ],
)
def test_duplicate_keys_are_detected_before_mapping(
    raw: bytes, location: tuple[str | int, ...]
) -> None:
    rejected(raw, "duplicate_key", location)


@pytest.mark.parametrize(
    "family",
    ["accounts", "securities", "positions", "lots", "cash", "activity", "quotes", "coverage"],
)
def test_duplicate_record_id_is_never_merged(family: str) -> None:
    document = fixture()
    document[family].append(copy.deepcopy(document[family][0]))
    rejected(encode(document), "duplicate_record_id", (family, len(document[family]) - 1, "id"))


@pytest.mark.parametrize("family", ["positions", "cash"])
def test_composite_identity_collision_even_when_row_ids_differ(family: str) -> None:
    document = fixture()
    row = copy.deepcopy(document[family][0])
    row["id"] = "DIFFERENT-ROW-ID"
    document[family].append(row)
    rejected(encode(document), "duplicate_composite_identity", (family, len(document[family]) - 1))


def test_distinct_events_and_order_bearing_fields_are_not_collapsed() -> None:
    document = fixture()
    row = copy.deepcopy(document["activity"][0])
    row["id"] = "BUY-002"
    document["activity"].append(row)
    assert len(parsed(document).document.activity) == 2
    document["metadata"]["included_activity_ids"] = ["BUY-001", "BUY-002"]
    ordered = parsed(document)
    document["metadata"]["included_activity_ids"].reverse()
    assert parsed(document).canonical_sha256 == ordered.canonical_sha256
    document["metadata"]["included_activity_ids"] = ["BUY-001", "BUY-001"]
    rejected(encode(document), "duplicate_inclusion_reference")
    document["metadata"]["included_activity_ids"] = ["BUY-001"]
    document["activity"][0]["lot_ids"] *= 2
    rejected(encode(document), "duplicate_lot_reference")


@pytest.mark.parametrize(
    ("family", "field", "value", "code"),
    [
        ("activity", "quantity", "0", "positive_value_required"),
        ("quotes", "price", "0", "positive_value_required"),
        ("cash", "settled", "-1", "negative_sign_forbidden"),
        ("lots", "basis_quantum", "0", "positive_value_required"),
    ],
)
def test_field_sign_contract_is_applied(family: str, field: str, value: str, code: str) -> None:
    document = fixture()
    document[family][0][field]["value"] = value
    rejected(encode(document), code, (family, 0, field, "value"))


def test_unknown_quantities_and_diagnostic_holdings_are_preserved() -> None:
    document = fixture()
    document["positions"][0]["quantity"] = {"value": None, "reason": "source_missing"}
    document["securities"][0]["tax_classification"] = {
        "value": "Excluded diagnostic class",
        "reason": None,
    }
    receipt = parsed(document)
    assert receipt.document.positions[0].quantity.value is None
    assert receipt.document.positions[0].quantity.reason == "source_missing"
    assert receipt.document.securities[0].tax_classification.value == "Excluded diagnostic class"


def test_closed_fields_unknown_events_and_missing_families() -> None:
    document = fixture()
    document["lots"][0]["surprise"] = "do not execute this"
    rejected(encode(document), "extra_forbidden", ("lots", 0, "surprise"))
    document = fixture()
    del document["coverage"]
    rejected(encode(document), "missing", ("coverage",))
    document = fixture()
    document["activity"][0]["activity_type"] = "unqualified_type"
    rejected(encode(document), "literal_error", ("activity", 0, "activity_type"))


def test_adversarial_text_is_inert_and_receipts_are_immutable(tmp_path: Path) -> None:
    document = fixture()
    marker = tmp_path / "must-not-exist"
    text = (
        '<script>fetch("https://example.invalid")</script> =cmd '
        f'__import__("pathlib").Path({str(marker)!r}).touch()'
    )
    document["accounts"][0]["alias"] = text
    receipt = parsed(document)
    assert receipt.document.accounts[0].alias == text
    assert not marker.exists()
    with pytest.raises(ValidationError):
        receipt.document.accounts[0].alias = "changed"
    with pytest.raises(FrozenInstanceError):
        receipt.raw_bytes = b"changed"  # type: ignore[misc]
    basis = receipt.document.lots[0].basis.value
    assert basis is not None
    with pytest.raises(FrozenInstanceError):
        basis.original_text = "0"  # type: ignore[misc]
    exported = receipt.document.model_dump(mode="json")
    exported["lots"].clear()
    document["lots"].clear()
    assert len(receipt.document.lots) == 3
    rejected(b"invalid", "invalid_json")
    assert receipt.document.lots[0].basis.value == basis


def test_byte_depth_array_object_and_text_limits() -> None:
    raw = encode(fixture())
    at_limit = raw + b" " * (MAX_BYTES - len(raw))
    assert parse_bundle(at_limit).parsed is not None
    rejected(at_limit + b" ", "byte_limit_exceeded")
    for depth in (MAX_DEPTH, MAX_DEPTH + 1):
        nested = b'{"x":' + b"[" * (depth - 1) + b"null" + b"]" * (depth - 1) + b"}"
        result = parse_bundle(nested)
        assert any(i.code == "container_depth_exceeded" for i in result.issues) == (
            depth > MAX_DEPTH
        )
    document = fixture()
    document["metadata"]["stipulations"] = ["x"] * MAX_ARRAY
    assert parsed(document).document.metadata.stipulations[-1] == "x"
    document["metadata"]["stipulations"].append("x")
    rejected(encode(document), "array_elements_exceeded", ("metadata", "stipulations"))
    for count in (MAX_MEMBERS, MAX_MEMBERS + 1):
        result = parse_bundle(encode({f"x{i}": None for i in range(count)}))
        assert any(i.code == "object_members_exceeded" for i in result.issues) == (
            count > MAX_MEMBERS
        )
    document = fixture()
    document["accounts"][0]["alias"] = "x" * MAX_TEXT
    assert parsed(document).document.accounts[0].alias == "x" * MAX_TEXT
    document["accounts"][0]["alias"] += "x"
    rejected(encode(document), "text_length_exceeded", ("accounts", 0, "alias"))
    document = fixture()
    document["metadata"]["bundle_id"] = "x" * 128
    assert parsed(document).document.metadata.bundle_id == "x" * 128
    document["metadata"]["bundle_id"] += "x"
    rejected(encode(document), "string_pattern_mismatch", ("metadata", "bundle_id"))


def test_aggregate_record_and_issue_limits_do_not_truncate_into_success() -> None:
    document = fixture()
    for family in (
        "accounts",
        "securities",
        "positions",
        "lots",
        "cash",
        "activity",
        "quotes",
        "coverage",
    ):
        document[family] = []
    document["lots"] = [{}] * (MAX_RECORDS // 2)
    document["positions"] = [{}] * (MAX_RECORDS // 2)
    result = parse_bundle(encode(document))
    assert not any(issue.code == "record_limit_exceeded" for issue in result.issues)
    assert result.parsed is None and result.further_issues and len(result.issues) == MAX_ISSUES
    document["positions"].append({})
    rejected(encode(document), "record_limit_exceeded")
    for count in (MAX_ISSUES, MAX_ISSUES + 1):
        document = fixture()
        document.update({f"extra{i}": "do not echo this value" for i in range(count)})
        result = parse_bundle(encode(document))
        assert len(result.issues) == MAX_ISSUES
        assert result.further_issues == (count > MAX_ISSUES)
        assert "do not echo this value" not in repr(result)


def test_depth_scanner_respects_escaped_quotes_and_container_characters() -> None:
    document = fixture()
    document["accounts"][0]["alias"] = '{["escaped \\" quote"]}' * 30
    assert parsed(document).document.accounts[0].alias == document["accounts"][0]["alias"]


def test_canonical_format_preserves_every_field_and_explicit_source_quantum() -> None:
    document = fixture()
    receipt = parsed(document)
    independent = copy.deepcopy(document)
    for family in (
        "accounts",
        "securities",
        "positions",
        "lots",
        "cash",
        "activity",
        "quotes",
        "coverage",
    ):
        independent[family] = sorted(independent[family], key=lambda row: row["id"])
    expected = {"canonicalization_version": "canonical-json-v1", "document": independent}
    assert receipt.canonical_bytes == json.dumps(
        expected, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    changed = fixture()
    changed["lots"][0]["basis"]["value"] = "1000.00"
    equivalent = parsed(changed)
    assert equivalent.canonical_sha256 == receipt.canonical_sha256
    assert equivalent.raw_sha256 != receipt.raw_sha256
    assert equivalent.document.lots[0].basis.value is not None
    assert equivalent.document.lots[0].basis.value.original_text == "1000.00"
    assert str(equivalent.document.lots[0].basis.value.source_quantum) == "0.01"
    changed["lots"][0]["basis_quantum"]["value"] = "0.001"
    assert parsed(changed).canonical_sha256 != receipt.canonical_sha256


@pytest.mark.parametrize(
    "change", ["basis", "reason", "event_id", "source_id", "stipulation_order"]
)
def test_meaningful_changes_change_normalized_identity(change: str) -> None:
    original = parsed(fixture())
    document = fixture()
    if change == "basis":
        document["lots"][0]["basis"]["value"] = "1001"
    elif change == "reason":
        document["accounts"][0]["lot_method"]["reason"] = "different_reason"
    elif change == "event_id":
        document["activity"][0]["id"] = "BUY-002"
    elif change == "source_id":
        document["metadata"]["source_id"] = "DIFFERENT-SOURCE"
    else:
        document["metadata"]["stipulations"].reverse()
    assert parsed(document).canonical_sha256 != original.canonical_sha256


@settings(max_examples=40, derandomize=True, database=None)
@given(data=st.data())
def test_key_record_and_whitespace_permutations_preserve_identity(data: st.DataObject) -> None:
    document = fixture()
    original = parsed(document)
    for family in (
        "accounts",
        "securities",
        "positions",
        "lots",
        "cash",
        "activity",
        "quotes",
        "coverage",
    ):
        document[family] = list(data.draw(st.permutations(document[family])))
    reordered = dict(data.draw(st.permutations(list(document.items()))))
    raw = json.dumps(reordered, indent=3, sort_keys=data.draw(st.booleans())).encode()
    result = parse_bundle(raw)
    assert result.parsed is not None
    assert result.parsed.canonical_sha256 == original.canonical_sha256
    assert result.parsed.raw_bytes == raw
    assert result.parsed.raw_sha256 != original.raw_sha256


@settings(max_examples=100, derandomize=True, database=None)
@given(raw=st.binary(max_size=5000))
def test_arbitrary_bytes_return_a_bounded_result(raw: bytes) -> None:
    result = parse_bundle(raw)
    assert len(result.issues) <= MAX_ISSUES
    assert result.parsed is None or result.parsed.status == "parsed_unvalidated"
