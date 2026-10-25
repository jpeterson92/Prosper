"""Replay fictional exact basket/industry cases in development or installed wheels."""

import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

from prosper import basket as b
from prosper import industry as i


def reference_input() -> b.BasketInput:
    path = Path(__file__).resolve().parents[1] / "examples/synthetic/basket/reference.json"
    raw = path.read_bytes()
    ref = json.loads(raw)
    evidence = b.Evidence(
        hashlib.sha256(raw).hexdigest(),
        "fictional fixture",
        ref["as_of"],
        ref["as_of"],
        ref["as_of"],
    )
    securities = tuple(b.Security(s, "USD", "stock", evidence) for s in ref["security_ids"])
    return b.BasketInput(
        "Fictional Benchmark",
        ref["as_of"],
        ref["as_of"],
        tuple(ref["security_ids"]),
        tuple(
            b.Position(
                f"P{j}", s, b.Fact(ref["quantity"], evidence), b.Fact(ref["mark_usd"], evidence)
            )
            for j, s in enumerate(securities[:3])
        ),
        tuple(
            b.BenchmarkRow(f"B{j}", s, b.Fact(w, evidence), "percent")
            for j, (s, w) in enumerate(
                zip(securities[:3], ref["benchmark_weights_percent"], strict=True)
            )
        ),
        (securities[3],),
        b.Fact(ref["portfolio_cash_usd"], evidence),
        b.Fact(ref["benchmark_cash_percent"], evidence),
        "percent",
    )


def qualify() -> dict[str, object]:
    data = reference_input()
    first = b.qualify(data)
    budget = b.qualify(replace(data, portfolio_cash=replace(data.portfolio_cash, raw="1.00")))
    incomplete = b.qualify(
        replace(
            data,
            benchmark=(
                replace(data.benchmark[0], weight=replace(data.benchmark[0].weight, raw="48.54")),
                *data.benchmark[1:],
            ),
        )
    )
    taxonomy = i.Taxonomy(
        "Fictional hierarchy",
        "v1",
        data.as_of,
        data.portfolio_cash.evidence.source_sha256,
        tuple(
            i.Classification(
                s,
                "Alpha" if j < 2 else "Beta",
                "Group",
                data.as_of,
                data.as_of,
                "stipulated fixture",
            )
            for j, s in enumerate(data.universe)
        ),
        (("Alpha", "Group"), ("Beta", "Group")),
    )
    covariance = i.FrozenCovariance(
        data.universe,
        tuple(tuple(float(j == k) for k in range(4)) for j in range(4)),
        data.as_of,
        1,
        "one_session",
        "stipulated-identity-covariance",
        "fixed synthetic identity covariance",
    )
    diagnostic = i.diagnose(b.to_industry(first), taxonomy, (), covariance)
    if first.status != "qualified-synthetic-input" or diagnostic.attribution is None:
        raise RuntimeError("reference qualification failed")
    return {
        "base": asdict(first),
        "selected_cash": asdict(budget),
        "non_unit": asdict(incomplete),
        "industry": asdict(diagnostic),
    }


if __name__ == "__main__":
    print(json.dumps(qualify(), sort_keys=True, separators=(",", ":"), allow_nan=False))
