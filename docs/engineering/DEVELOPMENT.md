# Local development

Updated October 22, 2026. [ADR-0003](../architecture/decisions/0003-adopt-standard-local-development.md) adopts a standard local filesystem checkout and supersedes the original Google Drive/external-temp procedure. The current checkout is `C:\Users\jpete\Documents\Projects\Prosper`; commands do not hardcode that machine path. [T003.1](../tasks/T003.1-development-baseline.md) is historical evidence of the first bootstrap; [setup evidence](../tasks/SETUP-local-filesystem.md) records the migration checks.

This guide owns exercised developer commands; [STATUS](../STATUS.md) and task reports own current module coverage and observed results. The synthetic library includes SQLite/evidence storage and atomic import services; no investor application, tax engine, API or UI exists. Windows x64 is the first supported target. Investor installation and other operating systems remain unqualified.

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
New-Item -ItemType Directory -Force '.local/pytest' | Out-Null
.venv\Scripts\python.exe -m pytest --basetemp (Join-Path '.local/pytest' ([Guid]::NewGuid().ToString('N')))
.venv\Scripts\python.exe scripts/check_project.py
```

The four bootstrap tests qualify editable installed imports from an unrelated working directory, deliberate Ruff/type errors, and positive/negative pytest/Hypothesis execution. Expected failing subprocesses are asserted by passing outer tests. They validate no financial behavior. T003.2's separate 56 primitive cases include four deterministic property tests against rational references; [task evidence](../tasks/T003.2-exact-values.md) records their scope and actual results. T004.1.1 adds 82 parser cases including two deterministic property tests. `package` builds a wheel offline, creates a fresh isolated environment, installs only the exact locked runtime dependencies via `uv sync --locked --offline --no-dev --no-install-project`, then installs Prosper's wheel with no editable source. It checks installed dependency compatibility and imports with Python isolation enabled, verifying package/typing-marker origin. The environment target and VIRTUAL_ENV overrides are process-scoped and restored. The isolated parser smoke in task evidence exercises the actual installed module with F000/F001. It leaves synthetic output in ignored `.local/package-check`; it is no release installer or reproducible-build claim.

Pinned development versions remain Ruff **0.17.2**, mypy **2.4.0** strict, pytest **9.1.1**, Hypothesis **6.170.5**, Hatchling **1.32.4**, uv **0.13.5**. [The dependency inventory](DEVELOPMENT_DEPENDENCIES.md) lists the 19 external distributions and metadata/license limits. Prosper's runtime dependency is now Pydantic 2.14.1 with its locked required packages, qualified in T004.1.1. No public Prosper software license is selected. Add API/frontend/numerical tools only in their owning child tasks. A filesystem move is not a reason to install the entire future stack.

## Synthetic evidence adapter

T003.3.1 adds a library boundary, not an investor launcher. The following API is exercised by synthetic filesystem tests and the isolated installed-wheel smoke described in [task evidence](../tasks/T003.3.1-immutable-evidence.md). From the checkout root, with the project environment:

```python
from pathlib import Path
from prosper.evidence import EvidenceStore, RuntimeBoundary

source = Path.cwd().resolve()
boundary = RuntimeBoundary(source / ".local/evidence/demo", source, "synthetic")
store = EvidenceStore(boundary)
raw = (source / "examples/synthetic/F001.json").read_bytes()
receipt = store.publish(raw)
assert EvidenceStore(boundary).read(receipt) == raw
```

Constructing the boundary validates paths without creating them; opening the store creates only the explicit runtime's versioned object/staging directories. Synthetic mode requires a child of source `.local`; `.local` itself is not an evidence root. Private mode requires a separate, nonoverlapping local directory and is tested only with synthetic scratch here. No default per-user runtime is installed. The source boundary and mode are trusted caller configuration, never imported file content. The adapter cannot identify whether arbitrary bytes are real portfolio data; caller authorization still governs data use.

Receipts contain `storage_version`, `raw_sha256`, `byte_length` and `relative_reference`. The `evidence-bytes-v1/objects/<sha256>.bin` object contains original bytes; canonical identity remains the parser's separate responsibility. `EvidenceError.code` gives safe failure details without payloads or paths. Publication uses exclusive staging, flush/fsync, close, a same-volume hard link that cannot replace an existing object, and removal of that operation's staging name. Unsupported filesystems fail explicitly; there is no copying fallback. Verified repeated publication reuses the same complete object. Reads enforce the parser's 2 MiB byte bound, regular single-link files, size and SHA-256.

Existing symlinks, Windows junctions/reparse points, unsafe relative references and invalid private/source overlap are rejected and rechecked during operations. This local boundary assumes no hostile concurrent directory replacement; it does not establish ACL isolation, encrypted storage, authenticity or power-loss durability. Failed/interrupted publication may retain staging files; interruption after linking may leave a complete object with two names, which reads reject until separately qualified recovery. No automatic orphan cleanup, backup/restore or database reference commit is implemented. Use the existing full check/package commands; [STATUS](../STATUS.md) records current results and next task.

## Exact checkpoint store

T003.3.2 adds `prosper.persistence.CheckpointStore(evidence_store)`. Call `append(validated_checkpoint)` with the inspector's result; an optional evidence receipt is verified against the original bytes. `get(raw_sha256)` returns a verified `StoredCheckpoint` containing sequence, actual recorded time, receipt and reconstructed inspection. `list_ids()` returns storage inventory in append sequence; it is not a readiness assessment or active portfolio reference. Every operation closes its SQLite connection.

The explicit runtime contains `checkpoints-v1.sqlite3`, with application/schema markers and STRICT tables. Schema version three retains durable previews and adds activation/command tables alongside the unchanged checkpoint table. Opening an exactly matching version-one or version-two store transactionally upgrades the schema and preserves checkpoint/preview rows; incompatible/altered schemas fail rather than being repaired. Checkpoint row encoding remains `checkpoint-sqlite-v1`; the filename is retained to find existing stores. Older application versions cannot open schema three and no downgrade is provided. Canonical JSON is TEXT with decimal strings and explicit null/reason pairs. Original evidence reconstructs spelling/quantum; reads reparse/reinspect it and compare persisted canonical content, identities, versions and source metadata. Source cutoff and UTC recorded time stay separate. The checkpoint adapter exposes no update/delete method; identical raw input returns its first row/time, while changed raw input appends a separate version without accepting a correction. Missing/corrupt committed evidence blocks duplicate appends as well as reads.

Files publish and verify before row insertion. Explicit transactions roll back failed inserts/references; a failed transaction may leave a complete unreferenced evidence object. Database and journal/WAL/SHM names reuse the runtime path guards, including regular-file/single-link checks. Existing foreign/empty/unknown-version/changed-schema databases fail without automatic initialization or broad migration. Newly created files that fail initialization may remain non-ready and require a future qualified recovery procedure. The adapter uses the standard-library SQLite shipped with the qualified Python host; [task evidence](../tasks/T003.3.2-sqlite-checkpoints.md) records its version, SQL type checks and actual commands. Full check/package commands remain unchanged. Import activation, command receipts/concurrency, backups and complete recovery are later tasks.

## Durable synthetic previews

[T004.2.1 evidence](../tasks/T004.2.1-durable-previews.md) qualifies `prosper.previews.PreviewService` over the same guarded database/evidence runtime. Using the synthetic evidence `store` and `raw` from the earlier example:

```python
from prosper.persistence import CheckpointStore
from prosper.previews import PreviewService

previews = PreviewService(CheckpointStore(store))
preview = previews.stage(raw)
rejected = previews.reject(preview.receipt.raw_sha256)
assert previews.get(preview.receipt.raw_sha256) == rejected
assert previews.stage(raw) == rejected
```

`stage` accepts safely bounded malformed/contradictory input as evidence with parser/inspection diagnostics; it does not append checkpoint rows. `get` reconstructs diagnostics and exact/source values from verified original evidence. Results retain the receipt, first recorded time, lifecycle/rejection time, parsing result and optional inspection. Invalid byte type/oversized payloads raise `PreviewError` with bounded `.issues` before publication. Parser success and inspection validity remain distinct from lifecycle and financial-use readiness.

Exact raw repeats reuse the preview, including terminal rejection; changed bytes keep separate evidence even when normalized values match. Missing/corrupt evidence and bad metadata fail explicitly; staging cannot silently repair a broken preview/checkpoint reference. Real rollback and abrupt-upgrade interruption were tested, but complete recovery/cleanup remains future work. The atomic service below now owns active imports, generations and receipts. The existing full check/package commands and isolated installed-module qualification apply; this is a library boundary, not an investor UI or financial-use release.

## Atomic synthetic activation

`prosper.imports.ImportService(CheckpointStore(store))` shares the existing evidence/database runtime. Stage with `.previews.stage(raw)`, inspect the preview, then call `.commit(preview.receipt.raw_sha256, command_key, expected_generation)`. `.current()` returns `ActiveState(generation, checkpoint)`; a new runtime is explicitly `(0, None)`. A nonempty checkpoint carries its verified inspection and financial blocks. [Task evidence](../tasks/T004.2.2-atomic-activation.md) records the exercised semantics and checks.

Commands use one fixed versioned synthetic-portfolio scope and a 1-128 character identifier key. Receipts retain original outcome, observed generation, optional original activation generation and timestamp. Same-key/same-payload retries return that receipt after evidence checks; changed payload reuse fails. Distinct stale commands return a durable stale outcome. A distinct current-generation reimport of already activated raw bytes records a duplicate no-op referencing its original activation; it never restores old active state. Use `.current()` separately to inspect present state.

Checkpoint insertion, committed preview transition, new generation and successful receipt share one SQLite transaction. Rejected/invalid/identity-conflicting/source-conflicting previews retain evidence and cannot replace active state. Historical committed event content is compared across all retained accepted versions; changed source versions cannot bypass conflict detection. Changed facts for the same source snapshot require review; general correction acceptance/account switching remain unsupported. Inspection-valid incomplete basis/coverage may activate, with planning readiness false. Committed previews cannot be rejected. Missing/corrupt evidence or relational metadata causes explicit errors without silent repair or success receipts for failed writes. Schema one/two upgrades and activation writes have real SQL/process interruption checks; complete application recovery remains T004.3.

## Consistent foundation backup and isolated restore

`prosper.recovery.backup(checkpoint_store, backup_boundary, candidate_id="candidate-label")` creates a new versioned backup. `prosper.recovery.restore(backup_boundary, new_runtime_boundary)` restores it to a new runtime. Both return the closed `BackupManifest`; reopen with `CheckpointStore(EvidenceStore(new_runtime_boundary))` and `ImportService` as usual. The boundary is the same guarded `RuntimeBoundary` used above: synthetic roots must be below ignored `.local`, private roots must stay outside their source tree, and source/destination roots must not overlap or cross modes. Existing destinations, including empty directories, are refused. [Execution evidence](../tasks/T004.3.1-backup-restore.md) owns the exercised qualification.

Backup uses SQLite's backup API; its resulting snapshot determines the required original-evidence objects. It retains inactive checkpoints, staged/rejected/committed previews, all active generations and successful/unsuccessful command receipts. Verification reconstructs every row and checks database integrity, current schema, evidence identity, historical conflicts and receipt relationships. The manifest records application/schema versions, a fingerprint of actual package Python sources/runtime dependency versions, caller-supplied candidate label, file hashes/lengths and state counts/generation. The label is provenance supplied by the caller, not proof of a Git revision. Hashes establish integrity, not authentication. Caches, unreferenced objects and incomplete publication files are excluded; no database-only recovery claim is valid.

The current conservative envelope is 512 MiB per database, 10,000 distinct required evidence objects (each within the parser's existing byte limit), and 8 MiB for the manifest. These are engineering rejection limits, not measured capacity. Restore requires exactly the same implementation fingerprint/application version and schema three; backup migration and cross-version compatibility are unimplemented. This deliberately rejects an incompatible backup before any schema-upgrading constructor runs.

Backup publishes its complete manifest last. Restore copies into an isolated work directory, verifies the copied state, publishes evidence then the database, and clears `restore-in-progress` only after completion. The storage adapter refuses a runtime bearing that marker. Interrupted operations retain their files; choose a new destination for a retry. Do not remove a marker or repair files manually and assume the result is qualified. General inspection/recovery and orphan cleanup remain T004.3.2. This is a local synthetic library workflow, with no investor installer, encryption/ACL isolation, hostile concurrent path-replacement or power-loss guarantee. Restored inspection keeps its existing financial blocks.

## Text, candidate identity and GitHub

`.editorconfig` and `.gitattributes` standardize authored text as UTF-8 without BOM with LF endings and explicit binary treatment. Global Git/editor settings are unchanged. `scripts/check_project.py` checks authored files using Git's non-ignored file inventory, text encoding/endings, conflict markers, Markdown fences/local links/headings and the supplemental [manifest](../PLANNING_MANIFEST.sha256). Regenerate the manifest after authored edits before the final check/commit; it excludes itself, Git internals and ignored generated/private state. It is a source-tree fingerprint, not a release signature. Git commit IDs are the primary history/change-control identity when available. Git itself is a prerequisite for the checker, including before the first commit.

The prepared [Windows workflow](../../.github/workflows/checks.yml) runs the same bootstrap/check/package sequence on push, pull request and manual dispatch after upload. It uses a pinned Windows runner family, exact Python version, SHA-pinned official actions, read-only contents permission and no persisted checkout credentials. The owner-created [GitHub repository](https://github.com/jpeterson92/Prosper) is connected as origin. Owner-completed browser sign-in enabled the initial upload; local main now tracks origin/main. Hosted workflow results and exact revisions are recorded in STATUS. Local commands passing does not qualify the hosted runner or establish branch protection. Hosted CI may download Python and the same locked tools; the local helper does not install global runtimes.

For this connected GitHub repository, use `git push` to upload reviewed committed changes on the tracked main branch. The initial authenticated upload succeeded after the owner completed browser sign-in. Repository-local credential helpers select Git Credential Manager with the Windows Credential Manager store; global configuration is unchanged. Do not put a token in source, command arguments or chat. The owner selected/created the repository; this task does not change visibility. Public licensing/distribution decisions remain open. The first hosted Windows run passed; see [STATUS](../STATUS.md) for the exact run/commit. Main is currently unprotected. Configure required PR checks/branch protection only under an owner-directed repository-setting request. The owner created the repository and the follow-up setup connected origin. The first push attempt was rejected by authentication, then the authenticated retry succeeded. Source hosting does not establish financial-use release approval. GitHub backs up committed/pushed source, not uncommitted files, ignored environments or private investor data. Application backup must still cover consistent SQLite state and authoritative evidence separately.

For authorized source synchronization, follow the [hosted CI handoff protocol](NEXT_STEP.md#github-synchronization-and-hosted-ci-handoff): review the previous relevant run at the next sync and finish each push without waiting for its new Actions run. Required local checks still apply. Actions runs remain enabled; no workflow, branch protection or release gate is changed by this timing preference.

Independent software/tax/risk review, other-machine/OS checks, financial/application tests, investor acceptance and release remain separate evidence gates. Hosted CI evidence is recorded per exact commit in STATUS. [STATUS](../STATUS.md) owns the current next task and exact handoff identity.
