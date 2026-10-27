"""Offline fictional D045 exact-weight and basket/industry consumer replay."""

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from prosper import basket as b
from prosper import benchmark_reconciliation as r
from prosper import equity_benchmark as e
from prosper import vanguard as v

DAY = "2000-01-03"
NOW = datetime(2000, 1, 4, 12, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


def scenario(
    raw: bytes | None = None,
) -> tuple[v.Acquisition, r.Stipulation, e.Policy, r.PortfolioContext]:
    if raw is None:
        raw = (ROOT / "examples/synthetic/benchmark/equity-only.json").read_bytes()
    selection = v.select_fund("VTI", date.fromisoformat(DAY))
    acquisition = v.acquire(
        selection,
        collected_at=NOW,
        transport=lambda s: v.Response(200, s.url, "application/json", raw),
    )
    snapshot = acquisition.snapshot
    if snapshot is None:
        raise RuntimeError(acquisition.issues)
    evidence = b.Evidence(
        hashlib.sha256(b"independent fictional D045 assertions").hexdigest(),
        "explicit fictional equity/relationship proof",
        DAY,
        "2000-01-04",
        DAY,
    )
    sections = tuple(
        r.SectionRule(
            s.name, "primary" if s.rows else "empty", "percentOfFunds", "percent", evidence
        )
        for s in snapshot.sections
    )
    securities = tuple(b.Security(f"FICTIONAL-{j}", "USD", "stock", evidence) for j in range(2))
    rows = tuple(
        r.RowRule(
            r.Locator(s.name, j),
            r.row_identity(row),
            securities[j] if s.name == "equity" and j < 2 else None,
            None,
            evidence,
        )
        for s in snapshot.sections
        for j, row in enumerate(s.rows)
    )
    policy = e.Policy(
        tuple(e.ValueField(s.name, "marketValue", "USD") for s in snapshot.sections),
        tuple(
            e.Decision(
                row.locator,
                "include" if row.security else "exclude",
                "qualified fictional ordinary equity"
                if row.security
                else "unresolved fictional identity"
                if row.locator == r.Locator("equity", 2)
                else "unsupported fictional instrument",
            )
            for row in rows
        ),
    )
    stipulation = r.Stipulation(
        snapshot.raw_sha256,
        selection.fund,
        DAY,
        DAY,
        NOW.isoformat(),
        evidence,
        sections,
        rows,
        b.Fact("0.00", evidence),
        "decimal",
    )
    portfolio = r.PortfolioContext(
        DAY,
        "2000-01-04",
        ("FICTIONAL-0", "FICTIONAL-1"),
        tuple(
            b.Position(f"P{j}", sec, b.Fact("1.00", evidence), b.Fact("1.00", evidence))
            for j, sec in enumerate(securities)
        ),
        (),
        b.Fact("0.00", evidence),
    )
    return acquisition, stipulation, policy, portfolio


def qualify() -> dict[str, object]:
    from dataclasses import asdict

    acquisition, stipulation, policy, portfolio = scenario()
    return asdict(e.estimate(acquisition, stipulation, policy, portfolio))


if __name__ == "__main__":
    print(json.dumps(qualify(), sort_keys=True, separators=(",", ":"), allow_nan=False))
