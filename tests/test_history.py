"""Independent fictional grid accounting and real immutable-filesystem failures."""

import hashlib
import json
import os
import runpy
import subprocess
import sys
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

import prosper.evidence as evidence
from prosper import history as h
from prosper.evidence import EvidenceError, EvidenceReceipt, RuntimeBoundary
from prosper.maintenance import maintain_runtime

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/synthetic/history/reference.json"
reference_input = cast(
    Callable[[h.HistoryStore], h.Envelope],
    runpy.run_path(str(ROOT / "scripts/qualify_history.py"))["reference_input"],
)


@pytest.fixture
def store(tmp_path: Path) -> h.HistoryStore:
    return h.HistoryStore(RuntimeBoundary(tmp_path / "history-runtime", ROOT, "synthetic"))


def changed(data: h.Envelope, **updates: object) -> h.Envelope:
    document = data.model_dump(mode="json")
    document.update(updates)
    return h.Envelope.model_validate_json(json.dumps(document))


def cells(items: tuple[h.Cell, ...]) -> list[list[str]]:
    return [[c.security_id, c.session] for c in items]


def test_complete_grid_exact_identity_reopen_and_idempotence(store: h.HistoryStore) -> None:
    data = reference_input(store)
    result = store.publish(data)
    fixture = json.loads(FIXTURE.read_bytes())
    actual = result.manifest.coverage
    assert actual.complete and not actual.issues
    assert cells(actual.requested) == fixture["expected_requested"]
    assert actual.requested == actual.received == actual.usable
    assert result.manifest.envelope.observations[0].close.text == "0010.000000000000"
    assert store.publish(data) == result
    assert h.HistoryStore(store.runtime, existing=True).read(result.receipt) == result
    assert result.snapshot_sha256 == hashlib.sha256(h.canonical_bytes(result.manifest)).hexdigest()
    assert data.sources[0].raw.sha256 == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert result.snapshot_sha256 != data.sources[0].raw.sha256
    assert not list(store.runtime.root.rglob("*.part"))
    with pytest.raises(ValidationError):
        result.manifest.envelope.observations[0].close.text = "0"


def test_missing_middle_unknown_action_conflicting_duplicates_and_failure(
    store: h.HistoryStore,
) -> None:
    data = reference_input(store)
    rows = [r.model_dump(mode="json") for j, r in enumerate(data.observations) if j != 1]
    rows[2]["dividend"] = {"text": None, "unknown_reason": "fictional action unavailable"}
    duplicate = dict(rows[3])
    duplicate["close"] = {"text": "11", "unknown_reason": None}
    duplicate["source_row"] = "conflicting-copy"
    rows.append(duplicate)
    failed = h.Source(
        source_id="failed-response",
        context=data.selection.series[0],
        raw=store.retain(b"fictional throttle error body"),
        validated_at=data.selection.known_at,
        outcome="failed",
        reason="outage",
    )
    data = changed(
        data,
        observations=rows,
        sources=[
            *(s.model_dump(mode="json") for s in data.sources),
            failed.model_dump(mode="json"),
        ],
    )
    result = store.publish(data)
    fixture = json.loads(FIXTURE.read_bytes())
    actual = result.manifest.coverage
    assert not actual.complete
    assert cells(actual.requested) == fixture["expected_requested"]
    assert cells(actual.received) == fixture["expected_received_incomplete"]
    assert cells(actual.usable) == fixture["expected_usable_incomplete"]
    assert {i.code for i in actual.issues} == {
        "missing_observation",
        "unknown_fact",
        "duplicate_observation",
        "contradictory_ohlc",
        "source_failed",
    }
    assert len(result.manifest.envelope.observations) == 6
    assert store.evidence.read(failed.raw.receipt()) == b"fictional throttle error body"
    assert store.read(result.receipt).manifest.envelope == data


@pytest.mark.parametrize("outcome", ["partial", "empty", "failed"])
def test_outcomes_never_create_complete_watermark(store: h.HistoryStore, outcome: str) -> None:
    data = reference_input(store)
    sources = [s.model_dump(mode="json") for s in data.sources]
    sources[0].update(outcome=outcome, reason="stipulated source issue")
    result = store.publish(changed(data, sources=sources))
    assert not result.manifest.coverage.complete
    assert len(result.manifest.coverage.received) == 6
    assert len(result.manifest.coverage.usable) == (6 if outcome == "partial" else 3)


def test_empty_attempt_retains_missing_grid(store: h.HistoryStore) -> None:
    data = changed(reference_input(store), sources=[], observations=[])
    result = store.publish(data)
    assert not result.manifest.coverage.complete
    assert len(result.manifest.coverage.requested) == 6
    assert not result.manifest.coverage.received and not result.manifest.coverage.usable
    assert len(result.manifest.coverage.issues) == 6


@pytest.mark.parametrize(
    "field",
    [
        "provider",
        "dataset",
        "permission_scope",
        "provider_symbol",
        "currency",
        "calendar",
        "timezone",
        "interval",
        "adjustment",
        "repair",
        "source_schema",
        "transform_version",
        "library_version",
        "return_convention",
        "return_transform_version",
        "vintage",
        "security_id",
        "mapping_start",
        "mapping_end",
        "captured_at",
    ],
)
def test_context_changes_are_distinct_and_incompatible(store: h.HistoryStore, field: str) -> None:
    data = reference_input(store)
    prior = store.publish(data)
    document = data.model_dump(mode="json")
    context = document["selection"]["series"][0]
    context[field] = {
        "mapping_start": "2025-12-31",
        "mapping_end": "2027-01-01",
        "captured_at": "2026-01-08T11:00:00Z",
    }.get(field, f"changed-{field}")
    # Updating selected context alone cannot silently reuse old source context.
    with pytest.raises(ValidationError, match="incompatible_source_context"):
        h.Envelope.model_validate_json(json.dumps(document))
    document["sources"][0]["context"] = context
    if field == "security_id":
        for row in document["observations"]:
            if row["security_id"] == "FICTION-A":
                row["security_id"] = context[field]
    modified = h.Envelope.model_validate_json(json.dumps(document))
    other = store.publish(modified)
    assert other.snapshot_sha256 != prior.snapshot_sha256
    with pytest.raises(h.HistoryError, match="incompatible_history_selection"):
        store.read(prior.receipt, expected=modified.selection)
    assert store.read(prior.receipt).manifest.envelope == data


def test_raw_spelling_and_order_and_cutoff_changes_freeze_new_versions(
    store: h.HistoryStore,
) -> None:
    data = reference_input(store)
    prior = store.publish(data)
    raw = store.retain(FIXTURE.read_bytes() + b"\n")
    document = data.model_dump(mode="json")
    document["sources"][0]["raw"] = raw.model_dump(mode="json")
    document["observations"][0]["close"]["text"] = "10.0"
    modified = h.Envelope.model_validate_json(json.dumps(document))
    second = store.publish(modified)
    assert prior.snapshot_sha256 != second.snapshot_sha256
    assert data.sources[0].raw.sha256 != modified.sources[0].raw.sha256
    assert second.manifest.coverage.complete
    for edit in ("order", "cutoff", "known_at"):
        document = data.model_dump(mode="json")
        if edit == "order":
            document["selection"]["series"].reverse()
        elif edit == "cutoff":
            document["selection"]["cutoff"] = "2026-01-08"
        else:
            document["selection"]["known_at"] = "2026-01-09T12:00:00Z"
        assert store.publish(h.Envelope.model_validate_json(json.dumps(document))) != prior
    assert store.read(prior.receipt).manifest.envelope == data


@pytest.mark.parametrize("target", ["raw", "manifest"])
@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_required_evidence_damage_refuses_replay_and_publication(
    store: h.HistoryStore,
    target: str,
    damage: str,
) -> None:
    data = reference_input(store)
    prior = store.publish(data)
    receipt = data.sources[0].raw.receipt() if target == "raw" else prior.receipt
    path = store.evidence.runtime.path(receipt.relative_reference)
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"fictional corrupt bytes")
    code = "evidence_missing" if damage == "missing" else "evidence_identity_mismatch"
    with pytest.raises(EvidenceError, match=code):
        store.read(prior.receipt)
    if target == "raw":
        with pytest.raises(EvidenceError, match=code):
            store.publish(data)
    assert (
        not path.exists()
        if damage == "missing"
        else path.read_bytes() == b"fictional corrupt bytes"
    )


@pytest.mark.parametrize("phase", ["write", "publish", "bad_write"])
def test_interrupted_manifest_preserves_old_snapshot(
    store: h.HistoryStore,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    data = reference_input(store)
    prior = store.publish(data)
    modified = changed(data, diagnostics=["new retained synthetic diagnostic"])

    def fail_write(path: Path, raw: bytes) -> None:
        path.write_bytes(raw[:30])
        raise OSError("private text")

    def bad_write(path: Path, raw: bytes) -> None:
        path.write_bytes(raw[:30])

    def fail_publish(staged: Path, final: Path) -> None:
        raise OSError("private text")

    monkeypatch.setattr(
        evidence,
        "_publish" if phase == "publish" else "_write_staged",
        {
            "write": fail_write,
            "bad_write": bad_write,
            "publish": fail_publish,
        }[phase],
    )
    with pytest.raises(
        EvidenceError,
        match=(
            "staging_identity_mismatch" if phase == "bad_write" else "evidence_publication_failed"
        ),
    ):
        store.publish(modified)
    assert store.read(prior.receipt) == prior
    partial = next(store.runtime.root.rglob("*.part"))
    assert not partial.read_bytes() == h.canonical_bytes(prior.manifest)
    expected = h.Manifest(envelope=modified, coverage=h.coverage(modified))
    manifest_hash = hashlib.sha256(h.canonical_bytes(expected)).hexdigest()
    assert not store.evidence.runtime.path(
        f"evidence-bytes-v1/objects/{manifest_hash}.bin"
    ).exists()


def _publish_process(root: str, document: str) -> EvidenceReceipt | str:
    child = h.HistoryStore(RuntimeBoundary(Path(root), ROOT, "synthetic"))
    try:
        return child.publish(h.Envelope.model_validate_json(document)).receipt
    except EvidenceError as error:
        if error.code != "history_runtime_busy":
            raise
        return error.code


def test_competing_reader_publisher_refuse_temporary_link_alias(
    store: h.HistoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = reference_input(store)
    prior = store.publish(data)
    modified = changed(data, diagnostics=["race-version"])
    raw = h.canonical_bytes(h.Manifest(envelope=modified, coverage=h.coverage(modified)))
    digest = hashlib.sha256(raw).hexdigest()
    candidate = EvidenceReceipt(digest, len(raw), f"evidence-bytes-v1/objects/{digest}.bin")

    def compete(staged: Path, final: Path) -> None:
        os.link(staged, final)
        other = h.HistoryStore(store.runtime, existing=True)
        with pytest.raises(EvidenceError, match="untrusted_file_type_or_links"):
            other.read(candidate)
        with pytest.raises(EvidenceError, match="history_runtime_busy"):
            other.publish(modified)
        assert other.read(prior.receipt) == prior
        staged.unlink()

    monkeypatch.setattr(evidence, "_publish", compete)
    assert store.publish(modified).receipt == candidate
    assert store.read(candidate).manifest.envelope == modified


@pytest.mark.parametrize("phase", ["staged", "linked", "unlinked"])
def test_abrupt_manifest_publication_exit(
    store: h.HistoryStore,
    tmp_path: Path,
    phase: str,
) -> None:
    data = reference_input(store)
    prior = store.publish(data)
    modified = changed(data, diagnostics=["abrupt-version"])
    input_path = tmp_path / "synthetic-envelope.json"
    input_path.write_text(modified.model_dump_json(), encoding="utf-8")
    code = """
import os, sys
from pathlib import Path
import prosper.evidence as e
from prosper.history import HistoryStore, Envelope
store=HistoryStore(e.RuntimeBoundary(Path(sys.argv[1]),Path(sys.argv[2]),'synthetic'))
def crash(staged, final):
    if sys.argv[4] != 'staged':
        os.link(staged, final)
    if sys.argv[4] == 'unlinked':
        staged.unlink()
    os._exit(61)
e._publish=crash
store.publish(Envelope.model_validate_json(Path(sys.argv[3]).read_bytes()))
"""
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(store.runtime.root),
            str(ROOT),
            str(input_path),
            phase,
        ],
        capture_output=True,
    )
    assert child.returncode == 61, child.stderr.decode()
    raw = h.canonical_bytes(h.Manifest(envelope=modified, coverage=h.coverage(modified)))
    digest = hashlib.sha256(raw).hexdigest()
    candidate = EvidenceReceipt(digest, len(raw), f"evidence-bytes-v1/objects/{digest}.bin")
    reopened = h.HistoryStore(store.runtime, existing=True)
    assert reopened.read(prior.receipt) == prior
    if phase == "unlinked":
        # A fully published manifest can survive death before receipt return.
        assert reopened.read(candidate).manifest.envelope == modified
    else:
        code = "evidence_missing" if phase == "staged" else "untrusted_file_type_or_links"
        with pytest.raises(EvidenceError, match=code):
            reopened.read(candidate)


@pytest.mark.parametrize(
    "edit",
    [
        "unknown-with-value",
        "unknown-without-reason",
        "unordered",
        "duplicate-session",
        "future-capture",
        "future-validation",
        "invalid-date",
        "missing-source",
    ],
)
def test_structural_contradictions_are_refused(store: h.HistoryStore, edit: str) -> None:
    document = reference_input(store).model_dump(mode="json")
    if edit == "unknown-with-value":
        document["observations"][0]["close"]["unknown_reason"] = "both cannot be true"
    elif edit == "unknown-without-reason":
        document["observations"][0]["close"]["text"] = None
    elif edit == "unordered":
        document["selection"]["sessions"].reverse()
    elif edit == "duplicate-session":
        document["selection"]["sessions"].append("2026-01-07")
    elif edit == "future-capture":
        document["selection"]["series"][0]["captured_at"] = "2026-01-09T12:00:00Z"
    elif edit == "future-validation":
        document["sources"][0]["validated_at"] = "2026-01-09T12:00:00Z"
    elif edit == "invalid-date":
        document["observations"][0]["session"] = "2026-02-30"
    else:
        document["observations"][0]["source_id"] = "absent-source"
    with pytest.raises(ValidationError):
        h.Envelope.model_validate_json(json.dumps(document))


@pytest.mark.parametrize("same", [True, False])
def test_concurrent_process_publication(store: h.HistoryStore, same: bool) -> None:
    data = reference_input(store)
    documents = [
        data.model_dump_json(),
        (
            data if same else changed(data, diagnostics=["other immutable version"])
        ).model_dump_json(),
    ]
    with ProcessPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(_publish_process, [str(store.runtime.root)] * 2, documents))
    # Fail-fast contention is explicit; retry only after both processes finish.
    resolved = [
        store.publish(h.Envelope.model_validate_json(document)).receipt
        if isinstance(result, str)
        else result
        for result, document in zip(results, documents, strict=True)
    ]
    assert (resolved[0] == resolved[1]) == same
    for receipt, document in zip(resolved, documents, strict=True):
        assert store.read(receipt).manifest.envelope == h.Envelope.model_validate_json(document)


def test_restart_offline_and_namespace_not_foundation_cleanup(store: h.HistoryStore) -> None:
    data = reference_input(store)
    prior = store.publish(data)
    code = (
        "import sys; from pathlib import Path; from prosper.history import HistoryStore; "
        "from prosper.evidence import RuntimeBoundary, EvidenceReceipt; "
        "rt=RuntimeBoundary(Path(sys.argv[1]),Path(sys.argv[2]),'synthetic'); "
        "s=HistoryStore(rt,existing=True); "
        "r=EvidenceReceipt(sys.argv[3],int(sys.argv[4]),sys.argv[5]); "
        "from prosper.history import canonical_bytes; "
        "sys.stdout.buffer.write(canonical_bytes(s.read(r).manifest))"
    )
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(store.runtime.root),
            str(ROOT),
            prior.receipt.raw_sha256,
            str(prior.receipt.byte_length),
            prior.receipt.relative_reference,
        ],
        capture_output=True,
        check=True,
    )
    assert child.stdout == h.canonical_bytes(prior.manifest)
    before = {p: p.read_bytes() for p in store.runtime.root.rglob("*.bin")}
    result = maintain_runtime(store.runtime)
    assert result.status != "verified"
    # Foundation maintenance cannot discover these as disposable lot objects.
    assert before == {p: p.read_bytes() for p in store.runtime.root.rglob("*.bin")}
    assert store.read(prior.receipt) == prior


def test_closed_schema_and_forged_coverage_refused(store: h.HistoryStore) -> None:
    data = reference_input(store)
    result = store.publish(data)
    for mutation in ("version", "coverage", "extra"):
        document = result.manifest.model_dump(mode="json")
        if mutation == "version":
            document["schema_version"] = "future-version"
        elif mutation == "coverage":
            document["coverage"]["usable"] = []
        else:
            document["envelope"]["extra"] = "unrecognized"
        receipt = store.evidence.publish(json.dumps(document).encode())
        with pytest.raises(h.HistoryError, match="invalid_history_manifest"):
            store.read(receipt)
    document = json.loads(h.canonical_bytes(result.manifest))
    receipt = store.evidence.publish(json.dumps(document).encode())
    with pytest.raises(h.HistoryError, match="noncanonical_history_manifest"):
        store.read(receipt)


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("close", "0", "unsupported_decimal"),
        ("total_return", "-1.01", "return_below_minus_one"),
        ("close", "1.0000000000001", "unsupported_decimal"),
        ("close", "NaN", "unsupported_decimal"),
        ("return_from_session", None, "invalid_return_boundary"),
        ("security_id", "unknown-security", "source_security_mismatch"),
        ("session", "2026-01-09", "outside_selected_grid"),
    ],
)
def test_unusable_facts_are_retained_without_repair(
    store: h.HistoryStore,
    field: str,
    value: str | None,
    code: str,
) -> None:
    data = reference_input(store)
    rows = [r.model_dump(mode="json") for r in data.observations]
    if isinstance(rows[0][field], dict):
        rows[0][field]["text"] = value
    else:
        rows[0][field] = value
    data = changed(data, observations=rows)
    result = store.publish(data)
    assert not result.manifest.coverage.complete
    assert len(result.manifest.coverage.usable) == 5
    assert code in {i.code for i in result.manifest.coverage.issues}
    assert result.manifest.envelope == data


def test_reopen_does_not_initialize_and_private_mode_refused(tmp_path: Path) -> None:
    root = tmp_path / "uncreated"
    with pytest.raises(EvidenceError, match="runtime_missing"):
        h.HistoryStore(RuntimeBoundary(root, ROOT, "synthetic"), existing=True)
    assert not root.exists()
    if os.name == "nt":
        private = Path(os.environ["TEMP"]) / "prosper-fictional-history-private"
        with pytest.raises(h.HistoryError, match="synthetic_history_only"):
            h.HistoryStore(RuntimeBoundary(private, ROOT, "private"))
