"""Shared bounded current record scalars, without checkpoint/exact transport."""

import re
from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, Field, StrictStr
from pydantic_core import PydanticCustomError


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


Identifier = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]
Text = Annotated[StrictStr, Field(min_length=1, max_length=4096), AfterValidator(_text)]
DateText = Annotated[StrictStr, AfterValidator(_date)]
Timestamp = Annotated[StrictStr, AfterValidator(_timestamp)]
