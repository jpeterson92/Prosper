# Synthetic import review

T004.4.1.2 adds the synthetic preview/current-checkpoint review screen over T004.4.1.1's qualified browser/client boundary. Choose a fictional canonical JSON file and select **Stage preview**, or retrieve a retained preview by original-byte SHA-256. **Current checkpoint** and **Refresh current state** inspect active state separately. Staging retains original evidence but does not activate it. Only synthetic files are authorized; never select real account data. No commit/reject or trading controls are included.

From the repository root on the qualified Windows x64 host:

```powershell
.\scripts\frontend.ps1 -Command bootstrap
.\scripts\frontend.ps1 -Command check
```

Bootstrap needs the existing project Python `.venv`, downloads the pinned portable official Node 24.22.1 archive into ignored `.tools` if missing, checks its recorded SHA-256, installs `package-lock.json` with `npm ci --ignore-scripts`, and installs Playwright Chromium in its ordinary user cache. It does not change global Node, npm or PATH. Network access to nodejs.org, registry.npmjs.org and the Playwright download service is required for a cold setup. The helper restores its process PATH/working directory. Later `sync` repeats the locked package installation; `build` builds without installing; `contracts` deliberately refreshes the authored schema/types after an intended backend contract change. Normal `check` captures fresh protected OpenAPI and rejects drift rather than rewriting the contract.

Run the built review interface using an absolute synthetic runtime and build path:

```powershell
$prosperSource = (Get-Location).Path
.venv/Scripts/python.exe -m prosper.local_api --source-root $prosperSource --synthetic-runtime (Join-Path $prosperSource '.local/browser-demo') --ui-dist (Join-Path $prosperSource 'frontend/dist')
```

Open the printed public origin in a browser. Stage `examples/synthetic/F001.json` for the fictional reference preview; select **Current checkpoint** to inspect active state. The earlier **Check connection** fixed-fixture probe remains under **Developer connection diagnostic** and stages its own synthetic previews. No token appears in the URL or process output. Build files are loaded once at startup; restart after rebuilding. Only `/` and direct snapshotted JS/CSS files are public for bootstrap. API/session checks remain active. No arbitrary filesystem route or SPA fallback exists. Runtime/evidence roots, JSON, source maps and other files are not served. Build selection is trusted launcher configuration, not an imported setting; the development host/build must be trusted.

`dev` starts Vite on exactly `127.0.0.1:5173` with strict port/no fallback. Cross-origin API access additionally requires the existing launcher's explicit `--development-port 5173`; there is no production origin override, proxy or wildcard. The browser suite exercises the exported source probe against that trusted development API. The built review uses its own origin and bundled assets.

`check` runs actual-schema drift, isolated deliberate-failure checks, strict TypeScript, production build and 19 Playwright checks (18 browser scenarios and one decimal-display test). Browser traces/video are disabled to avoid recording bearer headers; screenshots, request-path summaries, dependency inventory and synthetic databases are ignored under `.local`. Tests intercept unexpected runtime network destinations/queries and fail on console errors, persisted session data and observed token leakage. This is bounded browser evidence, not an OS network firewall or local-malware isolation.

The generator maps the API's octet-stream `contentMediaType` to `Uint8Array<ArrayBuffer>` and uses an identity body serializer. Decimal book values remain generated strings. The client does not independently validate financial rules; the existing backend remains authoritative. Current generation values beyond JavaScript's safe-integer range fail explicitly. The review shows source cutoff/inclusion, located readiness/parser reasons, exact/source quantum details, lots, positions and separate cash buckets. Optional two-decimal HALF_EVEN formatting uses decimal strings and scaled integers, never binary floating-point book values; exact facts remain unchanged. Session/request failures require explicit refresh/retrieval; upload response uncertainty can be checked using the digest computed before staging. No automatic upload retry occurs.

For an installed-wheel browser qualification, set process-only `PROSPER_BROWSER_PYTHON` to the absolute isolated wheel environment's Python, run the helper's `check`, then restore/remove that variable. This override affects test/tool processes only. [Toolchain evidence](../docs/tasks/T004.4.1.1-browser-client.md) owns the qualified versions; [inspection UI evidence](../docs/tasks/T004.4.1.2-inspection-ui.md) owns current acceptance, artifacts and limits.
