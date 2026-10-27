"""Generic runtime path protections survive removal of legacy proof storage."""

from pathlib import Path

import pytest

from prosper.storage import EvidenceError, RuntimeBoundary


@pytest.mark.parametrize(
    "reference",
    ["../escape", "/absolute", "a/../b", "a//b", "C:/file", "CON", "name.", "a\\b", "", "a:b"],
)
def test_relative_runtime_paths_cannot_escape_or_alias(tmp_path: Path, reference: str) -> None:
    root = tmp_path / "source"
    root.mkdir()
    boundary = RuntimeBoundary(root / ".local/runtime")
    with pytest.raises(EvidenceError):
        boundary.path(reference)


def test_any_explicit_local_workspace_can_be_used(tmp_path: Path) -> None:
    for root in (tmp_path / "data", tmp_path / "checkout/.local/demo"):
        boundary = RuntimeBoundary(root)
        assert boundary.path("advisory-v1.sqlite3").parent == root


def test_file_component_cannot_masquerade_as_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    runtime = source / ".local/runtime"
    runtime.mkdir(parents=True)
    (runtime / "collision").write_bytes(b"fictional")
    boundary = RuntimeBoundary(runtime)
    with pytest.raises(EvidenceError, match="directory_required"):
        boundary.path("collision/file")


def test_protected_application_location_is_checked_on_each_access(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    artifact = tmp_path / "application"
    artifact.mkdir()
    with pytest.raises(EvidenceError, match="protected_runtime_overlap"):
        RuntimeBoundary(artifact / "data", (artifact,))
    with pytest.raises(EvidenceError, match="protected_runtime_overlap"):
        RuntimeBoundary(tmp_path, (artifact,))
    boundary = RuntimeBoundary(tmp_path / "research", (artifact,))
    artifact.rmdir()
    artifact.write_bytes(b"fictional unsafe replacement")
    with pytest.raises(EvidenceError):
        boundary.path("advisory-v1.sqlite3")
