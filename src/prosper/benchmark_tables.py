"""Typed, ordinal-preserving Polars matching for the benchmark domain loops.

Tables contain scalar keys and record ordinals, never Python Object payloads or
financial floats. Original immutable records remain the validation/arithmetic
boundary. Null locator keys do not match; duplicate keys refuse multiplication.
"""

import hashlib
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import polars as pl

IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
RUNTIME_VERSION = f"polars={pl.__version__};polars-runtime-32={version('polars-runtime-32')}"
Key = tuple[str, int]


@dataclass(frozen=True)
class Bindings:
    sections: tuple[int | None, ...]
    rows: tuple[int | None, ...]
    values: tuple[int | None, ...]
    decisions: tuple[int | None, ...]
    extra_sections: tuple[int, ...]
    extra_rows: tuple[int, ...]
    extra_values: tuple[int, ...]


@dataclass(frozen=True)
class Links:
    targets: tuple[int | None, ...]
    duplicates: tuple[bool, ...]
    complete_sections: tuple[str, ...]


def _sections(names: tuple[str, ...], ordinal: str) -> pl.DataFrame:
    frame = pl.DataFrame(
        [(name, n) for n, name in enumerate(names)],
        schema={"section": pl.String, ordinal: pl.Int64},
        orient="row",
    )
    if frame.select("section").is_duplicated().any():
        raise ValueError("unique section keys required before join")
    return frame


def _rows(keys: tuple[Key, ...], ordinal: str) -> pl.DataFrame:
    frame = pl.DataFrame(
        # Rule locators may contain an out-of-range Python integer. Preserve it
        # as an unmatched key rather than overflow a machine integer or round it.
        [(section, str(index), n) for n, (section, index) in enumerate(keys)],
        schema={"section": pl.String, "index": pl.String, ordinal: pl.Int64},
        orient="row",
    )
    if frame.select("section", "index").is_duplicated().any():
        raise ValueError("unique full row locators required before join")
    return frame


def _ordinals(frame: pl.DataFrame, name: str) -> tuple[int | None, ...]:
    return tuple(None if n is None else int(n) for n in frame.get_column(name).to_list())


def _extra(rules: pl.DataFrame, source: pl.DataFrame, keys: list[str]) -> tuple[int, ...]:
    result = rules.join(source.select(keys), on=keys, how="anti", nulls_equal=False).sort("rule")
    return tuple(int(n) for n in result.get_column("rule").to_list())


def bind(
    source_sections: tuple[str, ...],
    source_rows: tuple[Key, ...],
    section_rules: tuple[str, ...],
    row_rules: tuple[Key, ...],
    value_rules: tuple[str, ...] = (),
    decision_rules: tuple[Key, ...] = (),
) -> Bindings:
    sections, rows = _sections(source_sections, "ordinal"), _rows(source_rows, "ordinal")
    sr, rr = _sections(section_rules, "rule"), _rows(row_rules, "rule")
    vr, dr = _sections(value_rules, "rule"), _rows(decision_rules, "rule")
    section_matches = (
        sections.join(sr, on="section", how="left", validate="1:1", nulls_equal=False)
        .join(
            vr.rename({"rule": "value"}),
            on="section",
            how="left",
            validate="1:1",
            nulls_equal=False,
        )
        .sort("ordinal")
    )
    row_matches = (
        rows.join(rr, on=["section", "index"], how="left", validate="1:1", nulls_equal=False)
        .join(
            dr.rename({"rule": "decision"}),
            on=["section", "index"],
            how="left",
            validate="1:1",
            nulls_equal=False,
        )
        .sort("ordinal")
    )
    return Bindings(
        _ordinals(section_matches, "rule"),
        _ordinals(row_matches, "rule"),
        _ordinals(section_matches, "value"),
        _ordinals(row_matches, "decision"),
        _extra(sr, sections, ["section"]),
        _extra(rr, rows, ["section", "index"]),
        _extra(vr, sections, ["section"]),
    )


def unmatched(rules: tuple[Key, ...], source: tuple[Key, ...]) -> tuple[int, ...]:
    return _extra(_rows(rules, "rule"), _rows(source, "ordinal"), ["section", "index"])


def link(
    sections: tuple[str, ...],
    rows: tuple[tuple[str, str | None, int | None, bool], ...],
    targets: tuple[tuple[str, int, bool], ...],
) -> Links:
    source = pl.DataFrame(
        [
            (n, section, target_section, str(index) if index is not None else None, candidate)
            for n, (section, target_section, index, candidate) in enumerate(rows)
        ],
        schema={
            "ordinal": pl.Int64,
            "section": pl.String,
            "target_section": pl.String,
            "target_index": pl.String,
            "candidate": pl.Boolean,
        },
        orient="row",
    )
    primary = _rows(tuple((s, n) for s, n, _ in targets), "target").rename(
        {"section": "target_section", "index": "target_index"}
    )
    primary = primary.with_columns(
        pl.Series("valid", [valid for _, _, valid in targets], dtype=pl.Boolean)
    )
    matched = (
        source.filter("candidate")
        .join(
            primary.filter("valid").drop("valid"),
            on=["target_section", "target_index"],
            how="left",
            validate="m:1",
            nulls_equal=False,
        )
        .sort("ordinal")
        .with_columns(
            pl.col("target")
            .cum_count()
            .over(["section", "target_section", "target_index"])
            .alias("occurrence")
        )
    )
    matched = matched.with_columns((pl.col("occurrence") > 1).alias("duplicate"))
    covered = matched.filter(pl.col("target").is_not_null() & ~pl.col("duplicate"))
    counts = covered.group_by("section").agg(pl.col("target").n_unique().alias("count"))
    complete = (
        _sections(sections, "ordinal")
        .join(counts, on="section", how="left", validate="1:1", nulls_equal=False)
        .filter(pl.col("count").fill_null(0) == len(targets))
    )
    all_rows = (
        source.select("ordinal")
        .join(
            matched.select("ordinal", "target", "duplicate"),
            on="ordinal",
            how="left",
            validate="1:1",
            nulls_equal=False,
        )
        .sort("ordinal")
    )
    return Links(
        _ordinals(all_rows, "target"),
        tuple(bool(n) for n in all_rows.get_column("duplicate").fill_null(False).to_list()),
        tuple(str(s) for s in complete.sort("ordinal").get_column("section").to_list()),
    )


def duplicate_ids(values: tuple[str | None, ...]) -> bool:
    series = pl.Series("security_id", values, dtype=pl.String)
    return series.n_unique() != len(values)


def included_ordinals(dispositions: tuple[str, ...]) -> tuple[int, ...]:
    frame = pl.DataFrame({"disposition": pl.Series(dispositions, dtype=pl.String)}).with_row_index()
    return tuple(
        int(n)
        for n in frame.filter(pl.col("disposition") == "included-equity")
        .get_column("index")
        .to_list()
    )
