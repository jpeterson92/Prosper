"""Deliberate complete-window HTTP/input/recovery measurement; never fits a model.

Question: do declared 20/100/500-name R1 input windows pass the real bounded
transport, immutable records, backup/restore and isolated worker input reader?
Synthetic simple OHLC is a dimensional workload, not a calibrated risk sample.
"""

import argparse
import base64
import copy
import hashlib
import inspect
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import zlib
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from qualify_dcc import peak_working_set

from prosper.advisory_records import encode
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import AdvisoryStore
from prosper.api_contracts import HistoryUpload
from prosper.candidate_workflow import CandidateStart, FrozenCandidate
from prosper.history_table import OBSERVATION_SCHEMA, HistoryTable, SessionGrid
from prosper.modeled_inputs import ModeledResult, ModeledUpload
from prosper.storage import PersistenceError, RuntimeBoundary
from prosper.worker_packet import encode_input

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples/synthetic/candidates/application"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_bytes())


def inputs(names: int, *, fit_workload: bool = False) -> tuple[HistoryUpload, ModeledUpload]:
    model = load("modeled.json")
    bundle = model["bundle"]
    days = [bundle["history"]["predecessor"], *bundle["history"]["sessions"]]
    ids = ["security-faaa", "security-fbbb", *[f"S{i:04d}" for i in range(2, names)]]
    templates = {k: copy.deepcopy(bundle[k]) for k in ("securities", "marks", "classifications")}
    context = bundle["history"]["series"][0]
    contexts = []
    parts = []
    generated: list[dict[str, list[float]]] = []
    if fit_workload:
        # Explicit invented fit workload, independent of the dimensional source.
        # Rounded generated OHLC are the source facts, not a repair of market data.
        rng = np.random.Generator(np.random.PCG64(622241))
        shocks = rng.standard_normal((len(days) - 1, names + 1))
        for i in range(names):
            series = {key: [100.0] for key in ("open", "high", "low", "close", "adjusted_close")}
            previous, variance = 100.0, 0.0001
            for common, specific in zip(shocks[:, 0], shocks[:, i + 1], strict=True):
                r = float(np.sqrt(variance) * (common + specific) / np.sqrt(2))
                close = previous * (1 + r)
                opening = previous * float(np.exp(0.3 * r + 0.001 * specific))
                padding = 0.001 + 0.002 * abs(float(common))
                values = (
                    opening,
                    max(opening, close) * (1 + padding),
                    min(opening, close) / (1 + padding),
                    close,
                    close,
                )
                for key, value in zip(series, values, strict=True):
                    series[key].append(round(value, 4))
                previous = close
                variance = 0.000002 + 0.06 * r * r + 0.92 * variance
            generated.append(series)
    for k in templates:
        bundle[k] = []
    for i, sid in enumerate(ids):
        ctx = {**context, "security_id": sid, "provider_symbol": sid}
        contexts.append(ctx)
        prices = [100 + i / 100 + (j % 97) / 100 for j in range(len(days))]
        columns: dict[str, Any] = {
            "security_id": [sid] * len(days),
            "session": days,
            "source_ref": [f"row:{j + 2}" for j in range(len(days))],
            **{k: [None] * len(days) for k in OBSERVATION_SCHEMA if k.endswith("_reason")},
            "open": prices,
            "close": prices,
            "adjusted_close": prices,
            "high": [p + 1 for p in prices],
            "low": [p - 1 for p in prices],
            "action": ["none"] * len(days),
        }
        if fit_workload:
            columns.update(generated[i])
        frame = pl.DataFrame(columns, schema=OBSERVATION_SCHEMA)
        raw = (
            "fictional-security="
            + sid
            + "\n"
            + frame.select(
                "session", "open", "high", "low", "close", "adjusted_close", "action"
            ).write_csv()
        ).encode()
        batch = {
            "version": "advisory-history-v2",
            "source_name": "Fictional complete-window " + sid,
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "collected_at": bundle["history"]["known_at"],
            "validated_at": bundle["history"]["known_at"],
            "contexts": [ctx],
            "sessions": SessionGrid.pack(tuple(days)).model_dump(mode="json"),
            "validation_scope": "full-window",
            "rows": HistoryTable.pack(frame, "observations").model_dump(mode="json"),
        }
        parts.append(
            {"batch": batch, "source_zlib_base64": base64.b64encode(zlib.compress(raw)).decode()}
        )
        for key, examples in templates.items():
            entry = copy.deepcopy(examples[i % 2])
            if key == "marks":
                entry["mark"]["security_id"] = sid
            else:
                entry["security_id"] = sid
            if i >= 2:
                identity = "fictional-identity:" + sid
                if key == "securities":
                    entry["identity"]["value"] = identity
                if key == "marks":
                    entry["mark"]["identity"] = identity
            bundle[key].append(entry)
    facts = json.dumps(
        {
            "securities": bundle["securities"],
            "marks": bundle["marks"],
            "classifications": bundle["classifications"],
        },
        separators=(",", ":"),
    ).encode()
    digest = hashlib.sha256(facts).hexdigest()
    for key in templates:
        for i, entry in enumerate(bundle[key]):
            entry["evidence"]["source_sha256"] = digest
            entry["evidence"]["source_ref"] = f"{key}/{i}"
    model["sources"] = [{"sha256": digest, "source_base64": base64.b64encode(facts).decode()}]
    bundle["candidate_security_ids"] = ids[1:]
    bundle["history"]["series"] = contexts
    bundle["profile"]["maximum_universe_size"] = names
    return (
        HistoryUpload.model_validate_json(
            json.dumps(
                {
                    "part_count": names,
                    "parts": parts,
                    "command_key": "history",
                    "expected_revision": 3,
                }
            )
        ),
        ModeledUpload.model_validate_json(json.dumps(model)),
    )


def measure(names: int, *, varied: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    history, model = inputs(names, fit_workload=varied)
    folder = (
        ROOT
        / (".local/t007.1.5.3" if varied else ".local/t007.1.4.1")
        / f"{names}-{uuid.uuid4().hex}"
    )
    peak_code = "import ctypes,platform\n" + inspect.getsource(peak_working_set)
    code = peak_code + (
        "\nfrom pathlib import Path;import sys,json;from prosper.local_api import serve;"
        "from prosper.storage import RuntimeBoundary;"
        "serve(runtime=RuntimeBoundary(Path(sys.argv[1])));"
        "Path(sys.argv[3]).write_text(json.dumps(peak_working_set()),encoding='utf-8')"
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
    token = None
    failure = None
    stage = "session"

    def call(path: str, value: Any = None) -> Any:
        req = urllib.request.Request(
            origin + path,
            data=None if value is None else json.dumps(value, separators=(",", ":")).encode(),
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)

    try:
        for _ in range(40):
            try:
                req = urllib.request.Request(
                    origin + "/session",
                    data=b"",
                    headers={"Origin": origin, "X-Prosper-Bootstrap": "1"},
                )
                with urllib.request.urlopen(req, timeout=3) as response:
                    token = json.load(response)["token"]
                break
            except OSError:
                time.sleep(0.05)
        assert token
        headers["Authorization"] = "Bearer " + token
        staged = call("/api/v1/previews", load("holdings.json"))
        call(
            "/api/v1/select",
            {"snapshot_id": staged["id"], "command_key": "select", "expected_revision": 0},
        )
        call("/api/v1/benchmarks/import", load("benchmark.json"))
        call(
            "/api/v1/benchmarks/diagnostics",
            {
                "run_id": "benchmark",
                "expected_revision": 1,
                "as_of": "2026-10-25T23:00:00Z",
                "review": load("benchmark-review.json"),
            },
        )
        call(
            "/api/v1/benchmarks/select",
            {"run_id": "benchmark", "command_key": "benchmark", "expected_revision": 1},
        )
        call(
            "/api/v1/lots/settings",
            {
                "settings": load("lot-settings.json"),
                "command_key": "settings",
                "expected_revision": 2,
            },
        )
        stage = "history-parts"
        part_ids = [
            call("/api/v1/history/parts", part.model_dump(mode="json"))["id"]
            for part in history.parts
        ]
        body = {
            "version": "advisory-history-manifest-v1",
            "part_count": history.part_count,
            "part_ids": part_ids,
            "command_key": history.command_key,
            "expected_revision": history.expected_revision,
        }
        stage = "history-preview"
        call("/api/v1/history/preview", body)
        stage = "history-activation"
        refreshed = call("/api/v1/history/refresh", body)
        assert refreshed == {"outcome": "changed", "revision": 4}
        assert call("/api/v1/history/refresh", body) == refreshed
        diagnostic = {
            **model.model_dump(mode="json"),
            "run_id": "inputs",
            "expected_revision": 4,
            "as_of": "2026-10-25T23:00:00Z",
        }
        stage = "modeled-inputs"
        saved = call("/api/v1/inputs/diagnostics", diagnostic)
        assert saved["outputs"]["software_inputs_complete"]
        assert saved["outputs"]["return_cell_count"] == names * 1260
        assert saved["outputs"]["unavailable_return_count"] == 0
        assert saved["outputs"]["security_ids"] == sorted(
            s.security_id for s in model.bundle.history.series
        )
    except urllib.error.HTTPError as error:
        failure = {"stage": stage, "http_status": error.code, "response": json.loads(error.read())}
    finally:
        if token:
            req = urllib.request.Request(origin + "/shutdown", data=b"", headers=headers)
            with urllib.request.urlopen(req, timeout=5):
                pass
        child.wait(timeout=10)
    http_peak = json.loads((folder / "http-peak.json").read_bytes())
    store = AdvisoryStore.existing(RuntimeBoundary(folder / "source"))
    if failure is not None:
        # A refusal is the measured result. Preserve every received original;
        # do not raise a guard or fit a smaller union to produce a success label.
        for part in history.parts:
            assert store.source_bytes(part.batch.source_sha256) == zlib.decompress(
                base64.b64decode(part.source_zlib_base64)
            )
        recovery: dict[str, Any]
        try:
            raw_backup = backup(store)
            target = AdvisoryStore(RuntimeBoundary(folder / "restored"))
            restore(target, raw_backup)
            for part in history.parts:
                assert target.source_bytes(part.batch.source_sha256) == store.source_bytes(
                    part.batch.source_sha256
                )
            recovery = {"bytes": len(raw_backup), "originals_equal": True}
        except PersistenceError as error:
            recovery = {"refusal": error.code}
        pending = store.catalog()["pending_history_parts"]
        assert isinstance(pending, list)
        return {
            "names": names,
            "sessions": 1260,
            "varied": varied,
            "runtime": str(folder),
            "source_parts": history.part_count,
            "http_file_bytes": len(history.model_dump_json().encode()),
            "largest_part_request_bytes": max(
                len(p.model_dump_json().encode()) for p in history.parts
            ),
            "active_parts": len(store.history_batches()),
            "pending_parts": len(pending),
            "received_originals_equal": True,
            "refusal": failure,
            "recovery": recovery,
            "fitting_attempted": False,
            "wall_seconds": time.perf_counter() - started,
        }
    run = store.run("inputs")
    frozen = store.modeled_inputs(run.inputs["modeled_inputs"])
    controls = load("command.json")
    controls.update(input_run_id="inputs", expected_revision=4)
    controls["controls"].update(
        method="deterministic-loss-prefix-repair-v1",
        buy_bounds={sid: 0 for sid in model.bundle.candidate_security_ids},
    )
    command = CandidateStart.model_validate_json(json.dumps(controls))
    packet = FrozenCandidate(
        command=command,
        modeled=frozen,
        coverage=ModeledResult.model_validate_json(json.dumps(run.outputs)),
        snapshot=store.snapshot(run.snapshot_id),
        retained_snapshots=(),
        required_sources=frozen.retained_sources,
    )
    raw = encode_input(packet)
    worker_code = peak_code + (
        "\nfrom pathlib import Path;import sys,json;from prosper.candidate_worker import main;"
        "peak_path=Path(sys.argv[1]);sys.argv=['prosper.candidate_worker','--inspect-input'];"
        "main();peak_path.write_text(json.dumps(peak_working_set()),encoding='utf-8')"
    )
    worker = subprocess.run(
        [sys.executable, "-I", "-c", worker_code, str(folder / "reader-peak.json")],
        input=raw,
        capture_output=True,
        timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert worker.returncode == 0 and not worker.stderr
    stdout = worker.stdout
    worker_peak = json.loads((folder / "reader-peak.json").read_bytes())
    inspected = json.loads(stdout)
    assert inspected == {"names": names, "return_cells": names * 1260, "fitting_attempted": False}
    store.clear_history_cache("clear", 4)
    try:
        backup_bytes = backup(store)
    except PersistenceError as error:
        return {
            "names": names,
            "sessions": 1260,
            "varied": varied,
            "runtime": str(folder),
            "http_history_bytes": len(history.model_dump_json().encode()),
            "largest_part_request_bytes": max(
                len(p.model_dump_json().encode()) for p in history.parts
            ),
            "http_and_input_diagnostics_complete": True,
            "worker_reader": inspected,
            "worker_input_bytes": len(raw),
            "recovery": {"refusal": error.code},
            "fitting_attempted": False,
            "wall_seconds": time.perf_counter() - started,
        }
    target = AdvisoryStore(RuntimeBoundary(folder / "restored"))
    restore(target, backup_bytes)
    assert target.run("inputs") == run
    assert target.modeled_inputs(run.inputs["modeled_inputs"]) == frozen
    for part in history.parts:
        assert target.source_bytes(part.batch.source_sha256) == zlib.decompress(
            base64.b64decode(part.source_zlib_base64)
        )
    with store._connection() as connection:
        count, size = connection.execute(
            "SELECT count(*),sum(length(document)) FROM input_records"
        ).fetchone()
    return {
        "names": names,
        "varied": varied,
        "runtime": str(folder),
        "largest_part_request_bytes": max(len(p.model_dump_json().encode()) for p in history.parts),
        "sessions": 1260,
        "source_parts": history.part_count,
        "required_return_cells": names * 1260,
        "http_history_bytes": len(encode(history).encode()),
        "original_source_bytes": sum(
            len(zlib.decompress(base64.b64decode(p.source_zlib_base64))) for p in history.parts
        ),
        "immutable_alignment_records": count,
        "alignment_record_bytes": size,
        "saved_input_run_bytes": len(encode(run).encode()),
        "worker_input_bytes": len(raw),
        "backup_bytes": len(backup_bytes),
        "http_and_input_diagnostics_complete": True,
        "cache_clear_reopen_originals_restore": True,
        "worker_reader": inspected,
        "wall_seconds": time.perf_counter() - started,
        "measurement_process_peak_bytes": peak_working_set(),
        "http_process_peak_bytes": http_peak,
        "worker_reader_peak_bytes": worker_peak,
        "scope": "Synthetic input boundary only; no fitting/search/investor-capacity qualification",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--names", type=int, choices=(20, 100, 500))
    parser.add_argument("--varied", action="store_true")
    args = parser.parse_args()
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cases": [
            measure(n, varied=args.varied) for n in ([args.names] if args.names else [20, 100, 500])
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, allow_nan=False))
