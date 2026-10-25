"""Replay the stipulated A05/A06 rational reference in development or a wheel."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from prosper import industry as i
from prosper.innovations import fingerprint


def qualify() -> dict[str, object]:
    path = Path(__file__).resolve().parents[1] / "examples/synthetic/industry/reference.json"
    ref = json.loads(path.read_text())
    ids = tuple(ref["security_ids"])
    day = "2000-03-04"
    weights = i.Weights(
        ids,
        tuple(ref["portfolio"]),
        tuple(ref["benchmark"]),
        ref["portfolio_cash"],
        ref["benchmark_cash"],
        "fictional-stock-sleeve-plus-selected-USD-NAV-portfolio",
        "fictional-benchmark-NAV-including-declared-cash",
        day,
    )
    taxonomy = i.Taxonomy(
        "Fictional Research Hierarchy",
        "v1",
        day,
        hashlib.sha256(path.read_bytes()).hexdigest(),
        tuple(
            i.Classification(s, sector, industry, "2000-01-01", day, "stipulated fixture")
            for s, sector, industry in zip(
                ids,
                ("Tech", "Tech", "Defensive"),
                ("Hardware", "Services", "Services"),
                strict=True,
            )
        ),
        (("Tech", "Hardware"), ("Tech", "Services"), ("Defensive", "Services"), ("Empty", "Empty")),
    )
    covariance = i.FrozenCovariance(
        ids,
        tuple(tuple(row) for row in ref["covariance"]),
        day,
        1,
        "one_session",
        fingerprint(ref),
        "stipulated one-session covariance",
    )
    result = i.diagnose(weights, taxonomy, (), covariance)
    if result.status != "qualified-synthetic-diagnostic":
        raise RuntimeError(result.issues)
    return {"reference_sha256": fingerprint(ref), "result": asdict(result)}


if __name__ == "__main__":
    print(json.dumps(qualify(), sort_keys=True, separators=(",", ":"), allow_nan=False))
