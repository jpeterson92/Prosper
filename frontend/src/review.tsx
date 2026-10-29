import { useEffect, useRef, useState } from "react";
import { ClientError, connect } from "./client";
import type { Alignment, HistoryReview, HistoryManifest, HistoryRequest, HistoryDiagnosticRequest, Catalog, Current, DiagnosticRequest, Preview, Run, SelectRequest, SettingsRequest } from "./client";
import { HistoryRows, SavedHistory } from "./history";
import { decimalDisplay } from "./display";
import { readLocation, writeLocation } from "./navigation";
import { recordStatus } from "./presentation";
import { RecordContext, runContext } from "./record-context";
import type { RecordSelection } from "./navigation";
import { AppShell } from "./app-shell";
import type { Page, Stage } from "./app-shell";
import { DetailsPanel, ExactValue, Help, Icon, SecurityLabels, Warnings } from "./ui";
import { SavedWork } from "./saved-work";
import { CashTreatments } from "./cash-treatment";
import type { CashAction } from "./cash-treatment";
import { HoldingsMapping } from "./holdings-mapping";
import { LotControls, LotView } from "./lots";
import type { LotAction } from "./lots";
import { BenchmarkControls } from "./benchmark";
import type { BenchmarkAction } from "./benchmark";
import { CandidateControls, CandidateView } from "./candidates";
import { Worksheets } from "./worksheets";
import type { WorksheetAction } from "./worksheets";
import type { Worksheet } from "./client";
import type { CandidateAction } from "./candidates";
import { InputsControls, InputsView, RiskSettingsView } from "./inputs";
import { InputPreparation } from "./input-preparation";
import type { InputsAction } from "./inputs";
import type { ModeledResult, ModeledUpload } from "./client";

type Pending = CashAction | WorksheetAction | CandidateAction | InputsAction | BenchmarkAction | LotAction | { kind: "history-refresh"; body: HistoryManifest } | { kind: "history-discard"; body: HistoryManifest } | { kind: "history-diagnostic"; body: HistoryDiagnosticRequest } | { kind: "history-clear"; body: { command_key: string; expected_revision: number } } | { kind: "select"; body: SelectRequest } | { kind: "settings"; body: SettingsRequest } | { kind: "diagnostic"; body: DiagnosticRequest } | { kind: "restore"; body: Uint8Array<ArrayBuffer> };
type Fact = { value: string | null; reason?: string | null };
function resourceMessage(problem: unknown): string | null {
  if (!(problem instanceof ClientError)) return null;
  if (problem.code === "history_alignment_size_limit") return "The complete history alignment exceeds the current record limit. Retained sources remain available; risk diagnostics are blocked.";
  if (problem.code === "pending_history_budget_exceeded") return "Pending history parts exceed the staging budget. Refresh the workspace and discard unneeded pending parts before reselecting the complete file.";
  return null;
}
function FactValue({ fact, rounded = false, money=false }: { fact: Fact; rounded?: boolean; money?:boolean }) {
  return fact.value === null ? <span className="unknown">Unknown <small>{fact.reason}</small></span> : <span className="number" title={fact.value}>{rounded ? <ExactValue value={fact.value} kind={money?"money":"number"} places={money?2:4}/> : fact.value}</span>;
}
function Snapshot({preview,rounded}:{preview:Preview;rounded:boolean}) {
  const s=preview.snapshot,held=new Set([...s.lots,...s.positions].map(row=>row.security_id)),grouped=new Map<string,typeof s.findings>();
  for(const issue of [...s.findings,...s.exclusions])grouped.set(issue.code,[...(grouped.get(issue.code)??[]),issue]);
  return <SecurityLabels value={s.securities}><article aria-label="Snapshot review"><section><div className="section-heading"><h2>Your holdings</h2><DetailsPanel title="Original holdings source" label="Source details"><dl className="facts"><div><dt>Account</dt><dd>{s.account_alias} / {s.account_id}</dd></div><div><dt>Scope</dt><dd>{s.account_scope}</dd></div><div><dt>Source</dt><dd>{s.source_name} / {s.source_as_of}</dd></div></dl><p>Snapshot ID {preview.id}</p><p>Original source SHA-256 {s.source_sha256}</p><pre>{JSON.stringify(s,null,2)}</pre></DetailsPanel></div><p>{s.account_alias} - {s.source_as_of.slice(0,10)} - {held.size} reported holding{held.size===1?"":"s"}</p>
    <div className="table-scroll"><table><caption>Holdings and tax lots</caption><thead><tr><th>Security</th><th>Shares</th><th>Reported basis (USD)</th><th>Lot details</th><th>Review</th></tr></thead><tbody>{s.securities.filter(security=>s.lots.some(l=>l.security_id===security.id)||s.positions.some(p=>p.security_id===security.id)).map(security=>{const lots=s.lots.filter(l=>l.security_id===security.id),positions=s.positions.filter(p=>p.security_id===security.id),quantity=positions.length===1?positions[0]?.quantity:lots.length===1?lots[0]?.quantity:null;return <tr key={security.id}><th>{security.ticker}<small>{security.name.value??"Name not supplied"}</small></th><td>{quantity?<FactValue fact={quantity} rounded={rounded}/>:lots.length?`${lots.length} lots` : "Not reported"}</td><td>{lots.length===1?<FactValue fact={lots[0]!.total_basis} rounded={rounded} money/>:lots.length?"See individual lots":"Not reported"}</td><td>{lots.length>0?<DetailsPanel title={`Lots for ${security.ticker}`} label={`${lots.length} tax lot${lots.length===1?"":"s"}`}><div className="table-scroll"><table><caption>Original tax lots</caption><thead><tr><th>Lot</th><th>Quantity</th><th>Basis (USD)</th><th>Acquired / term</th></tr></thead><tbody>{lots.map(l=><tr key={l.id}><th>{l.id}</th><td><FactValue fact={l.quantity} rounded={rounded}/></td><td><FactValue fact={l.total_basis} rounded={rounded} money/></td><td><FactValue fact={l.acquired}/><FactValue fact={l.term}/><details><summary>Source reference</summary>{l.source_ref}</details></td></tr>)}</tbody></table></div></DetailsPanel>:<span>No reported lots</span>}</td><td>{security.identity.value===null?"Identity needs review":security.classification.value===null?"Classification needs review":"Supplied identity"}<Help label={`About ${security.ticker} review status`}>Identity: {security.identity.value??security.identity.reason}. Classification: {security.classification.value??security.classification.reason}. A supplied identity does not establish tax eligibility.</Help></td></tr>;})}</tbody></table></div>
    {grouped.size>0&&<div className="source-findings"><h3>Source findings and exclusions</h3>{[...grouped].map(([code,items])=><div className="issue-item" key={code}><div><p>{items[0]?.reason}</p><DetailsPanel title="Source findings" label={`View ${items.length} affected items`}><ul>{items.map((i,n)=><li key={n}>{i.reason}<details><summary>Source details</summary>{i.code} / {i.locator}</details></li>)}</ul></DetailsPanel></div></div>)}</div>}
    <DetailsPanel title="Positions and cash observations" label="View reported cash and independent positions"><ul>{s.positions.map(row=><li key={row.id}>{s.securities.find(v=>v.id===row.security_id)?.ticker??row.security_id}: <FactValue fact={row.quantity} rounded={rounded}/><details><summary>Source details</summary>{row.source_ref}</details></li>)}{s.cash.map(row=><li key={row.id}>{row.kind} ({row.currency}): <FactValue fact={row.amount} rounded={rounded}/><details><summary>Source details</summary>{row.source_ref}</details></li>)}</ul><p>Reported cash does not set the amount selected for investment.</p></DetailsPanel>
  </section></article></SecurityLabels>;
}

function DiagnosticView({ run, revision }: { run: Run; revision: number | undefined }) {
  const counts = run.outputs?.counts;
  const findings = run.outputs?.findings;
  return <SecurityLabels value={[]}><article aria-label="Saved diagnostic">
    <p>Analysis date: {runContext(run).analysis??"Unavailable in saved record"} - {recordStatus(run)}</p><DetailsPanel title="Saved analysis identity" label="Record details"><p>{run.id} / {run.model_version} / {run.as_of}</p></DetailsPanel>
    <p>{run.input_revision === revision ? "Matches current inputs" : "Historical inputs"}<Help label="About saved input identity">Saved input revision {run.input_revision}. Historical outputs are never recalculated when opened.</Help></p>
    {run.outputs?.kind === "history-inputs-v1" && <>
      <p>{run.outputs.coverage_complete === true ? "Recorded history coverage complete" : "Recorded history incomplete"}; this is input coverage, with financial qualification still unavailable.</p>
      {Array.isArray(run.outputs.ordered_securities) && <p>Saved security order: {run.outputs.ordered_securities.map(String).join(", ")}</p>}
      {Array.isArray(run.outputs.sessions) && <p>Saved sessions: {run.outputs.sessions.map(String).join(", ")}</p>}
    </>}
    {counts !== null && typeof counts === "object" && !Array.isArray(counts) && <dl className="facts">{Object.entries(counts).map(([name, value]) => <div key={name}><dt>{name.replaceAll("_"," ")}</dt><dd>{typeof value === "number" ? value : "Unavailable"}</dd></div>)}</dl>}
    <Warnings values={run.warnings}/>
    {Array.isArray(findings) && <ul>{findings.map((finding, index) => finding && typeof finding === "object" && !Array.isArray(finding) ? <li key={index}>{String(finding.reason)}<details><summary>Source reference</summary>{String(finding.code)} / {String(finding.locator)}</details></li> : null)}</ul>}
    {run.exclusions.length > 0 && <><h3>Exclusions</h3><ul>{run.exclusions.map((f, i) => <li key={i}>{f.locator}: {f.reason}</li>)}</ul></>}
    {Array.isArray(run.outputs?.issues) && <details><summary>Original located issues</summary><ul>{run.outputs.issues.map((issue, index) => <li key={index}>{JSON.stringify(issue)}</li>)}</ul></details>}
    <SavedHistory run={run} />
    <LotView run={run} />
    <CandidateView run={run} />
    {run.model_version === "modeled-inputs-v1" && run.status === "partial" && <>
      <InputsView result={run.outputs as unknown as ModeledResult} label="Saved modeled inputs" />
      <RiskSettingsView profile={(run.inputs.modeled_request as unknown as {bundle: ModeledUpload["bundle"]}).bundle.profile} />
    </>}
    <details><summary>Saved inputs and result record</summary><pre>{JSON.stringify(run, null, 2)}</pre></details>
  </article></SecurityLabels>;
}

export function Review() {
  const [page,setPage]=useState<Page>(()=>readLocation().page);
  const [stage,setStage]=useState<Stage>(()=>readLocation().stage);
  const [preparedPrices,setPreparedPrices]=useState<{revision:number;marks:import("./client").LotSettings["marks"]}|null>(null);
  const [latest,setLatest]=useState<Run|null>(null);
  const [currentInput,setCurrentInput]=useState<Run|null>(null);
  const [loading,setLoading]=useState(true),[latestUnavailable,setLatestUnavailable]=useState(false);
  const [record,setRecord]=useState<RecordSelection|null>(()=>readLocation().record??null);
  const [recordLoading,setRecordLoading]=useState(Boolean(readLocation().record)),[recordError,setRecordError]=useState(false);
  const recordAttempt=useRef(0);
  const [recordRetry,setRecordRetry]=useState(0);
  const [selected,setSelected]=useState<Preview|null>(null);
  const [current, setCurrent] = useState<Current | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [diagnosticOpen,setDiagnosticOpen]=useState(false);
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
  const [rounded, setRounded] = useState(true);
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
  async function refresh(reviewSelected = false) {
    setLoading(true);
    try {
      const c=await client();await c.runtime();
      const state=await c.current(),list=await c.catalog(),chosen=state.snapshot_id?await c.preview(state.snapshot_id):null;
      let latest:Run|null=null,input:Run|null=null,unavailable=false;
      try {
        latest=state.current_run_id?await c.run(state.current_run_id):null;
        if(latest?.input_revision===state.revision) {
          if(latest.model_version==="modeled-inputs-v1")input=latest;
          else if(latest.model_version==="candidate-workflow-v1"&&typeof latest.inputs.candidate_command==="object") {
            const id=(latest.inputs.candidate_command as {input_run_id?:unknown}|null)?.input_run_id;
            if(typeof id==="string")input=await c.run(id);
          } else {
            for(const id of [...list.runs].reverse().slice(0,20)) {
              const value=await c.run(id);
              if(value.input_revision===state.revision&&value.model_version==="modeled-inputs-v1"&&value.outputs?.software_inputs_complete===true){input=value;break;}
            }
          }
        }
      }catch{unavailable=true;}
      setCurrent(state);setCatalog(list);setSelected(chosen);setLatest(latest);setCurrentInput(input);setLatestUnavailable(unavailable);setRuntimeReady(true);setReviewed(false);setSettingsReviewed(false);
      if(reviewSelected)setPreview(chosen);
    } catch(problem){setCurrent(null);setLatestUnavailable(true);throw problem;} finally {setLoading(false);}
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
  async function refreshAfterAction(reviewSelected = false) {
    try { await refresh(reviewSelected); } catch {
      session.current = null; setCurrent(null);
      setError("The action outcome is shown above. Current state could not be refreshed. Refresh the workspace before another change.");
    }
  }
  async function execute(command: Pending) {
    if(command.kind==="settings")document.querySelector<HTMLDialogElement>("dialog.detail-panel[open]")?.close();
    const c = await client();
    try {
    if (command.kind === "cash-treatment") {
      const result=await c.treatCash(command.body);setPreview(null);
      setMessage(`Cash treatment: ${result.outcome}; revision ${result.revision}. Investment budget unchanged.`);
    } else if (command.kind === "worksheet-save") {
      const value=await c.saveWorksheet(command.body);setWorksheet(value);selectRecord({kind:"worksheet",id:value.command.id}); setMessage("Dated manual worksheet saved. Review its frozen inputs, assumptions and warnings.");
    } else if (command.kind === "candidate-start" || command.kind === "candidate-cancel") {
      if(command.kind==="candidate-start")setWorksheet(null);setDiagnosticOpen(false);setRun(command.kind === "candidate-start" ? await c.startCandidate(command.body) : await c.cancelCandidate(command.body)); setMessage("Candidate run state saved. Review progress and qualification below.");
    } else if (command.kind === "modeled-inputs") {
      setDiagnosticOpen(true);setRun(await c.diagnoseInputs(command.body)); setMessage("Dated modeled input diagnostics saved.");
    } else if (command.kind === "benchmark-diagnostic") {
      setDiagnosticOpen(true);setRun(await c.diagnoseBenchmark(command.body)); setMessage("Reviewed benchmark result saved; selection unchanged.");
    } else if (command.kind === "benchmark-select") {
      const result = await c.selectBenchmark(command.body); setMessage(`Benchmark selection: ${result.outcome}; revision ${result.revision}.`);
    } else if (command.kind === "lot-diagnostic") {
      setDiagnosticOpen(true);setRun(await c.diagnoseLots(command.body)); setMessage("Dated lot diagnostics saved.");
    } else if ((command.kind === "diagnostic" || command.kind === "history-diagnostic")) {
      setDiagnosticOpen(true);setRun(command.kind === "history-diagnostic" ? await c.diagnoseHistory(command.body) : await c.diagnose(command.body)); setMessage(command.kind === "history-diagnostic" ? "Dated history diagnostics saved." : "Dated source diagnostics saved.");
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
    setPending(null); setReviewed(false); setSettingsReviewed(false); await refreshAfterAction(command.kind==="cash-treatment");
  }
  function mutate(command: Pending) { setPending(command); void perform(() => execute(command), true); }
  function plan(mode: "missing" | "selected" | "full") {
    if (!historyRequest) return;
    const selected = mode === "full" ? historyRequest.series.map(s => s.security_id) : mode === "selected" ? manualNames.split(",").map(s => s.trim()).filter(Boolean) : [];
    const request = { ...historyRequest, manual_security_ids: selected };
    void perform(async () => { setAlignment(await (await client()).planHistory(request)); setMessage("History refresh plan read; no acquisition or financial calculation was requested."); });
  }
  const disabled = busy || pending !== null || current === null;
  function navigate(next:Page) {if(!loading)setMessage("Workspace read.");setPage(next);recordAttempt.current++;setRecord(null);writeLocation({page:next,stage});window.scrollTo({top:0,behavior:"instant"});}
  function changeStage(next:Stage) {recordAttempt.current++;setRecord(null);if(!loading)setMessage("Workspace read.");setPage("analysis");setStage(next);writeLocation({page:"analysis",stage:next});window.scrollTo({top:0,behavior:"instant"});}
  useEffect(()=>{const restore=()=>{const location=readLocation();setMessage("Workspace read.");setPage(location.page);setStage(location.stage);setRecord(location.record??null);};window.addEventListener("popstate",restore);return()=>window.removeEventListener("popstate",restore);},[]);
  useEffect(()=>{document.querySelectorAll<HTMLDialogElement>("dialog[open]").forEach(dialog=>dialog.close());document.querySelector<HTMLElement>("#workspace-content h1")?.focus({preventScroll:true});},[page,stage,record?.id]);
  const currentWork=latest?.input_revision===current?.revision?latest:null;
  const inputReady=currentInput?.input_revision===current?.revision&&currentInput?.outputs?.software_inputs_complete===true;
  const proposalReady=currentWork?.model_version==="candidate-workflow-v1"&&currentWork.status!=="running"&&currentWork.outputs?.outcome==="checked";
  const calculating=currentWork?.model_version==="candidate-workflow-v1"&&currentWork.status==="running";
  const limited=currentWork?.model_version==="candidate-workflow-v1"&&!calculating&&!proposalReady;
  const nextLabel=loading?"Reading workspace":!current?"Retry workspace read":latestUnavailable?"Refresh analysis state":!current.snapshot_id?"Import holdings":!current.settings.benchmark_run_id?"Choose a benchmark":calculating?"View calculation":proposalReady?"Compare proposals":limited?"Review calculation":inputReady?"Create proposals":"Review inputs";
  const outcomeLabel:Record<string,string>={cancelled:"Calculation cancelled",timeout:"Calculation time limit reached",interrupted:"Calculation interrupted",stale:"Inputs changed",failed:"Calculation failed",unavailable:"Inputs need attention"};
  const stateLabel=loading?"Reading workspace":!current||latestUnavailable?"State unavailable":calculating?"Calculating proposals":proposalReady?"Comparison available":limited?outcomeLabel[String(currentWork?.outputs?.outcome)]??"Calculation needs review":inputReady?"Inputs reviewed":"Needs attention";
  const nextDescription=loading?"Reading selected holdings and saved work.":!current||latestUnavailable?"Saved state could not be read completely. Refresh before choosing your next task.":!current.snapshot_id?"Import a dated holdings snapshot to explore loss opportunities and trade-offs.":!current.settings.benchmark_run_id?"Choose the benchmark you want to track.":calculating?"The calculation is in progress. Open it to review progress or request cancellation.":limited?"Review the saved calculation outcome. A limited or cancelled search does not prove infeasibility.":proposalReady?"Compare estimates against making no changes, then check a manual worksheet.":inputReady?"Your saved input review matches current inputs. Review proposal costs and share limits next.":"Review the remaining source facts and investor choices before calculating.";
  function continueAnalysis() {
    if(!current||latestUnavailable){void perform(refresh);return;}
    if(!current.snapshot_id){navigate("holdings");return;}
    if(calculating||limited){setRun(currentWork);changeStage("proposals");return;}
    if(proposalReady){openRun(currentWork!.id);return;}
    if(inputReady)setRun(currentInput);
    changeStage(current.settings.benchmark_run_id?(inputReady?"proposals":"review"):"benchmark");
  }
  function selectRecord(value:RecordSelection) {if(!loading)setMessage("Workspace read.");setPage("worksheets");setRecord(value);setRecordLoading(true);writeLocation({page:"worksheets",stage,record:value});window.scrollTo({top:0,behavior:"instant"});}
  function openWorksheet(id:string) {selectRecord({kind:"worksheet",id});}
  function openRun(id:string) {selectRecord({kind:"run",id});}
  useEffect(()=>{
    const ticket=++recordAttempt.current;
    if(!record||!runtimeReady){setRecordLoading(Boolean(record));return;}
    setRecordLoading(true);setRecordError(false);setWorksheet(null);setRun(null);
    void client().then(async c=>{
      const worksheet=record.kind==="worksheet"?await c.worksheet(record.id):null;
      const value=await c.run(worksheet?.command.run_id??record.id);
      if(ticket===recordAttempt.current){setWorksheet(worksheet);setRun(value);setDiagnosticOpen(value.model_version!=="candidate-workflow-v1");}
    }).catch(()=>{if(ticket===recordAttempt.current){session.current=null;setRecordError(true);}}).finally(()=>{if(ticket===recordAttempt.current)setRecordLoading(false);});
    return()=>{recordAttempt.current++;};
  },[record?.kind,record?.id,runtimeReady,recordRetry]);
  return <SecurityLabels value={(preview??selected)?.snapshot.securities??[]}><AppShell page={page} stage={stage} onNavigate={navigate} onStage={changeStage} onRefresh={()=>void perform(async()=>{await refresh();setMessage("Workspace read.");})} refreshing={busy||loading} loading={loading} unavailable={!loading&&!current} account={current?selected?.snapshot.account_alias??null:null} date={current?selected?.snapshot.source_as_of??null:null}>
    <div className="workspace-feedback"><p role="status" aria-label="Workspace status" className={message==="Workspace read."?"sr-only":undefined}>{message}</p>{loading&&<span className="loading-indicator" aria-label="Loading workspace"/>}{error&&<p role="alert">{error}</p>}
    {pending&&<section aria-label="Pending action" className="pending-action"><strong>The response is unresolved</strong><p>Your original request is retained. Retry it before making another change.</p><button disabled={busy} onClick={()=>void perform(()=>execute(pending),true)}>Retry identical action</button></section>}</div>
    <div hidden={page!=="overview"} className="workspace-page" aria-label="Overview page">
      <section className="welcome-panel"><div><span className="badge">{stateLabel}</span><h2>{loading?"Opening your workspace":current?.snapshot_id?"Your next step":"Start with your holdings"}</h2><p>{nextDescription}</p><div className="action-row"><button className="primary" disabled={busy||pending!==null||loading} onClick={continueAnalysis}>{nextLabel}<Icon name="arrow"/></button><button className="secondary" onClick={()=>navigate(current?.snapshot_id?"worksheets":"settings")}>{current?.snapshot_id?"Open saved work":"Restore a backup"}</button></div></div>
      <div className="portfolio-context"><h3>Portfolio snapshot</h3>{loading?<p>Reading holdings...</p>:selected&&current?<><strong>{selected.snapshot.lots.length} tax lot{selected.snapshot.lots.length===1?"":"s"}</strong><p>{new Set([...selected.snapshot.lots,...selected.snapshot.positions].map(row=>row.security_id)).size} reported holding{new Set([...selected.snapshot.lots,...selected.snapshot.positions].map(row=>row.security_id)).size===1?"":"s"} - {selected.snapshot.source_as_of.slice(0,10)}</p><button className="text-button" onClick={()=>navigate("holdings")}>Review holdings &rarr;</button></>:<p>{current?"No holdings selected yet.":"Holdings unavailable. Refresh to retry."}</p>}</div></section>
      <div className="context-actions"><button className="text-button" onClick={()=>navigate("settings")}>Backup & recovery</button>{inputReady&&<button className="text-button" onClick={()=>openRun(currentInput!.id)}>View saved input review</button>}</div>
      <SavedWork catalog={catalog} api={client} active={page==="overview"} compact onRun={openRun} onWorksheet={openWorksheet}/>
    </div>
    <div hidden={page!=="holdings"} className="workspace-page" aria-label="Holdings page">
      <div className="context-actions"><button className="text-button" disabled={disabled || !current?.snapshot_id} onClick={() => void perform(async () => { setPreview(await (await client()).preview(current!.snapshot_id!)); setReviewed(false); })}>Review current holdings</button></div>

            {preview&&preview.id!==current?.snapshot_id && <><p className="notice">Import preview - these holdings are not selected yet.</p><label><input type="checkbox" checked={reviewed} disabled={disabled} onChange={(event) => setReviewed(event.target.checked)} />I reviewed this snapshot and its unknowns</label><button disabled={disabled || !reviewed} onClick={() => mutate({ kind: "select", body: { snapshot_id: preview.id, command_key: crypto.randomUUID(), expected_revision: current!.revision } })}>Select reviewed snapshot</button><button disabled={disabled} onClick={() => void perform(async () => { await (await client()).reject(preview.id); await refresh(); setReviewed(false); setMessage("Preview rejected."); })}>Reject preview</button></>}
    {(preview??selected) && <Snapshot preview={(preview??selected)!} rounded={rounded} />}
    {(preview??selected)?.cash_holdings?.length!==0&&(preview??selected) && <CashTreatments preview={(preview??selected)!} current={current} disabled={disabled} onMutate={mutate} />}
    {(preview??selected) && <details className="mapping-tools"><summary>Stock identity mapping and exclusions</summary><HoldingsMapping preview={(preview??selected)!} current={current} disabled={disabled} api={client} onPreview={value=>{setPreview(value);setReviewed(false);setMessage("Holdings mapping preview staged; selected holdings unchanged.");void perform(refresh);}} /></details>}

    {preparedPrices&&<aside className="notice" aria-label="Return to input preparation"><p>{preparedPrices.revision===current?.revision?"Review the prepared EOD prices with your cash settings below, then save explicitly.":"Settings changed. Prepare again to review inputs against the new revision."} Your preparation declarations remain in this session.</p><button className="secondary" onClick={()=>changeStage("review")}>Return to input preparation</button></aside>}
    <LotControls current={current} disabled={disabled} api={client} onPreview={value => { setPreview(value); setReviewed(false); void perform(refresh); }} onMutate={mutate} preparedMarks={preparedPrices?.revision===current?.revision?preparedPrices?.marks??[]:[]} />
      <details className="advanced-section"><summary>Advanced import and retained snapshots</summary>    <section aria-label="Import"><h2>Import and review</h2><label>Normalized snapshot JSON file (up to 2 MiB)<input type="file" accept=".json" disabled={disabled} onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
      <button disabled={disabled || !file} onClick={() => void perform(async () => {
        if (!file || file.size > 2 * 1024 * 1024) throw new ClientError(422);
        setReviewed(false); setPreview(await (await client()).stage(await file.text())); await refresh(); setMessage("Preview staged; selected snapshot unchanged.");
      })}>Stage preview</button>
      <label>Retained snapshot<select value="" disabled={disabled} onChange={(event) => { const id = event.target.value; if (id) void perform(async () => { setReviewed(false); setPreview(await (await client()).preview(id)); }); }}><option value="">Choose a snapshot</option>{catalog?.snapshots.map((s) => <option key={s.id} value={s.id}>{s.state} / {s.imported_at} / {s.id}</option>)}</select></label>
      <label><input type="checkbox" checked={rounded} onChange={(event) => setRounded(event.target.checked)} />Round displayed numeric values to 2 decimals</label>
    </section>
</details>


      <div className="step-footer"><p>Next, choose the benchmark for your analysis.</p><button className="primary" disabled={disabled||!current?.snapshot_id} onClick={()=>changeStage("benchmark")}>Continue to benchmark<Icon name="arrow"/></button></div>
    </div>
    <div hidden={page!=="analysis"} className="workspace-page" aria-label="Analysis page">
      <div hidden={stage!=="benchmark"}>    <BenchmarkControls current={current} catalog={catalog} disabled={disabled} api={client} onMutate={mutate} onRefresh={refresh} saved={run} />
<div className="step-footer"><p>Use the explicitly selected benchmark to prepare your inputs.</p><button className="primary" disabled={disabled||!current?.settings.benchmark_run_id} onClick={()=>changeStage("review")}>Review inputs<Icon name="arrow"/></button></div></div>
      <div hidden={stage!=="review"}><div className="context-actions"><button className="text-button" onClick={()=>navigate("holdings")}>Review cash, costs and restrictions</button><button className="text-button" onClick={()=>navigate("settings")}>Manage market history</button></div>      <InputPreparation onSelectSource={source=>source==="holdings"?navigate("holdings"):changeStage("benchmark")} current={current} disabled={disabled} api={client} onMutate={mutate} onReviewPrices={(marks,revision)=>{setPreparedPrices({marks,revision});navigate("holdings");requestAnimationFrame(()=>{const cash=document.querySelector<HTMLElement>('[aria-label="Cash and cost settings"]');cash?.scrollIntoView({block:"start"});cash?.querySelector<HTMLButtonElement>("button")?.focus({preventScroll:true});});}} />
      <details><summary>Advanced supplied input configuration</summary><InputsControls current={current} disabled={disabled} api={client} onMutate={mutate} /></details>
<div className="step-footer"><p>{inputReady?"Current input review saved. Continue with costs and share limits.":"Save a complete input review before creating a proposal. You can inspect the Proposals stage at any time."}</p><button className="primary" disabled={disabled||!inputReady} onClick={()=>changeStage("proposals")}>Continue to proposals<Icon name="arrow"/></button></div></div>
      <div hidden={stage!=="proposals"}>    <CandidateControls current={current} disabled={disabled} api={client} onMutate={mutate} saved={run} onRead={setRun} onFinished={refresh} />
{run?.model_version==="candidate-workflow-v1"&&<CandidateView run={run}/>}<button className="text-button" onClick={()=>navigate("worksheets")}>Compare and save a worksheet &rarr;</button></div>
    </div>
    <div hidden={page!=="worksheets"} className="workspace-page" aria-label="Worksheets page"><div hidden={record!==null}><SavedWork catalog={catalog} api={client} active={page==="worksheets"} onRun={openRun} onWorksheet={openWorksheet}/></div>
    {record&&<button className="text-button" onClick={()=>navigate("worksheets")}>Back to saved work</button>}{recordLoading&&<p role="status">Reading original saved document...</p>}{recordError&&<p role="alert">This saved record could not be read. Return to the library or retry opening it. Current holdings were not substituted. <button className="secondary" onClick={()=>setRecordRetry(value=>value+1)}>Retry opening saved record</button></p>}{record&&!recordLoading&&!recordError&&run&&<RecordContext run={run} worksheet={worksheet} api={client}/>}
    {record&&!recordLoading&&!recordError&&!worksheet&&run?.model_version==="candidate-workflow-v1"&&<CandidateView run={run}/>}
    <div hidden={recordLoading||recordError||(!!record&&run?.model_version!=="candidate-workflow-v1"&&!worksheet)}><Worksheets current={current} run={run} catalog={catalog} worksheet={worksheet} onOpen={openWorksheet} api={client} onMutate={mutate} disabled={disabled}/></div>
    <section aria-label="Saved diagnostics" hidden={recordLoading||recordError||!!record&&!!worksheet||!!record&&run?.model_version==="candidate-workflow-v1"}><details open={diagnosticOpen} onToggle={e=>setDiagnosticOpen(e.currentTarget.open)}><summary>Saved analysis details</summary><h2 hidden={!!record}>Saved analysis</h2><p hidden={!!record}>Saved source quality, conditional lot estimates and history coverage retain their original inputs. Financial qualification remains unavailable.</p><button hidden={!!record} disabled={disabled || !current?.snapshot_id} onClick={() => mutate({ kind: "diagnostic", body: { run_id: crypto.randomUUID(), expected_revision: current!.revision, as_of: new Date().toISOString() } })}>Save source diagnostics</button><details hidden={!!record}><summary>Advanced saved-record tools</summary><label>Saved diagnostic<select value="" disabled={busy} onChange={(event) => { const id = event.target.value; if (id) openRun(id); }}><option value="">Choose a saved diagnostic</option>{catalog?.runs.map((id) => <option key={id} value={id}>{id}</option>)}</select></label></details>{run && <>{run.model_version==="modeled-inputs-v1"&&run.input_revision===current?.revision&&run.outputs?.software_inputs_complete===true&&<button onClick={()=>changeStage("proposals")}>Create proposals from this saved review</button>}<DiagnosticView run={run} revision={current?.revision} />{run.status === "running" && run.model_version === "lot-opportunities-v1" && run.inputs?.lot_request && <button disabled={disabled} onClick={() => mutate({ kind: "lot-diagnostic", body: run.inputs!.lot_request as unknown as Extract<LotAction, {kind: "lot-diagnostic"}>["body"] })}>Resume saved lot diagnostic</button>}{run.status === "running" && run.model_version === "history-inputs-v1" && run.inputs?.history_request && <button disabled={disabled} onClick={() => mutate({ kind: "history-diagnostic", body: { run_id: run.id, expected_revision: run.input_revision, as_of: run.as_of, request: run.inputs!.history_request as HistoryRequest } })}>Resume saved history diagnostic</button>}{run.status === "running" && run.model_version === "source-quality-v1" && <button disabled={disabled} onClick={() => mutate({ kind: "diagnostic", body: { run_id: run.id, expected_revision: run.input_revision, as_of: run.as_of } })}>Resume saved diagnostic</button>}</>}</details></section>
</div>
    <div hidden={page!=="settings"} className="workspace-page" aria-label="Settings page"><section className="settings-intro"><h2>Workspace & data</h2><p>Manage local work, source data and optional expert controls.</p><button className="secondary" onClick={()=>navigate("holdings")}>Edit cash, costs and restrictions</button></section>
    <section aria-label="Recovery"><h2>Backup and restore</h2><p>Download the current workspace, including original sources and saved outputs. Restore requires an empty workspace and never overwrites user work. This workspace is {current?.snapshot_id||catalog?.runs.length||catalog?.snapshots.length?"already in use; restore a backup in a separate empty workspace":"empty and available for a current-format backup"}.</p><button disabled={disabled} onClick={() => void perform(async () => {
      const blob = await (await client()).backup(); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "prosper-advisory.sqlite3"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); setMessage("Workspace backup downloaded.");
    })}>Download workspace backup</button><details open={!current?.snapshot_id&&!catalog?.runs.length&&!catalog?.snapshots.length}><summary>Restore a backup into an empty workspace</summary><label>Current workspace backup (up to 64 MiB)<input type="file" disabled={disabled} onChange={(e) => setRestoreFile(e.target.files?.[0] ?? null)} /></label><button disabled={disabled || !restoreFile} onClick={() => void perform(async () => {
      if (!restoreFile || restoreFile.size > 64 * 1024 * 1024) throw new ClientError(422);
      const command: Pending = { kind: "restore", body: new Uint8Array(await restoreFile.arrayBuffer()) }; setPending(command); try { await execute(command); } catch { session.current = null; setError("Restore response unresolved or refused. Use an empty current workspace; retrying the same backup is safe."); }
    })}>Restore into empty workspace</button></details></section>
<details className="advanced-section"><summary>Market history and source tools</summary>    <section aria-label="Retained history">
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
</details><DetailsPanel title="Advanced workspace tools" label="Advanced workspace tools" dismissSignal={current?.revision}>    <section aria-label="Current selection"><h2>Selected snapshot and settings</h2><p>Revision {current?.revision ?? "unknown"}; selected snapshot: {current?.snapshot_id ?? "None"}</p><p>Current diagnostic: {current?.current_run_id ?? "None"}</p><pre aria-label="Current settings">{JSON.stringify(current?.settings ?? {}, null, 2)}</pre>
    </section>
    <section aria-label="Settings"><h2>Advanced workspace settings</h2><p>Record supplied settings as a JSON object. No financial defaults or validation of investor limits is supplied by this foundation.</p><label>Settings JSON<textarea rows={8} value={settings} disabled={disabled} onChange={(e) => { setSettings(e.target.value); setSettingsReviewed(false); }} /></label><button disabled={disabled} onClick={() => { setSettings(JSON.stringify(current!.settings, null, 2)); setSettingsReviewed(false); }}>Load current settings</button><label><input type="checkbox" checked={settingsReviewed} disabled={disabled} onChange={(e) => setSettingsReviewed(e.target.checked)} />I reviewed these settings</label><button disabled={disabled || !settingsReviewed} onClick={() => void perform(async () => {
      const value: unknown = JSON.parse(settings, (_key, value: unknown) => { if (typeof value === "number" && !Number.isFinite(value)) throw new ClientError(422); return value; }); if (value === null || Array.isArray(value) || typeof value !== "object") throw new ClientError(422);
      const command: Pending = { kind: "settings", body: { settings: value as SettingsRequest["settings"], command_key: crypto.randomUUID(), expected_revision: current!.revision } };
      setPending(command); try { await execute(command); } catch (problem) { session.current = null; setError("The settings response is unresolved. Retry the identical pending action."); }
    })}>Save reviewed settings</button></section>
</DetailsPanel></div>
  </AppShell></SecurityLabels>;
}
