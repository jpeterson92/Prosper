"""Dated identity links, explicit exclusions and preservation through real services."""

import base64
import csv
import io
import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from prosper.advisory_records import DecimalFact, Fact, HoldingMappingRow, Security
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import DATABASE_NAME, AdvisoryStore
from prosper.api_contracts import DiagnosticRequest, FidelityOpening, Upload
from prosper.benchmark import BenchmarkDiagnostic, BenchmarkImport
from prosper.benchmark_metadata import IVV_URL, MetadataImport, PrepareRequest
from prosper.candidate_records import CandidateRequest, Orders
from prosper.candidate_validation import validate
from prosper.cash_treatment import CashTreatmentRequest
from prosper.fidelity_import import normalize
from prosper.holdings_mapping import HoldingsMappingRequest, coverage
from prosper.lot_opportunities import evaluate, retained_activities, screening_inputs
from prosper.lot_records import (
    FidelityContext,
    LotDiagnosticRequest,
    LotSettings,
    ScreeningFacts,
    SecurityMapping,
)
from prosper.modeled_inputs import ModeledUpload, union
from prosper.storage import PersistenceError, RuntimeBoundary
from prosper.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "examples/synthetic/blackrock"
RAW = (ROOT / "examples/synthetic/fidelity/benchmark-holdings.csv").read_bytes()


def seed(
    path: Path,
    raw: bytes = RAW,
    benchmark_raw: bytes | None = None,
    cash: bool = True,
    source_day: str = "2026-10-20",
) -> Workspace:
    w = Workspace(AdvisoryStore(RuntimeBoundary(path)))
    opened = w.open_fidelity(
        FidelityOpening(
            source_base64=base64.b64encode(raw).decode(),
            source_account="000SYNTH001",
            source_as_of=source_day,
            account_alias="Fictional mapping account",
            currency="USD",
            recorded_at="2026-10-21T12:00:00Z",
        )
    )
    assert opened.preview is not None
    w.store.select(opened.preview.id, "holdings", 0)
    supplied = BenchmarkImport.model_validate_json(
        (FOLDER / "current-observation.json").read_bytes()
    )
    if benchmark_raw is not None:
        supplied = supplied.model_copy(
            update={"source_base64": base64.b64encode(benchmark_raw).decode()}
        )
    observed = w.import_benchmark(supplied)
    reviewed = w.prepare_benchmark(
        PrepareRequest(
            observation_id=observed.request.observation_id,
            metadata_response=MetadataImport(
                collected_at="2026-10-22T12:00:00Z",
                response_url=IVV_URL,
                content_type="text/html",
                http_status=200,
                body_complete=True,
                source_base64=base64.b64encode((FOLDER / "metadata.html").read_bytes()).decode(),
            ),
        )
    )
    w.diagnose_benchmark(
        BenchmarkDiagnostic(
            run_id="benchmark",
            expected_revision=1,
            as_of=datetime.now(UTC).isoformat(),
            review=reviewed,
        )
    )
    w.store.select_benchmark("benchmark", "benchmark-choice", 1)
    if cash:
        sid = next(s.id for s in opened.preview.snapshot.securities if s.ticker == "FMMXX")
        w.store.treat_cash(
            CashTreatmentRequest(
                snapshot_id=opened.preview.id,
                security_id=sid,
                kind="cash-equivalent",
                command_key="cash",
                expected_revision=2,
            )
        )
    return w


def request(w: Workspace, exclusions: dict[str, str] | None = None) -> HoldingsMappingRequest:
    state = w.store.current()
    return HoldingsMappingRequest(
        snapshot_id=str(state["snapshot_id"]),
        benchmark_run_id="benchmark",
        expected_revision=int(str(state["revision"])),
        recorded_at=datetime.now(UTC).isoformat(),
        exclusions=exclusions or {},
    )


def test_actual_source_mapping_exclusions_cash_preview_selection_and_recovery(
    tmp_path: Path,
) -> None:
    w = seed(tmp_path / "source")
    before = w.store.current()
    original = w.store.snapshot(str(before["snapshot_id"]))
    saved = w.diagnose(
        DiagnosticRequest(
            run_id="original", expected_revision=3, as_of=datetime.now(UTC).isoformat()
        )
    )
    before = w.store.current()
    command = request(w)
    preview = w.prepare_holdings(command)
    assert w.prepare_holdings(command) == preview
    with pytest.raises(PersistenceError, match="holdings_mapping_generated_record_required"):
        w.stage(
            Upload(
                version="advisory-upload-v1",
                snapshot=preview.snapshot,
                source_base64=base64.b64encode(RAW).decode(),
            )
        )
    assert w.store.current() == before
    proof = preview.snapshot.holding_preparation
    assert proof is not None
    assert [(r.source.ticker, r.disposition) for r in proof.rows] == [
        ("FIAA", "mapped"),
        ("FIBB", "mapped"),
        ("FZZ", "excluded"),
        ("FMMXX", "cash-treatment"),
    ]
    assert [s.id for s in preview.snapshot.securities][:2] == ["FIAA", "FIBB"]
    assert all(
        s.identity.value == s.id and s.classification.value is None
        for s in preview.snapshot.securities[:2]
    )
    assert preview.snapshot.cash_treatments == original.cash_treatments
    assert proof.reference_value_usd.value == "1620.00"
    assert proof.excluded_known_value_usd == "20.00"
    assert proof.aggregate_excluded_bps == pytest.approx(20 / 1620 * 10000)
    assert proof.aggregate_highlight and proof.rows[2].highlight
    for previous, current in zip(original.lots, preview.snapshot.lots, strict=True):
        assert previous.model_dump(exclude={"security_id"}) == current.model_dump(
            exclude={"security_id"}
        )
    assert w.store.select(preview.id, "mapped", 3) == {"outcome": "changed", "revision": 4}
    assert w.store.current()["current_run_id"] is None
    assert w.store.current()["settings"] == before["settings"]
    assert w.store.source(preview.id) == RAW and w.store.run("original") == saved
    target = Workspace(AdvisoryStore(RuntimeBoundary(tmp_path / "restored")))
    restore(target.store, backup(w.store))
    assert target.preview(preview.id) == preview
    assert target.store.run("original") == saved
    assert target.store.current() == w.store.current()
    assert target.store.source(preview.id) == RAW


@pytest.mark.parametrize(
    "case", ["name-conflict", "share-class-exact", "share-class-punctuation", "ambiguous-source"]
)
def test_exact_names_share_classes_and_ambiguity_refuse_guesses(tmp_path: Path, case: str) -> None:
    raw, benchmark = RAW, (FOLDER / "current.csv").read_bytes()
    if case == "name-conflict":
        raw = raw.replace(b"Fictional Alpha", b"Different Company")
    if case.startswith("share-class"):
        benchmark = benchmark.replace(b"FIAA", b"BRK B")
        raw = raw.replace(b"FIAA", b"BRK B" if case == "share-class-exact" else b"BRK.B")
    if case == "ambiguous-source":
        rows = list(csv.reader(io.StringIO(raw.decode())))
        extra = rows[1].copy()
        extra[3], extra[5] = "Different Company", "7"
        extra[4] = "SYNTHETIC_A_FIAA_SECOND.csv"
        rows.append(extra)
        buffer = io.StringIO(newline="")
        csv.writer(buffer).writerows(rows)
        raw = buffer.getvalue().encode()
    w = seed(tmp_path / "source", raw, benchmark)
    preview = w.prepare_holdings(request(w))
    proof = preview.snapshot.holding_preparation
    assert proof is not None
    first = proof.rows[0]
    if case == "share-class-exact":
        assert first.disposition == "mapped" and first.security_id.startswith("issuer-")
        assert first.source.ticker == "BRK B"
    else:
        assert first.disposition == "excluded"


def test_explicit_exclusion_and_frozen_universe_do_not_erase_acquisitions(tmp_path: Path) -> None:
    w = seed(tmp_path / "source")
    original = w.store.snapshot(str(w.store.current()["snapshot_id"]))
    sid = next(s.id for s in original.securities if s.ticker == "FIBB")
    preview = w.prepare_holdings(request(w, {sid: "Explicit investor exclusion"}))
    proof = preview.snapshot.holding_preparation
    assert proof is not None and proof.rows[1].reason == "Explicit investor exclusion"
    bundle = ModeledUpload.model_validate_json(
        (ROOT / "examples/synthetic/modeled-inputs/current.json").read_bytes()
    ).bundle.model_copy(update={"candidate_security_ids": ()})
    ids, _, exclusions = union(preview.snapshot, None, bundle)
    assert ids == ("FIAA",) and any(r.code == "holding_mapping_excluded" for r in exclusions)
    all_activity = retained_activities((preview.snapshot, original))
    alpha_refs = proof.rows[0].source_refs
    assert all(a.identity.value == "FIAA" for a in all_activity if a.source_ref in alpha_refs)
    # The excluded unknown stock's actual source acquisition is retained.
    assert any(
        a.source_ref in proof.rows[1].source_refs and a.identity.value is None for a in all_activity
    )


def test_stale_preparation_and_cash_changes_cannot_select_an_old_draft(tmp_path: Path) -> None:
    w = seed(tmp_path / "source")
    command = request(w)
    preview = w.prepare_holdings(command)
    original = w.store.snapshot(command.snapshot_id)
    sid = original.cash_treatments[0].security_id
    w.store.treat_cash(
        CashTreatmentRequest(
            snapshot_id=command.snapshot_id,
            security_id=sid,
            kind="cash",
            command_key="changed-cash",
            expected_revision=3,
        )
    )
    state = w.store.current()
    assert w.store.select(preview.id, "stale-selection", 4)["outcome"] == "prepared_snapshot_stale"
    assert w.store.current() == state
    with pytest.raises(PersistenceError, match="holdings_mapping_inputs_changed"):
        w.prepare_holdings(command)


@pytest.mark.parametrize("case", ["date", "future", "missing-source", "corrupt-parent"])
def test_wrong_dates_and_required_evidence_refuse_without_changing_selection(
    tmp_path: Path, case: str
) -> None:
    w = seed(tmp_path / "source", source_day="2026-10-19" if case == "date" else "2026-10-20")
    command = request(w)
    state = w.store.current()
    if case == "date":
        with pytest.raises(
            PersistenceError, match="holdings_mapping_fund_date_or_knowledge_invalid"
        ):
            w.prepare_holdings(command)
    elif case == "future":
        with pytest.raises(
            PersistenceError, match="holdings_mapping_fund_date_or_knowledge_invalid"
        ):
            w.prepare_holdings(command.model_copy(update={"recorded_at": "2099-01-01T00:00:00Z"}))
    elif case == "missing-source":
        with sqlite3.connect(tmp_path / "source" / DATABASE_NAME) as connection:
            connection.execute(
                "DELETE FROM sources WHERE sha256=?",
                (w.store.benchmark_observation("fictional-ivv").source_sha256,),
            )
        with pytest.raises(PersistenceError):
            w.prepare_holdings(command)
    else:
        preview = w.prepare_holdings(command)
        with sqlite3.connect(tmp_path / "source" / DATABASE_NAME) as connection:
            connection.execute(
                "UPDATE snapshots SET document=replace(document,?,?) WHERE id=?",
                ("Fictional Alpha", "Changed Alpha", command.snapshot_id),
            )
        with pytest.raises(PersistenceError):
            w.preview(preview.id)
        with pytest.raises(PersistenceError):
            backup(w.store)
        return
    assert w.store.current() == state


@pytest.mark.parametrize("amount,expected", [("1", False), ("1.0000000001", True)])
def test_strict_single_name_threshold_uses_original_denominator(
    amount: str, expected: bool
) -> None:
    # Total $1000: $1 is exactly 10 bps; a positive increment must highlight.
    security = Security(
        id="one",
        source_ref="one",
        ticker="ONE",
        identity=Fact[str](value=None, reason="Unknown"),
        classification=Fact[str](value=None, reason="Unknown"),
    )
    rows = [
        HoldingMappingRow(
            source=security,
            source_refs=("one",),
            security_id="one",
            disposition="excluded",
            reason="Unmapped",
            reported_value=DecimalFact(value=amount),
        ),
        HoldingMappingRow(
            source=security.model_copy(update={"id": "two"}),
            source_refs=("two",),
            security_id="two",
            disposition="preserved",
            reason="Known",
            reported_value=DecimalFact(value=str(Decimal(1000) - Decimal(amount))),
        ),
    ]
    result = coverage(rows)
    checked = result["rows"]
    assert isinstance(checked, tuple) and checked[0].highlight is expected


def test_unknown_coverage_is_not_zero_and_failed_staging_rolls_back(tmp_path: Path) -> None:
    raw = RAW.replace(b"$20.00,1.000", b"--,1.000")
    w = seed(tmp_path / "source", raw)
    command = request(w)
    state = w.store.current()
    with patch("prosper.advisory_store._before_commit", side_effect=RuntimeError("Interrupted")):
        with pytest.raises(RuntimeError):
            w.prepare_holdings(command)
    assert w.store.current() == state
    proof = w.prepare_holdings(command).snapshot.holding_preparation
    assert proof is not None and proof.reference_value_usd.value is None
    assert proof.aggregate_excluded_bps is None and proof.aggregate_highlight is None
    assert proof.unknown_value_ids and proof.coverage_unknown_reasons


@pytest.mark.parametrize("amount,expected", [("10", False), ("10.0000000001", True)])
def test_strict_aggregate_threshold_is_a_warning(amount: str, expected: bool) -> None:
    security = Security(
        id="one",
        source_ref="one",
        ticker="ONE",
        identity=Fact[str](value=None, reason="Unknown"),
        classification=Fact[str](value=None, reason="Unknown"),
    )
    rows = [
        HoldingMappingRow(
            source=security,
            source_refs=("one",),
            security_id="one",
            disposition="excluded",
            reason="Unmapped",
            reported_value=DecimalFact(value=amount),
        ),
        HoldingMappingRow(
            source=security.model_copy(update={"id": "two"}),
            source_refs=("two",),
            security_id="two",
            disposition="preserved",
            reason="Known",
            reported_value=DecimalFact(value=str(Decimal(1000) - Decimal(amount))),
        ),
    ]
    assert coverage(rows)["aggregate_highlight"] is expected


def test_excluded_lots_keep_source_rows_and_cannot_be_proposed_as_stock_trades(
    tmp_path: Path,
) -> None:
    w = seed(tmp_path / "source")
    snapshot = w.prepare_holdings(request(w)).snapshot
    excluded = next(lot for lot in snapshot.lots if lot.security_id in snapshot.excluded_stock_ids)
    candidate = CandidateRequest.model_validate_json(
        (ROOT / "examples/synthetic/candidates/tiny-request.json").read_bytes()
    )
    candidate = candidate.model_copy(
        update={
            "snapshot": snapshot,
            "sale_bounds": {lot.id: 1 for lot in snapshot.lots},
            "buy_bounds": {excluded.security_id: 1},
        }
    )
    checked = validate(candidate, Orders(sales=(), buys=()))
    assert "holding_mapping_excluded_sale" in checked.blockers
    assert "holding_mapping_excluded_purchase" in checked.blockers
    settings = LotSettings.model_validate_json(
        (ROOT / "examples/synthetic/fidelity/current-lot-settings.json").read_bytes()
    )
    result = evaluate(
        snapshot,
        screening_inputs((snapshot,)),
        settings,
        LotDiagnosticRequest(
            run_id="lots", expected_revision=3, as_of=datetime.now(UTC).isoformat()
        ),
    )
    row = next(r for r in result.rows if r.lot_id == excluded.id)
    assert len(result.rows) == len(snapshot.lots)
    assert (
        row.status == "excluded"
        and row.proposed_whole_shares is None
        and row.price_basis_loss.value is None
    )


def test_independent_activity_with_an_adapter_shaped_id_remains_unknown(tmp_path: Path) -> None:
    w = seed(tmp_path / "source")
    original = w.store.snapshot(str(w.store.current()["snapshot_id"]))
    context = FidelityContext.model_validate_json(json.dumps(original.observations["lot_context"]))
    facts = ScreeningFacts.model_validate_json(json.dumps(original.observations["screening"]))
    independent = facts.activities[0].model_copy(update={"day": Fact[str](value="2026-10-20")})
    context = context.model_copy(
        update={
            "screening": context.screening.model_copy(
                update={"activities": (*context.screening.activities, independent)}
            )
        }
    )
    supplied, _ = normalize(RAW, context)
    assert supplied is not None
    supplied = supplied.model_copy(update={"cash_treatments": original.cash_treatments})
    identity = w.store.stage(supplied, RAW)
    assert w.store.select(identity, "independent-facts", 3)["outcome"] == "changed"
    prepared = w.prepare_holdings(request(w)).snapshot
    activities = retained_activities((prepared, supplied, original))
    assert independent in activities and independent.identity.value is None
    assert any(
        a.source_ref == independent.source_ref and a.identity.value == "FIAA" for a in activities
    )


def test_supplied_identity_and_classification_are_preserved_instead_of_replaced(
    tmp_path: Path,
) -> None:
    w = seed(tmp_path / "source")
    original = w.store.snapshot(str(w.store.current()["snapshot_id"]))
    context = FidelityContext.model_validate_json(json.dumps(original.observations["lot_context"]))
    alpha = next(s for s in original.securities if s.ticker == "FIAA").model_copy(
        update={
            "id": "reviewed-alpha",
            "identity": Fact[str](value="known-alpha"),
            "classification": Fact[str](value="us-domestic-common-equity"),
        }
    )
    context = context.model_copy(
        update={
            "mappings": (
                SecurityMapping(
                    source_account="000SYNTH001",
                    symbol="FIAA",
                    security=alpha,
                    evidence=context.evidence,
                ),
            )
        }
    )
    supplied, _ = normalize(RAW, context)
    assert supplied is not None
    supplied = supplied.model_copy(update={"cash_treatments": original.cash_treatments})
    identity = w.store.stage(supplied, RAW)
    w.store.select(identity, "reviewed-context", 3)
    prepared = w.prepare_holdings(request(w)).snapshot
    assert prepared.securities[0] == alpha
    assert prepared.holding_preparation is not None
    assert prepared.holding_preparation.rows[0].disposition == "preserved"
