"""Synthetic-only import measurements; no broker data, trades or capacity guarantee."""

import argparse
import copy
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import sqlite3
import statistics
import sys
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from time import perf_counter_ns
from typing import Any, cast

from prosper.bundle import MAX_BYTES, parse_bundle
from prosper.checkpoint import Inspection, inspect_checkpoint
from prosper.evidence import EvidenceStore, RuntimeBoundary
from prosper.exact import ExactValue
from prosper.persistence import CheckpointStore
from prosper.previews import PreviewService

ROOT = Path(__file__).resolve().parents[1]
type Document = dict[str, Any]
EXPECTED = {
    "quantity": "5250",
    "basis": "790125",
    "market_value": "527625",
    "settled_cash": "12345.67",
    "settled_cash_nav": "539970.67",
    "market_minus_basis": "-262500",
}


def cents(value: int) -> str:
    return f"{value // 100}.{value % 100:02d}"


def workload() -> bytes:
    """100 stocks, 20 old lots each; lot j has j/4 shares, price 50+i.

    Basis per share is 100+i. Position quantity is stipulated as 52.50;
    a separate Fraction oracle checks the generated rows, not product arithmetic.
    """
    data = cast(Document, json.loads((ROOT / "examples/synthetic/F001.json").read_bytes()))
    data["metadata"].update(
        bundle_id="SCALE-100-2000",
        source_id="SYNTHETIC-MEASUREMENT",
        included_activity_ids=[],
        inclusion={
            "value": "Post-event closing checkpoint; no recent activity stipulated.",
            "reason": None,
        },
        stipulations=[
            "Entirely fictional import-only measurement, no market or broker observations.",
            "100 distinct ordinary domestic common stocks, 20 old lots per position.",
            "All lots acquired 2024-01-02; no recent activity or adjustments stipulated.",
            "Settled/available USD cash 12345.67, unsettled cash explicitly zero.",
            "No financial-use, risk, optimizer or broker-workflow qualification.",
        ],
    )
    security, position, lot, quote = (
        copy.deepcopy(data[family][0]) for family in ("securities", "positions", "lots", "quotes")
    )
    for family in ("securities", "positions", "lots", "quotes", "activity"):
        data[family] = []
    for i in range(1, 101):
        sid = f"SEC-M{i:03d}"
        sec = copy.deepcopy(security)
        sec.update(id=sid, source_ref=f"SRC-{sid}", ticker=f"M{i:03d}")
        sec["issuer_id"]["value"] = f"ISSUER-M{i:03d}"
        sec["share_class_id"]["value"] = f"CLASS-M{i:03d}"
        data["securities"].append(sec)
        pos = copy.deepcopy(position)
        pos.update(
            id=f"POS-{i}",
            source_ref=f"SRC-POS-{i}",
            security_id=sid,
            checkpoint_id="SCALE-100-2000",
        )
        pos["quantity"]["value"] = "52.50"
        data["positions"].append(pos)
        mark = copy.deepcopy(quote)
        mark.update(id=f"MARK-{i}", source_ref=f"SRC-MARK-{i}", security_id=sid)
        mark["price"]["value"] = str(50 + i)
        data["quotes"].append(mark)
        for j in range(1, 21):
            row = copy.deepcopy(lot)
            row.update(
                id=f"LOT-{i}-{j}",
                source_ref=f"SRC-LOT-{i}-{j}",
                security_id=sid,
                checkpoint_id="SCALE-100-2000",
            )
            row["quantity"]["value"] = cents(j * 25)
            row["basis"]["value"] = cents(j * (100 + i) * 25)
            data["lots"].append(row)
    data["cash"][0]["checkpoint_id"] = "SCALE-100-2000"
    for field in ("settled", "available"):
        data["cash"][0][field]["value"] = "12345.67"
    return (json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n").encode()


def verify_workload(raw: bytes) -> dict[str, str]:
    """Independent rational-number totals and per-stock reconciliation oracle.

    sum(j/4, j=1..20)=52.5. Sum stock indices=5050. Thus holdings
    value=52.5*(5000+5050)=527625; basis=52.5*(10000+5050)=790125.
    No product parser, exact-value helper or inspection is used by this oracle.
    """
    data = json.loads(raw)
    assert data["metadata"]["fictional"] is True
    assert data["metadata"]["bundle_id"] == "SCALE-100-2000"
    assert data["metadata"]["included_activity_ids"] == [] and data["activity"] == []
    assert len(raw) <= MAX_BYTES
    assert len(data["securities"]) == len(data["positions"]) == len(data["quotes"]) == 100
    assert len(data["lots"]) == 2000
    ids = {row["id"] for row in data["securities"]}
    assert len(ids) == 100
    assert {row["security_id"] for row in data["lots"]} == ids
    assert {row["security_id"] for row in data["positions"]} == ids
    assert {row["security_id"] for row in data["quotes"]} == ids
    quantity = basis = market = Fraction(0)
    for pos in data["positions"]:
        sid = pos["security_id"]
        rows = [row for row in data["lots"] if row["security_id"] == sid]
        marks = [row for row in data["quotes"] if row["security_id"] == sid]
        assert len(rows) == 20 and len(marks) == 1
        qty = sum((Fraction(row["quantity"]["value"]) for row in rows), Fraction(0))
        assert qty == Fraction(pos["quantity"]["value"]) == Fraction(105, 2)
        assert all(row["acquired"]["value"] == "2024-01-02" for row in rows)
        quantity += qty
        basis += sum((Fraction(row["basis"]["value"]) for row in rows), Fraction(0))
        market += qty * Fraction(marks[0]["price"]["value"])
    cash = data["cash"]
    assert len(cash) == 1
    settled = Fraction(cash[0]["settled"]["value"])
    assert settled == Fraction(cash[0]["available"]["value"])
    assert Fraction(cash[0]["unsettled"]["value"]) == 0
    actual = dict(
        zip(
            EXPECTED,
            (quantity, basis, market, settled, market + settled, market - basis),
            strict=True,
        )
    )
    assert actual == {key: Fraction(value) for key, value in EXPECTED.items()}
    return EXPECTED.copy()


def check_inspection(inspection: Inspection, expected: dict[str, str]) -> None:
    assert inspection.validated is not None
    assert inspection.readiness.inspection == "complete"
    assert not inspection.readiness.planning_ready
    for field in ("total_basis", "settled_cash_nav", "market_minus_basis"):
        value = getattr(inspection, field)
        assert isinstance(value, ExactValue)
        key = "basis" if field == "total_basis" else field
        assert value.canonical == expected[key]


def checked_parse_inspect(raw: bytes, expected: dict[str, str]) -> Inspection:
    parsed = parse_bundle(raw)
    assert parsed.parsed is not None and not parsed.issues
    result = inspect_checkpoint(parsed.parsed)
    check_inspection(result, expected)
    return result


def sample(operation: Callable[[], object], repeats: int) -> dict[str, object]:
    def once() -> float:
        start = perf_counter_ns()
        operation()
        return (perf_counter_ns() - start) / 1_000_000

    first = once()
    for _ in range(2):
        operation()
    values = [once() for _ in range(repeats)]
    return {
        "first_ms": first,
        "samples_ms": values,
        "median_ms": statistics.median(values),
        "p95_ms": sorted(values)[math.ceil(0.95 * repeats) - 1],
        "max_ms": max(values),
    }


def measure(raw: bytes, expected: dict[str, str], output: Path, repeats: int) -> Document:
    # All correctness assertions are outside the timed operations.
    baseline = checked_parse_inspect(raw, expected)
    parsed = baseline.source
    results: Document = {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "expected": expected,
        "parse": sample(lambda: parse_bundle(raw), repeats),
        "inspect_preparsed": sample(lambda: inspect_checkpoint(parsed), repeats),
    }

    def combined() -> Inspection:
        result = parse_bundle(raw)
        assert result.parsed is not None
        return inspect_checkpoint(result.parsed)

    results["parse_and_inspect"] = sample(combined, repeats)
    # Fresh DB/schema setup and runtime construction excluded from stage timing.
    fresh: list[PreviewService] = []
    for i in range(repeats + 3):
        evidence = EvidenceStore(RuntimeBoundary(output / f"runtime-{i}", ROOT, "synthetic"))
        fresh.append(PreviewService(CheckpointStore(evidence)))
    fresh_iter = iter(fresh)
    results["stage_new"] = sample(lambda: next(fresh_iter).stage(raw), repeats)
    service = fresh[-1]
    staged = service.get(hashlib.sha256(raw).hexdigest())
    assert staged.inspection is not None
    check_inspection(staged.inspection, expected)
    results["stage_repeat"] = sample(lambda: service.stage(raw), repeats)
    assert service.get(staged.receipt.raw_sha256) == staged
    results["target_ms"] = 2000
    results["all_combined_under_target"] = (
        max(results["parse_and_inspect"]["first_ms"], results["parse_and_inspect"]["max_ms"])
        <= 2000
    )
    results["all_new_stages_under_target"] = (
        max(results["stage_new"]["first_ms"], results["stage_new"]["max_ms"]) <= 2000
    )
    return results


def footprint() -> list[Document]:
    result = []
    for dist in importlib.metadata.distributions():
        paths = [Path(str(dist.locate_file(file))) for file in (dist.files or ())]
        result.append(
            {
                "name": dist.metadata["Name"],
                "version": dist.version,
                "recorded_file_bytes": sum(path.stat().st_size for path in paths if path.is_file()),
            }
        )
    return sorted(result, key=lambda row: str(row["name"]).lower())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / ".local") or output.exists():
        parser.error("output must be a new project-local .local directory")
    if not 3 <= args.repeats <= 100:
        parser.error("repeats must be 3..100")
    output.mkdir(parents=True)
    raw = workload()
    expected = verify_workload(raw)
    (output / "SCALE-100-2000.json").write_bytes(raw)
    results = {
        "method": "perf_counter_ns wall time; first call then 2 warmups and N samples; "
        "p95 nearest rank; GC enabled; OS caches not cleared; sequential single process; "
        "source collection/UI/HTTP and runtime initialization excluded; no concurrent load",
        "repeats": args.repeats,
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": os.environ.get("PROCESSOR_IDENTIFIER", platform.processor()),
            "logical_cpus": os.cpu_count(),
            "python": sys.version,
            "sqlite": sqlite3.sqlite_version,
        },
        "installed_distribution_footprint": footprint(),
        "F001": measure(
            (ROOT / "examples/synthetic/F001.json").read_bytes(),
            {"basis": "2181", "settled_cash_nav": "2399", "market_minus_basis": "-101"},
            output / "F001",
            args.repeats,
        ),
        "SCALE-100-2000": measure(raw, expected, output / "scale", args.repeats),
    }
    (output / "measurements.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Synthetic import measurements: {output / 'measurements.json'}")


if __name__ == "__main__":
    main()
