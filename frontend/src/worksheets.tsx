import { compactValue, percentPreview, metricChange } from "./display";
import { useEffect, useRef, useState } from "react";
import { DetailsPanel, ExactValue, Help, SecurityLabels, SecurityName, Warnings } from "./ui";
import type { connect, CandidateOutput, Catalog, Current, Run, Worksheet, WorksheetCheck, WorksheetPreview, WorksheetSave } from "./client";

export type WorksheetAction = {kind:"worksheet-save";body:WorksheetSave};
type API = () => ReturnType<typeof connect>;
type Check = Worksheet["check"];
type Orders = WorksheetCheck["orders"];
const money = (v:number|undefined) => v === undefined||!Number.isFinite(v) ? "Unavailable" : `${v<0?"-":""}$${compactValue(Math.abs(v),"money",2)}`;
const percent = (v:number|undefined) => v === undefined ? "Unavailable" : `${compactValue(v*100,"number",2)}%`;
const state = (p:Check) => p.unresolved ? "Unresolved" : p.feasible ? "Passes selected checks" : "Breaches selected limits";

function Metrics({check}:{check:Check}) {
  const m=check.metrics;
  return <><p>{state(check)}. {check.blockers.join("; ")}</p><dl className="facts metric-grid">
    <div><dt>Price/basis loss before wash adjustments</dt><dd>{money(m?.price_loss)}</dd></div>
    <div><dt>Short-term loss</dt><dd>{money(m?.short_term_loss)}</dd></div>
    <div><dt>Long-term loss</dt><dd>{money(m?.long_term_loss)}</dd></div>
    <div><dt>Unknown-term loss</dt><dd>{money(m?.unknown_term_loss)}</dd></div>
    <div><dt>Modeled cost</dt><dd>{money(m?.modeled_cost)}</dd></div>
    <div><dt>Final modeled cash</dt><dd>{money(m?.final_cash)}</dd></div>
    <div><dt>Modeled sleeve value</dt><dd>{money(m?.final_nav)}</dd></div>
    <div><dt>Annual tracking error<Help label="About worksheet tracking error">Estimated benchmark-relative volatility, annualized from the saved horizon. The conservative upper bound remains available for exact final-check review.</Help></dt><dd>{percent(m?.tracking_error)}<small>Conservative bound: {percent(m?.risk_upper_bound)}</small></dd></div>
    <div><dt>Turnover / orders</dt><dd>{percent(m?.turnover)} / {m?.order_count ?? "Unavailable"}</dd></div>
    <div><dt>Illustrative scenario value</dt><dd>{m?.scenario_net_value == null ? "Not selected or unavailable" : money(m.scenario_net_value)}</dd></div>
  </dl><DetailsPanel title="Exact worksheet metrics" label="Exact metric values"><dl className="facts">{Object.entries(m??{}).map(([key,value])=><div key={key}><dt>{key.replaceAll("_"," ")}</dt><dd>{value===null?"Unavailable":Array.isArray(value)?value.join(", "):String(value)}</dd></div>)}</dl><p>Display rounding never changes saved validator outcomes or enabled limits.</p></DetailsPanel></>;
}

function LimitsSummary({limits}:{limits:Worksheet["limits"]}) {
  return <div className="limit-summary" aria-label="Selected investor limits"><h4>Selected limits</h4><dl className="readiness-grid"><div><dt>Annual tracking error maximum</dt><dd>{percentPreview(limits.tracking_error)}</dd></div><div><dt>Modeled cost maximum</dt><dd>USD {limits.max_cost}</dd></div><div><dt>Maximum orders</dt><dd>{limits.max_orders}</dd></div><div><dt>Turnover maximum</dt><dd>{percentPreview(limits.max_turnover)}</dd></div></dl><DetailsPanel title="All selected limits" label="All limits and exact values"><dl className="facts"><div><dt>Minimum order USD</dt><dd>{limits.min_order_notional}</dd></div><div><dt>Maximum order USD</dt><dd>{limits.max_order_notional.enabled?limits.max_order_notional.value??"Unknown":"Explicitly disabled"}</dd></div><div><dt>Position weight maximum</dt><dd>{percentPreview(limits.max_position_weight)}</dd></div></dl><pre>{JSON.stringify(limits,null,2)}</pre></DetailsPanel><small>Check outcomes use the saved exact values and conservative risk bound, including every enabled exposure and value limit.</small></div>;
}
function Change({value,baseline,kind="money"}:{value:number|undefined;baseline:number|undefined;kind?:"money"|"risk"}) {
  return <small className="metric-change">{metricChange(value,baseline,kind)} vs no changes</small>;
}

function GroupWeights({output,check}:{output:CandidateOutput;check:Check}) {
  if(!output.search || !check.metrics) return <p>Group weights unavailable.</p>;
  const assets=output.search.inputs.assets;
  if(check.metrics.final_weights.length!==assets.length) return <p>Group weights unavailable: dimension mismatch.</p>;
  const rows: [string,string,number][]=[];
  for(const level of ["sector","industry"] as const) {
    const groups=new Map<string,number>();
    assets.forEach((a,i)=>{const name=a[level].value ?? `Unknown: ${a[level].reason ?? "not supplied"}`;groups.set(name,(groups.get(name)??0)+check.metrics!.final_weights[i]!);});
    for(const [name,weight] of groups) rows.push([level,name,weight]);
  }
  return <details><summary>Sector and industry weights</summary><ul>{rows.map(([level,name,weight])=><li key={`${level}:${name}`}>{level} / {name}: {percent(weight)}</li>)}</ul><p>Derived display weights use the full saved security order. Cash remains outside these equity groups.</p></details>;
}

export function SavedWorksheet({worksheet,api,disabled}:{worksheet:Worksheet;api:API;disabled:boolean}) {
  const [error,setError]=useState(false);
  return <article aria-label="Saved manual worksheet"><h3>Dated manual worksheet</h3>
    <p>{worksheet.validation_outcome==="checked-estimate"?"Checked worksheet - unqualified estimate":"No-change diagnostic - selected-limit breaches remain"}. Saved {worksheet.saved_at.slice(0,16).replace("T"," ")} UTC.</p><details><summary>Exact worksheet dates and validation outcome</summary>{worksheet.validation_outcome}; financially unauthorized. Saved {worksheet.saved_at}; worksheet as of {worksheet.command.as_of}.</details>
    <p>Historical estimate based on source {worksheet.source_as_of}, analysis {worksheet.analysis_date}, risk cutoff {worksheet.risk_as_of}; {worksheet.risk_horizon}-session horizon annualized at {worksheet.annualization_sessions}.</p>
    <p className="notice">Manual execution only. Verify current broker facts; after external changes, import refreshed holdings.</p>
    <details><summary>Calculation scope and model details</summary><p>Original candidate search: {worksheet.scope.search_method === "complete-cartesian-whole-share-reference" ? "Tiny exhaustive reference" : "Experimental proposal and repair"}; {worksheet.scope.search_outcome}, stopped at {worksheet.scope.stopping}; {worksheet.scope.evaluated_states} / {worksheet.scope.max_states} budgeted states or proposals. Quantity revisions receive final checks and are not reoptimized.</p>
    <p>Risk is a fitted, unqualified estimate using {worksheet.scope.lookback_sessions} sessions.</p><details><summary>Saved worksheet, model and input references</summary><p>Worksheet {worksheet.command.id}; candidate {worksheet.command.run_id}; parent {worksheet.command.parent_id ?? "none"}.</p><p>{worksheet.scope.risk_reference}. Retained security order: {worksheet.scope.security_ids.join(", ")}.</p></details>
    </details><LimitsSummary limits={worksheet.limits}/><Metrics check={worksheet.check}/>
    <details><summary>Saved sector and industry weights</summary><ul>{worksheet.group_weights.map((g,i)=><li key={i}>{g.level} / {g.classification.value ?? `Unknown: ${g.classification.reason}`}: {percent(g.weight)}</li>)}</ul></details>
    {!worksheet.lines.length?<p>No-change diagnostic. Selected-limit breaches remain visible above.</p>:<div className="table-scroll" tabIndex={0}><table><caption>Worksheet trades</caption><thead><tr><th>Action / whole shares</th><th>Security / lot</th><th>Indicative price (USD)</th><th>Price date</th><th>Details</th></tr></thead><tbody>{worksheet.lines.map((line,i)=><tr key={i}><th>{line.side} {line.shares}</th><td>{line.ticker}<small>{line.lot_id?`Lot ${line.lot_id}`:"Replacement buy"}</small></td><td><ExactValue value={line.indicative_price}/></td><td>{line.price_date}</td><td><DetailsPanel title="Worksheet line source" label="Lot and source details"><p>Account: {line.account_alias} / {line.account_id}</p><p>Security {line.security_id}; lot {line.lot_id??"not applicable to a buy"}; identity {line.identity}.</p><p>Reference USD {line.reference_price}; indicative USD {line.indicative_price}.</p><p>{line.source_ref}</p></DetailsPanel></td></tr>)}</tbody></table></div>}
    <p>Selected additional cash USD {worksheet.cash_to_invest}.</p>
    <p>{worksheet.exclusions.length} original source exclusions retained. Excluded holdings do not create spendable cash.</p><Warnings values={worksheet.warnings}/>
    <DetailsPanel title="Worksheet assumptions and original evidence" label="Assumptions and source details"><ul>{worksheet.assumptions.map((v,i)=><li key={i}>{v}</li>)}</ul>
    <ul>{worksheet.exclusions.map((v,i)=><li key={i}>{v.locator}: {v.reason}</li>)}</ul>
    <ul>{worksheet.findings.map((v,i)=><li key={i}>{v.locator}: {v.reason}</li>)}</ul>
    </DetailsPanel><details><summary>Saved limits and no-trade baseline</summary><pre>{JSON.stringify({limits:worksheet.limits,baseline:worksheet.baseline},null,2)}</pre></details>
    <button disabled={disabled} onClick={()=>{setError(false);void api().then(c=>c.exportWorksheet(worksheet.command.id)).then(blob=>{const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="prosper-manual-worksheet.txt";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}).catch(()=>setError(true));}}>Download dated text worksheet</button>
    {error && <p role="alert">Worksheet export could not be read. Retry the download.</p>}
  </article>;
}

export function Worksheets({current,run,catalog,worksheet,onOpen,api,onMutate,disabled}:{
  current:Current|null;run:Run|null;catalog:Catalog|null;worksheet:Worksheet|null;
  onOpen:(id:string)=>void;api:API;onMutate:(action:WorksheetAction)=>void;disabled:boolean;
}) {
  const [view,setView]=useState("compare");
  useEffect(()=>setView("compare"),[run?.id]);
  useEffect(()=>{if(worksheet)setView("saved");},[worksheet?.command.id]);
  const [sales,setSales]=useState<Record<string,string>>({});
  const [buys,setBuys]=useState<Record<string,string>>({});
  const [chosen,setChosen]=useState(false);
  const [parent,setParent]=useState<string|null>(null);
  const [preview,setPreview]=useState<WorksheetPreview|null>(null);
  const [reviewed,setReviewed]=useState(false);
  const [checking,setChecking]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const generation=useRef(0);
  useEffect(()=>{generation.current++;setChosen(false);setChecking(false);setPreview(null);setReviewed(false);setParent(null);setError(null);},[run?.id,current?.revision]);
  const output=run?.model_version==="candidate-workflow-v1" && run.status!=="running" ? run.outputs as unknown as CandidateOutput : null;
  const result=output?.outcome==="checked" ? output.search : null;
  const inputs=result?.inputs;
  const historical=!current || run?.input_revision!==current.revision;
  function choose(orders:Orders,parentId:string|null=null) {
    if(!inputs) return;
    if(orders.sales.some(s=>!(s.lot_id in inputs.sale_bounds)) || orders.buys.some(b=>!(b.security_id in inputs.buy_bounds))) {setError("The worksheet uses different input identities. Select a point from this candidate run.");return;}
    generation.current++;setChecking(false);setChosen(true);setParent(parentId);setReviewed(false);setPreview(null);setError(null);
    setSales(Object.fromEntries(inputs.snapshot.lots.map(l=>[l.id,String(orders.sales.find(s=>s.lot_id===l.id)?.shares ?? 0)])));
    setBuys(Object.fromEntries(Object.keys(inputs.buy_bounds).map(sid=>[sid,String(orders.buys.find(b=>b.security_id===sid)?.shares ?? 0)])));
  }
  function changed() {generation.current++;setPreview(null);setReviewed(false);setError(null);setChecking(false);}
  function readOrders():Orders {
    const quantity=(v:string)=>{if(!/^(0|[1-9][0-9]*)$/.test(v) || !Number.isSafeInteger(Number(v)))throw Error();return Number(v);};
    return {sales:Object.entries(sales).map(([lot_id,v])=>({lot_id,shares:quantity(v)})).filter(s=>s.shares>0),buys:Object.entries(buys).map(([security_id,v])=>({security_id,shares:quantity(v)})).filter(b=>b.shares>0)};
  }
  const blocked=disabled||historical||checking;
  return <SecurityLabels value={inputs?.assets.map(a=>a.security)??[]}><section aria-label="Comparison and manual worksheet"><h2>Compare & save a worksheet</h2>
    <p>Compare dated estimates under the same frozen inputs and limits. A failed or limited search is not a proof of infeasibility. Financial-use authorization remains unavailable.</p>
    {worksheet&&<nav className="view-switch" aria-label="Worksheet views"><button className="secondary" aria-pressed={view==="compare"} onClick={()=>setView("compare")}>Compare and revise</button><button className="secondary" aria-pressed={view==="saved"} onClick={()=>setView("saved")}>Saved worksheet</button></nav>}
    <div hidden={Boolean(worksheet)&&view!=="compare"}>{result && inputs && output && <>
      <details><summary>Calculation scope</summary><p>Candidate {run!.id}; method {result.method}; stopping {result.stopping}; {result.evaluated_states} checked states/proposals. {result.domain_states===null ? "Share domain not enumerated." : `Declared domain: ${result.domain_states} states.`}</p>
      </details><LimitsSummary limits={inputs.limits}/><p className="comparison-caption">Each proposal shows its change from the no-change portfolio. Tracking error changes are percentage points (pp); price/basis loss is before wash adjustments, not tax savings.</p><div className="table-scroll" tabIndex={0}><table aria-label="Candidate comparison" className="comparison-table"><thead><tr><th>Alternative</th><th>Check</th><th>Price loss USD</th><th>Cost USD</th><th>Cash USD</th><th>Annual tracking error</th><th>Turnover / orders</th><th>Review</th></tr></thead><tbody>{[result.baseline,...result.candidates].map((p,i)=><tr key={i}><th>{i===0 ? "No changes" : `Proposal ${i}`}</th><td data-label="Checks">{state(p)}<small>{p.blockers.join("; ")}</small><GroupWeights output={output} check={p}/></td><td data-label="Estimated price loss">{money(p.metrics?.price_loss)}{i>0&&<Change value={p.metrics?.price_loss} baseline={result.baseline.metrics?.price_loss}/>}</td><td data-label="Estimated cost">{money(p.metrics?.modeled_cost)}{i>0&&<Change value={p.metrics?.modeled_cost} baseline={result.baseline.metrics?.modeled_cost}/>}</td><td data-label="Final selected cash">{money(p.metrics?.final_cash)}{i>0&&<Change value={p.metrics?.final_cash} baseline={result.baseline.metrics?.final_cash}/>}</td><td data-label="Annual tracking error">{percent(p.metrics?.tracking_error)}{i>0&&<Change kind="risk" value={p.metrics?.tracking_error} baseline={result.baseline.metrics?.tracking_error}/>}<small>Conservative bound: {percent(p.metrics?.risk_upper_bound)}</small></td><td data-label="Turnover / orders">{percent(p.metrics?.turnover)} / {p.metrics?.order_count ?? "Unavailable"}</td><td data-label="Review"><button className="secondary" disabled={blocked} onClick={()=>choose(p.orders)}>{i===0 ? "Review no changes" : `Review proposal ${i}`}</button></td></tr>)}</tbody></table></div>
      <DetailsPanel title="Exact proposal comparison" label="Exact comparison values"><pre>{JSON.stringify({baseline:result.baseline,candidates:result.candidates},null,2)}</pre></DetailsPanel>
      <p>Source as of {inputs.snapshot.source_as_of}; analysis {inputs.settings.analysis_date}; marks are dated per security; risk cutoff {inputs.risk.as_of}, {output.risk?.horizon}-session horizon, {inputs.risk.annualization_sessions} annualization sessions.</p>
      <details><summary>Selected limits, funding and exclusions</summary><pre>{JSON.stringify({limits:inputs.limits,cash_to_invest:inputs.settings.cash_to_invest,funding:inputs.settings.funding_assumption,marks:inputs.settings.marks,exclusions:result.exclusions,source_exclusions:inputs.snapshot.exclusions},null,2)}</pre></details>
      <DetailsPanel title="Proposal assumptions and limitations" label="Assumptions and limitations"><ul>{[...output.warnings,...result.warnings].map((v,i)=><li key={i}>{v}</li>)}</ul></DetailsPanel>
      {historical && <p role="status">Historical candidate: new revisions require current modeled inputs. Saved worksheets remain viewable and downloadable.</p>}
      {worksheet&&worksheet.command.run_id===run?.id && <button disabled={blocked} onClick={()=>choose(worksheet.command.orders,worksheet.command.id)}>Revise saved worksheet quantities</button>}
      {chosen && <fieldset disabled={blocked}><legend>Whole-share worksheet revision</legend>
        <p>Zero explicitly means no order. Edits use the saved fitted risk and strict limits; changing run settings requires a new candidate calculation.</p>
        <div className="table-scroll" tabIndex={0}><table><thead><tr><th>Sale lot / source</th><th>Supplied quantity / basis USD</th><th>Whole shares to sell</th></tr></thead><tbody>{inputs.snapshot.lots.map(l=><tr key={l.id}><th><SecurityName id={l.security_id}/><small>Lot {l.id}</small><DetailsPanel title="Sale lot source" label="Source details"><p>{l.account_id} / {l.security_id} / {l.source_ref}</p></DetailsPanel></th><td>{l.quantity.value ?? `Unknown: ${l.quantity.reason}`} / {l.total_basis.value ?? `Unknown: ${l.total_basis.reason}`}</td><td><label>Shares to sell<input aria-label={`Sell shares ${l.id}`} type="number" min="0" step="1" max={inputs.sale_bounds[l.id]} value={sales[l.id] ?? "0"} onChange={e=>{changed();setSales({...sales,[l.id]:e.target.value});}}/></label><small>Declared maximum {inputs.sale_bounds[l.id]}</small></td></tr>)}</tbody></table></div>
        {Object.entries(inputs.buy_bounds).map(([sid,max])=><label key={sid}>Shares to buy - <SecurityName id={sid}/><input aria-label={`Buy shares ${sid}`} type="number" min="0" step="1" max={max} value={buys[sid] ?? "0"} onChange={e=>{changed();setBuys({...buys,[sid]:e.target.value});}}/><small>Declared maximum {max}; indicative mark {inputs.settings.marks.find(m=>m.security_id===sid)?.price.value ?? "unknown"}</small></label>)}
        <button onClick={()=>{let orders:Orders;try{orders=readOrders();}catch{setError("Enter explicit nonnegative whole-share quantities, using zero for no order.");return;}const ticket=++generation.current;setChecking(true);setError(null);void api().then(c=>c.checkWorksheet({run_id:run!.id,expected_revision:current!.revision,orders})).then(value=>{if(generation.current===ticket)setPreview(value);}).catch(()=>{if(generation.current===ticket)setError("Final checks could not be read. Refresh the workspace and check current inputs.");}).finally(()=>{if(generation.current===ticket)setChecking(false);});}}>Check worksheet quantities</button>
      </fieldset>}
      {preview && <article aria-label="Worksheet final checks"><h3>Final quantity checks</h3><Metrics check={preview.check}/>{preview.save_allowed ? <p>{preview.check.orders.sales.length || preview.check.orders.buys.length ? "Eligible to save as a checked worksheet." : "Eligible to save as a no-trade diagnostic; this does not clear baseline breaches."}</p> : <p>Refused: revise quantities or create a new run with explicitly reviewed settings.</p>}
        <label><input type="checkbox" checked={reviewed} disabled={blocked} onChange={e=>setReviewed(e.target.checked)}/>I confirm no external account changes since this snapshot; after external changes I will import refreshed holdings</label>
        <button disabled={blocked||!preview.save_allowed||!reviewed} onClick={()=>onMutate({kind:"worksheet-save",body:{id:crypto.randomUUID(),run_id:run!.id,parent_id:parent,expected_revision:current!.revision,as_of:new Date().toISOString(),no_external_changes:true,orders:preview.check.orders}})}>Save dated manual worksheet</button>
      </article>}
    </>}
    {!result && <p>Open a completed checked candidate to compare or revise quantities. Unavailable, cancelled, timeout and failed runs cannot produce a trade worksheet.</p>}
    </div><details><summary>Advanced worksheet lookup</summary><label>Saved manual worksheet<select value="" disabled={disabled} onChange={e=>{if(e.target.value)onOpen(e.target.value);}}><option value="">Choose a saved worksheet</option>{catalog?.worksheets.map(id=><option key={id} value={id}>{id}</option>)}</select></label></details>
    {worksheet && <div hidden={view!=="saved"}>{worksheet.command.run_id!==run?.id&&<p className="notice">This worksheet belongs to another saved proposal. <button className="secondary" onClick={()=>onOpen(worksheet.command.id)}>Open its original comparison</button></p>}<SavedWorksheet worksheet={worksheet} api={api} disabled={disabled}/></div>}
    {error && <p role="alert">{error}</p>}
  </section></SecurityLabels>;
}
