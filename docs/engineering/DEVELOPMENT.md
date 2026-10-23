# Local development

Updated October 23, 2026. [ADR-0003](../architecture/decisions/0003-adopt-standard-local-development.md) adopts a standard local filesystem checkout and supersedes the original Google Drive/external-temp procedure. The current checkout is `C:\Users\jpete\Documents\Projects\Prosper`; commands do not hardcode that machine path. [T003.1](../tasks/T003.1-development-baseline.md) is historical evidence of the first bootstrap; [setup evidence](../tasks/SETUP-local-filesystem.md) records the migration checks.

This guide owns exercised developer commands; [STATUS](../STATUS.md) and task reports own current module coverage and observed results. The synthetic application includes SQLite/evidence storage, atomic import services, protected local HTTP access and a minimal browser transport diagnostic. T004.4.1.2 adds the synthetic preview/current review screen; lifecycle controls, tax engine and investor installation remain future work. Windows x64 is the first supported target. Investor installation and other operating systems remain unqualified.

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

Pinned development versions remain Ruff **0.17.2**, mypy **2.4.0** strict, pytest **9.1.1**, Hypothesis **6.170.5**, Hatchling **1.32.4**, uv **0.13.5**. [The dependency inventory](DEVELOPMENT_DEPENDENCIES.md) retains baseline and subsequent runtime metadata/license limits. Runtime now includes Pydantic 2.14.1 and T003.4.1's pinned FastAPI/minimal Uvicorn stack described below. No public Prosper software license is selected. Add frontend/numerical tools only in their owning child tasks. A filesystem move is not a reason to install the entire future stack.

## Protected synthetic loopback runtime

T004.4.1.1 adds the qualified [frontend bootstrap/check/build commands and built diagnostic launcher](../../frontend/README.md). Its optional `--ui-dist` snapshots only a trusted build's root HTML and bounded direct JS/CSS assets. Public bootstrap assets receive the same peer/host, no-query and security-header checks; every financial route and protected schema retains session/origin enforcement. No runtime-directory serving is added. [Browser execution evidence](../tasks/T004.4.1.1-browser-client.md) supersedes the earlier browser-unverified limitation only for this diagnostic and its exercised cases; [T004.4.1.2 evidence](../tasks/T004.4.1.2-inspection-ui.md) now adds the actual preview/current inspection screen, without lifecycle mutations.

T003.4.1 adds the diagnostic process; T003.4.2 optionally exposes the existing synthetic import services through it. Investor installation and financial-use qualification remain separate. From the checkout root:

```powershell
.venv/Scripts/python.exe -m prosper.local_api
```

The launcher owns an IPv4 socket bound only to `127.0.0.1`, using an OS-selected port by default. `--port <1-65535>` selects an explicit port. It prints one public JSON `origin` line, never a token; HTTP processing starts immediately afterward. Address conflicts/invalid ports fail without a traceback or secret-bearing output. Stop with the protected shutdown operation or normal process termination.

| Request | Required boundary | Response |
| --- | --- | --- |
| `POST /session` with empty body | Exact allowed Origin, exact Host including API port, `X-Prosper-Bootstrap: 1` | In-memory per-launch bearer token; repeated acquisition returns the same token |
| `GET /diagnostic` | Allowed Origin and `Authorization: Bearer <token>` | Closed synthetic status model; `planning_ready: false` |
| `POST /shutdown` with empty body | Allowed Origin and bearer token | Invalidates the session and stops this process |
| `OPTIONS` | Allowed Origin, requested GET/POST and only listed headers | Narrow CORS preflight; no session or financial state |

Same-origin browser GETs can omit Origin only when they include `Sec-Fetch-Site: same-origin` and the bearer token. Missing Origin on bootstrap/mutation, opaque `null` and other origins are rejected. Host must always be the exact `127.0.0.1:<API-port>` authority; `localhost`, other ports/names, wildcard hosts and forwarded/proxy headers grant no access. All other paths require a bearer before routing, including docs paths and the optionally enabled OpenAPI path. Tokens belong only in memory and the authorization header; query strings are refused, cookies grant no session, responses are no-store and no token is persisted. These original T003.4.1 results are HTTP/process checks; T004.4.1.1 now qualifies actual browser behavior for its bounded diagnostic, with the actual preview/current review now qualified by T004.4.1.2 and lifecycle actions still future work.

Development cross-origin access is disabled by default. `--development-port 5173` explicitly allows exactly `http://127.0.0.1:5173` in addition to the API origin, without changing the bind address; the actual frontend port must match. No wildcard, automatic port fallback, credential cookie or remote serving is provided. The trusted local development server can acquire the session; malicious local processes or code at an explicitly trusted origin are outside this browser-origin boundary. It is not OS-user authentication, TLS or a sandbox against local malware.

Requests pass host/origin/session checks before reading bodies. Header totals are capped at 16 KiB in the ASGI guard, with h11's incomplete-event limit also 16 KiB. Declared/streamed bodies are limited to 2 MiB, accumulated in one bounded byte buffer with a three-second receive deadline before any route parser; diagnostic operations reject every nonempty body. Configured import uploads use the same 2 MiB ceiling; commit/reject controls have a tighter 4 KiB ceiling and duplicate-key/nonfinite JSON rejection before closed-model validation. Uvicorn uses h11/asyncio, transport read backpressure, a 16-request concurrency guard, no WebSockets, two-second keepalive and three-second graceful shutdown. Connections close after responses. These are engineering limits, not a measured throughput/DoS guarantee; idle sockets/incomplete-header attacks and hostile-local-process resistance remain unqualified.

Access/error request logging and FastAPI tracing/metrics/logs/automatic telemetry configuration are explicitly disabled. No SDK/exporter, Swagger/CDN assets or remote data service is installed by this feature. [Dependency inventory](DEVELOPMENT_DEPENDENCIES.md#t00341-local-api-runtime-qualification) records the locked stack and license metadata; [task evidence](../tasks/T003.4.1-loopback-runtime.md) owns commands, installed-wheel qualification and limitations. The typed import HTTP configuration below is synthetic-only. Do not launch the internal ASGI application through an arbitrary server or treat another host/proxy configuration as qualified.

## Typed synthetic import HTTP API

To expose the verified services, explicitly select an absolute ignored synthetic runtime below this checkout's `.local` folder and its source root:

```powershell
$prosperSourceRoot = (Get-Location).Path
.venv/Scripts/python.exe -m prosper.local_api --source-root $prosperSourceRoot --synthetic-runtime (Join-Path $prosperSourceRoot '.local/api/demo')
```

Without both options the process stays diagnostic-only. Invalid/relative/outside-source/overlapping paths fail under `RuntimeBoundary`; this HTTP launcher rejects private mode. No default private/investor directory is installed and no HTTP request can select a storage path. Existing synthetic state reopens under the same service/schema guards. Use a new synthetic runtime rather than relabeling incompatible backups.

All routes below and `GET /openapi.json` require the existing host/origin/session checks. `Authorization: Bearer <token>` is a header, never a URL parameter. Application responses are JSON with no-store/nosniff headers; Swagger/Redoc remain disabled. Normal synchronous handlers run in FastAPI's thread pool and use the services' separate per-operation SQLite connections/transactions. HTTP adds no second writer or financial calculation.

| Route | Request | Response and meaning |
| --- | --- | --- |
| `POST /api/v1/previews` | Original bytes, `Content-Type: application/octet-stream`, at most 2 MiB | Versioned preview, retained raw-byte hash/length, normalized source/identity, source exact values, parser issues and optional inspection; malformed/empty input is durable non-ready evidence |
| `GET /api/v1/previews/{sha256}` | Lowercase 64-character original-byte digest | Reconstructed verified preview and its actual lifecycle |
| `GET /api/v1/current` | No body | Active generation/checkpoint or explicit generation zero and null checkpoint |
| `POST /api/v1/commit` | Closed JSON control below, at most 4 KiB | Original durable command receipt, including business rejection/stale/duplicate outcomes |
| `POST /api/v1/reject` | Closed JSON with `schema_version` and `preview_sha256`, at most 4 KiB | Terminal rejected preview; a committed preview cannot be rejected |
| `GET /openapi.json` | No body | Actual protected schema, including closed models, bearer requirements and the raw upload media contract |

A commit control contains exactly these fields:

```json
{
  "schema_version": "synthetic-import-api-v1",
  "preview_sha256": "<64 lowercase hex characters from the preview receipt>",
  "command_key": "synthetic-review-1",
  "expected_generation": 0
}
```

The command key uses the existing 1-128 character identifier grammar. Generation must be a nonnegative integer below `2**63 - 1`; floats/bools are refused. Unknown fields, missing/wrong schema versions and invalid identities are rejected, without accepting storage paths or financial overrides. The preview body is the original bundle, not this control envelope; its existing bundle schema/parser remains authoritative.

Successful service operations return HTTP 200, including durable `preview_invalid`, `preview_rejected`, `stale_generation`, `source_conflict` and `identity_review_required` receipts. A receipt describes its original observed generation/outcome; fetch current state separately. Same-key/same-payload retries return the original receipt. Same-key/different-payload and reject-after-commit errors return 409; missing previews return 404. Wrong media is 415, size is 413, malformed/duplicate/nonfinite control JSON is 400, and strict model validation is 422. Missing/corrupt/unavailable required evidence returns a safe 503 code; an unexpected internal failure returns a generic 500. A failure after a committed operation but before its response requires retry with the same key, not a new command. Validation errors omit input values, raw decoder messages and arbitrary supplied field names; request logs/tracebacks are not emitted. Server/protocol-level denials can be plain text. On Windows, a sender that continues an oversized upload after early refusal can receive a TCP reset instead of the already-sent 413; treat transport failure as failure and retry identical preview bytes or the same mutation command key as appropriate.

Responses use `schema_version: synthetic-import-api-v1`. Normalized `source.document` book values are canonical decimal strings or explicit null/reason facts. `source.source_values` locates every known source decimal and retains canonical `value`, `original_text` and decimal-string `source_quantum`. Inspection values use a `state` discriminator: known values carry those strings; unknown values carry `value: null` and a nonempty `reasons` array. Parser issue path components are capped at 128 characters with explicit `path_truncated` when shortened; the complete original evidence remains retained by its hash. Parser status, inspection validity, lifecycle and readiness remain distinct. `planning_ready` stays false, including inspection-valid incomplete-basis/coverage activation. Original byte content and storage paths are not returned.

[T003.4.2 evidence](../tasks/T003.4.2-import-api.md) owns observed HTTP/SQLite and installed-wheel results and limits. This does not qualify a broker adapter, investment return, tax/risk engine, real-data use, browser integration, TypeScript generator or release. T004.4.1 owns the next typed preview/inspection UI and its actual generator/browser qualification.

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

Backup publishes its complete manifest last. Restore copies into an isolated work directory, verifies the copied state, publishes evidence then the database, and clears `restore-in-progress` only after completion. The storage adapter refuses a runtime bearing that marker. Interrupted operations retain their files; choose a new destination for a retry. Do not remove a marker or repair files manually and assume the result is qualified. The bounded inspection/recovery and guarded cleanup workflows are described below. This is a local synthetic library workflow, with no investor installer, encryption/ACL isolation, hostile concurrent path-replacement or power-loss guarantee. Restored inspection keeps its existing financial blocks.

## Interrupted-state inspection

`prosper.inspection.inspect_recovery(boundary, role)` inspects an existing guarded root. The caller must explicitly select `"runtime"`, `"backup"` or `"interrupted_restore"`; filenames/imported text cannot select authority. It returns immutable `RecoveryInspection` observations: overall `verified`/`non_ready`, database status, coherent row-snapshot fingerprint, required receipts, optional fully verified state counts/generation, file identity/hash/link classifications and safe relative-reference findings. `planning_ready` is always false. No report grants permission to delete. [Inspection evidence](../tasks/T004.3.2.1-inspection.md) records qualification.

The inspector uses constructor-free existing adapters and read-only SQLite connections with query-only/trusted-schema guards. Schema/reference/row verification occurs within one read snapshot; missing/empty/incompatible databases are not initialized or upgraded. Required evidence includes inactive checkpoints and every preview lifecycle. Valid unreferenced objects and standalone staging remain distinct from imports; a matching local object/staging inode, digest and complete alias count is only a potentially recoverable interruption. Unknown ownership, links, bytes or provenance remains non-ready. Complete backup manifests must match all required files and state, including the current implementation fingerprint. A legacy restore marker is unbound and never cleared by inspection.

Normal SQLite read locks modify `-shm`; that engine coordination file has no authoritative content hash in the report, while identity/type/link/size guards remain. A cold SQLite read may create sidecars and yield a conservative `inventory_changed` finding; once sidecars exist, repeat inspection is stable on unchanged state. Concurrent commits may leave a coherent earlier snapshot plus explicit changed findings. Hot journals requiring writes are refused without rollback. Ordinary database/evidence/manifest bytes are never repaired, renamed or deleted. Known empty work directories left by completed restores are recognized; retained nonempty work remains unresolved.

Work limits are 25,000 enumerated entries, 1 GiB cumulative observed file lengths, 50,000 financial/application rows, and the existing per-file database/evidence/manifest limits. Enumeration/hashing is bounded and unknown directories/reparse points are not traversed. These are rejection limits, not a capacity measurement. Path checks retain the existing non-hostile-filesystem assumptions; ACL isolation, power-loss and hostile concurrent replacement are unqualified. Guarded repair/cleanup uses the workflow below.

## Guarded foundation recovery

`prosper.maintenance.maintain_runtime(boundary)` obtains its own fresh inspection, then opens the existing schema-three database and holds `BEGIN IMMEDIATE` while it reproves state and acts. It never accepts a caller's inspection as deletion permission, initializes/upgrades a database or writes financial SQL rows. Unqualified initial artifacts, including an already hot/unreadable journal, are preserved before a writable opening. [Recovery evidence](../tasks/T004.3.2.2-guarded-recovery.md) owns exercised commands and limits.

For a complete proven local object/staging alias set, a private proof reader first verifies the entire application state without changing the aliases. Only then may the coordinator unlink redundant staging names, preserving the canonical object and rechecking required lengths/hashes. Normal evidence/full-state verification runs after repair. It removes a canonical unreferenced object only after rechecking current complete references under the SQLite write transaction, resolved containment, regular-file identity, single-link ownership, length and digest immediately before unlink. It never recursively cleans a directory or selects unknown/corrupt/externally linked files. Standalone staging has no proved intended content and is preserved with `unbound_staging_preserved`, even if another orphan was safely removed.

The immutable `RecoveryResult` reports `verified`, `retained`, `partial` or `restored`, before/after inspections, exact completed file actions and retained findings; planning readiness remains false. File actions are individually safe and cannot be rolled back with SQL. An interruption can leave a partially completed cleanup; repeat the operation to reprove remaining work. The database transaction always rolls back/releases without committing financial facts. Unknown state remains preserved rather than repaired.

SQLite serializes competing application/recovery writers. Direct `EvidenceStore.publish` calls do not take that lock: a race can produce a coded publication/append failure that needs retry or leave a new unreferenced object for a later pass. Existing transaction-time evidence checks prevent a missing object from committing. No transparent concurrent-cleanup or permanently zero-orphan guarantee is made. Path/identity/hash guards retain the existing non-hostile-filesystem assumptions; work/history-growth performance and long-lock behavior at target scale are unmeasured.

`recover_from_backup(source_boundary, role, backup_boundary, new_destination)` preserves the explicitly selected source artifact and restores a fully verified compatible backup into a new, separate destination. It never resumes an unbound marker or repairs a failed initialization in place. Source/backup/destination must not overlap or cross runtime modes, and existing destinations are refused. Incompatible/missing evidence is retained non-ready. Partial restore failures retain their marker/work and report partial outcome; a retry chooses another new destination. Backup migration/implementation compatibility and financial readiness are unchanged. Synthetic tests cover the private boundary using synthetic scratch only; no investor runtime is installed.

## Text, candidate identity and GitHub

`.editorconfig` and `.gitattributes` standardize authored text as UTF-8 without BOM with LF endings and explicit binary treatment. Global Git/editor settings are unchanged. `scripts/check_project.py` checks authored files using Git's non-ignored file inventory, text encoding/endings, conflict markers, Markdown fences/local links/headings and the supplemental [manifest](../PLANNING_MANIFEST.sha256). Regenerate the manifest after authored edits before the final check/commit; it excludes itself, Git internals and ignored generated/private state. It is a source-tree fingerprint, not a release signature. Git commit IDs are the primary history/change-control identity when available. Git itself is a prerequisite for the checker, including before the first commit.

The prepared [Windows workflow](../../.github/workflows/checks.yml) runs the same bootstrap/check/package sequence on push, pull request and manual dispatch after upload. It uses a pinned Windows runner family, exact Python version, SHA-pinned official actions, read-only contents permission and no persisted checkout credentials. The owner-created [GitHub repository](https://github.com/jpeterson92/Prosper) is connected as origin. Owner-completed browser sign-in enabled the initial upload; local main now tracks origin/main. Hosted workflow results and exact revisions are recorded in STATUS. Local commands passing does not qualify the hosted runner or establish branch protection. Hosted CI may download Python and the same locked tools; the local helper does not install global runtimes.

For this connected GitHub repository, use `git push` to upload reviewed committed changes on the tracked main branch. The initial authenticated upload succeeded after the owner completed browser sign-in. Repository-local credential helpers select Git Credential Manager with the Windows Credential Manager store; global configuration is unchanged. Do not put a token in source, command arguments or chat. The owner selected/created the repository; this task does not change visibility. Public licensing/distribution decisions remain open. The first hosted Windows run passed; see [STATUS](../STATUS.md) for the exact run/commit. Main is currently unprotected. Configure required PR checks/branch protection only under an owner-directed repository-setting request. The owner created the repository and the follow-up setup connected origin. The first push attempt was rejected by authentication, then the authenticated retry succeeded. Source hosting does not establish financial-use release approval. GitHub backs up committed/pushed source, not uncommitted files, ignored environments or private investor data. Application backup must still cover consistent SQLite state and authoritative evidence separately.

For authorized source synchronization, follow the [hosted CI handoff protocol](NEXT_STEP.md#github-synchronization-and-hosted-ci-handoff): review the previous relevant run at the next sync and finish each push without waiting for its new Actions run. Required local checks still apply. Actions runs remain enabled; no workflow, branch protection or release gate is changed by this timing preference.

Independent software/tax/risk review, other-machine/OS checks, financial/application tests, investor acceptance and release remain separate evidence gates. Hosted CI evidence is recorded per exact commit in STATUS. [STATUS](../STATUS.md) owns the current next task and exact handoff identity.
