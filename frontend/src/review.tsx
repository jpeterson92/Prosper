import { useEffect, useRef, useState } from "react";
import { ClientError, connect } from "./client";
import type { Alignment, HistoryReview, HistoryManifest, HistoryRequest, HistoryDiagnosticRequest, Catalog, Current, DiagnosticRequest, Preview, Run, SelectRequest, SettingsRequest } from "./client";
import { HistoryRows, SavedHistory } from "./history";
import { decimalDisplay } from "./display";
import { LotControls, LotView } from "./lots";
import type { LotAction } from "./lots";
import { BenchmarkControls } from "./benchmark";
import type { BenchmarkAction } from "./benchmark";
import { CandidateControls, CandidateView } from "./candidates";
import { Worksheets } from "./worksheets";
import type { WorksheetAction } from "./worksheets";
import type { Worksheet } from "./client";
import type { CandidateAction } from "./candidates";
import { InputsControls, InputsView } from "./inputs";
import type { InputsAction } from "./inputs";
import type { ModeledResult } from "./client";

type Pending = WorksheetAction | CandidateAction | InputsAction | BenchmarkAction | LotAction | { kind: "history-refresh"; body: HistoryManifest } | { kind: "history-discard"; body: HistoryManifest } | { kind: "history-diagnostic"; body: HistoryDiagnosticRequest } | { kind: "history-clear"; body: { command_key: string; expected_revision: number } } | { kind: "select"; body: SelectRequest } | { kind: "settings"; body: SettingsRequest } | { kind: "diagnostic"; body: DiagnosticRequest } | { kind: "restore"; body: Uint8Array<ArrayBuffer> };
type Fact = { value: string | null; reason?: string | null };
function resourceMessage(problem: unknown): string | null {
  if (!(problem instanceof ClientError)) return null;
  if (problem.code === "history_alignment_size_limit") return "The complete history alignment exceeds the current record limit. Retained sources remain available; risk diagnostics are blocked.";
  if (problem.code === "pending_history_budget_exceeded") return "Pending history parts exceed the staging budget. Refresh the workspace and discard unneeded pending parts before reselecting the complete file.";
  return null;
}
function FactValue({ fact, rounded = false }: { fact: Fact; rounded?: boolean }) {
  return fact.value === null ? <span className="unknown">Unknown <small>{fact.reason}</small></span> : <span className="number" title={fact.value}>{rounded ? decimalDisplay(fact.value, true) : fact.value}</span>;
}
function Snapshot({ preview, rounded }: { preview: Preview; rounded: boolean }) {
  const s = preview.snapshot;
  return <article aria-label="Snapshot review">
    <section><h2>Reviewed source</h2><dl className="facts">
      <div><dt>Account</dt><dd>{s.account_alias} / {s.account_id}</dd></div>
      <div><dt>Scope</dt><dd>{s.account_scope}</dd></div>
      <div><dt>Source / as of</dt><dd>{s.source_name} / {s.source_as_of}</dd></div>
      <div><dt>Snapshot ID</dt><dd>{preview.id}</dd></div>
      <div><dt>Original source SHA-256</dt><dd>{s.source_sha256}</dd></div>
    </dl><p>Original source bytes are retained with this snapshot. Unknown facts block their dependent financial results.</p></section>
    <section><h3>Securities</h3><ul>{s.securities.map((row) => <li key={row.id}>{row.id} / {row.ticker} <FactValue fact={row.identity} /> <FactValue fact={row.classification} /><small>{row.source_ref}</small></li>)}</ul></section>
    <section><h3>Lots</h3><div className="table-scroll" tabIndex={0}><table><thead><tr><th>Lot / security</th><th>Quantity</th><th>Total basis (USD)</th><th>Acquired / term</th><th>Source row</th></tr></thead>
      <tbody>{s.lots.map((row) => <tr key={row.id}><th>{row.id}<small>{row.account_id} / {row.security_id}</small></th><td><FactValue fact={row.quantity} rounded={rounded} /></td><td><FactValue fact={row.total_basis} rounded={rounded} /></td><td><FactValue fact={row.acquired} /><FactValue fact={row.term} /></td><td>{row.source_ref}</td></tr>)}</tbody></table></div></section>
    <section><h3>Positions and cash observations</h3><ul>{s.positions.map((row) => <li key={row.id}>{row.security_id}: <FactValue fact={row.quantity} rounded={rounded} /><small>{row.source_ref}</small></li>)}{s.cash.map((row) => <li key={row.id}>{row.kind} ({row.currency}): <FactValue fact={row.amount} rounded={rounded} /><small>{row.source_ref}</small></li>)}</ul><p>Imported cash observations do not set an investment budget.</p></section>
    <section><h3>Source findings and exclusions</h3><ul>{[...s.findings, ...s.exclusions].map((f, i) => <li key={i}><strong>{f.code}</strong> / {f.locator}: {f.reason}</li>)}</ul><details><summary>Other supplied observations</summary><pre>{JSON.stringify(s.observations, null, 2)}</pre></details></section>
  </article>;
}

function DiagnosticView({ run, revision }: { run: Run; revision: number | undefined }) {
  const counts = run.outputs?.counts;
  const findings = run.outputs?.findings;
  return <article aria-label="Saved diagnostic">
    <p>{run.id} / {run.status} / {run.as_of}</p>
    <p>Saved input revision {run.input_revision}; {run.input_revision === revision ? "matches current inputs" : "historical inputs"}</p>
    {run.outputs?.kind === "history-inputs-v1" && <>
      <p>{run.outputs.coverage_complete === true ? "Recorded history coverage complete" : "Recorded history incomplete"}; this is input coverage, with financial qualification still unavailable.</p>
      {Array.isArray(run.outputs.ordered_securities) && <p>Saved security order: {run.outputs.ordered_securities.map(String).join(", ")}</p>}
      {Array.isArray(run.outputs.sessions) && <p>Saved sessions: {run.outputs.sessions.map(String).join(", ")}</p>}
    </>}
    {counts !== null && typeof counts === "object" && !Array.isArray(counts) && <dl className="facts">{Object.entries(counts).map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{typeof value === "number" ? value : "Unavailable"}</dd></div>)}</dl>}
    <ul>{run.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>
    {Array.isArray(findings) && <ul>{findings.map((finding, index) => finding && typeof finding === "object" && !Array.isArray(finding) ? <li key={index}><strong>{String(finding.code)}</strong> / {String(finding.locator)}: {String(finding.reason)}</li> : null)}</ul>}
    {run.exclusions.length > 0 && <><h3>Exclusions</h3><ul>{run.exclusions.map((f, i) => <li key={i}>{f.locator}: {f.reason}</li>)}</ul></>}
    {Array.isArray(run.outputs?.issues) && <ul>{run.outputs.issues.map((issue, index) => <li key={index}>{JSON.stringify(issue)}</li>)}</ul>}
    <SavedHistory run={run} />
    <LotView run={run} />
    <CandidateView run={run} />
    {run.model_version === "modeled-inputs-v1" && run.status === "partial" && <InputsView result={run.outputs as unknown as ModeledResult} label="Saved modeled inputs" />}
    <details><summary>Saved inputs and result record</summary><pre>{JSON.stringify(run, null, 2)}</pre></details>
  </article>;
}

export function Review() {
  const [current, setCurrent] = useState<Current | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [worksheet, setWorksheet] = useState<Worksheet | null>(null);
  const [historyFile, setHistoryFile] = useState<HistoryReview | null>(null);
  const [historyReviewed, setHistoryReviewed] = useState(false);
  const [historyRequest, setHistoryRequest] = useState<HistoryRequest | null>(null);
  const [alignment, setAlignment] = useState<Alignment | null>(null);
  const [manualNames, setManualNames] = useState("");
  const [clearReviewed, setClearReviewed] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [rounded, setRounded] = useState(false);
  const [settings, setSettings] = useState("{}");
  const [settingsReviewed, setSettingsReviewed] = useState(false);
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("Reading workspace...");
  const [runtimeReady, setRuntimeReady] = useState(false);
  const session = useRef<ReturnType<typeof connect> | null>(null);
  const active = useRef(false);
  const client = () => session.current ??= connect();
  async function refresh() {
    const c = await client(); await c.runtime(); setRuntimeReady(true); const state = await c.current();
    setCurrent(state); setCatalog(await c.catalog()); setReviewed(false); setSettingsReviewed(false);
  }
  async function perform(action: () => Promise<void>, mutation = false) {
    if (active.current) return;
    active.current = true; setBusy(true); setError(null);
    try { await action(); } catch (problem) {
      session.current = null;
      setError(resourceMessage(problem) ?? (mutation ? "The response is unresolved. Retry the identical pending action before making another change." : problem instanceof ClientError && problem.status === 422 ? "The file or request is invalid. Review the current format and source checksum." : "The local request failed. Check the runtime and retry."));
    } finally { active.current = false; setBusy(false); }
  }
  useEffect(() => { void perform(async () => { await refresh(); setMessage("Workspace read."); }); }, []);
  async function refreshAfterAction() {
    try { await refresh(); } catch {
      session.current = null; setCurrent(null);
      setError("The action outcome is shown above. Current state could not be refreshed. Refresh the workspace before another change.");
    }
  }
  async function execute(command: Pending) {
    const c = await client();
    try {
    if (command.kind === "worksheet-save") {
      setWorksheet(await c.saveWorksheet(command.body)); setMessage("Dated manual worksheet saved. Review its frozen inputs, assumptions and warnings.");
    } else if (command.kind === "candidate-start" || command.kind === "candidate-cancel") {
      setRun(command.kind === "candidate-start" ? await c.startCandidate(command.body) : await c.cancelCandidate(command.body)); setMessage("Candidate run state saved. Review progress and qualification below.");
    } else if (command.kind === "modeled-inputs") {
      setRun(await c.diagnoseInputs(command.body)); setMessage("Dated modeled input diagnostics saved.");
    } else if (command.kind === "benchmark-diagnostic") {
      setRun(await c.diagnoseBenchmark(command.body)); setMessage("Reviewed benchmark result saved; selection unchanged.");
    } else if (command.kind === "benchmark-select") {
      const result = await c.selectBenchmark(command.body); setMessage(`Benchmark selection: ${result.outcome}; revision ${result.revision}.`);
    } else if (command.kind === "lot-diagnostic") {
      setRun(await c.diagnoseLots(command.body)); setMessage("Dated lot diagnostics saved.");
    } else if ((command.kind === "diagnostic" || command.kind === "history-diagnostic")) {
      setRun(command.kind === "history-diagnostic" ? await c.diagnoseHistory(command.body) : await c.diagnose(command.body)); setMessage(command.kind === "history-diagnostic" ? "Dated history diagnostics saved." : "Dated source diagnostics saved.");
    } else {
      const result = command.kind === "lot-settings" ? await c.configureLots(command.body) : command.kind === "select" ? await c.select(command.body) : command.kind === "settings" ? await c.configure(command.body) : command.kind === "history-refresh" ? await c.refreshHistory(command.body) : command.kind === "history-discard" ? await c.discardHistory(command.body) : command.kind === "history-clear" ? await c.clearHistory(command.body) : await c.restore(command.body);
      setMessage(`Action result: ${result.outcome}; revision ${result.revision}.`);
    }
    } catch (problem) {
      if (problem instanceof ClientError && [400, 404, 409, 413, 415, 422].includes(problem.status ?? 0)) {
        setPending(null); setMessage("Action refused. Review current inputs or use an empty workspace for restore."); setError(resourceMessage(problem)); await refreshAfterAction(); return;
      }
      throw problem;
    }
    setPending(null); setReviewed(false); setSettingsReviewed(false); await refreshAfterAction();
  }
  function mutate(command: Pending) { setPending(command); void perform(() => execute(command), true); }
  function plan(mode: "missing" | "selected" | "full") {
    if (!historyRequest) return;
    const selected = mode === "full" ? historyRequest.series.map(s => s.security_id) : mode === "selected" ? manualNames.split(",").map(s => s.trim()).filter(Boolean) : [];
    const request = { ...historyRequest, manual_security_ids: selected };
    void perform(async () => { setAlignment(await (await client()).planHistory(request)); setMessage("History refresh plan read; no acquisition or financial calculation was requested."); });
  }
  const disabled = busy || pending !== null || current === null;
  return <>
    <header className="page-header"><div><p className="eyebrow">PROSPER / LOCAL WORKSPACE</p><h1>Current advisory workspace</h1><p>Review a snapshot, record explicit settings and save dated source diagnostics.</p></div><span className="badge" role="status" aria-label="Workspace purpose">{runtimeReady ? "Exploratory estimates; financial use unauthorized" : "Reading workspace"}</span></header>
    <p className="notice">Conditional lot loss estimates use reviewed source facts, marks and screening assumptions. Fitted-risk candidate runs require complete inputs and explicit settings. Financial-use authorization remains unavailable.</p>
    <p role="status" aria-label="Workspace status">{message}</p>{error && <p role="alert">{error}</p>}
    {pending && <section aria-label="Pending action"><p>An action is unresolved. Its original request is retained in this window.</p><button disabled={busy} onClick={() => void perform(() => execute(pending), true)}>Retry identical action</button></section>}
    <section aria-label="Current selection"><h2>Selected snapshot and settings</h2><p>Revision {current?.revision ?? "unknown"}; selected snapshot: {current?.snapshot_id ?? "None"}</p><p>Current diagnostic: {current?.current_run_id ?? "None"}</p><pre aria-label="Current settings">{JSON.stringify(current?.settings ?? {}, null, 2)}</pre>
      <button disabled={busy} onClick={() => void perform(async () => { await refresh(); setMessage("Workspace read."); })}>Refresh workspace</button>
      <button disabled={disabled || !current?.snapshot_id} onClick={() => void perform(async () => { setPreview(await (await client()).preview(current!.snapshot_id!)); setReviewed(false); })}>Review selected snapshot</button>
    </section>
    <section aria-label="Import"><h2>Import and review</h2><label>Normalized snapshot JSON file (up to 2 MiB)<input type="file" accept=".json" disabled={disabled} onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
      <button disabled={disabled || !file} onClick={() => void perform(async () => {
        if (!file || file.size > 2 * 1024 * 1024) throw new ClientError(422);
        setReviewed(false); setPreview(await (await client()).stage(await file.text())); await refresh(); setMessage("Preview staged; selected snapshot unchanged.");
      })}>Stage preview</button>
      <label>Retained snapshot<select value="" disabled={disabled} onChange={(event) => { const id = event.target.value; if (id) void perform(async () => { setReviewed(false); setPreview(await (await client()).preview(id)); }); }}><option value="">Choose a snapshot</option>{catalog?.snapshots.map((s) => <option key={s.id} value={s.id}>{s.state} / {s.imported_at} / {s.id}</option>)}</select></label>
      <label><input type="checkbox" checked={rounded} onChange={(event) => setRounded(event.target.checked)} />Round displayed numeric values to 2 decimals</label>
      {preview && <><label><input type="checkbox" checked={reviewed} disabled={disabled} onChange={(event) => setReviewed(event.target.checked)} />I reviewed this snapshot and its unknowns</label><button disabled={disabled || !reviewed} onClick={() => mutate({ kind: "select", body: { snapshot_id: preview.id, command_key: crypto.randomUUID(), expected_revision: current!.revision } })}>Select reviewed snapshot</button><button disabled={disabled} onClick={() => void perform(async () => { await (await client()).reject(preview.id); await refresh(); setReviewed(false); setMessage("Preview rejected."); })}>Reject preview</button></>}
    </section>
    <LotControls current={current} disabled={disabled} api={client} onPreview={value => { setPreview(value); setReviewed(false); void perform(refresh); }} onMutate={mutate} />
    <Worksheets current={current} run={run} catalog={catalog} worksheet={worksheet} onOpen={id=>void perform(async()=>setWorksheet(await (await client()).worksheet(id)))} api={client} onMutate={mutate} disabled={disabled}/>
    <CandidateControls current={current} disabled={disabled} api={client} onMutate={mutate} saved={run} onRead={setRun} onFinished={refresh} />
    <InputsControls current={current} disabled={disabled} api={client} onMutate={mutate} />
    <BenchmarkControls current={current} catalog={catalog} disabled={disabled} api={client} onMutate={mutate} onRefresh={refresh} saved={run} />
    {preview && <Snapshot preview={preview} rounded={rounded} />}
    <section aria-label="Settings"><h2>Explicit settings</h2><p>Record supplied settings as a JSON object. No financial defaults or validation of investor limits is supplied by this foundation.</p><label>Settings JSON<textarea rows={8} value={settings} disabled={disabled} onChange={(e) => { setSettings(e.target.value); setSettingsReviewed(false); }} /></label><button disabled={disabled} onClick={() => { setSettings(JSON.stringify(current!.settings, null, 2)); setSettingsReviewed(false); }}>Load current settings</button><label><input type="checkbox" checked={settingsReviewed} disabled={disabled} onChange={(e) => setSettingsReviewed(e.target.checked)} />I reviewed these settings</label><button disabled={disabled || !settingsReviewed} onClick={() => void perform(async () => {
      const value: unknown = JSON.parse(settings, (_key, value: unknown) => { if (typeof value === "number" && !Number.isFinite(value)) throw new ClientError(422); return value; }); if (value === null || Array.isArray(value) || typeof value !== "object") throw new ClientError(422);
      const command: Pending = { kind: "settings", body: { settings: value as SettingsRequest["settings"], command_key: crypto.randomUUID(), expected_revision: current!.revision } };
      setPending(command); try { await execute(command); } catch (problem) { session.current = null; setError("The settings response is unresolved. Retry the identical pending action."); }
    })}>Save reviewed settings</button></section>
    <section aria-label="Saved diagnostics"><h2>Dated diagnostics</h2><p>Saved source quality, conditional lot estimates and history coverage retain their original inputs. Financial qualification remains unavailable.</p><button disabled={disabled || !current?.snapshot_id} onClick={() => mutate({ kind: "diagnostic", body: { run_id: crypto.randomUUID(), expected_revision: current!.revision, as_of: new Date().toISOString() } })}>Save source diagnostics</button><label>Saved diagnostic<select value="" disabled={busy} onChange={(event) => { const id = event.target.value; if (id) void perform(async () => setRun(await (await client()).run(id))); }}><option value="">Choose a saved diagnostic</option>{catalog?.runs.map((id) => <option key={id} value={id}>{id}</option>)}</select></label>{run && <><DiagnosticView run={run} revision={current?.revision} />{run.status === "running" && run.model_version === "lot-opportunities-v1" && run.inputs?.lot_request && <button disabled={disabled} onClick={() => mutate({ kind: "lot-diagnostic", body: run.inputs!.lot_request as unknown as Extract<LotAction, {kind: "lot-diagnostic"}>["body"] })}>Resume saved lot diagnostic</button>}{run.status === "running" && run.model_version === "history-inputs-v1" && run.inputs?.history_request && <button disabled={disabled} onClick={() => mutate({ kind: "history-diagnostic", body: { run_id: run.id, expected_revision: run.input_revision, as_of: run.as_of, request: run.inputs!.history_request as HistoryRequest } })}>Resume saved history diagnostic</button>}{run.status === "running" && run.model_version === "source-quality-v1" && <button disabled={disabled} onClick={() => mutate({ kind: "diagnostic", body: { run_id: run.id, expected_revision: run.input_revision, as_of: run.as_of } })}>Resume saved diagnostic</button>}</>}</section>
    <section aria-label="Retained history">
      <h2>Retained history and manual refresh</h2>
      <p>Use normalized source responses with explicit identities, calendar, dates and conventions. Compatible observations can be reused. Changed or unverified vintages require a coherent full-window refresh. No provider is selected automatically.</p>
      <p>{catalog?.pending_history_parts.length ?? 0} pending history parts retained. Pending parts do not change active inputs; reselect the original file after restart to resume review. Backups include pending originals.</p>
      <button disabled={disabled || !catalog?.pending_history_parts.length} onClick={() => { setHistoryFile(null); setHistoryReviewed(false); void mutate({kind:"history-discard",body:{version:"advisory-history-manifest-v1",part_count:catalog!.pending_history_parts.length,part_ids:catalog!.pending_history_parts,command_key:crypto.randomUUID(),expected_revision:current!.revision}}); }}>Discard pending history parts</button>
      <label>History file (up to 64 MiB; staged in bounded parts)<input type="file" accept=".json" disabled={disabled} onChange={(event) => {
        const file = event.target.files?.[0]; if (file) void perform(async () => { setHistoryFile(null); setHistoryReviewed(false); if (file.size > 64 * 1024 * 1024) throw new ClientError(422); const review = await (await client()).previewHistory(await file.text()); await refresh(); setHistoryFile(review); });
      }} /></label>
      {historyFile && <><p>{historyFile.manifest.part_count} source parts staged; activation saves all reviewed parts together.</p>{historyFile.parts.map((part, i) => <article key={i} aria-label={`History source part ${i + 1}`}><p>{part.batch.source_name} / validated {part.batch.validated_at} / {part.batch.validation_scope}</p><p>{part.batch.rows.row_count} observations; {part.batch.contexts.map(c => `${c.security_id}: ${c.provider} / ${c.dataset} / ${c.vintage} / ${c.adjustment}`).join("; ")}</p><p>Original source SHA-256: {part.batch.source_sha256}</p><HistoryRows table={part.batch.rows} /></article>)}<label><input type="checkbox" checked={historyReviewed} disabled={disabled} onChange={(e) => setHistoryReviewed(e.target.checked)} />I reviewed the history source and conventions</label><button disabled={disabled || !historyReviewed} onClick={() => mutate({ kind: "history-refresh", body: { ...historyFile.manifest, command_key: crypto.randomUUID(), expected_revision: current!.revision } })}>Refresh from reviewed source</button></>}

      <label>Required history window JSON<input type="file" accept=".json" disabled={disabled} onChange={(event) => {
        const file = event.target.files?.[0]; if (file) void perform(async () => { if (file.size > 2 * 1024 * 1024) throw new ClientError(422); const value = await (await client()).planHistoryDocument(await file.text()); setHistoryRequest(value.request); setAlignment(value); });
      }} /></label>
      {historyRequest && <><p>Requested order: {historyRequest.series.map(c => c.security_id).join(", ")}; sessions {historyRequest.sessions[0]} through {historyRequest.cutoff}; predecessor {historyRequest.predecessor}.</p><p>Known at {historyRequest.known_at}; calendar evidence: {historyRequest.calendar_evidence}</p><label>Selected security IDs for manual refresh<input value={manualNames} disabled={disabled} onChange={(e) => setManualNames(e.target.value)} /></label><button disabled={disabled} onClick={() => plan("missing")}>Plan missing history</button><button disabled={disabled || !manualNames.trim()} onClick={() => plan("selected")}>Plan selected-name refresh</button><button disabled={disabled} onClick={() => plan("full")}>Plan full-window refresh</button><button disabled={disabled || !current?.snapshot_id} onClick={() => mutate({ kind: "history-diagnostic", body: { request: historyRequest, run_id: crypto.randomUUID(), expected_revision: current!.revision, as_of: new Date().toISOString() } })}>Save history diagnostics</button></>}
      {alignment && <article aria-label="History coverage"><p>{alignment.complete ? "Required retained observations complete" : "Required history incomplete"}. This coverage result does not establish model or source qualification.</p><ul>{alignment.intervals.map((i,n) => <li key={n}>{i.security_id}: {i.reason}; {i.sessions.join(", ")}</li>)}</ul><ul>{alignment.issues.map((i,n) => <li key={n}>{i.security_id} / {i.session ?? "window"}: {i.code} / {i.reason}</li>)}</ul><p>Full-window validation scope: {JSON.stringify(alignment.validated_at)}</p><HistoryRows table={alignment.rows} /></article>}
      <label><input type="checkbox" disabled={disabled} checked={clearReviewed} onChange={(e) => setClearReviewed(e.target.checked)} />Remove reusable history cache; keep all saved-run inputs and outputs</label><button disabled={disabled || !clearReviewed} onClick={() => mutate({ kind: "history-clear", body: { command_key: crypto.randomUUID(), expected_revision: current!.revision } })}>Clear reusable history cache</button>
    </section>
    <section aria-label="Recovery"><h2>Backup and restore</h2><p>Download the current workspace, including original sources and saved outputs. Restore accepts an empty workspace and never overwrites user work. Old development backups are unsupported.</p><button disabled={disabled} onClick={() => void perform(async () => {
      const blob = await (await client()).backup(); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "prosper-advisory.sqlite3"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); setMessage("Workspace backup downloaded.");
    })}>Download workspace backup</button><label>Current workspace backup (up to 64 MiB)<input type="file" disabled={disabled} onChange={(e) => setRestoreFile(e.target.files?.[0] ?? null)} /></label><button disabled={disabled || !restoreFile} onClick={() => void perform(async () => {
      if (!restoreFile || restoreFile.size > 64 * 1024 * 1024) throw new ClientError(422);
      const command: Pending = { kind: "restore", body: new Uint8Array(await restoreFile.arrayBuffer()) }; setPending(command); try { await execute(command); } catch { session.current = null; setError("Restore response unresolved or refused. Use an empty current workspace; retrying the same backup is safe."); }
    })}>Restore into empty workspace</button></section>
  </>;
}
