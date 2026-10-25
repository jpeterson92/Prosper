"""Persistent opt-in fictional-clock validation; no timer, live adapter or UI.

Every transition is append-only and checked against prior state. An OS writer
guard serializes policy changes, dispatch and recovery. Opening never dispatches.
An interrupted pending acquisition is not retried implicitly: a committed refresh
is finalized, otherwise interruption is recorded without a provider call.
"""

import hashlib
import json
import os
import sqlite3
import stat
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated, Literal, Self

from pydantic import Field, ValidationError, model_validator

from prosper import history as h
from prosper import history_refresh as f
from prosper.evidence import EvidenceError
from prosper.history_coordination import history_writer
from prosper.history_registry import HistoryRegistry, RegistryProof

NAMESPACE = "history-validation-v1"
DATABASE_REFERENCE = f"{NAMESPACE}/policy.sqlite3"
ADOPTION_MARKER = "history-validation-adopted-v1"
MARKER_BYTES = b"synthetic-validation-policy-v1\n"
APPLICATION_ID = 0x50525631
MAX_DATABASE_BYTES = 128 * 1024 * 1024
MAX_EVENTS = 10000
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
EMPTY = hashlib.sha256(b"synthetic-validation-policy-v1:empty").hexdigest()
META_SQL = "CREATE TABLE policy_state (count INTEGER NOT NULL, tip TEXT NOT NULL) STRICT"
EVENT_SQL = (
    "CREATE TABLE policy_events (sequence INTEGER PRIMARY KEY CHECK(sequence>0), "
    "event_id TEXT UNIQUE NOT NULL, document TEXT NOT NULL, sha256 TEXT NOT NULL) STRICT"
)
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]
Outcome = Literal["complete", "incomplete", "interrupted", "refused"]


class ValidationPolicyError(EvidenceError):
    """Stable refusal codes; missing reserved state never means Off or empty."""


class Settings(h.Closed):
    enabled: bool = False
    cadence_seconds: Annotated[int, Field(strict=True, ge=1, le=2678400)] | None = None
    request: f.Request | None = None

    @model_validator(mode="after")
    def explicit_scope(self) -> Self:
        if not self.enabled:
            if self.cadence_seconds is not None or self.request is not None:
                raise ValueError("disabled_policy_is_never")
        elif self.cadence_seconds is None or self.request is None:
            raise ValueError("enabled_policy_requires_cadence_and_scope")
        elif self.request.mode != "manual" or set(self.request.manual_security_ids) != {
            s.security_id for s in self.request.selection.series
        }:
            raise ValueError("scheduled_scope_requires_full_selected_windows")
        return self


class Event(h.Closed):
    format: Literal["synthetic-validation-event-v1"] = "synthetic-validation-event-v1"
    event_id: Identifier
    kind: Literal["initialize", "configure", "pending", "result"]
    now: h.Text
    expected_generation: int | None = None
    settings: Settings | None = None
    refresh_id: Identifier | None = None
    request: f.Request | None = None
    outcome: Outcome | None = None
    reason: h.Text | None = None


class Pending(h.Closed):
    refresh_id: Identifier
    request: f.Request


class State(h.Closed):
    generation: int
    observed_at: h.Text
    settings: Settings
    next_due: h.Text | None = None
    pending: Pending | None = None
    last_attempt_at: h.Text | None = None
    last_successful_dispatch_at: h.Text | None = None
    last_outcome: (
        Literal["pending", "cancelled", "complete", "incomplete", "interrupted", "refused"] | None
    ) = None
    last_refresh_id: Identifier | None = None


class DispatchResult(h.Closed):
    status: Literal["off", "not_due", "complete", "incomplete", "interrupted", "refused"]
    state: State
    refresh: f.Record | None = None


@dataclass(frozen=True)
class PolicyProof:
    state: State
    events: tuple[Event, ...]
    tip: str


def _bytes(event: Event) -> bytes:
    return json.dumps(event.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()


def _later(now: str, seconds: int) -> str:
    return (datetime.fromisoformat(now) + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _request(settings: Settings, now: str) -> f.Request:
    if settings.request is None:
        raise ValidationPolicyError("validation_scope_missing")
    if settings.request.selection.known_at > now:
        raise ValidationPolicyError("validation_scope_from_future")
    selection = settings.request.selection.model_copy(update={"known_at": now})
    return f._validate_request(
        "validation-scope", settings.request.model_copy(update={"selection": selection})
    )


def _apply(prior: State | None, event: Event, sequence: int, tip: str) -> State:
    h._instant(event.now)
    if prior is not None and event.now < prior.observed_at:
        raise ValidationPolicyError("validation_clock_regressed")
    if event.kind == "initialize":
        if (
            prior is not None
            or sequence != 1
            or event != Event(event_id="initialize", kind="initialize", now=event.now)
        ):
            raise ValidationPolicyError("invalid_validation_initialization")
        return State(generation=1, observed_at=event.now, settings=Settings())
    if prior is None:
        raise ValidationPolicyError("validation_initialization_missing")
    if event.kind == "configure":
        if (
            event.settings is None
            or event.expected_generation != prior.generation
            or event
            != Event(
                event_id=event.event_id,
                kind="configure",
                now=event.now,
                expected_generation=prior.generation,
                settings=event.settings,
            )
        ):
            raise ValidationPolicyError("validation_stale_or_invalid_configuration")
        if event.settings.enabled:
            _request(event.settings, event.now)
        return prior.model_copy(
            update={
                "generation": sequence,
                "observed_at": event.now,
                "settings": event.settings,
                "next_due": _later(event.now, event.settings.cadence_seconds)
                if event.settings.cadence_seconds is not None
                else None,
                "pending": None,
                "last_outcome": "cancelled" if prior.pending else prior.last_outcome,
            }
        )
    if not prior.settings.enabled or prior.settings.cadence_seconds is None:
        raise ValidationPolicyError("validation_dispatch_disabled")
    if event.kind == "pending":
        expected_id = "validation-" + tip[:48]
        expected_request = _request(prior.settings, event.now)
        if (
            prior.pending is not None
            or prior.next_due is None
            or event.now < prior.next_due
            or event
            != Event(
                event_id="pending-" + tip[:48],
                kind="pending",
                now=event.now,
                refresh_id=expected_id,
                request=expected_request,
            )
        ):
            raise ValidationPolicyError("invalid_validation_pending")
        return prior.model_copy(
            update={
                "generation": sequence,
                "observed_at": event.now,
                "pending": Pending(refresh_id=expected_id, request=expected_request),
                "last_attempt_at": event.now,
                "last_outcome": "pending",
                "last_refresh_id": expected_id,
            }
        )
    if (
        prior.pending is None
        or event.outcome is None
        or event
        != Event(
            event_id="result-" + prior.pending.refresh_id,
            kind="result",
            now=event.now,
            refresh_id=prior.pending.refresh_id,
            outcome=event.outcome,
            reason=event.reason,
        )
    ):
        raise ValidationPolicyError("invalid_validation_result")
    if (event.outcome == "refused") != (event.reason is not None):
        raise ValidationPolicyError("invalid_validation_result_reason")
    return prior.model_copy(
        update={
            "generation": sequence,
            "observed_at": event.now,
            "pending": None,
            "last_outcome": event.outcome,
            "next_due": _later(event.now, prior.settings.cadence_seconds),
            "last_successful_dispatch_at": event.now
            if event.outcome == "complete"
            else prior.last_successful_dispatch_at,
        }
    )


def _step(name: str) -> None:
    """Actual durable transaction and dispatch fault-injection boundaries."""


def scheduled_records(
    registry: HistoryRegistry, proof: RegistryProof
) -> Iterator[tuple[str, f.Record]]:
    """Discover required policy from committed trigger evidence, even if directories were lost."""
    for entry in proof.dependencies:
        for supporting in entry.supporting:
            raw = registry.history.evidence.read(supporting.receipt())
            try:
                document = json.loads(raw)
            except (ValueError, UnicodeError):
                continue
            if (
                isinstance(document, dict)
                and document.get("format") == "synthetic-history-refresh-v2"
            ):
                yield entry.dependency_id, f._record(registry, entry)
                break


class ValidationStore:
    def __init__(self, registry: HistoryRegistry) -> None:
        self.registry = registry
        self.runtime = registry.runtime

    @classmethod
    def initialize(cls, registry: HistoryRegistry, *, now: str) -> "ValidationStore":
        event = Event(event_id="initialize", kind="initialize", now=now)
        _apply(None, event, 1, EMPTY)
        result = cls(registry)
        with history_writer(registry.runtime):
            with registry._connection() as connection:
                connection.execute("BEGIN")
                registry_proof = registry._proof(connection)
            if (
                result.runtime.path(ADOPTION_MARKER).exists()
                or result.runtime.path(NAMESPACE).exists()
                or any(scheduled_records(registry, registry_proof))
            ):
                raise ValidationPolicyError("validation_policy_already_reserved")
            with result.runtime.path(ADOPTION_MARKER).open("xb") as marker:
                marker.write(MARKER_BYTES)
                marker.flush()
                os.fsync(marker.fileno())
            _step("initialize_reserved")
            try:
                result.runtime.path(NAMESPACE).mkdir(exist_ok=False)
            except FileExistsError:
                raise ValidationPolicyError("validation_policy_already_reserved") from None
            with result.runtime.path(DATABASE_REFERENCE).open("xb"):
                pass
            with result._connection(writable=True) as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    connection.execute(META_SQL)
                    connection.execute(EVENT_SQL)
                    connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
                    connection.execute("PRAGMA user_version=1")
                    connection.execute("INSERT INTO policy_state VALUES (0, ?)", (EMPTY,))
                    result._insert(connection, event, 1, EMPTY)
                    _step("initialize_before_commit")
                    connection.commit()
                finally:
                    connection.rollback()
            _step("initialize_committed")
        return result

    def _guard(self) -> None:
        self.registry.history._check_ready()
        marker = self.runtime.path(ADOPTION_MARKER)
        try:
            info = marker.lstat()
        except FileNotFoundError:
            raise ValidationPolicyError("validation_adoption_missing") from None
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_size != len(MARKER_BYTES)
        ):
            raise ValidationPolicyError("untrusted_validation_adoption")
        if marker.read_bytes() != MARKER_BYTES:
            raise ValidationPolicyError("invalid_validation_adoption")
        for suffix in ("", "-journal", "-wal", "-shm"):
            path = self.runtime.path(DATABASE_REFERENCE + suffix)
            try:
                info = path.lstat()
            except FileNotFoundError:
                if not suffix:
                    raise ValidationPolicyError("validation_policy_missing") from None
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValidationPolicyError("untrusted_validation_policy")
            if info.st_size > MAX_DATABASE_BYTES:
                raise ValidationPolicyError("validation_policy_size_exceeded")

    @contextmanager
    def _connection(
        self, *, writable: bool = False, readonly: bool = False
    ) -> Iterator[sqlite3.Connection]:
        self._guard()
        try:
            mode = "ro" if readonly else "rw"
            path = self.runtime.path(DATABASE_REFERENCE)
            with closing(
                sqlite3.connect(
                    path.as_uri() + f"?mode={mode}", uri=True, timeout=0, isolation_level=None
                )
            ) as connection:
                connection.execute("PRAGMA trusted_schema=OFF")
                if writable:
                    page_size = connection.execute("PRAGMA page_size").fetchone()[0]
                    connection.execute(f"PRAGMA max_page_count={MAX_DATABASE_BYTES // page_size}")
                else:
                    connection.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
                    connection.execute("PRAGMA query_only=ON")
                yield connection
        except sqlite3.Error:
            raise ValidationPolicyError("validation_policy_database_failed") from None

    @staticmethod
    def _entries(connection: sqlite3.Connection) -> PolicyProof:
        if (
            connection.execute("PRAGMA application_id").fetchone() != (APPLICATION_ID,)
            or connection.execute("PRAGMA user_version").fetchone() != (1,)
            or connection.execute(
                "SELECT type,name,sql FROM sqlite_master "
                "WHERE name NOT GLOB 'sqlite_*' ORDER BY name"
            ).fetchall()
            != [("table", "policy_events", EVENT_SQL), ("table", "policy_state", META_SQL)]
        ):
            raise ValidationPolicyError("incompatible_validation_policy_schema")
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValidationPolicyError("validation_policy_corrupt")
        rows = connection.execute(
            "SELECT sequence,event_id,document,sha256 FROM policy_events ORDER BY sequence LIMIT ?",
            (MAX_EVENTS + 1,),
        ).fetchall()
        if not rows or len(rows) > MAX_EVENTS:
            raise ValidationPolicyError("validation_policy_count_invalid")
        tip, state = EMPTY, None
        events: list[Event] = []
        try:
            for index, (sequence, event_id, document, digest) in enumerate(rows, 1):
                if not isinstance(document, str) or len(document.encode()) > MAX_DOCUMENT_BYTES:
                    raise ValidationPolicyError("validation_event_invalid")
                event = Event.model_validate_json(document)
                if (
                    sequence != index
                    or event.event_id != event_id
                    or _bytes(event).decode() != document
                    or hashlib.sha256(document.encode()).hexdigest() != digest
                ):
                    raise ValidationPolicyError("validation_policy_identity_mismatch")
                state = _apply(state, event, sequence, tip)
                tip = hashlib.sha256(f"{tip}:{digest}".encode()).hexdigest()
                events.append(event)
        except (ValidationError, ValueError, OverflowError):
            raise ValidationPolicyError("validation_event_invalid") from None
        if (
            connection.execute("SELECT * FROM policy_state").fetchall() != [(len(events), tip)]
            or state is None
        ):
            raise ValidationPolicyError("validation_policy_state_mismatch")
        return PolicyProof(state, tuple(events), tip)

    def _proof(self, registry_proof: RegistryProof, *, readonly: bool = False) -> PolicyProof:
        with self._connection(readonly=readonly) as connection:
            connection.execute("BEGIN")
            proof = self._entries(connection)
        entries = {e.dependency_id: e for e in registry_proof.dependencies}
        pending: dict[str, f.Request] = {}
        for event in proof.events:
            if (
                event.kind == "pending"
                and event.refresh_id is not None
                and event.request is not None
            ):
                pending[event.refresh_id] = event.request
                if event.refresh_id in entries:
                    record = f._record(self.registry, entries[event.refresh_id])
                    if record.request != event.request or record.dispatch_event != event.event_id:
                        raise ValidationPolicyError("validation_result_scope_mismatch")
            if event.settings is not None and event.settings.request is not None:
                for cache_id in event.settings.request.cache_ids:
                    if cache_id not in entries:
                        raise ValidationPolicyError("validation_cache_missing")
                    f._record(self.registry, entries[cache_id])
            if event.kind == "result" and event.outcome in ("complete", "incomplete"):
                if event.refresh_id not in entries:
                    raise ValidationPolicyError("validation_refresh_missing")
                record = f._record(self.registry, entries[event.refresh_id])
                if record.complete != (
                    event.outcome == "complete"
                ) or record.request != pending.get(event.refresh_id):
                    raise ValidationPolicyError("validation_result_mismatch")
        pending_events = {
            event.event_id: event for event in proof.events if event.kind == "pending"
        }
        for dependency_id, record in scheduled_records(self.registry, registry_proof):
            trigger = pending_events.get(record.dispatch_event or "")
            if (
                trigger is None
                or trigger.refresh_id != dependency_id
                or trigger.request != record.request
            ):
                raise ValidationPolicyError("validation_trigger_evidence_missing")
        return proof

    def _load(self) -> PolicyProof:
        with self.registry._connection() as connection:
            connection.execute("BEGIN")
            registry_proof = self.registry._proof(connection)
        return self._proof(registry_proof)

    def current(self) -> State:
        with history_writer(self.runtime):
            return self._load().state

    @staticmethod
    def _insert(connection: sqlite3.Connection, event: Event, sequence: int, tip: str) -> None:
        document = _bytes(event)
        if len(document) > MAX_DOCUMENT_BYTES or sequence > MAX_EVENTS:
            raise ValidationPolicyError("validation_policy_size_exceeded")
        digest = hashlib.sha256(document).hexdigest()
        connection.execute(
            "INSERT INTO policy_events VALUES (?,?,?,?)",
            (sequence, event.event_id, document.decode(), digest),
        )
        connection.execute(
            "UPDATE policy_state SET count=?,tip=?",
            (sequence, hashlib.sha256(f"{tip}:{digest}".encode()).hexdigest()),
        )

    def _append(self, proof: PolicyProof, event: Event) -> State:
        sequence = proof.state.generation + 1
        state = _apply(proof.state, event, sequence, proof.tip)
        with self._connection(writable=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                if self._entries(connection) != proof:
                    raise ValidationPolicyError("validation_policy_changed")
                self._insert(connection, event, sequence, proof.tip)
                _step("event_before_commit")
                connection.commit()
            finally:
                connection.rollback()
        _step("event_committed")
        return state

    def configure(
        self, command_id: str, *, expected_generation: int, now: str, settings: Settings
    ) -> State:
        event = Event(
            event_id=command_id,
            kind="configure",
            now=now,
            expected_generation=expected_generation,
            settings=settings,
        )
        event = Event.model_validate_json(_bytes(event))
        with history_writer(self.runtime):
            proof = self._load()
            prior_state: State | None = None
            tip = EMPTY
            for index, old in enumerate(proof.events, 1):
                prior_state = _apply(prior_state, old, index, tip)
                tip = hashlib.sha256(
                    f"{tip}:{hashlib.sha256(_bytes(old)).hexdigest()}".encode()
                ).hexdigest()
                if old.event_id == command_id:
                    if old != event:
                        raise ValidationPolicyError("validation_command_conflict")
                    return prior_state
            if settings.request is not None:
                with self.registry._connection() as connection:
                    connection.execute("BEGIN")
                    entries = {
                        e.dependency_id: e for e in self.registry._proof(connection).dependencies
                    }
                for cache_id in settings.request.cache_ids:
                    if cache_id not in entries:
                        raise ValidationPolicyError("validation_cache_missing")
                    f._record(self.registry, entries[cache_id])
            return self._append(proof, event)

    def dispatch(self, *, now: str, provider: f.Provider) -> DispatchResult:
        h._instant(now)
        with history_writer(self.runtime):
            proof = self._load()
            state = proof.state
            if now < state.observed_at:
                raise ValidationPolicyError("validation_clock_regressed")
            if not state.settings.enabled:
                return DispatchResult(status="off", state=state)
            if state.pending is not None:
                with self.registry._connection() as connection:
                    connection.execute("BEGIN")
                    entries, _ = self.registry._entries(connection)
                entry = next(
                    (e for e in entries if e.dependency_id == state.pending.refresh_id), None
                )
                record = f._record(self.registry, entry) if entry is not None else None
                outcome: Outcome = (
                    "complete"
                    if record and record.complete
                    else "incomplete"
                    if record
                    else "interrupted"
                )
                final = self._append(
                    proof,
                    Event(
                        event_id="result-" + state.pending.refresh_id,
                        kind="result",
                        now=now,
                        refresh_id=state.pending.refresh_id,
                        outcome=outcome,
                    ),
                )
                return DispatchResult(status=outcome, state=final, refresh=record)
            if state.next_due is None or now < state.next_due:
                return DispatchResult(status="not_due", state=state)
            refresh_id = "validation-" + proof.tip[:48]
            with self.registry._connection() as connection:
                connection.execute("BEGIN")
                entries, _ = self.registry._entries(connection)
            if any(e.dependency_id == refresh_id for e in entries):
                raise ValidationPolicyError("validation_refresh_id_conflict")
            try:
                request = _request(state.settings, now)
            except EvidenceError:
                # Do not invent a pending acquisition if its selected policy is already invalid.
                raise ValidationPolicyError("validation_scope_refused") from None
            self._append(
                proof,
                Event(
                    event_id="pending-" + proof.tip[:48],
                    kind="pending",
                    now=now,
                    refresh_id=refresh_id,
                    request=request,
                ),
            )
            _step("dispatch_pending")
            record = None
            reason = None
            try:
                record = f._refresh_locked(
                    self.registry,
                    refresh_id,
                    request,
                    provider,
                    dispatch_event="pending-" + proof.tip[:48],
                )
                outcome = "complete" if record.complete else "incomplete"
            except EvidenceError as error:
                outcome, reason = "refused", error.code
            _step("refresh_committed")
            proof = self._load()
            final = self._append(
                proof,
                Event(
                    event_id="result-" + refresh_id,
                    kind="result",
                    now=now,
                    refresh_id=refresh_id,
                    outcome=outcome,
                    reason=reason,
                ),
            )
            _step("dispatch_completed")
            return DispatchResult(status=outcome, state=final, refresh=record)
