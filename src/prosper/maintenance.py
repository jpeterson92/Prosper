"""Guarded foundation recovery. No financial row repair or inferred import intent.

SQLite's write transaction serializes application/recovery writers. Direct raw
publishers may race and fail safely; transaction-time evidence checks still
prevent committing a missing object. Hostile path replacement is unqualified.
"""

import hashlib
import os
import re
import sqlite3
import stat
from contextlib import closing
from dataclasses import dataclass, replace
from typing import Literal

from prosper.bundle import MAX_BYTES
from prosper.evidence import (
    STORAGE_VERSION,
    EvidenceError,
    EvidenceReceipt,
    EvidenceStore,
    RuntimeBoundary,
)
from prosper.inspection import (
    ArtifactRole,
    FileObservation,
    Finding,
    RecoveryInspection,
    _snapshot,
    inspect_recovery,
)
from prosper.persistence import CheckpointStore, PersistenceError
from prosper.recovery import (
    RecoveryError,
    _references_connection,
    _separate,
    _verify_connection,
    restore,
)


@dataclass(frozen=True)
class RecoveryAction:
    kind: Literal["removed_staging_alias", "removed_unreferenced_object"]
    reference: str
    sha256: str
    file_identity: tuple[int, int]


@dataclass(frozen=True)
class RecoveryResult:
    status: Literal["verified", "retained", "partial", "restored"]
    before: RecoveryInspection
    after: RecoveryInspection
    actions: tuple[RecoveryAction, ...] = ()
    retained: tuple[Finding, ...] = ()
    planning_ready: Literal[False] = False


def _step(name: str) -> None:
    """Fault-injection seam at actual operation boundaries; no user callback."""


def _before_unlink(connection: sqlite3.Connection, reference: str) -> None:
    """Test seam before final transaction/reference/path/hash checks."""


def _eligible(report: RecoveryInspection, *, advisory: bool = False) -> bool:
    permitted = {"local_publication_alias", "untrusted_file_type_or_links"}
    if advisory:
        permitted |= {"inventory_changed", "snapshot_changed"}
    return (
        len(report.databases) == 1
        and report.databases[0].required is not None
        and report.databases[0].snapshot_sha256 is not None
        and all(finding.code in permitted for finding in report.findings)
    )


def _proof(runtime: RuntimeBoundary, nodes: tuple[FileObservation, ...]) -> bytes:
    """Verify the complete observed local alias set, including the survivor.

    Single-link canonical objects use the same proof with a one-node set.
    All paths are resolved/guarded again, never accepted from a caller report.
    """
    objects = [node for node in nodes if node.kind == "object"]
    if not nodes or len(objects) != 1:
        raise RecoveryError("recovery_proof_invalid")
    original = objects[0]
    identity = original.file_identity
    if identity is None or identity[1] == 0 or original.sha256 is None:
        raise RecoveryError("recovery_proof_invalid")
    root = runtime.root.resolve()
    for node in nodes:
        pattern = (
            rf"{STORAGE_VERSION}/objects/[0-9a-f]{{64}}\.bin"
            if node.kind == "object"
            else rf"{STORAGE_VERSION}/staging/[0-9a-f]{{32}}\.part"
        )
        if not re.fullmatch(pattern, node.reference):
            raise RecoveryError("recovery_proof_invalid")
        path = runtime.path(node.reference)
        if not path.resolve().is_relative_to(root):
            raise RecoveryError("recovery_path_escape")
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or (info.st_dev, info.st_ino) != identity
            or info.st_nlink != len(nodes)
            or info.st_size != original.byte_length
            or node.file_identity != identity
            or node.sha256 != original.sha256
            or node.byte_length != original.byte_length
        ):
            raise RecoveryError("recovery_proof_changed")
    path = runtime.path(original.reference)
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_nlink) != (*identity, len(nodes)):
            raise RecoveryError("recovery_proof_changed")
        raw = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
        if (
            (after.st_dev, after.st_ino, after.st_nlink, after.st_size, after.st_mtime_ns)
            != (opened.st_dev, opened.st_ino, opened.st_nlink, opened.st_size, opened.st_mtime_ns)
            or len(raw) != original.byte_length
            or len(raw) > MAX_BYTES
            or hashlib.sha256(raw).hexdigest() != original.sha256
            or original.reference != f"{STORAGE_VERSION}/objects/{original.sha256}.bin"
        ):
            raise RecoveryError("recovery_proof_changed")
    return raw


class _AliasEvidence(EvidenceStore):
    """Only for pre-mutation full verification of already proven local aliases."""

    def __init__(
        self, runtime: RuntimeBoundary, groups: dict[str, tuple[FileObservation, ...]]
    ) -> None:
        runtime.check()
        self.runtime = runtime
        self.groups = groups

    def read(self, receipt: EvidenceReceipt) -> bytes:
        receipt.check()
        group = self.groups.get(receipt.relative_reference)
        if group is None:
            return super().read(receipt)
        raw = _proof(self.runtime, group)
        if len(raw) != receipt.byte_length or hashlib.sha256(raw).hexdigest() != receipt.raw_sha256:
            raise RecoveryError("recovery_required_evidence_mismatch")
        return raw


def _groups(report: RecoveryInspection) -> dict[str, tuple[FileObservation, ...]]:
    groups: dict[str, tuple[FileObservation, ...]] = {}
    for node in report.files:
        if node.kind == "object" and node.classification == "local_publication_alias":
            group = tuple(
                other for other in report.files if other.file_identity == node.file_identity
            )
            if any(other.classification != "local_publication_alias" for other in group):
                raise RecoveryError("recovery_proof_invalid")
            groups[node.reference] = group
    return groups


def _unlink(
    runtime: RuntimeBoundary,
    connection: sqlite3.Connection,
    node: FileObservation,
    group: tuple[FileObservation, ...],
    kind: Literal["removed_staging_alias", "removed_unreferenced_object"],
) -> RecoveryAction:
    _before_unlink(connection, node.reference)
    required = _references_connection(connection)
    if any(receipt.relative_reference == node.reference for receipt in required):
        raise RecoveryError("recovery_reference_now_required")
    # For aliases, the required survivor's length/hash must still agree too.
    original = next(item for item in group if item.kind == "object")
    if any(
        receipt.relative_reference == original.reference
        and (receipt.raw_sha256 != original.sha256 or receipt.byte_length != original.byte_length)
        for receipt in required
    ):
        raise RecoveryError("recovery_required_evidence_mismatch")
    _proof(runtime, group)
    target = runtime.path(node.reference)
    if not target.resolve().is_relative_to(runtime.root.resolve()):
        raise RecoveryError("recovery_path_escape")
    _step("validated_unlink")
    target.unlink()  # One proven leaf only; never recursive/wildcard cleanup.
    assert node.sha256 is not None and node.file_identity is not None
    return RecoveryAction(kind, node.reference, node.sha256, node.file_identity)


def _retained(report: RecoveryInspection) -> tuple[Finding, ...]:
    return tuple(
        sorted(
            {
                *report.findings,
                *(
                    Finding(node.reference, "unbound_staging_preserved")
                    for node in report.files
                    if node.kind == "staging" and node.classification == "unreferenced_staging"
                ),
            }
        )
    )


def maintain_runtime(runtime: RuntimeBoundary) -> RecoveryResult:
    """Reprove state under the SQLite writer lock; repair aliases and prune orphans.

    No caller-supplied inventory, no financial SQL writes and no initializer.
    Unqualified initial state is preserved before writable SQLite is opened.
    """
    before = inspect_recovery(runtime, "runtime")
    actions: list[RecoveryAction] = []
    if not _eligible(before, advisory=True):
        return RecoveryResult("retained", before, before, retained=_retained(before))
    try:
        _step("before_lock")
        normal = CheckpointStore.existing(EvidenceStore.existing(runtime))
        with closing(normal._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                normal._check_schema(connection)
                _step("locked")
                observed = inspect_recovery(runtime, "runtime")
                if not _eligible(observed):
                    return RecoveryResult(
                        "retained", before, observed, retained=_retained(observed)
                    )
                groups = _groups(observed)
                proof_store = CheckpointStore.existing(_AliasEvidence(runtime, groups))
                expected, _ = _verify_connection(proof_store, connection)
                snapshot = _snapshot(connection)
                _step("state_proven")
                for group in groups.values():
                    remaining = group
                    _proof(runtime, remaining)
                    for node in group:
                        if node.kind == "staging":
                            actions.append(
                                _unlink(
                                    runtime, connection, node, remaining, "removed_staging_alias"
                                )
                            )
                            remaining = tuple(
                                replace(other, links=len(remaining) - 1)
                                for other in remaining
                                if other.reference != node.reference
                            )
                            _step("after_unlink")
                _verify_connection(normal, connection)
                clean = inspect_recovery(runtime, "runtime")
                if clean.status != "verified":
                    return RecoveryResult(
                        "partial" if actions else "retained",
                        before,
                        clean,
                        tuple(actions),
                        _retained(clean),
                    )
                for node in clean.files:
                    if node.kind == "object" and node.classification == "unreferenced_object":
                        actions.append(
                            _unlink(
                                runtime, connection, node, (node,), "removed_unreferenced_object"
                            )
                        )
                        _step("after_unlink")
                final, _ = _verify_connection(normal, connection)
                if final != expected or _snapshot(connection) != snapshot:
                    raise RecoveryError("recovery_state_changed")
                _step("state_reverified")
                after = inspect_recovery(runtime, "runtime")
                retained = _retained(after)
                status: Literal["verified", "retained", "partial"] = (
                    "retained" if retained else "verified"
                )
                return RecoveryResult(status, before, after, tuple(actions), retained)
            finally:
                # File actions are individually safe, not rollbackable. No SQL
                # writes belong here; release the lock without committing facts.
                connection.rollback()
    except (EvidenceError, PersistenceError) as error:
        code = error.code
    except (OSError, sqlite3.Error):
        code = "recovery_operation_failed"
    after = inspect_recovery(runtime, "runtime")
    retained = tuple(sorted({*_retained(after), Finding(".", code)}))
    return RecoveryResult(
        "partial" if actions else "retained", before, after, tuple(actions), retained
    )


def recover_from_backup(
    source: RuntimeBoundary,
    role: ArtifactRole,
    backup: RuntimeBoundary,
    destination: RuntimeBoundary,
) -> RecoveryResult:
    """Preserve an explicit source artifact and restore a compatible backup anew.

    Unbound markers/failed initialization are never resumed or overwritten.
    Backup/schema/implementation compatibility is not widened by this wrapper.
    """
    before = inspect_recovery(source, role)
    attempted = False
    try:
        _separate(source, backup)
        _separate(source, destination)
        _separate(backup, destination)
        selected = inspect_recovery(backup, "backup")
        if selected.status != "verified":
            return RecoveryResult(
                "retained",
                before,
                selected,
                retained=(Finding(".", "verified_compatible_backup_required"),),
            )
        attempted = True
        restore(backup, destination)
        after = inspect_recovery(destination, "runtime")
        if after.status != "verified":
            return RecoveryResult("partial", before, after, retained=_retained(after))
        return RecoveryResult("restored", before, after, retained=_retained(before))
    except (EvidenceError, PersistenceError) as error:
        code = error.code
    except (OSError, sqlite3.Error):
        code = "recovery_restore_failed"
    after = inspect_recovery(destination, "runtime")
    status: Literal["partial", "retained"] = (
        "partial"
        if attempted and destination.root.exists() and code != "destination_exists"
        else "retained"
    )
    return RecoveryResult(status, before, after, retained=(Finding(".", code),))
