import { useRef, useState } from "react";
import { ClientError, connect } from "./client";
import { DetailsPanel, ExactValue, Help, Issues, SecurityName } from "./ui";
import type { Current, ModeledUpload, ModeledResult, ModeledDiagnostic } from "./client";

export type InputsAction = { kind: "modeled-inputs"; body: ModeledDiagnostic };

export function RiskSettingsView({ profile }: {profile: ModeledUpload["bundle"]["profile"]}) {
  return <article aria-label="Effective risk settings" className="risk-summary"><div className="section-heading"><h3>{profile.preset?"Standard R1":"Custom risk settings"}</h3><Help label="About the risk estimate">An exploratory estimate of benchmark-relative risk. It is not calibrated or approved for financial use. Missing required inputs still prevent a calculation.</Help></div><p>{profile.horizon_sessions}-session projection - {profile.require_full_window_validation?"Full-window history required":"Supplied history validation setting"}</p><DetailsPanel title="Risk settings and assumptions" label="View model details"><p>Exploratory IDR-DCC-NL; unqualified. {profile.lookback_sessions} required sessions, minimum {profile.minimum_history_sessions}; {profile.horizon_sessions}-session projection; annualization {profile.annualization_sessions}.</p><p>Profile {profile.model?.identity??"Unknown"}; f {profile.model?.f??"Unknown"}, a3 {profile.model?.a3??"Unknown"}, kappa {profile.model?.kappa??"Unknown"}.</p><p>Preset: {profile.preset?.identity??"Supplied settings"}. Explicit overrides: {Object.keys(profile.preset?.overrides??{}).length?JSON.stringify(profile.preset?.overrides):"None"}.</p><p>Supplied maximum ages (days): marks {profile.max_mark_age_days}, snapshot {profile.max_snapshot_age_days}, benchmark {profile.max_benchmark_age_days}, history {profile.max_history_age_days}. Supplied universe bound: {profile.maximum_universe_size}.</p><pre>{JSON.stringify(profile,null,2)}</pre></DetailsPanel></article>;
}

export function InputsView({ result, label = "Modeled input coverage", showIssues=true }: { result: ModeledResult; label?: string; showIssues?:boolean }) {
  return <article aria-label={label}>
    <h3>{result.software_inputs_complete?"Inputs ready for exploratory calculation":"Input review needs attention"}</h3>
    <p>{result.security_ids.length} retained securities - {result.sessions.length} required sessions<Help label="About input coverage">Every retained security needs compatible complete inputs. Input coverage does not establish independent model or financial acceptance.</Help></p>
    {result.sleeve&&<section aria-label="Modeled sleeve review"><h4>Holdings included in this analysis</h4><p>{result.sleeve.decisions.length} names reviewed; {result.sleeve.decisions.filter(d=>d.excluded).length} excluded for inadequate history. Excluded holdings create no spendable cash and cannot be traded.</p>
      {[result.sleeve.portfolio,result.sleeve.benchmark].map(c=>c&&<div key={c.scope} className="coverage-summary"><strong>{c.scope==="portfolio"?"Portfolio":"Benchmark"} exclusion coverage</strong><p>{c.aggregate_excluded_bps===null?"Coverage unknown":`${(c.aggregate_excluded_bps/100).toLocaleString(undefined,{maximumFractionDigits:2})}% excluded`}{c.aggregate_highlight?" - review warning: above 1%":""}. {c.unknown_value_keys.length} unknown original values. Valued {c.valuation_date}.</p>{c.names.filter(n=>n.highlight).map(n=><p className="attention" key={n.key}>{n.key}: {n.excluded_bps??"Unknown"} bps excluded - above 0.10%.</p>)}<DetailsPanel title={`${c.scope} original-value exclusion coverage`}><p>{c.denominator_scope}. Reference USD {c.reference_value_usd.value??`Unknown: ${c.reference_value_usd.reason}`}; known excluded USD {c.excluded_known_value_usd}.</p><p>Aggregate {c.aggregate_excluded_bps??"Unknown"} bps; strict thresholds: 10 bps per name / 100 bps aggregate.</p><ul>{c.names.filter(n=>n.excluded).map(n=><li key={n.key}>{n.key}: USD {n.value_usd.value??`Unknown: ${n.value_usd.reason}`}; {n.excluded_bps??"Unknown"} bps. {n.locators.join(", ")}</li>)}</ul></DetailsPanel></div>)}
      <DetailsPanel title="History decisions" label="View included and excluded holdings"><div className="table-scroll"><table><caption>History decisions</caption><thead><tr><th>Security</th><th>Membership</th><th>Reasons</th></tr></thead><tbody>{result.sleeve.decisions.map(d=><tr key={d.security_id}><th><SecurityName id={d.security_id}/><small>{d.roles.join(", ")}</small></th><td>{d.excluded?"Excluded":"Retained"}</td><td>{d.issue_codes.length?d.issue_codes.map(v=>v.replaceAll("_"," ")).join(", "):"No located history issue"}</td></tr>)}</tbody></table></div><details><summary>Source details</summary><pre>{JSON.stringify(result.sleeve.decisions,null,2)}</pre></details></DetailsPanel>
    </section>}
    {showIssues&&<Issues issues={result.issues}/>}
    <DetailsPanel title="Complete modeled union" label="View security prices and weights"><div className="table-scroll"><table><caption>Complete modeled union</caption><thead><tr><th>Security / role</th><th>Held shares</th><th>Benchmark weight</th><th>Price (USD)</th><th>Sector / industry</th></tr></thead><tbody>{result.members.map(m=><tr key={m.security_id}><th><SecurityName id={m.security_id}/><small>{m.roles.join(", ")}</small></th><td><ExactValue value={m.held_quantity}/></td><td><ExactValue value={m.benchmark_weight} kind="weight"/></td><td><ExactValue value={m.mark}/></td><td>{m.sector??"Unknown"} / {m.industry??"Unknown"}</td></tr>)}</tbody></table></div></DetailsPanel>
    <DetailsPanel title="Input sources and assumptions" label="Source details and limitations"><p>OHLC/IDR inputs: {result.innovation_inputs_available?"available for exploratory calculations":"unavailable"}. {result.return_cell_count} required return cells; {result.unavailable_return_count} unavailable.</p><pre>{JSON.stringify({sessions:result.sessions,required_sources:result.required_sources,exclusions:result.exclusions},null,2)}</pre><ul>{result.warnings.map((warning,i)=><li key={i}>{warning}</li>)}</ul></DetailsPanel>
  </article>;
}

export function InputsControls({ current, disabled, api, onMutate }: {
  current: Current | null; disabled: boolean; api: () => ReturnType<typeof connect>;
  onMutate: (action: InputsAction) => void;
}) {
  const [upload, setUpload] = useState<ModeledUpload | null>(null);
  const [result, setResult] = useState<ModeledResult | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<ModeledUpload | null>(null);
  const [overrides, setOverrides] = useState("{}");
  const attempt = useRef(0);
  const revision = useRef(current?.revision); revision.current = current?.revision;
  const suppliedProfileComplete = source !== null && ["variant", "model", "model_reference", "lookback_sessions", "minimum_history_sessions", "horizon_sessions", "annualization_sessions", "require_full_window_validation"].every(key => key in source.bundle.profile);
  async function read(raw: string, mode: "standard" | "supplied" | "saved" = "standard", explicit = "{}") {
    const id = ++attempt.current, expectedRevision = revision.current;
    setBusy(true); setError(null); setReviewed(false); setResult(null); setUpload(null);
    try {
      const client = await api();
      // Send original JSON through the protected decoder before parsing it locally.
      const prepared = mode === "standard" ? await client.prepareRiskPreset(raw, explicit) : null;
      const value = await client.previewInputs(prepared ? JSON.stringify(prepared) : raw);
      const original = JSON.parse(raw) as ModeledUpload;
      if (id !== attempt.current) return;
      if (revision.current !== expectedRevision) {setError("Inputs changed while the risk settings were being prepared. Recheck the current inputs.");return;}
      setSource(original); setUpload(prepared ?? original); setResult(value);
      setOverrides(JSON.stringify((prepared ?? original).bundle.profile.preset?.overrides ?? {}, null, 2));
    } catch (problem) {
      if (id === attempt.current) setError(problem instanceof ClientError && [400, 422].includes(problem.status ?? 0) ? "Input/profile file or overrides are invalid. Check current fields, source bytes, profile consistency and checksums." : "Input review failed. Select a current snapshot and refresh the workspace before retrying.");
    } finally { if (id === attempt.current) setBusy(false); }
  }
  async function reuse() {
    const id = ++attempt.current, expectedRevision = revision.current;
    setBusy(true); setReviewed(false); setResult(null); setUpload(null); setError(null);
    try {
      const client = await api(), catalog = await client.catalog();
      for (const identity of [...catalog.runs].reverse()) {
        const saved = await client.run(identity);
        if (id !== attempt.current || revision.current !== expectedRevision) return;
        const request = saved.inputs?.modeled_request as {bundle?: ModeledUpload["bundle"]} | undefined;
        if (saved.model_version === "modeled-inputs-v1" && request?.bundle) {
          await read(JSON.stringify({bundle:request.bundle,sources:[]}), "saved"); return;
        }
      }
      setError("No saved input configuration is available. Import one reviewed configuration first.");
    } catch { if (id === attempt.current) setError("Saved input configuration could not be loaded."); }
    finally { if (id === attempt.current) setBusy(false); }
  }
  return <section aria-label="Complete modeled inputs">
    <h2>Complete modeled inputs and profile</h2><p>Review the full held, selected-benchmark and candidate union with explicit identities, marks, taxonomy, required history, model profile and investor controls. Missing facts remain located blockers; no names or missing returns are silently removed.</p>
    <p>Standard R1 is selected for new uploads: 1,260 sessions, a 21-session projection and annualization 252. End-of-day source dates and the supplied completed-session cutoff remain explicit; preparation does not create missing history or marks.</p>
    <button disabled={disabled || busy} onClick={()=>{void reuse();}}>Reuse saved input configuration</button>
    <label>Modeled input/profile JSON<input type="file" accept=".json" disabled={disabled || busy} onChange={e => { const id=++attempt.current; setUpload(null); setResult(null); setSource(null); setReviewed(false); setError(null); const file=e.target.files?.[0]; if(file) { if(file.size>16*1024*1024) setError("Input/profile file exceeds 16 MiB."); else {setBusy(true);void file.text().then(raw=>{if(id===attempt.current) return read(raw);}).catch(()=>{if(id===attempt.current){setBusy(false);setError("Input/profile file could not be read.");}});} } }} /></label>
    {upload && <RiskSettingsView profile={upload.bundle.profile} />}
    <details><summary>Advanced settings</summary>
      <p>Optional estimator overrides remain subject to all input and R1 fit checks. Unsupported fit settings produce an unavailable result. Source facts, investor limits and funding are retained.</p>
      <label>Risk parameter overrides JSON<textarea value={overrides} disabled={disabled || busy} onChange={e=>{setOverrides(e.target.value);setReviewed(false);setResult(null);setUpload(null);}} /></label>
      <button disabled={disabled || busy || !source} onClick={()=>{try{JSON.parse(overrides);void read(JSON.stringify(source),"standard",overrides);}catch{setError("Risk overrides are invalid JSON.");}}}>Apply standard preset and overrides</button>
      <button disabled={disabled || busy || !suppliedProfileComplete} onClick={()=>{if(source)void read(JSON.stringify({...source,bundle:{...source.bundle,profile:{...source.bundle.profile,preset:null}}}),"supplied");}}>Use supplied risk settings</button>
      {source && !suppliedProfileComplete && <p>The upload omits estimator settings. Use the standard preset or explicit overrides above.</p>}
      <p>Override keys: model (identity, f, a3, kappa), lookback_sessions, minimum_history_sessions, horizon_sessions, annualization_sessions, require_full_window_validation.</p>
    </details>
    {upload && <details><summary>Review supplied profile, limits and source facts</summary><pre>{JSON.stringify({bundle:upload.bundle,source_digests:upload.sources.map(s=>s.sha256)},null,2)}</pre></details>}
    {result && <InputsView result={result} />}
    {upload && result && <><label><input type="checkbox" checked={reviewed} disabled={disabled || busy} onChange={e=>setReviewed(e.target.checked)} />I reviewed the complete union, source coverage, profile and investor settings</label><button disabled={disabled || busy || !reviewed || !current?.snapshot_id} onClick={()=>onMutate({kind:"modeled-inputs",body:{...upload,run_id:crypto.randomUUID(),expected_revision:result.input_revision,as_of:new Date().toISOString()}})}>Save modeled input diagnostics</button><button disabled={disabled || busy} onClick={()=>{void read(JSON.stringify(upload),"saved");}}>Recheck current modeled inputs</button></>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
