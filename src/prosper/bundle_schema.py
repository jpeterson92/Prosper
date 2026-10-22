"""Closed synthetic record shapes; these models do not reconcile a checkpoint."""

import re
from collections.abc import Callable
from datetime import date, datetime
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StrictStr,
    WithJsonSchema,
    model_validator,
)
from pydantic_core import PydanticCustomError

from prosper.exact import ExactValue, ExactValueError, Sign

SCHEMA_VERSION = "synthetic-checkpoint-v1"
SEMANTICS_VERSION = "authoritative-checkpoint-v1"
CANONICALIZATION_VERSION = "canonical-json-v1"


def _text(value: str) -> str:
    if not value.strip():
        raise PydanticCustomError("empty_text", "Nonempty text required")
    return value


def _date(value: str) -> str:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise PydanticCustomError("iso_date_required", "ISO calendar date required")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise PydanticCustomError("invalid_date", "Invalid calendar date") from error
    return value


def _timestamp(value: str) -> str:
    if not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})",
        value,
    ):
        raise PydanticCustomError("offset_timestamp_required", "Offset timestamp required")
    try:
        datetime.fromisoformat(value)
        # datetime accepts offsets such as +01:60 by normalizing them. Reject those forms.
        if value[-1] != "Z" and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
            raise ValueError("invalid offset")
    except ValueError as error:
        raise PydanticCustomError("invalid_timestamp", "Invalid timestamp") from error
    return value


def _true(value: object) -> Literal[True]:
    if value is not True:
        raise PydanticCustomError("fictional_flag_required", "Literal true required")
    return True


def _decimal(sign: Sign) -> Callable[[object], ExactValue]:
    def validate(value: object) -> ExactValue:
        try:
            if not isinstance(value, str):
                raise ExactValueError("value", "decimal_string_required")
            return ExactValue(value, sign)
        except ExactValueError as error:
            raise PydanticCustomError(error.code, "Unsupported exact value") from error

    return validate


def _serialize_exact(value: ExactValue) -> str:
    return value.canonical


Identifier = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]
Text = Annotated[StrictStr, Field(max_length=4096), AfterValidator(_text)]
DateText = Annotated[StrictStr, AfterValidator(_date)]
Timestamp = Annotated[StrictStr, AfterValidator(_timestamp)]
Nonnegative = Annotated[
    ExactValue,
    BeforeValidator(_decimal(Sign.NONNEGATIVE)),
    PlainSerializer(_serialize_exact),
    WithJsonSchema({"type": "string"}),
]
Positive = Annotated[
    ExactValue,
    BeforeValidator(_decimal(Sign.POSITIVE)),
    PlainSerializer(_serialize_exact),
    WithJsonSchema({"type": "string"}),
]
Signed = Annotated[
    ExactValue,
    BeforeValidator(_decimal(Sign.SIGNED)),
    PlainSerializer(_serialize_exact),
    WithJsonSchema({"type": "string"}),
]


class ClosedModel(BaseModel):
    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, arbitrary_types_allowed=True
    )


class Fact[T](ClosedModel):
    value: T | None
    reason: Text | None

    @model_validator(mode="after")
    def explicit_known_or_unknown(self) -> Self:
        if (self.value is None) != (self.reason is not None):
            raise PydanticCustomError("value_reason_mismatch", "Explicit known or unknown required")
        return self


class Metadata(ClosedModel):
    schema_version: Literal["synthetic-checkpoint-v1"]
    semantics_version: Literal["authoritative-checkpoint-v1"]
    fictional: Annotated[Literal[True], BeforeValidator(_true)]
    bundle_id: Identifier
    source_id: Identifier
    source_version: Text
    profile_id: Identifier
    cutoff: Timestamp
    source_timezone: Text
    inclusion: Fact[Text]
    included_activity_ids: tuple[Identifier, ...]
    stipulations: tuple[Text, ...]


class Record(ClosedModel):
    id: Identifier


class Account(Record):
    source_ref: Identifier
    alias: Text
    profile_id: Identifier
    currency: Literal["USD"]
    role: Literal["traded", "monitor_only"]
    classification: Fact[Text]
    relationship: Fact[Text]
    lot_method: Fact[Text]


class Security(Record):
    source_ref: Identifier
    issuer_id: Fact[Identifier]
    share_class_id: Fact[Identifier]
    ticker: Text
    currency: Literal["USD"]
    security_type: Fact[Text]
    tax_classification: Fact[Text]
    adjustments: Fact[Text]


class Position(Record):
    source_ref: Identifier
    account_id: Identifier
    security_id: Identifier
    checkpoint_id: Identifier
    quantity: Fact[Nonnegative]


class Lot(Record):
    source_ref: Identifier
    account_id: Identifier
    security_id: Identifier
    checkpoint_id: Identifier
    quantity: Fact[Nonnegative]
    acquired: Fact[DateText]
    holding_evidence: Fact[Text]
    basis: Fact[Nonnegative]
    basis_quantum: Fact[Positive]
    adjustments: Fact[Text]


class Cash(Record):
    source_ref: Identifier
    account_id: Identifier
    checkpoint_id: Identifier
    currency: Literal["USD"]
    settled: Fact[Nonnegative]
    available: Fact[Nonnegative]
    unsettled: Fact[Nonnegative]


class Activity(Record):
    source_ref: Identifier
    account_id: Identifier
    security_id: Identifier
    activity_type: Literal["buy", "sell", "dividend", "transfer", "fee", "corporate_action"]
    lot_ids: tuple[Identifier, ...]
    trade_date: Fact[DateText]
    settlement_date: Fact[DateText]
    quantity: Fact[Positive]
    price: Fact[Positive]
    principal: Fact[Nonnegative]
    fees: Fact[Nonnegative]
    cash_movement: Fact[Signed]
    inclusion_evidence: Fact[Text]
    correction_evidence: Fact[Text]
    basis_treatment: Fact[Text]


class Quote(Record):
    source_ref: Identifier
    security_id: Identifier
    currency: Literal["USD"]
    price: Fact[Positive]
    as_of: Fact[Timestamp]
    kind: Fact[Text]
    session: Fact[Text]
    adjustments: Fact[Text]


class Coverage(Record):
    scope: Literal["household", "account"]
    account_id: Fact[Identifier]
    starts: Fact[DateText]
    ends: Fact[DateText]
    status: Literal["complete", "partial", "unknown", "contradictory"]
    evidence: Fact[Text]
    activity_types: tuple[Text, ...]
    automation: Fact[Text]
    other_accounts: Fact[Text]
    outstanding_restrictions: Fact[Text]
    verification_date: Fact[DateText]
    expiry_date: Fact[DateText]


class BundleDocument(ClosedModel):
    metadata: Metadata
    accounts: tuple[Account, ...]
    securities: tuple[Security, ...]
    positions: tuple[Position, ...]
    lots: tuple[Lot, ...]
    cash: tuple[Cash, ...]
    activity: tuple[Activity, ...]
    quotes: tuple[Quote, ...]
    coverage: tuple[Coverage, ...]

    def record_groups(self) -> tuple[tuple[str, tuple[Record, ...]], ...]:
        return (
            ("accounts", self.accounts),
            ("securities", self.securities),
            ("positions", self.positions),
            ("lots", self.lots),
            ("cash", self.cash),
            ("activity", self.activity),
            ("quotes", self.quotes),
            ("coverage", self.coverage),
        )
