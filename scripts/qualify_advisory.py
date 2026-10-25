"""Offline advisory estimates using the existing fictional input scenarios."""

import json
import runpy
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from typing import cast

from prosper import advisory as a
from prosper import basket as b
from prosper import benchmark_reconciliation as r
from prosper import equity_benchmark as e
from prosper import industry as i
from prosper import vanguard as v

ROOT = Path(__file__).resolve().parents[1]


def reference() -> b.BasketInput:
    loader = cast(
        Callable[[], b.BasketInput],
        runpy.run_path(str(ROOT / "scripts/qualify_basket.py"))["reference_input"],
    )
    return loader()


def equity_scenario(
    raw: bytes | None = None,
) -> tuple[v.Acquisition, r.Stipulation, e.Policy, r.PortfolioContext]:
    loader = cast(
        Callable[..., tuple[v.Acquisition, r.Stipulation, e.Policy, r.PortfolioContext]],
        runpy.run_path(str(ROOT / "scripts/qualify_equity_benchmark.py"))["scenario"],
    )
    return loader(raw)


def hierarchy(data: b.BasketInput) -> i.Taxonomy:
    return i.Taxonomy(
        "Fictional hierarchy",
        "v1",
        data.as_of,
        data.portfolio_cash.evidence.source_sha256,
        tuple(
            i.Classification(
                s, "Alpha" if j < 2 else "Beta", "Group", data.as_of, data.as_of, "fictional input"
            )
            for j, s in enumerate(data.universe)
        ),
        (("Alpha", "Group"), ("Beta", "Group")),
    )


def covariance(data: b.BasketInput) -> i.FrozenCovariance:
    n = len(data.universe)
    return i.FrozenCovariance(
        data.universe,
        tuple(tuple(float(j == k) for k in range(n)) for j in range(n)),
        data.as_of,
        1,
        "one_session",
        "fictional-identity",
        "identity covariance",
    )


def qualify() -> dict[str, object]:
    data = reference()
    basket = b.estimate(data)
    if basket.weights is None:
        raise RuntimeError("reference estimated weights unavailable")
    industry = i.estimate(basket.weights, hierarchy(data), (), covariance(data))
    acq, stip, policy, portfolio = equity_scenario()
    equity = e.estimate(acq, stip, policy, portfolio)
    if industry.attribution is None or equity.basket is None or equity.basket.weights is None:
        raise RuntimeError("estimated consumer integration failed")
    return {
        "basket": asdict(basket),
        "selected_cash": asdict(
            b.estimate(replace(data, portfolio_cash=replace(data.portfolio_cash, raw="1.00")))
        ),
        "industry": asdict(industry),
        "equity": asdict(equity),
        "partial_sale": asdict(a.sale_estimate("3", "1", 1, "0.2")),
        "near_gain": asdict(a.sale_estimate("1", "100", 1, "100.0001")),
        "near_cash": a.cash_estimate("0", "100", "100.0001", "0"),
    }


if __name__ == "__main__":
    print(json.dumps(qualify(), sort_keys=True, separators=(",", ":"), allow_nan=False))
