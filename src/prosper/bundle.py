"""Bounded synthetic JSON parsing and evidence identity; no financial validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal, cast, get_args

from pydantic import ValidationError

from prosper.bundle_schema import CANONICALIZATION_VERSION, BundleDocument, ClosedModel, Metadata

MAX_BYTES = 2 * 1024 * 1024
MAX_DEPTH = 16
MAX_RECORDS = 10000
MAX_ARRAY = 10000
MAX_TEXT = 4096
MAX_ISSUES = 100
MAX_MEMBERS = 1000
FAMILIES = ("accounts", "securities", "positions", "lots", "cash", "activity", "quotes", "coverage")
type Location = tuple[str | int, ...]


@dataclass(frozen=True)
class Issue:
    code: str
    path: Location = ()
    offset: int | None = None


@dataclass
class _Issues:
    items: list[Issue] = field(default_factory=list)
    more: bool = False

    def add(self, code: str, path: Location = (), offset: int | None = None) -> None:
        if len(self.items) < MAX_ISSUES:
            self.items.append(Issue(code, path, offset))
        else:
            self.more = True


@dataclass(frozen=True)
class _Number:
    token: str


@dataclass(frozen=True)
class _Pairs:
    items: tuple[tuple[str, Decoded], ...]


type Decoded = str | bool | None | _Number | _Pairs | list[Decoded]
type InputValue = str | bool | None | _Number | dict[str, InputValue] | tuple[InputValue, ...]
type Canonical = str | bool | None | dict[str, Canonical] | list[Canonical]


def _pairs(items: list[tuple[str, Decoded]]) -> _Pairs:
    return _Pairs(tuple(items))


def _check_depth(text: str, issues: _Issues) -> None:
    depth = 0
    quoted = escaped = False
    for offset, character in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                issues.add("container_depth_exceeded", offset=offset)
                return
        elif character in "]}":
            depth -= 1


def _string(value: str, path: Location, issues: _Issues) -> bool:
    valid = True
    if len(value) > MAX_TEXT:
        issues.add("text_length_exceeded", path)
        valid = False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        issues.add("invalid_unicode_scalar", path)
        valid = False
    return valid


def _walk(value: Decoded, path: Location, issues: _Issues) -> InputValue:
    if issues.more:
        return None
    if isinstance(value, _Pairs):
        if len(value.items) > MAX_MEMBERS:
            issues.add("object_members_exceeded", path)
            return None
        result: dict[str, InputValue] = {}
        for key, child in value.items:
            if not _string(key, path, issues):
                continue
            child_path = (*path, key)
            if key in result:
                issues.add("duplicate_key", child_path)
                continue
            result[key] = _walk(child, child_path, issues)
        return result
    if isinstance(value, list):
        if len(value) > MAX_ARRAY:
            issues.add("array_elements_exceeded", path)
            return None
        return tuple(_walk(child, (*path, index), issues) for index, child in enumerate(value))
    if isinstance(value, str):
        _string(value, path, issues)
    if isinstance(value, _Number) and value.token in ("NaN", "Infinity", "-Infinity"):
        issues.add("json_nonfinite_forbidden", path)
    return value


def _validate_model(
    model: type[ClosedModel], value: InputValue, path: Location, issues: _Issues
) -> ClosedModel | None:
    try:
        return model.model_validate(value)
    except ValidationError as error:
        for detail in error.errors(include_url=False, include_context=False, include_input=False):
            issues.add(detail["type"], (*path, *detail["loc"]))
        return None


def _document(value: InputValue, issues: _Issues) -> BundleDocument | None:
    # Validate each bounded record separately so 10,000 malformed rows cannot create
    # one unbounded Pydantic error tree before the diagnostic limit is applied.
    assert isinstance(value, dict)
    for name in value:
        if name not in BundleDocument.model_fields:
            issues.add("extra_forbidden", (name,))
    for name in BundleDocument.model_fields:
        if name not in value:
            issues.add("missing", (name,))
    if issues.items:
        return None
    typed: dict[str, object] = {}
    metadata = _validate_model(Metadata, value["metadata"], ("metadata",), issues)
    if metadata is not None:
        typed["metadata"] = metadata
    for family in FAMILIES:
        if issues.more:
            break
        rows = value[family]
        if not isinstance(rows, tuple):
            issues.add("tuple_type", (family,))
            continue
        annotation = BundleDocument.model_fields[family].annotation
        # All record arrays are explicitly tuple[ConcreteRecord, ...] in the closed schema.
        model = cast(type[ClosedModel], get_args(annotation)[0])
        models = []
        for index, row in enumerate(rows):
            if issues.more:
                break
            item = _validate_model(model, row, (family, index), issues)
            if item is not None:
                models.append(item)
        typed[family] = tuple(models)
    return None if issues.items else BundleDocument.model_validate(typed)


@dataclass(frozen=True)
class ParsedBundle:
    document: BundleDocument
    raw_bytes: bytes
    raw_sha256: str
    canonical_bytes: bytes
    canonical_sha256: str

    @property
    def status(self) -> Literal["parsed_unvalidated"]:
        return "parsed_unvalidated"


@dataclass(frozen=True)
class ParseResult:
    parsed: ParsedBundle | None
    issues: tuple[Issue, ...]
    further_issues: bool


def _failed(issues: _Issues) -> ParseResult:
    return ParseResult(None, tuple(issues.items), issues.more)


def _duplicates(document: BundleDocument, issues: _Issues) -> None:
    for family, records in document.record_groups():
        seen: set[str] = set()
        composites: set[tuple[str, ...]] = set()
        for index, record in enumerate(records):
            if record.id in seen:
                issues.add("duplicate_record_id", (family, index, "id"))
            seen.add(record.id)
            # Positions and currency balances also have a logical identity beyond row ID.
            key: tuple[str, ...] | None = None
            if family == "positions":
                row = document.positions[index]
                key = (row.account_id, row.security_id, row.checkpoint_id)
            elif family == "cash":
                cash = document.cash[index]
                key = (cash.account_id, cash.currency, cash.checkpoint_id)
            if key is not None:
                if key in composites:
                    issues.add("duplicate_composite_identity", (family, index))
                composites.add(key)
    references = document.metadata.included_activity_ids
    if len(set(references)) != len(references):
        issues.add("duplicate_inclusion_reference", ("metadata", "included_activity_ids"))
    for index, event in enumerate(document.activity):
        if len(set(event.lot_ids)) != len(event.lot_ids):
            issues.add("duplicate_lot_reference", ("activity", index, "lot_ids"))


def _identity(document: BundleDocument) -> bytes:
    data = cast(dict[str, Canonical], document.model_dump(mode="json"))
    for family in FAMILIES:
        records = data[family]
        assert isinstance(records, list)
        records.sort(key=lambda row: str(cast(dict[str, Canonical], row)["id"]))
    metadata = data["metadata"]
    assert isinstance(metadata, dict)
    references = metadata["included_activity_ids"]
    assert isinstance(references, list)
    references.sort(key=str)
    # Other nested arrays retain their input order. Only included IDs are defined as a set.
    envelope: dict[str, Canonical] = {
        "canonicalization_version": CANONICALIZATION_VERSION,
        "document": data,
    }
    return json.dumps(
        envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def parse_bundle(raw: bytes) -> ParseResult:
    """The untrusted-input entry point. Success means parsed, never reconciled."""
    issues = _Issues()
    if not isinstance(raw, bytes):
        issues.add("byte_payload_required")
        return _failed(issues)
    if len(raw) > MAX_BYTES:
        issues.add("byte_limit_exceeded")
        return _failed(issues)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        issues.add("invalid_utf8", offset=error.start)
        return _failed(issues)
    if text.startswith("\ufeff"):
        issues.add("utf8_bom_forbidden", offset=0)
        return _failed(issues)
    _check_depth(text, issues)
    if issues.items:
        return _failed(issues)
    try:
        decoded = cast(
            Decoded,
            json.loads(
                text,
                object_pairs_hook=_pairs,
                parse_int=_Number,
                parse_float=_Number,
                parse_constant=_Number,
            ),
        )
    except json.JSONDecodeError as error:
        issues.add("invalid_json", offset=error.pos)
        return _failed(issues)
    if not isinstance(decoded, _Pairs):
        issues.add("object_root_required")
        return _failed(issues)
    count = sum(
        len(child) for key, child in decoded.items if key in FAMILIES and isinstance(child, list)
    )
    if count > MAX_RECORDS:
        issues.add("record_limit_exceeded")
        return _failed(issues)
    supplied = _walk(decoded, (), issues)
    if issues.items:
        return _failed(issues)
    document = _document(supplied, issues)
    if document is None:
        return _failed(issues)
    _duplicates(document, issues)
    if issues.items:
        return _failed(issues)
    canonical = _identity(document)
    return ParseResult(
        ParsedBundle(
            document,
            raw,
            hashlib.sha256(raw).hexdigest(),
            canonical,
            hashlib.sha256(canonical).hexdigest(),
        ),
        (),
        False,
    )
