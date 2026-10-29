import { DetailsPanel, Help } from "./ui";
import {useEffect,useRef,useState} from "react";
import {ClientError} from "./client";
import type {Current,Preview,HoldingsMappingRequest,connect} from "./client";

export function HoldingsMapping({current,preview,disabled,api,onPreview}:{current:Current|null;preview:Preview;disabled:boolean;api:()=>ReturnType<typeof connect>;onPreview:(preview:Preview)=>void}) {
  const [compatible,setCompatible]=useState<boolean|null>(null);
  useEffect(()=>{let live=true;setCompatible(null);const id=current?.settings.benchmark_run_id;if(typeof id!=="string")return;void api().then(c=>c.run(id)).then(run=>{if(live)setCompatible(run.outputs?.ticker==="IVV"&&run.outputs?.effective_date===preview.snapshot.source_as_of.slice(0,10));}).catch(()=>{if(live)setCompatible(false);});return()=>{live=false;};},[current?.revision,preview.id]);
  const [exclusions,setExclusions]=useState<Record<string,string>>({});
  const [pending,setPending]=useState<HoldingsMappingRequest|null>(null);
  const [busy,setBusy]=useState(false);const [error,setError]=useState<string|null>(null);
  const generation=useRef(0);
  useEffect(()=>{generation.current++;setPending(null);setBusy(false);setError(null);setExclusions({});return()=>{generation.current++;};},[current?.revision,preview.id]);
  const benchmark=current?.settings.benchmark_run_id;
  const selected=current?.snapshot_id===preview.id;
  const proof=preview.snapshot.holding_preparation;
  async function prepare(body:HoldingsMappingRequest){
    const token=++generation.current;setBusy(true);setError(null);setPending(body);
    try{const result=await (await api()).prepareHoldings(body);if(token===generation.current){setPending(null);onPreview(result);}}
    catch(problem){if(token===generation.current)setError(problem instanceof ClientError && problem.code==="holdings_mapping_fund_date_or_knowledge_invalid"?"This preparation requires IVV evidence and holdings from the same reporting date. No neighboring date or source was substituted.":problem instanceof ClientError && problem.code==="holdings_mapping_inputs_changed"?"The selected holdings or benchmark changed. Refresh the workspace before preparing again.":"Stock mappings could not be prepared. Use the original source-shaped snapshot and a supported selected IVV benchmark; original holdings remain selected.");}
    finally{if(token===generation.current)setBusy(false);}
  }
  const held=new Set([...preview.snapshot.lots,...preview.snapshot.positions].map(row=>row.security_id));
  const cash=new Set((preview.snapshot.cash_treatments??[]).map(row=>row.security_id));
  return <section aria-label="Holdings stock mapping"><h3>Prepare stock identities from your benchmark</h3>
    {compatible===false&&<p className="notice">Stock mapping needs a selected IVV benchmark from this holdings date. Your existing identities and benchmark are unchanged.</p>}
    <p>Confirm supported stock identities using your selected IVV benchmark. Tax classification and market history may still need review.<Help label="About stock identity mapping">The retained benchmark and holdings must share their reporting date. Exact tickers and names after case, whitespace and punctuation comparison must agree. Share-class punctuation is preserved. Mapping does not establish tax eligibility or complete history.</Help></p>
    {proof ? <><p>Prepared from IVV holdings dated {proof.benchmark_date}. {proof.rows.filter(r=>r.disposition==="mapped").length} mapped; {proof.rows.filter(r=>r.disposition==="preserved").length} supplied identities preserved; {proof.rows.filter(r=>r.disposition==="excluded").length} excluded; {proof.rows.filter(r=>r.disposition==="cash-treatment").length} cash-treated holdings preserved.</p><p>Review this complete result before selecting the staged snapshot. To change exclusions before selection, review the selected original snapshot and prepare again. A later import starts its own review.</p><DetailsPanel title="Holdings mapping decisions" label="View holding decisions"><ul>{proof.rows.map(row=><li key={row.source.id}>{row.source.ticker} / {row.source.name.value??"unknown name"}: {row.disposition.replaceAll("-"," ")} — {row.reason}</li>)}</ul></DetailsPanel><details><summary>Mapping source evidence</summary><p>Benchmark run: {proof.benchmark_run_id}; original snapshot: {proof.source_snapshot_id}; source SHA-256: {proof.benchmark_source_sha256}. Prepared {proof.recorded_at}.</p><ul>{proof.rows.map(row=><li key={row.source.id}>{row.source.ticker}: {row.security_id}; {row.source_refs.join("; ")}{row.benchmark_index===null?"":`; benchmark holdings row ${row.benchmark_index}`}</li>)}</ul></details></> : <>
      {!selected && <p>Select this reviewed source snapshot before preparing stock mappings.</p>}
      {typeof benchmark!=="string" && <p>Select a reviewed IVV benchmark to prepare supported stock identities.</p>}
      <details><summary>Advanced mapping exclusions</summary><p>Optionally exclude a source holding with a reason. Cash treatments are preserved separately; no manual mapping file is required for supported matches.</p>
        {preview.snapshot.securities.filter(row=>held.has(row.id)&&!cash.has(row.id)).map(row=><label key={row.id}>Exclusion reason for {row.ticker}<input disabled={disabled||busy||pending!==null} value={exclusions[row.id]??""} maxLength={256} onChange={event=>setExclusions({...exclusions,[row.id]:event.target.value})}/></label>)}
      </details>
      <button disabled={disabled||busy||pending!==null||!selected||typeof benchmark!=="string"||compatible!==true} onClick={()=>{if(current&&typeof benchmark==="string")void prepare({snapshot_id:preview.id,benchmark_run_id:benchmark,expected_revision:current.revision,recorded_at:new Date().toISOString(),exclusions:Object.fromEntries(Object.entries(exclusions).filter(([,value])=>value.trim()))});}}>Prepare stock mappings</button>
    </>}
    {proof && <section aria-label="Holdings exclusion coverage"><p>Original pre-exclusion portfolio reported value (USD), as of {proof.source_as_of}: {proof.reference_value_usd.value??"Unknown"}. Known excluded value: {proof.excluded_known_value_usd}; {proof.unknown_value_ids.length} unknown holding values. Cash treatment creates no funding.</p>
      {proof.coverage_unknown_reasons.length>0?<p role="alert">Exclusion coverage unavailable: {proof.coverage_unknown_reasons.join(", ")}. Unknown exposure is not zero or below threshold.</p>:<p>Aggregate excluded exposure: {proof.aggregate_excluded_bps?.toFixed(4)} bps. Highlights apply strictly above 10 bps per name or 100 bps in aggregate; they are warnings.</p>}
      {proof.aggregate_highlight&&<p role="alert">Aggregate exclusions exceed 100 bps.</p>}
      {proof.rows.filter(row=>row.highlight).map(row=><p key={row.source.id}>Above 10 bps: {row.source.ticker} / {row.excluded_bps?.toFixed(4)} bps.</p>)}
    </section>}
    {busy && <p role="status">Preparing retained holdings identities…</p>}
    {error && <p role="alert">{error}</p>}
    {pending&&!busy&&<button disabled={disabled} onClick={()=>void prepare(pending)}>Retry identical mapping preparation</button>}
    {pending&&!busy&&<button disabled={disabled} onClick={()=>{generation.current++;setPending(null);setError(null);}}>Change preparation</button>}
  </section>;
}
