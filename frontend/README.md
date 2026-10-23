# Synthetic browser diagnostic

T004.4.1.1 qualifies the local browser/client boundary. This fixed-fictional-data probe is not a portfolio review interface. It stages F001, an equivalent precise-source variant and an incomplete-basis variant, checks transport/current-state preservation and shows only diagnostic status. There are no file-selection, commit/reject or trading controls. Staging adds durable synthetic preview evidence; it does not activate a checkpoint.

From the repository root on the qualified Windows x64 host:

```powershell
.\scripts\frontend.ps1 -Command bootstrap
.\scripts\frontend.ps1 -Command check
```

Bootstrap needs the existing project Python `.venv`, downloads the pinned portable official Node 24.22.1 archive into ignored `.tools` if missing, checks its recorded SHA-256, installs `package-lock.json` with `npm ci --ignore-scripts`, and installs Playwright Chromium in its ordinary user cache. It does not change global Node, npm or PATH. Network access to nodejs.org, registry.npmjs.org and the Playwright download service is required for a cold setup. The helper restores its process PATH/working directory. Later `sync` repeats the locked package installation; `build` builds without installing; `contracts` deliberately refreshes the authored schema/types after an intended backend contract change. Normal `check` captures fresh protected OpenAPI and rejects drift rather than rewriting the contract.

Run the built diagnostic using an absolute synthetic runtime and build path:

```powershell
$prosperSource = (Get-Location).Path
.venv/Scripts/python.exe -m prosper.local_api --source-root $prosperSource --synthetic-runtime (Join-Path $prosperSource '.local/browser-demo') --ui-dist (Join-Path $prosperSource 'frontend/dist')
```

Open the printed public origin in a browser and select **Check connection**. No token appears in the URL or process output. Build files are loaded once at startup; restart after rebuilding. Only `/` and direct snapshotted JS/CSS files are public for bootstrap. API/session checks remain active. No arbitrary filesystem route or SPA fallback exists. Runtime/evidence roots, JSON, source maps and other files are not served. Build selection is trusted launcher configuration, not an imported setting; the development host/build must be trusted.

`dev` starts Vite on exactly `127.0.0.1:5173` with strict port/no fallback. Cross-origin API access additionally requires the existing launcher's explicit `--development-port 5173`; there is no production origin override, proxy or wildcard. The browser suite exercises the exported source probe against that trusted development API. Built diagnostics use their own origin and bundled assets.

`check` runs actual-schema drift, isolated deliberate-failure checks, strict TypeScript, production build and seven Playwright cases. Browser traces/video are disabled to avoid recording bearer headers; screenshots, request-path summaries, dependency inventory and synthetic databases are ignored under `.local`. Tests intercept unexpected runtime network destinations/queries and fail on console errors, persisted session data and observed token leakage. This is bounded browser evidence, not an OS network firewall or local-malware isolation.

The generator maps the API's octet-stream `contentMediaType` to `Uint8Array<ArrayBuffer>` and uses an identity body serializer. Decimal book values remain generated strings. The client does not independently validate financial rules; the existing backend remains authoritative. Current generation values beyond JavaScript's safe-integer range fail explicitly. The complete review screen and its hostile-text/exact-display checks belong to T004.4.1.2.

For an installed-wheel browser qualification, set process-only `PROSPER_BROWSER_PYTHON` to the absolute isolated wheel environment's Python, run the helper's `check`, then restore/remove that variable. This override affects test/tool processes only. [Execution evidence](../docs/tasks/T004.4.1.1-browser-client.md) owns the exact versions, commands, observations and limits.
