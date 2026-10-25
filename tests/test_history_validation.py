"""Fictional-clock persistent policy, bounded dispatch and recovery qualification."""

import json
import os
import runpy
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

import pytest
from pydantic import ValidationError

from prosper import history as h
from prosper import history_recovery as b
from prosper import history_refresh as f
from prosper import history_registry as r
from prosper import history_validation as v
from prosper.evidence import EvidenceError, RuntimeBoundary

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/qualify_validation.py"
fixture = runpy.run_path(str(SCRIPT))
request = cast(Callable[..., f.Request], fixture["request"])
settings = cast(Callable[[], v.Settings], fixture["enabled_settings"])


class FixtureProvider(f.Provider, Protocol):
    calls: list[f.Range]


provider_factory = cast(Callable[[f.Request], FixtureProvider], fixture["provider_factory"])


def boundary(path: Path) -> RuntimeBoundary:
    return RuntimeBoundary(path, ROOT, "synthetic")


@pytest.fixture
def policy(tmp_path: Path) -> v.ValidationStore:
    registry = r.HistoryRegistry.initialize(h.HistoryStore(boundary(tmp_path / "history")))
    return v.ValidationStore.initialize(registry, now="2026-03-01T12:00:00Z")


def enable(policy: v.ValidationStore) -> v.State:
    return policy.configure(
        "enable", expected_generation=1, now="2026-03-01T12:01:00Z", settings=settings()
    )


def test_default_never_persists_and_clock_advances_make_zero_calls(
    policy: v.ValidationStore,
) -> None:
    original = policy.current()
    assert original.generation == 1 and not original.settings.enabled
    assert original.next_due is None and original.settings.cadence_seconds is None
    provider = provider_factory(request())
    for now in ("2026-03-01T12:00:00Z", "2026-03-02T12:00:00Z", "2026-10-01T12:00:00Z"):
        reopened = v.ValidationStore(
            r.HistoryRegistry(h.HistoryStore(policy.registry.history.runtime, existing=True))
        )
        assert reopened.current() == original
        assert reopened.dispatch(now=now, provider=provider).status == "off"
    assert not provider.calls and policy.current() == original


def test_explicit_enable_due_once_disable_and_reenable_do_not_catch_up(
    policy: v.ValidationStore,
) -> None:
    enabled = enable(policy)
    assert enabled.next_due == "2026-03-01T12:02:00Z"
    provider = provider_factory(request())
    assert policy.dispatch(now="2026-03-01T12:01:59Z", provider=provider).status == "not_due"
    assert not provider.calls
    done = policy.dispatch(now="2026-03-01T12:02:00Z", provider=provider)
    assert done.status == "complete" and len(provider.calls) == 1
    assert done.state.next_due == "2026-03-01T12:03:00Z"
    assert done.state.last_successful_dispatch_at == "2026-03-01T12:02:00Z"
    assert done.refresh is not None and done.refresh.format == "synthetic-history-refresh-v2"
    assert done.refresh.dispatch_event is not None
    assert done.refresh.freshness[0].last_successful_broader_validation == "2026-03-01T12:02:00Z"
    assert policy.dispatch(now="2026-03-01T12:02:00Z", provider=provider).status == "not_due"
    # Missing many former due times yields exactly one validation and a new future anchor.
    late = policy.dispatch(now="2026-03-02T12:00:00Z", provider=provider)
    assert late.status == "complete" and len(provider.calls) == 2
    assert late.state.next_due == "2026-03-02T12:01:00Z"
    disabled = policy.configure(
        "off",
        expected_generation=late.state.generation,
        now="2026-03-02T12:00:30Z",
        settings=v.Settings(),
    )
    assert disabled.next_due is None
    assert policy.dispatch(now="2026-03-03T12:00:00Z", provider=provider).status == "off"
    assert len(provider.calls) == 2
    again = policy.configure(
        "again",
        expected_generation=disabled.generation,
        now="2026-03-03T12:00:00Z",
        settings=settings(),
    )
    assert again.next_due == "2026-03-03T12:01:00Z"
    assert again.last_successful_dispatch_at == late.state.last_successful_dispatch_at
    assert policy.dispatch(now="2026-03-03T12:00:00Z", provider=provider).status == "not_due"


def test_manual_requested_and_targeted_remain_independent_while_off(
    policy: v.ValidationStore,
) -> None:
    before = policy.current()
    req = request(count=3)
    provider = provider_factory(req)
    first = f.refresh(policy.registry, "manual-base", req, provider)
    assert first.complete and len(provider.calls) == 1
    extended = request(cache=("manual-base",))

    class Changed:
        calls = 0

        def fetch(self, interval: f.Range) -> bytes:
            self.calls += 1
            raw = json.loads(provider_factory(extended).fetch(interval))
            if self.calls == 1:
                raw["observations"][0]["dividend"]["text"] = "2.00"
            return json.dumps(raw).encode()

    changed = Changed()
    result = f.refresh(policy.registry, "targeted-off", extended, changed)
    assert result.complete and changed.calls == 2
    assert policy.current() == before
    manual = request(manual=("FICTION-A",))
    assert f.refresh(policy.registry, "manual-full", manual, provider_factory(manual)).complete
    assert policy.current() == before


@pytest.mark.parametrize("failure", ["empty", "partial", "transport"])
def test_failure_retains_last_success_and_bounds_the_next_attempt(
    policy: v.ValidationStore, failure: str
) -> None:
    enable(policy)
    good = policy.dispatch(now="2026-03-01T12:02:00Z", provider=provider_factory(request()))
    baseline = provider_factory(request())

    class Broken:
        def fetch(self, interval: f.Range) -> bytes:
            if failure == "transport":
                raise RuntimeError("fictional transport error")
            raw = json.loads(baseline.fetch(interval))
            raw.update(outcome=failure, reason="stipulated response failure")
            if failure == "empty":
                raw["observations"] = []
            return json.dumps(raw).encode()

    broken = Broken()
    result = policy.dispatch(now="2026-03-01T12:03:00Z", provider=broken)
    assert result.status == "incomplete"
    assert result.state.last_successful_dispatch_at == good.state.last_successful_dispatch_at
    assert result.state.next_due == "2026-03-01T12:04:00Z"
    assert policy.dispatch(now="2026-03-01T12:03:00Z", provider=broken).status == "not_due"
    assert result.refresh is not None and not result.refresh.complete
    assert result.refresh.freshness[0].last_successful_broader_validation is None
    assert policy.current() == result.state


def test_settings_staleness_conflicts_scope_and_clock_guards(policy: v.ValidationStore) -> None:
    enabled = enable(policy)
    assert enable(policy) == enabled  # Same command receipt, including original generation.
    with pytest.raises(v.ValidationPolicyError, match="conflict"):
        policy.configure(
            "enable",
            expected_generation=enabled.generation,
            now="2026-03-01T12:02:00Z",
            settings=v.Settings(),
        )
    with pytest.raises(v.ValidationPolicyError):
        policy.configure(
            "stale", expected_generation=1, now="2026-03-01T12:02:00Z", settings=v.Settings()
        )
    with pytest.raises(v.ValidationPolicyError, match="clock_regressed"):
        policy.dispatch(now="2026-03-01T12:00:00Z", provider=provider_factory(request()))
    for doc in (
        {"enabled": True},
        {"enabled": False, "cadence_seconds": 60},
        {"enabled": True, "cadence_seconds": 0, "request": request().model_dump(mode="json")},
        {"enabled": True, "cadence_seconds": 60, "request": request().model_dump(mode="json")},
    ):
        with pytest.raises(ValidationError):
            v.Settings.model_validate_json(json.dumps(doc))


@pytest.mark.parametrize(
    "damage",
    [
        "missing-db",
        "lost-directory",
        "missing-marker",
        "corrupt-db",
        "corrupt-marker",
        "db-alias",
        "marker-alias",
        "schema",
        "omitted-event",
    ],
)
def test_damaged_policy_never_resets_or_dispatches_or_qualifies_backup(
    policy: v.ValidationStore, tmp_path: Path, damage: str
) -> None:
    enable(policy)
    database = policy.runtime.path(v.DATABASE_REFERENCE)
    marker = policy.runtime.path(v.ADOPTION_MARKER)
    if damage == "missing-db":
        database.unlink()
    elif damage == "lost-directory":
        policy.runtime.path(v.NAMESPACE).rename(policy.runtime.path("lost-policy-evidence"))
    elif damage == "missing-marker":
        marker.unlink()
    elif damage == "corrupt-db":
        database.write_bytes(b"fictional corruption")
    elif damage == "corrupt-marker":
        marker.write_bytes(b"fictional corruption")
    elif damage == "db-alias":
        os.link(database, tmp_path / "db-alias")
    elif damage == "marker-alias":
        os.link(marker, tmp_path / "marker-alias")
    else:
        with sqlite3.connect(database) as connection:
            connection.execute(
                "PRAGMA user_version=99"
                if damage == "schema"
                else "DELETE FROM policy_events WHERE sequence=2"
            )
    provider = provider_factory(request())
    with pytest.raises((EvidenceError, ValueError)):
        policy.current()
    with pytest.raises((EvidenceError, ValueError)):
        policy.dispatch(now="2026-03-01T12:02:00Z", provider=provider)
    with pytest.raises(v.ValidationPolicyError, match="already_reserved"):
        v.ValidationStore.initialize(policy.registry, now="2026-03-01T12:02:00Z")
    with pytest.raises(b.HistoryRecoveryError):
        b.backup(
            policy.registry, boundary(tmp_path / "refused-backup"), candidate_id="damaged-policy"
        )
    assert not provider.calls


@pytest.mark.parametrize("enabled", [False, True])
def test_policy_aware_backup_restore_preserves_state_without_dispatch(
    policy: v.ValidationStore, tmp_path: Path, enabled: bool
) -> None:
    if enabled:
        enable(policy)
        policy.dispatch(now="2026-03-01T12:02:00Z", provider=provider_factory(request()))
    expected = policy.current()
    saved, destination = boundary(tmp_path / "backup"), boundary(tmp_path / "restored")
    manifest = b.backup(policy.registry, saved, candidate_id="policy-backup")
    assert manifest.format == "prosper-required-history-backup-v2"
    assert manifest.validation_policy is not None and manifest.validation_marker is not None
    assert b.inspect_backup(saved) == manifest
    b.restore(saved, destination)
    reopened = v.ValidationStore(r.HistoryRegistry(h.HistoryStore(destination, existing=True)))
    assert reopened.current() == expected
    with pytest.raises(v.ValidationPolicyError, match="already_reserved"):
        v.ValidationStore.initialize(reopened.registry, now="2026-03-02T12:00:00Z")
    assert reopened.registry.proof() == policy.registry.proof()


@pytest.mark.parametrize("target", ["database", "marker", "omitted"])
def test_backup_requires_policy_and_marker_integrity(
    policy: v.ValidationStore, tmp_path: Path, target: str
) -> None:
    saved = boundary(tmp_path / "backup")
    b.backup(policy.registry, saved, candidate_id="integrity")
    if target == "omitted":
        path = saved.path(b.MANIFEST_NAME)
        doc = json.loads(path.read_bytes())
        doc.pop("validation_policy")
        path.write_bytes(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode())
    else:
        name = v.DATABASE_REFERENCE if target == "database" else v.ADOPTION_MARKER
        saved.path(f"{h.VERSION}/{name}").unlink()
    with pytest.raises(b.HistoryRecoveryError):
        b.inspect_backup(saved)
    with pytest.raises(b.HistoryRecoveryError):
        b.restore(saved, boundary(tmp_path / "refused"))


CHILD = """
import os,runpy,sys,time
from pathlib import Path
from prosper import history as h,history_registry as r,history_validation as v
from prosper.evidence import RuntimeBoundary
root,runtime,phase,signal,release = sys.argv[1:]
fixture=runpy.run_path(str(Path(root)/'scripts/qualify_validation.py'))
registry=r.HistoryRegistry(h.HistoryStore(RuntimeBoundary(Path(runtime),Path(root),'synthetic'),existing=True))
def hook(name):
    if name==phase:
        Path(signal).write_text('paused')
        if release=='die': os._exit(75)
        while not Path(release).exists(): time.sleep(0.02)
v._step=hook
if phase.startswith('initialize'):
    v.ValidationStore.initialize(registry,now='2026-03-01T12:00:00Z')
else:
    v.ValidationStore(registry).dispatch(now='2026-03-01T12:02:00Z',provider=fixture['provider_factory'](fixture['request']()))
"""


@pytest.mark.parametrize("phase", ["dispatch_pending", "refresh_committed", "dispatch_completed"])
def test_real_process_death_finalizes_or_marks_interruption_without_reacquisition(
    policy: v.ValidationStore, tmp_path: Path, phase: str
) -> None:
    enable(policy)
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            CHILD,
            str(ROOT),
            str(policy.registry.history.runtime.root),
            phase,
            str(tmp_path / "signal"),
            "die",
        ],
        capture_output=True,
        timeout=30,
    )
    assert process.returncode == 75, process.stderr.decode()
    provider = provider_factory(request())
    result = policy.dispatch(now="2026-03-01T12:02:30Z", provider=provider)
    assert not provider.calls
    assert (
        result.status
        == {
            "dispatch_pending": "interrupted",
            "refresh_committed": "complete",
            "dispatch_completed": "not_due",
        }[phase]
    )
    assert policy.current().pending is None
    assert (policy.current().last_successful_dispatch_at is None) == (phase == "dispatch_pending")


@pytest.mark.parametrize(
    "phase", ["initialize_reserved", "initialize_before_commit", "initialize_committed"]
)
def test_interrupted_initialization_never_invents_off_state(tmp_path: Path, phase: str) -> None:
    registry = r.HistoryRegistry.initialize(h.HistoryStore(boundary(tmp_path / "history")))
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            CHILD,
            str(ROOT),
            str(registry.history.runtime.root),
            phase,
            str(tmp_path / "signal"),
            "die",
        ],
        capture_output=True,
        timeout=30,
    )
    assert process.returncode == 75, process.stderr.decode()
    store = v.ValidationStore(registry)
    if phase == "initialize_committed":
        assert not store.current().settings.enabled
    else:
        with pytest.raises(EvidenceError):
            store.current()
    with pytest.raises(v.ValidationPolicyError, match="already_reserved"):
        v.ValidationStore.initialize(registry, now="2026-03-01T12:03:00Z")


def test_pending_dispatch_blocks_competing_policy_change_and_backup(
    policy: v.ValidationStore, tmp_path: Path
) -> None:
    enabled = enable(policy)
    signal, release = tmp_path / "signal", tmp_path / "release"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            CHILD,
            str(ROOT),
            str(policy.registry.history.runtime.root),
            "dispatch_pending",
            str(signal),
            str(release),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 20
        while not signal.exists():
            assert process.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.02)
        with pytest.raises(EvidenceError, match="history_runtime_busy"):
            policy.configure(
                "off",
                expected_generation=enabled.generation,
                now="2026-03-01T12:02:00Z",
                settings=v.Settings(),
            )
        with pytest.raises(b.HistoryRecoveryError):
            b.backup(policy.registry, boundary(tmp_path / "busy-backup"), candidate_id="busy")
        release.write_text("continue")
        _, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr.decode()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    state = policy.current()
    off = policy.configure(
        "off",
        expected_generation=state.generation,
        now="2026-03-01T12:03:00Z",
        settings=v.Settings(),
    )
    provider = provider_factory(request())
    assert not off.settings.enabled
    assert policy.dispatch(now="2026-04-01T12:00:00Z", provider=provider).status == "off"
    assert not provider.calls


def test_deterministic_offline_installed_replay_inputs() -> None:
    first = subprocess.check_output([sys.executable, "-I", str(SCRIPT)])
    second = subprocess.check_output([sys.executable, "-I", str(SCRIPT)])
    assert first == second
    report = json.loads(first)
    assert report["default"]["status"] == "off" and report["restored_equal"]


def test_committed_trigger_requires_policy_even_if_both_markers_are_lost(
    policy: v.ValidationStore, tmp_path: Path
) -> None:
    enable(policy)
    policy.dispatch(now="2026-03-01T12:02:00Z", provider=provider_factory(request()))
    policy.runtime.path(v.NAMESPACE).rename(policy.runtime.path("retained-lost-policy"))
    policy.runtime.path(v.ADOPTION_MARKER).unlink()
    with pytest.raises(v.ValidationPolicyError, match="already_reserved"):
        v.ValidationStore.initialize(policy.registry, now="2026-03-01T12:03:00Z")
    with pytest.raises(b.HistoryRecoveryError):
        b.backup(policy.registry, boundary(tmp_path / "refused"), candidate_id="missing-policy")


@pytest.mark.parametrize("phase", ["dispatch_pending", "refresh_committed"])
def test_disabling_an_interrupted_dispatch_cancels_catch_up(
    policy: v.ValidationStore, tmp_path: Path, phase: str
) -> None:
    enable(policy)
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            CHILD,
            str(ROOT),
            str(policy.registry.history.runtime.root),
            phase,
            str(tmp_path / "signal"),
            "die",
        ],
        capture_output=True,
        timeout=30,
    )
    assert process.returncode == 75, process.stderr.decode()
    pending = policy.current()
    assert pending.pending is not None
    policy.configure(
        "off-after-crash",
        expected_generation=pending.generation,
        now="2026-03-01T12:02:30Z",
        settings=v.Settings(),
    )
    provider = provider_factory(request())
    assert policy.dispatch(now="2026-04-01T12:00:00Z", provider=provider).status == "off"
    assert not provider.calls
    assert policy.current().last_outcome == "cancelled"


@pytest.mark.parametrize("phase", ["backup_policy", "restore_published"])
def test_actual_policy_aware_backup_restore_death_preserves_prior_state(
    policy: v.ValidationStore, tmp_path: Path, phase: str
) -> None:
    enable(policy)
    saved, destination = boundary(tmp_path / "backup"), boundary(tmp_path / "restored")
    if phase == "restore_published":
        b.backup(policy.registry, saved, candidate_id="before-crash")
    script = """
import os,sys
from pathlib import Path
from prosper import history as h, history_registry as r, history_recovery as b
from prosper.evidence import RuntimeBoundary
root,runtime,saved,destination,phase=sys.argv[1:]
def boundary(p): return RuntimeBoundary(Path(p),Path(root),'synthetic')
def hook(name):
    if name==phase: os._exit(76)
b._step=hook
if phase=='backup_policy':
    b.backup(r.HistoryRegistry(h.HistoryStore(boundary(runtime),existing=True)),boundary(saved),candidate_id='crash')
else:
    b.restore(boundary(saved),boundary(destination))
"""
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(ROOT),
            str(policy.registry.history.runtime.root),
            str(saved.root),
            str(destination.root),
            phase,
        ],
        capture_output=True,
        timeout=30,
    )
    assert process.returncode == 76, process.stderr.decode()
    assert policy.current().settings.enabled
    if phase == "backup_policy":
        with pytest.raises(b.HistoryRecoveryError):
            b.inspect_backup(saved)
        b.backup(policy.registry, boundary(tmp_path / "new-backup"), candidate_id="retry")
    else:
        with pytest.raises(h.HistoryError, match="history_restore_in_progress"):
            h.HistoryStore(destination, existing=True)
        retry = boundary(tmp_path / "new-destination")
        b.restore(saved, retry)
        restored = v.ValidationStore(r.HistoryRegistry(h.HistoryStore(retry, existing=True)))
        assert restored.current() == policy.current()


def test_event_capacity_failure_preserves_prior_policy(
    policy: v.ValidationStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    prior = policy.current()
    monkeypatch.setattr(v, "MAX_EVENTS", 1)
    with pytest.raises(v.ValidationPolicyError, match="size_exceeded"):
        enable(policy)
    assert policy.current() == prior


def test_expired_scope_refuses_without_provider_calls(policy: v.ValidationStore) -> None:
    enable(policy)
    provider = provider_factory(request())
    with pytest.raises(v.ValidationPolicyError, match="scope_refused"):
        policy.dispatch(now="2027-01-01T12:00:00Z", provider=provider)
    assert not provider.calls and policy.current().last_successful_dispatch_at is None


def test_infrastructure_refusal_records_no_success_and_future_retry_only(
    policy: v.ValidationStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    enable(policy)
    provider = provider_factory(request())

    def fail(raw: bytes) -> object:
        raise EvidenceError("stipulated_evidence_write_failure")

    monkeypatch.setattr(policy.registry.history.evidence, "publish", fail)
    result = policy.dispatch(now="2026-03-01T12:02:00Z", provider=provider)
    assert result.status == "refused" and result.state.last_successful_dispatch_at is None
    assert result.state.next_due == "2026-03-01T12:03:00Z"
    assert policy.dispatch(now="2026-03-01T12:02:00Z", provider=provider).status == "not_due"
    assert len(provider.calls) == 1


@pytest.mark.parametrize("phase", ["event_before_commit", "event_committed"])
def test_actual_opt_out_transaction_death_and_identical_command_retry(
    policy: v.ValidationStore, tmp_path: Path, phase: str
) -> None:
    enabled = enable(policy)
    script = """
import os,sys
from pathlib import Path
from prosper import history as h,history_registry as r,history_validation as v
from prosper.evidence import RuntimeBoundary
root,runtime,phase=sys.argv[1:]
def hook(name):
    if name==phase: os._exit(77)
v._step=hook
registry=r.HistoryRegistry(h.HistoryStore(RuntimeBoundary(Path(runtime),Path(root),'synthetic'),existing=True))
v.ValidationStore(registry).configure('off-transaction',expected_generation=2,now='2026-03-01T12:01:30Z',settings=v.Settings())
"""
    process = subprocess.run(
        [sys.executable, "-c", script, str(ROOT), str(policy.registry.history.runtime.root), phase],
        capture_output=True,
        timeout=30,
    )
    assert process.returncode == 77, process.stderr.decode()
    assert policy.current().settings.enabled == (phase == "event_before_commit")
    off = policy.configure(
        "off-transaction",
        expected_generation=enabled.generation,
        now="2026-03-01T12:01:30Z",
        settings=v.Settings(),
    )
    assert not off.settings.enabled
    provider = provider_factory(request())
    assert policy.dispatch(now="2026-03-02T12:00:00Z", provider=provider).status == "off"
    assert not provider.calls
