"""Current input ownership and real subprocess lifecycle; guards never fit a model."""

import json
import sqlite3
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from prosper import covariance, volatility
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import DATABASE_NAME, AdvisoryStore
from prosper.api_contracts import HistoryUpload, LotSettingsRequest, Upload
from prosper.benchmark import BenchmarkDiagnostic, BenchmarkImport, BenchmarkReview
from prosper.candidate_fit import compact
from prosper.candidate_jobs import lease
from prosper.candidate_workflow import (
    CandidateOutput,
    CandidateStart,
    FrozenCandidate,
    calculate,
    check_output_links,
    prepare,
)
from prosper.modeled_inputs import ModeledDiagnostic
from prosper.risk_inputs import assemble
from prosper.storage import PersistenceError, RuntimeBoundary
from prosper.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples/synthetic/candidates/application"
POPEN = subprocess.Popen


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_bytes())


def service(path: Path) -> Workspace:
    return Workspace(AdvisoryStore(RuntimeBoundary(path)))


def seed(w: Workspace) -> None:
    staged = w.stage(Upload.model_validate_json(json.dumps(load("holdings.json"))))
    w.store.select(staged.id, "holdings", 0)
    w.import_benchmark(BenchmarkImport.model_validate_json(json.dumps(load("benchmark.json"))))
    w.diagnose_benchmark(
        BenchmarkDiagnostic(
            run_id="benchmark",
            expected_revision=1,
            as_of="2026-10-25T23:00:00Z",
            review=BenchmarkReview.model_validate_json(json.dumps(load("benchmark-review.json"))),
        )
    )
    w.store.select_benchmark("benchmark", "benchmark-choice", 1)
    w.configure_lots(
        LotSettingsRequest.model_validate_json(
            json.dumps(
                dict(
                    settings=load("lot-settings.json"), command_key="settings", expected_revision=2
                )
            )
        )
    )
    w.import_history(HistoryUpload.model_validate_json(json.dumps(load("history.json"))))
    result = w.diagnose_inputs(
        ModeledDiagnostic.model_validate_json(
            json.dumps(
                dict(
                    **load("modeled.json"),
                    run_id="inputs",
                    expected_revision=4,
                    as_of="2026-10-25T23:00:00Z",
                )
            )
        )
    )
    assert result.outputs["software_inputs_complete"], result.outputs["issues"]


def command(**changes: Any) -> CandidateStart:
    d = load("command.json")
    d.update(changes)
    return CandidateStart.model_validate_json(json.dumps(d))


def wait(w: Workspace) -> Any:
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        r = w.store.run("candidate")
        if r.status != "running":
            return r
        time.sleep(0.05)
    raise AssertionError("worker did not terminate")


def stub(monkeypatch: pytest.MonkeyPatch, mode: str = "complete") -> list[int]:
    original = POPEN
    calls: list[int] = []

    def popen(args: Any, **kwargs: Any) -> POPEN[bytes]:
        calls.append(1)
        action = (
            "import time;time.sleep(10)"
            if mode == "sleep"
            else "print('malformed',flush=True)"
            if mode == "invalid"
            else "print(json.dumps(dict(kind='candidate-workflow-v1',outcome='unavailable',"
            "issues=['stub-no-fit'],risk=None,search=None)),flush=True)"
        )
        if mode == "checked":
            action = (
                "from pathlib import Path;print(json.dumps(json.loads(Path("
                + repr(str(FIXTURES / "checked-output.json"))
                + ").read_bytes())),flush=True)"
            )
        code = (
            "import sys,json;sys.stdin.buffer.read();"
            "print(json.dumps(dict(phase='fitting',states=0)),flush=True);" + action
        )
        return original([sys.executable, "-c", code], **kwargs)

    monkeypatch.setattr("prosper.candidate_jobs.subprocess.Popen", popen)
    return calls


def test_compact_payload_and_frozen_guard_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (FIXTURES / "history.json").stat().st_size < 2 * 1024 * 1024
    w = service(tmp_path / "runtime")
    seed(w)
    stub(monkeypatch)
    try:
        w.start_candidate(command())
        r = wait(w)
        frozen = w.store.candidate_inputs(r.inputs["candidate_inputs"])
        request, issues = prepare(frozen)
        assert request and not issues
        assert len(frozen.modeled.alignment.cells) == 2520  # type: ignore[union-attr]
        assert request.limits.tracking_error == "1" and request.limits.max_orders == 3
        assert request.risk.as_of == "2026-10-23"
        assert request.settings.cash_to_invest == "0"
    finally:
        w.candidates.close()


def test_failed_fit_context_is_bound_to_saved_original_inputs_without_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    stub(monkeypatch)
    try:
        w.start_candidate(command())
        run = wait(w)
        frozen = w.store.candidate_inputs(run.inputs["candidate_inputs"])
        assert frozen.modeled.alignment is not None
        innovation = assemble(frozen.modeled.alignment)
        assert innovation is not None
        # A deliberately failed component fixture; no optimizer is run here.
        data = volatility.series_from_innovations(
            innovation,
            0,
            purpose="research-window",
            expected_observations=1260,
        )
        scalar = volatility.VolatilityResult(
            status="unavailable",
            issues=("no_eligible_start",),
            version=volatility.VERSION,
            data=data,
            horizon=21,
            configuration_sha256="a" * 64,
            input_sha256="b" * 64,
            starts=(),
            selected_start=None,
            path=None,
            forecast=(),
            objective_range=None,
            parameter_ranges=(),
            output_sha256="c" * 64,
            identity_sha256="d" * 64,
        )
        fit = covariance.compose_covariance(
            tuple(
                replace(scalar, data=replace(data, security_id=sid))
                for sid in frozen.coverage.security_ids
            ),
            None,
        )
        risk = compact(fit)
        output = CandidateOutput(outcome="unavailable", issues=fit.issues, risk=risk, search=None)
        check_output_links(frozen, output)
        for changes in (
            {"cutoff": "2026-10-22"},
            {"security_ids": tuple(reversed(risk.security_ids))},
            {"sessions": 1259},
            {"horizon": 1},
            {"calendar": "another-calendar"},
            {"timezone": "another-timezone"},
            {"variant": "returns-only"},
            {"source_units": "percent-experiment"},
            {"purpose": "primitive"},
        ):
            with pytest.raises(ValueError, match="candidate_output_links_invalid"):
                check_output_links(
                    frozen,
                    output.model_copy(
                        update={
                            "risk": risk.model_copy(update=changes),
                        }
                    ),
                )
        monkeypatch.setattr(covariance, "fit_covariance", lambda *a, **k: pytest.fail("refit"))
        # Install a failed-result recovery fixture in this fresh synthetic test DB.
        saved = run.model_copy(update={"outputs": output.model_dump(mode="json")})
        with w.store._connection(write=True) as connection:
            connection.execute(
                "UPDATE runs SET document=? WHERE id=?",
                (
                    saved.model_dump_json(),
                    saved.id,
                ),
            )
        target = service(tmp_path / "restored")
        restore(target.store, backup(w.store))
        assert target.store.run(saved.id) == saved
        assert CandidateOutput.model_validate_json(output.model_dump_json()) == output
    finally:
        w.candidates.close()


def test_identical_retry_changed_payload_and_reopen_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    calls = stub(monkeypatch)
    try:
        w.start_candidate(command())
        r = wait(w)
        assert w.start_candidate(command()) == r and len(calls) == 1
        with pytest.raises(PersistenceError, match="analysis_id_reused"):
            w.start_candidate(command(as_of="2026-10-25T23:01:00Z"))
        w.store.clear_history_cache("clear", 4)
        target = service(tmp_path / "restored")
        restore(target.store, backup(w.store))
        assert target.start_candidate(command()) == r
        assert target.store.run(r.id) == r and len(calls) == 1
    finally:
        w.candidates.close()


@pytest.mark.parametrize("reason", ["cancelled", "timeout", "stale", "interrupted"])
def test_worker_stop_or_isolation_and_no_current_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    stub(monkeypatch, "sleep")
    controls = load("command.json")["controls"]
    if reason == "timeout":
        controls["timeout_seconds"] = 1
    w.start_candidate(command(controls=controls))
    if reason == "cancelled":
        w.candidates.cancel("candidate")
        w.candidates.cancel("candidate")
    elif reason == "stale":
        w.store.configure({"changed": True}, "new-window", 4)
    elif reason == "interrupted":
        w.candidates.close()
    r = wait(w)
    assert r.status == "failed" and r.outputs["outcome"] == reason
    assert w.store.current()["current_run_id"] != "candidate"
    assert w.start_candidate(command(controls=controls)) == r
    w.candidates.close()


def test_one_worker_across_two_controllers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    calls = stub(monkeypatch, "sleep")
    other = service(tmp_path / "runtime")
    try:
        w.start_candidate(command())
        assert other.start_candidate(command()).status == "running"
        with pytest.raises(PersistenceError, match="candidate_worker_busy"):
            other.start_candidate(command(run_id="other"))
        other.candidates.cancel("candidate")
        assert wait(w).outputs["outcome"] == "cancelled" and len(calls) == 1
    finally:
        w.candidates.close()
        other.candidates.close()


def test_malformed_worker_and_guarded_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    stub(monkeypatch, "invalid")
    w.start_candidate(command())
    r = wait(w)
    assert r.status == "failed" and r.outputs["outcome"] == "failed"
    w.candidates.close()
    path = w.store.runtime.path("candidate-worker.lock")
    path.write_bytes(b"owner-file-must-not-be-overwritten")
    with pytest.raises(PersistenceError, match="candidate_lease_unsafe"):
        lease(w.store)
    assert path.read_bytes() == b"owner-file-must-not-be-overwritten"


def test_running_backup_resume_uses_original_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    stub(monkeypatch, "sleep")
    w.start_candidate(command())
    saved = backup(w.store)
    w.candidates.cancel("candidate")
    wait(w)
    w.candidates.close()
    stub(monkeypatch, "complete")
    target = service(tmp_path / "restored")
    restore(target.store, saved)
    target.start_candidate(command())
    r = wait(target)
    assert r.outputs["outcome"] == "unavailable"
    assert r.inputs == w.store.run("candidate").inputs
    target.candidates.close()


def test_missing_or_corrupt_candidate_sources_refuse_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    stub(monkeypatch)
    w.start_candidate(command())
    wait(w)
    w.candidates.close()
    with sqlite3.connect(w.store.runtime.path(DATABASE_NAME)) as c:
        c.execute("DELETE FROM run_sources WHERE run_id='candidate'")
    with pytest.raises(PersistenceError, match="required_run_sources_missing"):
        backup(w.store)


def test_profile_and_full_union_refuse_before_fitting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    stub(monkeypatch)
    w.start_candidate(command())
    r = wait(w)
    w.candidates.close()
    raw = w.store.candidate_inputs(r.inputs["candidate_inputs"]).model_dump(mode="json")
    raw["modeled"]["bundle"]["profile"]["lookback_sessions"] = 3

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("guard attempted a fit")

    monkeypatch.setattr("prosper.candidate_workflow.covariance.fit_covariance", forbidden)
    output = calculate(FrozenCandidate.model_validate_json(json.dumps(raw)))
    assert output.outcome == "unavailable" and any("lookback_sessions" in v for v in output.issues)


def test_running_progress_corruption_refuses_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    stub(monkeypatch, "sleep")
    w.start_candidate(command())
    saved = backup(w.store)
    w.candidates.cancel("candidate")
    wait(w)
    w.candidates.close()
    target = service(tmp_path / "restored")
    restore(target.store, saved)
    with sqlite3.connect(target.store.runtime.path(DATABASE_NAME)) as c:
        d = json.loads(c.execute("SELECT document FROM runs WHERE id='candidate'").fetchone()[0])
        d["outputs"]["phase"] = "invented"
        c.execute("UPDATE runs SET document=? WHERE id='candidate'", (json.dumps(d),))
    with pytest.raises((PersistenceError, ValueError)):
        backup(target.store)


def test_restored_running_run_can_cancel_without_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = service(tmp_path / "runtime")
    seed(w)
    stub(monkeypatch, "sleep")
    w.start_candidate(command())
    saved = backup(w.store)
    w.candidates.cancel("candidate")
    wait(w)
    w.candidates.close()
    target = service(tmp_path / "restored")
    restore(target.store, saved)
    result = target.candidates.cancel("candidate")
    assert result.status == "failed" and result.outputs["outcome"] == "cancelled"
