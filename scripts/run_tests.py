"""Affected/selected development tests and explicit full checkpoint verification."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIRECTORY = Path(__file__).resolve().parent
GLOBAL_FILES = {
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    "scripts/dev.ps1",
    "scripts/run_tests.py",
    "scripts/pytest_workflow.py",
}


class WorkflowError(Exception):
    """A safe checkpoint or explicit selection is required."""


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root: Path) -> dict[str, Any]:
    sources: dict[str, str] = {}
    inputs = {name: hash_file(root / name) for name in GLOBAL_FILES if (root / name).is_file()}
    for directory in ("src", "tests", "scripts", "examples"):
        for path in sorted((root / directory).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if path.suffix == ".md":
                continue
            name = path.relative_to(root).as_posix()
            if path.suffix == ".py":
                sources[name] = hash_file(path)
                if path.name == "conftest.py":
                    inputs[name] = sources[name]
            else:
                inputs[name] = hash_file(path)
    return {
        "global_inputs": inputs,
        "sources": sources,
        "environment": {
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "distributions": sorted(
                [d.metadata["Name"], d.version] for d in metadata.distributions()
            ),
        },
    }


def selected_paths(root: Path, tests: list[str]) -> list[str]:
    result = []
    for test in tests:
        filename = test.split("::", 1)[0]
        path = (root / filename).resolve()
        if not path.is_relative_to(root / "tests") or path.suffix != ".py" or not path.is_file():
            raise WorkflowError(f"Test selection must name a Python file under tests/: {test}")
        result.append(test)
    return result


def child_process_tests(root: Path) -> list[str]:
    # Explicit conservative supplement for code invisible to in-process coverage.
    return [
        path.relative_to(root).as_posix()
        for path in sorted((root / "tests").rglob("test_*.py"))
        if any(
            token in path.read_text(encoding="utf-8")
            for token in ("subprocess", "Popen", "multiprocessing", "os.system", "os.spawn")
        )
    ]


def read_baseline(state: Path, current: dict[str, Any]) -> dict[str, Any]:
    try:
        baseline = json.loads((state / "baseline.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkflowError(
            "Affected selection has no valid full baseline. Use explicit -TestPath "
            "now; the next authorized check/checkpoint creates the baseline."
        ) from exc
    if (
        not isinstance(baseline, dict)
        or baseline.get("schema") != 1
        or not (state / "testmon.sqlite").is_file()
    ):
        raise WorkflowError(
            "Missing testmon database or incompatible baseline; use explicit "
            "-TestPath until the next check/checkpoint."
        )
    if (
        baseline.get("global_inputs") != current["global_inputs"]
        or baseline.get("environment") != current["environment"]
    ):
        raise WorkflowError(
            "Data/configuration/fixture/environment inputs changed. Full "
            "qualification is deferred to check/checkpoint; use explicit -TestPath now."
        )
    failure_path = state / "failed.json"
    if failure_path.exists():
        try:
            failure = json.loads(failure_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise WorkflowError(
                "Invalid failure state; use explicit tests until a checkpoint."
            ) from exc
        if failure.get("inputs_unchanged") is not True:
            raise WorkflowError(
                "Interrupted/mutated input state needs a fresh full checkpoint; "
                "explicit -TestPath remains available."
            )
    return cast(dict[str, Any], baseline)


def run_phase(
    root: Path,
    state: Path,
    output: Path,
    *,
    mode: str,
    workers: int | str,
    tests: list[str],
    last_failed: bool = False,
    exclude: Path | None = None,
) -> tuple[int, Path]:
    output.mkdir()
    report = output / "pytest.json"
    cache = output / "pytest-cache"
    cache_values = cache / "v/cache"
    cache_values.mkdir(parents=True)
    failures_path = state / "lastfailed.json"
    failures = (
        json.loads(failures_path.read_text(encoding="utf-8")) if failures_path.exists() else {}
    )
    (cache_values / "lastfailed").write_text(json.dumps(failures), encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "pytest_workflow",
        "-q",
        "--durations=20",
        "--durations-min=0.1",
        "--junitxml",
        str(output / "junit.xml"),
        "--workflow-json",
        str(report),
        "--basetemp",
        str(output / "tmp"),
        "-o",
        f"cache_dir={cache}",
        "-n",
        str(workers),
        "--dist",
        "worksteal",
        "--max-worker-restart=0",
    ]
    if mode == "full":
        command += ["--testmon", "--testmon-noselect"]
    elif mode == "affected":
        command += ["--testmon"]
    else:
        command += ["--no-testmon"]
    if last_failed:
        command += ["--last-failed", "--last-failed-no-failures=none"]
    if exclude:
        command += ["--workflow-exclude-json", str(exclude)]
    command += tests
    env = os.environ.copy()
    env.update(
        {
            "TESTMON_DATAFILE": str(state / "testmon.sqlite"),
            "PYTHONPATH": str(PLUGIN_DIRECTORY)
            + os.pathsep
            + str(root)
            + os.pathsep
            + env.get("PYTHONPATH", ""),
            "PYTHONIOENCODING": "utf-8",
            # Nested pytest processes get separate scratch; no worker flags are inherited.
            "PYTEST_ADDOPTS": f'-o cache_dir="{output / "nested-cache"}"',
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    started = time.perf_counter()
    with (output / "stdout.log").open("w", encoding="utf-8") as log:
        with subprocess.Popen(
            command,
            cwd=root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as process:
            assert process.stdout is not None
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
            code = process.wait()
    (output / "command.json").write_text(
        json.dumps(
            {
                "argv": command,
                "exitcode": code,
                "seconds": time.perf_counter() - started,
                "workers": workers,
                "thread_limits": {
                    name: env[name]
                    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if report.exists():
        recorded = json.loads(report.read_text(encoding="utf-8"))
        for nodeid in recorded["executed"]:
            failures.pop(nodeid, None)
        for item in recorded["reports"]:
            if item["outcome"] == "failed":
                failures[item["nodeid"]] = True
        temporary = state / "lastfailed.json.tmp"
        temporary.write_text(json.dumps(failures), encoding="utf-8")
        temporary.replace(failures_path)
    return code, report


def run(
    root: Path,
    *,
    mode: str,
    workers: int | str,
    tests: list[str],
    last_failed: bool = False,
    force: bool = False,
) -> int:
    root = root.resolve()
    if mode not in ("affected", "selected", "full") or not (
        workers == "auto" or str(workers).isdigit() and 0 <= int(workers) <= 256
    ):
        raise WorkflowError("Invalid mode/worker count")
    if mode == "selected" and not tests:
        raise WorkflowError("Selected mode requires explicit test paths")
    if mode != "selected" and (tests or last_failed):
        raise WorkflowError("Explicit paths/last-failed require selected mode")
    if force and mode != "full":
        raise WorkflowError("Force is restricted to full checkpoints")
    paths = selected_paths(root, tests)
    state = root / ".local/test-workflow/state"
    state.mkdir(parents=True, exist_ok=True)
    try:
        lock = (state / "active.lock").open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise WorkflowError(
            "Another workflow owns active.lock. Inspect an interrupted run before "
            "removing its stale lock; do not run against the same database concurrently."
        ) from exc
    with lock:
        lock.write(str(os.getpid()))
        lock.flush()
        try:
            return run_locked(
                root,
                state,
                mode=mode,
                workers=workers,
                tests=paths,
                last_failed=last_failed,
                force=force,
            )
        finally:
            lock.close()
            (state / "active.lock").unlink()


def run_locked(
    root: Path,
    state: Path,
    *,
    mode: str,
    workers: int | str,
    tests: list[str],
    last_failed: bool,
    force: bool,
) -> int:
    before = snapshot(root)
    before["execution"] = {"workers": str(workers), "distribution": "worksteal", "blas_threads": 1}
    input_hash = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
    if mode == "full" and not force and not (state / "failed.json").exists():
        try:
            previous = read_baseline(state, before)
            receipt = Path(previous["last_full_run"]) / "summary.json"
            if not receipt.resolve().is_relative_to(state.parent / "runs"):
                raise WorkflowError("Invalid full-run receipt path")
            value = json.loads(receipt.read_text(encoding="utf-8"))
            if (
                previous.get("full_input_sha256") == input_hash
                and value.get("passed") is True
                and value.get("full_suite") is True
                and value.get("input_sha256") == input_hash
            ):
                print(f"Reusing unchanged passing full-suite result: {receipt}", flush=True)
                return 0
        except (WorkflowError, OSError, ValueError, KeyError):
            pass
    baseline = read_baseline(state, before) if mode == "affected" else None
    output = (
        state.parent
        / "runs"
        / (datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8])
    )
    output.mkdir(parents=True)
    print(f"Test workflow: {mode}; {workers} workers (0=serial); reports: {output}", flush=True)
    code, first_report = run_phase(
        root,
        state,
        output / "primary",
        mode=mode,
        workers=workers,
        tests=tests,
        last_failed=last_failed,
    )
    # Exit 5 is legitimate only when a restricted/affected selection has no tests.
    okay = code == 0 or (code == 5 and (mode == "affected" or last_failed))
    phases = [str(first_report)]
    if okay and baseline is not None and baseline.get("sources") != before["sources"]:
        supplemental = child_process_tests(root)
        if supplemental:
            print(
                "Checking child-process cases; already executed node IDs are excluded.", flush=True
            )
            extra, report = run_phase(
                root,
                state,
                output / "child-process",
                mode="selected",
                workers=workers,
                tests=supplemental,
                exclude=first_report,
            )
            phases.append(str(report))
            okay = extra in (0, 5)
            if not okay:
                code = extra
    after = snapshot(root)
    after["execution"] = before["execution"]
    unchanged = after == before
    if okay and not unchanged:
        okay, code = False, 3
        print("Inputs changed during verification; result cannot advance the baseline.", flush=True)
    if okay and mode in ("full", "affected"):
        value = {
            "schema": 1,
            **before,
            "last_run": str(output),
            "last_full_run": str(output)
            if mode == "full"
            else baseline["last_full_run"]
            if baseline
            else "",
            "full_input_sha256": input_hash
            if mode == "full"
            else baseline.get("full_input_sha256")
            if baseline
            else None,
        }
        temporary = state / "baseline.json.tmp"
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
        temporary.replace(state / "baseline.json")
    summary = {
        "mode": mode,
        "workers": workers,
        "passed": okay,
        "phases": phases,
        "inputs_unchanged": unchanged,
        "full_suite": mode == "full",
        "input_sha256": input_hash,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    if not okay:
        (state / "failed.json").write_text(json.dumps(summary), encoding="utf-8")
    elif mode == "full":
        (state / "failed.json").unlink(missing_ok=True)
    print(f"{'Passed' if okay else 'Failed'}: {output / 'summary.json'}", flush=True)
    return 0 if okay else code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("affected", "selected", "full"), required=True)
    parser.add_argument("--workers", default="auto")
    parser.add_argument("--last-failed", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("tests", nargs="*")
    args = parser.parse_args()
    try:
        return run(
            ROOT,
            mode=args.mode,
            workers=args.workers,
            tests=args.tests,
            last_failed=args.last_failed,
            force=args.force,
        )
    except WorkflowError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
