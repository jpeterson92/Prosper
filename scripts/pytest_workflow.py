"""Local pytest timing/execution records for the development runner."""

import json
from pathlib import Path
from typing import Any

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--workflow-json")
    parser.addoption("--workflow-exclude-json")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    filename = config.getoption("workflow_exclude_json")
    if filename:
        previous = set(json.loads(Path(filename).read_text(encoding="utf-8"))["executed"])
        excluded = [item for item in items if item.nodeid in previous]
        items[:] = [item for item in items if item.nodeid not in previous]
        config.hook.pytest_deselected(items=excluded)


class Recorder:
    def __init__(self, destination: Path) -> None:
        self.destination = destination
        self.executed: set[str] = set()
        self.reports: list[dict[str, Any]] = []
        self.worker_count = 0

    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_setupnodes(self, specs: list[Any]) -> None:
        self.worker_count = len(specs)

    def pytest_runtest_logstart(self, nodeid: str) -> None:
        self.executed.add(nodeid)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self.reports.append(
            {
                "nodeid": report.nodeid,
                "phase": report.when,
                "outcome": report.outcome,
                "seconds": report.duration,
                "worker": getattr(report, "worker_id", "serial"),
            }
        )

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        self.destination.write_text(
            json.dumps(
                {
                    "exitstatus": int(exitstatus),
                    "collected": session.testscollected,
                    "executed": sorted(self.executed),
                    "worker_count": self.worker_count,
                    "reports": self.reports,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )


def pytest_configure(config: pytest.Config) -> None:
    filename = config.getoption("workflow_json")
    if filename and not hasattr(config, "workerinput"):
        config.pluginmanager.register(Recorder(Path(filename)), "workflow-recorder")
