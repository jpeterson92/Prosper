"""Explicit instance-local workspace creation/reopen for a local artifact.

No default runtime, migration, repair or source import fallback.
The workspace container is independent of replaceable application files. Small
path/lifecycle boundaries use the standard library rather than tabular tooling.
"""

import argparse
import json
import os
import stat
import sys
from pathlib import Path, PureWindowsPath

from prosper.advisory_store import AdvisoryStore
from prosper.local_api import serve
from prosper.storage import RuntimeBoundary, _chain
from prosper.web_assets import WebAssets


def _locations(workspace: Path, artifact: Path) -> None:
    for path in (workspace, artifact):
        if (
            not path.is_absolute()
            or ".." in path.parts
            or str(path).startswith("\\\\")
            or any(
                part.endswith((".", " ")) or PureWindowsPath(part).is_reserved() or ":" in part
                for part in path.parts[1:]
            )
        ):
            raise ValueError("absolute_local_path_required")
        _chain(path)
    if (
        workspace == artifact
        or workspace.is_relative_to(artifact)
        or artifact.is_relative_to(workspace)
    ):
        raise ValueError("workspace_artifact_overlap")


def boundary(workspace: Path, artifact: Path) -> RuntimeBoundary:
    """One instance-local data directory, independent of replaceable app files."""
    _locations(workspace, artifact)
    return RuntimeBoundary(workspace / ".local" / "workspace", (artifact,))


def initialize(workspace: Path, artifact: Path) -> None:
    runtime = boundary(workspace, artifact)
    # Explicit exclusive creation never turns an unknown folder into an empty portfolio.
    workspace.mkdir()
    AdvisoryStore(runtime)


def start(workspace: Path, artifact: Path) -> None:
    runtime = boundary(workspace, artifact)
    WebAssets.load(artifact / "ui")
    AdvisoryStore.existing(runtime)
    serve(runtime=runtime, ui_dist=artifact / "ui", require_existing=True)


def installed_artifact(path: Path) -> None:
    """Refuse launching through editable/global Python or an aliased artifact."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute_local_path_required")
    _chain(path)
    prefix = path / ".venv"
    if Path(sys.prefix) != prefix or not Path(__file__).is_relative_to(prefix):
        raise ValueError("installed_artifact_python_required")
    marker = path / "artifact.json"
    _chain(marker)
    info = marker.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65536:
        raise ValueError("artifact_manifest_invalid")
    document = json.loads(marker.read_bytes())
    if (
        not isinstance(document, dict)
        or document.get("kind") != "prosper-local-v1"
        or document.get("ready") is not True
    ):
        raise ValueError("artifact_not_ready")
    if os.name != "nt" or sys.version_info[:2] != (3, 12):
        raise ValueError("artifact_platform_unsupported")
    WebAssets.load(path / "ui")


def main() -> None:
    parser = argparse.ArgumentParser(description="Installed Prosper local workspace")
    parser.add_argument("command", choices=("initialize", "start"))
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    try:
        installed_artifact(args.artifact)
        if args.command == "initialize":
            initialize(args.workspace, args.artifact)
            print("Workspace created. Use start to reopen it.")
        else:
            start(args.workspace, args.artifact)
    except (ValueError, OSError):
        parser.exit(2, "local_launch_refused; existing files were not reset\n")


if __name__ == "__main__":
    main()
