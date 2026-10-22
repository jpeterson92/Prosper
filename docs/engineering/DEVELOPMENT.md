# Local development

Updated October 22, 2026. [ADR-0003](../architecture/decisions/0003-adopt-standard-local-development.md) adopts a standard local filesystem checkout and supersedes the original Google Drive/external-temp procedure. The current checkout is `C:\Users\jpete\Documents\Projects\Prosper`; commands do not hardcode that machine path. [T003.1](../tasks/T003.1-development-baseline.md) is historical evidence of the first bootstrap; [setup evidence](../tasks/SETUP-local-filesystem.md) records the migration checks.

This is a minimal developer package and toolchain, with no financial/application behavior, API, database or UI. Windows x64 is the first supported target. Investor installation and other operating systems remain unqualified.

## Prerequisites and first setup

The exercised host uses CPython **3.12.4 x64**, Windows build **22635.3640**, PowerShell **5.1.22621.2706**, and Git **2.50.1.windows.1**. These are observations, not a certified OS support matrix or a recommendation to retain an old interpreter indefinitely. `.python-version` retains the qualified interpreter and metadata admits Python 3.12; a patch upgrade should be separately exercised rather than bundled into a filesystem move.

Run from a new local checkout in PowerShell with Python 3.12.4 and Git available:

```powershell
.\scripts\dev.ps1 -Command bootstrap
.\scripts\dev.ps1 -Command check
.\scripts\dev.ps1 -Command package
```

`bootstrap` creates ignored `.tools/uv` using Python venv/ensurepip, installs **uv 0.13.5** there from public PyPI, then syncs `uv.lock` into ignored `.venv`. It changes neither base Python nor global PATH/settings. With a compatible uv already installed, use `-Command sync` directly; `-Uv` can select an explicit executable. `-Python` selects an existing interpreter. The helper does not download an interpreter. Package acquisition uses HTTPS to PyPI/files.pythonhosted.org and requires permitted network access; no portfolio data or credentials are involved. Managed execution may also require permission for normal user-cache and OS-temp writes.

| Location | Purpose | In Git? |
| --- | --- | --- |
| `src/`, `tests/`, `scripts/`, `docs/`, `.github/` | Authored source, tests, docs and workflow | Yes |
| `pyproject.toml`, `uv.lock`, `.python-version` | Exact dependency/build inputs and qualified interpreter | Yes |
| `.venv/` | Editable developer package and locked dependencies for this checkout | No |
| `.tools/uv/` | Optional local bootstrap tool, independent of the project environment | No |
| `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `.hypothesis/`, `__pycache__/` | Ordinary rebuildable development state | No |
| `.local/package-check/<unique-id>/` | Fresh wheel, isolated wheel environment and import working directory | No |
| `.local/`, `artifacts/`, browser result directories | Synthetic generated databases/evidence/logs/results as needed | No |
| uv's default user cache | Shared reusable download/build cache across projects | Outside source |
| `.local/pytest/<unique-id>/` | Synthetic pytest scratch files, isolated per check run | No |
| Future per-user application-data directory | Private investor state, evidence and configuration | Outside source; not yet implemented |

Installed dependencies belong in `.venv`; the uv download/build cache works well in its standard user location and need not be duplicated per checkout. See [uv cache documentation](https://docs.astral.sh/uv/concepts/cache/). Moving/copying a checkout requires recreating `.venv` and `.tools`, because virtual environments contain absolute paths. Old external temporary environments are no longer referenced or required and were left untouched.

## Daily checks and package qualification

```powershell
.\scripts\dev.ps1 -Command sync
.venv\Scripts\python.exe scripts/check_project.py --write-manifest
.\scripts\dev.ps1 -Command check
.\scripts\dev.ps1 -Command package
```

`sync` uses `uv sync --locked` with editable source installation. `check` first syncs offline against the lock using the environment's pinned uv, then runs Ruff lint/format checks, strict mypy, pytest with a fresh ignored `.local/pytest/<unique-id>` scratch directory, and authored-project checks. This keeps test scratch isolated per checkout/run without changing process TEMP/TMP or relying on a shared pytest temp root. If offline build/dependency artifacts are unavailable, run `sync` with permitted network access first. Routine commands never rewrite the lock. The helper sets only `UV_PROJECT_ENVIRONMENT` (the checkout's `.venv`) and `UV_PYTHON_DOWNLOADS=never` for subprocesses and restores both on success/failure. Existing tool-cache/temp settings otherwise retain ordinary behavior. It also restores the working directory.

Equivalent lint/type/test commands, after syncing:

```powershell
.venv\Scripts\python.exe -m ruff check src tests scripts
.venv\Scripts\python.exe -m ruff format --check src tests scripts
.venv\Scripts\python.exe -m mypy --config-file pyproject.toml
.venv\Scripts\python.exe -m pytest --basetemp (Join-Path '.local/pytest' ([Guid]::NewGuid().ToString('N')))
.venv\Scripts\python.exe scripts/check_project.py
```

The four bootstrap tests qualify editable installed imports from an unrelated working directory, deliberate Ruff/type errors, and positive/negative pytest/Hypothesis execution. Expected failing subprocesses are asserted by passing outer tests. They validate no financial behavior. `package` separately builds a wheel offline, creates a fresh isolated environment, installs only that wheel, then imports with Python isolation enabled and verifies the package/typing marker came from that environment. It leaves synthetic output in ignored `.local/package-check`; it is no release installer or reproducible-build claim.

Pinned development versions remain Ruff **0.17.2**, mypy **2.4.0** strict, pytest **9.1.1**, Hypothesis **6.170.5**, Hatchling **1.32.4**, uv **0.13.5**. [The dependency inventory](DEVELOPMENT_DEPENDENCIES.md) lists the 19 external distributions and metadata/license limits. Prosper has no runtime dependencies or selected public software license. Add API/frontend/numerical tools only in their owning child tasks. A filesystem move is not a reason to install the entire future stack.

## Text, candidate identity and GitHub

`.editorconfig` and `.gitattributes` standardize authored text as UTF-8 without BOM with LF endings and explicit binary treatment. Global Git/editor settings are unchanged. `scripts/check_project.py` checks authored files using Git's non-ignored file inventory, text encoding/endings, conflict markers, Markdown fences/local links/headings and the supplemental [manifest](../PLANNING_MANIFEST.sha256). Regenerate the manifest after authored edits before the final check/commit; it excludes itself, Git internals and ignored generated/private state. It is a source-tree fingerprint, not a release signature. Git commit IDs are the primary history/change-control identity when available. Git itself is a prerequisite for the checker, including before the first commit.

The prepared [Windows workflow](../../.github/workflows/checks.yml) runs the same bootstrap/check/package sequence on push, pull request and manual dispatch after upload. It uses a pinned Windows runner family, exact Python version, SHA-pinned official actions, read-only contents permission and no persisted checkout credentials. No remote workflow has run yet. Local commands passing does not qualify the hosted runner or establish branch protection. Hosted CI may download Python and the same locked tools; the local helper does not install global runtimes.

For eventual GitHub setup, create the owner-selected repository/visibility, connect its remote, review the synthetic-only staged source and push the reviewed history. Start private while the public license/distribution decisions remain open. Then observe the first CI run and configure required PR checks/branch protection to match the actual repository plan. Repository creation, remote changes, push and public release were not performed by this setup task. GitHub backs up committed/pushed source, not uncommitted files, ignored environments or private investor data. Application backup must still cover consistent SQLite state and authoritative evidence separately.

Independent software/tax/risk review, hosted CI, other-machine/OS checks, financial/application tests, investor acceptance and release remain separate evidence gates. [STATUS](../STATUS.md) owns the current next task and exact handoff identity.
