import { useEffect, useState } from "react";
import type { Run, connect, Preview, Worksheet } from "./client";
import { DetailsPanel } from "./ui";

export function field(value:unknown,...keys:string[]):unknown {
  for(const key of keys) {
    if(!value||typeof value!=="object"||Array.isArray(value))return undefined;
    value=(value as Record<string,unknown>)[key];
  }
  return value;
}
const text=(value:unknown)=>typeof value==="string"&&value?value:null;
export function runContext(run:Run) {
  const bundle=field(run.inputs,"modeled_request","bundle"),search=field(run.outputs,"search","inputs");
  const snapshot=field(search,"snapshot")??field(run.inputs,"candidate_inputs","snapshot");
  return {
    analysis:text(field(bundle,"analysis_date"))??text(field(search,"settings","analysis_date"))??(run.model_version==="lot-opportunities-v1"?text(field(run.settings,"lot_opportunities","analysis_date")):null),
    source:text(field(snapshot,"source_as_of"))??(run.model_version==="benchmark-proxy-v1"?text(field(run.outputs,"effective_date")):null),
    account:text(field(snapshot,"account_alias")),
    benchmark:text(field(run.inputs,"modeled_inputs","benchmark","ticker"))??text(field(run.outputs,"ticker")),
  };
}
export const runName=(run:Run)=>({"candidate-workflow-v1":"Proposal comparison","modeled-inputs-v1":"Input review","lot-opportunities-v1":"Loss opportunities","benchmark-proxy-v1":"Benchmark review","history-inputs-v1":"Market history review","source-quality-v1":"Holdings review"}[run.model_version]??"Saved analysis");

export function RecordContext({run,worksheet,api}:{run:Run;worksheet:Worksheet|null;api:()=>ReturnType<typeof connect>}) {
  const [source,setSource]=useState<Preview|null>(null),[reading,setReading]=useState(true),[benchmark,setBenchmark]=useState<string|null>(null);
  useEffect(()=>{
    let live=true;setSource(null);setBenchmark(null);setReading(true);
    void api().then(async c=>{
      const id=run.settings.benchmark_run_id;
      const [source,benchmark]=await Promise.allSettled([c.preview(run.snapshot_id),typeof id==="string"?c.run(id):Promise.resolve(null)]);
      if(live){if(source.status==="fulfilled")setSource(source.value);if(benchmark.status==="fulfilled"&&benchmark.value)setBenchmark(text(field(benchmark.value.outputs,"ticker")));}
    }).catch(()=>{}).finally(()=>{if(live)setReading(false);});
    return()=>{live=false;};
  },[run.id,run.snapshot_id]);
  const context=runContext(run);
  return <header role="region" className="record-context" aria-label="Original saved context"><span className="badge">Saved record · exploratory estimate</span><h2>{worksheet?"Manual worksheet":runName(run)}</h2>
    <dl className="facts"><div><dt>Original account</dt><dd>{context.account??source?.snapshot.account_alias??(reading?"Reading original account…":"Unavailable in saved context")}</dd></div><div><dt>Analysis date</dt><dd>{worksheet?.analysis_date??context.analysis??"Unavailable in saved record"}</dd></div><div><dt>Holdings source date</dt><dd>{worksheet?.source_as_of??context.source??source?.snapshot.source_as_of??"Unavailable in saved record"}</dd></div></dl>
    <p>Original benchmark: {context.benchmark??benchmark??"Unavailable; original reference in details"}. {worksheet?"Saved":"Created"} {(worksheet?.saved_at??run.started_at).slice(0,16).replace("T"," ")} UTC.</p>
    <DetailsPanel title="Original record references" label="Original references and knowledge time"><p>Knowledge time: {run.as_of}. Input revision: {run.input_revision}.</p><p>Run: {run.id}; snapshot: {run.snapshot_id}; benchmark: {String(run.settings.benchmark_run_id??"Unavailable")}.</p></DetailsPanel>
  </header>;
}
