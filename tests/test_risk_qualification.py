"""Matched research references, explicit profile compatibility and refusal semantics."""

import importlib
import json
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pytest

from prosper import covariance as cv
from prosper import dcc, volatility
from prosper.innovations import InnovationContext, OHLCRow
from prosper.modeled_inputs import InputProfile, ModeledUpload
from prosper.risk_qualification import ResearchFit, fit_r1, profile_issues

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def probe() -> Iterator[ModuleType]:
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(ROOT / "scripts"))
        yield importlib.import_module("qualify_risk_profile")


@dataclass
class Source:
    profile: InputProfile
    context: InnovationContext
    rows: tuple[OHLCRow, ...]
    limits: dict[str, float]


@dataclass
class Experiment(Source):
    fits: tuple[ResearchFit, ...]
    comparisons: list[dict[str, Any]]


@pytest.fixture(scope="module")
def source(probe: ModuleType) -> Source:
    manifest = json.loads(probe.MANIFEST.read_bytes())
    context, rows = probe.source(manifest)
    profile = InputProfile.model_validate(manifest["profile"])
    return Source(profile, context, rows, manifest["comparison"])


@pytest.fixture(scope="module")
def experiment(probe: ModuleType, source: Source) -> Experiment:
    fits = tuple(
        fit_r1(source.context, source.rows, source.profile, variant=v)
        for v in ("idr", "returns-only")
    )
    comparisons = [probe.compare_fit(fit, source.limits) for fit in fits]
    return Experiment(source.profile, source.context, source.rows, source.limits, fits, comparisons)


def test_matched_full_window_keeps_source_order_profile_and_diagnostics(
    experiment: Experiment,
) -> None:
    e = experiment
    assert len(e.context.sessions) == 1260 and len(e.rows) == 3780
    enhanced, standard = e.fits
    assert enhanced.innovation is not None and standard.innovation is not None
    assert enhanced.innovation.input_sha256 == standard.innovation.input_sha256
    assert enhanced.innovation.source_rows == standard.innovation.source_rows == e.rows
    assert enhanced.innovation.innovations != standard.innovation.innovations
    assert enhanced.innovation.identity_sha256 != standard.innovation.identity_sha256
    for fit, comparison in zip(e.fits, e.comparisons, strict=True):
        assert fit.status == "computed"
        result = fit.covariance
        assert result is not None and result.projection is not None and result.dcc_fit is not None
        assert result.security_ids == e.context.security_ids and result.cutoff == e.context.cutoff
        assert len(result.scalars) == 3
        assert all(len(s.starts) == 9 for s in result.scalars)
        assert len(result.dcc_fit.starts) == 12
        assert all(s.data.purpose == "research-window" for s in result.scalars)
        assert all(s.data.variant == fit.variant for s in result.scalars)
        assert comparison["status"] == "compared"
        assert set(comparison["projections"]) == {"1", "21"}
        for horizon, value in comparison["projections"].items():
            projection = value["result"]
            assert projection["annualization"] == 252 and projection["horizon"] == int(horizon)
            assert np.allclose(
                projection["annualized"], np.asarray(projection["cumulative"]) * 252 / int(horizon)
            )
        # This independent fixed nonzero-alpha probe exercises a moving Q path
        # even when the selected fit is at an alpha-zero/flat-persistence boundary.
        fixed = comparison["nonzero_dcc"]
        assert fixed["parameters"] == (0.04, 0.91)
        assert not np.allclose(fixed["terminal_q"], fixed["next_q"], atol=1e-8)


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("lookback_sessions", 3, "lookback_sessions"),
        ("minimum_history_sessions", 12, "minimum_history_sessions"),
        ("annualization_sessions", 365, "annualization_sessions"),
        ("horizon_sessions", 22, "horizon_sessions"),
        ("require_full_window_validation", False, "require_full_window_validation"),
        ("maximum_universe_size", 2, "security_ids"),
        ("model", None, "profile/model"),
    ],
)
def test_incompatible_profile_blocks_before_transformation_or_fit(
    source: Source, monkeypatch: pytest.MonkeyPatch, field: str, value: Any, code: str
) -> None:
    e = source
    profile = InputProfile.model_validate({**e.profile.model_dump(), field: value})

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("incompatible profile must block numerical work")

    monkeypatch.setattr("prosper.risk_qualification.transform_ohlc", forbidden)
    result = fit_r1(e.context, e.rows, profile, variant="idr")
    assert result.status == "unavailable"
    assert result.innovation is None and result.covariance is None
    assert any(code in issue for issue in result.issues)


@pytest.mark.parametrize(
    "model",
    [
        {"identity": "unqualified-example", "f": ".25", "a3": ".17", "kappa": "10000"},
        {"identity": "R1", "f": ".2", "a3": ".17", "kappa": "10000"},
        {"identity": "R1", "f": ".25", "a3": ".17", "kappa": "100"},
        {"identity": "R1", "f": "NaN", "a3": ".17", "kappa": "10000"},
        {"identity": "R1", "f": "invalid", "a3": ".17", "kappa": "10000"},
    ],
)
def test_profile_identity_constants_and_decimal_units_are_not_relabelled(
    source: Source, model: dict[str, str]
) -> None:
    e = source
    profile = InputProfile.model_validate({**e.profile.model_dump(), "model": model})
    assert any("profile/model" in v for v in profile_issues(profile, e.context, "idr"))


def test_decimal_equivalent_constants_and_one_session_are_compatible(
    source: Source,
) -> None:
    e = source
    profile = InputProfile.model_validate(
        {
            **e.profile.model_dump(),
            "horizon_sessions": 1,
            "model": {"identity": "R1", "f": ".2500", "a3": "0.170", "kappa": "1e4"},
        }
    )
    assert not profile_issues(profile, e.context, "returns-only")


def test_unselected_variant_and_single_name_cannot_enter_multivariate_fit(
    source: Source,
) -> None:
    e = source
    unsupported: Any = "automatic-fallback"
    assert any("variant:" in v for v in profile_issues(e.profile, e.context, unsupported))
    single = replace(e.context, security_ids=e.context.security_ids[:1])
    assert any("security_ids" in v for v in profile_issues(e.profile, single, "idr"))


def test_three_session_application_example_is_coverage_only(source: Source) -> None:
    e = source
    upload = ModeledUpload.model_validate_json(
        (ROOT / "examples/synthetic/modeled-inputs/current.json").read_bytes()
    )
    before = upload.model_dump_json()
    result = fit_r1(e.context, e.rows, upload.bundle.profile, variant="idr")
    assert result.status == "unavailable" and result.covariance is None
    assert any("lookback_sessions" in v for v in result.issues)
    assert upload.model_dump_json() == before
    short = replace(e.context, sessions=e.context.sessions[:3], cutoff=e.context.sessions[2])
    result = fit_r1(short, e.rows[:9], e.profile, variant="idr")
    assert any("history/sessions" in v for v in result.issues)


@pytest.mark.parametrize("case", ["vintage", "order", "missing", "cutoff", "zero"])
def test_bad_source_never_fits_a_partial_or_downgraded_universe(
    source: Source, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    e = source
    context, rows = e.context, e.rows
    if case == "vintage":
        rows = (replace(rows[0], ohlc_vintage="different"), *rows[1:])
    elif case == "order":
        rows = (rows[1], rows[0], *rows[2:])
    elif case == "missing":
        rows = rows[:-1]
    elif case == "cutoff":
        context = replace(context, cutoff=context.sessions[-2])
    else:
        rows = tuple(replace(row, total_return="0") for row in rows)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("invalid source must not reach fitting")

    monkeypatch.setattr(cv, "fit_covariance", forbidden)
    result = fit_r1(context, rows, e.profile, variant="idr")
    assert result.status == "unavailable" and result.covariance is None
    assert result.variant == "idr" and result.innovation is not None
    assert result.innovation.context.security_ids == e.context.security_ids
    assert result.innovation.status != "ready"


@pytest.mark.parametrize("component", ["scalar", "dcc"])
def test_fit_failure_keeps_all_diagnostics_and_no_projection(
    experiment: Experiment, monkeypatch: pytest.MonkeyPatch, component: str
) -> None:
    e = experiment
    result = e.fits[0].covariance
    assert result is not None and result.dcc_fit is not None
    scalars = result.scalars
    if component == "scalar":
        failed = replace(scalars[1], status="unavailable", issues=("no_eligible_start",), path=None)
        scalars = (scalars[0], failed, scalars[2])
    by_id = {s.data.security_id: s for s in scalars}
    monkeypatch.setattr(volatility, "fit_volatility", lambda data, **kw: by_id[data.security_id])
    if component == "scalar":

        def forbidden(*args: Any) -> None:
            raise AssertionError("unavailable scalar must block DCC")

        monkeypatch.setattr(dcc, "fit_dcc", forbidden)
    else:
        failed_dcc = replace(
            result.dcc_fit, status="unavailable", issues=("no_eligible_start",), evaluation=None
        )
        monkeypatch.setattr(dcc, "fit_dcc", lambda data: failed_dcc)
    failed_fit = fit_r1(e.context, e.rows, e.profile, variant="idr")
    assert failed_fit.status == "unavailable" and failed_fit.covariance is not None
    assert failed_fit.covariance.projection is None
    assert failed_fit.covariance.scalars == scalars
    assert all(len(s.starts) == 9 for s in failed_fit.covariance.scalars)
    if component == "dcc":
        assert failed_fit.covariance.dcc_fit == failed_dcc


def test_reference_detects_perturbed_transform_and_next_state(
    experiment: Experiment, probe: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    e = experiment
    result = e.fits[0].covariance
    assert result is not None and result.next_q is not None
    altered = replace(result, next_q=tuple(tuple(v + 0.1 for v in row) for row in result.next_q))
    with pytest.raises(AssertionError, match="reference comparison failed"):
        probe.compare_fit(replace(e.fits[0], covariance=altered), e.limits)
    original = probe.reference_rows

    def perturbed(*args: Any) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = original(*args)
        rows[0]["x"] = "0.4"
        return rows

    monkeypatch.setattr(probe, "reference_rows", perturbed)
    with pytest.raises(AssertionError, match="reference comparison failed"):
        probe.compare_fit(e.fits[0], e.limits)


def test_fresh_process_repeats_matched_reference_outputs(
    experiment: Experiment, tmp_path: Path
) -> None:
    output = tmp_path / "comparison.json"
    run = subprocess.run(
        [sys.executable, str(ROOT / "scripts/qualify_risk_profile.py"), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    report = json.loads(output.read_bytes())
    assert report["status"] == "passed"
    assert report["variants"] == json.loads(json.dumps(experiment.comparisons))
