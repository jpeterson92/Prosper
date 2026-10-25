"""Replay exact fictional frozen risk-input assembly and required-source restore."""

import json
import runpy
import tempfile
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from prosper import basket as b
from prosper import history as h
from prosper import history_recovery as recovery
from prosper import history_refresh as f
from prosper import history_registry as r
from prosper import industry as i
from prosper import innovations as n
from prosper import risk_inputs as a
from prosper.evidence import RuntimeBoundary

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = json.loads((ROOT / "examples/synthetic/risk-inputs/reference.json").read_bytes())
history_fixture = runpy.run_path(str(ROOT / "scripts/qualify_refresh.py"))
history_request = cast(Callable[..., f.Request], history_fixture["fictional_request"])
provider_factory = cast(Callable[[f.Request], f.Provider], history_fixture["FictionalProvider"])


def retain(history: h.HistoryStore, value: object) -> h.RawReference:
    return history.retain(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def reference_request(registry: r.HistoryRegistry, *, selected_cash: bool = False) -> a.Request:
    ids = tuple(REFERENCE["security_ids"])
    as_of, known = REFERENCE["as_of"], REFERENCE["known_at"]
    req = history_request(names=ids)
    f.refresh(registry, "history", req, provider_factory(req))
    dated = {
        "effective": as_of,
        "recorded": known,
        "valid_through": as_of,
        "evidence_unknown_reasons": [],
    }
    facts: dict[str, dict[str, Any]] = {}
    for name in ids:
        facts["security-" + name] = {
            "security_id": name,
            "currency": "USD",
            "asset_type": "stock",
            "unknown_reasons": [],
            **dated,
        }
    for name in ids[:2]:
        facts["quantity-" + name] = {
            "raw": REFERENCE["quantity"],
            "unknown_reasons": [],
            "unit": "shares",
            **dated,
        }
        facts["mark-" + name] = {
            "raw": REFERENCE["mark"],
            "unknown_reasons": [],
            "unit": "USD",
            "kind": "reference-close",
            **dated,
        }
    for name, weight in zip(ids[:2], REFERENCE["benchmark_weights"], strict=True):
        facts["benchmark-" + name] = {
            "raw": weight,
            "unknown_reasons": [],
            "unit": "percent",
            **dated,
        }
    facts["portfolio-cash"] = {
        "raw": REFERENCE["selected_cash"] if selected_cash else REFERENCE["cash"],
        "unknown_reasons": [],
        "unit": "USD",
        "scope": "selected-residual",
        **dated,
    }
    facts["benchmark-cash"] = {"raw": "0.0000", "unknown_reasons": [], "unit": "percent", **dated}
    classes = [
        {
            "security_id": name,
            "sector": "fictional-tech" if name != "FICTION-B" else "fictional-finance",
            "industry": "fictional-software" if name != "FICTION-B" else "fictional-banks",
            "effective": "2026-01-01",
            "recorded": known,
            "unknown_reasons": [],
            "corrections": [],
        }
        for name in ids
    ]
    hierarchy = (("fictional-tech", "fictional-software"), ("fictional-finance", "fictional-banks"))
    source = retain(
        registry.history,
        {
            "description": REFERENCE["description"],
            "facts": facts,
            "taxonomy": {
                "name": "Fictional hierarchy",
                "version": "fixture-v1",
                "as_of": as_of,
                "hierarchy": hierarchy,
                "records": classes,
            },
        },
    )

    def evidence(key: str) -> b.Evidence:
        return b.Evidence(source.sha256, "facts/" + key, as_of, known, as_of)

    def fact(key: str) -> b.Fact:
        return b.Fact(facts[key]["raw"], evidence(key))

    securities = tuple(
        b.Security(name, "USD", "stock", evidence("security-" + name)) for name in ids
    )
    basket = b.BasketInput(
        "Fictional full benchmark",
        as_of,
        known,
        ids,
        tuple(
            b.Position("P-" + name, security, fact("quantity-" + name), fact("mark-" + name))
            for name, security in zip(ids[:2], securities[:2], strict=True)
        ),
        tuple(
            b.BenchmarkRow("B-" + name, security, fact("benchmark-" + name), "percent")
            for name, security in zip(ids[:2], securities[:2], strict=True)
        ),
        (securities[2],),
        fact("portfolio-cash"),
        fact("benchmark-cash"),
        "percent",
    )
    taxonomy = i.Taxonomy(
        "Fictional hierarchy",
        "fixture-v1",
        as_of,
        source.sha256,
        tuple(
            i.Classification(
                row["security_id"],
                row["sector"],
                row["industry"],
                row["effective"],
                row["recorded"],
                f"taxonomy/records/{index}",
            )
            for index, row in enumerate(classes)
        ),
        hierarchy,
    )
    return a.Request(
        history_id="history",
        basket=retain(registry.history, asdict(basket)),
        taxonomy=retain(registry.history, asdict(taxonomy)),
        profile=retain(registry.history, asdict(n.R1_PROFILE)),
        limits=retain(registry.history, []),
        sources=(source,),
    )


def main() -> None:
    (ROOT / ".local").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="risk-input-replay-", dir=ROOT / ".local") as scratch:

        def boundary(name: str) -> RuntimeBoundary:
            return RuntimeBoundary(Path(scratch) / name, ROOT, "synthetic")

        registry = r.HistoryRegistry.initialize(h.HistoryStore(boundary("history")))
        base = a.publish(registry, "base", reference_request(registry))
        selected = a.publish(registry, "selected", reference_request(registry, selected_cash=True))
        if not base.synthetic_ready or not selected.synthetic_ready or selected.financial_ready:
            raise RuntimeError("fictional assembly refused")
        saved, destination = boundary("backup"), boundary("restored")
        recovery.backup(registry, saved, candidate_id="fictional-risk-inputs")
        recovery.restore(saved, destination)
        restored = r.HistoryRegistry(h.HistoryStore(destination, existing=True))
        if a.replay(restored, "base") != base or a.replay(restored, "selected") != selected:
            raise RuntimeError("frozen risk-input replay differs")
        print(
            json.dumps(
                {
                    "base": base.model_dump(mode="json"),
                    "selected": selected.model_dump(mode="json"),
                    "required_objects": len(restored.proof().required),
                    "restore_equal": True,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )


if __name__ == "__main__":
    main()
