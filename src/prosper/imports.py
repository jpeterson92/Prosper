"""Synthetic atomic activation, historical event review and durable command outcomes."""

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from typing import cast

from prosper.bundle_schema import CANONICALIZATION_VERSION
from prosper.persistence import (
    CheckpointStore,
    PersistenceError,
    StoredCheckpoint,
    _check_recorded_time,
)
from prosper.previews import PreviewService, _now

COMMAND_SCOPE = "synthetic-portfolio-import-v1"
PAYLOAD_VERSION = "activate-preview-v1"
OUTCOMES = frozenset(
    (
        "committed",
        "duplicate",
        "stale_generation",
        "preview_rejected",
        "preview_invalid",
        "identity_review_required",
        "source_conflict",
    )
)


class ImportError(PersistenceError):
    """Safe bounded code; business rejections are durable receipts instead."""


@dataclass(frozen=True)
class CommandReceipt:
    scope: str
    command_key: str
    payload_version: str
    payload_sha256: str
    preview_sha256: str
    expected_generation: int
    outcome: str
    generation: int
    activation_generation: int | None
    recorded_at: str


@dataclass(frozen=True)
class ActiveState:
    generation: int
    checkpoint: StoredCheckpoint | None


def _key(key: str) -> None:
    if not isinstance(key, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", key) is None:
        raise ImportError("invalid_command_key")


def _payload(identity: str, expected: int) -> str:
    # Evidence identity is the preview identity: SHA-256 of the retained original bytes.
    text = json.dumps([COMMAND_SCOPE, PAYLOAD_VERSION, identity, expected], separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def _decode(row: tuple[object, ...]) -> CommandReceipt:
    if (
        len(row) != 10
        or any(not isinstance(row[i], str) for i in (0, 1, 2, 3, 4, 6, 9))
        or any(type(row[i]) is not int or cast(int, row[i]) < 0 for i in (5, 7))
        or row[0] != COMMAND_SCOPE
        or row[2] != PAYLOAD_VERSION
        or row[6] not in OUTCOMES
    ):
        raise ImportError("stored_command_invalid")
    receipt = CommandReceipt(
        *cast(tuple[str, str, str, str, str, int, str, int, int | None, str], row)
    )
    _key(receipt.command_key)
    PreviewService._identity(receipt.preview_sha256)
    _check_recorded_time(receipt.recorded_at)
    if receipt.payload_sha256 != _payload(receipt.preview_sha256, receipt.expected_generation):
        raise ImportError("stored_command_invalid")
    target = receipt.activation_generation
    if receipt.outcome in ("committed", "duplicate"):
        if type(target) is not int or not 1 <= target <= receipt.generation:
            raise ImportError("stored_command_invalid")
        if receipt.outcome == "committed":
            valid = (
                receipt.generation == receipt.expected_generation + 1
                and target == receipt.generation
            )
        else:
            valid = receipt.generation == receipt.expected_generation
    else:
        valid = target is None and (
            (receipt.generation != receipt.expected_generation)
            if receipt.outcome == "stale_generation"
            else (receipt.generation == receipt.expected_generation)
        )
    if not valid:
        raise ImportError("stored_command_invalid")
    return receipt


def _before_activation_commit(connection: sqlite3.Connection) -> None:
    """Failure seam after actual coordinated writes, never a user callback."""


def _review(history: list[StoredCheckpoint], candidate: StoredCheckpoint) -> str | None:
    """Rebuild accepted event history from verified evidence; never from staged input."""
    prior_events: dict[tuple[str, str, str, str], str] = {}
    snapshots: dict[tuple[str, str, str, str], str] = {}
    accounts: dict[str, str] = {}
    securities: dict[str, str] = {}
    first = (
        history[0].inspection.source.document if history else candidate.inspection.source.document
    )
    traded = (
        history[0].inspection.traded_account_id
        if history
        else candidate.inspection.traded_account_id
    )
    for stored in [*history, candidate]:
        inspection = stored.inspection
        doc = inspection.source.document
        if (
            doc.metadata.profile_id != first.metadata.profile_id
            or doc.metadata.source_id != first.metadata.source_id
            or inspection.traded_account_id != traded
        ):
            return "identity_review_required"
        snapshot_key = (
            doc.metadata.profile_id,
            doc.metadata.source_id,
            doc.metadata.bundle_id,
            doc.metadata.cutoff,
        )
        snapshot = json.dumps(
            {
                family: [row.model_dump(mode="json") for row in sorted(records, key=lambda r: r.id)]
                for family, records in doc.record_groups()
                if family in ("positions", "lots", "cash", "quotes")
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        if snapshot_key in snapshots and snapshots[snapshot_key] != snapshot:
            return "source_conflict"
        snapshots[snapshot_key] = snapshot
        for account in doc.accounts:
            if account.id in accounts and accounts[account.id] != account.source_ref:
                return "identity_review_required"
            accounts[account.id] = account.source_ref
        for security in doc.securities:
            mapping = json.dumps(
                [
                    security.source_ref,
                    security.issuer_id.model_dump(),
                    security.share_class_id.model_dump(),
                ],
                sort_keys=True,
                separators=(",", ":"),
            )
            if security.id in securities and securities[security.id] != mapping:
                return "identity_review_required"
            securities[security.id] = mapping
        for event in doc.activity:
            key = (doc.metadata.profile_id, doc.metadata.source_id, event.account_id, event.id)
            normalized = json.dumps(
                [
                    CANONICALIZATION_VERSION,
                    doc.metadata.semantics_version,
                    event.model_dump(mode="json"),
                ],
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            if key in prior_events and prior_events[key] != normalized:
                return "source_conflict"
            prior_events[key] = normalized
    return None


class ImportService:
    """One reviewed synthetic portfolio. Receipts describe original outcomes, not current state."""

    def __init__(self, store: CheckpointStore) -> None:
        self.store = store
        self.previews = PreviewService(store)

    def _history(self, connection: sqlite3.Connection) -> list[StoredCheckpoint]:
        history: list[StoredCheckpoint] = []
        for generation, identity, recorded in connection.execute(
            "SELECT * FROM import_activations ORDER BY generation"
        ).fetchall():
            if (
                type(generation) is not int
                or generation != len(history) + 1
                or not isinstance(recorded, str)
            ):
                raise ImportError("stored_activation_invalid")
            moment = _check_recorded_time(recorded)
            preview = self.previews._row(connection, identity)
            if preview.state != "committed" or moment < _check_recorded_time(preview.recorded_at):
                raise ImportError("stored_activation_invalid")
            row = connection.execute(
                "SELECT * FROM checkpoints WHERE raw_sha256=?", (identity,)
            ).fetchone()
            if row is None:
                raise ImportError("active_checkpoint_missing")
            stored = self.store._load(cast(tuple[object, ...], row))
            receipts = connection.execute(
                "SELECT * FROM import_commands WHERE outcome='committed' "
                "AND activation_generation=?",
                (generation,),
            ).fetchall()
            if len(receipts) != 1:
                raise ImportError("activation_receipt_missing")
            receipt = _decode(receipts[0])
            if (
                receipt.preview_sha256 != identity
                or receipt.generation != generation
                or receipt.recorded_at != recorded
            ):
                raise ImportError("stored_activation_invalid")
            history.append(stored)
        committed = {
            row[0]
            for row in connection.execute(
                "SELECT raw_sha256 FROM import_previews WHERE state='committed'"
            )
        }
        if committed != {stored.receipt.raw_sha256 for stored in history}:
            raise ImportError("stored_activation_invalid")
        if history and _review(history[:-1], history[-1]) is not None:
            raise ImportError("stored_activation_conflict")
        return history

    def current(self) -> ActiveState:
        try:
            with closing(self.store._connect()) as connection:
                connection.execute("BEGIN")
                self.store._check_schema(connection)
                history = self._history(connection)
                return ActiveState(len(history), history[-1] if history else None)
        except sqlite3.Error:
            raise ImportError("active_read_failed") from None

    def commit(self, identity: str, command_key: str, expected_generation: int) -> CommandReceipt:
        PreviewService._identity(identity)
        _key(command_key)
        if type(expected_generation) is not int or not 0 <= expected_generation < 2**63 - 1:
            raise ImportError("invalid_expected_generation")
        payload = _payload(identity, expected_generation)
        try:
            with closing(self.store._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    self.store._check_schema(connection)
                    old = connection.execute(
                        "SELECT * FROM import_commands WHERE scope=? AND command_key=?",
                        (COMMAND_SCOPE, command_key),
                    ).fetchone()
                    if old is not None:
                        receipt = _decode(old)
                        if receipt.payload_sha256 != payload:
                            raise ImportError("command_payload_mismatch")
                    preview = self.previews._row(connection, identity)
                    history = self._history(connection)
                    generation = len(history)
                    if old is not None:
                        if receipt.generation > generation:
                            raise ImportError("stored_command_invalid")
                        if receipt.activation_generation is not None and (
                            history[receipt.activation_generation - 1].receipt.raw_sha256
                            != identity
                        ):
                            raise ImportError("stored_command_invalid")
                        connection.commit()
                        return receipt
                    target = None
                    if expected_generation != generation:
                        outcome = "stale_generation"
                    elif preview.state == "rejected":
                        outcome = "preview_rejected"
                    elif preview.inspection is None or preview.inspection.validated is None:
                        outcome = "preview_invalid"
                    else:
                        target = next(
                            (
                                i + 1
                                for i, stored in enumerate(history)
                                if stored.receipt.raw_sha256 == identity
                            ),
                            None,
                        )
                        if target is not None:
                            outcome = "duplicate"
                        else:
                            # The immutable append shares this transaction. A business
                            # conflict must not leave even an unactivated checkpoint row.
                            candidate = StoredCheckpoint(
                                0, preview.recorded_at, preview.receipt, preview.inspection
                            )
                            outcome = _review(history, candidate) or "committed"
                            if outcome == "committed":
                                self.store._append_in_transaction(
                                    connection, preview.inspection, preview.receipt
                                )
                                generation += 1
                                target = generation
                                connection.execute(
                                    "UPDATE import_previews SET state='committed' "
                                    "WHERE raw_sha256=?",
                                    (identity,),
                                )
                    recorded = _now()
                    if outcome == "committed":
                        if _check_recorded_time(recorded) < _check_recorded_time(
                            preview.recorded_at
                        ):
                            raise ImportError("activation_time_invalid")
                        connection.execute(
                            "INSERT INTO import_activations VALUES (?, ?, ?)",
                            (generation, identity, recorded),
                        )
                    values = (
                        COMMAND_SCOPE,
                        command_key,
                        PAYLOAD_VERSION,
                        payload,
                        identity,
                        expected_generation,
                        outcome,
                        generation,
                        target,
                        recorded,
                    )
                    connection.execute(
                        "INSERT INTO import_commands VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values
                    )
                    _before_activation_commit(connection)
                    receipt = _decode(values)
                    # Recheck real referenced evidence and relational state after writes.
                    self.previews._row(connection, identity)
                    self._history(connection)
                    self.store._guard_paths()
                    connection.commit()
                    return receipt
                except BaseException:
                    connection.rollback()
                    raise
        except sqlite3.Error:
            raise ImportError("activation_write_failed") from None
