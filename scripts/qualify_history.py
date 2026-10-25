"""Stipulated synthetic history replay for development and installed-wheel probes."""

import argparse
import json
import tempfile
from dataclasses import asdict
from pathlib import Path

from prosper import history as h
from prosper import history_recovery as recovery
from prosper import history_registry as r
from prosper.evidence import RuntimeBoundary
from prosper.history_coordination import REGISTRY_NAMESPACE

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/synthetic/history/reference.json"


def reference_input(store: h.HistoryStore) -> h.Envelope:
    raw = FIXTURE.read_bytes()
    fixture = json.loads(raw)
    contexts = tuple(
        h.SeriesContext(
            security_id=security,
            provider="fictional-provider",
            dataset="fictional-daily",
            permission_scope="synthetic-only-v1",
            provider_symbol=security,
            mapping_start="2026-01-01",
            mapping_end="2026-12-31",
            currency="USD",
            calendar="stipulated-three-session-grid-v1",
            timezone="America/New_York",
            interval="one-session",
            adjustment="explicit-stipulated-total-return-v1",
            repair="none",
            source_schema="fictional-v1",
            transform_version="identity-v1",
            library_version="stdlib-fixture-v1",
            return_convention="close-to-close-fraction",
            return_transform_version="stipulated-zero-v1",
            vintage="fictional-vintage-1",
            captured_at=fixture["known_at"],
        )
        for security in fixture["security_ids"]
    )
    selection = h.Selection(
        series=contexts,
        sessions=tuple(fixture["sessions"]),
        cutoff="2026-01-07",
        known_at=fixture["known_at"],
        calendar_evidence="reference.json stipulated session order",
    )
    reference = store.retain(raw)
    sources = tuple(
        h.Source(
            source_id=c.security_id,
            context=c,
            raw=reference,
            outcome="complete",
            validated_at=fixture["known_at"],
        )
        for c in contexts
    )
    observations = tuple(
        h.Observation(
            security_id=c.security_id,
            session=session,
            source_id=c.security_id,
            source_row=f"stipulated/{c.security_id}/{j}",
            open=h.Fact(text=fixture["price"]),
            high=h.Fact(text=fixture["price"]),
            low=h.Fact(text=fixture["price"]),
            close=h.Fact(text=fixture["price"]),
            adjusted_close=h.Fact(text=fixture["price"]),
            dividend=h.Fact(text=fixture["zero"]),
            split_ratio=h.Fact(text=fixture["split_ratio"]),
            total_return=h.Fact(text=fixture["zero"]),
            return_from_session=fixture["sessions"][j - 1] if j else fixture["prior_session"],
        )
        for c in contexts
        for j, session in enumerate(fixture["sessions"])
    )
    return h.Envelope(selection=selection, sources=sources, observations=observations)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", action="store_true", help="Exercise explicit synthetic pins")
    parser.add_argument(
        "--recovery", action="store_true", help="Backup/restore required history offline"
    )
    args = parser.parse_args()
    store = h.HistoryStore(RuntimeBoundary(ROOT / ".local/history-replay", ROOT, "synthetic"))
    frozen = store.publish(reference_input(store))
    reopened = h.HistoryStore(store.runtime, existing=True).read(frozen.receipt)
    if not reopened.manifest.coverage.complete:
        raise RuntimeError("stipulated complete grid failed")
    if args.registry or args.recovery:
        # The fixture harness explicitly initializes only a never-reserved registry.
        # Reserved/missing/corrupt state always goes through reopen and refuses.
        registry = (
            r.HistoryRegistry(store)
            if store.evidence.runtime.path(REGISTRY_NAMESPACE).exists()
            else r.HistoryRegistry.initialize(store)
        )
        dependency = registry.register(
            "fixture-run-v1",
            frozen.receipt,
            expected=frozen.manifest.envelope.selection,
        )
        replayed = registry.replay(dependency.dependency_id)
        proof = registry.proof()
        recovered: dict[str, object] = {}
        if args.recovery:
            with tempfile.TemporaryDirectory(
                prefix="history-recovery-", dir=ROOT / ".local"
            ) as scratch:
                saved = RuntimeBoundary(Path(scratch) / "backup", ROOT, "synthetic")
                destination = RuntimeBoundary(Path(scratch) / "restored", ROOT, "synthetic")
                manifest = recovery.backup(registry, saved, candidate_id="fictional-replay-v1")
                recovery.inspect_backup(saved)
                recovery.restore(saved, destination)
                restored = r.HistoryRegistry(h.HistoryStore(destination, existing=True))
                if (
                    restored.proof() != proof
                    or restored.replay(dependency.dependency_id) != replayed
                ):
                    raise RuntimeError("required history restore changed frozen evidence")
                recovered = {
                    "recovery": {
                        "format": manifest.format,
                        "scope": manifest.scope,
                        "dependencies": manifest.dependency_count,
                        "objects": len(manifest.evidence),
                        "replay_equal": True,
                    }
                }
        print(
            json.dumps(
                {
                    **recovered,
                    "dependency": dependency.model_dump(mode="json"),
                    "manifest": replayed.manifest.model_dump(mode="json"),
                    "required": [asdict(x) for x in proof.required],
                    "state_sha256": proof.state_sha256,
                    "retention": asdict(registry.assess_removal(frozen.receipt.relative_reference)),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    else:
        print(h.canonical_bytes(reopened.manifest).decode("ascii"))


if __name__ == "__main__":
    main()
