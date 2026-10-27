"""Current-workspace recovery outcomes, including actual killed transactions."""

import hashlib
import random
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest

import prosper.advisory_recovery as recovery
import prosper.advisory_store as storage
from prosper.advisory_recovery import backup, restore
from prosper.advisory_store import DATABASE_NAME, AdvisoryStore
from prosper.api_contracts import DiagnosticRequest, Upload
from prosper.storage import RESTORE_MARKER, PersistenceError, RuntimeBoundary
from prosper.workspace import Workspace

ROOT = Path(__file__).resolve().parents[1]


def store(path: Path) -> AdvisoryStore:
    return AdvisoryStore(RuntimeBoundary(path))


def seeded(path: Path) -> AdvisoryStore:
    result = store(path)
    workspace = Workspace(result)
    preview = workspace.stage(
        Upload.model_validate_json(
            (ROOT / "examples/synthetic/advisory-workspace.json").read_bytes()
        )
    )
    result.select(preview.id, "first", 0)
    result.configure({"selected_cash": "100.00", "risk_enabled": False}, "settings", 1)
    workspace.diagnose(
        DiagnosticRequest(run_id="diagnostic", expected_revision=2, as_of="2026-10-25T20:00:00Z")
    )
    return result


def test_current_backup_restore_retains_sources_settings_outputs_receipts(tmp_path: Path) -> None:
    source = seeded(tmp_path / "source")
    raw = backup(source)
    target = store(tmp_path / "target")
    assert restore(target, raw) == {"outcome": "restored", "revision": 2}
    assert target.current() == source.current()
    assert target.catalog() == source.catalog()
    assert target.run("diagnostic") == source.run("diagnostic")
    identity = str(source.current()["snapshot_id"])
    assert target.source(identity) == source.source(identity)
    assert target.select(identity, "first", 0) == {"outcome": "changed", "revision": 1}
    target.configure({"later": True}, "later", 2)
    before = target.current()
    # A lost restore response retried later cannot roll back subsequent edits.
    assert restore(target, raw) == {"outcome": "restored", "revision": 2}
    assert target.current() == before
    with pytest.raises(PersistenceError, match="restore_requires_empty_workspace"):
        restore(source, raw)


def test_backup_compacts_scratch_free_pages_without_changing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = seeded(tmp_path / "source")
    baseline = backup(source)
    # Compression must not erase the free-page pressure this test exercises.
    transient = b"fictional disposable cache\0" + random.Random(713).randbytes(2 * 1024 * 1024)
    digest = hashlib.sha256(transient).hexdigest()
    with source._connection(write=True) as connection:
        source._retain_source(connection, digest, transient)
    with source._connection(write=True) as connection:
        connection.execute("DELETE FROM sources WHERE sha256=?", (digest,))
    path = source.runtime.path(DATABASE_NAME)
    before = path.read_bytes()
    assert len(before) > len(baseline) + 1024 * 1024
    monkeypatch.setattr(recovery, "MAX_BACKUP_BYTES", len(baseline) + 4096)
    compact = backup(source)
    assert len(compact) <= len(baseline) + 4096
    assert path.read_bytes() == before
    target = store(tmp_path / "target")
    restore(target, compact)
    assert target.current() == source.current()
    assert target.run("diagnostic") == source.run("diagnostic")
    monkeypatch.setattr(recovery, "MAX_BACKUP_BYTES", len(compact) - 1)
    with pytest.raises(PersistenceError, match="backup_size_limit"):
        backup(source)


def test_compressed_originals_preserve_exact_bytes_and_backup_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = seeded(tmp_path / "source")
    baseline = len(backup(source))
    raw = b"Fictional exact source,12.5000,unknown basis\r\n" * 50000
    digest = source.retain_source(raw)
    assert source.retain_source(raw) == digest
    with source._connection() as connection:
        size, encoded = connection.execute(
            "SELECT original_size,zlib_bytes FROM sources WHERE sha256=?", (digest,)
        ).fetchone()
    assert size == len(raw) and len(encoded) < len(raw) // 100
    monkeypatch.setattr(recovery, "MAX_BACKUP_BYTES", baseline + 32768)
    packed = backup(source)
    assert len(packed) <= baseline + 32768 < len(raw)
    target = store(tmp_path / "target")
    restore(target, packed)
    assert target.source_bytes(digest) == raw
    assert target.current() == source.current()
    monkeypatch.setattr(recovery, "MAX_BACKUP_BYTES", len(packed) - 1)
    with pytest.raises(PersistenceError, match="backup_size_limit"):
        backup(source)


@pytest.mark.parametrize(
    "kind",
    [
        "schema",
        "prior-schema",
        "source",
        "source-size",
        "missing-source",
        "output",
        "truncated",
        "trigger",
    ],
)
def test_corrupt_or_unsupported_backup_preserves_empty_target(tmp_path: Path, kind: str) -> None:
    source = seeded(tmp_path / "source")
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(backup(source))
    with closing(sqlite3.connect(path)) as connection:
        if kind == "schema":
            connection.execute("PRAGMA user_version=99")
        elif kind == "prior-schema":
            connection.execute(f"PRAGMA user_version={storage.SCHEMA_VERSION - 1}")
        elif kind == "source":
            connection.execute("UPDATE sources SET zlib_bytes=x'00'")
        elif kind == "source-size":
            connection.execute("UPDATE sources SET original_size=original_size-1")
        elif kind == "missing-source":
            connection.execute("DELETE FROM sources")
        elif kind == "trigger":
            connection.execute(
                "CREATE TRIGGER injected AFTER INSERT ON state BEGIN DELETE FROM sources; END"
            )
        elif kind == "output":
            connection.execute("UPDATE runs SET document='{}'")
        connection.commit()
    raw = path.read_bytes()
    if kind == "truncated":
        raw = raw[:100]
    target = store(tmp_path / "target")
    before = target.current()
    with pytest.raises(PersistenceError):
        restore(target, raw)
    assert target.current() == before
    assert target.catalog() == {
        "snapshots": [],
        "runs": [],
        "worksheets": [],
        "benchmarks": [],
        "pending_history_parts": [],
    }


def test_restore_transaction_failure_and_process_death_leave_retryable_empty_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = backup(seeded(tmp_path / "source"))
    target = store(tmp_path / "target")

    def fail(connection: sqlite3.Connection) -> None:
        raise PersistenceError("injected_before_commit")

    monkeypatch.setattr(storage, "_before_commit", fail)
    with pytest.raises(PersistenceError, match="injected_before_commit"):
        restore(target, raw)
    assert target.current()["snapshot_id"] is None
    monkeypatch.undo()
    file = tmp_path / "backup.sqlite3"
    file.write_bytes(raw)
    code = """
import os, sys
from pathlib import Path
import prosper.advisory_store as storage
from prosper.advisory_store import AdvisoryStore
from prosper.advisory_recovery import restore
from prosper.storage import RuntimeBoundary
target = AdvisoryStore.existing(RuntimeBoundary(Path(sys.argv[1])))
storage._before_commit = lambda connection: os._exit(27)
restore(target,Path(sys.argv[3]).read_bytes())
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(target.runtime.root), str(ROOT), str(file)],
        capture_output=True,
    )
    assert result.returncode == 27 and result.stdout == result.stderr == b""
    reopened = AdvisoryStore.existing(target.runtime)
    assert reopened.current()["snapshot_id"] is None
    assert restore(reopened, raw)["outcome"] == "restored"


def test_restore_and_user_writer_serialize_without_lost_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = backup(seeded(tmp_path / "source"))
    target = store(tmp_path / "target")
    entered, release = threading.Event(), threading.Event()

    def pending(connection: sqlite3.Connection) -> None:
        if threading.current_thread().name.startswith("restore-test"):
            entered.set()
            assert release.wait(8)

    monkeypatch.setattr(storage, "_before_commit", pending)
    with ThreadPoolExecutor(1, thread_name_prefix="restore-test") as worker:
        restored = worker.submit(restore, target, raw)
        assert entered.wait(8)
        with ThreadPoolExecutor(1) as writers:
            write = writers.submit(target.configure, {"later": True}, "later", 0)
            assert not write.done()
            release.set()
            assert restored.result(timeout=8)["revision"] == 2
            assert write.result(timeout=8)["outcome"] == "stale_revision"
    assert target.current()["settings"] == {"selected_cash": "100.00", "risk_enabled": False}


def test_consistent_backup_while_writer_waits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = seeded(tmp_path / "source")
    entered, release = threading.Event(), threading.Event()
    original = recovery._validate

    def hold(connection: sqlite3.Connection) -> None:
        entered.set()
        assert release.wait(8)
        original(connection)

    monkeypatch.setattr(recovery, "_validate", hold)
    with ThreadPoolExecutor(2) as workers:
        saved = workers.submit(backup, source)
        assert entered.wait(8)
        write = workers.submit(source.configure, {"later": True}, "later", 2)
        release.set()
        raw = saved.result(timeout=8)
        assert write.result(timeout=8)["revision"] == 3
    monkeypatch.undo()
    target = store(tmp_path / "target")
    restore(target, raw)
    assert target.current()["revision"] == 2
    assert target.run("diagnostic").settings == {"selected_cash": "100.00", "risk_enabled": False}


def test_backup_refuses_missing_required_source_without_hiding_saved_outputs(
    tmp_path: Path,
) -> None:
    source = seeded(tmp_path / "source")
    saved = source.run("diagnostic")
    with closing(sqlite3.connect(source.runtime.path(DATABASE_NAME))) as connection:
        connection.execute("DELETE FROM sources")
        connection.commit()
    with pytest.raises(PersistenceError):
        backup(source)
    assert source.run("diagnostic") == saved


def test_alias_and_interrupted_runtime_refusal(tmp_path: Path) -> None:
    source = seeded(tmp_path / "source")
    alias = tmp_path / "alias.sqlite3"
    alias.hardlink_to(source.runtime.path(DATABASE_NAME))
    with pytest.raises(PersistenceError, match="untrusted_database_file"):
        backup(source)
    alias.unlink()
    source.runtime.path(RESTORE_MARKER).write_text("interrupted")
    with pytest.raises(PersistenceError, match="restore_incomplete"):
        backup(source)


def test_old_runtime_is_explicitly_refused_without_initializing_empty_advisory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "old-runtime"
    root.mkdir()
    legacy = root / "checkpoints-v1.sqlite3"
    legacy.write_bytes(b"unsupported development state")
    with pytest.raises(PersistenceError, match="fresh_advisory_runtime_required"):
        store(root)
    assert not (root / DATABASE_NAME).exists()
    assert legacy.read_bytes() == b"unsupported development state"


def test_interrupted_diagnostic_resumes_frozen_inputs_without_publishing_stale_result(
    tmp_path: Path,
) -> None:
    target = seeded(tmp_path / "source")
    code = """
import os, sys
from pathlib import Path
from prosper.advisory_store import AdvisoryStore
from prosper.storage import RuntimeBoundary
from prosper.api_contracts import DiagnosticRequest
from prosper.workspace import Workspace
store = AdvisoryStore.existing(RuntimeBoundary(Path(sys.argv[1])))
Workspace.findings = staticmethod(lambda snapshot: os._exit(28))
Workspace(store).diagnose(DiagnosticRequest(run_id='crashed',expected_revision=2,as_of='2026-10-25T20:00:00Z'))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(target.runtime.root), str(ROOT)],
        capture_output=True,
    )
    assert result.returncode == 28 and result.stdout == result.stderr == b""
    frozen = target.run("crashed")
    assert frozen.status == "running"
    target.configure({"later": True}, "later", 2)
    completed = Workspace(target).diagnose(
        DiagnosticRequest(
            run_id=frozen.id,
            expected_revision=frozen.input_revision,
            as_of=frozen.as_of,
        )
    )
    assert completed.status == "partial" and completed.settings == frozen.settings
    assert target.current()["current_run_id"] is None
