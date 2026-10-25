"""Offline immutable fictional refresh and required-history recovery replay."""

import json
import tempfile
from pathlib import Path

from prosper import history as h
from prosper import history_recovery as recovery
from prosper import history_refresh as f
from prosper import history_registry as r
from prosper.evidence import RuntimeBoundary

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "examples/synthetic/history/refresh-reference.json").read_bytes())


def fictional_request(
    *,
    count: int = 5,
    names: tuple[str, ...] = ("FICTION-A",),
    cache: tuple[str, ...] = (),
    known_at: str = "2026-03-01T12:00:00Z",
    manual: tuple[str, ...] = (),
) -> f.Request:
    contexts = tuple(
        h.SeriesContext(
            security_id=name,
            provider="fictional-offline-provider",
            dataset="archived-fixture-v1",
            permission_scope="fictional-only",
            provider_symbol=name,
            mapping_start="2026-01-01",
            mapping_end="2026-12-31",
            currency="USD",
            calendar="stipulated-sparse-five-session-calendar-v1",
            timezone="UTC",
            interval="declared-session",
            adjustment="fixture-adjusted-close-v1",
            repair="none",
            source_schema="fictional-history-response-v1",
            transform_version="exact-ratio-v1",
            library_version="stdlib-v1",
            return_convention="close-to-close-fraction",
            return_transform_version="fixture-adjusted-close-ratio-v1",
            vintage="immutable-corpus-v1",
            captured_at="2026-03-01T12:00:00Z",
        )
        for name in names
    )
    return f.Request(
        selection=h.Selection(
            series=contexts,
            sessions=tuple(FIXTURE["sessions"][:count]),
            cutoff=FIXTURE["sessions"][count - 1],
            known_at=known_at,
            calendar_evidence=FIXTURE["description"],
        ),
        calendar=f.Calendar(
            sessions=tuple(FIXTURE["sessions"]), predecessor=FIXTURE["predecessor"]
        ),
        policy=f.Policy(overlap_sessions=1, permission_valid_until="2026-12-31T23:59:59Z"),
        cache_ids=cache,
        mode="manual" if manual else "requested",
        manual_security_ids=manual,
    )


class FictionalProvider:
    """A fixed archived fictional corpus; fetch only selects local fixture rows."""

    def __init__(self, request: f.Request) -> None:
        self.contexts = {s.security_id: s for s in request.selection.series}
        self.calls: list[f.Range] = []

    def fetch(self, request: f.Range) -> bytes:
        self.calls.append(request)
        days = (FIXTURE["predecessor"], *FIXTURE["sessions"])
        prices = dict(zip(days, FIXTURE["adjusted_closes"], strict=True))
        observations = tuple(
            h.Observation(
                security_id=request.security_id,
                session=day,
                source_id="provider",
                source_row=f"fixture/{day}",
                open=h.Fact(text=prices[day]),
                high=h.Fact(text=prices[day]),
                low=h.Fact(text=prices[day]),
                close=h.Fact(text=prices[day]),
                adjusted_close=h.Fact(text=prices[day]),
                dividend=h.Fact(text="0.0000"),
                split_ratio=h.Fact(text="1.00"),
                total_return=h.Fact(text="0.1000"),
                return_from_session=days[days.index(day) - 1] if days.index(day) else "2026-01-01",
            )
            for day in request.sessions
        )
        body = f.Body(
            context=self.contexts[request.security_id],
            start=request.sessions[0],
            end=request.sessions[-1],
            outcome="complete",
            observations=observations,
        )
        return body.model_dump_json().encode()


def main() -> None:
    scratch_root = ROOT / ".local"
    scratch_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="refresh-replay-", dir=scratch_root) as scratch:

        def boundary(name: str) -> RuntimeBoundary:
            return RuntimeBoundary(Path(scratch) / name, ROOT, "synthetic")

        registry = r.HistoryRegistry.initialize(h.HistoryStore(boundary("history")))
        first = fictional_request(count=3)
        first_provider = FictionalProvider(first)
        initial = f.refresh(registry, "initial", first, first_provider)
        later = fictional_request(cache=("initial",), known_at="2026-03-02T12:00:00Z")
        provider = FictionalProvider(later)
        tail = f.refresh(registry, "month-later", later, provider)
        repeat_request = fictional_request(cache=("month-later",), known_at="2026-03-03T12:00:00Z")
        repeat_provider = FictionalProvider(repeat_request)
        repeat = f.refresh(registry, "repeat", repeat_request, repeat_provider)
        manual_request = fictional_request(
            cache=("repeat",), known_at="2026-03-04T12:00:00Z", manual=("FICTION-A",)
        )
        manual_provider = FictionalProvider(manual_request)
        manual = f.refresh(registry, "manual", manual_request, manual_provider)
        if not all(record.complete for record in (initial, tail, repeat, manual)):
            raise RuntimeError("fictional refresh failed")
        if len(provider.calls) != 1 or repeat_provider.calls:
            raise RuntimeError("unexpected fictional request count")
        saved, destination = boundary("backup"), boundary("restored")
        recovery.backup(registry, saved, candidate_id="fictional-refresh-replay")
        recovery.restore(saved, destination)
        restored = r.HistoryRegistry(h.HistoryStore(destination, existing=True))
        if restored.proof() != registry.proof() or f.replay(restored, "manual") != manual:
            raise RuntimeError("restored refresh state differs")
        print(
            json.dumps(
                {
                    "initial": initial.model_dump(mode="json"),
                    "tail": tail.model_dump(mode="json"),
                    "repeat": repeat.model_dump(mode="json"),
                    "manual": manual.model_dump(mode="json"),
                    "initial_calls": [x.model_dump(mode="json") for x in first_provider.calls],
                    "tail_calls": [x.model_dump(mode="json") for x in provider.calls],
                    "repeat_calls": len(repeat_provider.calls),
                    "required_objects": len(restored.proof().required),
                    "restore_equal": True,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )


if __name__ == "__main__":
    main()
