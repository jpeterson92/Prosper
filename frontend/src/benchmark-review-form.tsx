import { useEffect, useRef, useState } from "react";
import { ClientError } from "./client";
import type { BenchmarkObservation, BenchmarkReview, BenchmarkReviewContext, connect } from "./client";

type Evidence = BenchmarkReview["stipulation"]["fund_assertion"];
type EvidenceDraft = { source: "" | "metadata" | "holdings"; reference: string; effective: string; recorded: string; valid: string; unknown: string };
type SectionDraft = { role: "" | BenchmarkReview["stipulation"]["sections"][number]["role"]; weight: string; unit: string; value: string; currency: string; evidence: EvidenceDraft };
type RowDraft = { action: "" | "include" | "exclude"; reason: string; security: string; currency: string; asset: string; targetSection: string; targetIndex: string; evidence: EvidenceDraft };
const emptyEvidence = (): EvidenceDraft => ({source:"", reference:"", effective:"", recorded:"", valid:"", unknown:""});
const emptySection = (): SectionDraft => ({role:"", weight:"", unit:"", value:"", currency:"", evidence:emptyEvidence()});
const emptyRow = (): RowDraft => ({action:"", reason:"", security:"", currency:"", asset:"", targetSection:"", targetIndex:"", evidence:emptyEvidence()});
const rowKey = (section: string, index: number) => JSON.stringify([section,index]);

function EvidenceFields({ title, value, onChange, fund = false }: {title: string; value: EvidenceDraft; onChange: (value: EvidenceDraft) => void; fund?: boolean}) {
  return <fieldset aria-label={title}><legend>{title}</legend>
    <label>Evidence source<select value={value.source} onChange={e => onChange({...value, source:e.target.value as EvidenceDraft["source"]})}><option value="">Unreviewed / unknown</option><option value="metadata">Supplied metadata file</option>{!fund && <option value="holdings">Retained holdings response</option>}</select></label>
    <label>Evidence reference<input maxLength={256} value={value.reference} onChange={e => onChange({...value,reference:e.target.value})} /></label>
    <label>Evidence effective date<input type="date" value={value.effective} onChange={e => onChange({...value,effective:e.target.value})} /></label>
    <label>Evidence recorded date<input type="date" value={value.recorded} onChange={e => onChange({...value,recorded:e.target.value})} /></label>
    <label>Evidence valid through<input type="date" value={value.valid} onChange={e => onChange({...value,valid:e.target.value})} /></label>
    <label>Unknown reasons (semicolon separated)<input maxLength={4096} value={value.unknown} onChange={e => onChange({...value,unknown:e.target.value})} /></label>
  </fieldset>;
}

function evidence(value: EvidenceDraft, context: BenchmarkReviewContext, metadataDigest: string): Evidence {
  return {source_sha256:value.source === "metadata" ? metadataDigest : context.source_sha256,
    reference:value.reference || "Unreviewed source facts", effective:value.effective || null,
    recorded:value.recorded || null, valid_through:value.valid || null,
    unknown_reasons:value.source ? value.unknown.split(";").map(s=>s.trim()).filter(Boolean) : ["not_reviewed", ...value.unknown.split(";").map(s=>s.trim()).filter(Boolean)]};
}

export function BenchmarkReviewForm({ observation, disabled, api, onInvalidate, onPreview }: {
  observation: BenchmarkObservation; disabled: boolean; api: () => ReturnType<typeof connect>;
  onInvalidate: () => void; onPreview: (build: () => Promise<BenchmarkReview>) => void;
}) {
  const [context, setContext] = useState<BenchmarkReviewContext | null>(null);
  const [loadingError, setLoadingError] = useState(false);
  const [retry, setRetry] = useState(0);
  const [metadata, setMetadata] = useState<File | null>(null);
  const [ticker, setTicker] = useState(""); const [port, setPort] = useState(""); const [cusip, setCusip] = useState(""); const [day, setDay] = useState("");
  const [fundEvidence, setFundEvidence] = useState<EvidenceDraft>(emptyEvidence);
  const [metadataReviewed, setMetadataReviewed] = useState(false);
  const [cash, setCash] = useState(""); const [cashUnit, setCashUnit] = useState(""); const [cashEvidence, setCashEvidence] = useState<EvidenceDraft>(emptyEvidence);
  const [sections, setSections] = useState<Record<string,SectionDraft>>({});
  const [rows, setRows] = useState<Record<string,RowDraft>>({});
  const [rowSection, setRowSection] = useState(""); const [search, setSearch] = useState(""); const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set()); const [excludeReason, setExcludeReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [preparedReview, setPreparedReview] = useState<BenchmarkReview | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [prepareError, setPrepareError] = useState(false);
  const preparationRequest = useRef(0);
  function acceptPrepared(review:BenchmarkReview) {
    const ev=review.stipulation.fund_assertion;
    const draftEvidence=(item:Evidence):EvidenceDraft=>({source:"metadata",reference:item.reference,effective:item.effective??"",recorded:item.recorded??"",valid:item.valid_through??"",unknown:item.unknown_reasons.join("; ")});
    setPreparedReview(review);setMetadata(null);setMetadataReviewed(false);
    setTicker(review.metadata_ticker);setPort(review.metadata_port_id);setCusip(review.metadata_cusip);setDay(review.metadata_as_of);setFundEvidence(draftEvidence(ev));
    setCash(review.stipulation.benchmark_cash.raw??"");setCashUnit(review.stipulation.benchmark_cash_unit);setCashEvidence(draftEvidence(review.stipulation.benchmark_cash.evidence));
  }
  async function prepareOfficial() {
    const request=++preparationRequest.current;setPreparing(true);setPrepareError(false);onInvalidate();
    try {const review=await (await api()).prepareBenchmark(observation.request.observation_id);if(request===preparationRequest.current)acceptPrepared(review);}
    catch {if(request===preparationRequest.current)setPrepareError(true);}
    finally {if(request===preparationRequest.current)setPreparing(false);}
  }
  useEffect(() => {
    let active=true; setLoadingError(false);setContext(null);
    void (async()=>{try {const value=await (await api()).benchmarkReviewContext(observation.request.observation_id);if(active){
      setContext(value);
      if(value.mapping){
        const ev:EvidenceDraft={source:"holdings",reference:`Retained ${value.ticker} holdings ${value.effective_date}`,effective:value.effective_date,recorded:value.collected_at.slice(0,10),valid:value.effective_date,unknown:""};
        setSections({holdings:{role:"primary",weight:"percentOfFunds",unit:"percent",value:"marketValue",currency:"USD",evidence:{...ev}}});
        setRows(Object.fromEntries(value.mapping.rows.map(row=>[rowKey(row.section,row.index),{...emptyRow(),action:row.action,reason:row.reason,security:row.security_id??"",currency:row.security_id?"USD":"",asset:row.security_id?"stock":"",evidence:{...ev}}])));
      }
      if(value.metadata)void prepareOfficial();
    }} catch {if(active)setLoadingError(true);}})();
    return ()=>{active=false;preparationRequest.current++;};
    // The observation owns this read; the parent creates its session factory per render.
  },[observation.request.observation_id,retry]);
  function editSection(name: string, change: Partial<SectionDraft>) {onInvalidate();setSections(previous=>({...previous,[name]:{...(previous[name]??emptySection()),...change}}));}
  function editRow(key: string, change: Partial<RowDraft>) {onInvalidate();setRows(previous=>({...previous,[key]:{...(previous[key]??emptyRow()),...change}}));}
  function copyFundEvidenceToSelected() {onInvalidate();setRows(previous=>{const next={...previous};for(const key of selected)next[key]={...(next[key]??emptyRow()),evidence:{...fundEvidence}};return next;});}
  function excludeSelected() {onInvalidate();setRows(previous=>{const next={...previous};for(const key of selected)next[key]={...(next[key]??emptyRow()),action:"exclude",reason:excludeReason};return next;});}
  async function build(): Promise<BenchmarkReview> {
    setError(null);
    try {
      if(!context || (!preparedReview && (!metadata || !metadataReviewed)) || !ticker || !port || !cusip || !day || fundEvidence.source!=="metadata" || !fundEvidence.reference.trim()) throw new Error("Prepare official metadata or supply and review its file, identity, date and evidence reference.");
      if(metadata && (metadata.size===0 || metadata.size>4*1024*1024)) throw new Error("Supply a nonempty metadata file up to 4 MiB.");
      const bytes=metadata?new Uint8Array(await metadata.arrayBuffer()):Uint8Array.from(atob(preparedReview!.metadata_base64),c=>c.charCodeAt(0));
      const digest=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),b=>b.toString(16).padStart(2,"0")).join("");
      const chunks=[];for(let i=0;i<bytes.length;i+=32768)chunks.push(String.fromCharCode(...bytes.subarray(i,i+32768)));
      const sectionRules: BenchmarkReview["stipulation"]["sections"]=[];
      const values: BenchmarkReview["policy"]["values"]=[];
      for(const original of context.sections) {
        const item=sections[original.section];if(!item)continue;
        if(item.role) {
          if(!item.weight.trim() || !item.unit)throw new Error("A declared section role requires its weight field and percentage convention.");
          sectionRules.push({section:original.section,role:item.role,weight_field:item.weight,unit:item.unit,evidence:evidence(item.evidence,context,digest)});
        }
        if(item.value) {if(!item.currency)throw new Error("A declared value field requires its currency.");values.push({section:original.section,field:item.value,currency:item.currency});}
      }
      const rowRules: BenchmarkReview["stipulation"]["rows"]=[];
      const decisions: BenchmarkReview["policy"]["decisions"]=[];
      for(const original of context.rows) {
        const item=rows[rowKey(original.section,original.index)];if(!item)continue;
        const locator={section:original.section,index:original.index};
        const hasTarget=item.targetSection!=="" || item.targetIndex!=="";
        if(hasTarget && (!item.targetSection || !/^\d+$/.test(item.targetIndex) || !Number.isSafeInteger(Number(item.targetIndex))))throw new Error("A row link requires a section and nonnegative integer row index.");
        if(item.action && !item.reason.trim())throw new Error("Every inclusion or exclusion needs an explicit reason.");
        const ev=evidence(item.evidence,context,digest);
        rowRules.push({locator,row_sha256:original.row_sha256,evidence:ev,
          target:hasTarget?{section:item.targetSection,index:Number(item.targetIndex)}:null,
          security:item.security || item.currency || item.asset ? {security_id:item.security || null,currency:item.currency || null,asset_type:item.asset || "unknown",evidence:ev,unknown_reasons:item.security && item.currency && item.asset ? [] : ["identity_incomplete"]}:null});
        if(item.action)decisions.push({locator,action:item.action,reason:item.reason});
      }
      if(cash!=="" && !cashUnit)throw new Error("A declared benchmark cash value requires its convention.");
      return {observation_id:context.observation_id,reviewed_at:new Date().toISOString(),
        metadata_base64:btoa(chunks.join("")),metadata_reference:fundEvidence.reference,
        metadata_ticker:ticker as BenchmarkReview["metadata_ticker"],metadata_port_id:port as BenchmarkReview["metadata_port_id"],metadata_cusip:cusip as BenchmarkReview["metadata_cusip"],metadata_as_of:day,metadata_reviewed:true,
        stipulation:{raw_sha256:context.source_sha256,fund:{ticker:context.ticker,port_id:context.port_id},requested_date:context.requested_date,effective_date:context.effective_date,collected_at:context.collected_at,
          fund_assertion:evidence(fundEvidence,context,digest),sections:sectionRules,rows:rowRules,
          benchmark_cash:{raw:cash===""?null:cash,evidence:evidence(cashEvidence,context,digest),unknown_reasons:cash===""?["not_supplied"]:[]},benchmark_cash_unit:cashUnit || "unknown"},
        policy:{values,decisions,version:"equity-benchmark-v1"}};
    } catch(problem) {setError(problem instanceof Error ? problem.message : "Review preparation failed.");throw new ClientError(422);}
  }
  const matching=context?.rows.filter(row=>(!rowSection || row.section===rowSection) && `${row.section}:${row.index} ${row.source_ticker??""} ${row.source_name??""}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()))??[];
  const page=matching.slice(offset,offset+20);
  return <section aria-label="Prepare benchmark review"><h3>Prepare benchmark review</h3>
    <p>Source/date/row bindings come from the retained response. The inspected IVV layout receives dated issuer mappings and explicit policy exclusions automatically; other layouts keep unresolved review fields. History and tax eligibility remain unassessed. Review the summary and exceptions; advanced row decisions remain editable.</p>
    {!context && !loadingError && <p role="status">Reading review source bindings…</p>}
    {loadingError && <><p role="alert">Retained review bindings could not be read. No empty source is assumed.</p><button disabled={disabled} onClick={()=>setRetry(n=>n+1)}>Retry review preparation</button></>}
    {context && <form onChange={onInvalidate} onSubmit={e=>{e.preventDefault();onPreview(build);}}><fieldset disabled={disabled || preparing}>
      <legend>Review for {context.ticker} / {context.effective_date}</legend>
      <p>{context.rows.length} retained rows; {Object.keys(rows).length} prepared or edited. Edits are held in this form until previewed and saved. Opening a different observation or reloading clears this unsaved form.</p>
      {context.mapping && <section aria-label="Prepared mapping coverage"><h4>Dated issuer mapping</h4>
        <p>{context.mapping.included_count} mapped equities; {context.mapping.excluded_count} explicit exclusions. History and tax eligibility: not assessed. Mappings apply to this reported date; review the exceptions below.</p>
        <p>Known retained value: {context.mapping.retained_known_value_usd.toLocaleString("en-US",{style:"currency",currency:"USD"})}; known excluded value: {context.mapping.excluded_known_value_usd.toLocaleString("en-US",{style:"currency",currency:"USD"})}; {context.mapping.unknown_value_rows.length} unknown USD values.</p>
        {context.mapping.coverage_unknown_reasons.length>0 ? <p role="alert">Exclusion coverage unavailable: {context.mapping.coverage_unknown_reasons.map(reason=>reason.replaceAll("_"," ")).join(", ")}. Unknown exposure is not zero or below threshold.</p> : <p>Excluded exposure: {context.mapping.aggregate_excluded_bps?.toFixed(4)} bps of original pre-exclusion source market value. Highlights apply strictly above 10 bps per name or 100 bps in aggregate.</p>}
        {context.mapping.aggregate_highlight && <p role="alert">Aggregate exclusions exceed 100 bps. This is a coverage warning.</p>}
        {context.mapping.rows.filter(row=>row.action==="exclude").map(row=><p key={row.index}>{row.highlight && <strong>Above 10 bps: </strong>}{row.section}:{row.index} / {row.ticker??"unknown ticker"} / {row.reason.replaceAll("_"," ")} / {row.excluded_bps===null?"unknown exposure":`${row.excluded_bps.toFixed(4)} bps`}</p>)}
        <p>Fund metadata, evidence and benchmark cash remain separate inputs. Editing row decisions changes the draft; this source-preparation summary remains the original policy result, not a recalculated financial preview.</p>
      </section>}
      {context.mapping && <section aria-label="Official fund preparation"><h4>Fund metadata and proxy cash</h4>
        <button type="button" disabled={preparing} onClick={()=>void prepareOfficial()}>{preparedReview?"Reuse checked official metadata":"Prepare official fund metadata"}</button>
        {preparing && <p role="status">Preparing official metadata for this reporting date…</p>}
        {prepareError && <p role="alert">Official metadata could not be prepared for this fund/date. No alternate source or date was used. Retry this action or use an explicitly reviewed file under Advanced fund metadata.</p>}
        {preparedReview && <><p>Automatically checked: {preparedReview.metadata_ticker}, CUSIP {preparedReview.metadata_cusip}, holdings date {preparedReview.metadata_as_of}. Complete original metadata is retained and reused on reopen.</p><p>Prepared default — Modeled benchmark cash: 0, by the equity-only proxy definition. This is not the fund's actual cash balance or portfolio buying power. The current cash declaration and preview reflect manual edits. Review the consolidated preview before explicit save/selection.</p></>}
      </section>}
      <details><summary>Advanced fund metadata</summary><fieldset onChange={e=>{if(e.target.getAttribute("type")!=="checkbox"){setMetadataReviewed(false);setPreparedReview(null);}}}><legend>Independent fund metadata</legend>
        <p>Manual edits switch to reviewed-file preparation. Original source facts are preserved.</p>
        <label>Fund metadata file (up to 4 MiB)<input type="file" onChange={e=>{setMetadata(e.target.files?.[0]??null);setMetadataReviewed(false);}} /></label>
        <label>Metadata fund ticker<select value={ticker} onChange={e=>setTicker(e.target.value)}><option value="">Choose reviewed ticker</option>{["ITOT","IVV","VTI","VOO"].map(x=><option key={x}>{x}</option>)}</select></label>
        <label>Metadata portfolio ID<select value={port} onChange={e=>setPort(e.target.value)}><option value="">Choose reviewed portfolio ID</option>{["239724","239726","0970","0968"].map(x=><option key={x}>{x}</option>)}</select></label>
        <label>Metadata fund CUSIP<select value={cusip} onChange={e=>setCusip(e.target.value)}><option value="">Choose reviewed CUSIP</option>{["464287150","464287200","922908769","922908363"].map(x=><option key={x}>{x}</option>)}</select></label>
        <label>Metadata holdings date<input type="date" value={day} onChange={e=>setDay(e.target.value)} /></label>
        <EvidenceFields title="Fund identity evidence" fund value={fundEvidence} onChange={setFundEvidence} />
        <label><input type="checkbox" checked={metadataReviewed} onChange={e=>setMetadataReviewed(e.target.checked)} />I reviewed this metadata file for the declared fund identity and holdings date</label>
      </fieldset></details>
      <details><summary>Benchmark cash declaration</summary><p>Unknown cash stays unknown. Entering an exclusion never creates benchmark cash.</p><label>Benchmark cash raw amount<input value={cash} maxLength={128} onChange={e=>setCash(e.target.value)} /></label><label>Benchmark cash convention<select value={cashUnit} onChange={e=>setCashUnit(e.target.value)}><option value="">Choose convention</option><option value="decimal">Decimal</option><option value="percent">Percent</option></select></label><EvidenceFields title="Benchmark cash evidence" value={cashEvidence} onChange={setCashEvidence} /><button type="button" onClick={()=>{onInvalidate();setCashEvidence({...fundEvidence});}}>Use fund evidence for cash</button></details>
      <h4>Section decisions</h4>
      {context.sections.map(original=>{const item=sections[original.section]??emptySection();return <details key={original.section}><summary>{original.section}: {original.row_count??"unknown"} rows / {item.role||"unresolved"}</summary><fieldset aria-label={`Section ${original.section}`}><legend>{original.section}</legend>
        <label>Section role<select value={item.role} onChange={e=>editSection(original.section,{role:e.target.value as SectionDraft["role"]})}><option value="">Unreviewed</option>{["primary","alternate","subset","empty","unresolved"].map(x=><option key={x}>{x}</option>)}</select></label>
        <label>Published weight field<input value={item.weight} maxLength={256} list={`fields-${original.section}`} onChange={e=>editSection(original.section,{weight:e.target.value})} /></label>
        <label>Published weight convention<select value={item.unit} onChange={e=>editSection(original.section,{unit:e.target.value})}><option value="">Choose convention</option><option value="percent">Percent</option><option value="decimal">Decimal</option></select></label>
        <label>Source market value field<input value={item.value} maxLength={256} list={`fields-${original.section}`} onChange={e=>editSection(original.section,{value:e.target.value})} /></label><datalist id={`fields-${original.section}`}>{original.fields.map(field=><option key={field} value={field} />)}</datalist>
        <label>Value currency<select value={item.currency} onChange={e=>editSection(original.section,{currency:e.target.value})}><option value="">Unknown</option><option value="USD">USD</option></select></label>
        <EvidenceFields title={`Section evidence ${original.section}`} value={item.evidence} onChange={evidence=>editSection(original.section,{evidence})} /><button type="button" onClick={()=>editSection(original.section,{evidence:{...fundEvidence}})}>Use fund evidence for this section</button>
      </fieldset></details>;})}
      <h4>Row decisions</h4><p>Row numbers are zero based, matching the retained source view. Supply the same security IDs used by your portfolio and history inputs; a ticker alone does not establish identity. Row evidence also supports any supplied identity.</p>
      <label>Review row section<select value={rowSection} onChange={e=>{setRowSection(e.target.value);setOffset(0);}}><option value="">All sections</option>{context.sections.map(s=><option key={s.section}>{s.section}</option>)}</select></label>
      <label>Search review rows<input type="search" maxLength={200} value={search} onChange={e=>{setSearch(e.target.value);setOffset(0);}} /></label>
      <p role="status">{matching.length} matching review rows; showing {page.length?offset+1:0}–{offset+page.length}. {selected.size} selected across pages.</p>
      <label><input type="checkbox" checked={page.length>0 && page.every(r=>selected.has(rowKey(r.section,r.index)))} onChange={e=>{const next=new Set(selected);for(const r of page){const key=rowKey(r.section,r.index);if(e.target.checked)next.add(key);else next.delete(key);}setSelected(next);}} />Select this page for explicit bulk edits</label>
      <label>Exclusion reason for selected rows<input value={excludeReason} maxLength={256} onChange={e=>setExcludeReason(e.target.value)} /></label>
      <button type="button" disabled={!selected.size || !excludeReason.trim()} onClick={excludeSelected}>Exclude selected rows with this reason</button><button type="button" disabled={!selected.size} onClick={copyFundEvidenceToSelected}>Apply fund evidence to selected rows</button><button type="button" onClick={()=>setSelected(new Set())}>Clear row selection</button>
      {page.map(original=>{const key=rowKey(original.section,original.index);const item=rows[key]??emptyRow();return <article key={key} aria-label={`Review row ${original.section}:${original.index}`}>
        <label><input type="checkbox" checked={selected.has(key)} onChange={e=>{const next=new Set(selected);if(e.target.checked)next.add(key);else next.delete(key);setSelected(next);}} />Select {original.section}:{original.index}</label>
        <details><summary>{original.section}:{original.index} / {original.source_ticker??"unknown ticker"} / {original.source_name??"unknown name"} / {item.action||"no primary-row decision"}</summary><fieldset aria-label={`Row ${original.section}:${original.index}`}><legend>{original.section}:{original.index}</legend>
          <label>Primary row decision<select value={item.action} onChange={e=>editRow(key,{action:e.target.value as RowDraft["action"]})}><option value="">Unresolved / no primary decision</option><option value="include">Include equity</option><option value="exclude">Exclude with reason</option></select></label>
          <label>Decision reason<input value={item.reason} maxLength={256} onChange={e=>editRow(key,{reason:e.target.value})} /></label>
          <label>Canonical security ID<input value={item.security} maxLength={256} onChange={e=>editRow(key,{security:e.target.value})} /></label>
          <label>Security currency<input value={item.currency} maxLength={32} onChange={e=>editRow(key,{currency:e.target.value})} /></label>
          <label>Security asset type<input value={item.asset} maxLength={32} onChange={e=>editRow(key,{asset:e.target.value})} /></label>
          <label>Linked primary section<input value={item.targetSection} maxLength={256} onChange={e=>editRow(key,{targetSection:e.target.value})} /></label><label>Linked primary row index<input type="number" min="0" step="1" value={item.targetIndex} onChange={e=>editRow(key,{targetIndex:e.target.value})} /></label>
          <EvidenceFields title={`Row evidence ${original.section}:${original.index}`} value={item.evidence} onChange={evidence=>editRow(key,{evidence})} /><button type="button" onClick={()=>editRow(key,{evidence:{...fundEvidence}})}>Use fund evidence for this row</button>
        </fieldset></details>
      </article>;})}
      {page.length===0 && <p>No review rows match. All retained rows still participate in preview accounting.</p>}
      <button type="button" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>Previous review rows</button><button type="button" disabled={offset+20>=matching.length} onClick={()=>setOffset(offset+20)}>Next review rows</button>
      <p>Preview checks the existing review contract. Missing section/row decisions remain located blockers; contradictory metadata, stale evidence and unsupported identities cannot select a benchmark.</p>
      <button type="submit" disabled={!preparedReview && (!metadata || !metadataReviewed)}>Preview prepared benchmark review</button>
      {error && <p role="alert">{error}</p>}
    </fieldset></form>}
  </section>;
}
