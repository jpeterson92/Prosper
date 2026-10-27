"""Current worksheet financial boundaries, source references, retries and recovery."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from prosper import advisory_store, worksheets
from prosper.advisory_recovery import backup, restore
from prosper.candidate_records import Orders
from prosper.candidate_validation import FinalValidator
from prosper.storage import PersistenceError
from prosper.worksheets import WorksheetCheck, WorksheetSave
from tests.test_candidate_workflow import command, seed, service, stub, wait


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    w = service(tmp_path / "source")
    seed(w)
    stub(monkeypatch, "checked")
    w.start_candidate(command())
    assert wait(w).outputs["outcome"] == "checked"
    yield w
    w.candidates.close()


def orders(sales: int = 2, buys: int = 0) -> Orders:
    return Orders.model_validate_json(
        json.dumps(
            {
                "sales": [{"lot_id": "lot-a", "shares": sales}] if sales else [],
                "buys": [{"security_id": "security-fbbb", "shares": buys}] if buys else [],
            }
        )
    )


def save_command(**changes: Any) -> WorksheetSave:
    return WorksheetSave(
        id="worksheet",
        parent_id=None,
        run_id="candidate",
        expected_revision=4,
        as_of="2026-10-26T00:00:00Z",
        no_external_changes=True,
        orders=orders(),
    ).model_copy(update=changes)


def test_independently_reasoned_partial_sale_and_no_trade_comparison(workspace: Any) -> None:
    s = workspace.store
    # 2.5 source shares with total basis 30, reference mark 10: sell 2 =>
    # allocated basis 24, price loss 4, cash 20, remainder .5, NAV 25.
    viewed = worksheets.preview(
        s, WorksheetCheck(run_id="candidate", expected_revision=4, orders=orders())
    )
    m = viewed.check.metrics
    assert viewed.save_allowed and m and viewed.baseline.metrics
    assert (m.price_loss, m.final_cash, m.final_nav, m.final_quantities) == (4, 20, 25, (0.5, 0))
    assert viewed.baseline.metrics.price_loss == 0 and viewed.baseline.metrics.final_cash == 0
    saved = worksheets.save(s, save_command())
    line = saved.lines[0]
    assert (line.lot_id, line.security_id, line.shares) == ("lot-a", "security-faaa", 2)
    assert line.account_id == s.snapshot(saved.snapshot_id).lots[0].account_id
    assert line.source_ref == s.snapshot(saved.snapshot_id).lots[0].source_ref
    assert saved.scope.security_ids == ("security-faaa", "security-fbbb")
    assert saved.scope.lookback_sessions == 1260 and saved.scope.max_states == 100
    for level in ("sector", "industry"):
        assert sum(g.weight for g in saved.group_weights if g.level == level) == pytest.approx(0.2)
    assert (line.reference_price, line.indicative_price, line.price_date) == (
        "10",
        10,
        "2026-10-23",
    )
    revised = worksheets.save(
        s, save_command(id="revision", parent_id="worksheet", orders=orders(1))
    )
    assert revised.check.metrics and revised.check.metrics.price_loss == 2
    assert revised.check.metrics.final_cash == 10
    assert worksheets.read(s, "worksheet") == saved
    baseline = worksheets.save(s, save_command(id="baseline", orders=orders(0)))
    assert baseline.validation_outcome == "baseline-diagnostic" and not baseline.lines
    assert b"NO TRADE" in worksheets.export_text(baseline)
    assert s.current()["current_run_id"] == "candidate"


@pytest.mark.parametrize(
    "sale,buy,reason",
    [
        (3, 0, "sale_exceeds_supplied_quantity"),
        (1, 2, "cash"),
        (0, 1, "cash"),
    ],
)
def test_invalid_edits_report_refusal_and_never_save(
    workspace: Any,
    sale: int,
    buy: int,
    reason: str,
) -> None:
    proposed = orders(sale, buy)
    p = worksheets.preview(
        workspace.store,
        WorksheetCheck(
            run_id="candidate",
            expected_revision=4,
            orders=proposed,
        ),
    )
    assert not p.save_allowed and any(reason in b for b in p.check.blockers)
    with pytest.raises(PersistenceError, match="worksheet_orders_refused"):
        worksheets.save(workspace.store, save_command(orders=proposed))
    assert workspace.store.catalog()["worksheets"] == []


@pytest.mark.parametrize("value", [False, 1, "true", None])
def test_external_change_review_cannot_be_coerced(value: Any) -> None:
    d = save_command().model_dump(mode="json")
    d["no_external_changes"] = value
    with pytest.raises(ValueError):
        WorksheetSave.model_validate_json(json.dumps(d))


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"as_of": "2026-10-24T00:00:00Z"}, "worksheet_date_before_analysis"),
        ({"as_of": "2099-01-01T00:00:00Z"}, "worksheet_date_future"),
        ({"parent_id": "worksheet"}, "worksheet_parent_invalid"),
        ({"parent_id": "missing-parent"}, "worksheet_missing"),
    ],
)
def test_dates_and_parent_identity_refuse_without_partial_save(
    workspace: Any,
    changes: dict[str, Any],
    reason: str,
) -> None:
    with pytest.raises(PersistenceError, match=reason):
        worksheets.save(workspace.store, save_command(**changes))
    assert workspace.store.catalog()["worksheets"] == []


def test_lost_response_identical_retry_conflict_and_two_window_insert(workspace: Any) -> None:
    s = workspace.store
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: worksheets.save(s, save_command()), range(2)))
    assert results[0] == results[1] and len(s.catalog()["worksheets"]) == 1
    with pytest.raises(PersistenceError, match="worksheet_id_reused"):
        worksheets.save(s, save_command(orders=orders(1)))
    s.configure({"new-window": True}, "other-window", 4)
    assert worksheets.save(s, save_command()) == results[0]
    with pytest.raises(PersistenceError, match="stale_revision"):
        worksheets.save(s, save_command(id="stale"))


def test_revision_race_and_transaction_fault_leave_no_partial_worksheet(
    workspace: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = FinalValidator.check

    def race(self: Any, proposed: Orders) -> Any:
        result = original(self, proposed)
        workspace.store.configure({"new-window": True}, "race", 4)
        return result

    monkeypatch.setattr(FinalValidator, "check", race)
    with pytest.raises(PersistenceError, match="stale_revision"):
        worksheets.save(workspace.store, save_command())
    assert workspace.store.catalog()["worksheets"] == []
    monkeypatch.setattr(FinalValidator, "check", original)


def test_failed_commit_rolls_back(workspace: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(connection: Any) -> None:
        raise OSError("synthetic commit fault")

    monkeypatch.setattr(advisory_store, "_before_commit", fail)
    with pytest.raises(PersistenceError):
        worksheets.save(workspace.store, save_command())
    monkeypatch.undo()
    assert workspace.store.catalog()["worksheets"] == []


def test_historical_read_export_and_recovery_never_recalculate(
    workspace: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved = worksheets.save(workspace.store, save_command())
    expected = worksheets.export_text(saved)
    revised = worksheets.save(
        workspace.store,
        save_command(
            id="revised",
            parent_id="worksheet",
            orders=orders(1),
        ),
    )
    workspace.store.clear_history_cache("clear", 4)
    monkeypatch.setattr(FinalValidator, "check", lambda *a: pytest.fail("recalculation"))
    target = service(tmp_path / "restored")
    restore(target.store, backup(workspace.store))
    assert worksheets.read(target.store, "worksheet") == saved
    assert worksheets.read(target.store, "revised") == revised
    assert worksheets.save(target.store, save_command()) == saved
    assert worksheets.export_text(worksheets.read(target.store, "worksheet")) == expected
    assert not saved.financial_use_authorized
    # Breaking a source relationship refuses backup; no numerical replay repairs it.
    with target.store._connection(write=True) as c:
        d = saved.model_dump(mode="json")
        d["lines"][0]["account_id"] = "invented-account"
        c.execute("UPDATE worksheets SET document=? WHERE id=?", (json.dumps(d), "worksheet"))
    with pytest.raises((PersistenceError, ValueError)):
        backup(target.store)
    with pytest.raises((PersistenceError, ValueError)):
        worksheets.read(target.store, "worksheet")


def test_plain_text_export_quotes_formulas_html_newlines_and_control_characters(
    workspace: Any,
) -> None:
    saved = worksheets.save(workspace.store, save_command())
    unsafe = '=HYPERLINK("https://fictional.invalid")\n<script>alert(1)</script>\x00\t+SUM(1)'
    line = saved.lines[0].model_copy(update={"ticker": unsafe, "source_ref": unsafe})
    exported = worksheets.export_text(saved.model_copy(update={"lines": (line,)})).decode()
    assert json.dumps(unsafe, ensure_ascii=True) in exported
    assert "\x00" not in exported and "\n<script>" not in exported
    assert "Financial-use authorization: unavailable" in exported
    assert "funding" in exported and "refreshed holdings" in exported
    assert saved.lines[0].ticker != unsafe  # Formatting did not mutate the source record.
