"""Isolated complete fictional history/storage/fitting/recovery workload worker.

Reports the first actual refused stage and whole-process Windows peak memory.
No limit change, truncation, provider acquisition or actual-universe claim.
"""

import argparse
import base64
import hashlib
import json
import platform
import time
import zlib
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from pydantic import ValidationError
from qualify_dcc import peak_working_set
from qualify_risk_profile import MANIFEST, source

from prosper import covariance, volatility
from prosper.advisory_records import encode
from prosper.advisory_recovery import MAX_BACKUP_BYTES, backup, restore
from prosper.advisory_store import AdvisoryStore
from prosper.api_contracts import HistoryPart, HistoryUpload
from prosper.history import HistoryBatch, HistoryRequest, Observation, Profile, SeriesContext
from prosper.history_refresh import align
from prosper.history_table import MAX_ROWS, SessionGrid
from prosper.history_table import observations as pack_observations
from prosper.risk_inputs import assemble
from prosper.source_blob import MAX_SOURCE_BYTES
from prosper.storage import MAX_BYTES, RuntimeBoundary
from prosper.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]


def request_for(names: int) -> HistoryRequest:
    start = date(2001, 1, 1)
    sessions = tuple((start + timedelta(days=t)).isoformat() for t in range(1260))
    predecessor = (start - timedelta(days=1)).isoformat()
    template = json.loads((ROOT / "examples/synthetic/history/current-request.json").read_bytes())[
        "request"
    ]["series"][0]
    contexts = tuple(
        SeriesContext.model_validate(
            {
                **template,
                "security_id": f"FICTIONAL-WORK-{j}",
                "provider_symbol": f"FICTIONAL-WORK-{j}",
                "mapping_start": predecessor,
                "mapping_end": sessions[-1],
                "vintage": "fictional-r1-v1",
                "calendar": "fictional-all-days",
                "coherence": "immutable-vintage",
                "coherence_evidence": "stipulated immutable fictional generation",
            }
        )
        for j in range(names)
    )
    return HistoryRequest(
        series=contexts,
        sessions=sessions,
        predecessor=predecessor,
        cutoff=sessions[-1],
        known_at=sessions[-1] + "T23:00:00Z",
        calendar_evidence="fictional all-day grid",
        overlap_sessions=1,
        profile=Profile(identity="R1", f="0.25", a3="0.17", kappa="10000"),
    )


def workload(names: int) -> dict[str, Any]:
    report: dict[str, Any] = {
        "names": names,
        "sessions": 1260,
        "coordinates": names * 1260,
        "scope": "service workload and separate HTTP size assessment; no actual investor inputs",
        "worker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fitting_completed": False,
        "stages": [],
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "host": platform.node(),
            "python": platform.python_version(),
        },
        "limits": {
            "history_original_source_bytes": MAX_BYTES,
            "general_source_bytes": MAX_SOURCE_BYTES,
            "record_bytes": 16 * 1024 * 1024,
            "backup_bytes": MAX_BACKUP_BYTES,
            "history_coordinates": MAX_ROWS,
        },
    }
    wall, cpu = time.perf_counter(), time.process_time()
    last_wall, last_cpu = wall, cpu
    stage = "request"

    def finish(label: str) -> None:
        nonlocal last_wall, last_cpu
        now, used = time.perf_counter(), time.process_time()
        report["stages"].append(
            {
                "stage": label,
                "wall_seconds": now - last_wall,
                "cpu_seconds": used - last_cpu,
                "process_peak_working_set_bytes": peak_working_set(),
            }
        )
        last_wall, last_cpu = now, used

    try:
        request = request_for(names)
        finish(stage)
        stage = "source_generation"
        manifest = json.loads(MANIFEST.read_bytes())
        manifest["security_ids"] = [s.security_id for s in request.series]
        context, rows = source(manifest)
        raw = json.dumps(
            {"context": asdict(context), "rows": [asdict(r) for r in rows]},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        digest = hashlib.sha256(raw).hexdigest()
        report["source_bytes"] = len(raw)
        finish(stage)
        stage = "batch"
        observations = []
        for sid in context.security_ids:
            observations.append(
                Observation.model_validate(
                    {
                        "security_id": sid,
                        "session": request.predecessor,
                        "source_ref": "fictional/predecessor",
                        **{
                            field: {"value": 100.0}
                            for field in ("open", "high", "low", "close", "adjusted_close")
                        },
                        "action": {"value": "none"},
                    }
                )
            )
        for row in rows:
            observations.append(
                Observation.model_validate(
                    {
                        "security_id": row.security_id,
                        "session": row.session,
                        "source_ref": f"fictional/{row.session}/{row.security_id}",
                        **{
                            field: {"value": float(getattr(row, field))}
                            for field in ("open", "high", "low", "close")
                        },
                        "adjusted_close": {"value": float(row.close)},
                        "action": {"value": "none"},
                    }
                )
            )
        batch = HistoryBatch(
            source_name="fictional workload source",
            source_sha256=digest,
            collected_at=request.known_at,
            validated_at=request.known_at,
            contexts=request.series,
            sessions=SessionGrid.pack((request.predecessor, *request.sessions)),
            validation_scope="full-window",
            rows=pack_observations(tuple(observations)),
        )
        report["batch_document_bytes"] = len(batch.model_dump_json().encode())
        finish(stage)
        stage = "upload_envelope"
        upload = HistoryUpload(
            part_count=1,
            parts=(
                HistoryPart(
                    batch=batch, source_zlib_base64=base64.b64encode(zlib.compress(raw)).decode()
                ),
            ),
            command_key="workload-history",
            expected_revision=0,
        )
        report["upload_envelope_bytes"] = len(encode(upload).encode())
        report["history_http_body_limit"] = 16 * 1024 * 1024
        report["http_envelope_accepted"] = (
            report["upload_envelope_bytes"] <= report["history_http_body_limit"]
        )
        report["application_fitting_completed"] = False
        finish(stage)
        with TemporaryDirectory(prefix="risk-workload-", dir=ROOT / ".local") as folder:
            origin = Workspace(AdvisoryStore(RuntimeBoundary(Path(folder) / "source")))
            stage = "history_store_import"
            imported = origin.import_history(upload)
            assert imported["outcome"] == "changed"
            finish(stage)
            stage = "alignment"
            aligned = align(request, origin.store.history_batches())
            assert aligned.complete and len(aligned.cells) == names * 1260
            report["aligned_record_bytes"] = len(encode(aligned).encode())
            innovation = assemble(aligned)
            assert innovation is not None and innovation.status == "ready"
            finish(stage)
            stage = "full_fit"
            inputs = tuple(
                volatility.series_from_innovations(
                    innovation, j, purpose="research-window", expected_observations=1260
                )
                for j in range(names)
            )
            fitted = covariance.fit_covariance(inputs, horizon=21)
            report["fit_status"] = fitted.status
            report["fit_issues"] = fitted.issues
            report["fitting_completed"] = fitted.projection is not None
            if fitted.projection is None:
                report.update(status="fit-unavailable", stage=stage)
                finish(stage)
                return report
            report["security_ids"] = fitted.security_ids
            report["forecast_identity"] = fitted.identity_sha256
            finish(stage)
            stage = "backup_restore"
            before = encode(aligned)
            saved = backup(origin.store)
            report["backup_bytes"] = len(saved)
            destination = AdvisoryStore(RuntimeBoundary(Path(folder) / "restored"))
            restore(destination, saved)
            assert destination.source_bytes(digest) == raw
            assert destination.history_batches() == origin.store.history_batches()
            # Neither restoring nor clearing reusable history mutates the saved
            # standalone frozen alignment/forecast object. No refit is performed.
            origin.store.clear_history_cache("clear", 1)
            assert encode(aligned) == before
            finish(stage)
        report.update(
            status="completed-service-http-unavailable"
            if not report["http_envelope_accepted"]
            else "completed-service-only",
            stage="http_envelope" if not report["http_envelope_accepted"] else "service_complete",
            recovery_without_refitting=True,
        )
    except ValidationError as exc:
        report.update(
            status="refused",
            stage=stage,
            reasons=[
                {"location": error["loc"], "code": error["type"]}
                for error in exc.errors(include_input=False, include_context=False)
            ],
        )
        finish(stage)
    except ValueError as exc:
        report.update(
            status="refused", stage=stage, reason=str(exc)[:1200], exception=type(exc).__name__
        )
        finish(stage)
    except AssertionError as exc:
        report.update(status="verification-failed", stage=stage, reason=str(exc))
        finish(stage)
    finally:
        report.update(
            wall_seconds=time.perf_counter() - wall,
            cpu_seconds=time.process_time() - cpu,
            process_peak_working_set_bytes=peak_working_set(),
            peak_scope="whole worker including source/serialization; not incremental allocation",
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", type=int, required=True)
    args = parser.parse_args()
    if not 2 <= args.names <= 5000:
        raise SystemExit("fictional workload requires 2..5000 explicit names")
    print(json.dumps(workload(args.names), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
