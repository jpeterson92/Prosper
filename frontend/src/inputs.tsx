import { useState } from "react";
import { ClientError, connect } from "./client";
import type { Current, ModeledUpload, ModeledResult, ModeledDiagnostic } from "./client";

export type InputsAction = { kind: "modeled-inputs"; body: ModeledDiagnostic };

export function InputsView({ result, label = "Modeled input coverage" }: { result: ModeledResult; label?: string }) {
  return <article aria-label={label}>
    <h3>{result.software_inputs_complete ? "Complete input coverage" : "Modeled inputs have blockers"}</h3>
    <p>{result.security_ids.length} retained securities; {result.sessions.length} required sessions. Ordered union: {result.security_ids.join(", ")}.</p>
    <p>OHLC/IDR inputs: {result.innovation_inputs_available ? "available for exploratory calculations" : "unavailable"}. Risk metrics and validated suggestions remain unavailable.</p>
    <div className="table-scroll" tabIndex={0}><table><caption>Complete modeled union</caption><thead><tr><th>Security / role</th><th>Held quantity</th><th>Benchmark weight</th><th>Mark (USD)</th><th>Sector / industry</th></tr></thead><tbody>{result.members.map(member => <tr key={member.security_id}><th>{member.security_id}<small>{member.roles.join(", ")}</small></th><td>{member.held_quantity ?? "Unknown"}</td><td>{member.benchmark_weight ?? "Unavailable"}</td><td>{member.mark ?? "Unknown"}</td><td>{member.sector ?? "Unknown"} / {member.industry ?? "Unknown"}</td></tr>)}</tbody></table></div>
    <ul>{result.issues.map((issue, i) => <li key={i}><strong>{issue.scope} / {issue.security_id ?? "profile"} / {issue.code}</strong>: {issue.reason} ({issue.locator})</li>)}</ul>
    <p>{result.return_cell_count} required return cells; {result.unavailable_return_count} unavailable. Missing cells remain blockers.</p><details><summary>Required sessions and source/exclusion details</summary><pre>{JSON.stringify({sessions:result.sessions,required_sources:result.required_sources,exclusions:result.exclusions},null,2)}</pre></details>
    <ul>{result.warnings.map((warning,i) => <li key={i}>{warning}</li>)}</ul>
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
  async function read(raw: string) { setBusy(true); setError(null); try { const value = await (await api()).previewInputs(raw); setUpload(JSON.parse(raw) as ModeledUpload); setResult(value); } catch (problem) { setError(problem instanceof ClientError && problem.status === 422 ? "Input/profile file is invalid. Check current fields, source bytes and checksums." : "Input review failed. Select a current snapshot and refresh the workspace before retrying."); } finally {setBusy(false);} }
  return <section aria-label="Complete modeled inputs">
    <h2>Complete modeled inputs and profile</h2><p>Review the full held, selected-benchmark and candidate union with explicit identities, marks, taxonomy, required history, model profile and investor controls. Missing facts remain located blockers; no names or missing returns are silently removed.</p>
    <button disabled={disabled || busy} onClick={()=>{void(async()=>{try{const client=await api();const catalog=await client.catalog();for(const id of [...catalog.runs].reverse()){const saved=await client.run(id);const request=saved.inputs?.modeled_request as {bundle?: ModeledUpload["bundle"]} | undefined;if(saved.model_version==="modeled-inputs-v1" && request?.bundle){setReviewed(false);await read(JSON.stringify({bundle:request.bundle,sources:[]}));return;}}setError("No saved input configuration is available. Import one reviewed configuration first.");}catch{setError("Saved input configuration could not be loaded.");}})();}}>Reuse saved input configuration</button>
    <label>Modeled input/profile JSON<input type="file" accept=".json" disabled={disabled || busy} onChange={e => { setUpload(null); setResult(null); setReviewed(false); const file=e.target.files?.[0]; if(file) { if(file.size>16*1024*1024) setError("Input/profile file exceeds 16 MiB."); else void file.text().then(raw=>read(raw)).catch(()=>setError("Input/profile file could not be read.")); } }} /></label>
    {upload && <details><summary>Review supplied profile, limits and source facts</summary><pre>{JSON.stringify({bundle:upload.bundle,source_digests:upload.sources.map(s=>s.sha256)},null,2)}</pre></details>}
    {result && <InputsView result={result} />}
    {upload && <><label><input type="checkbox" checked={reviewed} disabled={disabled || busy} onChange={e=>setReviewed(e.target.checked)} />I reviewed the complete union, source coverage, profile and investor settings</label><button disabled={disabled || busy || !reviewed || !current?.snapshot_id} onClick={()=>onMutate({kind:"modeled-inputs",body:{...upload,run_id:crypto.randomUUID(),expected_revision:result!.input_revision,as_of:new Date().toISOString()}})}>Save modeled input diagnostics</button><button disabled={disabled || busy} onClick={()=>{setReviewed(false);void read(JSON.stringify(upload));}}>Recheck current modeled inputs</button></>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
