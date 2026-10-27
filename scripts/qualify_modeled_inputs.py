"""Offline complete-input workflow in development or an isolated installed wheel."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import AdvisoryStore
from prosper.api_contracts import HistoryUpload, LotSettingsRequest, Upload
from prosper.benchmark import BenchmarkDiagnostic, BenchmarkImport, BenchmarkReview
from prosper.modeled_inputs import ModeledDiagnostic
from prosper.storage import RuntimeBoundary
from prosper.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]


def qualify() -> dict[str, object]:
    with TemporaryDirectory(prefix="modeled-input-probe-", dir=ROOT / ".local") as scratch:
        source = Workspace(AdvisoryStore(RuntimeBoundary(Path(scratch) / "source")))
        staged = source.stage(
            Upload.model_validate_json(
                (ROOT / "examples/synthetic/advisory-workspace.json").read_bytes()
            )
        )
        source.store.select(staged.id, "holdings", 0)
        benchmarks = ROOT / "examples/synthetic/benchmark"
        source.import_benchmark(
            BenchmarkImport.model_validate_json(
                (benchmarks / "current-observation.json").read_bytes()
            )
        )
        source.diagnose_benchmark(
            BenchmarkDiagnostic(
                run_id="benchmark",
                expected_revision=1,
                as_of="2026-10-25T22:00:00Z",
                review=BenchmarkReview.model_validate_json(
                    (benchmarks / "current-review.json").read_bytes()
                ),
            )
        )
        source.store.select_benchmark("benchmark", "benchmark", 1)
        folder = ROOT / "examples/synthetic/modeled-inputs"
        settings = json.loads((folder / "lot-settings.json").read_bytes())
        source.configure_lots(
            LotSettingsRequest.model_validate_json(
                json.dumps(
                    {"settings": settings, "command_key": "settings", "expected_revision": 2}
                )
            )
        )
        source.import_history(
            HistoryUpload.model_validate_json((folder / "history.json").read_bytes())
        )
        upload = json.loads((folder / "current.json").read_bytes())
        command = ModeledDiagnostic.model_validate_json(
            json.dumps(
                {
                    **upload,
                    "run_id": "inputs",
                    "expected_revision": 4,
                    "as_of": "2026-10-25T22:00:00Z",
                }
            )
        )
        saved = source.diagnose_inputs(command)
        assert saved.outputs["software_inputs_complete"] is True
        source.store.clear_history_cache("clear", 4)
        target = Workspace(AdvisoryStore(RuntimeBoundary(Path(scratch) / "target")))
        restore(target.store, backup(source.store))
        assert target.store.run(saved.id) == saved
        assert target.diagnose_inputs(command) == saved
        return {
            "security_ids": saved.outputs["security_ids"],
            "sessions": saved.outputs["sessions"],
            "risk_available": saved.outputs["risk_available"],
            "saved_output_restored_without_recalculation": True,
            "original_required_sources_retained": True,
        }


if __name__ == "__main__":
    print(json.dumps(qualify(), sort_keys=True, allow_nan=False))
