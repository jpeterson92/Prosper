import { useState } from "react";
import { ClientError, connect } from "./client";
import { BenchmarkSourceView } from "./benchmark-source";
import { BenchmarkReviewForm } from "./benchmark-review-form";
import type { BenchmarkFetch, BenchmarkImport, BenchmarkObservation, BenchmarkResult, BenchmarkReview, BenchmarkDiagnostic, BenchmarkSelect, Catalog, Current, Run } from "./client";

export type BenchmarkAction = { kind: "benchmark-diagnostic"; body: BenchmarkDiagnostic } | { kind: "benchmark-select"; body: BenchmarkSelect };
type FetchAction = { kind: "source"; body: BenchmarkFetch } | { kind: "import"; body: BenchmarkImport };

export function BenchmarkView({ result }: { result: BenchmarkResult }) {
  return <article aria-label="Benchmark proxy review">
    <h3>{result.ticker} / {result.effective_date} / {result.label}</h3>
    <p>{result.status}</p><p>Requested: {result.requested_date ?? "Latest reported"}; effective: {result.effective_date}; collected: {result.collected_at}; reviewed: {result.reviewed_at}.</p>
    <p>Reviewed metadata: {result.metadata_reference}; fund {result.metadata_port_id}; CUSIP {result.metadata_cusip}; source {result.metadata_source_sha256}.</p>
    <p>{result.source_row_count} source rows; {result.included_count} included equities; {result.excluded_count} excluded; {result.linked_count} linked representations; {result.unresolved_count} unresolved.</p>
    <p>Retained equity value E: {result.equity_value_total ?? "Unavailable"} USD. Known excluded value: {result.excluded_known_usd_value} USD; unknown excluded values: {result.excluded_unknown_usd_values.length}.</p>
    <ul>{result.warnings.map((warning, i) => <li key={i}>{warning}</li>)}{result.issues.map((issue, i) => <li key={`issue-${i}`}>{issue.location}: {issue.code}</li>)}</ul>
    <div className="table-scroll"><table><caption>All original source row dispositions</caption><thead><tr><th>Locator</th><th>Disposition / reason</th><th>Security</th><th>Original market value</th><th>Original percentage</th><th>Derived weight</th><th>Issues</th></tr></thead><tbody>{result.ledger.map((row, i) => <tr key={i}><td>{row.locator.section}:{row.locator.index}</td><td>{row.disposition} / {row.reason ?? "See reviewed relationship"}{row.target && ` → ${row.target.section}:${row.target.index}`}</td><td>{row.security_id ?? "Unmapped"}</td><td>{row.raw_value === "" ? "Blank" : row.raw_value ?? "Unknown"} ({row.value_token_kind})</td><td>{row.raw_percentage === "" ? "Blank" : row.raw_percentage ?? "Unknown"} ({row.percentage_token_kind})</td><td>{row.derived_weight ?? "Unavailable"}</td><td>{row.issues.join(", ")}</td></tr>)}</tbody></table></div>
  </article>;
}

export function BenchmarkControls({ current, catalog, disabled, api, onMutate, onRefresh, saved }: {
  current: Current | null; catalog: Catalog | null; disabled: boolean;
  api: () => ReturnType<typeof connect>; onMutate: (action: BenchmarkAction) => void;
  onRefresh: () => Promise<void>; saved: Run | null;
}) {
  const [provider, setProvider] = useState<"BlackRock iShares" | "Vanguard">("BlackRock iShares");
  const [ticker, setTicker] = useState<"" | BenchmarkFetch["ticker"]>("");
  const [mode, setMode] = useState(""); const [day, setDay] = useState("");
  const [observation, setObservation] = useState<BenchmarkObservation | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [rawReview, setRawReview] = useState<string | null>(null);
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false); const [pending, setPending] = useState<FetchAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const locked = disabled || busy || pending !== null;
  async function perform(action: () => Promise<void>) { setBusy(true); setError(null); try { await action(); } catch (error) { setError(error instanceof ClientError && error.status === 422 ? "Invalid benchmark file or review. Check fund, date, source bindings and current schema." : "Benchmark request failed. Retry the identical fetch if its response is unresolved."); } finally { setBusy(false); } }
  function show(value: BenchmarkObservation) { setObservation(value); setSource(null); setRawReview(null); setResult(null); setReviewed(false); }
  async function fetchAction(action: FetchAction) {
    setPending(action);
    try { const c = await api(); show(action.kind === "source" ? await c.fetchBenchmark(action.body) : await c.importBenchmark(action.body)); setPending(null); await onRefresh(); }
    catch (error) { if (error instanceof ClientError && [400, 409, 413, 415, 422].includes(error.status ?? 0)) setPending(null); throw error; }
  }
  const savedResult = saved?.model_version === "benchmark-proxy-v1" && saved.status === "partial" ? saved.outputs as unknown as BenchmarkResult : null;
  return <section aria-label="Standard benchmark">
    <h2>Standard benchmark</h2><p>BlackRock iShares is the default holdings provider. Choose a fund and reported holdings date explicitly. ITOT covers the U.S. total market; IVV covers the S&amp;P 500. Review fund metadata, every row and the equity-only proxy before selecting it. No fund, date or provider fallback is applied.</p>
    <p>Selected benchmark result: {typeof current?.settings.benchmark_run_id === "string" ? current.settings.benchmark_run_id : "None"}</p>
    <label>Benchmark provider<select disabled={locked} value={provider} onChange={e => {setProvider(e.target.value as typeof provider);setTicker("");}}><option>BlackRock iShares</option><option>Vanguard</option></select></label>
    <label>{provider === "Vanguard" ? "Vanguard fund" : "iShares fund"}<select disabled={locked} value={ticker} onChange={e => { setTicker(e.target.value as typeof ticker); }}><option value="">Choose a fund</option>{provider === "Vanguard" ? <><option value="VTI">VTI</option><option value="VOO">VOO</option></> : <><option value="ITOT">ITOT — U.S. total market</option><option value="IVV">IVV — S&amp;P 500</option></>}</select></label>
    <label>Holdings date request<select disabled={locked} value={mode} onChange={e => setMode(e.target.value)}><option value="">Choose a date request</option><option value="latest">Latest reported</option><option value="historical">Specific reported date</option></select></label>
    {mode === "historical" && <label>Reported holdings date<input type="date" value={day} disabled={locked} onChange={e => setDay(e.target.value)} /></label>}
    <button disabled={locked || !ticker || !mode || (mode === "historical" && !day)} onClick={() => void perform(() => fetchAction({ kind: "source", body: { observation_id: crypto.randomUUID(), ticker: ticker as BenchmarkFetch["ticker"], requested_date: mode === "latest" ? null : day } }))}>Fetch full holdings</button>
    {pending && <button disabled={disabled || busy} onClick={() => void perform(() => fetchAction(pending))}>Retry identical benchmark fetch</button>}
    <details><summary>Import saved benchmark response</summary><label>Saved benchmark response JSON<input type="file" accept=".json" disabled={locked} onChange={e => { const file = e.target.files?.[0]; if (file) void perform(async () => { if (file.size > 16 * 1024 * 1024) throw new ClientError(422); const fixture = JSON.parse(await file.text()) as BenchmarkImport; await fetchAction({ kind: "import", body: fixture }); }); }} /></label></details>
    <label>Retained benchmark observation<select value={observation?.request.observation_id ?? ""} disabled={locked} onChange={e => { const id = e.target.value; if (id) void perform(async () => show(await (await api()).benchmarkObservation(id))); }}><option value="">Choose an observation</option>{catalog?.benchmarks.map(o => <option key={o.request.observation_id} value={o.request.observation_id}>{o.request.ticker} / {o.effective_date ?? o.request.requested_date ?? "latest requested"} / {o.status} / {o.request.observation_id}</option>)}</select></label>
    {observation && <article aria-label="Benchmark observation"><p>{observation.request.ticker}; {observation.status}. Requested {observation.request.requested_date ?? "latest reported"}; effective {observation.effective_date ?? "unavailable"}; collected {observation.collected_at}.</p><BenchmarkSourceView key={observation.request.observation_id} observation={observation} api={api} /><p>{observation.status === "pending" ? "An attempt was reserved but has no saved response. A new explicit fetch is required; retrying this ID never repeats the network request." : "Acquisition does not select a benchmark."}</p><button disabled={locked || !observation.source_sha256} onClick={() => void perform(async () => setSource(await (await api()).benchmarkSource(observation.request.observation_id)))}>Read original benchmark response</button>{source && <details open><summary>Original retained response</summary><pre>{source}</pre></details>}</article>}
    {observation?.status === "observed" && <BenchmarkReviewForm key={observation.request.observation_id} observation={observation} disabled={locked} api={api} onInvalidate={()=>{setRawReview(null);setResult(null);setReviewed(false);}} onPreview={build=>void perform(async()=>{setRawReview(null);setResult(null);setReviewed(false);const review=await build();const raw=JSON.stringify(review);const inspected=await (await api()).previewBenchmark(raw);setRawReview(raw);setResult(inspected);})} />}
    <details><summary>Import a prepared benchmark review</summary><label>Reviewed benchmark mapping and metadata JSON<input type="file" accept=".json" disabled={locked} onChange={e => { setRawReview(null); setResult(null); setReviewed(false); const file = e.target.files?.[0]; if (file) void perform(async () => { if (file.size > 16 * 1024 * 1024) throw new ClientError(422); const raw = await file.text(); const inspected = await (await api()).previewBenchmark(raw); setRawReview(raw); setResult(inspected); }); }} /></label></details>
    {result && <><BenchmarkView result={result} /><details><summary>Supplied review decisions and evidence</summary><pre>{JSON.stringify({ ...JSON.parse(rawReview!), metadata_base64: "Original metadata available below" }, null, 2)}</pre><button disabled={locked} onClick={() => { const review = JSON.parse(rawReview!) as BenchmarkReview; const bytes = Uint8Array.from(atob(review.metadata_base64), c => c.charCodeAt(0)); const url = URL.createObjectURL(new Blob([bytes], { type: "application/octet-stream" })); const link = document.createElement("a"); link.href = url; link.download = "reviewed-fund-metadata.bin"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }}>Download supplied fund metadata</button></details><label><input type="checkbox" checked={reviewed} disabled={locked} onChange={e => setReviewed(e.target.checked)} />I reviewed fund identity, reporting date, row accounting and exclusions</label><button disabled={locked || !reviewed || !current?.snapshot_id} onClick={() => onMutate({ kind: "benchmark-diagnostic", body: { run_id: crypto.randomUUID(), expected_revision: current!.revision, as_of: new Date().toISOString(), review: JSON.parse(rawReview!) as BenchmarkReview } })}>Save reviewed benchmark result</button></>}
    {savedResult && <><BenchmarkView result={savedResult} /><button disabled={locked || savedResult.status !== "estimated-equity-benchmark"} onClick={() => onMutate({ kind: "benchmark-select", body: { run_id: saved!.id, command_key: crypto.randomUUID(), expected_revision: current!.revision } })}>Select this reviewed benchmark</button></>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
