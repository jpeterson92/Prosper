"""Bounded, lossless column transport for current history facts.

Compression is a transport/storage detail. It never substitutes missing values or
changes precision. Bzip2-compressed JSON stores typed columns and backward exact-column aliases.
"""

import base64
import bz2
import json
import math
import zlib
from functools import cached_property
from typing import Annotated, Literal, Self

import polars as pl
from pydantic import Field, model_validator

from prosper.advisory_records import Record

MAX_TABLE_BYTES = 128 * 1024 * 1024
MAX_ENCODED_TABLE_BYTES = 16 * 1024 * 1024
MAX_ROWS = 650000
PRICES = ("open", "high", "low", "close", "adjusted_close")
OBSERVATION_SCHEMA = {
    "security_id": pl.String,
    "session": pl.String,
    "source_ref": pl.String,
    **{name: pl.Float64 for name in PRICES},
    **{name + "_reason": pl.String for name in PRICES},
    "action": pl.String,
    "action_reason": pl.String,
}
ALIGNMENT_SCHEMA = {
    **OBSERVATION_SCHEMA,
    "source_sha256": pl.String,
    "total_return": pl.Float64,
}


def decompress(raw: bytes, limit: int) -> bytes:
    """Refuse truncated, concatenated, trailing or over-expanding streams."""
    try:
        decoder = zlib.decompressobj()
        result = decoder.decompress(raw, limit + 1)
        if len(result) > limit or not decoder.eof or decoder.unused_data:
            raise ValueError("compressed_history_size_or_stream_invalid")
        return result
    except zlib.error as error:
        raise ValueError("compressed_history_invalid") from error


def decompress_table(raw: bytes) -> bytes:
    """One bzip2 stream, bounded before JSON or logical column expansion."""
    try:
        decoder = bz2.BZ2Decompressor()
        result = decoder.decompress(raw, max_length=MAX_TABLE_BYTES + 1)
        if len(result) > MAX_TABLE_BYTES or not decoder.eof or decoder.unused_data:
            raise ValueError("compressed_history_size_or_stream_invalid")
        return result
    except OSError as error:
        raise ValueError("compressed_history_invalid") from error


class HistoryTable(Record):
    encoding: Literal["bz2-column-json-v3"] = "bz2-column-json-v3"
    kind: Literal["observations", "alignment"]
    row_count: Annotated[int, Field(ge=0, le=MAX_ROWS)]
    data: Annotated[str, Field(max_length=MAX_ENCODED_TABLE_BYTES)]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HistoryTable):
            return False
        return self.model_dump() == other.model_dump()

    @cached_property
    def frame(self) -> pl.DataFrame:
        try:
            raw = decompress_table(base64.b64decode(self.data, validate=True))

            # No object nesting is needed inside a column. Reject duplicates too.
            def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
                result = dict(pairs)
                if len(result) != len(pairs):
                    raise ValueError("duplicate_history_column")
                return result

            columns = json.loads(raw, object_pairs_hook=unique)
            schema = OBSERVATION_SCHEMA if self.kind == "observations" else ALIGNMENT_SCHEMA
            if not isinstance(columns, dict) or set(columns) != set(schema):
                raise ValueError("history_columns_invalid")
            logical_text_bytes = 0
            text_sizes: dict[str, int] = {}
            decoded: dict[str, list[object]] = {}
            for name, column in columns.items():
                text_size = 0
                if isinstance(column, dict):
                    if set(column) == {"alias"}:
                        alias = column["alias"]
                        if (
                            not isinstance(alias, str)
                            or alias not in decoded
                            or schema[alias] != schema[name]
                        ):
                            raise ValueError("history_column_alias_invalid")
                        value = decoded[alias]
                        text_size = text_sizes[alias]
                    elif set(column) == {"value"}:
                        scalar = column["value"]
                        text_size = (
                            len(scalar.encode()) * self.row_count if isinstance(scalar, str) else 0
                        )
                        if logical_text_bytes + text_size > MAX_TABLE_BYTES:
                            raise ValueError("history_logical_text_size_limit")
                        value = [scalar] * self.row_count
                    elif set(column) == {"values", "indices"}:
                        values, indices = column["values"], column["indices"]
                        if (
                            schema[name] != pl.String
                            or not isinstance(values, list)
                            or not isinstance(indices, list)
                            or len(indices) != self.row_count
                        ):
                            raise ValueError("history_dictionary_invalid")
                        if len(values) > self.row_count or any(
                            type(i) is not int or not 0 <= i < len(values) for i in indices
                        ):
                            raise ValueError("history_dictionary_index_invalid")
                        if any(v is not None and not isinstance(v, str) for v in values):
                            raise ValueError("history_text_type_invalid")
                        lengths = [len(v.encode()) if isinstance(v, str) else 0 for v in values]
                        text_size = sum(lengths[i] for i in indices)
                        if logical_text_bytes + text_size > MAX_TABLE_BYTES:
                            raise ValueError("history_logical_text_size_limit")
                        value = [values[i] for i in indices]
                    else:
                        raise ValueError("history_column_encoding_invalid")
                else:
                    value = column
                    if schema[name] == pl.String and isinstance(value, list):
                        text_size = sum(len(v.encode()) for v in value if isinstance(v, str))
                if not isinstance(value, list) or len(value) != self.row_count:
                    raise ValueError("history_column_cardinality_invalid")
                if schema[name] == pl.Float64 and any(
                    v is not None and type(v) not in (int, float) for v in value
                ):
                    raise ValueError("history_number_type_invalid")
                if schema[name] == pl.String and any(
                    v is not None and not isinstance(v, str) for v in value
                ):
                    raise ValueError("history_text_type_invalid")
                logical_text_bytes += text_size
                if logical_text_bytes > MAX_TABLE_BYTES:
                    raise ValueError("history_logical_text_size_limit")
                text_sizes[name] = text_size
                decoded[name] = value
            columns = decoded
            frame = pl.DataFrame(columns, schema=schema, strict=True)
            if frame.height:
                if frame.select("security_id", "session").null_count().sum_horizontal().item():
                    raise ValueError("history_coordinate_missing")
                if (
                    not frame["security_id"]
                    .str.contains(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
                    .all()
                ):
                    raise ValueError("history_identity_invalid")
                if not frame["session"].str.contains(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$").all():
                    raise ValueError("history_session_invalid")
                frame["session"].str.to_date("%Y-%m-%d", strict=True)
                if frame.select("security_id", "session").is_duplicated().any():
                    raise ValueError("duplicate_observation")
                for name, dtype in schema.items():
                    col = frame[name]
                    if dtype == pl.Float64 and not col.drop_nulls().is_finite().all():
                        raise ValueError("history_nonfinite_number")
                    if dtype == pl.String and (
                        (col.drop_nulls().str.len_chars() > 4096).any()
                        or (col.drop_nulls().str.strip_chars() == "").any()
                    ):
                        raise ValueError("history_text_invalid")
                observed = pl.col("source_ref").is_not_null()
                if self.kind == "observations" and frame["source_ref"].null_count():
                    raise ValueError("history_locator_missing")
                for name in (*PRICES, "action"):
                    if frame.filter(
                        observed
                        & (pl.col(name).is_null() != pl.col(name + "_reason").is_not_null())
                    ).height:
                        raise ValueError("history_unknown_reason_invalid")
                if self.kind == "alignment":
                    digest = frame["source_sha256"].drop_nulls()
                    if not digest.str.contains(r"^[a-f0-9]{64}$").all():
                        raise ValueError("history_source_digest_invalid")
                    if frame.filter(
                        pl.col("source_ref").is_null() != pl.col("source_sha256").is_null()
                    ).height:
                        raise ValueError("history_source_locator_mismatch")
            return frame
        except (TypeError, OverflowError, pl.exceptions.PolarsError, RecursionError) as error:
            raise ValueError("history_table_invalid") from error

    @model_validator(mode="after")
    def checked(self) -> Self:
        _ = self.frame
        return self

    @classmethod
    def pack(cls, frame: pl.DataFrame, kind: Literal["observations", "alignment"]) -> Self:
        schema = OBSERVATION_SCHEMA if kind == "observations" else ALIGNMENT_SCHEMA
        if set(frame.columns) != set(schema) or any(
            frame.schema[name] != dtype for name, dtype in schema.items()
        ):
            raise ValueError("history_columns_invalid")
        columns: dict[str, object] = {}
        seen: dict[tuple[str, str], str] = {}
        for name, dtype in frame.schema.items():
            values = frame[name].to_list()
            unique = frame[name].unique(maintain_order=True).to_list()
            constant = len(unique) == 1
            # Polars considers signed zeros equal; this lossless codec must not.
            if constant and dtype == pl.Float64 and unique[0] == 0:
                constant = all(math.copysign(1, v) == math.copysign(1, values[0]) for v in values)
            column: object
            if constant:
                column = {"value": values[0]}
            elif dtype == pl.String:
                lookup = {value: i for i, value in enumerate(unique)}
                column = {"values": unique, "indices": [lookup[value] for value in values]}
            else:
                column = values
            key = (str(dtype), json.dumps(column, separators=(",", ":"), allow_nan=False))
            if key in seen:
                columns[name] = {"alias": seen[key]}
            else:
                columns[name] = column
                seen[key] = name
        raw = json.dumps(columns, separators=(",", ":"), allow_nan=False).encode()
        if len(raw) > MAX_TABLE_BYTES:
            raise ValueError("history_table_size_limit")
        data = base64.b64encode(bz2.compress(raw)).decode()
        if len(data) > MAX_ENCODED_TABLE_BYTES:
            raise ValueError("history_table_encoded_size_limit")
        return cls(kind=kind, row_count=frame.height, data=data)


def observations(rows: tuple[object, ...]) -> HistoryTable:
    """Build the sole current column format from typed boundary observations."""
    records = []
    for row in rows:
        values = row.model_dump()  # type: ignore[attr-defined]
        flat = {name: values[name] for name in ("security_id", "session", "source_ref")}
        for name in (*PRICES, "action"):
            flat[name] = values[name]["value"]
            flat[name + "_reason"] = values[name]["reason"]
        records.append(flat)
    return HistoryTable.pack(pl.DataFrame(records, schema=OBSERVATION_SCHEMA), "observations")


class SessionGrid(Record):
    count: Annotated[int, Field(ge=1, le=10000)]
    data: Annotated[str, Field(max_length=200000)]

    @property
    def values(self) -> tuple[str, ...]:
        from pydantic import TypeAdapter

        from prosper.record_types import DateText

        raw = decompress(base64.b64decode(self.data, validate=True), 150000)
        result = TypeAdapter(tuple[DateText, ...]).validate_json(raw)
        if len(result) != self.count or result != tuple(sorted(set(result))):
            raise ValueError("history_sessions_invalid")
        return result

    @model_validator(mode="after")
    def checked(self) -> Self:
        _ = self.values
        return self

    @classmethod
    def pack(cls, values: tuple[str, ...]) -> Self:
        return cls(
            count=len(values),
            data=base64.b64encode(zlib.compress(json.dumps(values).encode())).decode(),
        )
