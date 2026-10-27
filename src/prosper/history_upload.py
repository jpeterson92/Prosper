"""Bounded immutable staging and atomic publication of complete history manifests.

Pending originals are current workspace work, not active input or disposable
scratch. SQLite owns their recovery; explicit discard never removes active data.
"""

import base64
import hashlib
import json
import sqlite3
from typing import cast

from pydantic import JsonValue

from prosper.advisory_records import encode
from prosper.advisory_store import AdvisoryStore
from prosper.api_contracts import HistoryManifest, HistoryPart, HistoryPartReceipt
from prosper.history import HistoryBatch
from prosper.history_refresh import check_parts
from prosper.history_table import decompress
from prosper.storage import MAX_BYTES, PersistenceError

MAX_PARTS = 500
MAX_ROWS = 650000
MAX_ORIGINALS = 64 * 1024 * 1024


def decode(part: HistoryPart) -> tuple[HistoryBatch, bytes]:
    try:
        raw = decompress(base64.b64decode(part.source_zlib_base64, validate=True), MAX_BYTES)
    except ValueError:
        raise PersistenceError("invalid_history_source_encoding") from None
    if not raw or hashlib.sha256(raw).hexdigest() != part.batch.source_sha256:
        raise PersistenceError("source_checksum_or_size_invalid")
    return part.batch, raw


def validate(parts: tuple[tuple[HistoryBatch, bytes], ...]) -> None:
    if not 1 <= len(parts) <= MAX_PARTS:
        raise PersistenceError("invalid_history_parts")
    if len({b.source_sha256 for b, _ in parts}) != len(parts):
        raise PersistenceError("duplicate_history_source_part")
    if sum(b.rows.row_count for b, _ in parts) > MAX_ROWS:
        raise PersistenceError("history_observation_budget_exceeded")
    if sum(len(raw) for _, raw in parts) > MAX_ORIGINALS:
        raise PersistenceError("history_source_total_size_limit")
    try:
        check_parts(tuple(batch for batch, _ in parts))
    except ValueError:
        raise PersistenceError("contradictory_history_parts") from None


def read_part(connection: sqlite3.Connection, identity: str) -> tuple[HistoryBatch, bytes]:
    rows = connection.execute(
        "SELECT source_sha256,document FROM history_parts WHERE id=? UNION ALL "
        "SELECT source_sha256,document FROM history_batches WHERE id=?",
        (identity, identity),
    ).fetchall()
    if not rows:
        raise PersistenceError("history_part_missing")
    if any(row != rows[0] for row in rows):
        raise PersistenceError("history_part_corrupt")
    digest, document = rows[0]
    batch = HistoryBatch.model_validate_json(document)
    raw = AdvisoryStore._source(connection, digest)
    if (
        hashlib.sha256(encode(batch).encode()).hexdigest() != identity
        or batch.source_sha256 != digest
        or len(raw) > MAX_BYTES
    ):
        raise PersistenceError("history_part_corrupt")
    return batch, raw


def stage(store: AdvisoryStore, part: HistoryPart) -> HistoryPartReceipt:
    batch, raw = decode(part)
    if batch.rows.row_count > MAX_ROWS:
        raise PersistenceError("history_observation_budget_exceeded")
    document = encode(batch)
    identity = hashlib.sha256(document.encode()).hexdigest()
    with store._connection(write=True) as connection:
        exists = connection.execute(
            "SELECT id FROM history_parts WHERE id=? UNION ALL "
            "SELECT id FROM history_batches WHERE id=?",
            (identity, identity),
        ).fetchone()
        if exists:
            if read_part(connection, identity) != (batch, raw):
                raise PersistenceError("history_part_corrupt")
        else:
            count, known, present, rows, size = connection.execute(
                "SELECT count(*),count(json_extract(p.document,'$.rows.row_count')),"
                "count(s.sha256),coalesce(sum(json_extract(p.document,'$.rows.row_count')),0),"
                "coalesce(sum(s.original_size),0) FROM history_parts p "
                "LEFT JOIN sources s ON s.sha256=p.source_sha256"
            ).fetchone()
            if known != count or present != count:
                raise PersistenceError("history_part_corrupt")
            if (
                count + 1 > MAX_PARTS
                or rows + batch.rows.row_count > MAX_ROWS
                or size + len(raw) > MAX_ORIGINALS
            ):
                raise PersistenceError("pending_history_budget_exceeded")
            store._retain_source(connection, batch.source_sha256, raw)
            connection.execute(
                "INSERT INTO history_parts VALUES (?,?,?)",
                (identity, batch.source_sha256, document),
            )
    return HistoryPartReceipt(id=identity, batch=batch)


def preview(store: AdvisoryStore, manifest: HistoryManifest) -> HistoryManifest:
    with store._connection() as connection:
        validate(tuple(read_part(connection, identity) for identity in manifest.part_ids))
    return manifest


def activate(store: AdvisoryStore, manifest: HistoryManifest) -> dict[str, JsonValue]:
    payload = encode({"history_manifest": manifest.model_dump(mode="json")})
    with store._connection(write=True) as connection:
        prior = connection.execute(
            "SELECT payload,result FROM commands WHERE key=?", (manifest.command_key,)
        ).fetchone()
        if prior:
            if prior[0] != payload:
                raise PersistenceError("command_key_reused")
            return cast(dict[str, JsonValue], json.loads(prior[1]))
        state = store._state(connection)
        outcome = "stale_revision"
        if state["revision"] == manifest.expected_revision:
            parts = tuple(read_part(connection, identity) for identity in manifest.part_ids)
            validate(parts)
            changed = False
            for identity, (batch, _) in zip(manifest.part_ids, parts, strict=True):
                if not connection.execute(
                    "SELECT id FROM history_batches WHERE id=?", (identity,)
                ).fetchone():
                    connection.execute(
                        "INSERT INTO history_batches VALUES (?,?,?)",
                        (identity, batch.source_sha256, encode(batch)),
                    )
                    changed = True
                connection.execute("DELETE FROM history_parts WHERE id=?", (identity,))
            outcome = "changed" if changed else "duplicate"
            if changed:
                connection.execute(
                    "UPDATE state SET revision=revision+1,current_run_id=NULL WHERE id=1"
                )
        result: dict[str, JsonValue] = {
            "outcome": outcome,
            "revision": store._state(connection)["revision"],
        }
        connection.execute(
            "INSERT INTO commands VALUES (?,?,?)", (manifest.command_key, payload, encode(result))
        )
        return result


def discard(store: AdvisoryStore, manifest: HistoryManifest) -> dict[str, JsonValue]:
    payload = encode({"discard_history_parts": manifest.model_dump(mode="json")})
    with store._connection(write=True) as connection:
        prior = connection.execute(
            "SELECT payload,result FROM commands WHERE key=?", (manifest.command_key,)
        ).fetchone()
        if prior:
            if prior[0] != payload:
                raise PersistenceError("command_key_reused")
            return cast(dict[str, JsonValue], json.loads(prior[1]))
        outcome = "stale_revision"
        if store._state(connection)["revision"] == manifest.expected_revision:
            removed = 0
            digests = set()
            for identity in manifest.part_ids:
                row = connection.execute(
                    "SELECT source_sha256 FROM history_parts WHERE id=?", (identity,)
                ).fetchone()
                if row:
                    digests.add(row[0])
                removed += connection.execute(
                    "DELETE FROM history_parts WHERE id=?", (identity,)
                ).rowcount
            # Only originals no longer owned anywhere can be removed. Active,
            # saved, benchmark, snapshot and other pending work remains intact.
            for digest in digests:
                connection.execute(
                    "DELETE FROM sources WHERE sha256=? AND sha256 NOT IN ("
                    "SELECT source_sha256 FROM history_parts UNION "
                    "SELECT source_sha256 FROM history_batches UNION "
                    "SELECT source_sha256 FROM snapshots UNION "
                    "SELECT source_sha256 FROM run_sources UNION "
                    "SELECT source_sha256 FROM input_sources UNION "
                    "SELECT source_sha256 FROM benchmark_observations "
                    "WHERE source_sha256 IS NOT NULL)",
                    (digest,),
                )
            outcome = "changed" if removed else "duplicate"
        result: dict[str, JsonValue] = {
            "outcome": outcome,
            "revision": store._state(connection)["revision"],
        }
        connection.execute(
            "INSERT INTO commands VALUES (?,?,?)", (manifest.command_key, payload, encode(result))
        )
        return result
