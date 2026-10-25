"""Synthetic required-history closure, scope, interruption and coordinated snapshot tests."""

import hashlib
import json
import os
import runpy
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from prosper import history as h
from prosper import history_recovery as b
from prosper import history_registry as r
from prosper.evidence import EvidenceError, RuntimeBoundary
from prosper.history_coordination import LOCK_NAME
from prosper.recovery import RecoveryError
from prosper.recovery import restore as foundation_restore

ROOT = Path(__file__).resolve().parents[1]
reference_input = cast(
    Callable[[h.HistoryStore], h.Envelope],
    runpy.run_path(str(ROOT / "scripts/qualify_history.py"))["reference_input"],
)


def boundary(path: Path) -> RuntimeBoundary:
    return RuntimeBoundary(path, ROOT, "synthetic")


@pytest.fixture
def registry(tmp_path: Path) -> r.HistoryRegistry:
    history = h.HistoryStore(boundary(tmp_path / "source"))
    registry = r.HistoryRegistry.initialize(history)
    data = reference_input(history)
    first = history.publish(data)
    registry.register("old", first.receipt, expected=data.selection)
    second = history.publish(
        h.Envelope(
            selection=data.selection,
            sources=data.sources,
            observations=data.observations,
            diagnostics=("fictional source not qualified",),
        )
    )
    registry.register("new", second.receipt, expected=data.selection)
    return registry


def test_complete_snapshot_restore_prior_versions_scope_and_new_registration(
    registry: r.HistoryRegistry, tmp_path: Path
) -> None:
    orphan = registry.history.retain(b"fictional unreferenced cache, explicitly excluded")
    original = registry.proof()
    source_bytes = {
        x.relative_reference: registry.history.evidence.read(x) for x in original.required
    }
    saved = boundary(tmp_path / "backup")
    manifest = b.backup(registry, saved, candidate_id="fictional-candidate")
    assert manifest.scope == "registered-synthetic-history-only"
    assert manifest.dependency_count == 2 and len(manifest.evidence) == 3
    assert b.inspect_backup(saved) == manifest
    backup_bytes = {
        p.relative_to(saved.root): p.read_bytes() for p in saved.root.rglob("*") if p.is_file()
    }
    assert not saved.path(f"{h.VERSION}/{orphan.reference}").exists()
    assert not saved.path("prosper.sqlite3").exists()
    restored = boundary(tmp_path / "restored")
    assert b.restore(saved, restored) == manifest
    reopened = r.HistoryRegistry(h.HistoryStore(restored, existing=True))
    assert reopened.proof() == original
    assert reopened.replay("old") == registry.replay("old")
    assert reopened.replay("new") == registry.replay("new")
    assert not reopened.replay("new").manifest.coverage.complete
    assert {
        x.relative_reference: reopened.history.evidence.read(x) for x in original.required
    } == source_bytes
    assert (
        reopened.replay("old").manifest.envelope.observations[0].close.text == "0010.000000000000"
    )
    # Restored coordination/registry remain usable, without changing old links.
    old = reopened.replay("old")
    reopened.register("after-restore", old.receipt, expected=old.manifest.envelope.selection)
    assert len(reopened.proof().dependencies) == 3
    assert registry.proof() == original
    assert b.inspect_backup(saved) == manifest
    assert {
        p.relative_to(saved.root): p.read_bytes() for p in saved.root.rglob("*") if p.is_file()
    } == backup_bytes
    with pytest.raises(RecoveryError):
        foundation_restore(saved, boundary(tmp_path / "foundation-refuses-history"))
    with pytest.raises(b.HistoryRecoveryError):
        b.restore(saved, restored)
    with pytest.raises(b.HistoryRecoveryError):
        b.backup(registry, saved, candidate_id="again")


@pytest.mark.parametrize("target", ["registry", "raw", "manifest", "lock"])
@pytest.mark.parametrize("damage", ["missing", "corrupt", "alias"])
def test_backup_inspection_and_restore_refuse_damaged_closure(
    registry: r.HistoryRegistry, tmp_path: Path, target: str, damage: str
) -> None:
    saved = boundary(tmp_path / "backup")
    manifest = b.backup(registry, saved, candidate_id="damage-probe")
    entry = registry.proof().dependencies[0]
    reference = {
        "registry": r.DATABASE_REFERENCE,
        "raw": registry.replay("old").manifest.envelope.sources[0].raw.reference,
        "manifest": entry.manifest.reference,
        "lock": LOCK_NAME,
    }[target]
    path = saved.path(f"{h.VERSION}/{reference}")
    if damage == "missing":
        path.unlink()
    elif damage == "corrupt":
        path.write_bytes(b"fictional corruption")
    else:
        os.link(path, saved.path("unexpected-alias"))
    with pytest.raises(b.HistoryRecoveryError):
        b.inspect_backup(saved)
    destination = boundary(tmp_path / "destination")
    with pytest.raises(b.HistoryRecoveryError):
        b.restore(saved, destination)
    assert not destination.root.exists()
    assert manifest.dependency_count == len(registry.proof().dependencies)


@pytest.mark.parametrize(
    "change",
    ["omit", "extra", "duplicate", "selection", "version", "scope", "state", "implementation"],
)
def test_forged_or_incompatible_backup_never_becomes_ready(
    registry: r.HistoryRegistry, tmp_path: Path, change: str
) -> None:
    saved = boundary(tmp_path / "backup")
    b.backup(registry, saved, candidate_id="forged-probe")
    path = saved.path(b.MANIFEST_NAME)
    values = json.loads(path.read_bytes())
    if change == "omit":
        values["evidence"].pop()
    elif change == "extra":
        # A valid but unregistered object must not be smuggled into required scope.
        history = h.HistoryStore(saved, existing=True)
        item = history.retain(b"fictional unregistered object")
        values["evidence"].append(
            {"reference": item.reference, "sha256": item.sha256, "byte_length": item.byte_length}
        )
        values["evidence"].sort(key=lambda x: x["reference"])
    elif change == "duplicate":
        values["evidence"].append(values["evidence"][0])
    elif change == "selection":
        database = saved.path(f"{h.VERSION}/{r.DATABASE_REFERENCE}")
        with sqlite3.connect(database) as connection:
            sequence, document = connection.execute(
                "SELECT sequence, document FROM required_history ORDER BY sequence LIMIT 1"
            ).fetchone()
            record = json.loads(document)
            record["selection"]["calendar_evidence"] = "forged calendar"
            document = json.dumps(record, sort_keys=True, separators=(",", ":"))
            connection.execute(
                "UPDATE required_history SET document=?,sha256=? WHERE sequence=?",
                (document, hashlib.sha256(document.encode()).hexdigest(), sequence),
            )
        values["registry"]["sha256"] = hashlib.sha256(database.read_bytes()).hexdigest()
    elif change == "version":
        values["format"] = "prosper-required-history-backup-v0"
    elif change == "scope":
        values["scope"] = "all-state"
    elif change == "state":
        values["state_sha256"] = "0" * 64
    else:
        values["implementation_sha256"] = "0" * 64
    path.write_bytes(json.dumps(values, sort_keys=True, separators=(",", ":")).encode())
    with pytest.raises(b.HistoryRecoveryError):
        b.inspect_backup(saved)
    with pytest.raises(b.HistoryRecoveryError):
        b.restore(saved, boundary(tmp_path / "refused"))


def test_empty_explicit_registry_and_invalid_source_do_not_invent_dependencies(
    tmp_path: Path,
) -> None:
    history = h.HistoryStore(boundary(tmp_path / "source"))
    registry = r.HistoryRegistry.initialize(history)
    saved = boundary(tmp_path / "backup")
    manifest = b.backup(registry, saved, candidate_id="empty-explicit")
    assert manifest.evidence == () and manifest.dependency_count == 0
    destination = boundary(tmp_path / "restored")
    b.restore(saved, destination)
    assert r.HistoryRegistry(h.HistoryStore(destination, existing=True)).proof() == registry.proof()
    registry.runtime.path(r.DATABASE_REFERENCE).unlink()
    failed = boundary(tmp_path / "failed")
    with pytest.raises(b.HistoryRecoveryError):
        b.backup(registry, failed, candidate_id="no-reset")
    assert not failed.root.exists()


@pytest.mark.parametrize("target", ["raw", "manifest", "schema"])
def test_source_corruption_refuses_backup_without_touching_prior_versions(
    registry: r.HistoryRegistry, tmp_path: Path, target: str
) -> None:
    saved = boundary(tmp_path / "prior-backup")
    manifest = b.backup(registry, saved, candidate_id="prior")
    if target == "schema":
        with sqlite3.connect(registry.runtime.path(r.DATABASE_REFERENCE)) as connection:
            connection.execute("PRAGMA user_version=999")
    else:
        frozen = registry.replay("new")
        reference = (
            frozen.receipt.relative_reference
            if target == "manifest"
            else frozen.manifest.envelope.sources[0].raw.reference
        )
        registry.runtime.path(reference).write_bytes(b"fictional corrupt source")
    with pytest.raises(b.HistoryRecoveryError):
        b.backup(registry, boundary(tmp_path / "new-backup"), candidate_id="invalid")
    assert b.inspect_backup(saved) == manifest
    b.restore(saved, boundary(tmp_path / "restored"))


@pytest.mark.parametrize("phase", ["restore_copied", "restore_verified"])
def test_copy_failure_and_failed_final_publication_keep_marker_and_source(
    registry: r.HistoryRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    saved = boundary(tmp_path / "backup")
    manifest = b.backup(registry, saved, candidate_id="restore-failure")
    destination = boundary(tmp_path / "destination")

    def fail(name: str) -> None:
        if name == phase:
            raise OSError("stipulated copy/publication failure")

    monkeypatch.setattr(b, "_step", fail)
    with pytest.raises(b.HistoryRecoveryError):
        b.restore(saved, destination)
    assert destination.path(b.RESTORE_MARKER).exists()
    assert b.inspect_backup(saved) == manifest
    with pytest.raises(h.HistoryError, match="history_restore_in_progress"):
        h.HistoryStore(destination, existing=True)


def test_changed_copy_refuses_restore_and_new_destination_can_retry(
    registry: r.HistoryRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = boundary(tmp_path / "backup")
    manifest = b.backup(registry, saved, candidate_id="copy-recheck")
    destination = boundary(tmp_path / "destination")

    def damage(name: str) -> None:
        if name == "restore_copied":
            reference = f"history-restore-work/{h.VERSION}/{manifest.evidence[0].reference}"
            destination.path(reference).write_bytes(b"fictional copied-object corruption")

    monkeypatch.setattr(b, "_step", damage)
    with pytest.raises(b.HistoryRecoveryError):
        b.restore(saved, destination)
    assert destination.path(b.RESTORE_MARKER).exists()
    assert not destination.path(h.VERSION).exists()
    assert b.inspect_backup(saved) == manifest


@pytest.mark.parametrize("candidate", ["", "../escape", "private/path"])
def test_invalid_candidate_and_overlap_never_reserve_destination(
    registry: r.HistoryRegistry, tmp_path: Path, candidate: str
) -> None:
    destination = boundary(tmp_path / "invalid")
    with pytest.raises(b.HistoryRecoveryError):
        b.backup(registry, destination, candidate_id=candidate)
    assert not destination.root.exists()
    with pytest.raises(b.HistoryRecoveryError):
        b.backup(registry, boundary(registry.history.runtime.path("nested")), candidate_id="valid")
    assert not registry.history.runtime.path("nested").exists()


CHILD = """
import os, sys, time
from pathlib import Path
from prosper import history as h, history_registry as r, history_recovery as b
from prosper.evidence import RuntimeBoundary
root, source, backup, dest, phase, signal, release = map(Path, sys.argv[1:])
def bound(p): return RuntimeBoundary(p, root, 'synthetic')
def hook(name):
    if name == str(phase):
        signal.write_text('ready')
        if str(release) == 'die': os._exit(73)
        while not release.exists(): time.sleep(0.02)
b._step = hook
if str(phase) == 'backup_manifest_linked':
    original_link = os.link
    def linked(*args, **kwargs):
        original_link(*args, **kwargs)
        hook('backup_manifest_linked')
    os.link = linked
if str(phase).startswith('backup_'):
    registry = r.HistoryRegistry(h.HistoryStore(bound(source), existing=True))
    b.backup(registry, bound(backup), candidate_id='process-probe')
else:
    b.restore(bound(backup), bound(dest))
"""


def child(
    registry: r.HistoryRegistry, tmp_path: Path, phase: str, *, pause: bool = False
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            CHILD,
            str(ROOT),
            str(registry.history.runtime.root),
            str(tmp_path / "backup"),
            str(tmp_path / "destination"),
            phase,
            str(tmp_path / "signal"),
            str(tmp_path / "release") if pause else "die",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


@pytest.mark.parametrize(
    "phase",
    [
        "backup_snapshot",
        "backup_evidence",
        "backup_verified",
        "backup_published",
        "backup_manifest_linked",
        "restore_reserved",
        "restore_copied",
        "restore_verified",
        "restore_published",
        "restore_ready",
    ],
)
def test_actual_process_death_never_exposes_partial_readiness(
    registry: r.HistoryRegistry, tmp_path: Path, phase: str
) -> None:
    saved = boundary(tmp_path / "backup")
    if phase.startswith("restore"):
        b.backup(registry, saved, candidate_id="before-death")
    process = child(registry, tmp_path, phase)
    stdout, stderr = process.communicate(timeout=30)
    assert process.returncode == 73, (stdout, stderr)
    assert registry.replay("old").manifest.coverage.complete
    if phase.startswith("backup"):
        if phase == "backup_published":
            b.inspect_backup(saved)
        else:
            with pytest.raises(b.HistoryRecoveryError):
                b.inspect_backup(saved)
        # Source lock is released by OS process exit; original versions survive.
        b.backup(registry, boundary(tmp_path / "retry-backup"), candidate_id="retry")
    else:
        destination = boundary(tmp_path / "destination")
        if phase == "restore_ready":
            assert (
                r.HistoryRegistry(h.HistoryStore(destination, existing=True)).proof()
                == registry.proof()
            )
        else:
            with pytest.raises(h.HistoryError, match="history_restore_in_progress"):
                h.HistoryStore(destination, existing=True)
        with pytest.raises(b.HistoryRecoveryError):
            b.restore(saved, destination)
        retried = boundary(tmp_path / "new-destination")
        b.restore(saved, retried)
        assert r.HistoryRegistry(h.HistoryStore(retried, existing=True)).proof() == registry.proof()


def test_actual_backup_lock_blocks_registration_publication_and_retention(
    registry: r.HistoryRegistry, tmp_path: Path
) -> None:
    prior = registry.proof()
    frozen = registry.replay("old")
    process = child(registry, tmp_path, "backup_snapshot", pause=True)
    try:
        deadline = time.monotonic() + 20
        while not (tmp_path / "signal").exists():
            assert process.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.02)
        with pytest.raises(EvidenceError, match="history_runtime_busy"):
            registry.register("during", frozen.receipt, expected=frozen.manifest.envelope.selection)
        with pytest.raises(EvidenceError, match="history_runtime_busy"):
            registry.history.retain(b"fictional concurrent publication")
        assert registry.assess_removal(frozen.receipt.relative_reference).required is None
        with pytest.raises(b.HistoryRecoveryError):
            b.backup(registry, boundary(tmp_path / "contending"), candidate_id="busy")
        assert not (tmp_path / "contending").exists()
        (tmp_path / "release").write_text("continue")
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, (stdout, stderr)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    registry.register("after", frozen.receipt, expected=frozen.manifest.envelope.selection)
    restored = boundary(tmp_path / "restored")
    b.restore(boundary(tmp_path / "backup"), restored)
    assert r.HistoryRegistry(h.HistoryStore(restored, existing=True)).proof() == prior


def test_restore_marker_blocks_existing_handles_and_duplicate_json_refuses(
    registry: r.HistoryRegistry, tmp_path: Path
) -> None:
    history = registry.history
    frozen = registry.replay("old")
    marker = history.runtime.path(b.RESTORE_MARKER)
    marker.write_bytes(b"interrupted")
    for operation in (
        lambda: history.retain(b"blocked"),
        lambda: history.publish(frozen.manifest.envelope),
        lambda: history.read(frozen.receipt),
        registry.proof,
        lambda: r.HistoryRegistry.initialize(history),
    ):
        with pytest.raises(h.HistoryError, match="history_restore_in_progress"):
            operation()
    marker.unlink()
    saved = boundary(tmp_path / "backup")
    b.backup(registry, saved, candidate_id="duplicate-json")
    path = saved.path(b.MANIFEST_NAME)
    raw = path.read_bytes()
    path.write_bytes(b'{"scope":"registered-synthetic-history-only",' + raw[1:])
    with pytest.raises(b.HistoryRecoveryError):
        b.inspect_backup(saved)
