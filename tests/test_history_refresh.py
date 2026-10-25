"""Independent fictional calendar/request/return cases and durable refresh failures."""

import json
import runpy
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, cast

import pytest
from pydantic import ValidationError

from prosper import history as h
from prosper import history_recovery as b
from prosper import history_refresh as f
from prosper import history_registry as r
from prosper.evidence import EvidenceError, RuntimeBoundary
from prosper.history_coordination import history_writer

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/qualify_refresh.py"
fixture = runpy.run_path(str(SCRIPT))
request = cast(Callable[..., f.Request], fixture["fictional_request"])


class FixtureProvider(f.Provider, Protocol):
    calls: list[f.Range]


provider_factory = cast(Callable[[f.Request], FixtureProvider], fixture["FictionalProvider"])


def boundary(path: Path) -> RuntimeBoundary:
    return RuntimeBoundary(path, ROOT, "synthetic")


@pytest.fixture
def registry(tmp_path: Path) -> r.HistoryRegistry:
    return r.HistoryRegistry.initialize(h.HistoryStore(boundary(tmp_path / "history")))


class Altered:
    def __init__(self, req: f.Request, alter: Callable[[dict[str, Any], int], None]) -> None:
        self.fixture = provider_factory(req)
        self.alter = alter

    @property
    def calls(self) -> list[f.Range]:
        return self.fixture.calls

    def fetch(self, interval: f.Range) -> bytes:
        document = json.loads(self.fixture.fetch(interval))
        self.alter(document, len(self.calls))
        return json.dumps(document).encode()


def initial(registry: r.HistoryRegistry, *, count: int = 3) -> f.Record:
    req = request(count=count)
    return f.refresh(registry, "initial", req, provider_factory(req))


def test_repeat_restart_month_later_boundary_return_and_distinct_success_times(
    registry: r.HistoryRegistry,
) -> None:
    first_request = request(count=3)
    first_provider = provider_factory(first_request)
    first = f.refresh(registry, "initial", first_request, first_provider)
    assert first.complete
    assert [c.sessions for c in first_provider.calls] == [
        ("2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07")
    ]
    old_bytes = registry.history.evidence.read(first.snapshot.receipt())
    reopened = r.HistoryRegistry(h.HistoryStore(registry.history.runtime, existing=True))
    repeat = provider_factory(first_request)
    assert f.refresh(reopened, "initial", first_request, repeat) == first
    assert repeat.calls == []
    later = request(cache=("initial",), known_at="2026-03-02T12:00:00Z")
    provider = provider_factory(later)
    result = f.refresh(reopened, "month-later", later, provider)
    assert [c.sessions for c in provider.calls] == [("2026-01-07", "2026-02-02", "2026-02-03")]
    assert result.complete and len(result.returns) == 5
    first_new = result.returns[3]
    assert (first_new.predecessor, first_new.numerator, first_new.denominator) == (
        "2026-01-07",
        "1",
        "10",
    )
    fresh = result.freshness[0]
    assert fresh.last_successful_refresh == "2026-03-02T12:00:00Z"
    assert fresh.last_successful_broader_validation == "2026-03-01T12:00:00Z"
    assert fresh.broader_sessions == ("2026-01-05", "2026-01-06", "2026-01-07")
    another = request(cache=("month-later",), known_at="2026-03-03T12:00:00Z")
    zero = provider_factory(another)
    reused = f.refresh(reopened, "repeat", another, zero)
    assert reused.complete and not zero.calls and reused.freshness == result.freshness
    assert registry.history.evidence.read(first.snapshot.receipt()) == old_bytes
    assert reused.scheduled_validation == "Off / Never"


def test_leading_interior_tail_new_names_and_order_are_explicit(
    registry: r.HistoryRegistry,
) -> None:
    initial(registry)
    expanded = request(names=("FICTION-B", "FICTION-A"), cache=("initial",))
    provider = provider_factory(expanded)
    record = f.refresh(registry, "new-portfolio", expanded, provider)
    assert [(c.security_id, c.sessions) for c in provider.calls] == [
        (
            "FICTION-B",
            ("2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07", "2026-02-02", "2026-02-03"),
        ),
        ("FICTION-A", ("2026-01-07", "2026-02-02", "2026-02-03")),
    ]
    assert record.complete
    assert [x.security_id for x in record.freshness] == ["FICTION-B", "FICTION-A"]
    # A middle-only retained window exercises two disjoint missing intervals.
    whole = request()
    selected = whole.selection.model_copy(
        update={"sessions": ("2026-01-06",), "cutoff": "2026-01-06"}
    )
    middle = whole.model_copy(update={"selection": selected})
    f.refresh(registry, "middle", middle, provider_factory(middle))
    full = request(cache=("middle",))
    gap_provider = provider_factory(full)
    assert f.refresh(registry, "leading-tail", full, gap_provider).complete
    assert [c.sessions for c in gap_provider.calls] == [
        ("2026-01-02", "2026-01-05"),
        ("2026-01-06", "2026-01-07", "2026-02-02", "2026-02-03"),
    ]


def test_pure_planner_stipulates_interior_and_explicit_overlap() -> None:
    req = request()
    usable = {("FICTION-A", d) for d in ("2026-01-05", "2026-01-07", "2026-02-03")}
    assert [c.sessions for c in f.plan(req, usable)] == [
        ("2026-01-05", "2026-01-06"),
        ("2026-01-07", "2026-02-02"),
    ]
    doubled = req.model_copy(
        update={"policy": req.policy.model_copy(update={"overlap_sessions": 2})}
    )
    assert f.plan(doubled, usable)[1].sessions == ("2026-01-06", "2026-01-07", "2026-02-02")


def test_narrower_calendar_preserves_historical_broader_validation_scope(
    registry: r.HistoryRegistry,
) -> None:
    first = initial(registry, count=5)
    narrow = request(count=3, cache=("initial",), known_at="2026-03-02T12:00:00Z")
    narrow = narrow.model_copy(
        update={
            "calendar": narrow.calendar.model_copy(update={"sessions": narrow.selection.sessions})
        }
    )
    provider = provider_factory(narrow)
    record = f.refresh(registry, "narrower", narrow, provider)
    assert record.complete and not provider.calls
    assert record.freshness == first.freshness
    assert len(record.freshness[0].broader_sessions) == 5
    assert f.replay(registry, "narrower") == record


@pytest.mark.parametrize("change", ["split", "dividend", "price"])
def test_changed_boundary_action_or_price_triggers_full_window_not_mixed_append(
    registry: r.HistoryRegistry, change: str
) -> None:
    old = initial(registry)
    req = request(cache=("initial",))

    def alter(body: dict[str, Any], count: int) -> None:
        if count == 1:
            row = body["observations"][0]  # Predecessor/overlap, not first new return.
            if change == "price":
                row["adjusted_close"]["text"] = "130.0000"
            else:
                row["split_ratio" if change == "split" else "dividend"]["text"] = "2.00"

    provider = Altered(req, alter)
    record = f.refresh(registry, "revised", req, provider)
    assert record.complete
    assert len(provider.calls) == 2 and provider.calls[1].reason == "revision"
    assert provider.calls[1].sessions == (
        "2026-01-02",
        "2026-01-05",
        "2026-01-06",
        "2026-01-07",
        "2026-02-02",
        "2026-02-03",
    )
    assert record.attempts[0].changed_overlap
    assert record.freshness[0].broader_sessions == req.selection.sessions
    snapshot = registry.replay("revised")
    assert len(snapshot.manifest.envelope.sources) == 1
    assert f.replay(registry, "initial") == old


def test_changed_joining_predecessor_when_extending_lookback_revalidates_full_window(
    registry: r.HistoryRegistry,
) -> None:
    full = request()
    tail = full.model_copy(
        update={
            "selection": full.selection.model_copy(
                update={"sessions": ("2026-02-02", "2026-02-03")}
            )
        }
    )
    f.refresh(registry, "tail", tail, provider_factory(tail))
    req = request(cache=("tail",))

    def alter(body: dict[str, Any], count: int) -> None:
        if count == 1:
            body["observations"][-1]["split_ratio"]["text"] = "3.00"

    provider = Altered(req, alter)
    assert f.refresh(registry, "lookback-revision", req, provider).complete
    assert len(provider.calls) == 2 and provider.calls[1].reason == "revision"


@pytest.mark.parametrize(
    "field",
    [
        "provider",
        "dataset",
        "provider_symbol",
        "currency",
        "calendar",
        "timezone",
        "interval",
        "repair",
        "adjustment",
        "source_schema",
        "transform_version",
        "library_version",
        "permission_scope",
        "vintage",
        "captured_at",
    ],
)
def test_context_change_never_reuses_incompatible_cells(
    registry: r.HistoryRegistry, field: str
) -> None:
    initial(registry)
    req = request(cache=("initial",), known_at="2026-03-02T12:00:00Z")
    doc = req.model_dump(mode="json")
    doc["selection"]["series"][0][field] = (
        "2026-03-02T12:00:00Z" if field == "captured_at" else "changed-fictional-context"
    )
    changed = f.Request.model_validate_json(json.dumps(doc))
    provider = provider_factory(changed)
    if field in {"repair", "adjustment", "source_schema", "transform_version"}:
        with pytest.raises(f.RefreshError, match="refresh_unsupported_transform"):
            f.refresh(registry, "changed-context", changed, provider)
        assert not provider.calls
        return
    record = f.refresh(registry, "changed-context", changed, provider)
    assert record.complete and len(provider.calls) == 1
    assert provider.calls[0].sessions[0] == "2026-01-02"
    assert "FICTION-A:incompatible_cache_rebuild" in record.events
    assert len(registry.replay("changed-context").manifest.envelope.sources) == 1


@pytest.mark.parametrize(
    "damage",
    [
        "empty",
        "failed",
        "partial",
        "missing",
        "duplicate",
        "outside",
        "wrong-boundary",
        "wrong-security",
        "unknown",
        "bad-return",
        "bad-predecessor",
        "wrong-context",
        "extra-field",
    ],
)
def test_failed_response_retains_bytes_and_does_not_advance_success(
    registry: r.HistoryRegistry, damage: str
) -> None:
    before = initial(registry)
    req = request(cache=("initial",))

    def alter(body: dict[str, Any], count: int) -> None:
        if damage in ("empty", "failed", "partial"):
            body.update(outcome=damage, reason="stipulated unavailable response")
            if damage != "partial":
                body["observations"] = []
        elif damage == "missing":
            body["observations"].pop(1)
        elif damage == "duplicate":
            body["observations"].append(body["observations"][-1])
        elif damage == "outside":
            body["observations"][-1]["session"] = "2026-04-01"
        elif damage == "wrong-boundary":
            body["start"] = "2026-01-06"
        elif damage == "wrong-security":
            body["observations"][-1]["security_id"] = "FICTION-WRONG"
        elif damage == "unknown":
            body["observations"][-1]["dividend"] = {
                "text": None,
                "unknown_reason": "unverified action",
            }
        elif damage == "bad-return":
            body["observations"][-1]["total_return"]["text"] = "0.0000"
        elif damage == "bad-predecessor":
            body["observations"][-1]["return_from_session"] = "2026-01-06"
        elif damage == "wrong-context":
            body["context"]["vintage"] = "unknown-revised-vintage"
        else:
            body["unrecognized"] = "retained but refused"

    provider = Altered(req, alter)
    record = f.refresh(registry, "failure", req, provider)
    assert not record.complete
    assert record.freshness == before.freshness
    assert record.attempts[0].raw is not None
    assert registry.history.evidence.read(record.attempts[0].raw.receipt())
    assert f.replay(registry, "failure") == record
    assert f.replay(registry, "initial") == before
    repeated = provider_factory(req)
    assert f.refresh(registry, "failure", req, repeated) == record and not repeated.calls


def test_missing_interior_refetch_and_manual_selected_all_never_schedule(
    registry: r.HistoryRegistry,
) -> None:
    req = request()

    def drop(body: dict[str, Any], _: int) -> None:
        body["observations"].pop(2)  # Jan 6 missing, so Jan 7 also lacks its predecessor.

    first = f.refresh(registry, "partial-grid", req, Altered(req, drop))
    assert not first.complete
    retry = request(cache=("partial-grid",))
    provider = provider_factory(retry)
    fixed = f.refresh(registry, "fill-grid", retry, provider)
    assert fixed.complete
    assert [c.sessions for c in provider.calls] == [("2026-01-05", "2026-01-06", "2026-01-07")]
    # A correction outside the overlap is undetectable to a zero-call reuse.
    manual = request(cache=("fill-grid",), manual=("FICTION-A",), known_at="2026-03-02T12:00:00Z")
    manual_provider = provider_factory(manual)
    full = f.refresh(registry, "manual", manual, manual_provider)
    assert full.complete and len(manual_provider.calls) == 1
    assert manual_provider.calls[0].reason == "manual"
    assert full.freshness[0].last_successful_broader_validation == manual.selection.known_at
    assert full.scheduled_validation == "Off / Never"


def test_supporting_closure_survives_backup_and_omission_or_corruption_refuses(
    registry: r.HistoryRegistry, tmp_path: Path
) -> None:
    first = initial(registry)
    proof = registry.proof()
    entry = proof.dependencies[0]
    assert entry.format == "synthetic-history-dependency-v2" and len(entry.supporting) == 2
    assert len(proof.required) == 3  # response, frozen manifest, operation record
    saved, restored = boundary(tmp_path / "backup"), boundary(tmp_path / "restored")
    b.backup(registry, saved, candidate_id="refresh-required")
    b.restore(saved, restored)
    reopened = r.HistoryRegistry(h.HistoryStore(restored, existing=True))
    assert reopened.proof() == proof and f.replay(reopened, "initial") == first
    # A record is required even if the economic source/manifest remains intact.
    record_ref = next(x for x in entry.supporting if x.sha256 != first.attempts[0].raw.sha256)  # type: ignore[union-attr]
    reopened.runtime.path(record_ref.reference).unlink()
    with pytest.raises(EvidenceError):
        reopened.proof()
    with pytest.raises(EvidenceError):
        reopened.replay("initial")


def test_expired_invalid_conflicting_request_and_busy_runtime_make_zero_calls(
    registry: r.HistoryRegistry,
) -> None:
    req = request()
    provider = provider_factory(req)
    expired = req.model_copy(
        update={
            "policy": req.policy.model_copy(
                update={"permission_valid_until": "2026-01-01T00:00:00Z"}
            )
        }
    )
    with pytest.raises(f.RefreshError, match="expired"):
        f.refresh(registry, "expired", expired, provider)
    with pytest.raises(f.RefreshError, match="invalid_refresh_operation_id"):
        f.refresh(registry, "../escape", req, provider)
    invalid = req.model_copy(update={"manual_security_ids": ("FICTION-A",)})
    with pytest.raises(ValidationError):
        f.refresh(registry, "invalid", invalid, provider)
    with history_writer(registry.runtime):
        with pytest.raises(EvidenceError, match="history_runtime_busy"):
            f.refresh(registry, "busy", req, provider)
    assert provider.calls == []
    f.refresh(registry, "once", req, provider)
    changed = request(known_at="2026-03-02T12:00:00Z")
    with pytest.raises(f.RefreshError, match="refresh_operation_conflict"):
        f.refresh(registry, "once", changed, provider)
    assert len(provider.calls) == 1


CHILD = """
import os, runpy, sys, time
from pathlib import Path
from prosper import history as h, history_registry as r, history_refresh as f
from prosper.evidence import RuntimeBoundary
root, runtime, phase, signal, release = sys.argv[1:]
fixture = runpy.run_path(str(Path(root)/'scripts/qualify_refresh.py'))
request = fixture['fictional_request']()
def hook(name):
    if name == phase:
        Path(signal).write_text('paused')
        if release == 'die': os._exit(74)
        while not Path(release).exists(): time.sleep(0.02)
f._step = hook
boundary = RuntimeBoundary(Path(runtime), Path(root), 'synthetic')
registry = r.HistoryRegistry(h.HistoryStore(boundary, existing=True))
f.refresh(registry, 'child', request, fixture['FictionalProvider'](request))
"""


@pytest.mark.parametrize(
    "phase", ["response_retained", "snapshot_published", "record_published", "operation_committed"]
)
def test_actual_process_death_keeps_old_versions_and_retry_is_idempotent(
    registry: r.HistoryRegistry, tmp_path: Path, phase: str
) -> None:
    old = initial(registry)
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
    assert process.returncode == 74, process.stderr.decode()
    assert f.replay(registry, "initial") == old
    req = request()
    provider = provider_factory(req)
    result = f.refresh(registry, "child", req, provider)
    assert result.complete
    assert len(provider.calls) == (0 if phase == "operation_committed" else 1)
    assert len(registry.proof().dependencies) == 2


def test_real_pending_refresh_blocks_competing_refresh_registration_backup_and_retention(
    registry: r.HistoryRegistry, tmp_path: Path
) -> None:
    old = initial(registry)
    signal, release = tmp_path / "signal", tmp_path / "release"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            CHILD,
            str(ROOT),
            str(registry.history.runtime.root),
            "response_retained",
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
        req = request()
        provider = provider_factory(req)
        with pytest.raises(EvidenceError, match="history_runtime_busy"):
            f.refresh(registry, "competing", req, provider)
        assert not provider.calls
        with pytest.raises(b.HistoryRecoveryError):
            b.backup(registry, boundary(tmp_path / "busy-backup"), candidate_id="busy")
        assert registry.assess_removal(old.snapshot.reference).required is None
        release.write_text("continue")
        _, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr.decode()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    assert f.replay(registry, "child").complete


def test_offline_replay_script_is_deterministic_across_processes() -> None:
    first = subprocess.check_output([sys.executable, "-I", str(SCRIPT)])
    second = subprocess.check_output([sys.executable, "-I", str(SCRIPT)])
    assert first == second
    report = json.loads(first)
    assert report["repeat_calls"] == 0 and report["restore_equal"] is True


def test_numeric_spelling_change_retains_source_without_economic_revision(
    registry: r.HistoryRegistry,
) -> None:
    initial(registry)
    req = request(cache=("initial",))

    def spelling(body: dict[str, Any], _: int) -> None:
        body["observations"][0]["adjusted_close"]["text"] = "133.1"

    provider = Altered(req, spelling)
    record = f.refresh(registry, "spelling", req, provider)
    assert record.complete and len(provider.calls) == 1
    assert not record.attempts[0].changed_overlap
    raw = record.attempts[0].raw
    assert raw is not None and b'"133.1"' in registry.history.evidence.read(raw.receipt())


def test_manual_outside_overlap_correction_and_selected_name_scope(
    registry: r.HistoryRegistry,
) -> None:
    both = request(names=("FICTION-A", "FICTION-B"))
    old = f.refresh(registry, "both", both, provider_factory(both))
    req = request(
        names=("FICTION-A", "FICTION-B"),
        cache=("both",),
        manual=("FICTION-B",),
        known_at="2026-03-02T12:00:00Z",
    )

    def correction(body: dict[str, Any], _: int) -> None:
        body["observations"][1]["dividend"]["text"] = "1.2500"

    provider = Altered(req, correction)
    current = f.refresh(registry, "selected", req, provider)
    assert current.complete and [c.security_id for c in provider.calls] == ["FICTION-B"]
    assert current.freshness[0] == old.freshness[0]
    assert current.freshness[1].last_successful_broader_validation == req.selection.known_at
    source_rows = registry.replay("selected").manifest.envelope.observations
    assert (
        next(row for row in source_rows if row.security_id == "FICTION-B").dividend.text == "1.2500"
    )
    assert registry.replay("both").manifest.envelope.observations[0].dividend.text == "0.0000"
    all_req = request(
        names=("FICTION-A", "FICTION-B"), cache=("selected",), manual=("FICTION-A", "FICTION-B")
    )
    # Explicit historical request cannot consume future-known cache evidence.
    with pytest.raises(f.RefreshError, match="refresh_cache_from_future"):
        f.refresh(registry, "past", all_req, provider_factory(all_req))


@pytest.mark.parametrize(
    "kind", ["transport", "malformed", "duplicate-field", "unknown-predecessor"]
)
def test_failed_transport_and_unsupported_bytes_never_claim_success(
    registry: r.HistoryRegistry, kind: str
) -> None:
    req = request()

    class Broken:
        def fetch(self, interval: f.Range) -> bytes:
            if kind == "transport":
                raise RuntimeError("stipulated transport exception, not copied into evidence")
            raw = provider_factory(req).fetch(interval)
            if kind == "malformed":
                return b"fictional error response"
            if kind == "duplicate-field":
                return b'{"outcome":"complete",' + raw[1:]
            doc = json.loads(raw)
            doc["observations"][0]["adjusted_close"] = {
                "text": None,
                "unknown_reason": "missing boundary",
            }
            return json.dumps(doc).encode()

    record = f.refresh(registry, "broken", req, Broken())
    assert not record.complete
    assert record.freshness[0].last_successful_refresh is None
    assert record.freshness[0].last_successful_broader_validation is None
    assert (record.attempts[0].raw is None) == (kind == "transport")


def test_storage_failure_is_not_mislabeled_as_a_provider_response(
    registry: r.HistoryRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = initial(registry)
    req = request()

    def fail(raw: bytes) -> Any:
        raise EvidenceError("stipulated_storage_failure")

    monkeypatch.setattr(registry.history.evidence, "publish", fail)
    with pytest.raises(EvidenceError, match="stipulated_storage_failure"):
        f.refresh(registry, "failed-write", req, provider_factory(req))
    assert f.replay(registry, "initial") == old
    assert [d.dependency_id for d in registry.proof().dependencies] == ["initial"]


@pytest.mark.parametrize("field", ["return_convention", "return_transform_version"])
def test_unsupported_return_method_refuses_before_calls(
    registry: r.HistoryRegistry, field: str
) -> None:
    req = request()
    context = req.selection.series[0].model_copy(update={field: "unsupported-log-return"})
    req = req.model_copy(
        update={"selection": req.selection.model_copy(update={"series": (context,)})}
    )
    provider = provider_factory(req)
    with pytest.raises(f.RefreshError, match="refresh_unsupported_transform"):
        f.refresh(registry, "unsupported", req, provider)
    assert not provider.calls and not registry.proof().dependencies


def test_v1_dependency_wire_identity_is_preserved_and_support_is_versioned(
    registry: r.HistoryRegistry,
) -> None:
    initial(registry)
    frozen = registry.replay("initial")
    legacy = registry.register(
        "legacy", frozen.receipt, expected=frozen.manifest.envelope.selection
    )
    assert legacy.format == "synthetic-history-dependency-v1"
    assert "supporting" not in json.loads(legacy.model_dump_json())
    before = r._document(legacy)
    reopened = r.HistoryRegistry(h.HistoryStore(registry.history.runtime, existing=True))
    assert (
        r._document(next(d for d in reopened.proof().dependencies if d.dependency_id == "legacy"))
        == before
    )
    with pytest.raises(ValidationError, match="incompatible_dependency_support"):
        r.Dependency(
            format="synthetic-history-dependency-v2",
            dependency_id="bad-version",
            manifest=legacy.manifest,
            selection=legacy.selection,
        )
