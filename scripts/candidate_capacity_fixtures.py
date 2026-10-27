"""Invented source-shaped portfolio/benchmark pressure for the opt-in capacity run."""

import base64
import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from measure_history_inputs import load

from prosper import benchmark_reconciliation as reconciliation
from prosper import vanguard
from prosper.modeled_inputs import ModeledUpload


@dataclass(frozen=True)
class Workload:
    held_names: int = 100
    lots_per_name: int = 20
    buy_names: int = 25


def representative_sources(
    upload: ModeledUpload, workload: Workload
) -> tuple[dict[str, Any], ModeledUpload]:
    """Create explicit original bytes and located review facts, never market data.

    Python construction is appropriate here: these are nested fictional source
    records; the application still owns tabular reconciliation and calculations.
    History and attributable mark/identity/classification originals are unchanged.
    """
    model = json.loads(upload.model_dump_json())
    bundle = model["bundle"]
    ids = [s["security_id"] for s in bundle["securities"]]
    if (
        workload.held_names < 1
        or workload.lots_per_name < 1
        or workload.buy_names < 1
        or workload.held_names + workload.buy_names > len(ids)
        or workload.held_names * workload.lots_per_name > 2000
    ):
        raise ValueError("explicit_complete_representative_shape_required")
    held = ids[: workload.held_names]
    buy = ids[workload.held_names : workload.held_names + workload.buy_names]
    bundle["candidate_security_ids"] = buy
    values = {
        "tracking_error": "0.20",
        "max_orders": "30",
        "turnover": "0.50",
        "min_trade_notional": "10",
        "max_position_weight": "0.05",
    }
    for control in bundle["investor_controls"]:
        control["reference"] = "Predeclared fictional workload control; not an investor setting"
        if control["name"] in values:
            control.update(enabled=True, value={"value": values[control["name"]], "reason": None})
        else:
            control.update(
                enabled=False,
                value={"value": None, "reason": "Explicitly disabled in fictional workload"},
            )

    sources = {name: load(name) for name in ("holdings.json", "lot-settings.json", "command.json")}
    snapshot = sources["holdings.json"]["snapshot"]
    security_template = snapshot["securities"][0]
    snapshot["securities"] = [
        {
            **security_template,
            "id": s["security_id"],
            "ticker": "FICT" + str(i).zfill(4),
            "source_ref": "fictional-identity:" + s["security_id"],
            "identity": s["identity"],
            "classification": s["classification"],
        }
        for i, s in enumerate(bundle["securities"][: workload.held_names])
    ]
    lot_template = snapshot["lots"][0]
    lots = [
        {
            **lot_template,
            "id": f"L{i:04d}-{j:02d}",
            "security_id": sid,
            "source_ref": f"fictional-portfolio.csv:{2 + i * workload.lots_per_name + j}",
            "quantity": {"value": "2.5000", "reason": None},
            "total_basis": {
                "value": ("30.00", "32.50", "35.00", "37.50", "40.00")[j % 5],
                "reason": None,
            },
        }
        for i, sid in enumerate(held)
        for j in range(workload.lots_per_name)
    ]
    raw = (
        "fictional-security,lot,quantity,total_basis,acquired,term\n"
        + "".join(
            f"{lot['security_id']},{lot['id']},2.5000,{lot['total_basis']['value']},"
            "2000-01-01,long-term\n"
            for lot in lots
        )
    ).encode()
    snapshot.update(
        source_type="fictional-representative-workload",
        source_name="fictional-portfolio.csv",
        source_sha256=hashlib.sha256(raw).hexdigest(),
        lots=lots,
        positions=[],
        observations={},
    )
    context = load("holdings.json")["snapshot"]["observations"]["lot_context"]
    context.update(
        source_sha256=snapshot["source_sha256"],
        accounts=[context["accounts"][0]],
        mappings=[
            {
                "source_account": context["accounts"][0]["source_account"],
                "symbol": security["ticker"],
                "security": security,
                "evidence": context["evidence"],
            }
            for security in snapshot["securities"]
        ],
    )
    snapshot["observations"] = {"lot_context": context, "screening": context["screening"]}
    sources["holdings.json"]["source_base64"] = base64.b64encode(raw).decode()
    settings = sources["lot-settings.json"]
    settings.update(
        marks=[m["mark"] for m in bundle["marks"]],
        sell_fee_per_isolated_order={"value": "1", "reason": None},
        sell_discount_bps={"value": "10", "reason": None},
        cash_to_invest="100",
    )
    sources["command.json"]["controls"].update(
        buy_fee_per_security_order="1",
        buy_premium_bps="10",
        sale_bounds={lot["id"]: 2 for lot in lots},
        buy_bounds=dict.fromkeys(buy, 100),
        max_cost="50",
    )

    fixture = load("benchmark.json")
    review = load("benchmark-review.json")
    day = fixture["request"]["requested_date"]
    # All source values are strings, preserving exact original JSON lexemes.
    rows = [
        {
            "holdingName": "Fictional complete benchmark " + sid,
            "ticker": "FICT" + str(i).zfill(4),
            "cusip": "FICT" + str(i).zfill(5),
            "currency": "USD",
            "marketValue": "100.00",
            "percentOfFunds": "",  # Deliberately unknown; weights use retained value/E.
        }
        for i, sid in enumerate(ids)
    ]
    sections = {name: rows if name == "equity" else [] for name in vanguard.SECTIONS}
    benchmark_raw = json.dumps({day: sections}, separators=(",", ":")).encode()
    fixture["source_base64"] = base64.b64encode(benchmark_raw).decode()
    evidence = copy.deepcopy(review["stipulation"]["fund_assertion"])
    metadata = json.dumps(
        {"reference": "Complete invented benchmark mappings", "ids": ids},
        separators=(",", ":"),
    ).encode()
    evidence["source_sha256"] = hashlib.sha256(metadata).hexdigest()
    stipulation = review["stipulation"]
    stipulation.update(
        raw_sha256=hashlib.sha256(benchmark_raw).hexdigest(),
        fund_assertion=evidence,
        sections=[
            {
                **section,
                "role": "primary" if section["section"] == "equity" else "empty",
                "evidence": evidence,
            }
            for section in stipulation["sections"]
        ],
        rows=[
            {
                "locator": {"section": "equity", "index": i},
                "row_sha256": reconciliation.row_identity(vanguard.JsonObject(tuple(row.items()))),
                "security": {
                    "security_id": ids[i],
                    "currency": "USD",
                    "asset_type": "stock",
                    "evidence": evidence,
                    "unknown_reasons": [],
                },
                "target": None,
                "evidence": evidence,
            }
            for i, row in enumerate(rows)
        ],
    )
    stipulation["benchmark_cash"]["evidence"] = evidence
    review["metadata_base64"] = base64.b64encode(metadata).decode()
    review["policy"]["decisions"] = [
        {
            "locator": {"section": "equity", "index": i},
            "action": "include",
            "reason": "Explicit fictional common equity",
        }
        for i in range(len(ids))
    ]
    sources.update({"benchmark.json": fixture, "benchmark-review.json": review})
    return sources, ModeledUpload.model_validate_json(json.dumps(model))
