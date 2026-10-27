"""Dated manual worksheets from current checked candidates.

Order edits use the existing final validator, never refit risk or accept client
metrics. Historical reads/exports/recovery do not replay financial calculations.
Plain text and JSON string escaping preserve source text without spreadsheet or
HTML execution. These small boundary records do not need a tabular framework.
"""

import json
import sqlite3
from datetime import datetime
from decimal import Context, Decimal, localcontext
from typing import Literal

import polars as pl
from pydantic import Field, field_validator

from prosper.advisory import decimal_value
from prosper.advisory_records import AnalysisRun, Digest, Fact, Finding, Record, Revision, encode
from prosper.advisory_store import AdvisoryStore, _now
from prosper.candidate_records import (
    BuyOrder,
    CandidateCheck,
    CandidateLimits,
    CandidateRequest,
    Orders,
    SaleOrder,
    SearchMethod,
)
from prosper.candidate_validation import FinalValidator
from prosper.candidate_workflow import CandidateOutput, check_output_links
from prosper.record_types import DateText, Identifier, Text, Timestamp
from prosper.storage import PersistenceError

WARNINGS = (
    "Exploratory unqualified estimate; financial-use authorization is unavailable",
    "No broker order, reservation, fill, funding or deductible-loss guarantee",
    "Verify current broker lot selection, prices, fees, funding and household wash-sale facts",
    "After external activity or material changes, import refreshed holdings "
    "before another suggestion",
)


class WorksheetCheck(Record):
    run_id: Identifier
    expected_revision: Revision
    orders: Orders

    @field_validator("orders", mode="before")
    @classmethod
    def json_orders(cls, value: object) -> object:
        return Orders.model_validate_json(json.dumps(value)) if isinstance(value, dict) else value


class WorksheetSave(WorksheetCheck):
    id: Identifier
    parent_id: Identifier | None
    as_of: Timestamp
    no_external_changes: Literal[True]

    @field_validator("no_external_changes", mode="before")
    @classmethod
    def explicit_review(cls, value: object) -> object:
        if value is not True:
            raise ValueError("explicit_no_external_change_review_required")
        return value


class WorksheetLine(Record):
    side: Literal["sell", "buy"]
    account_id: Identifier
    account_alias: Text
    security_id: Identifier
    ticker: Text
    identity: Text
    lot_id: Identifier | None
    source_ref: Text
    shares: int = Field(ge=1, le=2**53 - 1)
    reference_price: Text
    price_date: DateText
    indicative_price: float


class WorksheetPreview(Record):
    run_id: Identifier
    baseline: CandidateCheck
    check: CandidateCheck
    lines: tuple[WorksheetLine, ...]
    save_allowed: bool


class WorksheetScope(Record):
    security_ids: tuple[Identifier, ...]
    risk_reference: Text
    lookback_sessions: int
    search_method: SearchMethod
    search_outcome: Text
    stopping: Text
    max_states: int
    evaluated_states: int
    domain_states: int | None
    max_candidates: int


class GroupWeight(Record):
    level: Literal["sector", "industry"]
    classification: Fact[str]
    weight: float


class Worksheet(Record):
    kind: Literal["manual-worksheet-v1"] = "manual-worksheet-v1"
    command: WorksheetSave
    saved_at: Timestamp
    snapshot_id: Digest
    source_as_of: DateText | Timestamp
    analysis_date: DateText
    risk_as_of: DateText
    risk_horizon: int
    annualization_sessions: int
    scope: WorksheetScope
    group_weights: tuple[GroupWeight, ...]
    baseline: CandidateCheck
    check: CandidateCheck
    lines: tuple[WorksheetLine, ...]
    limits: CandidateLimits
    cash_to_invest: Text
    assumptions: tuple[Text, ...]
    warnings: tuple[Text, ...]
    exclusions: tuple[Finding, ...]
    findings: tuple[Finding, ...]
    validation_outcome: Literal["checked-estimate", "baseline-diagnostic"]
    financial_use_authorized: Literal[False] = False


def _scope(output: CandidateOutput) -> WorksheetScope:
    assert output.search is not None and output.risk is not None
    result = output.search
    return WorksheetScope(
        security_ids=result.inputs.risk.security_ids,
        risk_reference=result.inputs.risk.reference,
        lookback_sessions=output.risk.sessions,
        search_method=result.method,
        search_outcome=result.outcome,
        stopping=result.stopping,
        max_states=result.inputs.max_states,
        evaluated_states=result.evaluated_states,
        domain_states=result.domain_states,
        max_candidates=result.inputs.max_candidates,
    )


def _groups(request: CandidateRequest, check: CandidateCheck) -> tuple[GroupWeight, ...]:
    if check.metrics is None:
        return ()
    rows = [
        (level, getattr(asset, level).value, getattr(asset, level).reason, weight)
        for level in ("sector", "industry")
        for asset, weight in zip(request.assets, check.metrics.final_weights, strict=True)
    ]
    frame = pl.DataFrame(
        rows,
        schema={
            "level": pl.String,
            "value": pl.String,
            "reason": pl.String,
            "weight": pl.Float64,
        },
        orient="row",
    )
    grouped = frame.group_by("level", "value", "reason", maintain_order=True).agg(
        pl.col("weight").sum()
    )
    return tuple(
        GroupWeight.model_validate_json(
            json.dumps(
                {
                    "level": row[0],
                    "classification": {"value": row[1], "reason": row[2]},
                    "weight": row[3],
                }
            )
        )
        for row in grouped.iter_rows()
    )


def _assumptions(request: CandidateRequest) -> tuple[str, ...]:
    return (
        "No external changes since the selected snapshot: investor-reported, not broker verified",
        request.settings.funding_assumption.value or "Funding assumption unavailable",
        "Sell fees apply once per security order, not once per lot row",
        f"Sell fee USD {request.settings.sell_fee_per_isolated_order.value}; "
        f"sell discount bps {request.settings.sell_discount_bps.value}; "
        f"buy fee USD {request.buy_fee_per_security_order}; "
        f"buy premium bps {request.buy_premium_bps}",
    )


def _warnings(output: CandidateOutput, checked: CandidateCheck) -> tuple[str, ...]:
    assert output.search is not None
    return tuple(
        dict.fromkeys(
            (
                *WARNINGS,
                *output.warnings,
                *output.search.warnings,
                *output.search.exclusions,
                *checked.warnings,
            )
        )
    )


def _candidate(store: AdvisoryStore, identity: str) -> tuple[AnalysisRun, CandidateOutput]:
    run = store.run(identity)
    if run.model_version != "candidate-workflow-v1" or run.status != "partial":
        raise PersistenceError("checked_candidate_required")
    output = CandidateOutput.model_validate_json(json.dumps(run.outputs))
    if output.outcome != "checked" or output.search is None:
        raise PersistenceError("checked_candidate_required")
    frozen = store.candidate_inputs(run.inputs["candidate_inputs"])
    check_output_links(frozen, output)
    for digest in frozen.required_sources:
        store.source_bytes(digest)
    return run, output


def _current(store: AdvisoryStore, run: AnalysisRun, revision: int) -> None:
    state = store.current()
    if state["revision"] != revision or (run.input_revision, run.snapshot_id) != (
        revision,
        state["snapshot_id"],
    ):
        raise PersistenceError("stale_revision")


def _no_trade(orders: Orders) -> bool:
    return not orders.sales and not orders.buys


def _allowed(check: CandidateCheck) -> bool:
    return _no_trade(check.orders) or (
        check.feasible
        and not check.unresolved
        and check.metrics is not None
        and check.metrics.price_loss > 0
        and not check.blockers
    )


def _lines(request: CandidateRequest, check: CandidateCheck) -> tuple[WorksheetLine, ...]:
    if not _allowed(check) or _no_trade(check.orders):
        return ()
    lots = {lot.id: lot for lot in request.snapshot.lots}
    assets = {a.security.id: a.security for a in request.assets}
    marks = {m.security_id: m for m in request.settings.marks}
    result = []
    # Supplied decimal price/spread boundary, bounded by the existing parser.
    # No per-lot fee allocation is invented: sell fees are charged per security.
    with localcontext(Context(prec=2048)):
        orders: tuple[SaleOrder | BuyOrder, ...] = (*check.orders.sales, *check.orders.buys)
        for order in orders:
            side = "sell" if isinstance(order, SaleOrder) else "buy"
            if isinstance(order, SaleOrder):
                lot = lots[order.lot_id]
                sid = lot.security_id
            else:
                lot, sid = None, order.security_id
            security, mark = assets[sid], marks[sid]
            assert mark.price.value is not None and mark.day.value is not None
            spread = (
                request.settings.sell_discount_bps.value
                if side == "sell"
                else request.buy_premium_bps
            )
            assert spread is not None
            factor = Decimal(1) + (-1 if side == "sell" else 1) * decimal_value(spread) / 10000
            value = decimal_value(mark.price.value) * factor
            indicative = float(value)
            if value != 0 and indicative == 0:
                raise PersistenceError("worksheet_price_unrepresentable")
            result.append(
                WorksheetLine(
                    side="sell" if side == "sell" else "buy",
                    account_id=lot.account_id if lot else request.snapshot.account_id,
                    account_alias=request.snapshot.account_alias,
                    security_id=sid,
                    ticker=security.ticker,
                    identity=security.identity.value or "",
                    lot_id=lot.id if lot else None,
                    source_ref=lot.source_ref if lot else security.source_ref,
                    shares=order.shares,
                    reference_price=mark.price.value,
                    price_date=mark.day.value,
                    indicative_price=indicative,
                )
            )
    return tuple(result)


def preview(store: AdvisoryStore, command: WorksheetCheck) -> WorksheetPreview:
    run, output = _candidate(store, command.run_id)
    _current(store, run, command.expected_revision)
    assert output.search is not None
    check = FinalValidator(output.search.inputs).check(command.orders)
    return WorksheetPreview(
        run_id=run.id,
        baseline=output.search.baseline,
        check=check,
        lines=_lines(output.search.inputs, check),
        save_allowed=_allowed(check),
    )


def _read(connection: sqlite3.Connection, identity: str) -> Worksheet:
    row = connection.execute(
        "SELECT run_id,document FROM worksheets WHERE id=?", (identity,)
    ).fetchone()
    if row is None:
        raise PersistenceError("worksheet_missing")
    worksheet = Worksheet.model_validate_json(row[1])
    if (worksheet.command.id, worksheet.command.run_id) != (identity, row[0]):
        raise ValueError("worksheet_links_invalid")
    check_links(worksheet, AdvisoryStore._run(connection, row[0]))
    if (
        worksheet.command.parent_id is not None
        and not connection.execute(
            "SELECT id FROM worksheets WHERE id=? "
            "AND rowid<(SELECT rowid FROM worksheets WHERE id=?)",
            (worksheet.command.parent_id, identity),
        ).fetchone()
    ):
        raise ValueError("worksheet_links_invalid")
    return worksheet


def read(store: AdvisoryStore, identity: str) -> Worksheet:
    with store._connection() as connection:
        return _read(connection, identity)


def save(store: AdvisoryStore, command: WorksheetSave) -> Worksheet:
    # An identical retry returns immutable historical output even after inputs change.
    with store._connection() as connection:
        if connection.execute("SELECT id FROM worksheets WHERE id=?", (command.id,)).fetchone():
            prior = _read(connection, command.id)
            if prior.command != command:
                raise PersistenceError("worksheet_id_reused")
            return prior
    run, output = _candidate(store, command.run_id)
    _current(store, run, command.expected_revision)
    if datetime.fromisoformat(command.as_of) < datetime.fromisoformat(run.as_of):
        raise PersistenceError("worksheet_date_before_analysis")
    assert output.search is not None and output.risk is not None
    request = output.search.inputs
    checked = FinalValidator(request).check(command.orders)
    if not _allowed(checked):
        raise PersistenceError("worksheet_orders_refused")
    saved_at = _now()
    if datetime.fromisoformat(command.as_of) > datetime.fromisoformat(saved_at):
        raise PersistenceError("worksheet_date_future")
    worksheet = Worksheet(
        command=command,
        saved_at=saved_at,
        snapshot_id=run.snapshot_id,
        source_as_of=request.snapshot.source_as_of,
        analysis_date=request.settings.analysis_date,
        risk_as_of=request.risk.as_of,
        risk_horizon=output.risk.horizon,
        annualization_sessions=request.risk.annualization_sessions,
        baseline=output.search.baseline,
        check=checked,
        lines=_lines(request, checked),
        limits=request.limits,
        cash_to_invest=request.settings.cash_to_invest,
        scope=_scope(output),
        group_weights=_groups(request, checked),
        assumptions=_assumptions(request),
        warnings=_warnings(output, checked),
        exclusions=(*request.snapshot.exclusions, *run.exclusions),
        findings=request.snapshot.findings,
        validation_outcome="baseline-diagnostic"
        if _no_trade(command.orders)
        else "checked-estimate",
    )
    check_links(worksheet, run)
    with store._connection(write=True) as connection:
        if connection.execute("SELECT id FROM worksheets WHERE id=?", (command.id,)).fetchone():
            prior = _read(connection, command.id)
            if prior.command != command:
                raise PersistenceError("worksheet_id_reused")
            return prior
        state = store._state(connection)
        if (state["revision"], state["snapshot_id"]) != (run.input_revision, run.snapshot_id):
            raise PersistenceError("stale_revision")
        if store._run(connection, run.id) != run:
            raise PersistenceError("worksheet_run_changed")
        if command.parent_id is not None:
            if command.parent_id == command.id:
                raise PersistenceError("worksheet_parent_invalid")
            _read(connection, command.parent_id)
        connection.execute(
            "INSERT INTO worksheets VALUES (?,?,?)",
            (
                command.id,
                run.id,
                encode(worksheet),
            ),
        )
    return worksheet


def check_links(worksheet: Worksheet, run: AnalysisRun) -> None:
    """Structural historical relationship checks; never validate orders or fit risk."""
    if run.model_version != "candidate-workflow-v1" or run.status != "partial":
        raise ValueError("worksheet_links_invalid")
    output = CandidateOutput.model_validate_json(json.dumps(run.outputs))
    result = output.search
    if output.outcome != "checked" or result is None or output.risk is None:
        raise ValueError("worksheet_links_invalid")
    request = result.inputs
    if (
        worksheet.command.run_id != run.id
        or worksheet.snapshot_id != run.snapshot_id
        or worksheet.command.expected_revision != run.input_revision
        or worksheet.check.orders != worksheet.command.orders
        or not _allowed(worksheet.check)
        or worksheet.baseline != result.baseline
        or worksheet.limits != request.limits
        or worksheet.cash_to_invest != request.settings.cash_to_invest
        or worksheet.source_as_of != request.snapshot.source_as_of
        or worksheet.analysis_date != request.settings.analysis_date
        or worksheet.risk_as_of != request.risk.as_of
        or worksheet.risk_horizon != output.risk.horizon
        or worksheet.annualization_sessions != request.risk.annualization_sessions
        or worksheet.validation_outcome
        not in (
            ("baseline-diagnostic",)
            if _no_trade(worksheet.command.orders)
            else ("checked-estimate",)
        )
        or worksheet.scope != _scope(output)
        or worksheet.exclusions != (*request.snapshot.exclusions, *run.exclusions)
        or worksheet.findings != request.snapshot.findings
        or worksheet.assumptions != _assumptions(request)
        or worksheet.check.warnings != result.baseline.warnings
        or worksheet.warnings != _warnings(output, worksheet.check)
        or not datetime.fromisoformat(run.as_of)
        <= datetime.fromisoformat(worksheet.command.as_of)
        <= datetime.fromisoformat(worksheet.saved_at)
    ):
        raise ValueError("worksheet_links_invalid")
    orders: tuple[SaleOrder | BuyOrder, ...] = (
        *worksheet.command.orders.sales,
        *worksheet.command.orders.buys,
    )
    if len(orders) != len(worksheet.lines):
        raise ValueError("worksheet_links_invalid")
    lots = {lot.id: lot for lot in request.snapshot.lots}
    assets = {a.security.id: a.security for a in request.assets}
    marks = {m.security_id: m for m in request.settings.marks}
    for line, order in zip(worksheet.lines, orders, strict=True):
        selling = isinstance(order, SaleOrder)
        if isinstance(order, SaleOrder):
            lot = lots.get(order.lot_id)
            if lot is None:
                raise ValueError("worksheet_links_invalid")
            sid = lot.security_id
        else:
            lot, sid = None, order.security_id
        security = assets.get(sid)
        mark = marks.get(sid)
        if (
            security is None
            or mark is None
            or (
                line.side != ("sell" if selling else "buy")
                or line.shares != order.shares
                or line.lot_id != (lot.id if lot else None)
                or line.security_id != sid
                or line.account_id != (lot.account_id if lot else request.snapshot.account_id)
                or line.account_alias != request.snapshot.account_alias
                or line.ticker != security.ticker
                or line.identity != security.identity.value
                or line.source_ref != (lot.source_ref if lot else security.source_ref)
                or line.reference_price != mark.price.value
                or line.price_date != mark.day.value
            )
        ):
            raise ValueError("worksheet_links_invalid")
    expected_groups = (
        {
            (level, getattr(asset, level).value, getattr(asset, level).reason)
            for level in ("sector", "industry")
            for asset in request.assets
        }
        if worksheet.check.metrics is not None
        else set()
    )
    actual_groups = [
        (g.level, g.classification.value, g.classification.reason) for g in worksheet.group_weights
    ]
    if set(actual_groups) != expected_groups or len(actual_groups) != len(expected_groups):
        raise ValueError("worksheet_links_invalid")
    metrics = worksheet.check.metrics
    if metrics is not None and (
        len(metrics.final_quantities) != len(request.assets)
        or len(metrics.final_weights) != len(request.assets)
    ):
        raise ValueError("worksheet_links_invalid")


def export_text(worksheet: Worksheet) -> bytes:
    """Format saved facts only; all source strings stay quoted and escaped."""

    def quoted(value: object) -> str:
        return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True)

    rows = [
        "PROSPER - DATED MANUAL WORKSHEET",
        "Historical estimate. Verify current broker facts before any manual action.",
        "Financial-use authorization: unavailable.",
        "Quantity edits receive final checks; they are not reoptimized or claimed optimal.",
        "Worksheet: " + quoted(worksheet.command.id),
        "Candidate run: " + quoted(worksheet.command.run_id),
        "Parent worksheet: " + quoted(worksheet.command.parent_id),
        "Worksheet as of: " + quoted(worksheet.command.as_of),
        "Saved at: " + quoted(worksheet.saved_at),
        "Snapshot: " + quoted(worksheet.snapshot_id),
        "Source as of: " + quoted(worksheet.source_as_of),
        "Analysis date: " + quoted(worksheet.analysis_date),
        "Risk cutoff / horizon / annualization: "
        + quoted(
            [
                worksheet.risk_as_of,
                worksheet.risk_horizon,
                worksheet.annualization_sessions,
            ]
        ),
        "Validation scope: " + quoted(worksheet.validation_outcome),
        "ORIGINAL CANDIDATE MODEL / UNIVERSE / SEARCH SCOPE: "
        + quoted(worksheet.scope.model_dump(mode="json")),
        "GROUP WEIGHTS: " + quoted([g.model_dump(mode="json") for g in worksheet.group_weights]),
        "Selected additional cash USD: " + quoted(worksheet.cash_to_invest),
        "NO-TRADE BASELINE: " + quoted(worksheet.baseline.model_dump(mode="json")),
        "FINAL CHECK: " + quoted(worksheet.check.model_dump(mode="json")),
        "INDICATIVE MANUAL LINES (not submitted orders):",
        *(quoted(line.model_dump(mode="json")) for line in worksheet.lines),
        "NO TRADE"
        if not worksheet.lines
        else "Whole shares only; sell fees apply per security order.",
        "SELECTED LIMITS: " + quoted(worksheet.limits.model_dump(mode="json")),
        "ASSUMPTIONS:",
        *(quoted(a) for a in worksheet.assumptions),
        "WARNINGS:",
        *(quoted(w) for w in worksheet.warnings),
        "SOURCE FINDINGS:",
        *(quoted(e.model_dump(mode="json")) for e in worksheet.findings),
        "EXCLUSIONS:",
        *(quoted(e.model_dump(mode="json")) for e in worksheet.exclusions),
    ]
    return ("\n".join(rows) + "\n").encode("utf-8")
