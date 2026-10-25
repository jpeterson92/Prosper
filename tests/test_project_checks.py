"""Project checks reuse work within a run without trusting stale persistent state."""

import hashlib
import importlib.util
import sys
from collections import Counter
from pathlib import Path
from typing import Any, cast

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_project.py"
SPEC = importlib.util.spec_from_file_location("project_checks", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
CHECKER: Any = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def configure(monkeypatch: pytest.MonkeyPatch, root: Path, files: list[Path]) -> Path:
    manifest = root / "manifest.sha256"
    monkeypatch.setattr(CHECKER, "ROOT", root)
    monkeypatch.setattr(CHECKER, "MANIFEST", manifest)
    monkeypatch.setattr(CHECKER, "authored_files", lambda: sorted(files))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--write-manifest"])
    return manifest


@pytest.mark.parametrize("links_per_source", [1, 100])
def test_repeated_links_read_authored_bytes_and_parse_headings_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, links_per_source: int
) -> None:
    target = tmp_path / "target.md"
    target.write_text("# Target\n\n## Repeated\n\n## Repeated\n", encoding="utf-8", newline="\n")
    files = [target]
    for index in range(10):
        source = tmp_path / f"source-{index}.md"
        source.write_text(
            "[target](target.md#repeated-1)\n" * links_per_source, encoding="utf-8", newline="\n"
        )
        files.append(source)
    binary = tmp_path / "asset.bin"
    binary.write_bytes(b"\x00\xff\r")
    files.append(binary)
    manifest = configure(monkeypatch, tmp_path, files)
    reads: Counter[Path] = Counter()
    parses: Counter[str] = Counter()
    original_read, original_headings = Path.read_bytes, CHECKER.heading_ids

    def read(path: Path) -> bytes:
        reads[path] += 1
        return original_read(path)

    def headings(text: str) -> set[str]:
        parses[text] += 1
        return cast(set[str], original_headings(text))

    monkeypatch.setattr(Path, "read_bytes", read)
    monkeypatch.setattr(CHECKER, "heading_ids", headings)
    assert CHECKER.main() == 0
    assert reads == Counter(dict.fromkeys(files, 1))
    assert sum(parses.values()) == 11
    assert parses["# Target\n\n## Repeated\n\n## Repeated\n"] == 1
    expected = "".join(
        f"{hashlib.sha256(original_read(p)).hexdigest()}  {p.name}\n" for p in sorted(files)
    )
    assert manifest.read_text(encoding="utf-8") == expected


def test_later_invocation_rechecks_headings_bytes_and_deleted_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source, target = tmp_path / "source.md", tmp_path / "target.md"
    source.write_text("[target](target.md#original)\n", encoding="utf-8", newline="\n")
    target.write_text("# Original\n", encoding="utf-8", newline="\n")
    manifest = configure(monkeypatch, tmp_path, [source, target])
    assert CHECKER.main() == 0
    previous = manifest.read_bytes()
    target.write_text("# Revised\n", encoding="utf-8", newline="\n")
    assert CHECKER.main() == 1
    assert "Missing heading" in capsys.readouterr().out
    assert manifest.read_bytes() == previous
    source.write_text("[target](target.md#revised)\n", encoding="utf-8", newline="\n")
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])
    assert CHECKER.main() == 1
    assert "manifest is stale" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--write-manifest"])
    assert CHECKER.main() == 0
    assert manifest.read_bytes() != previous
    target.unlink()
    assert CHECKER.main() == 1
    assert "Broken local link" in capsys.readouterr().out


@pytest.mark.parametrize("invalid", [b"\xff\n", b"# Title\r\n", b"<<<<<<< conflict\n"])
def test_invalid_text_never_writes_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: bytes
) -> None:
    source = tmp_path / "invalid.md"
    source.write_bytes(invalid)
    manifest = configure(monkeypatch, tmp_path, [source])
    assert CHECKER.main() == 1
    assert not manifest.exists()


def test_unlisted_markdown_target_is_checked_and_refreshed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source, target = tmp_path / "source.md", tmp_path / "local.md"
    source.write_text("[local](local.md#present)\n" * 100, encoding="utf-8", newline="\n")
    target.write_text("# Present\n", encoding="utf-8", newline="\n")
    configure(monkeypatch, tmp_path, [source])
    assert CHECKER.main() == 0
    target.write_bytes(b"\xff\n")
    assert CHECKER.main() == 1
    assert "Unreadable Markdown target" in capsys.readouterr().out
