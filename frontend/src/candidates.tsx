import { useEffect, useState } from "react";
import { connect } from "./client";
import type { CandidateStart, CandidateOutput, Current, Run } from "./client";

export type CandidateAction = {kind:"candidate-start";body:CandidateStart}|{kind:"candidate-cancel";body:{run_id:string}};
const money = (value:number) => value.toLocaleString(undefined,{style:"currency",currency:"USD"});
export function CandidateView({run}:{run:Run}) {
  if(run.model_version!=="candidate-workflow-v1") return null;
  if(run.status==="running") return <article aria-label="Candidate progress"><h3>Candidate calculation</h3><p>Phase: {String(run.outputs?.phase ?? "starting")}; checked states: {String(run.outputs?.states ?? 0)}.</p><p>{run.outputs?.cancel_requested===true ? "Cancellation requested; waiting for worker isolation." : "Running in a bounded local worker."}</p></article>;
  const output=run.outputs as unknown as CandidateOutput;
  const search=output.search;
  return <article aria-label="Checked candidate result"><h3>Dated exploratory candidate result</h3><p>Outcome: {output.outcome}. Financial-use authorization: unavailable.</p>
    <ul>{output.issues.map((v,i)=><li key={i}>{v}</li>)}</ul>
    {search && <><p>Search: {search.outcome}; stopping: {search.stopping}; {search.domain_states === null ? `${search.evaluated_states} proposals checked; domain not enumerated` : `${search.evaluated_states} / ${search.domain_states} states`}; {search.unresolved_states} unresolved.</p><p>Method: {search.method === "deterministic-loss-prefix-repair-v1" ? "Bounded proposal and repair (experimental)" : "Tiny exhaustive reference"}. {search.candidates.length} checked tradeoff points retained.</p><p>Baseline: {search.baseline.feasible ? "passes selected limits" : "breaches limits or has unavailable checks"}; {search.baseline.blockers.join("; ")}</p>
      {search.best?.metrics ? <><p>Checked whole-share incumbent; unqualified estimate.</p><dl className="facts"><div><dt>Price/basis loss before wash adjustments</dt><dd>{money(search.best.metrics.price_loss)}</dd></div><div><dt>Modeled cost</dt><dd>{money(search.best.metrics.modeled_cost)}</dd></div><div><dt>Final sleeve cash / NAV</dt><dd>{money(search.best.metrics.final_cash)} / {money(search.best.metrics.final_nav)}</dd></div><div><dt>Annual tracking error</dt><dd>{(search.best.metrics.tracking_error*100).toFixed(4)}%</dd></div></dl><ul>{search.best.orders.sales.map(s=><li key={s.lot_id}>Sell {s.shares} whole shares from lot {s.lot_id}</li>)}{search.best.orders.buys.map(b=><li key={b.security_id}>Buy {b.shares} whole shares of {b.security_id}</li>)}</ul><p>Retained security order: {search.inputs.risk.security_ids.join(", ")}. Final quantities: {search.best.metrics.final_quantities.join(", ")}.</p></> : <p>No independently checked positive-loss candidate is available.</p>}
      <p>Risk cutoff {search.inputs.risk.as_of}; analysis date {search.inputs.settings.analysis_date}; {String(output.risk?.horizon ?? "unavailable")}-session forecast annualized at {search.inputs.risk.annualization_sessions} sessions per year.</p><ul>{search.exclusions.map((v,i)=><li key={i}>{v}</li>)}</ul></>}
    <ul>{output.warnings.map((v,i)=><li key={i}>{v}</li>)}{search?.warnings.map((v,i)=><li key={`s${i}`}>{v}</li>)}</ul>
  </article>;
}

export function CandidateControls({current,disabled,api,onMutate,saved,onRead,onFinished}:{
  current:Current|null;disabled:boolean;api:()=>ReturnType<typeof connect>;
  onMutate:(action:CandidateAction)=>void;saved:Run|null;onRead:(run:Run)=>void;onFinished:()=>Promise<void>;
}) {
  const [document,setDocument]=useState<CandidateStart|null>(null);
  const [reviewed,setReviewed]=useState(false);
  const [error,setError]=useState<string|null>(null);
  function edit(value:CandidateStart) {setDocument(value);setReviewed(false);setError(null);}
  function editInteger(raw:string,change:(value:number)=>CandidateStart) {
    if(!/^[0-9]+$/.test(raw) || !Number.isSafeInteger(Number(raw))) {setReviewed(false);setError("Enter an explicit whole-number setting. Zero must be entered explicitly for an excluded domain.");return;}
    edit(change(Number(raw)));
  }
  useEffect(()=>setReviewed(false),[current?.revision,saved?.id]);
  useEffect(()=>{
    if(saved?.model_version!=="candidate-workflow-v1" || saved.status!=="running")return;
    let live=true;let reading=false;
    const timer=setInterval(()=>{if(reading)return;reading=true;void api().then(c=>c.run(saved.id)).then(async run=>{if(live){onRead(run);if(run.status!=="running")await onFinished();}}).catch(()=>{if(live)setError("Candidate progress could not be read. Refresh the workspace and reopen the saved run.");}).finally(()=>{reading=false;});},500);
    return ()=>{live=false;clearInterval(timer);};
  },[saved?.id,saved?.status]);
  return <section aria-label="Candidate calculation"><h2>Bounded exploratory candidate calculation</h2><p>Use a saved current modeled-input run and explicitly reviewed cost/search controls. Risk is fitted from its retained full history; supplied covariance files are not accepted here. Results remain conditional and financially unauthorized.</p>
    <label>Candidate controls JSON<input type="file" accept=".json" disabled={disabled} onChange={event=>{setDocument(null);setReviewed(false);setError(null);const file=event.target.files?.[0];if(file)void(async()=>{try{if(file.size>64*1024)throw Error();const value=JSON.parse(await file.text()) as CandidateStart;if(typeof value.input_run_id!=="string" || typeof value.controls!=="object" || !value.controls || Array.isArray(value.controls) || !value.controls.sale_bounds || Array.isArray(value.controls.sale_bounds) || typeof value.controls.sale_bounds!=="object" || !value.controls.buy_bounds || Array.isArray(value.controls.buy_bounds) || typeof value.controls.buy_bounds!=="object" || [value.controls.max_cost,value.controls.buy_fee_per_security_order,value.controls.buy_premium_bps].some(v=>typeof v!=="string") || [value.controls.max_states,value.controls.timeout_seconds,value.controls.max_candidates,...Object.values(value.controls.sale_bounds),...Object.values(value.controls.buy_bounds)].some(v=>!Number.isSafeInteger(v)))throw Error();setDocument(value);}catch{setError("Candidate controls file is invalid or exceeds 64 KiB.");}})();}} /></label>
    {saved?.model_version==="candidate-workflow-v1" && !!saved.inputs?.candidate_command && <button disabled={disabled} onClick={()=>edit({...saved.inputs!.candidate_command as unknown as CandidateStart,as_of:new Date().toISOString()})}>Edit saved candidate controls</button>}
    {document && <><fieldset disabled={disabled}><legend>Candidate run controls</legend>
      <p>Changes create a new fitted and checked candidate run. Risk, cash and exposure limits belong to the selected modeled-input run; change and review those inputs first when needed.</p>
      <label>Candidate input run ID<input value={document.input_run_id} onChange={e=>edit({...document,input_run_id:e.target.value})}/></label>
      <label>Maximum modeled cost USD<input value={document.controls.max_cost} onChange={e=>edit({...document,controls:{...document.controls,max_cost:e.target.value}})}/></label>
      <label>Buy fee per security order USD<input value={document.controls.buy_fee_per_security_order} onChange={e=>edit({...document,controls:{...document.controls,buy_fee_per_security_order:e.target.value}})}/></label>
      <label>Buy premium basis points<input value={document.controls.buy_premium_bps} onChange={e=>edit({...document,controls:{...document.controls,buy_premium_bps:e.target.value}})}/></label>
      <label>Maximum checked states or proposals<input type="number" min="1" max="100000" step="1" value={document.controls.max_states} onChange={e=>editInteger(e.target.value,value=>({...document,controls:{...document.controls,max_states:value}}))}/></label>
      <label>Candidate timeout seconds<input type="number" min="1" max="300" step="1" value={document.controls.timeout_seconds} onChange={e=>editInteger(e.target.value,value=>({...document,controls:{...document.controls,timeout_seconds:value}}))}/></label>
      <label>Maximum retained candidate points<input type="number" min="1" max="5" step="1" value={document.controls.max_candidates} onChange={e=>editInteger(e.target.value,value=>({...document,controls:{...document.controls,max_candidates:value}}))}/></label>
      <details><summary>Edit declared sale and buy domains</summary>{Object.entries(document.controls.sale_bounds).map(([id,bound])=><label key={id}>Sale bound {id}<input type="number" min="0" max="10000" step="1" value={bound} onChange={e=>editInteger(e.target.value,value=>({...document,controls:{...document.controls,sale_bounds:{...document.controls.sale_bounds,[id]:value}}}))}/></label>)}{Object.entries(document.controls.buy_bounds).map(([id,bound])=><label key={id}>Buy bound {id}<input type="number" min="0" max="10000" step="1" value={bound} onChange={e=>editInteger(e.target.value,value=>({...document,controls:{...document.controls,buy_bounds:{...document.controls.buy_bounds,[id]:value}}}))}/></label>)}</details>
    </fieldset><details><summary>Review candidate controls and saved input reference</summary><pre>{JSON.stringify(document,null,2)}</pre></details><label><input type="checkbox" disabled={disabled} checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/>I reviewed the saved inputs, costs, funding and bounded search controls</label><button disabled={disabled||!reviewed||!current?.snapshot_id||error!==null} onClick={()=>onMutate({kind:"candidate-start",body:{...document,run_id:crypto.randomUUID(),expected_revision:current!.revision}})}>Calculate exploratory candidate</button></>}
    {saved?.model_version==="candidate-workflow-v1" && saved.status==="running" && <><button disabled={disabled} onClick={()=>onMutate({kind:"candidate-cancel",body:{run_id:saved.id}})}>Cancel candidate calculation</button><button disabled={disabled} onClick={()=>onMutate({kind:"candidate-start",body:saved.inputs!.candidate_command as unknown as CandidateStart})}>Resume or retry saved candidate</button></>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
