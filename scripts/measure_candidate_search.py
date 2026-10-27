"""Measure bounded synthetic search and actual HTTP/schema refusal boundaries.

Question: can this explicitly experimental construction return checked points at
20/100/500 names, and which current application boundary prevents a full R1 run?
No model fits, source qualification or production method acceptance is implied.
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
from qualify_dcc import peak_working_set

from prosper.candidate_records import CandidateRequest
from prosper.candidate_search import METHOD, search

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples/synthetic/candidates"


def problem(names: int, *, max_states: int = 12) -> CandidateRequest:
    """Invented full universe/three-lot sleeve with an explicit stipulated PSD matrix."""
    document = json.loads((FIXTURES / "tiny-request.json").read_bytes())
    snapshot = document["snapshot"]
    original_security = snapshot["securities"][0]
    original_lot = snapshot["lots"][0]
    ids = [f"S{i:04d}" for i in range(names)]
    securities = [
        dict(
            **{
                k: v
                for k, v in original_security.items()
                if k not in ("id", "ticker", "identity", "source_ref")
            },
            id=sid,
            ticker=f"FICT{i:04d}",
            identity={"value": "fictional:" + sid, "reason": None},
            source_ref="identity:" + sid,
        )
        for i, sid in enumerate(ids)
    ]
    lots = [
        dict(
            **{
                k: v
                for k, v in original_lot.items()
                if k not in ("id", "security_id", "source_ref", "quantity", "total_basis")
            },
            id=f"L{i:04d}-{j}",
            security_id=sid,
            source_ref=f"row:{3 * i + j + 2}",
            quantity={"value": "3.5", "reason": None},
            total_basis={"value": "42", "reason": None},
        )
        for i, sid in enumerate(ids)
        for j in range(3)
    ]
    raw = (
        "lot,security,quantity,basis\n"
        + "\n".join(f"{lot['id']},{lot['security_id']},3.5,42" for lot in lots)
        + "\n"
    ).encode()
    snapshot.update(
        securities=securities,
        lots=lots,
        source_type="fictional-search-workload",
        source_name="fictional-search.csv",
        source_sha256=hashlib.sha256(raw).hexdigest(),
    )
    context = snapshot["observations"]["lot_context"]
    context["source_sha256"] = snapshot["source_sha256"]
    context["mappings"] = []
    document["assets"] = [
        dict(
            security=s,
            sector={"value": f"Sector-{i % 10}", "reason": None},
            industry={"value": f"Industry-{i % 25}", "reason": None},
        )
        for i, s in enumerate(securities)
    ]
    document["settings"]["marks"] = [
        dict(
            security_id=sid,
            identity="fictional:" + sid,
            price={"value": "10", "reason": None},
            day={"value": "2026-10-23", "reason": None},
            source_ref="stipulated-mark:" + sid,
            currency="USD",
        )
        for sid in ids
    ]
    document["settings"]["sell_fee_per_isolated_order"]["value"] = "1"
    document["settings"]["sell_discount_bps"]["value"] = "10"
    document["risk"].update(
        security_ids=ids,
        benchmark_ids=ids,
        benchmark_weights=[1 / names] * names,
        annual_covariance=(0.04 * np.eye(names) + 0.01 * np.ones((names, names))).tolist(),
        reference="Stipulated PSD .04*I+.01*11'; no fitted or investor risk",
    )
    document["limits"].update(tracking_error="0.05", max_orders=6, max_cost="50", max_turnover="1")
    document.update(
        method=METHOD,
        max_candidates=3,
        max_states=max_states,
        sale_bounds={lot["id"]: 3 for lot in lots},
        buy_bounds={sid: 100 for sid in ids},
        buy_fee_per_security_order="1",
        buy_premium_bps="10",
    )
    return CandidateRequest.model_validate_json(json.dumps(document))


def boundary(names: int) -> dict[str, Any]:
    from measure_history_inputs import measure as measure_inputs

    return measure_inputs(names)


def measure(names: int) -> dict[str, Any]:
    request = problem(names)
    before, cpu = time.perf_counter(), time.process_time()
    result = search(request)
    elapsed, used = time.perf_counter() - before, time.process_time() - cpu
    return dict(
        names=names,
        lots=3 * names,
        source_sha256=request.snapshot.source_sha256,
        method=result.method,
        budget=request.max_states,
        outcome=result.outcome,
        stopping=result.stopping,
        checked_proposals=result.evaluated_states,
        feasible=result.feasible_harvests,
        points=[c.metrics.model_dump(mode="json") for c in result.candidates if c.metrics],
        search_wall_seconds=elapsed,
        search_cpu_seconds=used,
        application=boundary(names),
        process_peak_bytes=peak_working_set(),
        memory_scope=(
            "whole measurement worker including source/request generation; "
            "separate HTTP server excluded"
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=int, choices=(20, 100, 500))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(measure(args.worker), allow_nan=False))
        return
    if args.output is None or not args.output.resolve().is_relative_to(ROOT / ".local"):
        parser.error("an exclusive report destination under .local is required")
    report: dict[str, Any] = dict(
        version="candidate-search-measurement-v1",
        host=platform.platform(),
        python=platform.python_version(),
        processor=platform.processor(),
        logical_cpus=os.cpu_count(),
        numpy=np.__version__,
        polars=version("polars"),
        scope=(
            "synthetic candidate component and separate complete-input boundary; "
            "no larger R1 fit claim"
        ),
        cases=[],
    )
    for names in (20, 100, 500):
        before = time.perf_counter()
        try:
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker", str(names)],
                capture_output=True,
                timeout=300,
                check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            case = json.loads(completed.stdout)
        except subprocess.CalledProcessError as error:
            case = dict(
                names=names,
                lots=3 * names,
                outcome="measurement-failed",
                returncode=error.returncode,
                detail=error.stderr.decode(errors="replace")[-1000:],
            )
        except subprocess.TimeoutExpired:
            case = dict(names=names, lots=3 * names, outcome="measurement-timeout", points=None)
        case["whole_worker_wall_seconds"] = time.perf_counter() - before
        report["cases"].append(case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(
        json.dumps(
            dict(
                report=str(args.output),
                cases=[
                    {k: case[k] for k in ("names", "lots", "outcome", "whole_worker_wall_seconds")}
                    for case in report["cases"]
                ],
            ),
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
