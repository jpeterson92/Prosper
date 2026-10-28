"""Explicit source-bound holding treatment, without redemption or funding inference."""

import json
from typing import Literal

import polars as pl

from prosper.advisory import supplied_sum
from prosper.advisory_records import (
    CashTreatment,
    DecimalFact,
    Digest,
    Fact,
    ImportSnapshot,
    Lot,
    Position,
    Record,
    Revision,
)
from prosper.record_types import Identifier, Text


class CashTreatmentRequest(Record):
    snapshot_id: Digest
    security_id: Identifier
    kind: Literal["cash", "cash-equivalent"] | None
    command_key: Identifier
    expected_revision: Revision


class CashHolding(Record):
    security_id: Identifier
    ticker: Text
    name: Fact[str]
    source_refs: tuple[Text, ...]
    reported_value: DecimalFact
    currency: Literal["USD"] = "USD"
    treatment: CashTreatment | None


def holdings(snapshot: ImportSnapshot, *, all_holdings: bool = False) -> tuple[CashHolding, ...]:
    """Group the complete source holding inventory; never count lots plus positions twice."""
    rows: list[tuple[str, Lot | Position]] = [
        *(("lot", r) for r in snapshot.lots),
        *(("position", r) for r in snapshot.positions),
    ]
    if not rows:
        return ()
    frame = pl.DataFrame(
        [(r.security_id, kind, r.source_ref, r.reported_value.value) for kind, r in rows],
        orient="row",
        schema={"security": pl.String, "kind": pl.String, "ref": pl.String, "value": pl.String},
    )
    securities = {s.id: s for s in snapshot.securities}
    treatments = {t.security_id: t for t in snapshot.cash_treatments}
    result = []
    for (sid,), group in frame.partition_by("security", as_dict=True, maintain_order=True).items():
        security = securities[sid]
        if (
            not all_holdings
            and security.identity.value is not None
            and security.classification.value == "us-domestic-common-equity"
        ):
            continue
        values = {}
        for kind in ("lot", "position"):
            selected = group.filter(pl.col("kind") == kind).get_column("value").to_list()
            if selected:
                # A small supplied-amount boundary sums reported values exactly;
                # this is not a mark/quantity valuation or model calculation.
                values[kind] = (
                    supplied_sum(tuple(selected)) if all(v is not None for v in selected) else None
                )
        known = [v for v in values.values() if v is not None]
        amount = DecimalFact(value=None, reason="Reported holding value is missing or incomplete")
        if known and len(known) == len(values):
            if len(set(known)) == 1:
                try:
                    amount = DecimalFact(value=str(known[0]))
                except ValueError:
                    amount = DecimalFact(
                        value=None, reason="Reported value exceeds the supported amount boundary"
                    )
            else:
                amount = DecimalFact(
                    value=None, reason="Reported lot and position values contradict each other"
                )
        if group.get_column("ref").n_unique() != group.height:
            amount = DecimalFact(value=None, reason="Ambiguous duplicate holding source locators")
        result.append(
            CashHolding(
                security_id=sid,
                ticker=security.ticker,
                name=security.name,
                source_refs=tuple(sorted(set(group.get_column("ref").to_list()))),
                reported_value=amount,
                treatment=treatments.get(sid),
            )
        )
    return tuple(result)


def apply(
    snapshot: ImportSnapshot, security_id: str, kind: str | None, recorded_at: str
) -> ImportSnapshot:
    row = next((r for r in holdings(snapshot) if r.security_id == security_id), None)
    if row is None:
        raise ValueError("cash_treatment_holding_unavailable")
    previous = next((t for t in snapshot.cash_treatments if t.security_id == security_id), None)
    if (previous.kind if previous else None) == kind:
        return snapshot
    treatments = tuple(t for t in snapshot.cash_treatments if t.security_id != security_id)
    if kind is not None:
        treatment = CashTreatment.model_validate(
            {
                "source_sha256": snapshot.source_sha256,
                "account_id": snapshot.account_id,
                "source_as_of": snapshot.source_as_of,
                "security_id": security_id,
                "source_refs": row.source_refs,
                "kind": kind,
                "recorded_at": recorded_at,
            }
        )
        treatments = (*treatments, treatment)
    document = snapshot.model_dump(mode="json")
    document["cash_treatments"] = [t.model_dump(mode="json") for t in treatments]
    return ImportSnapshot.model_validate_json(json.dumps(document))
