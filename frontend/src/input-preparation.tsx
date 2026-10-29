import { useEffect, useRef, useState } from "react";
import { percentPreview } from "./display";
import { ClientError, connect } from "./client";
import type { AssembledInputs, Current, InputAssemblyContext, LotSettings, ModeledUpload } from "./client";
import type { components } from "./generated/api";
import type { InputsAction } from "./inputs";
import type { LotAction } from "./lots";
import { InputsView, RiskSettingsView } from "./inputs";
import { DetailsPanel, ExactValue, Help, Issues, SecurityName } from "./ui";

type Request = components["schemas"]["InputAssemblyRequest"];
type Evidence = components["schemas"]["SourceFact"];
type Control = components["schemas"]["InvestorControl"];
const limits: [Control["name"], string, Control["unit"]][] = [
  ["tracking_error", "Annual tracking error", "annualized-decimal-volatility"], ["max_orders", "Maximum orders", "orders"],
  ["turnover", "Turnover", "decimal-weight"], ["min_trade_notional", "Minimum trade notional", "USD"],
  ["max_trade_notional", "Maximum trade notional", "USD"], ["max_position_weight", "Maximum position weight", "decimal-weight"],
  ["sector_exposure", "Sector exposure", "decimal-weight"], ["industry_exposure", "Industry exposure", "decimal-weight"],
];
const ages = ["max_mark_age_days", "max_snapshot_age_days", "max_benchmark_age_days", "max_history_age_days", "maximum_universe_size"] as const;
const ageLabels = ["Maximum mark age days", "Maximum snapshot age days", "Maximum benchmark age days", "Maximum history age days", "Maximum universe size"];
const unknown = (value: string) => value ? {value, reason:null} : {value:null, reason:"Not supplied in preparation"};
function integer(raw: string) { if (!/^\d+$/.test(raw) || !Number.isSafeInteger(Number(raw))) throw Error("integer"); return Number(raw); }
type ControlDraft = {state:string; value:string; reason:string; reference:string; group:string; kind:string};
type FactDraft = {security_id:string; identity:string; classification:string; currency:string; sector:string; industry:string; evidence:string; source_ref:string};

export function InputPreparation({current, disabled, api, onMutate,onReviewPrices}: {
  current:Current|null; disabled:boolean; api:()=>ReturnType<typeof connect>; onMutate:(action:InputsAction|LotAction)=>void; onReviewPrices?:(marks:LotSettings["marks"],revision:number)=>void;
}) {
  const [context,setContext]=useState<InputAssemblyContext|null>(null);
  const [result,setResult]=useState<AssembledInputs|null>(null);
  const [busy,setBusy]=useState(false), [error,setError]=useState<string|null>(null), [reviewed,setReviewed]=useState(false);
  const [batches,setBatches]=useState<string[]>([]), [factRun,setFactRun]=useState("");
  const [day,setDay]=useState(""), [asOf,setAsOf]=useState(new Date().toISOString());
  const [sessions,setSessions]=useState(""), [predecessor,setPredecessor]=useState(""), [knownAt,setKnownAt]=useState(new Date().toISOString());
  const [calendar,setCalendar]=useState(""), [overlap,setOverlap]=useState("1");
  const [coverage,setCoverage]=useState<Record<string,string>>({});
  const [controls,setControls]=useState<Record<string,ControlDraft>>({});
  const [taxonomy,setTaxonomy]=useState({name:"",version:""});
  const [declarations,setDeclarations]=useState<Evidence[]>([]), [facts,setFacts]=useState<FactDraft[]>([]);
  const [choices,setChoices]=useState<Record<string,string>>({}), [overrides,setOverrides]=useState("{}");
  const attempt=useRef(0), revision=useRef(current?.revision); revision.current=current?.revision;
  const locked=disabled||busy;
  function invalidate() {attempt.current++;setResult(null);setReviewed(false);setError(null);}
  useEffect(()=>{attempt.current++;setContext(null);setResult(null);setReviewed(false);setBusy(false);},[current?.revision,current?.snapshot_id]);
  useEffect(()=>()=>{attempt.current++;},[]);
  async function read(action:(client:Awaited<ReturnType<typeof connect>>, live:()=>boolean)=>Promise<void>) {
    const id=++attempt.current, expected=revision.current;setBusy(true);setError(null);setReviewed(false);setResult(null);
    const live=()=>id===attempt.current&&expected===revision.current;
    try {await action(await api(),live);} catch(problem) {if(live())setError(problem instanceof ClientError ? "Preparation request failed or was refused. Check the declarations and current sources, then retry. No selection or settings changed." : "Check dates, whole-number settings and Advanced overrides. Preparation could not be completed.");}
    finally {if(live())setBusy(false);}
  }
  const selected=context?.history_options.filter(h=>batches.includes(h.id))??[];
  const contexts=Object.fromEntries([...new Set(selected.flatMap(h=>h.contexts.map(c=>c.security_id)))].sort().map(id=>[id,selected.flatMap(h=>h.contexts).filter(c=>c.security_id===id).filter((c,i,all)=>all.findIndex(v=>JSON.stringify(v)===JSON.stringify(c))===i)]));
  const evidenceIds=[...new Set([...(context?.selected_source_sha256??[]),...selected.map(h=>h.source_sha256),...declarations.map(d=>d.source_sha256)])];
  function control(name:string) {return controls[name]??{state:"",value:"",reason:"",reference:"",group:"",kind:""};}
  function editControl(name:string,key:keyof ControlDraft,value:string) {setControls({...controls,[name]:{...control(name),[key]:value}});}
  function build():Request {
    if(!context||context.input_revision!==revision.current)throw Error("context");
    const investor_controls:Control[]=limits.flatMap(([name,,unit])=>{
      const c=control(name);if(!c.state)return [];
      return [{name,unit,enabled:c.state==="enabled",value:c.state==="enabled"?(c.value?unknown(c.value):{value:null,reason:c.reason||"Not supplied in preparation"}):{value:null,reason:c.reason||c.reference||"Explicitly disabled during preparation"},reference:c.reference,group:c.group||null,kind:(c.kind||null) as Exclude<Control["kind"],undefined>}];
    });
    const evidence=(f:FactDraft)=>{const d=declarations.find(d=>d.source_sha256===f.evidence);if(!d)throw Error("evidence");return {...d,source_ref:f.source_ref};};
    const coverage_settings=ages.every(k=>coverage[k]!==undefined&&coverage[k]!=="")?{...Object.fromEntries(ages.map(k=>[k,integer(coverage[k]??"")])),short_history_policy:"block"} as Exclude<Request["coverage_settings"],undefined>:null;
    JSON.parse(overrides); // Syntax only: original override text goes to the protected duplicate-key decoder.
    return {expected_revision:context.input_revision,analysis_date:day,as_of:asOf,
      history:batches.length&&sessions.trim()?{batch_ids:batches,sessions:sessions.trim().split(/[\s,]+/),predecessor,cutoff:day,known_at:knownAt,calendar_evidence:calendar,overlap_sessions:integer(overlap),series_choices:Object.entries(choices).flatMap(([id,key])=>contexts[id]?.filter(c=>JSON.stringify(c)===key)??[])}:null,
      coverage_settings,investor_controls,fact_run_id:factRun||null,taxonomy:taxonomy.name||taxonomy.version?taxonomy:null,
      source_declarations:declarations,
      securities:facts.filter(f=>f.identity||f.classification||f.currency).map(f=>({security_id:f.security_id,identity:unknown(f.identity),classification:unknown(f.classification),currency:f.currency,evidence:evidence(f)})),
      classifications:facts.filter(f=>f.sector||f.industry).map(f=>({security_id:f.security_id,sector:unknown(f.sector),industry:unknown(f.industry),evidence:evidence(f)})),marks:[],sources:[]};
  }
  const upload=result?.upload;
  const unresolvedLimits=limits.filter(([name])=>!control(name).state).length;
  const windowDeclared=Boolean(sessions&&predecessor&&calendar);

  // The backend validates these settings before coverage. Raw generic workspace
  // settings can contain an invalid object; keep that a located blocker.
  const lotSettings=result?.coverage&&!result.coverage.issues.some(i=>i.code==="lot_settings_required")
    ? current?.settings.lot_opportunities as unknown as LotSettings|undefined : undefined;
  return <section aria-label="Prepare EOD inputs">
    <h2>Review your inputs</h2><p>Confirm the data and limits for this analysis. We will show the decisions that need your attention.<Help label="About input preparation">Selected holdings, benchmark stocks and imported end-of-day history are assembled with the standard risk profile. Missing permissions, calendars and investor limits remain explicit. Unsaved drafts remain in this session until reload.</Help></p>
    <button disabled={locked} onClick={()=>void read(async(c,live)=>{const value=await c.inputAssemblyContext();if(live()){setContext(value);setBatches(old=>old.filter(id=>value.history_options.some(h=>h.id===id)));setFactRun(old=>value.fact_run_ids.includes(old)?old:"");}})}>Load selected input sources</button>
    {!context&&<p>Load current sources after changing holdings, benchmark or settings. Review retained draft declarations against the new selection.</p>}
    {context&&<><div className="readiness-strip" aria-label="Preparation checklist"><span>{context.snapshot_id?"Holdings selected":"Holdings needed"}</span><span>{context.benchmark_run_id?"Benchmark selected":"Benchmark needed"}</span><span>{windowDeclared?"History window declared":"History window needs review"}</span><span>{unresolvedLimits?`${unresolvedLimits} investor choices unresolved`:"Investor choices supplied"}</span></div><p>Selected holdings: {context.snapshot_id?"Available":"Unavailable"}. Benchmark: {context.benchmark_run_id?"Selected":"Unavailable"}. Replacement pool: all {context.benchmark_security_ids.length} supported benchmark stocks, subject to the history review.</p>
    <details><summary>Selected input identities</summary><p>Holdings {context.snapshot_id??"Unavailable"}; benchmark {context.benchmark_run_id??"Unavailable"}; revision {context.input_revision}.</p><ul>{context.selected_source_sha256.map(id=><li key={id}>{id}</li>)}</ul></details>
    <form onSubmit={e=>{e.preventDefault();void read(async(c,live)=>{const raw=JSON.stringify(build());const prepared=await c.prepareInputs(`${raw.slice(0,-1)},"risk_overrides":${overrides}}`);if(live())setResult(prepared);});}} onChange={invalidate}>
      <fieldset disabled={locked}>
        <legend>1. Prices and market history</legend>
        <label>Completed EOD session<input type="date" value={day} onChange={e=>setDay(e.target.value)} required/></label>
        <details><summary>Analysis time and source details</summary><label>Analysis knowledge time (ISO UTC)<input value={asOf} onChange={e=>setAsOf(e.target.value)}/></label></details>
        {context.history_options.length===0&&<p>No imported history is available. Import reviewed history in Settings / Market history and source tools; missing history cannot be created by preparation.</p>}
        {context.history_options.map(h=><div key={h.id}><label><input type="checkbox" checked={batches.includes(h.id)} onChange={e=>{setBatches(e.target.checked?[...batches,h.id]:batches.filter(id=>id!==h.id));setChoices({});}}/>Use history {h.source_name} ({h.sessions.count} sessions in source; collected {h.collected_at.slice(0,10)})</label><details><summary>History source evidence: {h.source_name}</summary><p>Original {h.source_sha256}; batch {h.id}; validation {h.validated_at}.</p><pre>{JSON.stringify(h.contexts,null,2)}</pre></details></div>)}
        {(!sessions||!predecessor||!calendar)&&<p className="notice">Confirm the exact history window and calendar, or explicitly reuse a saved declaration below.</p>}<details data-required={!windowDeclared}><summary><span>Declare calendar and exact window</span>{!windowDeclared&&<span className="required-badge">Needs review</span>}</summary>
          <p>A source grid is an observation, not a trading calendar. Choose the intended exact sessions and supply calendar evidence.</p>
          {selected.map(h=><button type="button" key={h.id} onClick={()=>{invalidate();void read(async(_c,live)=>{const bytes=Uint8Array.from(atob(h.sessions.data),c=>c.charCodeAt(0));const values:unknown=JSON.parse(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream("deflate"))).text());if(!Array.isArray(values)||values.length!==h.sessions.count||!values.every(v=>typeof v==="string"))throw Error();if(live())setSessions(values.join("\n"));});}}>Use session grid from {h.source_name}</button>)}
          <label htmlFor="preparation-sessions">Required sessions (one date per line)</label><textarea id="preparation-sessions" value={sessions} onChange={e=>setSessions(e.target.value)} rows={5}/>
          <label>Predecessor session<input type="date" value={predecessor} onChange={e=>setPredecessor(e.target.value)}/></label>
          <label>History knowledge time (ISO UTC)<input value={knownAt} onChange={e=>setKnownAt(e.target.value)}/></label>
          <label>Calendar evidence<input value={calendar} onChange={e=>setCalendar(e.target.value)}/></label>
          <label>History overlap sessions<input inputMode="numeric" value={overlap} onChange={e=>setOverlap(e.target.value)}/></label>
        </details>
        {Object.entries(contexts).filter(([,options])=>options.length>1).map(([id,options])=><label key={id}>History context {id}<select aria-label={`History context ${id}`} value={choices[id]??""} onChange={e=>setChoices({...choices,[id]:e.target.value})}><option value="">Unresolved: choose the exact source convention</option>{options.map(c=><option key={JSON.stringify(c)} value={JSON.stringify(c)}>{JSON.stringify(c)}</option>)}</select></label>)}
      </fieldset>
      <fieldset disabled={locked}><legend>2. Previously reviewed facts</legend>
        <label>Saved identity and taxonomy facts<select aria-label="Saved identity and taxonomy facts" value={factRun} onChange={e=>setFactRun(e.target.value)}><option value="">No saved fact run</option>{context.fact_run_ids.map((id,i)=><option key={id} value={id}>Saved input review {i+1}</option>)}</select></label>
        <p>Choose reviewed identity and classification facts. Window and investor declarations are reused only when you choose the button below.</p>
        <button type="button" disabled={!factRun} onClick={()=>void read(async(c,live)=>{const saved=await c.run(factRun);const b=(saved.inputs.modeled_request as unknown as {bundle:ModeledUpload["bundle"]}).bundle;if(!b)throw Error();if(live()){setDay(b.analysis_date);setSessions(b.history.sessions.join("\n"));setPredecessor(b.history.predecessor);setKnownAt(b.history.known_at);setCalendar(b.history.calendar_evidence);setOverlap(String(b.history.overlap_sessions));setCoverage(Object.fromEntries(ages.map(k=>[k,String(b.profile[k])])));setControls(Object.fromEntries(b.investor_controls.map(c=>[c.name,{state:c.enabled?"enabled":"disabled",value:c.value.value??"",reason:c.value.reason??"",reference:c.reference,group:c.group??"",kind:c.kind??""}])));}})}>Reuse saved window and investor declarations</button>
        {!factRun&&<><label>Taxonomy name<input value={taxonomy.name} onChange={e=>setTaxonomy({...taxonomy,name:e.target.value})}/></label><label>Taxonomy version<input value={taxonomy.version} onChange={e=>setTaxonomy({...taxonomy,version:e.target.value})}/></label></>}
        <details><summary>Resolve identity and taxonomy exceptions</summary>
          <p>Supported source identities and EOD marks are assembled automatically. Add only missing or corrected facts, using attributable evidence below. Blank identity/sector/industry facts remain explicitly unknown.</p>
          <button type="button" onClick={()=>{invalidate();setFacts([...facts,{security_id:"",identity:"",classification:"",currency:"",sector:"",industry:"",evidence:"",source_ref:""}]);}}>Add unresolved security facts</button>
          {facts.map((f,i)=><fieldset key={i}><legend>Security facts {i+1}</legend>{(["security_id","identity","classification","currency","sector","industry","source_ref"] as const).map(k=><label key={k}>{k.replaceAll("_"," ")} {i+1}<input value={f[k]} onChange={e=>setFacts(facts.map((v,j)=>j===i?{...v,[k]:e.target.value}:v))}/></label>)}<label>Evidence source {i+1}<select aria-label={`Evidence source ${i+1}`} value={f.evidence} onChange={e=>setFacts(facts.map((v,j)=>j===i?{...v,evidence:e.target.value}:v))}><option value="">Choose declared source</option>{declarations.map(d=><option key={d.source_sha256}>{d.source_sha256}</option>)}</select></label><button type="button" onClick={()=>{invalidate();setFacts(facts.filter((_,j)=>j!==i));}}>Remove facts {i+1}</button></fieldset>)}
        </details>
        <details><summary>Declare unresolved source permissions and validity</summary>
          <p>History marks retain their imported conventions. Identity/taxonomy sources need attributable provider, dataset, permission, original effective date and validity. No validity is inferred from a digest.</p>
          {evidenceIds.filter(id=>!declarations.some(d=>d.source_sha256===id)).map(id=><button type="button" key={id} onClick={()=>{invalidate();setDeclarations([...declarations,{source_sha256:id,source_ref:"",provider:"",dataset:"",permission_scope:"",effective:"",valid_through:"",recorded_at:""}]);}}>Declare source {id}</button>)}
          {declarations.map((d,i)=><fieldset key={d.source_sha256}><legend>Source {d.source_sha256}</legend>{(["source_ref","provider","dataset","permission_scope","effective","valid_through","recorded_at"] as const).map(k=><label key={k}>{k.replaceAll("_"," ")} source {i+1}<input value={d[k]} onChange={e=>setDeclarations(declarations.map((v,j)=>j===i?{...v,[k]:e.target.value}:v))}/></label>)}<button type="button" onClick={()=>{invalidate();setDeclarations(declarations.filter((_,j)=>j!==i));}}>Remove declaration {i+1}</button></fieldset>)}
        </details>
      </fieldset>
      <fieldset disabled={locked}><legend>3. Your data and investor limits</legend>
        <p>Enter your declarations or explicitly reuse saved ones. Empty settings remain unresolved; disabled limits require an explicit choice. Funding, cash targets and selling costs come from your cash settings. Limit editors show their exact input units; percentage previews help you check decimal fractions without changing the entered value.</p>
        {ages.some(k=>!coverage[k])&&<p className="notice">Freshness declarations are needed. Review the age allowances and capacity bound below.</p>}<details><summary>Review data freshness settings</summary>{ages.map((k,i)=><label key={k}>{ageLabels[i]}<input inputMode="numeric" value={coverage[k]??""} onChange={e=>setCoverage({...coverage,[k]:e.target.value})}/></label>)}</details>
        {limits.map(([name,label,unit])=>{const c=control(name);return <details key={name}><summary>{label}: {c.state||"Unresolved"}{c.state==="enabled"?` (${c.value||"Unknown"} ${unit})`:""}</summary><label>{label} choice<select aria-label={`${label} choice`} value={c.state} onChange={e=>editControl(name,"state",e.target.value)}><option value="">Unresolved</option><option value="enabled">Enable limit</option><option value="disabled">Explicitly disable</option></select></label>{c.state==="enabled"&&<label>{label} value ({unit})<input value={c.value} onChange={e=>editControl(name,"value",e.target.value)}/></label>}{c.state&&<label>{label} declaration reference<input value={c.reference} onChange={e=>editControl(name,"reference",e.target.value)}/></label>}{c.state==="enabled"&&c.value&&unit.includes("decimal")&&<p>Percentage preview: {percentPreview(c.value)}. The exact entered decimal remains {c.value}.</p>}{c.state==="enabled"&&name.endsWith("_exposure")&&<><label>{label} group<input value={c.group} onChange={e=>editControl(name,"group",e.target.value)}/></label><label>{label} meaning<select aria-label={`${label} meaning`} value={c.kind} onChange={e=>editControl(name,"kind",e.target.value)}><option value="">Unresolved</option><option value="absolute">Absolute</option><option value="active">Active</option></select></label></>}</details>;})}
      </fieldset>
      <details><summary>Advanced preparation settings</summary><label htmlFor="preparation-overrides">Preparation risk overrides JSON</label><textarea id="preparation-overrides" disabled={locked} value={overrides} onChange={e=>setOverrides(e.target.value)}/><p>Optional estimator overrides. Standard R1 remains the default; unsupported settings remain blockers.</p></details>
      <button disabled={locked} type="submit">Prepare and review EOD inputs</button>
    </form></>}
    {result&&<article aria-label="Preparation exceptions"><h3>{result.coverage?.software_inputs_complete?"Ready to save exploratory inputs":"Review unresolved exceptions"}</h3><p>{result.candidate_security_ids.length} original replacement names; {result.retained_candidate_security_ids===null?"retained pool unavailable":`${result.retained_candidate_security_ids.length} retained replacement names`}.</p><Issues issues={result.issues}/></article>}
    {upload&&<><RiskSettingsView profile={upload.bundle.profile}/>
      <article aria-label="Prepared settings and funding"><h3>Investor settings and funding</h3>
        <p>Selected cash budget USD {lotSettings?.cash_to_invest??"Unknown"}; budget reviewed: {lotSettings?.cash_budget_reviewed?"yes":"no"}. Funding assumption: {lotSettings?.funding_assumption.value??lotSettings?.funding_assumption.reason??"Unknown"}.</p>
        <p>Sell fee per isolated order USD {lotSettings?.sell_fee_per_isolated_order.value??"Unknown"}; sell discount {lotSettings?.sell_discount_bps.value??"Unknown"} bps. Final cash target: {lotSettings?.final_cash_target.enabled?JSON.stringify(lotSettings.final_cash_target):lotSettings?"Explicitly disabled":"Unknown"}.</p>
        <ul>{upload.bundle.investor_controls.map(c=><li key={c.name}><strong>{limits.find(([name])=>name===c.name)?.[1]??c.name.replaceAll("_"," ")}</strong>: {c.enabled?<>{c.value.value??`Unknown: ${c.value.reason}`} {c.unit.includes("decimal")&&c.value.value?`(${percentPreview(c.value.value)})`:c.unit}</>:<>Explicitly disabled: {c.value.reason}</>}<details><summary>Declaration reference</summary>{c.reference}</details></li>)}</ul>
      </article>
      {result.issues.some(i=>i.code==="lot_mark_conflict")&&<div className="table-scroll" tabIndex={0}><table><caption>EOD marks requiring settings review</caption><thead><tr><th>Security</th><th>Current lot mark USD / date</th><th>Prepared close USD / date</th></tr></thead><tbody>{upload.bundle.marks.map(m=><tr key={m.mark.security_id}><th><SecurityName id={m.mark.security_id}/></th><td><ExactValue value={lotSettings?.marks.find(p=>p.security_id===m.mark.security_id)?.price.value}/> / {lotSettings?.marks.find(p=>p.security_id===m.mark.security_id)?.day.value??"Unknown"}</td><td><ExactValue value={m.mark.price.value}/> / {m.mark.day.value??"Unknown"}</td></tr>)}</tbody></table></div>}
      <details><summary>Prepared sources, settings and funding</summary><pre>{JSON.stringify({assembly:upload.bundle.assembly,history:upload.bundle.history,investor_controls:upload.bundle.investor_controls,lot_settings:lotSettings??null},null,2)}</pre></details></>}
    {result?.coverage&&<InputsView result={result.coverage} label="Prepared input coverage" showIssues={false}/>}
    {upload&&result&&<>{onReviewPrices&&upload.bundle.marks.length>0&&<button type="button" className="secondary" disabled={locked} onClick={()=>onReviewPrices(upload.bundle.marks.map(m=>m.mark),result.input_revision)}>Review these prices with cash and costs</button>}<label><input type="checkbox" disabled={locked} checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/>I reviewed the prepared sources, exclusions, settings and unresolved exceptions</label>
      {lotSettings&&result.issues.some(i=>i.code==="lot_mark_conflict")&&<button disabled={locked||!reviewed} onClick={()=>onMutate({kind:"lot-settings",body:{settings:{...lotSettings,marks:[...lotSettings.marks.filter(m=>!upload.bundle.marks.some(p=>p.mark.security_id===m.security_id)),...upload.bundle.marks.map(m=>m.mark)]},command_key:crypto.randomUUID(),expected_revision:result.input_revision}})}>Use reviewed EOD marks in lot settings</button>}
      <button disabled={locked||!reviewed} onClick={()=>onMutate({kind:"modeled-inputs",body:{...upload,run_id:crypto.randomUUID(),expected_revision:result.input_revision,as_of:upload.bundle.assembly!.prepared_at}})}>Save prepared input diagnostics</button>
      <p>After saving, use the saved input run in Candidate calculation, then review and export its dated manual worksheet. Incomplete diagnostics can be saved; they cannot authorize a candidate or financial use.</p>
    </>}
    {error&&<p role="alert">{error}</p>}
  </section>;
}
