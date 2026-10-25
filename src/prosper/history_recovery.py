"""Explicitly scoped synthetic required-history snapshots and isolated restore.

Foundation backups retain their separate format/scope. Only registered history
is included here; unreferenced publications/caches and lot state are excluded.
No migrations, in-place repair, financial readiness or power-loss guarantee.
"""

import json
import re
import sqlite3
from contextlib import closing
from importlib.metadata import version
from typing import Annotated, Literal, Self

from pydantic import Field, SerializerFunctionWrapHandler, model_serializer, model_validator

from prosper import history_validation as validation
from prosper.bundle import MAX_BYTES
from prosper.evidence import (
    EvidenceError,
    EvidenceReceipt,
    RuntimeBoundary,
    _publish,
    _write_staged,
)
from prosper.history import VERSION, Closed, HistoryStore
from prosper.history_coordination import history_writer
from prosper.history_registry import (
    DATABASE_REFERENCE,
    MAX_DATABASE_BYTES,
    HistoryRegistry,
    RegistryProof,
)
from prosper.history_validation import ValidationStore
from prosper.persistence import _check_recorded_time
from prosper.previews import _now
from prosper.recovery import (
    BackupFile,
    _copy,
    _file,
    _reserve,
    _separate,
    implementation_identity,
)

MANIFEST_NAME = "required-history-backup.json"
RESTORE_MARKER = "history-restore-in-progress"
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_OBJECTS = 10000


class HistoryRecoveryError(EvidenceError):
    """Stable refusal codes; no supplied payloads or local paths."""


class HistoryBackupManifest(Closed):
    format: Literal["prosper-required-history-backup-v1", "prosper-required-history-backup-v2"] = (
        "prosper-required-history-backup-v1"
    )
    scope: Literal[
        "registered-synthetic-history-only", "registered-synthetic-history-and-validation-policy"
    ] = "registered-synthetic-history-only"
    implementation_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    application_version: str
    candidate_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]
    created_at: str
    registry: BackupFile
    state_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    dependency_count: Annotated[int, Field(strict=True, ge=0, le=10000)]
    evidence: Annotated[tuple[BackupFile, ...], Field(max_length=MAX_OBJECTS)]
    validation_policy: BackupFile | None = None
    validation_marker: BackupFile | None = None
    excluded: Literal["foundation-state-and-unreferenced-history"] = (
        "foundation-state-and-unreferenced-history"
    )

    @model_serializer(mode="wrap")
    def versioned_fields(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        document: dict[str, object] = handler(self)
        if self.format == "prosper-required-history-backup-v1":
            document.pop("validation_policy", None)
            document.pop("validation_marker", None)
        return document

    @model_validator(mode="after")
    def policy_scope(self) -> Self:
        legacy = self.format == "prosper-required-history-backup-v1"
        if (
            legacy != (self.validation_policy is None)
            or legacy != (self.validation_marker is None)
            or legacy != (self.scope == "registered-synthetic-history-only")
        ):
            raise ValueError("incompatible_history_backup_scope")
        if self.validation_policy is not None and (
            self.validation_policy.reference != validation.DATABASE_REFERENCE
            or self.validation_policy.byte_length > validation.MAX_DATABASE_BYTES
        ):
            raise ValueError("invalid_validation_backup_reference")
        if self.validation_marker is not None and (
            self.validation_marker.reference != validation.ADOPTION_MARKER
            or self.validation_marker.byte_length != len(validation.MARKER_BYTES)
        ):
            raise ValueError("invalid_validation_backup_marker")
        return self


def _step(name: str) -> None:
    """Fault injection at actual completed publication boundaries."""


def _payload(manifest: HistoryBackupManifest) -> bytes:
    return json.dumps(
        manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()


def _history(boundary: RuntimeBoundary) -> HistoryStore:
    return HistoryStore(boundary, existing=True)


def _proof(history: HistoryStore) -> RegistryProof:
    """Constructor-free registry verification, without recovering/mutating a backup."""
    registry = HistoryRegistry(history)
    registry._guard()
    path = registry.runtime.path(DATABASE_REFERENCE)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0)) as connection:
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        return registry._proof(connection)


def _new_history(boundary: RuntimeBoundary) -> HistoryStore:
    history = HistoryStore(boundary)
    # Fresh coordination identity, before the registry namespace is reserved.
    with history_writer(history.evidence.runtime, create=True):
        pass
    return history


def _manifest(source: RuntimeBoundary) -> HistoryBackupManifest:
    _file(source, MANIFEST_NAME, MAX_MANIFEST_BYTES)
    with source.path(MANIFEST_NAME).open("rb") as stream:
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    manifest = HistoryBackupManifest.model_validate_json(raw)
    # Canonical syntax also refuses duplicate fields and unknown/alternate encodings.
    if raw != _payload(manifest):
        raise HistoryRecoveryError("history_backup_manifest_invalid")
    _check_recorded_time(manifest.created_at)
    if (
        manifest.implementation_sha256 != implementation_identity()
        or manifest.application_version != version("prosper-local")
        or manifest.registry.reference != DATABASE_REFERENCE
        or manifest.registry.byte_length > MAX_DATABASE_BYTES
    ):
        raise HistoryRecoveryError("incompatible_history_backup")
    return manifest


def _verify(history: HistoryStore, manifest: HistoryBackupManifest) -> RegistryProof:
    runtime = history.evidence.runtime
    if _file(runtime, DATABASE_REFERENCE, MAX_DATABASE_BYTES) != manifest.registry:
        raise HistoryRecoveryError("history_backup_identity_mismatch")
    # Validate receipt paths before opening any supplied evidence reference.
    receipts = tuple(
        EvidenceReceipt(x.sha256, x.byte_length, x.reference) for x in manifest.evidence
    )
    if tuple(sorted({r.relative_reference for r in receipts})) != tuple(
        r.relative_reference for r in receipts
    ):
        raise HistoryRecoveryError("history_backup_reference_mismatch")
    with history_writer(runtime):
        proof = _proof(history)
        if manifest.validation_policy is None:
            if (
                runtime.path(validation.NAMESPACE).exists()
                or runtime.path(validation.ADOPTION_MARKER).exists()
                or any(validation.scheduled_records(HistoryRegistry(history), proof))
            ):
                raise HistoryRecoveryError("history_backup_policy_omitted")
        else:
            if (
                manifest.validation_marker is None
                or _file(runtime, validation.ADOPTION_MARKER, 128) != manifest.validation_marker
            ):
                raise HistoryRecoveryError("history_backup_policy_identity_mismatch")
            if (
                _file(runtime, validation.DATABASE_REFERENCE, validation.MAX_DATABASE_BYTES)
                != manifest.validation_policy
            ):
                raise HistoryRecoveryError("history_backup_policy_identity_mismatch")
            ValidationStore(HistoryRegistry(history))._proof(proof, readonly=True)
        # Registered assemblies contain typed references beyond the history envelope.
        # Load their numerical consumer only when that kind is actually present.
        has_assembly = False
        for entry in proof.dependencies:
            for reference in entry.supporting:
                try:
                    document = json.loads(history.evidence.read(reference.receipt()))
                except (ValueError, UnicodeError):
                    continue
                if (
                    isinstance(document, dict)
                    and document.get("format") == "synthetic-risk-inputs-v1"
                ):
                    has_assembly = True
                    break
            if has_assembly:
                break
        if has_assembly:
            from prosper.risk_inputs import verify_dependencies

            verify_dependencies(
                HistoryRegistry(history), {e.dependency_id: e for e in proof.dependencies}
            )
    if (
        proof.required != receipts
        or proof.state_sha256 != manifest.state_sha256
        or len(proof.dependencies) != manifest.dependency_count
    ):
        raise HistoryRecoveryError("history_backup_reference_mismatch")
    return proof


def inspect_backup(source: RuntimeBoundary) -> HistoryBackupManifest:
    """Return only a completely verified compatible backup; failures never grant readiness."""
    try:
        manifest = _manifest(source)
        _verify(_history(source), manifest)
        return manifest
    except HistoryRecoveryError:
        raise
    except (OSError, sqlite3.Error, ValueError, RecursionError):
        raise HistoryRecoveryError("history_backup_unverified") from None


def backup(
    registry: HistoryRegistry, destination: RuntimeBoundary, *, candidate_id: str
) -> HistoryBackupManifest:
    """Hold the shared writer guard through snapshot/closure copy; manifest publishes last."""
    try:
        if not isinstance(candidate_id, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", candidate_id
        ):
            raise HistoryRecoveryError("invalid_candidate_identity")
        _separate(registry.history.runtime, destination)
        with history_writer(registry.runtime):
            registry.history._check_ready()
            with registry._connection() as connection:
                connection.execute("BEGIN")
                proof = registry._proof(connection)
                if len(proof.required) > MAX_OBJECTS:
                    raise HistoryRecoveryError("history_backup_size_exceeded")
                _reserve(destination)
                target = _new_history(destination)
                database = target.evidence.runtime.path(DATABASE_REFERENCE)
                database.parent.mkdir()
                with database.open("xb"):
                    pass
                with closing(sqlite3.connect(database)) as snapshot:
                    connection.backup(snapshot)
                _step("backup_snapshot")
                for receipt in proof.required:
                    raw = registry.history.evidence.read(receipt)
                    path = target.evidence.runtime.path(receipt.relative_reference)
                    _write_staged(path, raw)
                _step("backup_evidence")
            runtime = target.evidence.runtime
            policy_file = None
            policy_marker = None
            if (
                registry.runtime.path(validation.NAMESPACE).exists()
                or registry.runtime.path(validation.ADOPTION_MARKER).exists()
                or any(validation.scheduled_records(registry, proof))
            ):
                policy = ValidationStore(registry)
                policy._proof(proof)
                policy_marker = _file(registry.runtime, validation.ADOPTION_MARKER, 128)
                _copy(registry.runtime, runtime, policy_marker, 128)
                policy_path = runtime.path(validation.DATABASE_REFERENCE)
                policy_path.parent.mkdir()
                with policy_path.open("xb"):
                    pass
                with (
                    policy._connection() as source,
                    closing(sqlite3.connect(policy_path)) as snapshot,
                ):
                    source.execute("BEGIN")
                    policy._entries(source)
                    source.backup(snapshot)
                policy_file = _file(
                    runtime, validation.DATABASE_REFERENCE, validation.MAX_DATABASE_BYTES
                )
                _step("backup_policy")
            manifest = HistoryBackupManifest(
                format="prosper-required-history-backup-v2"
                if policy_file
                else "prosper-required-history-backup-v1",
                scope="registered-synthetic-history-and-validation-policy"
                if policy_file
                else "registered-synthetic-history-only",
                implementation_sha256=implementation_identity(),
                application_version=version("prosper-local"),
                candidate_id=candidate_id,
                created_at=_now(),
                registry=_file(runtime, DATABASE_REFERENCE, MAX_DATABASE_BYTES),
                state_sha256=proof.state_sha256,
                dependency_count=len(proof.dependencies),
                evidence=tuple(
                    _file(runtime, r.relative_reference, MAX_BYTES) for r in proof.required
                ),
                validation_policy=policy_file,
                validation_marker=policy_marker,
            )
            _verify(target, manifest)
            payload = _payload(manifest)
            if len(payload) > MAX_MANIFEST_BYTES:
                raise HistoryRecoveryError("history_backup_size_exceeded")
            staged = destination.path("required-history-backup.part")
            _write_staged(staged, payload)
            _step("backup_verified")
            _publish(staged, destination.path(MANIFEST_NAME))
            _step("backup_published")
            return manifest
    except HistoryRecoveryError:
        raise
    except (OSError, sqlite3.Error, ValueError, RecursionError):
        raise HistoryRecoveryError("history_backup_failed") from None


def restore(source: RuntimeBoundary, destination: RuntimeBoundary) -> HistoryBackupManifest:
    """Prove copied closure, publish namespace, then clear the readiness marker."""
    try:
        _separate(source, destination)
        manifest = inspect_backup(source)
        _reserve(destination)
        _write_staged(destination.path(RESTORE_MARKER), b"required-history-restore-v1\n")
        _step("restore_reserved")
        work = RuntimeBoundary(
            destination.path("history-restore-work"), destination.source_root, destination.mode
        )
        work.root.mkdir()
        history = _new_history(work)
        incoming = _history(source).evidence.runtime
        runtime = history.evidence.runtime
        _copy(incoming, runtime, manifest.registry, MAX_DATABASE_BYTES)
        for item in manifest.evidence:
            _copy(incoming, runtime, item, MAX_BYTES)
        if manifest.validation_policy is not None:
            if manifest.validation_marker is None:
                raise HistoryRecoveryError("history_backup_policy_identity_mismatch")
            _copy(incoming, runtime, manifest.validation_marker, 128)
            _copy(incoming, runtime, manifest.validation_policy, validation.MAX_DATABASE_BYTES)
        _step("restore_copied")
        _verify(history, manifest)
        _step("restore_verified")
        runtime.root.rename(destination.path(VERSION))
        _step("restore_published")
        # The published registry is not consumable until this final boundary.
        destination.path(RESTORE_MARKER).unlink()
        _step("restore_ready")
        return manifest
    except HistoryRecoveryError:
        raise
    except (OSError, sqlite3.Error, ValueError, RecursionError):
        raise HistoryRecoveryError("history_restore_failed") from None
