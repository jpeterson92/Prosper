"""Explicit R1 research execution; no investor risk/profile acceptance.

Consume the current supplied input-profile type without changing input coverage
diagnostics. Marks, taxonomy, freshness and investor controls are not qualified by
this numerical experiment. The caller selects the named reference deliberately.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from prosper import covariance, volatility
from prosper.innovations import (
    InnovationContext,
    InnovationProfile,
    InnovationResult,
    OHLCRow,
    transform_ohlc,
)
from prosper.modeled_inputs import InputProfile

Variant = Literal["idr", "returns-only"]


@dataclass(frozen=True)
class ResearchFit:
    status: str
    issues: tuple[str, ...]
    variant: Variant
    innovation: InnovationResult | None
    covariance: covariance.CovarianceResult | None


def profile_issues(
    profile: InputProfile, context: InnovationContext, variant: Variant
) -> tuple[str, ...]:
    """Refuse incompatible supplied settings before transformation or fitting."""
    issues = []
    for field, expected in (
        ("lookback_sessions", 1260),
        ("minimum_history_sessions", 1260),
        ("annualization_sessions", 252),
        ("require_full_window_validation", True),
    ):
        if getattr(profile, field) != expected:
            issues.append(f"profile/{field}: R1 requires {expected}")
    if profile.horizon_sessions not in (1, 21):
        issues.append("profile/horizon_sessions: R1 supports one or 21 sessions")
    model = profile.model
    try:
        if (
            model is None
            or model.identity != "R1"
            or tuple(Decimal(v) for v in (model.f, model.a3, model.kappa))
            != (Decimal("0.25"), Decimal("0.17"), Decimal("10000"))
        ):
            issues.append("profile/model: explicit frozen R1 identity and constants required")
    except InvalidOperation:
        issues.append("profile/model: invalid decimal constants")
    if len(context.sessions) != 1260:
        issues.append("history/sessions: R1 research requires exactly 1260 observations")
    if not 2 <= len(context.security_ids) <= profile.maximum_universe_size:
        issues.append("history/security_ids: complete universe outside supplied research capacity")
    if variant not in ("idr", "returns-only"):
        issues.append("variant: select idr or named returns-only reference explicitly")
    return tuple(issues)


def fit_r1(
    context: InnovationContext,
    rows: tuple[OHLCRow, ...],
    profile: InputProfile,
    *,
    variant: Variant,
) -> ResearchFit:
    """Fit only the complete declared source; never repair or downgrade."""
    issues = profile_issues(profile, context, variant)
    if issues:
        return ResearchFit("unavailable", issues, variant, None, None)
    model = profile.model
    assert model is not None
    innovation = transform_ohlc(
        context,
        rows,
        profile=InnovationProfile(model.identity, model.f, model.a3, model.kappa),
        variant=variant,
        units="decimal",
    )
    if innovation.status != "ready":
        return ResearchFit(
            "unavailable", ("source/innovation: " + innovation.status,), variant, innovation, None
        )
    inputs = tuple(
        volatility.series_from_innovations(
            innovation, j, purpose="research-window", expected_observations=1260
        )
        for j in range(len(context.security_ids))
    )
    result = covariance.fit_covariance(inputs, horizon=profile.horizon_sessions)
    return ResearchFit(
        "computed" if result.projection is not None else "unavailable",
        result.issues,
        variant,
        innovation,
        result,
    )
