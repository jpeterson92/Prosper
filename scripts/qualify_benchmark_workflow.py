"""Offline current-workspace and isolated installed-wheel benchmark replay."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import AdvisoryStore
from prosper.api_contracts import Upload
from prosper.benchmark import BenchmarkDiagnostic, BenchmarkImport, BenchmarkReview
from prosper.storage import RuntimeBoundary
from prosper.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]


def qualify() -> dict[str, object]:
    with TemporaryDirectory(prefix="benchmark-probe-", dir=ROOT / ".local") as scratch:
        source = Workspace(AdvisoryStore(RuntimeBoundary(Path(scratch) / "source")))
        staged = source.stage(
            Upload.model_validate_json(
                (ROOT / "examples/synthetic/advisory-workspace.json").read_bytes()
            )
        )
        source.store.select(staged.id, "snapshot", 0)
        folder = ROOT / "examples/synthetic/benchmark"
        observation = source.import_benchmark(
            BenchmarkImport.model_validate_json((folder / "current-observation.json").read_bytes())
        )
        request = BenchmarkDiagnostic(
            run_id="benchmark",
            expected_revision=1,
            as_of="2026-10-25T22:00:00Z",
            review=BenchmarkReview.model_validate_json(
                (folder / "current-review.json").read_bytes()
            ),
        )
        run = source.diagnose_benchmark(request)
        source.store.select_benchmark(run.id, "selection", 1)
        target = Workspace(AdvisoryStore(RuntimeBoundary(Path(scratch) / "target")))
        restore(target.store, backup(source.store))
        assert target.store.run(run.id) == run
        assert target.store.current()["settings"] == {"benchmark_run_id": run.id}
        assert target.store.benchmark_observation(observation.request.observation_id) == observation
        assert target.diagnose_benchmark(request) == run
        return {
            "source_rows": run.outputs["source_row_count"],
            "retained_value": run.outputs["equity_value_total"],
            "weights": run.outputs["weights"],
            "original_sources_restored": True,
            "saved_output_restored_without_recalculation": True,
        }


if __name__ == "__main__":
    print(json.dumps(qualify(), sort_keys=True, allow_nan=False))
