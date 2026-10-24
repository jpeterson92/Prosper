"""Developer-runner qualification on tiny fictional projects; never the full Prosper suite."""

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_tests.py"
SPEC = importlib.util.spec_from_file_location("run_tests", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER: Any = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def project(root: Path) -> None:
    (root / "tests").mkdir()
    (root / "src").mkdir()
    (root / "examples").mkdir()
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths=["tests"]\n', encoding="utf-8"
    )
    (root / "src/calc.py").write_text("def value():\n    return 2\n", encoding="utf-8")
    (root / "src/other.py").write_text("def value():\n    return 9\n", encoding="utf-8")
    (root / "tests/test_calc.py").write_text(
        "from src.calc import value\ndef test_calc():\n    assert value() > 0\n", encoding="utf-8"
    )
    (root / "tests/test_other.py").write_text(
        "from src.other import value\ndef test_other():\n    assert value() == 9\n",
        encoding="utf-8",
    )
    (root / "tests/test_child.py").write_text(
        "import subprocess, sys\ndef test_child():\n"
        "    code = 'from src.calc import value; assert value() > 0'\n"
        "    r = subprocess.run([sys.executable, '-c', code])\n"
        "    assert r.returncode == 0\n",
        encoding="utf-8",
    )


def reports(root: Path) -> list[dict[str, Any]]:
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(
            (root / ".local/test-workflow/runs").glob("*/summary.json"),
            key=lambda p: p.stat().st_mtime_ns,
        )
    ]


def last_executed(root: Path) -> set[str]:
    latest = reports(root)[-1]
    return {
        node
        for phase in latest["phases"]
        for node in json.loads(Path(phase).read_text(encoding="utf-8"))["executed"]
    }


def test_cold_selection_never_starts_full_suite(tmp_path: Path) -> None:
    project(tmp_path)
    with pytest.raises(RUNNER.WorkflowError, match="no valid full baseline"):
        RUNNER.run(tmp_path, mode="affected", workers=0, tests=[])
    assert not list((tmp_path / ".local/test-workflow/runs").glob("*"))
    assert not (tmp_path / ".local/test-workflow/state/active.lock").exists()


def test_testmon_parallel_selection_and_hidden_child_dependency(tmp_path: Path) -> None:
    project(tmp_path)
    assert RUNNER.run(tmp_path, mode="full", workers=2, tests=[]) == 0
    assert len(last_executed(tmp_path)) == 3
    assert RUNNER.run(tmp_path, mode="full", workers=2, tests=[]) == 0
    assert len(reports(tmp_path)) == 1
    assert RUNNER.run(tmp_path, mode="full", workers=2, tests=[], force=True) == 0
    assert len(reports(tmp_path)) == 2
    (tmp_path / "src/calc.py").write_text("def value():\n    return 300\n", encoding="utf-8")
    assert RUNNER.run(tmp_path, mode="affected", workers=2, tests=[]) == 0
    assert last_executed(tmp_path) == {
        "tests/test_calc.py::test_calc",
        "tests/test_child.py::test_child",
    }
    phases = reports(tmp_path)[-1]["phases"]
    executed = [
        node for phase in phases for node in json.loads(Path(phase).read_text())["executed"]
    ]
    assert len(executed) == len(set(executed))
    assert RUNNER.run(tmp_path, mode="affected", workers=0, tests=[]) == 0
    assert last_executed(tmp_path) == set()
    (tmp_path / "examples/README.md").write_text("Fictional documentation\n", encoding="utf-8")
    assert RUNNER.run(tmp_path, mode="affected", workers=0, tests=[]) == 0
    assert last_executed(tmp_path) == set()
    (tmp_path / "examples/data.csv").write_text("fictional,value\nFTEST,1\n", encoding="utf-8")
    with pytest.raises(RUNNER.WorkflowError, match="inputs changed"):
        RUNNER.run(tmp_path, mode="affected", workers=0, tests=[])


def test_selected_failure_last_failed_and_baseline_preservation(tmp_path: Path) -> None:
    project(tmp_path)
    failure = tmp_path / "tests/test_calc.py"
    failure.write_text("def test_calc():\n    assert False\n", encoding="utf-8")
    assert RUNNER.run(tmp_path, mode="selected", workers=0, tests=["tests/test_calc.py"]) == 1
    assert not (tmp_path / ".local/test-workflow/state/baseline.json").exists()
    failure.write_text("def test_calc():\n    assert True\n", encoding="utf-8")
    assert (
        RUNNER.run(
            tmp_path, mode="selected", workers=0, tests=["tests/test_calc.py"], last_failed=True
        )
        == 0
    )
    assert last_executed(tmp_path) == {"tests/test_calc.py::test_calc"}
    assert (
        RUNNER.run(
            tmp_path, mode="selected", workers=0, tests=["tests/test_calc.py"], last_failed=True
        )
        == 0
    )
    assert last_executed(tmp_path) == set()


@pytest.mark.parametrize("kind", ["environment", "missing-db", "corrupt-baseline", "active-lock"])
def test_stale_or_concurrent_state_is_refused(tmp_path: Path, kind: str) -> None:
    project(tmp_path)
    state = tmp_path / ".local/test-workflow/state"
    state.mkdir(parents=True)
    before = RUNNER.snapshot(tmp_path)
    baseline = {"schema": 1, **before, "last_full_run": "fictional"}
    (state / "testmon.sqlite").touch()
    if kind == "environment":
        baseline["environment"] = {"python": "unqualified"}
    if kind == "missing-db":
        (state / "testmon.sqlite").unlink()
    (state / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    if kind == "corrupt-baseline":
        (state / "baseline.json").write_text("{", encoding="utf-8")
    if kind == "active-lock":
        (state / "active.lock").write_text("fictional owner", encoding="utf-8")
    with pytest.raises(RUNNER.WorkflowError):
        RUNNER.run(tmp_path, mode="affected", workers=0, tests=[])


@pytest.mark.parametrize("selection", ["../outside.py", "pyproject.toml", "tests/missing.py"])
def test_test_selection_cannot_escape_scope(tmp_path: Path, selection: str) -> None:
    project(tmp_path)
    with pytest.raises(RUNNER.WorkflowError, match="Test selection"):
        RUNNER.run(tmp_path, mode="selected", workers=0, tests=[selection])


def test_midrun_changes_never_advance_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project(tmp_path)

    def phase(*args: Any, **kwargs: Any) -> tuple[int, Path]:
        (tmp_path / "src/calc.py").write_text("changed during run\n", encoding="utf-8")
        return 0, tmp_path / "fictional.json"

    monkeypatch.setattr(RUNNER, "run_phase", phase)
    assert RUNNER.run(tmp_path, mode="full", workers=0, tests=[]) == 3
    assert not (tmp_path / ".local/test-workflow/state/baseline.json").exists()


def test_empty_explicit_selection_is_not_reported_as_verified(tmp_path: Path) -> None:
    project(tmp_path)
    (tmp_path / "tests/test_empty.py").write_text("# no tests\n", encoding="utf-8")
    assert RUNNER.run(tmp_path, mode="selected", workers=0, tests=["tests/test_empty.py"]) == 5
    assert reports(tmp_path)[-1]["passed"] is False


def test_failed_checkpoint_never_advances_baseline(tmp_path: Path) -> None:
    project(tmp_path)
    (tmp_path / "tests/test_calc.py").write_text(
        "def test_failure():\n    assert False\n", encoding="utf-8"
    )
    assert RUNNER.run(tmp_path, mode="full", workers=0, tests=[]) == 1
    assert not (tmp_path / ".local/test-workflow/state/baseline.json").exists()
    assert (tmp_path / ".local/test-workflow/state/failed.json").exists()
