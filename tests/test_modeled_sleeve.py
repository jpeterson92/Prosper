"""Observed history decisions, independently reasoned sleeve accounting and recovery."""

import base64
import hashlib
import json
import sqlite3
import zlib
from pathlib import Path
from typing import Any
from unittest.mock import patch

import polars as pl
import pytest

from prosper.advisory_records import DecimalFact
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import DATABASE_NAME
from prosper.api_contracts import HistoryUpload
from prosper.candidate_records import CandidateRequest, Orders
from prosper.candidate_validation import FinalValidator
from prosper.history_table import HistoryTable
from prosper.modeled_inputs import FrozenModeledInputs, ModeledResult, ModeledUpload
from prosper.modeled_sleeve import CoverageName, coverage
from prosper.storage import PersistenceError
from tests.test_modeled_inputs import command, seed, service, upload


def seed_missing(workspace: object, missing: set[str], *, incompatible: bool = False) -> None:
    from prosper.workspace import Workspace

    assert isinstance(workspace, Workspace)
    original = workspace.import_history

    def changed(request: HistoryUpload) -> object:
        parts = []
        for part in request.parts:
            frame = part.batch.rows.frame.filter(~pl.col("security_id").is_in(missing))
            # Authored fictional observation originals match this exact changed table.
            raw = frame.write_json().encode()
            batch = part.batch.model_copy(
                update={
                    "rows": HistoryTable.pack(frame, "observations"),
                    "source_sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
            if incompatible:
                batch = batch.model_copy(
                    update={
                        "contexts": tuple(
                            c.model_copy(update={"adjustment": "split-adjusted"})
                            if c.security_id == "FICTIONAL-0"
                            else c
                            for c in batch.contexts
                        )
                    }
                )
            parts.append(
                part.model_copy(
                    update={
                        "batch": batch,
                        "source_zlib_base64": base64.b64encode(zlib.compress(raw)).decode(),
                    }
                )
            )
        return original(
            HistoryUpload.model_validate_json(
                request.model_copy(update={"parts": tuple(parts)}).model_dump_json()
            )
        )

    with patch.object(workspace, "import_history", side_effect=changed):
        seed(workspace)


def test_observed_unsupported_history_is_excluded_without_model_downgrade(tmp_path: Path) -> None:
    w = service(tmp_path / "runtime")
    seed_missing(w, set(), incompatible=True)
    raw = upload().model_dump(mode="json")
    next(c for c in raw["bundle"]["history"]["series"] if c["security_id"] == "FICTIONAL-0")[
        "adjustment"
    ] = "split-adjusted"
    result = w.preview_inputs(ModeledUpload.model_validate_json(json.dumps(raw)))
    assert result.software_inputs_complete, result.issues
    assert result.sleeve and result.sleeve.excluded_ids == {"FICTIONAL-0"}
    assert "unsupported_history_conventions" in result.sleeve.decisions[0].issue_codes
    assert result.members[0].benchmark_weight == 1


def test_aggregate_small_exclusions_are_not_hidden_by_per_name_thresholds() -> None:
    names = tuple(
        CoverageName(
            key=f"name-{i}",
            security_id=f"name-{i}",
            locators=(f"row:{i}",),
            value_usd=DecimalFact(value="0.9"),
            excluded=True,
        )
        for i in range(12)
    )
    retained = CoverageName(
        key="retained",
        security_id="retained",
        locators=("row:13",),
        value_usd=DecimalFact(value="989.2"),
        excluded=False,
    )
    result = coverage("benchmark", "2026-10-23", (*names, retained), "original source total")
    assert all(n.highlight is False for n in result.names if n.excluded)
    assert result.aggregate_excluded_bps == 108 and result.aggregate_highlight is True


@pytest.mark.parametrize(
    "excluded,retained,aggregate",
    [
        ("1.000000000000000000000000000001", "998.999999999999999999999999999999", False),
        ("10.000000000000000000000000000001", "989.999999999999999999999999999999", True),
    ],
)
def test_warning_does_not_round_a_supplied_value_down_to_threshold(
    excluded: str, retained: str, aggregate: bool
) -> None:
    names = tuple(
        CoverageName(
            key=key,
            security_id=key,
            locators=(key,),
            value_usd=DecimalFact(value=value),
            excluded=key == "excluded",
        )
        for key, value in (("excluded", excluded), ("retained", retained))
    )
    result = coverage("portfolio", "2026-10-23", names, "original $1000 source total")
    assert result.names[0].highlight is True and result.aggregate_highlight is aggregate


def test_source_and_later_date_weights_use_same_declared_retained_names(tmp_path: Path) -> None:
    from prosper.benchmark_drift import weights_at

    w = service(tmp_path / "runtime")
    seed(w)
    frozen = w.store.modeled_inputs(w.diagnose_inputs(command()).inputs["modeled_inputs"])
    assert frozen.benchmark and frozen.alignment
    benchmark = frozen.benchmark.model_copy(
        update={
            "security_ids": ("FICTIONAL-0", "FICTIONAL-1", "security-c"),
            "weights": (0.6, 0.3, 0.1),
        }
    )
    retained = ("FICTIONAL-1", "security-c")
    source = weights_at(benchmark, None, benchmark.effective_date, retained_ids=retained)
    assert source.weights and tuple(source.weights.values()) == pytest.approx((0.75, 0.25))
    # Three explicit +10% and -10% sessions give growth factors 1.331 and .729.
    frame = frozen.alignment.rows.frame.with_columns(
        pl.when(pl.col("security_id") == "FICTIONAL-1")
        .then(0.1)
        .when(pl.col("security_id") == "security-c")
        .then(-0.1)
        .otherwise(pl.col("total_return"))
        .alias("total_return")
    )
    alignment = frozen.alignment.model_copy(update={"rows": HistoryTable.pack(frame, "alignment")})
    later = weights_at(benchmark, alignment, "2026-10-23", retained_ids=retained)
    expected = 0.3 * 1.331 / (0.3 * 1.331 + 0.1 * 0.729)
    assert later.weights and tuple(later.weights.values()) == pytest.approx(
        (expected, 1 - expected)
    )
    assert benchmark.weights == (0.6, 0.3, 0.1)


def test_history_sleeve_keeps_originals_and_renormalizes_only_retained_benchmark(
    tmp_path: Path,
) -> None:
    w = service(tmp_path / "runtime")
    seed_missing(w, {"FICTIONAL-0", "security-a", "security-b"})
    before = w.store.snapshot(str(w.store.current()["snapshot_id"]))
    result = w.preview_inputs(upload())
    assert result.software_inputs_complete, result.issues
    assert result.security_ids == ("FICTIONAL-1", "security-c")
    assert result.members[0].benchmark_weight == 1 and result.members[1].benchmark_weight == 0
    assert result.return_cell_count == 6
    assert result.sleeve and result.sleeve.excluded_ids == {
        "FICTIONAL-0",
        "security-a",
        "security-b",
    }
    assert len(result.sleeve.decisions) == 5
    saved = w.diagnose_inputs(command())
    frozen = w.store.modeled_inputs(saved.inputs["modeled_inputs"])
    assert frozen.bundle == upload().bundle
    assert frozen.benchmark and frozen.benchmark.security_ids == ("FICTIONAL-0", "FICTIONAL-1")
    assert frozen.benchmark.weights == pytest.approx((2 / 3, 1 / 3))
    assert frozen.source_alignment and len(frozen.source_alignment.cells) == 15
    assert frozen.alignment and len(frozen.alignment.cells) == 6
    assert before == w.store.snapshot(saved.snapshot_id)
    assert w.diagnose_inputs(command()) == saved
    target = service(tmp_path / "restored")
    restore(target.store, backup(w.store))
    assert target.store.run(saved.id) == saved
    assert target.store.modeled_inputs(saved.inputs["modeled_inputs"]) == frozen
    w.store.clear_history_cache("clear", 4)
    assert target.store.run(saved.id) == saved
    assert (
        service(tmp_path / "runtime").store.modeled_inputs(saved.inputs["modeled_inputs"]) == frozen
    )
    raw = frozen.model_dump(mode="json")
    raw["sleeve"]["decisions"][0]["issue_codes"] = []
    with pytest.raises(ValueError, match="history_sleeve_reason_mismatch"):
        FrozenModeledInputs.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize("blocker", ["profile", "context", "corrupt", "capacity", "controls"])
def test_missing_history_cannot_hide_declaration_corruption_or_resource_blocker(
    tmp_path: Path, blocker: str
) -> None:
    w = service(tmp_path / "runtime")
    seed_missing(w, {"FICTIONAL-0"})
    raw = upload().model_dump(mode="json")
    if blocker == "profile":
        raw["bundle"]["profile"]["lookback_sessions"] = 1260
    elif blocker == "context":
        next(c for c in raw["bundle"]["history"]["series"] if c["security_id"] == "FICTIONAL-0")[
            "adjustment"
        ] = "total-return-adjusted"
    elif blocker == "capacity":
        raw["bundle"]["profile"]["maximum_universe_size"] = 2
    elif blocker == "controls":
        raw["bundle"]["investor_controls"] = []
    else:
        digest = w.store.history_batches()[0].source_sha256
        with sqlite3.connect(w.store.runtime.path(DATABASE_NAME)) as connection:
            connection.execute(
                "UPDATE sources SET zlib_bytes=? WHERE sha256=?", (b"corrupt", digest)
            )
    result = w.preview_inputs(ModeledUpload.model_validate_json(json.dumps(raw)))
    assert not result.software_inputs_complete
    assert "FICTIONAL-0" in result.security_ids
    assert result.sleeve and not result.sleeve.excluded_ids


def test_empty_sleeve_is_unavailable_and_exclusion_evidence_remains_required(
    tmp_path: Path,
) -> None:
    w = service(tmp_path / "runtime")
    seed_missing(w, {"FICTIONAL-0", "FICTIONAL-1", "security-a", "security-b", "security-c"})
    saved = w.diagnose_inputs(command())
    assert not saved.outputs["software_inputs_complete"]
    assert saved.outputs["security_ids"] == []
    result = ModeledResult.model_validate_json(json.dumps(saved.outputs))
    assert "empty_modeled_union" in {i.code for i in result.issues}
    frozen = w.store.modeled_inputs(saved.inputs["modeled_inputs"])
    assert frozen.source_alignment and frozen.alignment is None
    digest = frozen.source_alignment.required_sources[0]
    with sqlite3.connect(w.store.runtime.path(DATABASE_NAME)) as connection:
        connection.execute("UPDATE sources SET zlib_bytes=? WHERE sha256=?", (b"damaged", digest))
    with pytest.raises(PersistenceError):
        backup(w.store)


@pytest.mark.parametrize(
    "excluded,individual,aggregate",
    [("1", False, False), ("1.0001", True, False), ("10", True, False), ("10.0001", True, True)],
)
def test_strict_coverage_uses_original_denominator(
    excluded: str, individual: bool, aggregate: bool
) -> None:
    # Original value is exactly $1,000: $1 = 10 bps, $10 = 100 bps.
    from decimal import Decimal

    names = (
        CoverageName(
            key="excluded",
            security_id="excluded",
            locators=("row:1",),
            value_usd=DecimalFact(value=excluded),
            excluded=True,
        ),
        CoverageName(
            key="retained",
            security_id="retained",
            locators=("row:2",),
            value_usd=DecimalFact(value=str(Decimal(1000) - Decimal(excluded))),
            excluded=False,
        ),
    )
    result = coverage("portfolio", "2026-10-23", names, "original source total")
    assert (
        result.reference_value_usd.value == "1000.0000"
        or Decimal(result.reference_value_usd.value or "0") == 1000
    )
    assert result.names[0].highlight is individual
    assert result.aggregate_highlight is aggregate
    unknown = coverage(
        "portfolio",
        "2026-10-23",
        (
            names[0].model_copy(
                update={"value_usd": DecimalFact(value=None, reason="Missing value")}
            ),
            names[1],
        ),
        "original source total",
    )
    assert unknown.aggregate_excluded_bps is None and unknown.aggregate_highlight is None
    assert unknown.names[0].highlight is None and unknown.unknown_value_keys == ("excluded",)


def test_excluded_holding_creates_no_nav_or_cash_and_cannot_be_traded() -> None:
    root = Path(__file__).resolve().parents[1]
    output = json.loads(
        (root / "examples/synthetic/candidates/application/checked-output.json").read_bytes()
    )
    raw = output["search"]["inputs"]
    # $25 original holding is outside this sleeve. Only explicitly selected
    # $100 cash remains: NAV and cash must both be $100, never $125.
    raw["history_excluded_ids"] = ["security-faaa"]
    raw["assets"] = raw["assets"][1:]
    raw["settings"]["marks"] = raw["settings"]["marks"][1:]
    raw["settings"]["cash_to_invest"] = "100"
    raw["risk"]["security_ids"] = ["security-fbbb"]
    raw["risk"]["benchmark_ids"] = ["security-fbbb"]
    raw["risk"]["benchmark_weights"] = [1.0]
    raw["risk"]["annual_covariance"] = [[raw["risk"]["annual_covariance"][1][1]]]
    raw["sale_bounds"] = {"lot-a": 0}
    raw["buy_bounds"] = {"security-fbbb": 0}
    request = CandidateRequest.model_validate_json(json.dumps(raw))
    validator = FinalValidator(request)
    assert not validator.issues, validator.issues
    baseline = validator.check(Orders(sales=(), buys=()))
    assert baseline.feasible and baseline.metrics
    assert (
        baseline.metrics.final_nav,
        baseline.metrics.final_cash,
        baseline.metrics.final_quantities,
    ) == (100, 100, (0,))
    from prosper.candidate_records import SaleOrder

    refused = validator.check(Orders(sales=(SaleOrder(lot_id="lot-a", shares=1),), buys=()))
    assert not refused.feasible and any("excluded_sale" in i for i in refused.blockers)
    bad = request.model_copy(update={"sale_bounds": {"lot-a": 1}})
    assert "history_excluded_sale" in FinalValidator(bad).issues


def test_exclusion_survives_actual_candidate_publication_worksheet_and_restore(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess
    import sys

    from prosper import worksheets
    from prosper.api_contracts import Upload
    from prosper.candidate_workflow import CandidateOutput
    from prosper.modeled_inputs import ModeledDiagnostic
    from prosper.worksheets import WorksheetSave
    from tests.test_candidate_workflow import command as candidate_command
    from tests.test_candidate_workflow import load, wait
    from tests.test_candidate_workflow import seed as candidate_seed

    w = service(tmp_path / "source")
    stage, diagnose = w.stage, w.diagnose_inputs
    sid = "security-excluded"

    def holding(request: Upload) -> object:
        raw = request.model_dump(mode="json")
        snapshot = raw["snapshot"]
        security = dict(
            snapshot["securities"][0], id=sid, ticker="FEXC", source_ref="tiny-holdings.csv:3"
        )
        security["identity"] = {"value": "fictional-identity:FEXC", "reason": None}
        snapshot["securities"].append(security)
        snapshot["lots"].append(
            dict(
                snapshot["lots"][0],
                id="lot-excluded",
                security_id=sid,
                source_ref="tiny-holdings.csv:3",
            )
        )
        # A separate authored normalized holding, with its own preserved original.
        source = base64.b64decode(raw["source_base64"]) + b"\nFEXC,2.5000,30.00\n"
        digest = hashlib.sha256(source).hexdigest()
        raw["source_base64"] = base64.b64encode(source).decode()
        snapshot["source_sha256"] = digest
        snapshot["observations"]["lot_context"]["source_sha256"] = digest
        return stage(Upload.model_validate_json(json.dumps(raw)))

    def inputs(request: ModeledDiagnostic) -> object:
        raw = request.model_dump(mode="json")
        bundle = raw["bundle"]
        security = json.loads(json.dumps(bundle["securities"][0]))
        mark = json.loads(json.dumps(bundle["marks"][0]))
        group = json.loads(json.dumps(bundle["classifications"][0]))
        security["security_id"] = group["security_id"] = mark["mark"]["security_id"] = sid
        security["identity"]["value"] = mark["mark"]["identity"] = "fictional-identity:FEXC"
        source = json.dumps({"security": security, "mark": mark, "taxonomy": group}).encode()
        digest = hashlib.sha256(source).hexdigest()
        for fact in (security, mark, group):
            fact["evidence"]["source_sha256"] = digest
            fact["evidence"]["source_ref"] = "fixture/FEXC"
        bundle["securities"].append(security)
        bundle["marks"].append(mark)
        bundle["classifications"].append(group)
        context = dict(bundle["history"]["series"][0], security_id=sid, provider_symbol="FEXC")
        bundle["history"]["series"].append(context)
        raw["sources"].append(
            {"sha256": digest, "source_base64": base64.b64encode(source).decode()}
        )
        return diagnose(ModeledDiagnostic.model_validate_json(json.dumps(raw)))

    with (
        patch.object(w, "stage", side_effect=holding),
        patch.object(w, "diagnose_inputs", side_effect=inputs),
    ):
        candidate_seed(w)
    saved_inputs = w.store.run("inputs")
    model = w.store.modeled_inputs(saved_inputs.inputs["modeled_inputs"])
    assert model.sleeve.excluded_ids == {sid}
    assert model.alignment and model.source_alignment
    assert len(model.alignment.cells) == 2520 and len(model.source_alignment.cells) == 3780
    # Reuse the existing two-name fit/covariance evidence. The excluded third
    # holding changes neither numerical input series nor the retained model.
    output = CandidateOutput.model_validate_json(json.dumps(load("checked-output.json")))
    assert output.search
    original_request = output.search.inputs
    snapshot = w.store.snapshot(saved_inputs.snapshot_id)
    request = original_request.model_copy(
        update={
            "snapshot": snapshot,
            "history_excluded_ids": (sid,),
            "sale_bounds": {"lot-a": 2, "lot-excluded": 0},
        }
    )
    search = output.search.model_copy(update={"inputs": request})
    output = output.model_copy(
        update={"search": search, "warnings": (*output.warnings, *model.sleeve.warnings)}
    )
    response_path = tmp_path / "checked.json"
    response_path.write_text(output.model_dump_json(), encoding="utf-8")
    popen = subprocess.Popen

    def worker(args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        code = (
            "import sys;from pathlib import Path;sys.stdin.buffer.read();"
            "print(Path(sys.argv[1]).read_text())"
        )
        return popen([sys.executable, "-c", code, str(response_path)], **kwargs)

    monkeypatch.setattr("prosper.candidate_jobs.subprocess.Popen", worker)
    controls = candidate_command().controls.model_copy(
        update={"sale_bounds": {"lot-a": 2, "lot-excluded": 0}}
    )
    try:
        w.start_candidate(candidate_command(controls=controls.model_dump(mode="json")))
        run = wait(w)
        assert run.outputs["outcome"] == "checked", run.outputs
        assert any(e.code == "history_excluded" for e in run.exclusions)
        assert output.search and output.search.best
        worksheet = worksheets.save(
            w.store,
            WorksheetSave(
                id="worksheet",
                parent_id=None,
                run_id=run.id,
                expected_revision=4,
                as_of="2026-10-26T00:00:00Z",
                no_external_changes=True,
                orders=output.search.best.orders,
            ),
        )
        assert worksheet.check.metrics and worksheet.check.metrics.final_nav == 25
        assert any(e.code == "history_excluded" for e in worksheet.exclusions)
        assert "security-excluded" in worksheets.export_text(worksheet).decode()
        target = service(tmp_path / "restored")
        restore(target.store, backup(w.store))
        assert worksheets.read(target.store, worksheet.command.id) == worksheet
        assert target.store.run(run.id) == run
    finally:
        w.candidates.close()
