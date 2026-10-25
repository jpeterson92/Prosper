"""Fictional append-only dependencies, explicit loss and coordinated retention."""

import json
import os
import runpy
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import cast

import pytest

from prosper import history as h
from prosper import history_registry as r
from prosper.evidence import EvidenceError, RuntimeBoundary
from prosper.history_coordination import LOCK_NAME, REGISTRY_NAMESPACE, history_writer
from prosper.maintenance import maintain_runtime

ROOT = Path(__file__).resolve().parents[1]
reference_input = cast(
    Callable[[h.HistoryStore], h.Envelope],
    runpy.run_path(str(ROOT / "scripts/qualify_history.py"))["reference_input"],
)


@pytest.fixture
def history(tmp_path: Path) -> h.HistoryStore:
    return h.HistoryStore(RuntimeBoundary(tmp_path / "history", ROOT, "synthetic"))


@pytest.fixture
def registry(history: h.HistoryStore) -> r.HistoryRegistry:
    return r.HistoryRegistry.initialize(history)


def frozen(history: h.HistoryStore, *, diagnostic: bool = False) -> h.FrozenHistory:
    data = reference_input(history)
    if diagnostic:
        data = h.Envelope(
            selection=data.selection,
            sources=data.sources,
            observations=data.observations,
            diagnostics=("stipulated source qualification unresolved",),
        )
    return history.publish(data)


def pin(
    registry: r.HistoryRegistry, snapshot: h.FrozenHistory, name: str = "fictional-run-1"
) -> r.Dependency:
    return registry.register(name, snapshot.receipt, expected=snapshot.manifest.envelope.selection)


def test_registration_idempotence_prior_versions_and_complete_closure(
    registry: r.HistoryRegistry,
) -> None:
    first = frozen(registry.history)
    entry = pin(registry, first)
    assert pin(registry, first) == entry
    proof = registry.proof()
    assert proof.dependencies == (entry,)
    # Two securities share one source object; closure is raw + manifest, not rows.
    assert {x.raw_sha256 for x in proof.required} == {
        first.snapshot_sha256,
        first.manifest.envelope.sources[0].raw.sha256,
    }
    assert len(proof.required) == 2
    second = frozen(registry.history, diagnostic=True)
    with pytest.raises(r.RegistryError, match="history_dependency_conflict"):
        pin(registry, second)
    pin(registry, second, "fictional-run-2")
    assert registry.replay("fictional-run-1") == first
    assert registry.replay("fictional-run-2") == second
    assert not registry.replay("fictional-run-2").manifest.coverage.complete
    assert len(registry.proof().required) == 3
    with pytest.raises(r.RegistryError, match="history_dependency_missing"):
        registry.replay("never-registered")
    reopened = r.HistoryRegistry(h.HistoryStore(registry.history.runtime, existing=True))
    assert reopened.proof() == registry.proof()
    assert reopened.replay(entry.dependency_id) == first


def test_explicit_initialization_and_loss_never_become_empty(history: h.HistoryStore) -> None:
    snapshot = frozen(history)
    unopened = r.HistoryRegistry(history)
    with pytest.raises(r.RegistryError, match="history_registry_missing"):
        unopened.proof()
    assert not history.evidence.runtime.path(REGISTRY_NAMESPACE).exists()
    registry = r.HistoryRegistry.initialize(history)
    assert registry.proof().dependencies == ()
    pin(registry, snapshot)
    with pytest.raises(r.RegistryError, match="history_registry_already_reserved"):
        r.HistoryRegistry.initialize(history)
    path = registry.runtime.path(r.DATABASE_REFERENCE)
    path.unlink()
    with pytest.raises(r.RegistryError, match="history_registry_missing"):
        r.HistoryRegistry(h.HistoryStore(history.runtime, existing=True)).proof()
    decision = registry.assess_removal(snapshot.receipt.relative_reference)
    assert decision.required is None and decision.remove_allowed is False
    assert decision.reason == "history_registry_missing"
    with pytest.raises(r.RegistryError, match="history_registry_already_reserved"):
        r.HistoryRegistry.initialize(history)
    assert not path.exists()


def test_retention_derives_required_set_and_preserves_retain_publish_interval(
    registry: r.HistoryRegistry,
) -> None:
    snapshot = frozen(registry.history)
    pin(registry, snapshot)
    before = {p: p.read_bytes() for p in registry.runtime.root.rglob("*.bin")}
    for receipt in registry.proof().required:
        decision = registry.assess_removal(receipt.relative_reference)
        assert decision.required is True
        assert decision.reason == "required_history_evidence" and not decision.remove_allowed
    # A retained source without any manifest cannot be proven disposable.
    retained = registry.history.retain(b"fictional raw evidence awaiting manifest publication")
    decision = registry.assess_removal(retained.reference)
    assert decision.required is False
    assert decision.reason == "publication_liveness_unknown" and not decision.remove_allowed
    assert all(p.read_bytes() == raw for p, raw in before.items())
    assert registry.history.evidence.read(retained.receipt()).startswith(b"fictional raw")
    assert not maintain_runtime(registry.history.runtime).actions
    assert registry.replay("fictional-run-1") == snapshot


@pytest.mark.parametrize("target", ["raw", "manifest"])
@pytest.mark.parametrize("damage", ["missing", "corrupt", "hardlink"])
def test_damaged_required_inputs_refuse_proof_replay_and_deletion(
    registry: r.HistoryRegistry,
    target: str,
    damage: str,
) -> None:
    snapshot = frozen(registry.history)
    pin(registry, snapshot)
    receipt = (
        snapshot.receipt
        if target == "manifest"
        else snapshot.manifest.envelope.sources[0].raw.receipt()
    )
    path = registry.runtime.path(receipt.relative_reference)
    if damage == "missing":
        path.unlink()
    elif damage == "corrupt":
        path.write_bytes(b"fictional damaged input")
    else:
        os.link(path, registry.runtime.root / "unexpected-alias.bin")
    for operation in (registry.proof, lambda: registry.replay("fictional-run-1")):
        with pytest.raises(EvidenceError):
            operation()
    decision = registry.assess_removal(snapshot.receipt.relative_reference)
    assert decision.required is None and not decision.remove_allowed
    # Nothing repairs, replaces, or removes the damaged evidence.
    assert path.exists() == (damage != "missing")
    if damage == "corrupt":
        assert path.read_bytes() == b"fictional damaged input"


@pytest.mark.parametrize(
    "sql,expected",
    [
        ("PRAGMA user_version=999", "incompatible_history_registry_schema"),
        ("CREATE TABLE unexpected (value TEXT)", "incompatible_history_registry_schema"),
        ("DELETE FROM required_history", "history_registry_state_mismatch"),
        ("UPDATE required_history SET document='{}'", "invalid_history_dependency"),
        ("UPDATE required_history SET sha256='incorrect'", "history_registry_identity_mismatch"),
        ("UPDATE required_history SET dependency_id='other'", "history_registry_identity_mismatch"),
        ("UPDATE required_history SET sequence=2", "history_registry_identity_mismatch"),
        ("UPDATE registry_state SET tip='incorrect'", "history_registry_state_mismatch"),
    ],
)
def test_registry_schema_identity_and_omission_damage(
    registry: r.HistoryRegistry,
    sql: str,
    expected: str,
) -> None:
    snapshot = frozen(registry.history)
    pin(registry, snapshot)
    with sqlite3.connect(registry.runtime.path(r.DATABASE_REFERENCE)) as connection:
        connection.execute(sql)
    with pytest.raises(r.RegistryError, match=expected):
        registry.proof()
    decision = registry.assess_removal(snapshot.receipt.relative_reference)
    assert decision.required is None and decision.reason == expected
    assert not decision.remove_allowed


@pytest.mark.parametrize("damage", ["corrupt", "hardlink", "directory"])
def test_invalid_registry_files_are_never_initialized_or_replaced(
    registry: r.HistoryRegistry,
    damage: str,
) -> None:
    path = registry.runtime.path(r.DATABASE_REFERENCE)
    if damage == "corrupt":
        path.write_bytes(b"fictional invalid sqlite bytes")
    elif damage == "hardlink":
        os.link(path, registry.runtime.root / "registry-alias")
    else:
        path.unlink()
        path.mkdir()
    with pytest.raises(EvidenceError):
        registry.proof()
    with pytest.raises(r.RegistryError, match="history_registry_already_reserved"):
        r.HistoryRegistry.initialize(registry.history)
    assert registry.assess_removal("evidence-bytes-v1/objects/unknown.bin").required is None


@pytest.mark.parametrize("damage", ["missing", "corrupt", "hardlink"])
def test_adopted_coordination_loss_refuses_writers_and_retention(
    registry: r.HistoryRegistry,
    damage: str,
) -> None:
    path = registry.runtime.path(LOCK_NAME)
    if damage == "missing":
        path.unlink()
    elif damage == "corrupt":
        path.write_bytes(b"invalid lock identity")
    else:
        os.link(path, registry.runtime.root / "lock-alias")
    with pytest.raises(EvidenceError):
        registry.history.retain(b"fictional must not publish")
    assert registry.assess_removal("arbitrary.bin").required is None
    assert path.exists() == (damage != "missing")


def test_selection_mismatch_and_invalid_ids_do_not_register(registry: r.HistoryRegistry) -> None:
    snapshot = frozen(registry.history)
    document = snapshot.manifest.envelope.selection.model_dump(mode="json")
    document["known_at"] = "2026-01-09T12:00:00Z"
    other = h.Selection.model_validate_json(json.dumps(document))
    with pytest.raises(h.HistoryError, match="incompatible_history_selection"):
        registry.register("mismatched-selection", snapshot.receipt, expected=other)
    with pytest.raises(r.RegistryError, match="invalid_history_dependency"):
        pin(registry, snapshot, "../invalid")
    assert not registry.proof().dependencies


def test_capacity_refusal_rolls_back_without_losing_registered_history(
    registry: r.HistoryRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = frozen(registry.history)
    pin(registry, first)
    document = first.manifest.envelope.model_dump(mode="json")
    document["selection"]["calendar_evidence"] = "x" * 1024
    for context in document["selection"]["series"]:
        context["permission_scope"] = "y" * 1024
    for source, context in zip(document["sources"], document["selection"]["series"], strict=True):
        source["context"] = context
    large = registry.history.publish(h.Envelope.model_validate_json(json.dumps(document)))
    before = registry.proof()
    size = registry.runtime.path(r.DATABASE_REFERENCE).stat().st_size
    monkeypatch.setattr(r, "MAX_DATABASE_BYTES", size)
    with pytest.raises(r.RegistryError, match="history_registry_database_failed"):
        pin(registry, large, "large")
    assert registry.proof() == before
    assert registry.replay("fictional-run-1") == first


def test_unknown_registry_inputs_do_not_clear_unrelated_replay(registry: r.HistoryRegistry) -> None:
    first = frozen(registry.history)
    second = frozen(registry.history, diagnostic=True)
    pin(registry, first, "first")
    pin(registry, second, "second")
    registry.runtime.path(second.receipt.relative_reference).unlink()
    assert registry.replay("first") == first
    with pytest.raises(EvidenceError, match="evidence_missing"):
        registry.replay("second")
    assert registry.assess_removal(first.receipt.relative_reference).required is None


@pytest.mark.parametrize(
    "phase", ["register_verified", "register_before_commit", "register_committed"]
)
def test_abrupt_registration_preserves_atomic_dependencies_and_releases_lock(
    registry: r.HistoryRegistry,
    tmp_path: Path,
    phase: str,
) -> None:
    snapshot = frozen(registry.history)
    pin(registry, snapshot, "prior")
    document = r.Dependency(
        dependency_id="new",
        manifest=h.RawReference.from_receipt(snapshot.receipt),
        selection=snapshot.manifest.envelope.selection,
    )
    input_path = tmp_path / "fictional-dependency.json"
    input_path.write_text(document.model_dump_json(), encoding="utf-8")
    code = """
import os, sys
from pathlib import Path
from prosper.history import HistoryStore
from prosper.evidence import RuntimeBoundary
import prosper.history_registry as r
store=HistoryStore(RuntimeBoundary(Path(sys.argv[1]),Path(sys.argv[2]),'synthetic'),existing=True)
entry=r.Dependency.model_validate_json(Path(sys.argv[3]).read_bytes())
def crash(name):
    if name==sys.argv[4]: os._exit(71)
r._step=crash
r.HistoryRegistry(store).register(entry.dependency_id,entry.manifest.receipt(),expected=entry.selection)
"""
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(registry.history.runtime.root),
            str(ROOT),
            str(input_path),
            phase,
        ],
        capture_output=True,
    )
    assert child.returncode == 71, child.stderr.decode()
    reopened = r.HistoryRegistry(h.HistoryStore(registry.history.runtime, existing=True))
    assert [e.dependency_id for e in reopened.proof().dependencies] == (
        ["prior", "new"] if phase == "register_committed" else ["prior"]
    )
    assert reopened.replay("prior") == snapshot
    pin(reopened, snapshot, "retry-after-exit")


@pytest.mark.parametrize("phase", ["initialize_before_commit", "initialize_committed"])
def test_abrupt_initialization_cannot_reset_reserved_state(
    history: h.HistoryStore,
    phase: str,
) -> None:
    code = """
import os, sys
from pathlib import Path
from prosper.history import HistoryStore
from prosper.evidence import RuntimeBoundary
import prosper.history_registry as r
store=HistoryStore(RuntimeBoundary(Path(sys.argv[1]),Path(sys.argv[2]),'synthetic'),existing=True)
def crash(name):
    if name==sys.argv[3]: os._exit(72)
r._step=crash
r.HistoryRegistry.initialize(store)
"""
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(history.runtime.root),
            str(ROOT),
            phase,
        ],
        capture_output=True,
    )
    assert child.returncode == 72, child.stderr.decode()
    registry = r.HistoryRegistry(history)
    if phase == "initialize_committed":
        assert not registry.proof().dependencies
    else:
        with pytest.raises(EvidenceError):
            registry.proof()
    with pytest.raises(r.RegistryError, match="history_registry_already_reserved"):
        r.HistoryRegistry.initialize(history)


def test_real_process_lock_serializes_publication_registration_and_retention(
    registry: r.HistoryRegistry,
    tmp_path: Path,
) -> None:
    snapshot = frozen(registry.history)
    ready = tmp_path / "lock-ready"
    entry_path = tmp_path / "pending-dependency.json"
    entry_path.write_text(
        r.Dependency(
            dependency_id="fictional-run-1",
            manifest=h.RawReference.from_receipt(snapshot.receipt),
            selection=snapshot.manifest.envelope.selection,
        ).model_dump_json(),
        encoding="utf-8",
    )
    code = """
import sys
from pathlib import Path
from prosper.evidence import RuntimeBoundary
from prosper.history import HistoryStore
import prosper.history_registry as r
store=HistoryStore(RuntimeBoundary(Path(sys.argv[1]),Path(sys.argv[2]),'synthetic'),existing=True)
entry=r.Dependency.model_validate_json(Path(sys.argv[4]).read_bytes())
def pause(name):
    if name=='register_before_commit':
        Path(sys.argv[3]).write_text('ready')
        sys.stdin.buffer.read(1)
r._step=pause
r.HistoryRegistry(store).register(entry.dependency_id,entry.manifest.receipt(),expected=entry.selection)
"""
    process = subprocess.Popen(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(registry.history.runtime.root),
            str(ROOT),
            str(ready),
            str(entry_path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        with pytest.raises(EvidenceError, match="history_runtime_busy"):
            registry.history.publish(snapshot.manifest.envelope)
        with pytest.raises(EvidenceError, match="history_runtime_busy"):
            registry.history.retain(b"fictional in flight")
        with pytest.raises(EvidenceError, match="history_runtime_busy"):
            pin(registry, snapshot)
        decision = registry.assess_removal(snapshot.receipt.relative_reference)
        assert decision.required is None and decision.reason == "history_runtime_busy"
        assert not decision.remove_allowed
    finally:
        process.communicate(b"x", timeout=10)
    assert process.returncode == 0
    pin(registry, snapshot)
    assert registry.replay("fictional-run-1") == snapshot


def test_same_process_coordination_is_non_reentrant_and_conservative(
    registry: r.HistoryRegistry,
) -> None:
    with history_writer(registry.runtime):
        assert registry.assess_removal("anything.bin").reason == "history_runtime_busy"


def test_offline_process_replay_includes_required_facts(registry: r.HistoryRegistry) -> None:
    snapshot = frozen(registry.history)
    pin(registry, snapshot)
    code = """
import sys
from pathlib import Path
from prosper.history import HistoryStore, canonical_bytes
from prosper.evidence import RuntimeBoundary
from prosper.history_registry import HistoryRegistry
store=HistoryStore(RuntimeBoundary(Path(sys.argv[1]),Path(sys.argv[2]),'synthetic'),existing=True)
sys.stdout.buffer.write(canonical_bytes(HistoryRegistry(store).replay('fictional-run-1').manifest))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(registry.history.runtime.root),
            str(ROOT),
        ],
        capture_output=True,
        check=True,
    )
    assert result.stdout == h.canonical_bytes(snapshot.manifest)
    assert (
        asdict(registry.assess_removal(snapshot.receipt.relative_reference))["remove_allowed"]
        is False
    )
