"""Pending originals, complete atomic publication and bounded protected requests."""

import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import polars as pl
import pytest

from prosper import advisory_store, history_table, history_upload
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import AdvisoryStore
from prosper.api_contracts import CatalogResponse, HistoryManifest
from prosper.storage import PersistenceError, RuntimeBoundary
from tests.test_history import ROOT, multipart, request, workspace
from tests.test_import_api import running


def pending(store: AdvisoryStore) -> tuple[str, ...]:
    return CatalogResponse.model_validate_json(json.dumps(store.catalog())).pending_history_parts


def staged(store: AdvisoryStore) -> HistoryManifest:
    upload = multipart()
    return HistoryManifest(
        part_count=upload.part_count,
        part_ids=tuple(history_upload.stage(store, p).id for p in upload.parts),
        command_key="activate-parts",
        expected_revision=1,
    )


def test_pending_restart_cache_clear_recovery_and_exact_retry(tmp_path: Path) -> None:
    w = workspace(tmp_path / "source")
    before = w.store.current()
    manifest = staged(w.store)
    assert w.store.current() == before and not w.store.history_batches()
    assert w.store.catalog()["pending_history_parts"] == list(manifest.part_ids)
    assert staged(w.store) == manifest
    reopened = AdvisoryStore.existing(w.store.runtime)
    reopened.clear_history_cache("clear", 1)
    target = AdvisoryStore(RuntimeBoundary(tmp_path / "restored"))
    restore(target, backup(reopened))
    assert target.catalog()["pending_history_parts"] == list(manifest.part_ids)
    assert not target.history_batches()
    for part in multipart().parts:
        assert target.source_bytes(part.batch.source_sha256) == history_upload.decode(part)[1]
    manifest = manifest.model_copy(update={"expected_revision": 2})
    assert history_upload.activate(target, manifest) == {"outcome": "changed", "revision": 3}
    assert not target.catalog()["pending_history_parts"] and len(target.history_batches()) == 2
    target.configure({"fictional": True}, "new-settings", 3)
    assert history_upload.activate(target, manifest) == {"outcome": "changed", "revision": 3}
    with pytest.raises(PersistenceError, match="command_key_reused"):
        history_upload.activate(target, manifest.model_copy(update={"expected_revision": 4}))


@pytest.mark.parametrize("fault", ["missing", "source", "document"])
def test_missing_corrupt_pending_refuses_activation_and_backup(tmp_path: Path, fault: str) -> None:
    w = workspace(tmp_path / "source")
    manifest = staged(w.store)
    identity = manifest.part_ids[0]
    with w.store._connection(write=True) as connection:
        if fault == "missing":
            connection.execute("DELETE FROM history_parts WHERE id=?", (identity,))
        elif fault == "source":
            connection.execute(
                "UPDATE sources SET zlib_bytes=x'00' WHERE sha256=?",
                (multipart().parts[0].batch.source_sha256,),
            )
        else:
            connection.execute("UPDATE history_parts SET document='{}' WHERE id=?", (identity,))
    with pytest.raises((PersistenceError, ValueError)):
        history_upload.activate(w.store, manifest)
    assert w.store.current()["revision"] == 1 and not w.store.history_batches()
    if fault != "missing":
        with pytest.raises(PersistenceError):
            backup(w.store)


@pytest.mark.parametrize("budget", ["MAX_PARTS", "MAX_ROWS", "MAX_ORIGINALS"])
def test_pending_aggregate_bounds_refuse_without_new_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, budget: str
) -> None:
    w = workspace(tmp_path / "source")
    first, second = multipart().parts
    history_upload.stage(w.store, first)
    limit = {
        "MAX_PARTS": 1,
        "MAX_ROWS": first.batch.rows.row_count,
        "MAX_ORIGINALS": len(history_upload.decode(first)[1]),
    }[budget]
    monkeypatch.setattr(history_upload, budget, limit)
    with pytest.raises(PersistenceError, match="pending_history_budget_exceeded"):
        history_upload.stage(w.store, second)
    assert len(pending(w.store)) == 1
    with pytest.raises(PersistenceError):
        w.store.source_bytes(second.batch.source_sha256)
    # Identical retries do not consume another part/budget.
    history_upload.stage(w.store, first)


def test_atomic_failure_death_stale_and_competing_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = workspace(tmp_path / "source")
    manifest = staged(w.store)

    def fail(connection: sqlite3.Connection) -> None:
        raise PersistenceError("injected-activation")

    monkeypatch.setattr(advisory_store, "_before_commit", fail)
    with pytest.raises(PersistenceError, match="injected-activation"):
        history_upload.activate(w.store, manifest)
    monkeypatch.undo()
    assert not w.store.history_batches() and len(pending(w.store)) == 2
    code = """
import os,sys
from pathlib import Path
from prosper import advisory_store, history_upload
from prosper.api_contracts import HistoryManifest
from prosper.storage import RuntimeBoundary
s=advisory_store.AdvisoryStore.existing(RuntimeBoundary(Path(sys.argv[1])))
advisory_store._before_commit=lambda connection:os._exit(29)
history_upload.activate(s,HistoryManifest.model_validate_json(sys.argv[3]))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(w.store.runtime.root),
            str(ROOT),
            manifest.model_dump_json(),
        ],
        capture_output=True,
    )
    assert result.returncode == 29 and not result.stdout and not result.stderr
    assert w.store.current()["revision"] == 1 and not w.store.history_batches()
    second = manifest.model_copy(update={"command_key": "competing"})
    with ThreadPoolExecutor(2) as workers:
        results = list(
            workers.map(lambda m: history_upload.activate(w.store, m), (manifest, second))
        )
    assert sorted(str(r["outcome"]) for r in results) == ["changed", "stale_revision"]
    assert w.store.current()["revision"] == 2 and len(w.store.history_batches()) == 2


def test_explicit_discard_preserves_active_pending_and_unrelated_sources(tmp_path: Path) -> None:
    w = workspace(tmp_path / "source")
    manifest = staged(w.store)
    first = manifest.model_copy(update={"part_count": 1, "part_ids": manifest.part_ids[:1]})
    history_upload.activate(w.store, first)
    second = manifest.model_copy(update={"command_key": "discard", "expected_revision": 2})
    assert history_upload.discard(w.store, second) == {"outcome": "changed", "revision": 2}
    assert history_upload.discard(w.store, second) == {"outcome": "changed", "revision": 2}
    assert len(w.store.history_batches()) == 1
    assert w.store.source_bytes(multipart().parts[0].batch.source_sha256)
    assert w.store.snapshot(str(w.store.current()["snapshot_id"]))
    history_upload.stage(w.store, multipart().parts[1])
    # A lost discard response retries its receipt, never deletes newly restaged work.
    history_upload.discard(w.store, second)
    assert len(pending(w.store)) == 1


def test_protected_parts_preview_activation_and_discard_roundtrip(tmp_path: Path) -> None:
    with running(tmp_path / "source") as api:
        ids = []
        for part in multipart().parts:
            status, receipt = api.request(
                "/api/v1/history/parts", "POST", part.model_dump(mode="json")
            )
            assert status == 200
            ids.append(receipt["id"])
        assert api.current()["revision"] == 0
        manifest = {
            "version": "advisory-history-manifest-v1",
            "part_count": 2,
            "part_ids": ids,
            "command_key": "http-activate",
            "expected_revision": 0,
        }
        assert api.request("/api/v1/history/preview", "POST", manifest)[0] == 200
        assert api.request("/api/v1/history/refresh", "POST", manifest) == (
            200,
            {"outcome": "changed", "revision": 1},
        )
        assert api.request("/api/v1/history/refresh", "POST", manifest)[1]["revision"] == 1
        assert (
            api.request(
                "/api/v1/history/discard",
                "POST",
                {**manifest, "command_key": "discard-http", "expected_revision": 1},
            )[1]["outcome"]
            == "duplicate"
        )
        assert (
            api.request("/api/v1/history/refresh", "POST", multipart().model_dump(mode="json"))[0]
            == 422
        )


def test_duplicate_or_missing_manifest_parts_refuse() -> None:
    for ids, count in [(("0" * 64,), 2), (("0" * 64, "0" * 64), 2)]:
        with pytest.raises(ValueError):
            HistoryManifest(
                part_count=count, part_ids=ids, command_key="invalid", expected_revision=0
            )


def test_alignment_guard_is_explicit_without_losing_active_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = workspace(tmp_path / "source")
    upload = multipart()
    w.import_history(upload)
    monkeypatch.setattr(history_table, "MAX_ENCODED_TABLE_BYTES", 1)
    with pytest.raises(PersistenceError, match="history_alignment_size_limit"):
        w.plan_history(request().request)
    assert w.store.current()["revision"] == 2 and len(w.store.history_batches()) == 2
    for part in upload.parts:
        assert w.store.source_bytes(part.batch.source_sha256) == history_upload.decode(part)[1]


def test_missing_pending_original_is_not_zero_budget(tmp_path: Path) -> None:
    w = workspace(tmp_path / "source")
    first, second = multipart().parts
    history_upload.stage(w.store, first)
    with closing(sqlite3.connect(w.store.runtime.path("advisory-v1.sqlite3"))) as connection:
        connection.execute("DELETE FROM sources WHERE sha256=?", (first.batch.source_sha256,))
        connection.commit()
    with pytest.raises(PersistenceError, match="history_part_corrupt"):
        history_upload.stage(w.store, second)
    assert len(pending(w.store)) == 1 and w.store.current()["revision"] == 1


def test_contradictory_pending_parts_cannot_publish(tmp_path: Path) -> None:
    w = workspace(tmp_path / "source")
    first, second = multipart().parts
    changed = first.batch.model_copy(
        update={
            "source_sha256": second.batch.source_sha256,
            "rows": history_table.HistoryTable.pack(
                first.batch.rows.frame.with_columns((pl.col("close") + 1).alias("close")),
                "observations",
            ),
        }
    )
    second = second.model_copy(update={"batch": changed})
    ids = tuple(history_upload.stage(w.store, p).id for p in (first, second))
    manifest = HistoryManifest(
        part_count=2, part_ids=ids, command_key="contradictory", expected_revision=1
    )
    with pytest.raises(PersistenceError, match="contradictory_history_parts"):
        history_upload.activate(w.store, manifest)
    assert w.store.current()["revision"] == 1 and not w.store.history_batches()
    assert len(pending(w.store)) == 2
