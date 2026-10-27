"""One input contract; source facts, arithmetic and recovery determine behavior."""

import base64
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from prosper.advisory_records import ImportSnapshot
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import AdvisoryStore
from prosper.api_contracts import FidelityOpening
from prosper.history_refresh import align, check_parts
from prosper.storage import RuntimeBoundary
from prosper.workspace import Workspace
from tests import test_candidate_workflow as candidate
from tests.test_lot_opportunities import FIXTURES
from tests.test_modeled_inputs import upload


def test_import_and_restore_have_no_data_category(tmp_path: Path) -> None:
    original = json.loads(
        (Path(__file__).parents[1] / "examples/synthetic/advisory-workspace.json").read_bytes()
    )
    snapshot = ImportSnapshot.model_validate_json(json.dumps(original["snapshot"]))
    source = AdvisoryStore(RuntimeBoundary(tmp_path / "source"))
    identity = source.stage(snapshot, base64.b64decode(original["source_base64"]))
    target = AdvisoryStore(RuntimeBoundary(tmp_path / "target"))
    restore(target, backup(source))
    assert target.snapshot(identity) == snapshot
    assert target.source(identity) == source.source(identity)
    assert "fictional" not in ImportSnapshot.model_fields
    original["snapshot"]["fictional"] = False
    with pytest.raises(ValidationError):
        ImportSnapshot.model_validate_json(json.dumps(original["snapshot"]))


def test_minimal_opening_keeps_unknowns_and_original_bytes(tmp_path: Path) -> None:
    raw = (FIXTURES / "combined-stocks.csv").read_bytes()
    opening = FidelityOpening(
        source_base64=base64.b64encode(raw).decode(),
        source_account="000SYNTH001",
        source_as_of="2026-10-23",
        account_alias="Chosen account",
        currency="USD",
        recorded_at="2026-10-27T00:00:00Z",
    )
    w = Workspace(AdvisoryStore(RuntimeBoundary(tmp_path / "data")))
    first = w.open_fidelity(opening)
    assert first == w.open_fidelity(opening)
    assert first.preview is not None
    snapshot = first.preview.snapshot
    assert snapshot.lots
    assert all(
        s.identity.value is None and s.classification.value is None for s in snapshot.securities
    )
    assert w.store.source(first.preview.id) == raw
    assert snapshot.observations["source_row_accounting"]
    from prosper.lot_records import FidelityContext

    context = FidelityContext.model_validate_json(json.dumps(snapshot.observations["lot_context"]))
    assert context.reported_basis_assumption.value is None


def test_imported_source_reaches_checked_candidate_and_recovery(tmp_path: Path) -> None:
    w = Workspace(AdvisoryStore(RuntimeBoundary(tmp_path / "data")))
    candidate.seed(w)
    w.start_candidate(candidate.command())
    run = candidate.wait(w)
    assert run.status == "partial", run.outputs
    assert run.outputs["outcome"] == "checked", run.outputs
    assert run.outputs["financial_use_authorized"] is False
    assert run.outputs["search"]["best"]["metrics"]["price_loss"] == 4
    restored = AdvisoryStore(RuntimeBoundary(tmp_path / "restored"))
    restore(restored, backup(w.store))
    assert restored.run(run.id) == run


def test_alignment_uses_conventions_not_origin_flags() -> None:
    from prosper.api_contracts import HistoryUpload

    request = upload().bundle.history
    source = Path(__file__).parents[1] / "examples/synthetic/modeled-inputs/history.json"
    parts = HistoryUpload.model_validate_json(source.read_bytes()).parts
    batches = tuple(p.batch for p in parts)
    assert align(request, batches).complete
    check_parts((batches[0], batches[0]))


def test_adjusted_history_requires_explicit_action_compatibility() -> None:
    import math

    import polars as pl

    from prosper.api_contracts import HistoryUpload
    from prosper.history_table import HistoryTable
    from prosper.risk_inputs import assemble, conventions_available

    source = Path(__file__).parents[1] / "examples/synthetic/modeled-inputs/history.json"
    parts = HistoryUpload.model_validate_json(source.read_bytes()).parts
    request = upload().bundle.history
    contexts = tuple(
        c.model_copy(update={"adjustment": "total-return-adjusted"}) for c in request.series
    )
    request = request.model_copy(update={"series": contexts})
    batches = tuple(
        p.batch.model_copy(
            update={
                "contexts": tuple(
                    c.model_copy(update={"adjustment": "total-return-adjusted"})
                    for c in p.batch.contexts
                ),
                "rows": HistoryTable.pack(
                    p.batch.rows.frame.with_columns(
                        pl.lit("dividend").alias("action"),
                        (pl.col("close") * 2).alias("adjusted_close"),
                    ),
                    "observations",
                ),
            }
        )
        for p in parts
    )
    alignment = align(request, batches)
    assert alignment.complete and conventions_available(alignment)
    result = assemble(alignment)
    assert result is not None and result.status == "ready"
    first = alignment.cells[0]
    observed = first.observation
    assert observed and first.total_return is not None
    assert (
        observed.open.value and observed.close.value and observed.high.value and observed.low.value
    )
    expected = 0.17 / 0.25 * (
        math.log(observed.open.value / observed.close.value) + math.log1p(first.total_return)
    ) ** 2 + 0.83 / 0.75 * math.log(observed.high.value / observed.low.value) ** 2 / (
        4 * math.log(2)
    )
    assert result.proxy[0][0] == pytest.approx(expected, rel=1e-12, abs=1e-15)
    unsafe = request.model_copy(
        update={
            "series": tuple(
                c.model_copy(update={"action_convention": "unverified"}) for c in contexts
            )
        }
    )
    assert not conventions_available(align(unsafe, batches))
