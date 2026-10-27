"""Opt-in actual application fitting/search cost on retained complete inputs.

Question: can the selected complete R1 windows finish inside the explicit 300s
application budget and preserve compact results/originals through recovery?
Explicit invented source facts; no numerical fallback, limit change or calibrated claim.
"""

import argparse
import inspect
import json
import os
import platform
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from functools import wraps
from pathlib import Path
from typing import Any

from candidate_capacity_fixtures import Workload, representative_sources
from measure_history_inputs import inputs, load
from qualify_dcc import peak_working_set

from prosper.advisory_records import encode
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import DATABASE_NAME, AdvisoryStore
from prosper.candidate_workflow import CandidateOutput, check_output_links
from prosper.storage import PersistenceError, RuntimeBoundary

ROOT = Path(__file__).resolve().parents[1]


def worker(peak_path: Path, profile: bool = False) -> None:
    """In-process OS peak probe also survives the supervisor killing this worker.

    Interrupted peaks cover the last 100ms sample, a lower bound; successful
    completion records the final OS peak. No launcher handle is measured.
    """
    from prosper.candidate_worker import main

    timings: dict[str, dict[str, float | int | None]] = {}
    if profile:
        from prosper import candidate_search, candidate_workflow, covariance, dcc, volatility

        def timed(module: Any, name: str) -> None:
            original = getattr(module, name)
            entry: dict[str, float | int | None] = {
                "completed_calls": 0,
                "completed_seconds": 0.0,
                "active_since": None,
            }
            timings[module.__name__ + "." + name] = entry

            @wraps(original)
            def invoke(*args: Any, **kwargs: Any) -> Any:
                started = time.perf_counter()
                entry["active_since"] = started
                try:
                    return original(*args, **kwargs)
                finally:
                    entry["completed_seconds"] = (
                        float(entry["completed_seconds"] or 0) + time.perf_counter() - started
                    )
                    entry["completed_calls"] = int(entry["completed_calls"] or 0) + 1
                    entry["active_since"] = None

            setattr(module, name, invoke)

        for module, names in (
            (volatility, ("evaluate_fixed", "fit_volatility")),
            (dcc, ("_evaluate", "fit_dcc")),
            (covariance, ("prepare_dcc", "compose_covariance")),
            (candidate_workflow, ("prepare",)),
            (candidate_search, ("search",)),
        ):
            for name in names:
                timed(module, name)

    done = threading.Event()

    def record(final: bool) -> None:
        temporary = peak_path.with_suffix(".tmp")
        now = time.perf_counter()
        snapshot = {
            name: {
                "completed_calls": entry["completed_calls"],
                "inclusive_seconds": float(entry["completed_seconds"] or 0)
                + (now - float(entry["active_since"]) if entry["active_since"] is not None else 0),
                "active": entry["active_since"] is not None,
            }
            for name, entry in timings.items()
        }
        temporary.write_text(
            json.dumps({"bytes": peak_working_set(), "final": final, "timings": snapshot})
        )
        os.replace(temporary, peak_path)

    def sample() -> None:
        while not done.wait(0.1):
            record(False)

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    sys.argv = ["candidate_worker"]
    try:
        main()
    finally:
        done.set()
        thread.join()
        record(True)


def recover(store: AdvisoryStore, folder: Path) -> dict[str, Any]:
    """Inspect actual retained work and compare its backup without recalculation."""
    current, catalog = store.current(), store.catalog()
    with sqlite3.connect(store.runtime.path(DATABASE_NAME)) as connection:
        digests = tuple(
            row[0] for row in connection.execute("SELECT sha256 FROM sources ORDER BY sha256")
        )
    # Check originals even when a later backup guard refuses. Unknown is not zero.
    for digest in digests:
        store.source_bytes(digest)
    report: dict[str, Any] = {
        "bytes": None,
        "original_count": len(digests),
        "retained_originals_readable": True,
        "source_database_bytes": store.runtime.path(DATABASE_NAME).stat().st_size,
    }
    try:
        raw = backup(store)
        report["bytes"] = len(raw)
        target = AdvisoryStore(RuntimeBoundary(folder / "restored"))
        restore(target, raw)
        assert target.current() == current
        assert target.catalog() == catalog
        for digest in digests:
            assert target.source_bytes(digest) == store.source_bytes(digest)
        runs, snapshots = catalog["runs"], catalog["snapshots"]
        assert isinstance(runs, list) and isinstance(snapshots, list)
        for run_id in runs:
            assert isinstance(run_id, str)
            assert target.run(run_id) == store.run(run_id)
        for item in snapshots:
            assert isinstance(item, dict) and isinstance(item["id"], str)
            assert target.snapshot(item["id"]) == store.snapshot(item["id"])
        report.update(identical_result_and_originals=True, identical_current_state=True)
    except PersistenceError as error:
        report["refusal"] = error.code
    assert store.current() == current and store.catalog() == catalog
    report["source_state_preserved"] = True
    return report


def measure(
    names: int,
    timeout: int,
    *,
    profile: bool = False,
    workload: Workload | None = None,
) -> dict[str, Any]:
    task = "t007.1.6" if workload else "t007.1.5.5"
    folder = ROOT / ".local" / task / f"{names}-{uuid.uuid4().hex}"
    store = AdvisoryStore(RuntimeBoundary(folder / "source"))
    history, upload = inputs(names, fit_workload=True)
    sources = {
        name: load(name)
        for name in (
            "holdings.json",
            "benchmark.json",
            "benchmark-review.json",
            "lot-settings.json",
            "command.json",
        )
    }
    if workload:
        sources, upload = representative_sources(upload, workload)
    ids = tuple(sorted(s.security_id for s in upload.bundle.history.series))
    command = sources["command.json"]
    revision = 3
    command.update(
        run_id="capacity", input_run_id="capacity-inputs", expected_revision=revision + 1
    )
    command["controls"].update(
        method="deterministic-loss-prefix-repair-v1",
        buy_bounds=command["controls"]["buy_bounds"]
        if workload
        else {sid: 0 for sid in upload.bundle.candidate_security_ids},
        timeout_seconds=timeout,
    )
    declaration = {
        "names": names,
        "held_names": len(
            {lot["security_id"] for lot in sources["holdings.json"]["snapshot"]["lots"]}
        ),
        "lots": len(sources["holdings.json"]["snapshot"]["lots"]),
        "positions": len(sources["holdings.json"]["snapshot"]["positions"]),
        "benchmark_names": names if workload else 2,
        "positive_buy_bounds": sum(q > 0 for q in command["controls"]["buy_bounds"].values()),
        "command": command,
        "lot_settings": sources["lot-settings.json"],
        "profile": upload.bundle.profile.model_dump(mode="json"),
        "investor_controls": [c.model_dump(mode="json") for c in upload.bundle.investor_controls],
        "generator": "PCG64(622241), generated four-decimal OHLC; fictional source facts",
    }
    (folder / "declaration.json").write_text(
        json.dumps(declaration, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n"
    )
    peak_code = "import ctypes,platform\n" + inspect.getsource(peak_working_set)
    worker_code = (
        f"import sys;sys.path.insert(0,{str(ROOT / 'scripts')!r});"
        f"from measure_candidate_capacity import worker;from pathlib import Path;"
        f"worker(Path({str(folder / 'worker-peak.json')!r}),profile={profile!r})"
    )
    code = peak_code + (
        "\nimport subprocess,sys,json\n"
        "from pathlib import Path\n"
        "from prosper import candidate_jobs\n"
        "from prosper.local_api import serve\n"
        "from prosper.storage import RuntimeBoundary\n"
        "original = subprocess.Popen\n"
        "def measured(args, **kwargs):\n"
        "    assert args[1:] == ['-I','-m','prosper.candidate_worker']\n"
        f"    return original([sys.executable,'-I','-c',{worker_code!r}], **kwargs)\n"
        "candidate_jobs.subprocess.Popen = measured\n"
        "serve(runtime=RuntimeBoundary(Path(sys.argv[1])))\n"
        "Path(sys.argv[3]).write_text(json.dumps(peak_working_set()))\n"
    )
    child = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(folder / "source"),
            str(ROOT),
            str(folder / "http-peak.json"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert child.stdout is not None
    origin = json.loads(child.stdout.readline())["origin"]
    headers = {"Origin": origin, "Content-Type": "application/json"}

    def call(path: str, value: Any = None) -> Any:
        payload = None if value is None else json.dumps(value, separators=(",", ":")).encode()
        request_headers = dict(headers)
        req = urllib.request.Request(
            origin + path,
            data=payload,
            headers=request_headers,
        )
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)

    stage = "session"
    admission_failure = None
    received_parts = 0
    candidate_started = False
    try:
        req = urllib.request.Request(
            origin + "/session",
            data=b"",
            headers={
                "Origin": origin,
                "X-Prosper-Bootstrap": "1",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            headers["Authorization"] = "Bearer " + json.load(response)["token"]
        stage = "snapshot-http"
        staged = call("/api/v1/previews", sources["holdings.json"])
        stage = "seed"
        call(
            "/api/v1/select",
            {"snapshot_id": staged["id"], "command_key": "select", "expected_revision": 0},
        )
        stage = "benchmark-http"
        call("/api/v1/benchmarks/import", sources["benchmark.json"])
        call(
            "/api/v1/benchmarks/diagnostics",
            {
                "run_id": "benchmark",
                "expected_revision": 1,
                "as_of": command["as_of"],
                "review": sources["benchmark-review.json"],
            },
        )
        stage = "benchmark-select-http"
        call(
            "/api/v1/benchmarks/select",
            {"run_id": "benchmark", "command_key": "benchmark", "expected_revision": 1},
        )
        stage = "lot-settings-http"
        call(
            "/api/v1/lots/settings",
            {
                "settings": sources["lot-settings.json"],
                "command_key": "settings",
                "expected_revision": 2,
            },
        )
        stage = "history-http"
        part_ids = []
        for part in history.parts:
            part_ids.append(call("/api/v1/history/parts", part.model_dump(mode="json"))["id"])
            received_parts += 1
        manifest = {
            "version": "advisory-history-manifest-v1",
            "part_count": history.part_count,
            "part_ids": part_ids,
            "command_key": "capacity-refresh",
            "expected_revision": revision,
        }
        call("/api/v1/history/preview", manifest)
        call("/api/v1/history/refresh", manifest)
        stage = "modeled-inputs-http"
        diagnostic = call(
            "/api/v1/inputs/diagnostics",
            {
                **upload.model_dump(mode="json"),
                "run_id": "capacity-inputs",
                "expected_revision": revision + 1,
                "as_of": command["as_of"],
            },
        )
        assert diagnostic["outputs"]["software_inputs_complete"]
        assert diagnostic["outputs"]["security_ids"] == list(ids)
        assert diagnostic["outputs"]["return_cell_count"] == names * 1260
        started = time.perf_counter()
        stage = "candidate-http"
        call("/api/v1/candidates/start", command)
        candidate_started = True
        deadline = time.monotonic() + timeout + 30
        while True:
            saved = call("/api/v1/runs/capacity")
            if saved["status"] != "running":
                break
            assert time.monotonic() < deadline, "application supervisor did not stop"
            time.sleep(0.5)
        wall = time.perf_counter() - started
        assert call("/api/v1/candidates/start", command) == saved
    except urllib.error.HTTPError as error:
        admission_failure = {
            "stage": stage,
            "http_status": error.code,
            "response": json.loads(error.read()),
        }
    finally:
        req = urllib.request.Request(origin + "/shutdown", data=b"", headers=headers)
        with urllib.request.urlopen(req, timeout=10):
            pass
        child.wait(timeout=15)
    common = {
        "names": names,
        "sessions": 1260,
        "runtime": str(folder),
        "http_history_bytes": len(history.model_dump_json().encode()),
        "declaration": str(folder / "declaration.json"),
        "workload": {
            key: declaration[key]
            for key in ("held_names", "lots", "positions", "benchmark_names", "positive_buy_bounds")
        },
        "received_history_parts": received_parts,
        "http_process_peak_bytes": json.loads((folder / "http-peak.json").read_bytes()),
        "scope": "Synthetic workload only; no production method/profile/capacity acceptance",
    }
    if admission_failure is not None:
        return {
            **common,
            "admission_failure": admission_failure,
            "candidate_started": candidate_started,
            "admission_scope": "Actual bounded-part HTTP admission",
            "recovery": recover(store, folder),
        }
    result = CandidateOutput.model_validate_json(json.dumps(saved["outputs"]))
    retained = store.candidate_inputs(store.run("capacity").inputs["candidate_inputs"])
    check_output_links(retained, result)
    assert retained.coverage.security_ids == ids
    store.clear_history_cache("capacity-clear", int(command["expected_revision"]))
    recovery = recover(store, folder)
    if recovery.get("identical_result_and_originals"):
        target = AdvisoryStore.existing(RuntimeBoundary(folder / "restored"))
        assert (
            target.candidate_inputs(target.run("capacity").inputs["candidate_inputs"]) == retained
        )
        recovery.update(identical_frozen_candidate_inputs=True, return_cells=names * 1260)
    search = result.search
    return {
        **common,
        "timeout_seconds": timeout,
        "wall_seconds": wall,
        "outcome": result.outcome,
        "issues": result.issues,
        "complete_union_retained": True,
        "result_bytes": len(encode(store.run("capacity")).encode()),
        "risk_bytes": len(result.risk.model_dump_json().encode()) if result.risk else 0,
        "scalar_fits": len(result.risk.scalars) if result.risk else None,
        "scalar_selected": sum(s.selected_start is not None for s in result.risk.scalars)
        if result.risk
        else None,
        "dcc_attempted": result.risk.dcc_fit is not None if result.risk else None,
        "projection_available": result.risk.projection is not None if result.risk else False,
        "search_outcome": search.outcome if search else None,
        "evaluated_states": search.evaluated_states if search else None,
        "checked_points": len(search.candidates) if search else None,
        "stopping": search.stopping if search else None,
        "points": [
            {
                "orders": point.orders.model_dump(mode="json"),
                "metrics": point.metrics.model_dump(mode="json") if point.metrics else None,
            }
            for point in search.candidates
        ]
        if search
        else [],
        "worker_process_peak": json.loads((folder / "worker-peak.json").read_bytes())
        if (folder / "worker-peak.json").exists()
        else None,
        "recovery": recovery,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", type=int, choices=(20, 100, 500), required=True)
    parser.add_argument("--timeout", type=int, default=300, choices=range(1, 301))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--representative", action="store_true")
    args = parser.parse_args()
    if args.representative and args.names != 500:
        parser.error("--representative requires the declared --names 500")
    if args.output.exists():
        parser.error("report destination already exists; select a fresh path")
    report: dict[str, Any] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "case": measure(
            args.names,
            args.timeout,
            profile=args.profile,
            workload=Workload() if args.representative else None,
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as report_file:
        report_file.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "report": str(args.output),
                "outcome": report["case"].get("outcome"),
                "refusal": report["case"].get("admission_failure"),
            }
        )
    )
