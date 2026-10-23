"""Synthetic browser qualification setup/inspection; never investor state."""

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from prosper.api_contracts import CurrentResponse, checkpoint_response
from prosper.evidence import EvidenceStore, RuntimeBoundary
from prosper.imports import ImportService
from prosper.persistence import DATABASE_NAME, CheckpointStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("seed", "inspect"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    service = ImportService(
        CheckpointStore(EvidenceStore(RuntimeBoundary(args.root, source, "synthetic")))
    )
    if args.operation == "seed":
        preview = service.previews.stage((source / "examples/synthetic/F001.json").read_bytes())
        result = service.commit(preview.receipt.raw_sha256, "browser-fixture-seed", 0)
        if result.outcome != "committed":
            raise ValueError("synthetic_seed_failed")
    current = service.current()
    response = CurrentResponse(
        generation=current.generation,
        checkpoint=checkpoint_response(current.checkpoint) if current.checkpoint else None,
    )
    with closing(sqlite3.connect(args.root / DATABASE_NAME)) as connection:
        counts = {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("checkpoints", "import_activations", "import_commands", "import_previews")
        }
    print(json.dumps({"current": response.model_dump(mode="json"), "counts": counts}))


if __name__ == "__main__":
    main()
