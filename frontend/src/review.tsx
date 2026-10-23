import { useEffect, useRef, useState } from "react";
import { ClientError, connect } from "./client";
import type { Command, CommitRequest, Current, Preview } from "./client";
import type { components } from "./generated/api";
import { decimalDisplay, locationText } from "./display";

type Source = components["schemas"]["SourceResponse"];
type Inspection = components["schemas"]["InspectionResponse"];
type Book = components["schemas"]["ValueResponse"];
type Fact = { value: string | null; reason: string | null };
const MAX_BYTES = 2 * 1024 * 1024;

function Value({ value, rounded }: { value: Book; rounded: boolean }) {
  return value.state === "known"
    ? <span className="number" title={`Exact: ${value.value}; source: ${value.original_text}; quantum: ${value.source_quantum}`}>{decimalDisplay(value.value, rounded)}</span>
    : <span className="unknown">Unknown <small>{value.reasons.join("; ")}</small></span>;
}

function FactValue({ fact, rounded = false, numeric = false }: { fact: Fact; rounded?: boolean; numeric?: boolean }) {
  return fact.value === null
    ? <span className="unknown">Unknown <small>{fact.reason ?? "No reason supplied"}</small></span>
    : <span className={numeric ? "number" : ""}>{numeric ? decimalDisplay(fact.value, rounded) : fact.value}</span>;
}

function SourceDetails({ source, rounded }: { source: Source; rounded: boolean }) {
  const doc = source.document;
  return <>
    <section aria-label="Source and inclusion">
      <h3>Source &amp; checkpoint boundary</h3>
      <dl className="facts">
        <div><dt>Bundle</dt><dd>{doc.metadata.bundle_id}</dd></div>
        <div><dt>Source</dt><dd>{doc.metadata.source_id} / version {doc.metadata.source_version}</dd></div>
        <div><dt>Source cutoff</dt><dd>{doc.metadata.cutoff}</dd></div>
        <div><dt>Source timezone</dt><dd>{doc.metadata.source_timezone}</dd></div>
        <div><dt>Profile</dt><dd>{doc.metadata.profile_id}</dd></div>
        <div><dt>Fictional data assertion</dt><dd>{doc.metadata.fictional === true ? "Fictional / synthetic" : "Unverified"}</dd></div>
      </dl>
      <p><strong>Inclusion evidence: </strong><FactValue fact={doc.metadata.inclusion} /></p>
      <p className="subtle">Activity already included: {doc.metadata.included_activity_ids.join(", ") || "None declared"}. The checkpoint is not transaction replay.</p>
      <details><summary>Source assertions and coverage</summary>
        <ul>{doc.metadata.stipulations.map((text, index) => <li key={index}>{text}</li>)}</ul>
        <pre>{JSON.stringify({ accounts: doc.accounts, coverage: doc.coverage }, null, 2)}</pre>
      </details>
    </section>
    <section aria-label="Source lots">
      <h3>Lots <span className="count">{doc.lots.length}</span></h3>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Lots table"><table>
        <thead><tr><th>Lot / account</th><th>Security</th><th>Acquired</th><th>Quantity</th><th>Total adjusted basis (USD)</th></tr></thead>
        <tbody>{doc.lots.map((lot) => <tr key={lot.id}><th scope="row">{lot.id}<small>{lot.account_id}</small></th><td>{lot.security_id}</td><td><FactValue fact={lot.acquired} /></td><td><FactValue fact={lot.quantity} numeric rounded={rounded} /></td><td><FactValue fact={lot.basis} numeric rounded={rounded} /></td></tr>)}</tbody>
      </table></div>
      <p className="subtle">Source basis is shown as supplied, including any embedded fees. No basis reconstruction or eligibility determination is performed here.</p>
    </section>
    <section aria-label="Exact source values">
      <details><summary>Exact &amp; source values <span className="count">{source.source_values.length}</span></summary>
        <p className="subtle">Unrounded canonical text, original source text and source quantum. Display settings do not change these values.</p>
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Exact source values table"><table>
          <thead><tr><th>Source location</th><th>Exact canonical</th><th>Original text</th><th>Source quantum</th></tr></thead>
          <tbody>{source.source_values.map((value, index) => <tr key={index}><th scope="row">{locationText(value.path)}</th><td className="number">{value.exact.value}</td><td className="number">{value.exact.original_text}</td><td className="number">{value.exact.source_quantum}</td></tr>)}</tbody>
        </table></div>
      </details>
    </section>
  </>;
}

function InspectionView({ inspection, rounded }: { inspection: Inspection; rounded: boolean }) {
  const ready = inspection.readiness;
  return <>
    <section className="readiness" aria-label="Readiness and findings">
      <div className="section-heading"><h3>Data readiness</h3><span className={inspection.inspection_valid ? "badge" : "badge blocked"}>{inspection.inspection_valid ? "Inspection-valid" : "Not inspection-valid"}</span></div>
      <p>Inspection checks the supplied data. Financial planning remains unavailable.</p>
      <dl className="readiness-grid">{(["inspection", "basis", "valuation", "coverage"] as const).map((scope) => <div key={scope}><dt>{scope === "coverage" ? "Household coverage" : scope[0]!.toUpperCase() + scope.slice(1)}</dt><dd className={ready[scope] === "complete" ? "complete" : "attention"}>{ready[scope]}</dd></div>)}</dl>
      <h4>Planning blockers</h4><ul>{ready.planning_reasons.map((reason, index) => <li key={index}><code>{reason}</code></li>)}</ul>
      {inspection.findings.length > 0 && <><h4>Located reconciliation &amp; coverage findings</h4><ul className="finding-list">{inspection.findings.map((finding, index) => <li key={index}><strong>{finding.code}</strong> <span className="badge muted">{finding.blocking ? "Blocking" : "Diagnostic"}</span><small>{locationText(finding.path)}</small>{finding.reason !== null && <p>{finding.reason}</p>}</li>)}</ul></>}
      {inspection.further_findings && <p className="notice">Further findings exist. This bounded report is truncated.</p>}
    </section>
    <div className="metrics" aria-label="Checkpoint totals">
      <section><h3>Settled-cash NAV (USD)</h3><Value value={inspection.settled_cash_nav} rounded={rounded} /><p className="subtle">Holdings plus supplied settled cash</p></section>
      <section><h3>Total basis (USD)</h3><Value value={inspection.total_basis} rounded={rounded} /><p className="subtle">Supplied adjusted lot basis</p></section>
      <section><h3>Market minus basis (USD)</h3><Value value={inspection.market_minus_basis} rounded={rounded} /><p className="subtle">Snapshot difference; not investment return</p></section>
    </div>
    <section aria-label="Positions">
      <h3>Positions</h3><div className="table-scroll" tabIndex={0} role="region" aria-label="Positions table"><table>
        <thead><tr><th>Security / account</th><th>Position quantity</th><th>Lot quantity</th><th>Price (USD)</th><th>Value (USD)</th><th>Basis (USD)</th></tr></thead>
        <tbody>{inspection.positions.map((position, index) => <tr key={index}><th scope="row">{position.security_id}<small>{position.account_id}</small></th>{(["quantity", "lot_quantity", "price", "market_value", "basis"] as const).map((field) => <td key={field}><Value value={position[field]} rounded={rounded} /></td>)}</tr>)}</tbody>
      </table></div>
    </section>
    <section aria-label="Cash buckets">
      <h3>Cash buckets (USD)</h3><p className="subtle">Separate source facts. Available and unsettled cash are not added to settled-cash NAV.</p>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Cash table"><table>
        <thead><tr><th>Account</th><th>Settled</th><th>Available</th><th>Unsettled</th></tr></thead>
        <tbody>{inspection.cash.map((cash, index) => <tr key={index}><th scope="row">{cash.account_id}</th>{(["settled", "available", "unsettled"] as const).map((field) => <td key={field}><Value value={cash[field]} rounded={rounded} /></td>)}</tr>)}</tbody>
      </table></div>
    </section>
  </>;
}

function ReviewContent({ source, inspection, issues = [], furtherIssues = false, rounded }: {
  source: Source | null; inspection: Inspection | null; issues?: Preview["issues"]; furtherIssues?: boolean; rounded: boolean;
}) {
  return <>
    {issues.length > 0 && <section className="parser-errors" aria-label="Parser issues"><h3>Bundle could not be parsed</h3><p>The original bytes were retained as non-ready evidence.</p><ul className="finding-list">{issues.map((issue, index) => <li key={index}><strong>{issue.code}</strong><small>{locationText(issue.path)}{issue.offset !== null ? `; byte offset ${issue.offset}` : ""}{issue.path_truncated ? "; location truncated" : ""}</small></li>)}</ul>{furtherIssues && <p className="notice">Further issues exist. This bounded report is truncated.</p>}</section>}
    {inspection && <InspectionView inspection={inspection} rounded={rounded} />}
    {source && <SourceDetails source={source} rounded={rounded} />}
  </>;
}

function safeError(error: unknown, mutation = false): string {
  if (error instanceof ClientError && error.status === 401) return "The local session expired. Retry the read or retrieval to establish a new session.";
  if (mutation) return "The import action response is unresolved. It may have completed. Retry the same command or retrieve the preview and refresh current state before making another decision.";
  if (error instanceof ClientError && error.status === 404) return "No retained preview was found for that SHA-256.";
  if (error instanceof ClientError && error.status === 413) return "The selected file exceeds the 2 MiB import limit.";
  return "The local request could not be completed. Check the runtime and retry. No active-state change was requested.";
}

const outcomes: Record<Command["outcome"], string> = {
  committed: "Checkpoint activated. Financial planning remains unavailable.",
  duplicate: "Already activated evidence. No new activation occurred; an older checkpoint was not restored.",
  stale_generation: "Current state changed. Refresh current state, inspect both views and review again before issuing a new command.",
  preview_rejected: "This preview was rejected and cannot be activated.",
  preview_invalid: "This preview is not inspection-valid and cannot be activated. Review its located findings.",
  identity_review_required: "Portfolio or source identity requires review. Account switching and identity overrides are unavailable.",
  source_conflict: "Source facts conflict with retained accepted history. Correction acceptance is unavailable; retained evidence and current state are preserved.",
};

export function Review() {
  const [view, setView] = useState<"preview" | "current">("preview");
  const [current, setCurrent] = useState<Current | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [digest, setDigest] = useState("");
  const [rounded, setRounded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Reading current checkpoint...");
  const [error, setError] = useState<string | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [command, setCommand] = useState<CommitRequest | null>(null);
  const [receipt, setReceipt] = useState<Command | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const [refused, setRefused] = useState(false);
  const [rejectRetry, setRejectRetry] = useState<string | null>(null);
  const [resumeKey, setResumeKey] = useState("");
  const [resumeGeneration, setResumeGeneration] = useState("");
  const active = useRef(false);
  const session = useRef<ReturnType<typeof connect> | null>(null);
  function client() { return session.current ??= connect(); }
  async function perform(action: () => Promise<void>, mutation = false) {
    if (active.current) return;
    active.current = true; setBusy(true); setError(null);
    try { await action(); } catch (problem) {
      session.current = null;
      setMessage("Request incomplete. Refresh or retrieve before relying on this view.");
      setReviewed(false);
      setError(safeError(problem, mutation));
    } finally { active.current = false; setBusy(false); }
  }
  function refresh() { return perform(async () => {
    setReviewed(false);
    setCurrent(null); setMessage("Reading current checkpoint...");
    const result = await (await client()).current(); setCurrent(result);
    setMessage(`Current checkpoint read. Active generation: ${result.generation}.`);
  }); }
  useEffect(() => { void refresh(); }, []);
  async function stage() { await perform(async () => {
    if (!file || file.size > MAX_BYTES) { setError("Select a synthetic file of at most 2 MiB."); return; }
    setReviewed(false); setPreview(null); setView("preview"); setMessage("Staging original bytes for inspection...");
    const bytes = new Uint8Array(await file.arrayBuffer());
    const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map((byte) => byte.toString(16).padStart(2, "0")).join("");
    setDigest(hash);
    const result = await (await client()).stage(bytes); setPreview(result);
    setMessage("Preview retained for inspection. The active checkpoint was not changed.");
  }); }
  async function retrieve(event: React.FormEvent) {
    event.preventDefault(); await perform(async () => {
      setReviewed(false); setPreview(null); setView("preview"); setMessage("Retrieving retained preview...");
      setPreview(await (await client()).preview(digest)); setMessage("Retained preview retrieved. The active checkpoint was not changed.");
    });
  }
  async function reread() {
    // Invalidate both cached views first. A receipt remains visible if either read fails.
    const identity = preview?.receipt.raw_sha256;
    setCurrent(null); setPreview(null); setReviewed(false);
    const api = await client();
    if (identity) setPreview(await api.preview(identity));
    setCurrent(await api.current());
  }
  function commit(request: CommitRequest) { return perform(async () => {
    setCommand(request); setReceipt(null); setUncertain(true); setRefused(false); setReviewed(false);
    setMessage("Submitting the reviewed command. Do not assume an outcome until its receipt is available.");
    // A thrown/lost response retains this exact descriptor for an explicit retry.
    let result: Command;
    try { result = await (await client()).commit(request); } catch (problem) {
      if (problem instanceof ClientError && problem.status === 409) {
        setUncertain(false); setRefused(true);
        setMessage("Commit command refused. Restore its original recovery details or review again.");
        setError("This command key is bound to a different payload. It cannot be reused with a changed preview or expected generation.");
        return;
      }
      throw problem;
    }
    setReceipt(result); setUncertain(false);
    setCurrent(null);
    setMessage(`Recorded command outcome: ${result.outcome}. Reading present state separately...`);
    try {
      await reread();
      setMessage(`Recorded command outcome: ${result.outcome}. Present state read separately.`);
    } catch {
      session.current = null;
      setMessage(`Recorded command outcome: ${result.outcome}. Follow-up read incomplete.`);
      setError("The command receipt is recorded. A follow-up read failed. Retrieve the preview and refresh current state before reviewing again.");
    }
  }, true); }
  function reject(identity: string) { return perform(async () => {
    setRejectRetry(identity); setReviewed(false);
    setMessage("Rejecting this retained preview; active state is preserved.");
    const result = await (await client()).reject(identity);
    setRejectRetry(null);
    if (preview?.receipt.raw_sha256 === identity) setPreview(result);
    setMessage(`Preview ${result.state}. Original evidence remains retained; active state was not changed by rejection.`);
  }, true); }
  const canReview = !!preview && !!current && !uncertain && !rejectRetry;
  const canCommit = canReview && reviewed && preview.state !== "rejected" && preview.inspection?.inspection_valid === true;
  const resumeNumber = /^\d+$/.test(resumeGeneration) ? Number(resumeGeneration) : NaN;
  const canResume = !!preview && reviewed && !!current && !uncertain && !rejectRetry &&
    /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(resumeKey) && Number.isSafeInteger(resumeNumber) && resumeNumber >= 0;
  return <>
    <header className="page-header"><div><p className="eyebrow">PROSPER / SYNTHETIC WORKSPACE</p><h1>Import review</h1><p>Inspect the evidence before it becomes portfolio state.</p></div><span className="badge">Fictional data only</span></header>
    <div className="notice">Synthetic import review. Financial planning and trade approval are unavailable.</div>
    <section className="import-panel" aria-label="Stage a synthetic file">
      <div><h2>Stage a synthetic bundle</h2><p>Choose a fictional canonical JSON bundle. Never select real account data. Original bytes are retained locally; staging does not activate a checkpoint.</p></div>
      <div className="file-controls"><label htmlFor="bundle-file">Synthetic JSON file (up to 2 MiB)</label><input id="bundle-file" type="file" accept=".json,application/json" disabled={busy} onChange={(event) => {
        const selected = event.target.files?.[0] ?? null; setReviewed(false); setFile(selected); setPreview(null); setView("preview"); setError(selected && selected.size > MAX_BYTES ? "The selected file exceeds the 2 MiB import limit." : null);
      }} /><button disabled={busy || !file || file.size > MAX_BYTES} onClick={() => void stage()}>Stage preview</button></div>
      <details className="retrieval"><summary>Retrieve a retained preview</summary><form onSubmit={(event) => void retrieve(event)}><label htmlFor="preview-digest">Original-byte SHA-256</label><input id="preview-digest" value={digest} onChange={(event) => setDigest(event.target.value)} autoComplete="off" spellCheck={false} disabled={busy} maxLength={64} /><button className="secondary" disabled={busy || !/^[0-9a-f]{64}$/.test(digest)}>Retrieve preview</button></form><p className="subtle">If an upload response is interrupted, use its computed digest here to check whether it was retained. No automatic upload retry occurs.</p></details>
    </section>
    <div className="review-toolbar"><div className="view-buttons" role="group" aria-label="Review view"><button className={view === "preview" ? "selected" : "secondary"} aria-pressed={view === "preview"} onClick={() => setView("preview")}>Selected preview</button><button className={view === "current" ? "selected" : "secondary"} aria-pressed={view === "current"} onClick={() => setView("current")}>Current checkpoint</button></div><button className="secondary" disabled={busy} onClick={() => void refresh()}>Refresh current state</button></div>
    <p className="current-indicator">Last read active generation: <strong>{current ? current.generation : "Unavailable"}</strong>. Preview and current state are separate.</p>
    <p role="status" aria-label="Review status" className="review-status">{busy ? "Working. " : ""}{message}</p>
    {error && <p role="alert" className="error">{error}</p>}
    {(command || rejectRetry) && <section aria-label="Last lifecycle command" className="lifecycle">
      <h2>Last lifecycle command</h2>
      {command && <>
        <p className="subtle">Keep these recovery details before reloading. This command always refers to its original preview and generation, even when a different preview is selected.</p>
        <dl className="facts"><div><dt>Command key</dt><dd>{command.command_key}</dd></div><div><dt>Expected generation</dt><dd>{command.expected_generation}</dd></div><div><dt>Command preview SHA-256</dt><dd>{command.preview_sha256}</dd></div></dl>
        {receipt ? <div role="status" aria-label="Command receipt">
          <h3>Recorded outcome: {receipt.outcome}</h3><p>{outcomes[receipt.outcome]}</p>
          <p>Observed generation at command: {receipt.generation}. Original activation generation: {receipt.activation_generation ?? "None"}.</p>
          <p className="subtle">Recorded at {receipt.recorded_at}. This receipt is the original durable result, not a statement of current active state.</p>
        </div> : <p className="notice">{refused ? "Command refused because its key is bound to different recovery details. Restore the original preview and expected generation, or review again for a new command." : "Outcome unresolved. Do not create a replacement command until this one is resolved."}</p>}
        <button className="secondary" disabled={busy || !!rejectRetry} onClick={() => void commit(command)}>Retry same commit command</button>
      </>}
      {rejectRetry && <><p className="notice">Rejection response unresolved for <code>{rejectRetry}</code>. A concurrent commit may prevent rejection. Retrieve that preview to inspect its lifecycle.</p><button className="secondary" disabled={busy} onClick={() => void reject(rejectRetry)}>Retry same rejection</button><button className="secondary" disabled={busy} onClick={() => { setRejectRetry(null); setReviewed(false); setPreview(null); setCurrent(null); setMessage("Retrieve the preview and refresh current state before reviewing again."); }}>Resolve by fresh reads</button></>}
    </section>}
    <div className="display-controls"><label><input type="checkbox" checked={rounded} onChange={(event) => setRounded(event.target.checked)} /> Round displayed numeric values to 2 decimals</label><p className="subtle">Display only; ties round to even. Exact canonical/source values remain unchanged and are available below.</p></div>
    <article aria-label={view === "preview" ? "Selected preview review" : "Current checkpoint review"} aria-busy={busy}>
      <div className="section-heading"><h2>{view === "preview" ? "Selected preview" : "Current checkpoint"}</h2>{view === "preview" && preview && <span className="badge muted">{preview.state}</span>}</div>
      {view === "preview" ? preview ? <>
        <div className="identity"><p><strong>Original-byte SHA-256</strong><code>{preview.receipt.raw_sha256}</code></p><p><strong>Recorded at</strong> {preview.recorded_at} / {preview.receipt.byte_length} bytes</p></div>
        <ReviewContent source={preview.source} inspection={preview.inspection} issues={preview.issues} furtherIssues={preview.further_issues} rounded={rounded} />
        <section aria-label="Review lifecycle actions" className="lifecycle">
          <h3>Review this import</h3>
          <p>Commit activates this checkpoint for synthetic inspection. Reject is terminal for these original bytes and retains the evidence. A committed preview cannot be rejected. Neither action approves trades or removes financial blockers.</p>
          <p>Review the selected preview and the separately read current checkpoint before choosing an action. Expected generation for a new commit: <strong>{current?.generation ?? "Unavailable; refresh current state"}</strong>.</p>
          {preview.state === "rejected" && <p className="notice">Rejected at {preview.rejected_at}. These original bytes cannot be activated.</p>}
          {!preview.inspection?.inspection_valid && <p className="notice">Commit unavailable: this preview is not inspection-valid. Its original evidence can be rejected.</p>}
          <label className="review-check"><input type="checkbox" checked={reviewed} disabled={busy || !canReview} onChange={(event) => setReviewed(event.target.checked)} /> I reviewed this preview, its readiness reasons and the current checkpoint.</label>
          <div className="lifecycle-buttons"><button disabled={busy || !canCommit} onClick={() => {
            if (current && preview && canCommit) void commit({ schema_version: "synthetic-import-api-v1", preview_sha256: preview.receipt.raw_sha256, command_key: crypto.randomUUID(), expected_generation: current.generation });
          }}>Commit reviewed preview</button><button className="secondary" disabled={busy || !canReview || !reviewed || preview.state !== "staged"} onClick={() => void reject(preview.receipt.raw_sha256)}>Reject reviewed preview</button></div>
          <details className="resume-command"><summary>Resume a commit after reload</summary><p className="subtle">Retrieve the original preview, inspect current state and enter the saved command key and original expected generation. This explicitly retries that exact payload. If it never reached the runtime, it may execute now; it does not silently use the current generation.</p><label>Saved command key<input value={resumeKey} maxLength={128} disabled={busy} onChange={(event) => setResumeKey(event.target.value)} /></label><label>Original expected generation<input value={resumeGeneration} inputMode="numeric" maxLength={16} disabled={busy} onChange={(event) => setResumeGeneration(event.target.value)} /></label><button className="secondary" disabled={busy || !canResume} onClick={() => void commit({ schema_version: "synthetic-import-api-v1", preview_sha256: preview.receipt.raw_sha256, command_key: resumeKey, expected_generation: resumeNumber })}>Resume saved commit command</button></details>
        </section>
      </> : <section className="empty"><h3>No preview selected</h3><p>Stage a synthetic file or retrieve an existing preview by digest. This does not replace the active checkpoint.</p></section>
      : current?.checkpoint ? <>
        <div className="identity"><p><strong>Active generation {current.generation}</strong> / checkpoint sequence {current.checkpoint.sequence}</p><p><strong>Recorded at</strong> {current.checkpoint.recorded_at}</p><code>{current.checkpoint.receipt.raw_sha256}</code></div>
        <ReviewContent source={current.checkpoint.source} inspection={current.checkpoint.inspection} rounded={rounded} />
      </> : <section className="empty"><h3>{current ? "No active checkpoint" : "Current state unavailable"}</h3><p>{current ? "Generation zero. A staged preview alone does not activate a portfolio." : "Refresh current state to obtain a new read."}</p></section>}
    </article>
  </>;
}
