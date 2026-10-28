# Local application artifact

One installed application uses one explicitly chosen local workspace. There is no synthetic/research runtime mode, checkout-location requirement or mode marker. There is no invented-versus-real category in the application. All inputs use the same source, numerical and state checks, without implying financial authorization. [STATUS](../STATUS.md) names current evidence and remaining actual-input/acceptance work.

## Build and launch

From the checkout, `./scripts/local-artifact.ps1 -Name <new-name>` builds the current frontend and installs a wheel into a new local artifact. Build for launch/package/worker-resolution changes or a delivery checkpoint, rather than routine text/default/UI edits. Never copy a virtual environment between paths.

In the artifact directory:

```powershell
./Launch.ps1 -Command initialize -Workspace C:/ProsperData/my-session
./Launch.ps1 -Command start -Workspace C:/ProsperData/my-session
```

Choose your actual absolute local path; the example does not create or authorize any owner data location. Its parent must exist. Initialization exclusively creates a new workspace; an existing folder or partial initialization refuses without reset. Start opens the existing database and installed assets; it never creates a missing portfolio. The data directory must stay outside the replaceable artifact. Ordinary local path/link, corrupted/unsupported state and asset checks remain.

Current checkout storage schema is **13**, reflecting source-bound cash treatments, reported holding facts and prepared identity/exclusion reports. The previously identified installed artifact remains schema 11 until an explicit rebuild; its evidence does not cover these checkout changes. Older stores/backups refuse clearly and remain untouched. For development checks, deliberately use a fresh workspace and reimport original inputs; no automatic migration, deletion, reset or repair occurs. Preserve an older artifact when needed to read its state.

## Explicit personal research mode

This historical heading is retained for existing documentation links. Personal research is now the ordinary local workflow, rather than a separate storage mode. The UI shows exploratory estimates and unavailable financial-use authorization. Separate experiments can use different chosen data directories. An installed app does not need to know where its source checkout is.

For source-checkout development, initialize a fresh ignored scratch runtime explicitly:

```powershell
./scripts/frontend.ps1 -Command build
.venv/Scripts/python.exe -m prosper.local_api --runtime C:/ProsperScratch/session --initialize --ui-dist frontend/dist
```

Reopen with the same command without `--initialize`. Initialization refuses an existing directory. Paths are explicit; a missing/corrupt database never silently becomes an empty portfolio. The API still binds loopback and checks host/origin/session; explicit development origins remain a development-only choice, not an automatic fallback.

## Inputs and results

For initial Fidelity-shaped diagnostics, select the combined CSV and enter its source account identifier and snapshot date for the supported U.S. taxable USD account. A reviewed context JSON is optional. Without it, exact quantities/basis/rows survive while identities, tax classifications, source completeness, basis assumption and activity coverage stay unknown. This opening diagnostic does not guess security mappings, current marks or eligible losses. An explicitly reviewed context/settings can supply further facts.

History/model inputs retain source dates, provider/identity/convention facts and unknowns. There is no fictional/synthetic flag or separate data-origin path. Exploratory fitting requires a complete usable declared union, UTC sessions, coherent OHLC/total returns/actions, explicit compatible conventions and a reviewed profile; incompatible/missing facts still block dependent output. The selected IDR-DCC-NL equations and financial caps are unchanged. Use a saved input configuration to avoid repeatedly preparing the same files. Benchmark observations can be fetched or uploaded using **Saved benchmark response JSON**; both use the same parser and review rules.

In the current checkout UI, open a retained observed benchmark and use **Prepare benchmark review**. The inspected IVV layout prefills section/row mappings and explicit exclusions with coverage highlights. **Prepare official fund metadata** checks the fixed official page's identity/date facts, retains the complete original and fills attributable evidence plus zero modeled cash by the equity-only proxy definition. Checked metadata is reused on retry/reopen. It does not assert human review or actual fund cash/buying power. Manual file/identity/evidence controls remain under collapsed **Advanced fund metadata**, accepting complete originals up to **4 MiB**. Other layouts retain unresolved fields. Search/page rows and select exact rows for shared evidence or reasoned exclusions. **Preview prepared benchmark review** uses the existing financial review checks; incomplete inputs remain located blockers. Review the consolidated preview before explicitly saving and selecting through the existing snapshot-bound flow. Unsaved form edits clear on reload or observation change; retained checked metadata and saved results use current backup/reopen behavior. **Import a prepared benchmark review** remains optional. The installed artifact contains these checkout changes only after an explicitly selected later rebuild; STATUS identifies the actual artifact version.

## Personal cash treatment in the current checkout

Import and review holdings, select the snapshot, then open **Cash and cash equivalent treatment** in its review. An unmapped/unsupported holding offers **Mark as Cash**, **Mark as Cash equivalent** and **Undo cash treatment**, alongside its reported name, USD value/date or unknown. The action saves an explicit classification for that original source/account/date/holding; it does not change original rows, redeem a fund or add reported value to the investment budget. Matching lot and position values count once; incomplete/conflicting values remain unknown. Known mapped ordinary equities are outside this action's scope.

A change selects a new immutable snapshot revision and clears the current-result pointer. Historical saved outputs retain their original inputs. Current-format backup/restore/reopen preserves treatment; a fresh import has no inherited classification. Use a fresh explicitly chosen schema-13 workspace for this checkout. Earlier stores/backups remain untouched and need their earlier artifact for reading; there is no automatic conversion/reset. This feature was verified with fictional inputs, not an owner portfolio.

## Saved work and replacement

With the current checkout, select an original source-shaped holdings snapshot and a reviewed IVV benchmark from the same date. **Prepare stock mappings** stages supported local identity links, supplied-identity preservation, cash treatments and explicit exceptions, without a manual identity file. Optional exclusion reasons are under Advanced controls. The summary shows original-portfolio value coverage and strict 10/100 bps warnings; internal identifiers are in collapsed source evidence. Review and select the staged snapshot explicitly. A newer cash/source/benchmark choice cannot be overwritten by an older draft. Missing or conflicting evidence is not guessed; tax classification/history remain unchanged. To prepare a different draft, return to the original source snapshot or import a new source. These checkout features are verified with fictional inputs and are not in the previously identified installed artifact.

Use the protected backup download and clean-destination restore. Keep source originals and dated saved output; reads/exports/restores do not refit. Restore refuses corrupt or populated destinations and supports identical-response retries. Replace/remove the application separately from its data directory; no uninstall routine deletes the workspace. Retain old artifacts only when needed to read their state or investigate a concrete issue, not as a release-matrix requirement.

Actual private files, AI disclosure, provider requests, trading and publication require their concrete applicable scope. This guide is not financial authorization or broad platform/distribution support. The [MVP route](../tasks/REMAINING_WORK_PLAN.md#mvp-delivery-route) separates useful local exploration from financial reliance and public release.
