# Local development

Use a normal Windows/local filesystem checkout, Python 3.12/project `.venv`, editable `src/prosper`, pinned `uv.lock` and ordinary caches. The installed investor runtime is separate from source/dependencies; private data/backups remain outside source. Synthetic databases/logs/package/browser evidence may live in ignored `.local`. Use UTF-8/LF authored text and existing editor/Git attributes; do not normalize imported source-format fixture bytes. Do not copy environments between checkouts, force global temp/cache settings or reintroduce synced-folder workarounds.

## Reproducible commands

Run from the repository root in PowerShell. Helpers restore their process environment/working directory. Exact pins and license metadata live in the project/lock and [dependency inventory](DEVELOPMENT_DEPENDENCIES.md); compared future tools are not installed automatically.

| Intent | Command and scope |
| --- | --- |
| First setup | `./scripts/dev.ps1 -Command bootstrap`; pinned uv under ignored `.tools/uv`, locked editable `.venv` |
| Locked dependency refresh | `./scripts/dev.ps1 -Command sync` |
| Ordinary affected Python work | `./scripts/dev.ps1 -Command dev`; Ruff/format/strict mypy, affected tests and project checks |
| Cold/stale explicit selection | `./scripts/dev.ps1 -Command dev -TestPath tests/test_advisory_store.py,tests/test_import_api.py`; include actual consumers/failure paths |
| Selected tests only | `./scripts/dev.ps1 -Command test -TestPath tests/test_advisory_store.py`; does not imply lint/type/full coverage |
| Documentation | `./scripts/dev.ps1 -Command docs` after final edits |
| Fresh wheel probe | `./scripts/dev.ps1 -Command package`; offline build, isolated locked runtime install, dependency/import checks |
| Explicit full local code commit/sync | `./scripts/checkpoint.ps1`; full Python/package then full browser, stopping on failure |
| Browser setup/build | `./scripts/frontend.ps1 -Command bootstrap` / `-Command build` |
| Focused current-build browser tests | `./scripts/frontend.ps1 -Command test -TestPath tests/review.spec.mjs`; optional `-Grep` title filter |
| Full frontend only | `./scripts/frontend.ps1 -Command check`; contracts/negative checks/type/build/all browser tests |
| Intentional API generation | `./scripts/frontend.ps1 -Command contracts`, then check generated snapshot/client and consumers |

Python defaults to `auto` workers, serial debug `-Workers 0`. Browser defaults to four fully parallel workers, serial debug `-Workers 1`. Filters never silently broaden to full checks or count as full evidence. `-LastFailed` requires explicit Python paths; `-ForceFull` is for deliberate full verification under helper rules. Do not overlap separate full Python and browser invocations. No automatic full run for ordinary next-step completion.

## Disposable research

Owner-directed experiments live in top-level [research](../../research/README.md), a separate uv project/environment consuming the local editable core. [Research instructions](../../research/AGENTS.md) set a lighter quality bar: manually run scripts/notebooks, optional types/tests and cheap checks for the conclusion. Production pytest, Ruff, strict mypy, test-receipt input scans and the application wheel do not include research. The repository text/link checker still covers its authored files. Push/PR changes confined to `research/**` skip automatic CI; mixed application changes and manual workflow dispatch retain normal checks. Application scripts/tests must not import or execute experiments. Research-only tasks do not need production STATUS updates or full suites unless the owner explicitly requests a full checkpoint. Changes to core still require normal affected verification; no experiment changes application financial authority or defaults.

Keep research-only dependencies in its own project/lock; do not add them to the application environment. Generated outputs use ignored `.local/research/`; private inputs remain outside source with their applicable access authority. Delete or promote experiments deliberately without compatibility obligations. The research guide owns setup, minimal run records and removal instructions.

## Test receipts and caches

`.local/test-workflow/runs/<id>/` owns fresh test scratch/reports; `.local/test-workflow/state/` owns selection/baseline/failure/run-lock state. Testmon full-baseline validity, installed distributions, configuration/source/data/child-process inputs and actual execution settings determine selection/reuse, not timestamps alone. Failed/interrupted/mid-run-mutated candidates do not advance verification. Inspect an interrupted lock's actual ownership before removing it. Do not remove caches/disable checks or globally change ACLs to bypass a failure; use the permitted project-helper path for environment/cache contention.

The docs helper checks current authored UTF-8/LF text, local links and diff whitespace. T019.4 removed the supplemental whole-tree hash manifest and its command coupling. Git commits identify source checkpoints; specific fixture/reference artifacts can have identities for concrete evidence. Source-control backup is separate from investor-data recovery.

Follow [proportional verification design](VALIDATION.md#proportional-verification-design) when adding tests or runners. Separate lightweight input/guard fixtures from fitted-model fixtures; module/session fixtures are recreated in each participating pytest worker. Only tests that require a fit should pay for it. Keep complete experiments deliberate rather than invoking their CLI/full fitting from routine rejection tests. Reuse applicable unchanged experiment results; a representative installed-package smoke probe normally suffices unless a specific packaging/runtime discrepancy requires full numerical replay. Keep default parallel workers; fix unnecessary setup duplication instead of globally serializing checks. Explicit checkpoint and receipt-validity rules still apply.

## Local browser workflow

Use one selected local data directory per instance; the app has no invented-versus-real classification. The [artifact guide](../guides/LOCAL_ARTIFACT.md) describes deliberate initialization/reopen and optional reviewed input context. From source, use `python -m prosper.local_api --runtime <absolute-path> --initialize --ui-dist frontend/dist` for a fresh scratch directory, then omit `--initialize` to reopen. Installed launch uses `Launch.ps1 initialize/start -Workspace <absolute-path>`, without a source checkout or mode marker.

Build/install when launch/package/worker resolution changes or at a delivery checkpoint. Ordinary UI/default/label changes use affected checks/current frontend build, not a new artifact family. Keep loopback host/origin/bootstrap/bearer/no-store safeguards, bounded requests/decodes and safe import/export. No local runtime/file directory is served. Do not introduce test-selection/receipt infrastructure or repeat unchanged reference/workload studies without an observed problem.

## Current records and clean development state

`advisory_records.py`/`advisory_store.py`, `workspace.py` and `advisory_recovery.py` own the current normalized browser/service path. [DATA_CONTRACTS](../architecture/DATA_CONTRACTS.md) records current imports, retained history, run-owned source inputs and recovery. The shared path/error boundary is `storage.py`; bounded record scalars are `record_types.py`. Old checkpoint/proof registries, scheduler journals, exact-result analytical APIs and code-hash backups have been removed. Identify a fresh scoped synthetic runtime/reimport when a breaking development change requires it, without silent repair/wipe or deletion of unrelated/private data.

## Qualification limits

Keep the existing Windows x64 [GitHub checks](../../.github/workflows/checks.yml) on push/PR triggers except research-only paths, using full Python/package verification, read-only repository permissions and SHA-pinned official actions. Manual workflow dispatch remains available. The existing hosted job does not run the browser suite; full local checkpoints include it. No publishing/deployment stage is adopted. Local editable development and isolated wheel qualification remain separate; observed hosted execution/branch protection must not be inferred from configuration. Authorized syncs follow NEXT_STEP's prior-run review and nonblocking new-run handoff.

Affected tests, full source checkpoint, installed wheel, browser probe, real-source integration, observed investor installation and independent financial/model acceptance are separate evidence. The pre-compaction checkpoint `69f8cba299b7d130a87684809df77fe124b8fe5d` passed 1,565 Python and 33 browser tests plus package/contracts/build checks; current docs/STATUS records later actual scope. Hosted CI after this local commit was not triggered or verified. No tool command authorizes broker/account access, source publication, real-data disclosure or release.

For complete-union input diagnostics, follow the [modeled-input walkthrough](../../examples/synthetic/modeled-inputs/README.md). Review the complete held/selected-benchmark/candidate grid and explicit source/profile/investor settings, save a dated diagnostic and reopen it through Saved diagnostic. Rechecking reads current sources/settings; old outputs and required originals remain immutable. Complete synthetic coverage is not model qualification or a financial-use permission.
