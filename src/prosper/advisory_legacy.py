"""Explicit read/export bridge. No legacy evidence or selected state is rewritten."""

import hashlib
import json
from typing import cast

from pydantic import JsonValue

from prosper.advisory_records import (
    Cash,
    DecimalFact,
    Fact,
    Finding,
    ImportSnapshot,
    Lot,
    Position,
    Security,
)
from prosper.bundle_schema import DateText
from prosper.bundle_schema import Fact as LegacyFact
from prosper.exact import ExactValue
from prosper.persistence import CheckpointStore, PersistenceError


def export_checkpoint(store: CheckpointStore, identity: str) -> bytes:
    """Exact original bytes through the unchanged validated legacy reader."""
    return store.evidence.read(store.get(identity).receipt)


def map_checkpoint(store: CheckpointStore, identity: str) -> ImportSnapshot:
    """Map a validated current snapshot; observations never reconstruct holdings.

    Unsupported legacy objects (history, registry, backups, failed previews) must
    use their existing readers/export paths. This bridge only takes checkpoints.
    Mapping is explicit staging material, never automatic activation.
    """
    stored = store.get(identity)
    inspection = stored.inspection
    document = inspection.source.document
    account = next((a for a in document.accounts if a.id == inspection.traded_account_id), None)
    if account is None:
        raise PersistenceError("legacy_traded_account_missing")

    def decimal(fact: LegacyFact[ExactValue]) -> DecimalFact:
        value = fact.value
        return (
            DecimalFact(value=value.original_text)
            if isinstance(value, ExactValue)
            else DecimalFact(value=None, reason=fact.reason)
        )

    def text(fact: LegacyFact[str]) -> Fact[str]:
        return Fact[str](value=fact.value, reason=fact.reason)

    securities = tuple(
        Security(
            id=s.id,
            source_ref=s.source_ref,
            ticker=s.ticker,
            identity=Fact[str](value=json.dumps([s.issuer_id.value, s.share_class_id.value]))
            if s.issuer_id.value is not None and s.share_class_id.value is not None
            else Fact[str](value=None, reason="legacy issuer/share-class identity incomplete"),
            classification=text(s.security_type),
        )
        for s in document.securities
    )
    lots = tuple(
        Lot(
            id=lot.id,
            account_id=lot.account_id,
            security_id=lot.security_id,
            source_ref=lot.source_ref,
            quantity=decimal(lot.quantity),
            total_basis=decimal(lot.basis),
            acquired=Fact[DateText](value=lot.acquired.value, reason=lot.acquired.reason),
            term=Fact[str](value=None, reason="term not inferred by legacy mapping"),
        )
        for lot in document.lots
        if lot.account_id == account.id
    )
    positions = tuple(
        Position(
            id=p.id,
            account_id=p.account_id,
            security_id=p.security_id,
            source_ref=p.source_ref,
            quantity=decimal(p.quantity),
        )
        for p in document.positions
        if p.account_id == account.id
    )
    cash = tuple(
        Cash(
            id=f"cash:{hashlib.sha256(c.id.encode()).hexdigest()}:{kind}",
            account_id=c.account_id,
            source_ref=c.source_ref,
            amount=decimal(getattr(c, kind)),
            kind=kind,
        )
        for c in document.cash
        if c.account_id == account.id
        for kind in ("settled", "available", "unsettled")
    )
    exclusions = tuple(
        Finding(
            code="monitor_only",
            locator=f"{family}/{row.id}",
            reason="outside selected traded account; retained in original source",
        )
        for family, rows in document.record_groups()
        for row in rows
        if hasattr(row, "account_id")
        and isinstance(row.account_id, str)
        and row.account_id != account.id
    )
    return ImportSnapshot(
        source_type="legacy-synthetic-checkpoint-v1",
        source_name=document.metadata.bundle_id,
        source_sha256=stored.receipt.raw_sha256,
        account_id=account.id,
        account_alias=account.alias,
        account_scope=f"profile:{document.metadata.profile_id};account:{account.source_ref}",
        source_as_of=document.metadata.cutoff,
        securities=securities,
        lots=lots,
        positions=positions,
        cash=cash,
        exclusions=exclusions,
        observations=cast(
            dict[str, JsonValue],
            {
                "legacy_metadata": document.metadata.model_dump(mode="json"),
                "accounts": [a.model_dump(mode="json") for a in document.accounts],
                "securities": [s.model_dump(mode="json") for s in document.securities],
                "activity": [a.model_dump(mode="json") for a in document.activity],
                "quotes": [q.model_dump(mode="json") for q in document.quotes],
                "coverage": [c.model_dump(mode="json") for c in document.coverage],
                "lot_facts": [lot.model_dump(mode="json") for lot in document.lots],
            },
        ),
        findings=(
            Finding(
                code="legacy_mapping",
                locator="source",
                reason="Current snapshot only; activity is screening input, not reapplied. "
                "No tax, risk, broker or execution qualification is inferred.",
            ),
        ),
    )
