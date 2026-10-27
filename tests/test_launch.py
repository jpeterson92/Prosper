"""Installed-launch boundaries: deliberate creation, fail-closed reopen, no reset."""

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from prosper import launch
from prosper.advisory_store import DATABASE_NAME, AdvisoryStore
from prosper.local_api import serve
from prosper.storage import PersistenceError
from tests.test_local_api import build_fixture


@pytest.fixture
def locations(tmp_path: Path) -> tuple[Path, Path]:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    build_fixture(artifact / "ui")
    return tmp_path / "fictional-workspace", artifact


def test_explicit_creation_and_reopen_retain_state(
    locations: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, artifact = locations
    launch.initialize(workspace, artifact)
    store = AdvisoryStore.existing(launch.boundary(workspace, artifact))
    store.configure({"fictional": True}, "settings", 0)
    invoked: list[dict[str, Any]] = []
    monkeypatch.setattr(launch, "serve", lambda **kwargs: invoked.append(kwargs))
    launch.start(workspace, artifact)
    assert invoked[0]["require_existing"] is True
    assert invoked[0]["runtime"] == store.runtime
    assert store.current()["settings"] == {"fictional": True}
    with pytest.raises(FileExistsError):
        launch.initialize(workspace, artifact)
    assert store.current()["revision"] == 1


def test_missing_reopen_never_creates_a_workspace(locations: tuple[Path, Path]) -> None:
    workspace, artifact = locations
    with pytest.raises(ValueError):
        launch.start(workspace, artifact)
    assert not workspace.exists()
    launch.initialize(workspace, artifact)
    store = launch.boundary(workspace, artifact)
    database = store.path(DATABASE_NAME)
    database.unlink()  # Deliberate loss of a fresh, empty synthetic test database.
    with pytest.raises(PersistenceError, match="advisory_database_unavailable"):
        launch.start(workspace, artifact)
    with pytest.raises(PersistenceError, match="advisory_database_unavailable"):
        serve(runtime=store, ui_dist=artifact / "ui", require_existing=True)
    assert not database.exists()


def test_existing_unknown_folder_and_corrupt_state_are_never_repaired(
    locations: tuple[Path, Path],
) -> None:
    workspace, artifact = locations
    workspace.mkdir()
    owner_file = workspace / "owner.txt"
    owner_file.write_bytes(b"fictional unrelated work")
    with pytest.raises(FileExistsError):
        launch.initialize(workspace, artifact)
    assert owner_file.read_bytes() == b"fictional unrelated work"
    runtime = launch.boundary(workspace, artifact)
    runtime.root.mkdir(parents=True)
    database = runtime.path(DATABASE_NAME)
    database.write_bytes(b"fictional unsupported database")
    with pytest.raises(PersistenceError):
        launch.start(workspace, artifact)
    assert database.read_bytes() == b"fictional unsupported database"


@pytest.mark.parametrize("which", ["same", "inside", "ancestor", "relative", "reserved"])
def test_workspace_cannot_overlap_or_alias_artifact(
    locations: tuple[Path, Path], which: str
) -> None:
    workspace, artifact = locations
    workspace = {
        "same": artifact,
        "inside": artifact / "data",
        "ancestor": artifact.parent,
        "relative": Path("relative"),
        "reserved": workspace.parent / "CON",
    }[which]
    with pytest.raises(ValueError):
        launch.initialize(workspace, artifact)
    assert not (artifact / "data").exists()


def test_missing_assets_do_not_touch_saved_work(locations: tuple[Path, Path]) -> None:
    workspace, artifact = locations
    launch.initialize(workspace, artifact)
    runtime = launch.boundary(workspace, artifact)
    before = runtime.path(DATABASE_NAME).read_bytes()
    (artifact / "ui" / "index.html").unlink()
    with pytest.raises(OSError):
        launch.start(workspace, artifact)
    assert runtime.path(DATABASE_NAME).read_bytes() == before


@pytest.mark.parametrize("document", [[], {}, {"kind": "other", "ready": True}])
def test_incomplete_artifact_manifest_refuses(
    locations: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, document: Any
) -> None:
    _, artifact = locations
    monkeypatch.setattr(sys, "prefix", str(artifact / ".venv"))
    monkeypatch.setattr(
        launch, "__file__", str(artifact / ".venv/Lib/site-packages/prosper/launch.py")
    )
    (artifact / "artifact.json").write_text(json.dumps(document), encoding="utf8")
    with pytest.raises(ValueError, match="artifact_not_ready"):
        launch.installed_artifact(artifact)


def test_editable_python_cannot_masquerade_as_installed_artifact(
    locations: tuple[Path, Path],
) -> None:
    _, artifact = locations
    with pytest.raises(ValueError, match="installed_artifact_python_required"):
        launch.installed_artifact(artifact)


def test_same_workspace_reopens_without_checkout_or_mode_marker(
    locations: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from prosper.advisory_recovery import backup, restore

    workspace, artifact = locations
    launch.initialize(workspace, artifact)
    store = AdvisoryStore.existing(launch.boundary(workspace, artifact))
    store.configure({"research": True}, "settings", 0)
    assert not (workspace / "workspace.json").exists()
    # A pre-existing label file has no authority over opening current local data.
    (workspace / "workspace.json").write_bytes(b'{"mode":"research"}')
    monkeypatch.setattr(launch, "serve", lambda **kwargs: None)
    launch.start(workspace, artifact)
    restored_path = workspace.parent / "restored"
    launch.initialize(restored_path, artifact)
    target = AdvisoryStore.existing(launch.boundary(restored_path, artifact))
    restore(target, backup(store))
    assert target.current() == store.current()
    replacement = workspace.parent / "replacement"
    replacement.mkdir()
    build_fixture(replacement / "ui")
    launch.start(workspace, replacement)
    assert (
        AdvisoryStore.existing(launch.boundary(workspace, replacement)).current() == store.current()
    )


def test_redirected_workspace_refuses_without_creation(
    locations: tuple[Path, Path], tmp_path: Path
) -> None:
    import subprocess

    workspace, artifact = locations
    destination = tmp_path / "owned-destination"
    destination.mkdir()
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(workspace), str(destination)],
            check=True,
            capture_output=True,
        )
    else:
        workspace.symlink_to(destination, target_is_directory=True)
    with pytest.raises(ValueError, match="redirected_path"):
        launch.initialize(workspace, artifact)
    assert list(destination.iterdir()) == []
