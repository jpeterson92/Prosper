"""One process-isolated candidate per workspace, durable cancellation and retries."""

import json
import os
import stat
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from typing import BinaryIO

from pydantic import JsonValue

from prosper.advisory_records import AnalysisRun, encode
from prosper.advisory_store import AdvisoryStore
from prosper.candidate_workflow import (
    MODEL,
    CandidateOutput,
    CandidateStart,
    FrozenCandidate,
    check_output_links,
)
from prosper.storage import PersistenceError
from prosper.worker_packet import MAX_MESSAGE, encode_input


def lease(store: AdvisoryStore) -> BinaryIO:
    """OS lease releases on process death; source/DB bytes never live in this file."""
    path = store.runtime.path("candidate-worker.lock")
    try:
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        handle = os.fdopen(descriptor, "r+b", buffering=0)
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1:
            handle.close()
            raise PersistenceError("candidate_lease_unsafe")
        if info.st_size == 0:
            handle.write(b"0")
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import importlib

            module = importlib.import_module("fcntl")
            module.flock(handle, module.LOCK_EX | module.LOCK_NB)
        return handle
    except OSError:
        if "handle" in locals():
            handle.close()
        raise PersistenceError("candidate_worker_busy") from None


def progress(store: AdvisoryStore, identity: str, claim: str, phase: str, states: int) -> None:
    with store._connection(write=True) as connection:
        run = store._run(connection, identity)
        if run.status != "running" or run.outputs.get("claim") not in (None, claim):
            return
        output: dict[str, JsonValue] = {
            "kind": "candidate-progress-v1",
            "claim": claim,
            "phase": phase,
            "states": states,
            "cancel_requested": run.outputs.get("cancel_requested") is True,
        }
        connection.execute(
            "UPDATE runs SET document=? WHERE id=?",
            (encode(run.model_copy(update={"outputs": output})), identity),
        )


class CandidateJobs:
    def __init__(self, store: AdvisoryStore) -> None:
        self.store = store
        self.guard = threading.Lock()
        self.closed = threading.Event()
        self.threads: list[threading.Thread] = []

    def start(self, command: CandidateStart, freeze: Callable[[], FrozenCandidate]) -> AnalysisRun:
        with self.guard:
            try:
                run = self.store.run(command.run_id)
            except PersistenceError as error:
                if error.code != "analysis_missing":
                    raise
                run = None
            if run is not None:
                if run.model_version != MODEL or run.inputs.get(
                    "candidate_command"
                ) != command.model_dump(mode="json"):
                    raise PersistenceError("analysis_id_reused")
                if run.status != "running":
                    return run
            try:
                handle = lease(self.store)
            except PersistenceError as error:
                if run is not None and error.code == "candidate_worker_busy":
                    return run
                raise
            try:
                if run is None:
                    frozen = freeze()
                    run = self.store.start_run(
                        command.run_id,
                        command.expected_revision,
                        inputs={
                            "candidate_command": command.model_dump(mode="json"),
                            "candidate_inputs": {
                                **frozen.model_dump(mode="json", exclude={"modeled", "coverage"}),
                                "modeled_input_run_id": command.input_run_id,
                            },
                        },
                        application_version="prosper-advisory-v1",
                        model_version=MODEL,
                        as_of=command.as_of,
                        source_ids=frozen.required_sources,
                    )
                else:
                    frozen = self.store.candidate_inputs(run.inputs["candidate_inputs"])
                claim = uuid.uuid4().hex
                # Holding the OS lease permits resuming an interrupted saved run.
                with self.store._connection(write=True) as connection:
                    run = self.store._run(connection, command.run_id)
                    outputs: dict[str, JsonValue] = {
                        "kind": "candidate-progress-v1",
                        "claim": claim,
                        "phase": "starting",
                        "states": 0,
                        "cancel_requested": run.outputs.get("cancel_requested") is True,
                    }
                    connection.execute(
                        "UPDATE runs SET document=? WHERE id=?",
                        (encode(run.model_copy(update={"outputs": outputs})), run.id),
                    )
                worker = threading.Thread(
                    target=self._run, args=(frozen, claim, handle), daemon=True
                )
                self.threads.append(worker)
                worker.start()
                return self.store.run(command.run_id)
            except BaseException:
                handle.close()
                raise

    def cancel(self, identity: str) -> AnalysisRun:
        with self.store._connection(write=True) as connection:
            run = self.store._run(connection, identity)
            if run.model_version != MODEL:
                raise PersistenceError("candidate_run_required")
            if run.status == "running":
                outputs = {**run.outputs, "cancel_requested": True}
                connection.execute(
                    "UPDATE runs SET document=? WHERE id=?",
                    (encode(run.model_copy(update={"outputs": outputs})), identity),
                )
        if run.status == "running":
            # A restored/interrupted run may have no supervising process. If its
            # OS lease is free, cancellation must still reach a terminal state.
            try:
                handle = lease(self.store)
            except PersistenceError as error:
                if error.code != "candidate_worker_busy":
                    raise
            else:
                try:
                    result = CandidateOutput(
                        outcome="cancelled", issues=("cancelled",), risk=None, search=None
                    )
                    self.store.complete_run(
                        identity,
                        outputs=result.model_dump(mode="json"),
                        status="failed",
                        warnings=result.warnings,
                        candidate_claim=str(run.outputs.get("claim")),
                    )
                finally:
                    handle.close()
        return self.store.run(identity)

    def close(self) -> None:
        self.closed.set()
        for thread in self.threads:
            thread.join(timeout=2)

    def _run(self, frozen: FrozenCandidate, claim: str, handle: BinaryIO) -> None:
        identity = frozen.command.run_id
        process = None
        finished = threading.Event()
        stop: list[str] = []
        result = CandidateOutput(
            outcome="failed", issues=("worker_failed",), risk=None, search=None
        )
        try:
            raw = encode_input(frozen)
            process = subprocess.Popen(
                [sys.executable, "-I", "-m", "prosper.candidate_worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            child = process
            deadline = time.monotonic() + frozen.command.controls.timeout_seconds

            def monitor() -> None:
                while not finished.wait(0.1):
                    try:
                        saved = self.store.run(identity)
                        state = self.store.current()
                        reason = (
                            "cancelled"
                            if saved.outputs.get("cancel_requested") is True
                            else "stale"
                            if state["revision"] != saved.input_revision
                            else "interrupted"
                            if self.closed.is_set()
                            else "timeout"
                            if time.monotonic() >= deadline
                            else None
                        )
                    except Exception:
                        reason = "interrupted"
                    if reason:
                        stop.append(reason)
                        if child.poll() is None:
                            try:
                                child.kill()
                            except OSError:
                                pass
                        return

            watcher = threading.Thread(target=monitor, daemon=True)
            watcher.start()
            assert process.stdin is not None and process.stdout is not None
            process.stdin.write(raw)
            process.stdin.close()
            total = 0
            stream = process.stdout
            for line in iter(lambda: stream.readline(MAX_MESSAGE + 1), b""):
                total += len(line)
                if total > 2 * MAX_MESSAGE or len(line) > MAX_MESSAGE:
                    raise ValueError("worker_output_size_limit")
                document = json.loads(line)
                if document.get("kind") == MODEL:
                    result = CandidateOutput.model_validate_json(line)
                    check_output_links(frozen, result)
                elif document.get("phase") in ("fitting", "searching"):
                    states = document.get("states")
                    if type(states) is not int or not 0 <= states <= 100000:
                        raise ValueError("invalid_worker_progress")
                    progress(self.store, identity, claim, document["phase"], states)
                else:
                    raise ValueError("invalid_worker_output")
            code = process.wait(timeout=2)
            if code != 0 and not stop:
                result = CandidateOutput(
                    outcome="failed", issues=("worker_exited",), risk=None, search=None
                )
        except Exception:
            result = CandidateOutput(
                outcome="failed", issues=("worker_failed",), risk=None, search=None
            )
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=2)
                if process.stdout is not None:
                    process.stdout.close()
                if process.stdin is not None:
                    process.stdin.close()
            finished.set()
            if stop:
                result = CandidateOutput.model_validate(
                    dict(outcome=stop[0], issues=(stop[0],), risk=None, search=None)
                )
            try:
                self.store.complete_run(
                    identity,
                    outputs=result.model_dump(mode="json"),
                    status="partial" if result.outcome in ("checked", "unavailable") else "failed",
                    warnings=result.warnings,
                    exclusions=tuple(
                        f for f in frozen.coverage.exclusions if f.code == "history_excluded"
                    ),
                    candidate_claim=claim,
                )
            finally:
                handle.close()
