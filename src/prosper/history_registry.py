"""Explicit append-only synthetic dependencies and non-destructive retention.

No run approval, unpin, eviction, backup/restore or financial readiness. Public
history writers and registry/retention proof cooperate through one OS lock.
Unreferenced bytes may be in flight between retain and publish: never delete.
"""

import hashlib
import json
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    ValidationError,
    model_serializer,
    model_validator,
)

from prosper.evidence import EvidenceError, EvidenceReceipt
from prosper.history import (
    Closed,
    FrozenHistory,
    HistoryError,
    HistoryStore,
    RawReference,
    Selection,
)
from prosper.history_coordination import REGISTRY_NAMESPACE, history_writer

REGISTRY_VERSION = "synthetic-history-required-v1"
DATABASE_REFERENCE = f"{REGISTRY_NAMESPACE}/registry.sqlite3"
APPLICATION_ID = 0x50524831
MAX_DEPENDENCIES = 10000
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_DATABASE_BYTES = 128 * 1024 * 1024
_EMPTY = hashlib.sha256(b"synthetic-history-required-v1:empty").hexdigest()
_META_SQL = (
    "CREATE TABLE registry_state ("
    "format TEXT PRIMARY KEY NOT NULL, count INTEGER NOT NULL CHECK(count>=0), "
    "tip TEXT NOT NULL) STRICT"
)
_LINK_SQL = (
    "CREATE TABLE required_history ("
    "sequence INTEGER PRIMARY KEY CHECK(sequence>0), "
    "dependency_id TEXT UNIQUE NOT NULL, document TEXT NOT NULL, sha256 TEXT NOT NULL) STRICT"
)


class RegistryError(EvidenceError):
    """Stable codes, with no supplied payload or local path."""


class Dependency(Closed):
    format: Literal["synthetic-history-dependency-v1", "synthetic-history-dependency-v2"] = (
        "synthetic-history-dependency-v1"
    )
    dependency_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]
    manifest: RawReference
    selection: Selection
    supporting: Annotated[tuple[RawReference, ...], Field(max_length=1001)] = ()

    @model_serializer(mode="wrap")
    def versioned_document(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        document: dict[str, object] = handler(self)
        if self.format == "synthetic-history-dependency-v1":
            document.pop("supporting", None)
        return document

    @model_validator(mode="after")
    def versioned_support(self) -> Self:
        if (self.format == "synthetic-history-dependency-v1") != (not self.supporting):
            raise ValueError("incompatible_dependency_support")
        if tuple(sorted({r.reference for r in self.supporting})) != tuple(
            r.reference for r in self.supporting
        ):
            raise ValueError("ordered_unique_support_required")
        return self


def _document(dependency: Dependency) -> str:
    document = dependency.model_dump(mode="json")
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def _chain(prior: str, document_sha256: str) -> str:
    return hashlib.sha256(f"{prior}:{document_sha256}".encode("ascii")).hexdigest()


def _step(name: str) -> None:
    """Fault-injection seam at actual transaction boundaries."""


@dataclass(frozen=True)
class RegistryProof:
    dependencies: tuple[Dependency, ...]
    required: tuple[EvidenceReceipt, ...]
    state_sha256: str


@dataclass(frozen=True)
class RetentionDecision:
    reference: str
    required: bool | None
    remove_allowed: Literal[False]
    reason: str


class HistoryRegistry:
    """Constructor reopens only; initialize() explicitly reserves a new registry.

    A reserved directory survives missing/failed database creation. Neither reopen
    nor initialize replaces it. Proof covers all entries; replay checks registry
    structure plus the selected dependency, so other damaged inputs stay scoped.
    """

    def __init__(self, history: HistoryStore) -> None:
        self.history = history
        self.runtime = history.evidence.runtime

    @classmethod
    def initialize(cls, history: HistoryStore) -> "HistoryRegistry":
        history._check_ready()
        result = cls(history)
        try:
            with history_writer(result.runtime, create=True):
                directory = result.runtime.path(REGISTRY_NAMESPACE)
                try:
                    directory.mkdir(exist_ok=False)
                except FileExistsError:
                    raise RegistryError("history_registry_already_reserved") from None
                path = result.runtime.path(DATABASE_REFERENCE)
                with path.open("xb"):
                    pass
                with result._connection(writable=True) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    try:
                        connection.execute(_META_SQL)
                        connection.execute(_LINK_SQL)
                        connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                        connection.execute("PRAGMA user_version=1")
                        connection.execute(
                            "INSERT INTO registry_state VALUES (?, 0, ?)",
                            (REGISTRY_VERSION, _EMPTY),
                        )
                        _step("initialize_before_commit")
                        connection.commit()
                    finally:
                        connection.rollback()
                _step("initialize_committed")
        except OSError:
            raise RegistryError("history_registry_initialization_failed") from None
        except sqlite3.Error:
            raise RegistryError("history_registry_database_failed") from None
        result.proof()
        return result

    def _guard(self) -> None:
        self.history._check_ready()
        for suffix in ("", "-journal", "-wal", "-shm"):
            path = self.runtime.path(DATABASE_REFERENCE + suffix)
            try:
                info = path.lstat()
            except FileNotFoundError:
                if not suffix:
                    raise RegistryError("history_registry_missing") from None
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise RegistryError("untrusted_history_registry")
            if info.st_size > MAX_DATABASE_BYTES:
                raise RegistryError("history_registry_size_exceeded")

    @contextmanager
    def _connection(self, *, writable: bool = False) -> Iterator[sqlite3.Connection]:
        self._guard()
        path = self.runtime.path(DATABASE_REFERENCE)
        # mode=rw never creates a missing database. SQLite may recover its hot
        # journal under the writer guard after a process dies; no registry facts
        # are manually repaired. Only register/initialize author SQL writes.
        mode = "rw"
        try:
            with closing(
                sqlite3.connect(
                    path.as_uri() + f"?mode={mode}",
                    uri=True,
                    isolation_level=None,
                    timeout=0,
                )
            ) as connection:
                connection.execute("PRAGMA trusted_schema=OFF")
                if writable:
                    page_size = connection.execute("PRAGMA page_size").fetchone()[0]
                    connection.execute(f"PRAGMA max_page_count={MAX_DATABASE_BYTES // page_size}")
                else:
                    # Permit normal hot-journal recovery before disabling SQL
                    # writes on proof/replay connections.
                    connection.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
                    connection.execute("PRAGMA query_only=ON")
                yield connection
        except sqlite3.Error:
            raise RegistryError("history_registry_database_failed") from None
        except OSError:
            raise RegistryError("history_registry_io_failed") from None

    @staticmethod
    def _entries(connection: sqlite3.Connection) -> tuple[tuple[Dependency, ...], str]:
        expected = [
            ("table", "registry_state", _META_SQL),
            ("table", "required_history", _LINK_SQL),
        ]
        if (
            connection.execute("PRAGMA application_id").fetchone() != (APPLICATION_ID,)
            or connection.execute("PRAGMA user_version").fetchone() != (1,)
            or connection.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE name NOT GLOB 'sqlite_*' ORDER BY name"
            ).fetchall()
            != expected
        ):
            raise RegistryError("incompatible_history_registry_schema")
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise RegistryError("history_registry_corrupt")
        rows = connection.execute(
            "SELECT sequence, dependency_id, document, sha256 FROM required_history "
            "ORDER BY sequence LIMIT ?",
            (MAX_DEPENDENCIES + 1,),
        ).fetchall()
        if len(rows) > MAX_DEPENDENCIES:
            raise RegistryError("history_registry_size_exceeded")
        entries: list[Dependency] = []
        tip = _EMPTY
        for index, (sequence, dependency_id, document, digest) in enumerate(rows, 1):
            if not isinstance(document, str) or len(document.encode()) > MAX_DOCUMENT_BYTES:
                raise RegistryError("invalid_history_dependency")
            try:
                entry = Dependency.model_validate_json(document)
            except (ValidationError, EvidenceError, ValueError):
                raise RegistryError("invalid_history_dependency") from None
            actual = hashlib.sha256(document.encode()).hexdigest()
            if (
                sequence != index
                or entry.dependency_id != dependency_id
                or document != _document(entry)
                or actual != digest
            ):
                raise RegistryError("history_registry_identity_mismatch")
            tip = _chain(tip, actual)
            entries.append(entry)
        if connection.execute("SELECT * FROM registry_state").fetchall() != [
            (REGISTRY_VERSION, len(entries), tip)
        ]:
            raise RegistryError("history_registry_state_mismatch")
        return tuple(entries), tip

    def _proof(self, connection: sqlite3.Connection) -> RegistryProof:
        entries, tip = self._entries(connection)
        required: dict[str, EvidenceReceipt] = {}
        for entry in entries:
            frozen = self.history.read(entry.manifest.receipt(), expected=entry.selection)
            for receipt in (
                frozen.receipt,
                *(s.raw.receipt() for s in frozen.manifest.envelope.sources),
                *(r.receipt() for r in entry.supporting),
            ):
                self.history.evidence.read(receipt)
                prior = required.setdefault(receipt.relative_reference, receipt)
                if prior != receipt:
                    raise RegistryError("history_dependency_reference_mismatch")
        return RegistryProof(entries, tuple(required[k] for k in sorted(required)), tip)

    def proof(self) -> RegistryProof:
        with history_writer(self.runtime):
            with self._connection() as connection:
                connection.execute("BEGIN")
                return self._proof(connection)

    def register(
        self,
        dependency_id: str,
        receipt: EvidenceReceipt,
        *,
        expected: Selection,
        supporting: tuple[EvidenceReceipt, ...] = (),
    ) -> Dependency:
        try:
            proposed = Dependency(
                format="synthetic-history-dependency-v2"
                if supporting
                else "synthetic-history-dependency-v1",
                dependency_id=dependency_id,
                manifest=RawReference.from_receipt(receipt),
                selection=Selection.model_validate_json(expected.model_dump_json()),
                supporting=tuple(RawReference.from_receipt(r) for r in supporting),
            )
        except (ValidationError, EvidenceError, ValueError):
            raise RegistryError("invalid_history_dependency") from None
        with history_writer(self.runtime):
            return self._register(proposed)

    def _register(self, proposed: Dependency) -> Dependency:
        """Append under an already-held shared writer guard (also used by refresh)."""
        proposed = Dependency.model_validate_json(_document(proposed))
        document = _document(proposed)
        if len(document.encode()) > MAX_DOCUMENT_BYTES:
            raise RegistryError("history_registry_size_exceeded")
        with self._connection(writable=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                proof = self._proof(connection)
                for entry in proof.dependencies:
                    if entry.dependency_id == proposed.dependency_id:
                        if entry != proposed:
                            raise RegistryError("history_dependency_conflict")
                        return entry
                if len(proof.dependencies) >= MAX_DEPENDENCIES:
                    raise RegistryError("history_registry_size_exceeded")
                self.history.read(proposed.manifest.receipt(), expected=proposed.selection)
                for item in proposed.supporting:
                    self.history.evidence.read(item.receipt())
                _step("register_verified")
                digest = hashlib.sha256(document.encode()).hexdigest()
                count = len(proof.dependencies) + 1
                connection.execute(
                    "INSERT INTO required_history VALUES (?, ?, ?, ?)",
                    (
                        count,
                        proposed.dependency_id,
                        document,
                        digest,
                    ),
                )
                connection.execute(
                    "UPDATE registry_state SET count=?, tip=?",
                    (
                        count,
                        _chain(proof.state_sha256, digest),
                    ),
                )
                _step("register_before_commit")
                connection.commit()
                _step("register_committed")
                return proposed
            finally:
                connection.rollback()

    def replay(self, dependency_id: str) -> FrozenHistory:
        with history_writer(self.runtime):
            with self._connection() as connection:
                connection.execute("BEGIN")
                entries, _ = self._entries(connection)
                for entry in entries:
                    if entry.dependency_id == dependency_id:
                        for item in entry.supporting:
                            self.history.evidence.read(item.receipt())
                        return self.history.read(entry.manifest.receipt(), expected=entry.selection)
        raise RegistryError("history_dependency_missing")

    def assess_removal(self, reference: str) -> RetentionDecision:
        """Derive all required objects; a candidate never supplies the required set.

        No deletion is authorized. Unknown registry proof is represented by None,
        never an empty set. Unreferenced bytes may still be retained for a publisher.
        """
        try:
            self.runtime.path(reference)
            proof = self.proof()
            required = any(r.relative_reference == reference for r in proof.required)
            return RetentionDecision(
                reference,
                required,
                False,
                "required_history_evidence" if required else "publication_liveness_unknown",
            )
        except (EvidenceError, HistoryError, OSError) as error:
            code = (
                error.code if isinstance(error, EvidenceError) else "history_dependency_unverified"
            )
            return RetentionDecision(reference, None, False, code)
