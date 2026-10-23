"""Real synthetic filesystem acceptance, with fault injection at write/publication."""

import hashlib
import json
import os
import subprocess
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

import prosper.evidence as evidence
from prosper.bundle import MAX_BYTES, parse_bundle
from prosper.evidence import EvidenceError, EvidenceReceipt, EvidenceStore, RuntimeBoundary

SOURCE = Path(__file__).resolve().parents[1]
FIXTURES = SOURCE / "examples/synthetic"


@pytest.fixture
def store(tmp_path: Path) -> EvidenceStore:
    # Actual project source, explicit ignored synthetic runtime; no private data.
    return EvidenceStore(RuntimeBoundary(tmp_path / "runtime", SOURCE, "synthetic"))


def error(code: str) -> pytest.RaisesExc[EvidenceError]:
    return pytest.raises(EvidenceError, match=f"^{code}$")


@pytest.mark.parametrize("name", ["F000", "F001"])
def test_fixture_reopen_and_independent_identity(store: EvidenceStore, name: str) -> None:
    raw = (FIXTURES / f"{name}.json").read_bytes()
    receipt = store.publish(raw)
    assert receipt.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert receipt.byte_length == len(raw)
    assert receipt.storage_version == "evidence-bytes-v1"
    reopened = EvidenceStore(store.runtime)
    restored = reopened.read(receipt)
    assert restored == raw
    before, after = parse_bundle(raw).parsed, parse_bundle(restored).parsed
    assert before is not None and after is not None
    assert after.canonical_bytes == before.canonical_bytes
    assert after.canonical_sha256 == before.canonical_sha256
    for old, new in zip(before.document.lots, after.document.lots, strict=True):
        assert new.basis == old.basis
        if old.basis.value is not None:
            assert new.basis.value is not None
            assert new.basis.value.original_text == old.basis.value.original_text
            assert new.basis.value.source_quantum == old.basis.value.source_quantum
    assert not list(store.runtime.root.rglob("*.part"))
    with pytest.raises(FrozenInstanceError):
        receipt.byte_length = 0  # type: ignore[misc]


def test_repeat_and_equivalent_formatting_keep_originals(store: EvidenceStore) -> None:
    raw = (FIXTURES / "F001.json").read_bytes()
    first = store.publish(raw)
    assert store.publish(raw) == first
    alternate = json.dumps(json.loads(raw), separators=(",", ":")).encode()
    second = store.publish(alternate)
    assert first.raw_sha256 != second.raw_sha256
    assert store.read(first) == raw
    assert store.read(second) == alternate
    a, b = parse_bundle(raw).parsed, parse_bundle(alternate).parsed
    assert a is not None and b is not None and a.canonical_sha256 == b.canonical_sha256
    assert len(list(store.runtime.root.rglob("*.bin"))) == 2
    ignored = subprocess.run(
        ["git", "check-ignore", str(store.runtime.root)], cwd=SOURCE, capture_output=True
    )
    assert ignored.returncode == 0


def test_byte_bounds_and_no_parser_claim(store: EvidenceStore) -> None:
    for raw in (b"", b"synthetic arbitrary evidence", b"x" * MAX_BYTES):
        assert store.read(store.publish(raw)) == raw
    with error("evidence_size_exceeded"):
        store.publish(b"x" * (MAX_BYTES + 1))
    with error("byte_payload_required"):
        store.publish("payload")  # type: ignore[arg-type]


@pytest.mark.parametrize("phase", ["write", "publish", "bad_write"])
def test_failures_preserve_prior_and_never_publish_partial(
    store: EvidenceStore, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    prior = store.publish(b"synthetic prior")

    def failed_write(path: Path, raw: bytes) -> None:
        path.write_bytes(raw[:2])
        raise OSError("sensitive payload must not escape")

    def failed_publish(staged: Path, final: Path) -> None:
        raise OSError("sensitive payload must not escape")

    def bad_write(path: Path, raw: bytes) -> None:
        path.write_bytes(b"incorrect synthetic bytes")

    if phase == "write":
        monkeypatch.setattr(evidence, "_write_staged", failed_write)
    elif phase == "publish":
        monkeypatch.setattr(evidence, "_publish", failed_publish)
    else:
        monkeypatch.setattr(evidence, "_write_staged", bad_write)
    expected = (
        "staging_identity_mismatch" if phase == "bad_write" else "evidence_publication_failed"
    )
    with error(expected):
        store.publish(b"synthetic next")
    assert store.read(prior) == b"synthetic prior"
    assert len(list(store.runtime.root.rglob("*.bin"))) == 1
    assert len(list(store.runtime.root.rglob("*.part"))) == 1


def test_destination_created_during_publication_is_verified(
    store: EvidenceStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def winner(staged: Path, final: Path) -> None:
        final.write_bytes(staged.read_bytes())
        raise FileExistsError()

    monkeypatch.setattr(evidence, "_publish", winner)
    receipt = store.publish(b"synthetic competing publisher")
    assert store.read(receipt) == b"synthetic competing publisher"
    assert len(list(store.runtime.root.rglob("*.part"))) == 1


def test_real_publication_primitive_never_replaces_destination(tmp_path: Path) -> None:
    staged, final = tmp_path / "stage.part", tmp_path / "existing.bin"
    staged.write_bytes(b"synthetic new")
    final.write_bytes(b"synthetic existing")
    with pytest.raises(FileExistsError):
        evidence._publish(staged, final)
    assert staged.read_bytes() == b"synthetic new"
    assert final.read_bytes() == b"synthetic existing"


@pytest.mark.parametrize(
    "replacement",
    [b"", b"bad", b"synthEtic", b"x" * (MAX_BYTES + 1)],
    ids=["empty", "truncated", "changed", "oversized"],
)
def test_corrupt_existing_is_never_replaced(store: EvidenceStore, replacement: bytes) -> None:
    raw = b"synthetic"
    digest = hashlib.sha256(raw).hexdigest()
    receipt = EvidenceReceipt(digest, len(raw), f"evidence-bytes-v1/objects/{digest}.bin")
    final = store.runtime.path(receipt.relative_reference)
    final.write_bytes(replacement)
    code = (
        "evidence_size_exceeded" if len(replacement) > MAX_BYTES else "evidence_identity_mismatch"
    )
    with error(code):
        store.publish(raw)
    with error(code):
        store.read(receipt)
    assert final.read_bytes() == replacement


def test_missing_and_receipt_mismatch(store: EvidenceStore) -> None:
    receipt = store.publish(b"synthetic receipt")
    with error("evidence_identity_mismatch"):
        store.read(replace(receipt, byte_length=receipt.byte_length - 1))
    store.runtime.path(receipt.relative_reference).unlink()
    with error("evidence_missing"):
        store.read(receipt)
    with error("receipt_required"):
        store.read("../../unrelated")  # type: ignore[arg-type]


@pytest.mark.parametrize("digest", ["", "../x", "a" * 63, "A" * 64, "g" * 64])
def test_invalid_digests(digest: str) -> None:
    with error("invalid_digest"):
        EvidenceReceipt(digest, 0, "unrelated")


@pytest.mark.parametrize("size", [-1, MAX_BYTES + 1, True, 1.5])
def test_invalid_receipt_sizes(size: int) -> None:
    with error("invalid_byte_length"):
        EvidenceReceipt("a" * 64, size, "unrelated")


def test_invalid_version_and_reference(store: EvidenceStore) -> None:
    receipt = store.publish(b"synthetic reference")
    with error("unsupported_evidence_version"):
        replace(receipt, storage_version="future")
    for ref in ("../x", "/absolute", "C:/absolute", receipt.relative_reference + "/x"):
        with error("invalid_reference"):
            replace(receipt, relative_reference=ref)
    # Revalidation protects against deliberately bypassing frozen construction.
    object.__setattr__(receipt, "relative_reference", "../x")
    with error("invalid_reference"):
        store.read(receipt)


@pytest.mark.parametrize(
    "reference", ["", ".", "..", "../x", "/x", "C:/x", "x\\y", "x//y", "CON", "x."]
)
def test_runtime_rejects_unsafe_relative_paths(store: EvidenceStore, reference: str) -> None:
    with error("invalid_reference"):
        store.runtime.path(reference)


def test_private_boundaries_and_sibling_prefix(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for root in (source, source / "private", tmp_path):
        with error("private_source_overlap"):
            RuntimeBoundary(root, source, "private")
    runtime = RuntimeBoundary(tmp_path / "source-private", source, "private")
    private_mode_with_synthetic_bytes = EvidenceStore(runtime)
    assert (
        private_mode_with_synthetic_bytes.read(
            private_mode_with_synthetic_bytes.publish(b"synthetic private-mode test")
        )
        == b"synthetic private-mode test"
    )
    assert not (source / "private").exists()
    with error("synthetic_local_subtree_required"):
        RuntimeBoundary(source / ".local-other" / "x", source, "synthetic")
    with error("synthetic_local_subtree_required"):
        RuntimeBoundary(source / ".local", source, "synthetic")


def test_bad_root_and_source_paths(tmp_path: Path) -> None:
    with error("absolute_local_path_required"):
        RuntimeBoundary(Path("relative"), SOURCE, "private")
    with error("absolute_local_path_required"):
        RuntimeBoundary(tmp_path / ".." / "escape", SOURCE, "private")
    with error("invalid_runtime_mode"):
        RuntimeBoundary(tmp_path, SOURCE, "unknown")  # type: ignore[arg-type]
    with error("source_directory_required"):
        RuntimeBoundary(tmp_path / "x", tmp_path / "missing", "private")
    file = tmp_path / "ordinary-file"
    file.write_bytes(b"synthetic")
    with error("directory_required"):
        RuntimeBoundary(file, SOURCE, "private")
    with error("directory_required"):
        RuntimeBoundary(file / "child", SOURCE, "private")


def test_directory_and_hardlink_leaf_fail(store: EvidenceStore) -> None:
    receipt = store.publish(b"synthetic linked file")
    final = store.runtime.path(receipt.relative_reference)
    os.link(final, store.runtime.root / "alias.bin")
    with error("untrusted_file_type_or_links"):
        store.read(receipt)
    other = store.publish(b"synthetic directory")
    path = store.runtime.path(other.relative_reference)
    path.unlink()
    path.mkdir()
    with error("untrusted_file_type_or_links"):
        store.read(other)


def test_runtime_subdirectory_file_collision(store: EvidenceStore) -> None:
    file = store.runtime.root / "collision"
    file.write_bytes(b"synthetic")
    with error("directory_required"):
        store.runtime.path("collision/child")


def test_interruption_after_link_never_returns_receipt(
    store: EvidenceStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    prior = store.publish(b"synthetic prior checkpoint evidence")
    raw = b"synthetic interrupted publication"

    def interrupted(staged: Path, final: Path) -> None:
        os.link(staged, final)
        raise OSError("synthetic failure before staging unlink")

    monkeypatch.setattr(evidence, "_publish", interrupted)
    with error("evidence_publication_failed"):
        store.publish(raw)
    assert store.read(prior) == b"synthetic prior checkpoint evidence"
    digest = hashlib.sha256(raw).hexdigest()
    guessed = EvidenceReceipt(digest, len(raw), f"evidence-bytes-v1/objects/{digest}.bin")
    reopened = EvidenceStore(store.runtime)
    # Complete bytes may exist under two names, but remain untrusted pending recovery.
    with error("untrusted_file_type_or_links"):
        reopened.read(guessed)
    with error("untrusted_file_type_or_links"):
        reopened.publish(raw)
    assert len(list(store.runtime.root.rglob("*.part"))) == 1


def test_read_io_failure_has_safe_code(
    store: EvidenceStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt = store.publish(b"synthetic io failure")

    def denied(path: Path) -> bytes:
        raise PermissionError("do not expose this raw OS detail")

    monkeypatch.setattr(evidence, "_read_file", denied)
    with error("evidence_read_failed") as caught:
        store.read(receipt)
    assert caught.value.__suppress_context__


def test_store_initialization_rejects_existing_file(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    root.mkdir()
    (root / "evidence-bytes-v1").write_bytes(b"synthetic blocking file")
    boundary = RuntimeBoundary(root, SOURCE, "synthetic")
    with error("directory_required"):
        EvidenceStore(boundary)


@pytest.mark.parametrize("kind", ["junction", "symlink"])
def test_redirects_rejected_before_and_after_store_open(
    tmp_path: Path, store: EvidenceStore, kind: str
) -> None:
    target = tmp_path / "redirect-target"
    target.mkdir()
    alias = tmp_path / f"{kind}-alias"
    if kind == "junction":
        if os.name != "nt":
            pytest.skip("Windows junction qualification only")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(target)],
            capture_output=True,
        )
        assert result.returncode == 0, "synthetic junction creation failed"
    else:
        try:
            alias.symlink_to(target, target_is_directory=True)
        except OSError as exc:
            if os.name == "nt" and exc.winerror == 1314:
                pytest.skip(
                    "Host lacks Windows symlink privilege (1314); junction tested separately"
                )
            raise
    with error("redirected_path"):
        RuntimeBoundary(alias / "runtime", SOURCE, "private")
    with error("redirected_path"):
        RuntimeBoundary(target / "runtime", alias, "private")
    # A newly introduced alias after opening is rejected on subsequent operations.
    redirected_child = store.runtime.root / "redirected"
    if kind == "junction":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(redirected_child), str(target)],
            capture_output=True,
        )
        assert result.returncode == 0
    else:
        redirected_child.symlink_to(target, target_is_directory=True)
    with error("redirected_path"):
        store.runtime.path("redirected/escape.bin")
    assert not (target / "escape.bin").exists()
    # Both public operations recheck the object directory after construction.
    object_dir = store.runtime.root / "evidence-bytes-v1/objects"
    object_dir.rmdir()  # Empty adapter-owned directory in this isolated test.
    if kind == "junction":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(object_dir), str(target)],
            capture_output=True,
        )
        assert result.returncode == 0
    else:
        object_dir.symlink_to(target, target_is_directory=True)
    raw = b"synthetic blocked alias"
    digest = hashlib.sha256(raw).hexdigest()
    receipt = EvidenceReceipt(digest, len(raw), f"evidence-bytes-v1/objects/{digest}.bin")
    with error("redirected_path"):
        store.publish(raw)
    with error("redirected_path"):
        store.read(receipt)
    assert not list(target.iterdir())
