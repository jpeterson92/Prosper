"""Isolated bounded compute process. Receives frozen inputs, never opens a workspace."""

import json
import os
import sys
from threading import Timer

from prosper.candidate_workflow import CandidateOutput, calculate
from prosper.worker_packet import MAX_MESSAGE, decode_input


def main() -> None:
    raw = sys.stdin.buffer.read(MAX_MESSAGE + 1)
    if len(raw) > MAX_MESSAGE:
        raise SystemExit(2)
    frozen = decode_input(raw)
    if sys.argv[1:] == ["--inspect-input"]:
        print(
            json.dumps(
                {
                    "names": len(frozen.coverage.security_ids),
                    "return_cells": frozen.modeled.alignment.rows.row_count
                    if frozen.modeled.alignment
                    else 0,
                    "fitting_attempted": False,
                }
            )
        )
        return
    if sys.argv[1:]:
        raise SystemExit(2)
    # Survives loss of the owning HTTP process: no orphan may run indefinitely.
    timer = Timer(frozen.command.controls.timeout_seconds + 2, lambda: os._exit(3))
    timer.daemon = True
    timer.start()

    def emit(phase: str, states: int) -> None:
        print(json.dumps({"phase": phase, "states": states}), flush=True)

    try:
        emit("fitting", 0)
        result = calculate(frozen, emit)
    except Exception:
        result = CandidateOutput(
            outcome="failed", issues=("worker_calculation_failed",), risk=None, search=None
        )
    document = result.model_dump_json()
    if len(document.encode()) > MAX_MESSAGE:
        document = CandidateOutput(
            outcome="failed", issues=("worker_result_size_limit",), risk=None, search=None
        ).model_dump_json()
    print(document, flush=True)
    timer.cancel()


if __name__ == "__main__":
    main()
