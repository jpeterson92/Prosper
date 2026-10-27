"""Frozen OHLC-to-IDR boundary (P22 4.7, 3.2-3.6; research R1).

Metadata is caller-attested construction evidence, never provider qualification.
Exact source lexemes survive the explicit Decimal-to-binary64 analytical cast.
An incomplete grid returns located issues and no partial analytical output.
"""

import hashlib
import json
import math
import platform
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

VERSION = "ohlc-idr-r1-v1"
SPECIFICATION_SHA256 = "9535aac0560aedc2d06d35d4201643d018500683f5f23910446dc52c3704e01b"
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class InnovationContext:
    security_ids: tuple[str, ...]
    sessions: tuple[str, ...]
    cutoff: str
    calendar: str
    timezone: str
    vintage: str
    source_sha256: str
    construction: str
    return_convention: str = "simple-total-return-decimal"


@dataclass(frozen=True)
class OHLCRow:
    session: str
    security_id: str
    total_return: str
    open: str
    high: str
    low: str
    close: str
    action: str
    action_evidence_sha256: str
    return_vintage: str
    ohlc_vintage: str
    action_vintage: str
    compatibility: str


@dataclass(frozen=True)
class InnovationProfile:
    identity: str = "R1"
    f: str = "0.25"
    a3: str = "0.17"
    kappa: str = "10000"


R1_PROFILE = InnovationProfile()


@dataclass(frozen=True)
class InputIssue:
    code: str
    session: str | None
    security_id: str | None
    detail: str


@dataclass(frozen=True)
class InnovationResult:
    status: str
    version: str
    context: InnovationContext
    profile: InnovationProfile
    variant: str
    units: str
    effective_kappa: float | None
    source_rows: tuple[OHLCRow, ...]
    issues: tuple[InputIssue, ...]
    # Row-major T by N immutable tuples; absent on any input failure.
    preceding_close: tuple[tuple[float, ...], ...]
    proxy: tuple[tuple[float, ...], ...]
    innovations: tuple[tuple[float, ...], ...]
    series_status: tuple[str, ...]
    input_sha256: str
    configuration_sha256: str
    output_sha256: str
    identity_sha256: str


def _number(text: str) -> float:
    # Only source strings cross this interface, never implicit numeric coercion.
    if not isinstance(text, str) or not text or text.strip() != text:
        raise ValueError("expected an unpadded decimal lexeme")
    try:
        exact = Decimal(text)
        value = float(exact)
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise ValueError("invalid decimal") from exc
    if not exact.is_finite() or not math.isfinite(value) or (exact != 0 and value == 0):
        raise ValueError("nonfinite or underflowing binary64 cast")
    return value


def regularized_innovation(r: float, proxy: float, kappa: float) -> float:
    """Scalar primitive; units/provenance belong to the enclosing frozen input."""
    if not all(math.isfinite(v) for v in (r, proxy, kappa)) or proxy < 0 or kappa <= 0:
        raise ValueError("invalid regularization arguments")
    return math.tanh((r / 2) * kappa) * math.sqrt(proxy)


def _sha(text: str) -> bool:
    return len(text) == 64 and all(c in "0123456789abcdef" for c in text)


def transform_ohlc(
    context: InnovationContext,
    rows: tuple[OHLCRow, ...],
    *,
    profile: InnovationProfile = R1_PROFILE,
    variant: Literal["idr", "returns-only"] = "idr",
    units: Literal["decimal", "percent-experiment"] = "decimal",
) -> InnovationResult:
    """Transform a complete declared grid, with no fill, drop or variant fallback.

    Inputs always contain decimal simple total returns. The explicitly selected
    percent experiment scales output x by 100, proxy by 10000 and kappa by 1/100.
    This interface checks metadata consistency, not the truth of its attestations.
    """
    issues: list[InputIssue] = []

    def issue(code: str, detail: str, row: OHLCRow | None = None) -> None:
        issues.append(
            InputIssue(code, row.session if row else None, row.security_id if row else None, detail)
        )

    if variant not in ("idr", "returns-only") or units not in ("decimal", "percent-experiment"):
        issue("unsupported_configuration", "explicit variant/output units required")
    try:
        f, a3, kappa = (_number(v) for v in (profile.f, profile.a3, profile.kappa))
        ef, ea3, ekappa = (Decimal(v) for v in (profile.f, profile.a3, profile.kappa))
        if not profile.identity or not (0 < f < 1 and 0 <= a3 <= 1 and kappa > 0):
            raise ValueError("invalid constants")
        if not (0 < ef < 1 and 0 <= ea3 <= 1 and ekappa > 0):
            raise ValueError("source decimal constants outside domain")
        if profile.identity == "R1" and tuple(
            Decimal(v) for v in (profile.f, profile.a3, profile.kappa)
        ) != (Decimal("0.25"), Decimal("0.17"), Decimal("10000")):
            raise ValueError("R1 constants cannot be relabeled")
    except ValueError as exc:
        issue("invalid_profile", str(exc))
        f = a3 = kappa = math.nan  # Unavailable; no calculation with invalid settings.
    if context.return_convention != "simple-total-return-decimal":
        issue("return_convention", "price-only/unknown/percent inputs are unsupported")
    if not all((context.calendar, context.vintage, context.construction)) or not _sha(
        context.source_sha256
    ):
        issue("missing_provenance", "calendar/vintage/construction/source hash required")
    if context.timezone != "UTC":
        issue("timezone", "this interface requires explicitly declared UTC sessions")
    try:
        dates = tuple(date.fromisoformat(s) for s in context.sessions)
        if any(d.isoformat() != s for d, s in zip(dates, context.sessions, strict=True)):
            raise ValueError("noncanonical session")
        if not dates or tuple(sorted(set(dates))) != dates:
            raise ValueError("sessions must be nonempty, unique and increasing")
        if context.cutoff != context.sessions[-1]:
            raise ValueError("cutoff must equal final declared session")
    except ValueError as exc:
        issue("sessions", str(exc))
    ids = context.security_ids
    if not ids or len(set(ids)) != len(ids) or any(not s.strip() or s != s.strip() for s in ids):
        issue("security_identity", "nonempty unique ordered identities required")
    expected = tuple((s, i) for s in context.sessions for i in ids)
    actual = tuple((row.session, row.security_id) for row in rows)
    if actual != expected:
        issue("grid_order", "row coordinates must match the full declared session/security grid")
        for s, i in expected:
            if (s, i) not in actual:
                issues.append(InputIssue("missing_observation", s, i, "no supplied row"))
        for s, i in actual:
            if actual.count((s, i)) > 1 or (s, i) not in expected:
                issues.append(
                    InputIssue("unexpected_observation", s, i, "duplicate/undeclared row")
                )
    parsed: list[tuple[float, ...]] = []
    for row in rows:
        if (
            row.action not in ("none", "split", "dividend", "split-and-dividend")
            or not _sha(row.action_evidence_sha256)
            or row.compatibility != "compatible-total-return-and-raw-ohlc"
        ):
            issue("action_compatibility", "declared action evidence/compatibility required", row)
        if not context.vintage or any(
            v != context.vintage for v in (row.return_vintage, row.ohlc_vintage, row.action_vintage)
        ):
            issue("mixed_vintage", "return/OHLC/action vintages must match frozen context", row)
        try:
            r, o, h, low, c = (
                _number(v) for v in (row.total_return, row.open, row.high, row.low, row.close)
            )
            er, eo, eh, el, ec = (
                Decimal(v) for v in (row.total_return, row.open, row.high, row.low, row.close)
            )
            if er <= -1 or min(eo, eh, el, ec) <= 0 or not el <= min(eo, ec) <= max(eo, ec) <= eh:
                raise ValueError("source decimals violate return/OHLC domain before binary64 cast")
            if r <= -1 or min(o, h, low, c) <= 0 or not low <= min(o, c) <= max(o, c) <= h:
                raise ValueError("require r>-1 and positive ordered OHLC")
            parsed.append((r, o, h, low, c))
        except ValueError as exc:
            issue("invalid_numeric", str(exc), row)
    previous: list[float] = []
    proxies: list[float] = []
    values: list[float] = []
    scale = 100.0 if units == "percent-experiment" else 1.0
    if not issues:
        for row, (r, o, h, low, c) in zip(rows, parsed, strict=True):
            try:
                p = c / (1 + r)
                if not math.isfinite(p) or p <= 0:
                    raise ValueError("derived preceding close is unrepresentable")

                # Safe log ratios also handle extreme finite price rescalings.
                def log_ratio(a: float, b: float) -> float:
                    ratio = a / b
                    return math.log(ratio) if 0 < ratio < math.inf else math.log(a) - math.log(b)

                overnight = log_ratio(o, c) + math.log1p(r)
                range_log = log_ratio(h, low)
                if (a3 > 0 and overnight != 0 and overnight**2 == 0) or (
                    a3 < 1 and range_log != 0 and range_log**2 == 0
                ):
                    raise ValueError("squared log ratio underflow")
                proxy = (a3 / f) * overnight**2 + ((1 - a3) / (1 - f)) * (
                    range_log**2 / (4 * math.log(2))
                )
                x = regularized_innovation(r, proxy, kappa) if variant == "idr" else r
                if variant == "idr" and r != 0 and proxy > 0 and x == 0:
                    raise ValueError("regularized innovation underflow")
                if not all(math.isfinite(v) for v in (proxy * scale**2, x * scale)):
                    raise ValueError("nonfinite derived analytical values")
                previous.append(p)
                proxies.append(proxy * scale**2)
                values.append(x * scale)
            except (ValueError, OverflowError) as exc:
                issue("derived_numeric", str(exc), row)

    def matrix(flat: list[float]) -> tuple[tuple[float, ...], ...]:
        return tuple(tuple(flat[j : j + len(ids)]) for j in range(0, len(flat), len(ids)))

    preceding_matrix: tuple[tuple[float, ...], ...]
    proxy_matrix: tuple[tuple[float, ...], ...]
    innovation_matrix: tuple[tuple[float, ...], ...]
    if issues:
        preceding_matrix = proxy_matrix = innovation_matrix = ()
        statuses: tuple[str, ...] = ()
        status = "unavailable"
    else:
        preceding_matrix, proxy_matrix, innovation_matrix = map(matrix, (previous, proxies, values))

        def series_status(j: int) -> str:
            column = tuple(row[j] for row in innovation_matrix)
            if all(v == 0 for v in column):
                return "zero-second-moment"
            try:
                second_moment = math.fsum(v * v for v in column) / len(column)
            except OverflowError:
                return "unrepresentable-second-moment"
            return (
                "usable"
                if math.isfinite(second_moment) and second_moment > 0
                else "unrepresentable-second-moment"
            )

        statuses = tuple(series_status(j) for j in range(len(ids)))
        status = "ready" if all(s == "usable" for s in statuses) else "unusable-series"
    input_hash = fingerprint({"context": asdict(context), "rows": [asdict(row) for row in rows]})
    config_hash = fingerprint(
        {
            "version": VERSION,
            "profile": asdict(profile),
            "variant": variant,
            "units": units,
            "cast": "decimal-lexeme-to-binary64",
            "specification": SPECIFICATION_SHA256,
            "implementation": IMPLEMENTATION_SHA256,
            "runtime": [platform.python_version(), platform.system(), platform.machine()],
        }
    )
    output_hash = fingerprint(
        {
            "status": status,
            "issues": [asdict(i) for i in issues],
            "previous": preceding_matrix,
            "proxy": proxy_matrix,
            "innovations": innovation_matrix,
            "series_status": statuses,
        }
    )
    return InnovationResult(
        status,
        VERSION,
        context,
        profile,
        variant,
        units,
        kappa / scale if math.isfinite(kappa) else None,
        rows,
        tuple(issues),
        preceding_matrix,
        proxy_matrix,
        innovation_matrix,
        statuses,
        input_hash,
        config_hash,
        output_hash,
        fingerprint([input_hash, config_hash, output_hash]),
    )
