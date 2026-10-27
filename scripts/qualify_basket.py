"""Replay fictional exact basket/industry cases in development or installed wheels."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from prosper import basket as b


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
    return asdict(b.estimate(reference_input()))


if __name__ == "__main__":
    print(json.dumps(qualify(), sort_keys=True, separators=(",", ":"), allow_nan=False))
