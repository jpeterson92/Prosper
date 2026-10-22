"""Check authored text, local Markdown links and the no-commit hash fallback."""

import argparse
import hashlib
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/PLANNING_MANIFEST.sha256"
TEXT_SUFFIXES = {".md", ".py", ".ps1", ".toml", ".lock", ".yml", ".yaml", ".json"}


def authored_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return sorted(
        {ROOT / name.decode("utf-8") for name in result.stdout.split(b"\0") if name} - {MANIFEST}
    )


def manifest_text(files: list[Path]) -> str:
    return "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT).as_posix()}\n"
        for path in files
    )


def heading_ids(text: str) -> set[str]:
    counts: dict[str, int] = {}
    anchors = set()
    for heading in re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        anchors.add(f"{slug}-{count}" if count else slug)
    return anchors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()
    files = authored_files()
    errors: list[str] = []
    links = 0
    markdown = 0
    for path in files:
        if not path.is_file():
            errors.append(f"Missing authored file: {path.relative_to(ROOT)}")
            continue
        if path.suffix not in TEXT_SUFFIXES and not path.name.startswith("."):
            continue
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"Not UTF-8: {path.relative_to(ROOT)}")
            continue
        if b"\r" in data or data.startswith(b"\xef\xbb\xbf") or not data.endswith(b"\n"):
            errors.append(f"Expected UTF-8 without BOM, LF and final newline: {path.name}")
        if re.search(r"^(?:<{7}|={7}|>{7})(?: |$)", text, re.MULTILINE):
            errors.append(f"Conflict marker: {path.name}")
        if path.suffix != ".md":
            continue
        markdown += 1
        if len(re.findall(r"^```", text, re.MULTILINE)) % 2:
            errors.append(f"Unbalanced Markdown fences: {path.name}")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            parsed = urlsplit(target.strip("<>"))
            if parsed.scheme or parsed.netloc:
                continue
            links += 1
            destination = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            if not destination.is_relative_to(ROOT) or not destination.exists():
                errors.append(f"Broken local link: {path.name}: {target}")
            elif parsed.fragment and destination.suffix == ".md":
                if unquote(parsed.fragment) not in heading_ids(
                    destination.read_text(encoding="utf-8")
                ):
                    errors.append(f"Missing heading: {path.name}: {target}")
    if not errors:
        expected = manifest_text(files)
        if args.write_manifest:
            MANIFEST.write_text(expected, encoding="utf-8", newline="\n")
        elif MANIFEST.read_text(encoding="utf-8") != expected:
            errors.append(
                "Authored manifest is stale; run scripts/check_project.py --write-manifest."
            )
    for error in errors:
        print(error)
    if errors:
        return 1
    print(
        f"Project checks OK: {len(files)} authored files, {markdown} Markdown files, {links} links."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
