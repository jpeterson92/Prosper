# Synthetic import review

T004.4.2 adds reviewed commit/reject actions to the synthetic preview/current-checkpoint screen over T004.4.1's qualified browser/client boundary. Choose a fictional canonical JSON file and select **Stage preview**, or retrieve a retained preview by original-byte SHA-256. **Current checkpoint** and **Refresh current state** inspect active state separately. Staging retains original evidence but does not activate it. Only synthetic files are authorized; never select real account data.

Inspect the preview, its readiness reasons and current state, then check the review acknowledgment before choosing **Commit reviewed preview** or **Reject reviewed preview**. Commit requires an inspection-valid, non-rejected preview and binds a new command key to the displayed expected generation. A stale result requires new review; source/identity conflicts offer no override. Rejection is terminal for the original bytes and preserves evidence; committed previews cannot be rejected. Financial planning and trade approval remain unavailable even after activation, including when basis/coverage is incomplete.

The last command panel shows its exact preview/key/expected generation and original durable receipt separately from a fresh current-state read. **Retry same commit command** reuses that frozen payload; no automatic write retry occurs. If a response is lost, a replacement command is blocked until the retained command is resolved. Keep the recovery details before reload, retrieve the original preview and use **Resume a commit after reload** with the saved key and original generation. A saved command that never reached the runtime may execute when explicitly resumed. A refused key cannot be rebound to different facts; correct its recovery details or review for a new command. Recovery details and sessions remain in memory, without browser persistence. Rejected previews can be retrieved after reload; unresolved rejection can be retried or resolved through fresh reads. A failed follow-up read preserves a known durable receipt while marking current state unavailable.

From the repository root on the qualified Windows x64 host:

```powershell
.\scripts\frontend.ps1 -Command bootstrap
.\scripts\frontend.ps1 -Command check
```

Browser tests default to **four workers with full parallelism**, including tests in the same file. Use the tests-only helper against the current existing build during development; it does not rebuild or regenerate contracts. File filters are relative to `frontend/` and use Playwright's regular-expression matching; `-Grep` is a title regular expression. Multiple files and a title pattern are combined. No matching tests is a failure, never a fallback full run. `-Workers 1` provides serial debugging.

```powershell
# Tests only against the current build.
.\scripts\frontend.ps1 -Command test -TestPath tests/browser.spec.mjs -Grep 'old token after restart' -Workers 1
.\scripts\frontend.ps1 -Command test -TestPath tests/browser.spec.mjs,tests/review.spec.mjs -Grep 'diagnostic error status|display-only decimal' -Workers 2

# Full frontend verification; defaults to four browser workers.
.\scripts\frontend.ps1 -Command check

# Full local commit/sync checkpoint, only when explicitly authorized.
.\scripts\checkpoint.ps1
```

`check` always runs contracts, typing, build and the complete browser suite; it rejects `-TestPath`/`-Grep`. The [combined checkpoint helper](../scripts/checkpoint.ps1) completes full Python checks and package qualification before starting full frontend verification, stopping on either stage's failure. Its Python `-Workers` defaults to `auto`, `-BrowserWorkers` defaults to `4`, and `-ForceFull` forwards the existing Python full-result-reuse override. The individual `dev.ps1 -Command checkpoint` remains the Python/package stage. Do not overlap full Python and browser suites in separate invocations; each suite can use its own internal parallelism. The helper does not lock unrelated sessions or schedule tests. [Browser workflow evidence](../docs/tasks/BROWSER_TEST_WORKFLOW.md) records actual timings, focused/guard checks and qualification limits.

Bootstrap needs the existing project Python `.venv`, downloads the pinned portable official Node 24.22.1 archive into ignored `.tools` if missing, checks its recorded SHA-256, installs `package-lock.json` with `npm ci --ignore-scripts`, and installs Playwright Chromium in its ordinary user cache. It does not change global Node, npm or PATH. Network access to nodejs.org, registry.npmjs.org and the Playwright download service is required for a cold setup. The helper restores its process PATH/working directory. Later `sync` repeats the locked package installation; `build` builds without installing; `contracts` deliberately refreshes the authored schema/types after an intended backend contract change. Normal `check` captures fresh protected OpenAPI and rejects drift rather than rewriting the contract.

Run the built review interface using an absolute synthetic runtime and build path:

```powershell
$prosperSource = (Get-Location).Path
.venv/Scripts/python.exe -m prosper.local_api --source-root $prosperSource --synthetic-runtime (Join-Path $prosperSource '.local/browser-demo') --ui-dist (Join-Path $prosperSource 'frontend/dist')
```

Open the printed public origin in a browser. Stage `examples/synthetic/F001.json` for the fictional reference preview; select **Current checkpoint** to inspect active state. The earlier **Check connection** fixed-fixture probe remains under **Developer connection diagnostic** and stages its own synthetic previews. No token appears in the URL or process output. Build files are loaded once at startup; restart after rebuilding. Only `/` and direct snapshotted JS/CSS files are public for bootstrap. API/session checks remain active. No arbitrary filesystem route or SPA fallback exists. Runtime/evidence roots, JSON, source maps and other files are not served. Build selection is trusted launcher configuration, not an imported setting; the development host/build must be trusted.

`dev` starts Vite on exactly `127.0.0.1:5173` with strict port/no fallback. Cross-origin API access additionally requires the existing launcher's explicit `--development-port 5173`; there is no production origin override, proxy or wildcard. The browser suite exercises the exported source probe against that trusted development API. The built review uses its own origin and bundled assets.

`check` runs actual-schema drift, isolated deliberate-failure checks, strict TypeScript, production build and 33 Playwright checks (32 browser scenarios and one decimal-display test). These include real lifecycle actions, original receipt retries, historical duplicate no-ops, source/identity conflicts, terminal rejection and rejected-commit races, two-window stale review, reload/restart, lost write responses, same-key changed-payload refusal and failed post-command reads. The integrated recovery case backs up browser-created state and all referenced evidence, restores to a new isolated runtime and checks exact/unknown facts and the original durable command receipt. Browser traces/video are disabled to avoid recording bearer headers; screenshots, request-path summaries, dependency inventory and synthetic databases are ignored under `.local`. Tests intercept unexpected runtime network destinations/queries and fail on console errors, persisted session data and observed token leakage. Missing/invalid sessions and foreign browser origins cannot mutate state in exercised cases. This is bounded browser evidence, not an OS network firewall or local-malware isolation.

The generator maps the API's octet-stream `contentMediaType` to `Uint8Array<ArrayBuffer>` and uses an identity body serializer. Decimal book values remain generated strings. The client does not independently validate financial rules; the existing backend remains authoritative. Current generation values beyond JavaScript's safe-integer range fail explicitly. The review shows source cutoff/inclusion, located readiness/parser reasons, exact/source quantum details, lots, positions and separate cash buckets. Optional two-decimal HALF_EVEN formatting uses decimal strings and scaled integers, never binary floating-point book values; exact facts remain unchanged. Session/request failures require explicit refresh/retrieval; upload response uncertainty can be checked using the digest computed before staging. No automatic upload retry occurs.

For an installed-wheel browser qualification, set process-only `PROSPER_BROWSER_PYTHON` to the absolute isolated wheel environment's Python, run the helper's `check`, then restore/remove that variable. This override affects test/tool processes only. [Toolchain evidence](../docs/tasks/T004.4.1.1-browser-client.md) owns the qualified versions; [inspection UI evidence](../docs/tasks/T004.4.1.2-inspection-ui.md) and [lifecycle evidence](../docs/tasks/T004.4.2-lifecycle-ui.md) own their acceptance, artifacts and limits.
