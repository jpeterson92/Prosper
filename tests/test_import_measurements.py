"""Independent workload oracle and meaningful corruption checks, never timing gates."""

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from prosper.bundle import parse_bundle
from prosper.checkpoint import inspect_checkpoint
from prosper.exact import ExactValue

SPEC = importlib.util.spec_from_file_location(
    "measure_imports", Path(__file__).resolve().parents[1] / "scripts/measure_imports.py"
)
assert SPEC is not None and SPEC.loader is not None
measurement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measurement)


def test_target_workload_is_deterministic_and_reconciles_independent_totals() -> None:
    raw = measurement.workload()
    assert raw == measurement.workload()
    assert measurement.verify_workload(raw) == {
        "quantity": "5250",
        "basis": "790125",
        "market_value": "527625",
        "settled_cash": "12345.67",
        "settled_cash_nav": "539970.67",
        "market_minus_basis": "-262500",
    }
    parsed = parse_bundle(raw)
    assert parsed.parsed is not None and not parsed.issues
    inspection = inspect_checkpoint(parsed.parsed)
    measurement.check_inspection(inspection, measurement.EXPECTED)
    assert len(inspection.positions) == 100
    for pos in inspection.positions:
        assert isinstance(pos.quantity, ExactValue) and pos.quantity.canonical == "52.5"
        assert isinstance(pos.lot_quantity, ExactValue)
        assert pos.quantity.canonical == pos.lot_quantity.canonical
        assert pos.quantity.original_text == "52.50"
    assert inspection.readiness.basis == inspection.readiness.valuation == "complete"


@pytest.mark.parametrize("fault", ["basis", "quantity", "price", "cash", "count", "fictional"])
def test_independent_oracle_refuses_corrupted_workload(fault: str) -> None:
    data: dict[str, Any] = json.loads(measurement.workload())
    if fault in ("basis", "quantity"):
        data["lots"][0][fault]["value"] = "999"
    elif fault == "price":
        data["quotes"][0]["price"]["value"] = "999"
    elif fault == "cash":
        data["cash"][0]["available"]["value"] = "0"
    elif fault == "count":
        data["lots"].pop()
    else:
        data["metadata"]["fictional"] = False
    with pytest.raises(AssertionError):
        measurement.verify_workload(json.dumps(data).encode())
