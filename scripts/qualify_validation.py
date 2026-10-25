"""Offline opt-in validation defaults, dispatch and policy-aware restore replay."""

import json
import runpy
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import cast

from prosper import history as h
from prosper import history_recovery as recovery
from prosper import history_refresh as f
from prosper import history_registry as r
from prosper import history_validation as v
from prosper.evidence import RuntimeBoundary

ROOT = Path(__file__).resolve().parents[1]
fixture = runpy.run_path(str(ROOT / "scripts/qualify_refresh.py"))
request = cast(Callable[..., f.Request], fixture["fictional_request"])
provider_factory = cast(Callable[[f.Request], f.Provider], fixture["FictionalProvider"])


def enabled_settings() -> v.Settings:
    return v.Settings(enabled=True, cadence_seconds=60, request=request(manual=("FICTION-A",)))


def main() -> None:
    (ROOT / ".local").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="validation-replay-", dir=ROOT / ".local") as scratch:

        def boundary(name: str) -> RuntimeBoundary:
            return RuntimeBoundary(Path(scratch) / name, ROOT, "synthetic")

        registry = r.HistoryRegistry.initialize(h.HistoryStore(boundary("history")))
        policy = v.ValidationStore.initialize(registry, now="2026-03-01T12:00:00Z")
        provider = provider_factory(request())
        default = policy.dispatch(now="2026-03-01T12:00:30Z", provider=provider)
        enabled = policy.configure(
            "enable", expected_generation=1, now="2026-03-01T12:01:00Z", settings=enabled_settings()
        )
        early = policy.dispatch(now="2026-03-01T12:01:59Z", provider=provider)
        due = policy.dispatch(now="2026-03-01T12:02:00Z", provider=provider)
        if (
            due.status != "complete"
            or due.refresh is None
            or due.refresh.scheduled_validation != "explicit-fictional-dispatch"
        ):
            raise RuntimeError("fictional scheduled validation failed")
        disabled = policy.configure(
            "disable",
            expected_generation=due.state.generation,
            now="2026-03-01T12:02:30Z",
            settings=v.Settings(),
        )
        manual = request(manual=("FICTION-A",), known_at="2026-03-01T12:03:00Z")
        manual_record = f.refresh(registry, "manual-off", manual, provider)
        if not manual_record.complete or policy.current() != disabled:
            raise RuntimeError("manual refresh changed disabled policy")
        saved, destination = boundary("backup"), boundary("restored")
        manifest = recovery.backup(registry, saved, candidate_id="fictional-validation-replay")
        recovery.restore(saved, destination)
        restored = v.ValidationStore(r.HistoryRegistry(h.HistoryStore(destination, existing=True)))
        later = restored.dispatch(now="2026-04-01T12:00:00Z", provider=provider)
        if restored.current() != disabled or later.status != "off":
            raise RuntimeError("disabled policy failed restoration")
        print(
            json.dumps(
                {
                    "default": default.model_dump(mode="json"),
                    "enabled": enabled.model_dump(mode="json"),
                    "early": early.status,
                    "due": due.model_dump(mode="json"),
                    "disabled": disabled.model_dump(mode="json"),
                    "manual_complete": manual_record.complete,
                    "backup_format": manifest.format,
                    "backup_scope": manifest.scope,
                    "restored_equal": restored.current() == disabled,
                    "later": later.status,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )


if __name__ == "__main__":
    main()
