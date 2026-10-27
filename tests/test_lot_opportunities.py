"""Independent lot arithmetic, source accounting and conservative conflict cases."""

import base64
import hashlib
import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import date, timedelta
from decimal import localcontext
from pathlib import Path
from typing import Literal

import pytest

from prosper.advisory_records import Cash, DecimalFact, Fact, ImportSnapshot
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import AdvisoryStore
from prosper.api_contracts import FidelityUpload, LotSettingsRequest
from prosper.fidelity_import import normalize
from prosper.lot_opportunities import evaluate, screen, screening_inputs
from prosper.lot_records import (
    Activity,
    Evidence,
    FidelityContext,
    IndependentPosition,
    LotDiagnosticRequest,
    LotSettings,
    Relationship,
    Restriction,
)
from prosper.storage import PersistenceError, RuntimeBoundary
from prosper.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "examples/synthetic/fidelity"


def context(raw: bytes | None = None) -> FidelityContext:
    result = FidelityContext.model_validate_json((FIXTURES / "current-context.json").read_bytes())
    return (
        result.model_copy(update={"source_sha256": hashlib.sha256(raw).hexdigest()})
        if raw
        else result
    )


def settings() -> LotSettings:
    return LotSettings.model_validate_json((FIXTURES / "current-lot-settings.json").read_bytes())


def source(raw: bytes | None = None) -> ImportSnapshot:
    raw = raw if raw is not None else (FIXTURES / "combined-stocks.csv").read_bytes()
    result, _ = normalize(raw, context(raw))
    assert result is not None
    return result


def command(**changes: object) -> LotDiagnosticRequest:
    return LotDiagnosticRequest.model_validate_json(
        json.dumps(
            {
                "run_id": "lot-run",
                "expected_revision": 2,
                "as_of": "2026-10-25T00:00:00Z",
                **changes,
            }
        )
    )


def single(
    quantity: str = "10", basis: str | None = "1250", mark: str = "100"
) -> tuple[ImportSnapshot, LotSettings]:
    s = source()
    lot = s.lots[0].model_copy(
        update={
            "id": "one-lot",
            "quantity": DecimalFact(value=quantity),
            "total_basis": DecimalFact(
                value=basis, reason="not supplied" if basis is None else None
            ),
            "acquired": Fact[str](value="2000-01-01"),
        }
    )
    s = s.model_copy(
        update={
            "lots": (lot,),
            "observations": {
                "lot_context": {"reported_basis_assumption": {"value": True, "reason": None}}
            },
        }
    )
    cfg = settings()
    m = cfg.marks[0].model_copy(update={"price": DecimalFact(value=mark)})
    cfg = cfg.model_copy(update={"marks": (m,)})
    return s, cfg


def activity(
    side: str = "acquisition",
    offset: int = 0,
    pnl: str | None = None,
    identity: str | None = "fictional-identity:FAAA",
) -> Activity:
    return Activity.model_validate_json(
        json.dumps(
            {
                "id": "event",
                "identity": {
                    "value": identity,
                    "reason": "not mapped" if identity is None else None,
                },
                "account_ref": "spouse-or-IRA",
                "account_scope": "ira-roth",
                "day": {
                    "value": (date(2026, 1, 15) + timedelta(days=offset)).isoformat(),
                    "reason": None,
                },
                "side": side,
                "quantity": {"value": "1", "reason": None},
                "pnl": {"value": pnl, "reason": "sale P&L not supplied" if pnl is None else None},
                "source_ref": "fictional:event",
            }
        )
    )


def test_csv_source_accounting_distinct_lots_original_bytes_and_ira_conflict() -> None:
    s = source()
    assert len(s.lots) == 5 and len({lot.id for lot in s.lots}) == 5
    assert [lot.quantity.value for lot in s.lots] == ["10.000", "2.500", "2.500", "3.000", "0.125"]
    accounting = s.observations["source_row_accounting"]
    assert isinstance(accounting, list) and len(accounting) == 8
    assert len([x for x in s.exclusions if x.code == "outside_selected_account"]) == 3
    result = evaluate(s, screening_inputs((s,)), settings(), command())
    assert [r.price_basis_loss.value for r in result.rows[:3]] == [250.0, 40.0, 40.0]
    assert all(any("known_acquisition_conflict" in b for b in r.blockers) for r in result.rows[:3])
    assert (
        result.rows[3].status == "conditional-loss"
        and result.rows[3].price_basis_loss.value == 10.0
    )
    assert result.rows[4].quantity.value == "0.125" and result.rows[4].proposed_whole_shares is None
    assert result.conditional_price_loss_subtotal.value == 10.0
    assert any("Unverified" in w for w in result.warnings)


@pytest.mark.parametrize(
    "quantity,basis,shares,mark,allocated,loss,remaining",
    [
        ("10", "1250", 10, "100", 1250.0, 250.0, "0"),
        ("10", "1250", 4, "100", 500.0, 100.0, "6"),
        ("3.7500", "112.50", 3, "20", 90.0, 30.0, "0.7500"),
        ("3", "30.000000000003", 1, "10", 10.000000000001, 1e-12, "2"),
    ],
)
def test_independent_full_partial_fractional_and_near_gain_estimates(
    quantity: str, basis: str, shares: int, mark: str, allocated: float, loss: float, remaining: str
) -> None:
    s, cfg = single(quantity, basis, mark)
    with localcontext() as ctx:
        ctx.prec = 3
        result = evaluate(
            s, screening_inputs((s,)), cfg, command(sale_quantities={"one-lot": shares})
        )
    row = result.rows[0]
    assert row.allocated_basis.value == pytest.approx(allocated, abs=1e-14)
    assert row.price_basis_loss.value == pytest.approx(loss, rel=1e-12, abs=1e-20)
    assert row.remaining_quantity == remaining and row.status == "conditional-loss"
    # Frozen marks less 10 bp spread and a full $1 isolated order fee.
    gross = shares * float(mark)
    cost = gross * 0.001 + 1
    assert row.modeled_cost.value == pytest.approx(cost)
    assert row.indicative_net_proceeds.value == pytest.approx(gross - cost)
    assert row.indicative_tax_pnl.value == pytest.approx(-loss - cost)


def test_fees_cannot_create_eligible_reference_loss_or_implicit_funding() -> None:
    s, cfg = single("1", "99", "100")
    cfg = cfg.model_copy(update={"sell_fee_per_isolated_order": DecimalFact(value="200")})
    s = s.model_copy(
        update={
            "cash": (
                Cash(
                    id="cash",
                    account_id=s.account_id,
                    source_ref="fictional cash",
                    amount=DecimalFact(value="1000000"),
                    kind="settled",
                ),
            )
        }
    )
    row = evaluate(s, screening_inputs((s,)), cfg, command()).rows[0]
    assert row.price_basis_loss.value == -1
    assert row.indicative_tax_pnl.value is not None and row.indicative_tax_pnl.value < 0
    assert "no_reference_price_loss" in row.blockers
    assert "isolated_sale_unfunded_under_selected_cash" in row.blockers
    assert cfg.cash_to_invest == "0" and s.cash[0].amount.value == "1000000"


def test_missing_basis_term_cost_and_fractional_remainder_never_become_zero() -> None:
    s, cfg = single("2.5000", None)
    s = s.model_copy(
        update={
            "lots": (
                s.lots[0].model_copy(
                    update={"term": Fact[str](value=None, reason="term not supplied")}
                ),
            )
        }
    )
    cfg = cfg.model_copy(
        update={"sell_fee_per_isolated_order": DecimalFact(value=None, reason="fee not entered")}
    )
    row = evaluate(s, screening_inputs((s,)), cfg, command()).rows[0]
    assert row.quantity.value == "2.5000" and row.remaining_quantity == "0.5000"
    assert row.price_basis_loss.value is None and row.allocated_basis.value is None
    assert row.indicative_net_proceeds.value is None and row.indicative_tax_pnl.value is None
    assert "basis_unknown" in row.blockers and any(
        "Unknown source holding term" in w for w in row.warnings
    )


@pytest.mark.parametrize(
    "offset,blocked", [(-31, False), (-30, True), (0, True), (30, True), (31, False)]
)
@pytest.mark.parametrize("side", ["sell", "buy"])
def test_inclusive_calendar_window_both_legs_and_cross_year(
    offset: int, blocked: bool, side: Literal["sell", "buy"]
) -> None:
    security = source().securities[0]
    cfg = settings().model_copy(update={"analysis_date": "2026-01-15"})
    event = activity("acquisition" if side == "sell" else "sale", offset, None)
    assert bool(screen(security, side, cfg, (event,), (), ())) is blocked


def test_unknown_sale_pnl_and_activity_dates_block_without_inventing_clean_history() -> None:
    security = source().securities[0]
    cfg = settings().model_copy(update={"analysis_date": "2026-01-15"})
    unknown = activity("sale", -1, None)
    assert screen(security, "buy", cfg, (unknown,), (), ())
    assert not screen(
        security, "buy", cfg, (unknown.model_copy(update={"pnl": Fact[str](value="1.00")}),), (), ()
    )
    event = activity().model_copy(update={"day": Fact[str](value=None, reason="cutoff unknown")})
    assert any(
        "activity_date_unknown" in r for r in screen(security, "sell", cfg, (event,), (), ())
    )
    assert screen(security, "sell", cfg, (activity(identity=None),), (), ())


def test_alias_identity_manual_names_and_reviewed_unknown_relationships() -> None:
    security = source().securities[0]
    cfg = settings().model_copy(update={"analysis_date": "2026-01-15"})
    alias = security.model_copy(update={"id": "different-ticker-id", "ticker": "ALIAS"})
    assert screen(alias, "sell", cfg, (activity(),), (), ())
    manual = Restriction(name="FAAA", identity=security.identity, source_ref="user list")
    assert screen(security, "sell", cfg, (), (), (manual,)) and screen(
        security, "buy", cfg, (), (), (manual,)
    )
    unresolved = manual.model_copy(
        update={"identity": Fact[str](value=None, reason="manual name unresolved")}
    )
    assert "unresolved_manual_name" in screen(security, "buy", cfg, (), (), (unresolved,))
    assert security.identity.value is not None
    relation = Relationship(
        left=security.identity.value,
        right="other-identity",
        status="unknown",
        valid_from="2025-01-01",
        valid_through="2027-01-01",
        evidence=Evidence(
            actor="Fictional reviewer",
            reference="unresolved pair",
            effective_at="2025-01-01",
            recorded_at="2025-01-01T00:00:00Z",
        ),
        rationale="No legal conclusion",
    )
    other = activity(identity="other-identity")
    assert any(
        "identity_relationship_unresolved" in r
        for r in screen(security, "sell", cfg, (other,), (relation,), ())
    )


@pytest.mark.parametrize(
    "kind",
    [
        "unknown-class",
        "foreign-class",
        "identity",
        "stale-mark",
        "future-mark",
        "basis-dispute",
        "event-impact",
        "unreviewed-basis",
        "oversell",
    ],
)
def test_scoped_blockers_preserve_other_source_facts(kind: str) -> None:
    s, cfg = single()
    cmd = command()
    if kind in ("unknown-class", "foreign-class"):
        sec = s.securities[0].model_copy(
            update={
                "classification": Fact[str](value=None, reason="classification unknown")
                if kind == "unknown-class"
                else Fact[str](value="adr-foreign")
            }
        )
        s = s.model_copy(update={"securities": (sec, *s.securities[1:])})
    elif kind == "identity":
        cfg = cfg.model_copy(
            update={"marks": (cfg.marks[0].model_copy(update={"identity": "different"}),)}
        )
    elif kind in ("stale-mark", "future-mark"):
        cfg = cfg.model_copy(
            update={
                "marks": (
                    cfg.marks[0].model_copy(
                        update={
                            "day": Fact[str](
                                value="2026-10-22" if kind == "stale-mark" else "2026-10-24"
                            )
                        }
                    ),
                )
            }
        )
    elif kind == "unreviewed-basis":
        s = s.model_copy(update={"observations": {}})
    elif kind == "oversell":
        cmd = command(sale_quantities={"one-lot": 11})
    else:
        facts = context().screening.model_copy(
            update={"basis_disputes": ("fictional-identity:FAAA",)}
            if kind == "basis-dispute"
            else {"unbounded_event": Fact[bool](value=None, reason="impact unknown")}
        )
        s = s.model_copy(
            update={"observations": {**s.observations, "screening": facts.model_dump(mode="json")}}
        )
    result = evaluate(s, screening_inputs((s,)), cfg, cmd)
    assert result.rows[0].status == "blocked" and result.rows[0].blockers
    assert result.rows[0].quantity.value == "10"


@pytest.mark.parametrize(
    "filename", ["repeated-reference.csv", "conflicting-reference.csv", "malformed-row.csv"]
)
def test_failed_replacement_keeps_selected_snapshot_and_original_evidence(
    tmp_path: Path, filename: str
) -> None:
    w = Workspace(AdvisoryStore(RuntimeBoundary(tmp_path / "runtime")))
    original = (FIXTURES / "combined-stocks.csv").read_bytes()
    first = w.stage_fidelity(
        FidelityUpload(context=context(), source_base64=base64.b64encode(original).decode())
    )
    assert first.preview
    w.store.select(first.preview.id, "first", 0)
    raw = (FIXTURES / filename).read_bytes()
    replaced = w.stage_fidelity(
        FidelityUpload(context=context(raw), source_base64=base64.b64encode(raw).decode())
    )
    if replaced.preview:
        assert w.store.select(replaced.preview.id, "bad", 1)["outcome"] == "preview_blocked"
    assert w.store.current()["snapshot_id"] == first.preview.id
    assert w.store.source(first.preview.id) == original


def test_current_store_retries_retained_conflicts_settings_and_source_recovery(
    tmp_path: Path,
) -> None:
    w = Workspace(AdvisoryStore(RuntimeBoundary(tmp_path / "runtime")))
    raw = (FIXTURES / "combined-stocks.csv").read_bytes()
    p = w.stage_fidelity(
        FidelityUpload(context=context(), source_base64=base64.b64encode(raw).decode())
    ).preview
    assert p
    w.store.select(p.id, "select", 0)
    w.configure_lots(
        LotSettingsRequest(settings=settings(), command_key="settings", expected_revision=1)
    )
    saved = w.diagnose_lots(command())
    assert w.diagnose_lots(command()) == saved and saved.status == "partial"
    assert saved.outputs["validation_outcome"] == "not_validated"
    w.configure_lots(
        LotSettingsRequest(
            settings=settings().model_copy(update={"cash_to_invest": "10"}),
            command_key="changed",
            expected_revision=2,
        )
    )
    assert w.store.current()["current_run_id"] is None and w.store.run(saved.id) == saved
    target = AdvisoryStore(RuntimeBoundary(tmp_path / "restored"))
    restore(target, backup(w.store))
    assert target.run(saved.id) == saved and target.source(p.id) == raw
    with pytest.raises(PersistenceError, match="analysis_id_reused"):
        w.diagnose_lots(command(sale_quantities={p.snapshot.lots[0].id: 1}))


def test_replacement_import_cannot_erase_a_known_ira_acquisition(tmp_path: Path) -> None:
    w = Workspace(AdvisoryStore(RuntimeBoundary(tmp_path / "runtime")))
    raw = (FIXTURES / "combined-stocks.csv").read_bytes()
    original = w.stage_fidelity(
        FidelityUpload(context=context(), source_base64=base64.b64encode(raw).decode())
    ).preview
    assert original
    w.store.select(original.id, "first", 0)
    # The new current source omits other accounts and the manual list is empty.
    replacement = (
        b"\n".join(
            line
            for line in raw.splitlines()
            if not line.startswith((b"000SYNTH002", b"000SYNTH003"))
        )
        + b"\n"
    )
    fresh = w.stage_fidelity(
        FidelityUpload(
            context=context(replacement), source_base64=base64.b64encode(replacement).decode()
        )
    ).preview
    assert fresh
    w.store.select(fresh.id, "second", 1)
    w.configure_lots(
        LotSettingsRequest(settings=settings(), command_key="settings", expected_revision=2)
    )
    saved = w.diagnose_lots(command(expected_revision=3))
    rows = saved.outputs["rows"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    assert "known_acquisition_conflict" in str(rows[0]["blockers"])
    assert len(w.store.selected_snapshots()) == 2
    target = AdvisoryStore(RuntimeBoundary(tmp_path / "restored"))
    restore(target, backup(w.store))
    assert target.run(saved.id) == saved and target.source(original.id) == raw


def test_killed_lot_calculation_resumes_frozen_inputs_after_settings_change(tmp_path: Path) -> None:
    w = Workspace(AdvisoryStore(RuntimeBoundary(tmp_path / "runtime")))
    raw = (FIXTURES / "combined-stocks.csv").read_bytes()
    preview = w.stage_fidelity(
        FidelityUpload(context=context(), source_base64=base64.b64encode(raw).decode())
    ).preview
    assert preview
    w.store.select(preview.id, "select", 0)
    w.configure_lots(
        LotSettingsRequest(settings=settings(), command_key="settings", expected_revision=1)
    )
    code = """
import os,sys
from pathlib import Path
import prosper.workspace as module
from prosper.advisory_store import AdvisoryStore
from prosper.storage import RuntimeBoundary
from prosper.lot_records import LotDiagnosticRequest
from prosper.workspace import Workspace
module.evaluate=lambda *args:os._exit(32)
w=Workspace(AdvisoryStore.existing(RuntimeBoundary(Path(sys.argv[1]))))
w.diagnose_lots(LotDiagnosticRequest(run_id='killed-lot',expected_revision=2,as_of='2026-10-25T00:00:00Z'))
"""
    killed = subprocess.run(
        [sys.executable, "-I", "-c", code, str(w.store.runtime.root), str(ROOT)],
        capture_output=True,
    )
    assert killed.returncode == 32 and killed.stdout == killed.stderr == b""
    frozen = w.store.run("killed-lot")
    assert frozen.status == "running"
    w.configure_lots(
        LotSettingsRequest(
            settings=settings().model_copy(update={"cash_to_invest": "8"}),
            command_key="change",
            expected_revision=2,
        )
    )
    resumed = w.diagnose_lots(command(run_id="killed-lot"))
    assert resumed.inputs == frozen.inputs and resumed.settings == frozen.settings
    assert resumed.outputs["conditional_price_loss_subtotal"] == {"value": 10.0, "reason": None}
    assert w.store.current()["current_run_id"] is None
    # Historical output remains useful, but corrupt required bytes prevent complete recovery.
    with closing(sqlite3.connect(w.store.runtime.path("advisory-v1.sqlite3"))) as connection:
        connection.execute("UPDATE sources SET zlib_bytes=?", (b"corrupt",))
        connection.commit()
    assert w.store.run(resumed.id) == resumed
    with pytest.raises(PersistenceError, match="source_unavailable_or_corrupt"):
        backup(w.store)


def test_future_relationship_assertions_cannot_clear_uncertain_pairs() -> None:
    s, cfg = single()
    cfg = cfg.model_copy(update={"analysis_date": "2026-01-15"})
    relation = Relationship(
        left="fictional-identity:FAAA",
        right="other",
        status="distinct",
        valid_from="2025-01-01",
        valid_through="2027-01-01",
        evidence=Evidence(
            actor="reviewer",
            reference="future assertion",
            effective_at="2026-01-16",
            recorded_at="2026-01-16T00:00:00Z",
        ),
        rationale="unavailable",
    )
    assert any(
        "relationship_unresolved" in reason
        for reason in screen(
            s.securities[0], "sell", cfg, (activity(identity="other"),), (relation,), ()
        )
    )


def test_independent_positions_never_become_lot_sum_defaults() -> None:
    raw = (FIXTURES / "combined-stocks.csv").read_bytes()
    assert source().positions == ()
    ctx = context().model_copy(
        update={
            "independent_positions": (
                IndependentPosition(
                    security_id="security-faaa",
                    quantity=DecimalFact(value="15.000"),
                    source_ref="independent:1",
                ),
                IndependentPosition(
                    security_id="security-fbbb",
                    quantity=DecimalFact(value="3.125"),
                    source_ref="independent:2",
                ),
            )
        }
    )
    s, _ = normalize(raw, ctx)
    assert s and s.observations["selection_blockers"] == []
    mismatch = ctx.model_copy(
        update={
            "independent_positions": (
                ctx.independent_positions[0].model_copy(
                    update={"quantity": DecimalFact(value="14.999")}
                ),
                ctx.independent_positions[1],
            )
        }
    )
    s, _ = normalize(raw, mismatch)
    assert s and "independent_position_quantity_mismatch" in str(
        s.observations["selection_blockers"]
    )
    unmatched = ctx.model_copy(
        update={
            "independent_positions": (
                ctx.independent_positions[0].model_copy(update={"security_id": "unmapped"}),
            )
        }
    )
    s, inspected = normalize(raw, unmatched)
    assert s is None and any(
        i.code == "independent_position_security_unresolved" for i in inspected.issues
    )


def test_cash_funding_sign_does_not_use_a_float_tolerance_or_imported_balance() -> None:
    s, cfg = single(quantity="1", basis="20", mark="10")
    # Float64 rounds this entered fee to 10, but it still requires funding.
    cfg = cfg.model_copy(
        update={
            "sell_fee_per_isolated_order": DecimalFact(value="10.000000000000000001"),
            "sell_discount_bps": DecimalFact(value="0"),
        }
    )
    row = evaluate(s, screening_inputs((s,)), cfg, command()).rows[0]
    assert "isolated_sale_unfunded_under_selected_cash" in row.blockers
    cfg = cfg.model_copy(update={"cash_to_invest": "0.000000000000000001"})
    row = evaluate(s, screening_inputs((s,)), cfg, command()).rows[0]
    assert "isolated_sale_unfunded_under_selected_cash" not in row.blockers
