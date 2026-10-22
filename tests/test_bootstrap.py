"""Toolchain qualification only; these tests do not validate financial behavior."""

import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
CONFIG = PROJECT / "pyproject.toml"


def run_module(module: str, *arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", "-m", module, *arguments],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )


def test_installed_package_imports_outside_source(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import prosper, json; from importlib import metadata; "
            "from pathlib import Path; "
            "print(json.dumps({'file': prosper.__file__, "
            "'name': metadata.metadata('prosper-local')['Name'], "
            "'typed': Path(prosper.__file__).with_name('py.typed').is_file()}))",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    imported = json.loads(result.stdout)
    package_path = Path(imported["file"]).resolve()
    assert package_path == (PROJECT / "src/prosper/__init__.py").resolve()
    assert package_path.read_bytes() == (PROJECT / "src/prosper/__init__.py").read_bytes()
    assert imported["name"] == "prosper-local"
    assert imported["typed"] is True


def test_ruff_rejects_deliberate_unused_import(tmp_path: Path) -> None:
    probe = tmp_path / "unused.py"
    probe.write_text("import os\n", encoding="utf-8")
    result = run_module(
        "ruff", "check", "--no-cache", "--config", str(CONFIG), str(probe), cwd=tmp_path
    )
    assert result.returncode == 1, result.stdout
    assert "F401" in result.stdout


def test_strict_mypy_accepts_annotations_and_rejects_misuse(tmp_path: Path) -> None:
    valid = tmp_path / "valid.py"
    valid.write_text(
        "from dataclasses import dataclass\n"
        "from typing import Protocol, TypedDict\n"
        "type Labels = list[str]\n"
        "class Named(Protocol):\n"
        "    @property\n"
        "    def name(self) -> str: ...\n"
        "class Details(TypedDict):\n"
        "    label: str\n"
        "@dataclass(frozen=True)\n"
        "class Item:\n"
        "    name: str\n"
        "def describe(item: Named, labels: Labels, details: Details | None) -> str:\n"
        "    return item.name + ''.join(labels) + (details['label'] if details else '')\n"
        "description: str = describe(Item('demo'), ['synthetic'], None)\n",
        encoding="utf-8",
    )
    accepted = run_module("mypy", "--config-file", str(CONFIG), str(valid), cwd=tmp_path)
    assert accepted.returncode == 0, accepted.stdout
    invalid = tmp_path / "invalid.py"
    invalid.write_text(
        "def untyped(value):\n    return value\ncount: int = 'wrong'\n", encoding="utf-8"
    )
    rejected = run_module("mypy", "--config-file", str(CONFIG), str(invalid), cwd=tmp_path)
    assert rejected.returncode == 1, rejected.stdout
    assert "[no-untyped-def]" in rejected.stdout
    assert "[assignment]" in rejected.stdout


def test_pytest_hypothesis_execute_and_find_counterexample(tmp_path: Path) -> None:
    valid = tmp_path / "test_valid.py"
    valid.write_text(
        "from hypothesis import given, settings, strategies as st\n"
        "@settings(database=None, derandomize=True, max_examples=20)\n"
        "@given(st.lists(st.integers(), max_size=10))\n"
        "def test_reverse_twice(values: list[int]) -> None:\n"
        "    assert list(reversed(list(reversed(values)))) == values\n",
        encoding="utf-8",
    )
    accepted = run_module("pytest", "-c", str(CONFIG), str(valid), "-q", cwd=tmp_path)
    assert accepted.returncode == 0, accepted.stdout
    assert "1 passed" in accepted.stdout
    invalid = tmp_path / "test_invalid.py"
    invalid.write_text(
        "from hypothesis import given, settings, strategies as st\n"
        "@settings(database=None, derandomize=True, max_examples=20)\n"
        "@given(st.integers(min_value=0, max_value=5))\n"
        "def test_deliberately_false(value: int) -> None:\n"
        "    assert value < 5\n",
        encoding="utf-8",
    )
    rejected = run_module("pytest", "-c", str(CONFIG), str(invalid), "-q", cwd=tmp_path)
    assert rejected.returncode == 1, rejected.stdout
    assert "1 failed" in rejected.stdout
    assert "assert 5 < 5" in rejected.stdout
    assert "value=5" in rejected.stdout
