"""Offline replay of fictional full-response reconciliation and basket bridging."""

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

from prosper import basket as b
from prosper import benchmark_reconciliation as r
from prosper import vanguard as v

DAY = "2000-01-03"
COLLECTED = datetime(2000, 1, 4, 12, tzinfo=UTC)
SELECTION = v.select_fund("VTI", date.fromisoformat(DAY))


def scenario(raw: bytes) -> tuple[v.Acquisition, r.Stipulation, r.PortfolioContext]:
    acquisition = v.acquire(
        SELECTION,
        collected_at=COLLECTED,
        transport=lambda s: v.Response(200, s.url, "application/json", raw),
    )
    snapshot = acquisition.snapshot
    if snapshot is None:
        raise RuntimeError(acquisition.issues)
    evidence = b.Evidence(
        hashlib.sha256(b"independent fictional identity and relationship assertions").hexdigest(),
        "stipulated fixture assertion",
        DAY,
        "2000-01-04",
        DAY,
    )
    sections = tuple(
        r.SectionRule(
            s.name,
            "primary" if s.name == "equity" else "empty",
            "percentOfFunds",
            "percent",
            evidence,
        )
        for s in snapshot.sections
    )
    row_rules = tuple(
        r.RowRule(
            r.Locator(s.name, j),
            r.row_identity(row),
            b.Security(f"FICTIONAL-{j}", "USD", "stock", evidence) if s.name == "equity" else None,
            None,
            evidence,
        )
        for s in snapshot.sections
        for j, row in enumerate(s.rows)
    )
    stipulation = r.Stipulation(
        snapshot.raw_sha256,
        SELECTION.fund,
        DAY,
        DAY,
        COLLECTED.isoformat(),
        evidence,
        sections,
        row_rules,
        b.Fact("0.00", evidence),
        "percent",
    )
    securities = tuple(b.Security(f"FICTIONAL-{j}", "USD", "stock", evidence) for j in range(2))
    portfolio = r.PortfolioContext(
        DAY,
        "2000-01-04",
        tuple(s.security_id for s in securities if s.security_id is not None),
        tuple(
            b.Position(f"P{j}", s, b.Fact("1.00", evidence), b.Fact("1.00", evidence))
            for j, s in enumerate(securities)
        ),
        (),
        b.Fact("0.00", evidence),
    )
    return acquisition, stipulation, portfolio


def qualify() -> object:
    path = Path(__file__).resolve().parents[1] / "examples/synthetic/benchmark/full-response.json"
    acquisition, stipulation, portfolio = scenario(path.read_bytes())
    base = r.reconcile(acquisition, stipulation)
    bridged = r.bridge(base, portfolio)
    if bridged.basket.weights is None or base.economic_total != "1":
        raise RuntimeError("fictional benchmark reference failed")
    # The alternate is explicitly linked, never discovered by comparing values.
    data = json.loads(path.read_bytes())
    data[DAY]["allocationToUnderlyingFunds"] = data[DAY]["equity"]
    other, rules, _ = scenario(json.dumps(data).encode())
    rules = replace(
        rules,
        sections=tuple(
            replace(s, role="alternate") if s.section == "allocationToUnderlyingFunds" else s
            for s in rules.sections
        ),
        rows=tuple(
            replace(row, target=r.Locator("equity", row.locator.index))
            if row.locator.section == "allocationToUnderlyingFunds"
            else row
            for row in rules.rows
        ),
    )
    alternate = r.reconcile(other, rules)
    if alternate.economic_total != "1":
        raise RuntimeError("alternate double-count reference failed")
    return {
        "benchmark_ready": False,
        "scope": "synthetic-only; real source qualification and activation remain open",
        "evidence": r.encoded((base, bridged, alternate)),
    }


if __name__ == "__main__":
    print(json.dumps(qualify(), sort_keys=True, separators=(",", ":"), allow_nan=False))
