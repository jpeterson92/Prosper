"""Independent synthetic assembly arithmetic, provenance, refusal and recovery."""

import hashlib
import json
import math
import runpy
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest

from prosper import history as h
from prosper import history_recovery as recovery
from prosper import history_refresh as f
from prosper import history_registry as r
from prosper import risk_inputs as a
from prosper.evidence import EvidenceError, RuntimeBoundary

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/qualify_risk_inputs.py"
fixture = runpy.run_path(str(SCRIPT))
reference_request = cast(Callable[..., a.Request], fixture["reference_request"])
retain = cast(Callable[[h.HistoryStore, object], h.RawReference], fixture["retain"])
history_request = cast(Callable[..., f.Request], fixture["history_request"])
provider_factory = cast(Callable[[f.Request], f.Provider], fixture["provider_factory"])


def boundary(path: Path) -> RuntimeBoundary:
    return RuntimeBoundary(path, ROOT, "synthetic")


@pytest.fixture
def registry(tmp_path: Path) -> r.HistoryRegistry:
    return r.HistoryRegistry.initialize(h.HistoryStore(boundary(tmp_path / "history")))


def document(registry: r.HistoryRegistry, reference: h.RawReference) -> Any:
    return json.loads(registry.history.evidence.read(reference.receipt()))


def mutate(
    registry: r.HistoryRegistry, reference: h.RawReference, change: Callable[[Any], None]
) -> h.RawReference:
    value = document(registry, reference)
    change(value)
    return retain(registry.history, value)


def test_exact_ratio_weights_pass_frozen_source_proof_idr_and_required_recovery(
    registry: r.HistoryRegistry, tmp_path: Path
) -> None:
    # Independently stipulated 60/90 and 30/90 benchmark values. The source
    # claims and transport must preserve recurring ratios through real consumers.
    req = reference_request(registry, selected_cash=True)
    source = document(registry, req.sources[0])
    basket = document(registry, req.basket)
    taxonomy = document(registry, req.taxonomy)
    for row, ratio in zip(basket["benchmark"], ("2/3", "1/3"), strict=True):
        key = row["weight"]["evidence"]["reference"].split("/")[-1]
        source["facts"][key].update(raw=ratio, unit="exact-ratio")
        row["weight"]["raw"], row["unit"] = ratio, "exact-ratio"
    replacement = retain(registry.history, source)

    def rebind(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("source_sha256") == req.sources[0].sha256:
                value["source_sha256"] = replacement.sha256
            for item in value.values():
                rebind(item)
        elif isinstance(value, list):
            for item in value:
                rebind(item)

    rebind(basket)
    rebind(taxonomy)
    request = req.model_copy(
        update={
            "basket": retain(registry.history, basket),
            "taxonomy": retain(registry.history, taxonomy),
            "sources": (replacement,),
        }
    )
    record = a.publish(registry, "exact-ratios", request)
    assert record.synthetic_ready and record.innovation is not None
    assert record.basket is not None and record.basket.weights is not None
    assert [row.weight.raw for row in record.basket.data.benchmark] == ["2/3", "1/3"]
    assert record.basket.weights.benchmark[0].numerator == "2"  # type: ignore[union-attr]
    assert record.basket.weights.benchmark[0].denominator == "3"  # type: ignore[union-attr]
    assert not record.financial_ready and a.replay(registry, "exact-ratios") == record
    saved, destination = boundary(tmp_path / "ratio-backup"), boundary(tmp_path / "ratio-restored")
    recovery.backup(registry, saved, candidate_id="fictional-exact-ratio-consumer")
    recovery.restore(saved, destination)
    reopened = r.HistoryRegistry(h.HistoryStore(destination, existing=True))
    assert a.replay(reopened, "exact-ratios") == record


def test_complete_union_exact_cash_weights_provenance_and_idr_oracle(
    registry: r.HistoryRegistry,
) -> None:
    req = reference_request(registry, selected_cash=True)
    result = a.publish(registry, "selected", req)
    assert result.synthetic_ready and not result.financial_ready and not result.issues
    assert result.basket is not None and result.basket.weights is not None
    assert Fraction(result.basket.portfolio_nav_usd or "0") == Fraction("483.153")
    weights = result.basket.weights
    assert weights.security_ids == ("FICTION-A", "FICTION-B", "FICTION-C")
    assert [
        Fraction(int(w.numerator), int(w.denominator)) if not isinstance(w, str) else Fraction(w)
        for w in weights.portfolio
    ] == [Fraction(1, 3), Fraction(1, 3), Fraction(0)]
    sectors = {e.group: e for e in result.exposures if e.level == "sector"}
    assert sectors[("sector", "fictional-tech")].active == "-1/6"
    assert sectors[("sector", "fictional-finance")].active == "-1/6"
    assert sectors[("cash", "selected-residual-USD")].portfolio == "1/3"
    assert result.basket.data.positions[0].reference_mark.raw == "161.0510"
    assert result.basket.data.positions[0].quantity.raw == "1.0000"
    innovation = result.innovation
    assert innovation is not None and innovation.status == "ready"
    assert innovation.context.security_ids == weights.security_ids
    assert len(innovation.source_rows) == 15
    assert all(abs(value - 100.0) <= math.ulp(100.0) for value in innovation.preceding_close[0])
    with localcontext() as context:
        context.prec = 90
        proxy = Decimal(17) / 25 * (Decimal(11) / 10).ln() ** 2
        exponential = (-Decimal(1000)).exp()
        expected = (1 - exponential) / (1 + exponential) * proxy.sqrt()
    assert math.isclose(innovation.proxy[0][0], float(proxy), rel_tol=2e-14)
    assert math.isclose(innovation.innovations[0][0], float(expected), rel_tol=2e-14)
    assert a.replay(registry, "selected") == result


def test_new_versions_and_original_replay_are_immutable(registry: r.HistoryRegistry) -> None:
    base_req = reference_request(registry)
    base = a.publish(registry, "base", base_req)
    selected_req = reference_request(registry, selected_cash=True)
    selected = a.publish(registry, "selected", selected_req)
    assert selected.synthetic_ready and base.synthetic_ready
    assert selected.input_sha256 != base.input_sha256
    assert selected.innovation is not None and base.innovation is not None
    assert selected.innovation.identity_sha256 != base.innovation.identity_sha256
    assert a.replay(registry, "base") == base
    assert a.publish(registry, "base", base_req) == base
    with pytest.raises(a.RiskInputError, match="conflict"):
        a.publish(registry, "base", selected_req)


@pytest.mark.parametrize(
    "change",
    [
        "universe",
        "mark",
        "mark-nan",
        "quantity-unknown",
        "stale-mark",
        "future-mark",
        "weight-residual",
        "cash-unknown",
        "extra-schema",
    ],
)
def test_basket_and_mark_blockers_preserve_unknowns_and_never_feed_idr(
    registry: r.HistoryRegistry, change: str
) -> None:
    req = reference_request(registry)

    def alter(value: dict[str, Any]) -> None:
        if change == "universe":
            value["universe"].reverse()
        elif change in ("mark", "mark-nan"):
            value["positions"][0]["reference_mark"]["raw"] = "1.0000" if change == "mark" else "NaN"
        elif change == "quantity-unknown":
            value["positions"][0]["quantity"].update(
                raw=None, unknown_reasons=["unverified shares"]
            )
        elif change in ("stale-mark", "future-mark"):
            value["positions"][0]["reference_mark"]["evidence"][
                "valid_through" if change == "stale-mark" else "recorded"
            ] = "2026-02-02" if change == "stale-mark" else "2026-03-02"
        elif change == "weight-residual":
            value["benchmark"][1]["weight"]["raw"] = "48.54"
        elif change == "cash-unknown":
            value["portfolio_cash"].update(raw=None, unknown_reasons=["selected cash unknown"])
        else:
            value["unrecognized"] = "must not disappear"

    bad = req.model_copy(update={"basket": mutate(registry, req.basket, alter)})
    result = a.publish(registry, "blocked", bad)
    assert not result.synthetic_ready and result.issues and result.innovation is None
    assert not result.financial_ready
    assert a.replay(registry, "blocked") == result
    if change == "weight-residual":
        assert result.basket is not None and result.basket.benchmark_weight_sum == "4927/5000"
        assert result.basket.benchmark_residual == "73/5000"
    if change == "quantity-unknown":
        assert result.basket is not None and result.basket.data.positions[0].quantity.raw is None


@pytest.mark.parametrize(
    "change", ["order", "missing-candidate", "unknown", "future", "source-missing"]
)
def test_taxonomy_complete_dated_provenance_is_required(
    registry: r.HistoryRegistry, change: str
) -> None:
    req = reference_request(registry)

    def alter(value: dict[str, Any]) -> None:
        if change == "order":
            value["records"].reverse()
        elif change == "missing-candidate":
            value["records"].pop()
        elif change == "unknown":
            value["records"][2].update(
                sector=None,
                industry=None,
                unknown_reasons=["unresolved zero-weight candidate classification"],
            )
        elif change == "future":
            value["records"][0]["recorded"] = "2026-03-02"
        else:
            value["source_sha256"] = "0" * 64

    result = a.publish(
        registry,
        "taxonomy-blocked",
        req.model_copy(update={"taxonomy": mutate(registry, req.taxonomy, alter)}),
    )
    assert not result.synthetic_ready and result.innovation is None
    assert a.replay(registry, "taxonomy-blocked") == result


@pytest.mark.parametrize(
    "field,value",
    [
        ("construction", "unknown-action-transform"),
        ("variant", "returns-only"),
        ("units", "percent-experiment"),
    ],
)
def test_unsupported_settings_never_select_fallback(
    registry: r.HistoryRegistry, field: str, value: str
) -> None:
    req = reference_request(registry)
    result = a.publish(registry, "unsupported", req.model_copy(update={field: value}))
    assert not result.synthetic_ready and result.innovation is None
    assert any(i.code == "unsupported_synthetic_construction" for i in result.issues)


def test_invalid_r1_settings_are_retained_with_no_analytical_arrays(
    registry: r.HistoryRegistry,
) -> None:
    req = reference_request(registry)
    profile = mutate(registry, req.profile, lambda value: value.update(kappa="5000"))
    result = a.publish(registry, "profile", req.model_copy(update={"profile": profile}))
    assert not result.synthetic_ready and result.innovation is not None
    assert result.innovation.issues and result.innovation.proxy == ()


def test_exact_exposure_limit_breach_is_retained_without_financial_readiness(
    registry: r.HistoryRegistry,
) -> None:
    req = reference_request(registry)
    limit = {
        "level": "sector",
        "group": ["sector", "fictional-tech"],
        "kind": "absolute",
        "enabled": True,
        "lower": "0",
        "upper": "0.40",
        "evidence": "explicit fictional limit, not investor adoption",
    }
    result = a.publish(
        registry,
        "limit-breach",
        req.model_copy(update={"limits": retain(registry.history, [limit])}),
    )
    assert result.synthetic_ready and not result.financial_ready
    assert result.limit_results[0].status == "breach" and result.limit_results[0].value == "1/2"
    assert a.replay(registry, "limit-breach") == result


@pytest.mark.parametrize("change", ["action", "raw-adjusted", "predecessor", "context", "partial"])
def test_ohlc_action_calendar_and_vintage_compatibility_gate(
    registry: r.HistoryRegistry, change: str
) -> None:
    req = reference_request(registry)
    hist = history_request(names=("FICTION-A", "FICTION-B", "FICTION-C"))
    if change == "context":
        altered = hist.selection.series[1].model_copy(update={"vintage": "different-corpus"})
        hist = hist.model_copy(
            update={
                "selection": hist.selection.model_copy(
                    update={"series": (hist.selection.series[0], altered, hist.selection.series[2])}
                )
            }
        )
    provider = provider_factory(hist)

    class Altered:
        def fetch(self, interval: f.Range) -> bytes:
            value = json.loads(provider.fetch(interval))
            if change in ("action", "predecessor"):
                value["observations"][1 if change == "action" else 0]["dividend"]["text"] = "1.0000"
            elif change == "raw-adjusted":
                for row in value["observations"]:
                    for key in ("open", "high", "low", "close"):
                        row[key]["text"] = str(Decimal(row[key]["text"]) * 2)
            elif change == "partial":
                value["observations"].pop(2)
            return json.dumps(value).encode()

    f.refresh(registry, "changed-history", hist, Altered())
    result = a.publish(
        registry, "history-blocked", req.model_copy(update={"history_id": "changed-history"})
    )
    assert not result.synthetic_ready and result.innovation is None and result.issues
    assert a.replay(registry, "history-blocked") == result


def test_source_lexemes_are_verified_and_raw_replacement_changes_identity(
    registry: r.HistoryRegistry,
) -> None:
    req = reference_request(registry)
    first = a.publish(registry, "first", req)
    # Byte-different source with identical factual claims is attributable new evidence.
    value = document(registry, req.sources[0])
    raw = json.dumps(value, indent=2).encode()
    replacement = registry.history.retain(raw)
    old_hash, new_hash = req.sources[0].sha256, replacement.sha256

    def retarget(value: object) -> object:
        if isinstance(value, dict):
            return {key: retarget(item) for key, item in value.items()}
        if isinstance(value, list):
            return [retarget(item) for item in value]
        return new_hash if value == old_hash else value

    newer = req.model_copy(
        update={
            "sources": (replacement,),
            "basket": retain(registry.history, retarget(document(registry, req.basket))),
            "taxonomy": retain(registry.history, retarget(document(registry, req.taxonomy))),
        }
    )
    second = a.publish(registry, "second", newer)
    assert second.synthetic_ready and first.synthetic_ready
    assert first.input_sha256 != second.input_sha256
    assert first.basket is not None and second.basket is not None
    assert first.basket.portfolio_nav_usd == second.basket.portfolio_nav_usd
    assert a.replay(registry, "first") == first


def test_missing_or_malformed_source_never_becomes_complete(registry: r.HistoryRegistry) -> None:
    req = reference_request(registry)
    unknown = a.publish(registry, "missing-source", req.model_copy(update={"sources": ()}))
    assert not unknown.synthetic_ready and any(
        i.code == "source_evidence_missing" for i in unknown.issues
    )
    broken = registry.history.retain(b"fictional malformed source document")
    bad = a.publish(registry, "malformed", req.model_copy(update={"profile": broken}))
    assert not bad.synthetic_ready and a.replay(registry, "malformed") == bad


def test_backup_restore_preserves_all_inputs_and_fails_corrupt_support(
    registry: r.HistoryRegistry, tmp_path: Path
) -> None:
    req = reference_request(registry)
    result = a.publish(registry, "assembly", req)
    saved, restored = boundary(tmp_path / "backup"), boundary(tmp_path / "restored")
    recovery.backup(registry, saved, candidate_id="frozen-risk-inputs")
    recovery.restore(saved, restored)
    reopened = r.HistoryRegistry(h.HistoryStore(restored, existing=True))
    assert a.replay(reopened, "assembly") == result
    assert reopened.proof() == registry.proof()
    reopened.runtime.path(req.taxonomy.reference).write_bytes(b"fictional damage")
    with pytest.raises(EvidenceError):
        a.replay(reopened, "assembly")
    with pytest.raises(recovery.HistoryRecoveryError):
        recovery.backup(reopened, boundary(tmp_path / "refused"), candidate_id="bad")


def test_required_source_omission_is_detected_even_with_consistent_registry_hashes(
    registry: r.HistoryRegistry, tmp_path: Path
) -> None:
    req = reference_request(registry)
    a.publish(registry, "assembly", req)
    path = registry.runtime.path(r.DATABASE_REFERENCE)
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT sequence,dependency_id,document FROM required_history ORDER BY sequence"
        ).fetchall()
        tip = r._EMPTY
        for sequence, dependency_id, document_text in rows:
            dep = r.Dependency.model_validate_json(document_text)
            if dependency_id == "assembly":
                dep = dep.model_copy(
                    update={"supporting": tuple(x for x in dep.supporting if x != req.profile)}
                )
            encoded = r._document(dep)
            digest = hashlib.sha256(encoded.encode()).hexdigest()
            connection.execute(
                "UPDATE required_history SET document=?,sha256=? WHERE sequence=?",
                (encoded, digest, sequence),
            )
            tip = r._chain(tip, digest)
        connection.execute("UPDATE registry_state SET tip=?", (tip,))
    registry.proof()  # Generic receipts remain valid; domain closure must independently refuse.
    with pytest.raises(a.RiskInputError, match="required_source_omitted"):
        a.replay(registry, "assembly")
    saved = boundary(tmp_path / "refused-backup")
    with pytest.raises(recovery.HistoryRecoveryError):
        recovery.backup(registry, saved, candidate_id="omitted-source")
    assert not saved.path(recovery.MANIFEST_NAME).exists()


CHILD = """
import os,runpy,sys,time
from pathlib import Path
from prosper import history as h,history_registry as r,risk_inputs as a
from prosper.evidence import RuntimeBoundary
root,runtime,phase,signal,release=sys.argv[1:]
fixture=runpy.run_path(str(Path(root)/'scripts/qualify_risk_inputs.py'))
registry=r.HistoryRegistry(h.HistoryStore(RuntimeBoundary(Path(runtime),Path(root),'synthetic'),existing=True))
request=fixture['reference_request'](registry)
def hook(name):
    if name==phase:
        Path(signal).write_text('paused')
        if release=='die': os._exit(78)
        while not Path(release).exists(): time.sleep(0.02)
a._step=hook
a.publish(registry,'child',request)
"""


@pytest.mark.parametrize("phase", ["assembly_verified", "record_published", "assembly_registered"])
def test_actual_process_death_preserves_versions_and_safe_retry(
    registry: r.HistoryRegistry, tmp_path: Path, phase: str
) -> None:
    req = reference_request(registry)
    original = a.publish(registry, "original", req)
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            CHILD,
            str(ROOT),
            str(registry.history.runtime.root),
            phase,
            str(tmp_path / "signal"),
            "die",
        ],
        capture_output=True,
        timeout=30,
    )
    assert process.returncode == 78, process.stderr.decode()
    assert a.replay(registry, "original") == original
    assert a.publish(registry, "child", req).synthetic_ready
    assert len(registry.proof().dependencies) == 3


def test_pending_publication_blocks_competing_backup_and_retention(
    registry: r.HistoryRegistry, tmp_path: Path
) -> None:
    req = reference_request(registry)
    signal, release = tmp_path / "signal", tmp_path / "release"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            CHILD,
            str(ROOT),
            str(registry.history.runtime.root),
            "record_published",
            str(signal),
            str(release),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 25
        while not signal.exists():
            assert process.poll() is None
            assert time.monotonic() < deadline
            time.sleep(0.02)
        with pytest.raises(EvidenceError, match="history_runtime_busy"):
            a.publish(registry, "competing", req)
        with pytest.raises(recovery.HistoryRecoveryError):
            recovery.backup(registry, boundary(tmp_path / "busy"), candidate_id="busy")
        assert registry.assess_removal(req.basket.reference).required is None
        release.write_text("continue")
        _, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, stderr.decode()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
    assert a.replay(registry, "child").synthetic_ready


def test_offline_replay_is_deterministic() -> None:
    first = subprocess.check_output([sys.executable, "-I", str(SCRIPT)])
    second = subprocess.check_output([sys.executable, "-I", str(SCRIPT)])
    assert first == second and json.loads(first)["restore_equal"] is True
