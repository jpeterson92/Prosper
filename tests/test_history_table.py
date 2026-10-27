"""Lossless Float64 columns, bounded aliases and protected row inspection."""

import base64
import bz2
import json
import struct
from pathlib import Path

import polars as pl
import pytest

from prosper import history_table
from prosper.history_table import HistoryTable, decompress_table
from tests.test_history import upload
from tests.test_import_api import running


def encoded(columns: dict[str, object]) -> str:
    return base64.b64encode(bz2.compress(json.dumps(columns).encode())).decode()


def test_float_bits_nulls_dictionary_values_and_column_order_round_trip() -> None:
    frame = upload().parts[0].batch.rows.frame
    numbers = [0.0, -0.0, 5e-324, -5e-324, 1.7976931348623157e308, 1.2345678901234567, None, 1e-300]
    frame = frame.with_columns(
        pl.Series("open", numbers, dtype=pl.Float64),
        pl.Series("open_reason", [None] * 6 + ["unavailable"] + [None], dtype=pl.String),
        # Same dictionary index pattern, different values: never an alias.
        pl.Series("source_ref", [f"row-{i % 2}" for i in range(8)]),
        pl.Series("action", [f"event-{i % 2}" for i in range(8)]),
    )
    table = HistoryTable.pack(frame, "observations")
    decoded = HistoryTable.model_validate_json(table.model_dump_json()).frame
    assert decoded.columns == frame.columns
    assert decoded.equals(frame)
    assert [None if v is None else struct.pack("!d", v) for v in decoded["open"]] == [
        None if v is None else struct.pack("!d", v) for v in numbers
    ]
    columns = json.loads(decompress_table(base64.b64decode(table.data)))
    assert columns["source_ref"] != columns["action"]
    assert any(isinstance(v, dict) and "alias" in v for v in columns.values())


@pytest.mark.parametrize("alias", ["open", "missing", "session"])
def test_alias_must_reference_an_earlier_column_of_the_same_type(alias: str) -> None:
    frame = upload().parts[0].batch.rows.frame
    columns: dict[str, object] = dict(frame.to_dict(as_series=False))
    columns["open"] = {"alias": alias}
    with pytest.raises(ValueError, match="history_column_alias_invalid"):
        HistoryTable(kind="observations", row_count=frame.height, data=encoded(columns))


@pytest.mark.parametrize("fault", ["truncated", "trailing", "concatenated", "invalid", "expanded"])
def test_single_stream_and_decoded_size_refuse_before_json(
    monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    raw = bz2.compress(b"x" * 100)
    monkeypatch.setattr(history_table, "MAX_TABLE_BYTES", 100)
    if fault == "truncated":
        raw = raw[:-1]
    elif fault == "trailing":
        raw += b"trailing"
    elif fault == "concatenated":
        raw += raw
    elif fault == "invalid":
        raw = b"invalid"
    else:
        raw = bz2.compress(b"x" * 101)
    with pytest.raises(ValueError):
        decompress_table(raw)


def test_paged_http_rows_preserve_facts_and_refuse_invalid_requests(tmp_path: Path) -> None:
    table = upload().parts[0].batch.rows
    frame = table.frame
    with running(tmp_path / "runtime") as api:
        before = api.current()
        for offset in (0, 3, 6, 8):
            status, result = api.request(
                "/api/v1/history/rows",
                "POST",
                {"table": table.model_dump(mode="json"), "offset": offset, "limit": 3},
            )
            assert status == 200
            assert result == {
                "row_count": 8,
                "offset": offset,
                "columns": frame.columns,
                "rows": [list(row) for row in frame.slice(offset, 3).rows()],
            }
        for change in ({"offset": 9}, {"offset": -1}, {"limit": 101}, {"limit": 0}):
            status, _ = api.request(
                "/api/v1/history/rows",
                "POST",
                {
                    "table": table.model_dump(mode="json"),
                    **change,
                },
            )
            assert status == 422
        status, _ = api.request(
            "/api/v1/history/rows",
            "POST",
            {
                "table": table.model_dump(mode="json"),
            },
            authorized=False,
        )
        assert status == 401
        assert api.current() == before
