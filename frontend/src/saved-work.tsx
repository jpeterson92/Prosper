import { useEffect, useState } from "react";
import type { Catalog, connect, Run, Worksheet } from "./client";
import { recordStatus } from "./presentation";
import { Help } from "./ui";
import { runContext,runName } from "./record-context";
type Item={id:string;kind:"run"|"worksheet";value:Run|Worksheet|null};
export function SavedWork({catalog,api,active,compact=false,onRun,onWorksheet}:{catalog:Catalog|null;api:()=>ReturnType<typeof connect>;active:boolean;compact?:boolean;onRun:(id:string)=>void;onWorksheet:(id:string)=>void}) {
  const [items,setItems]=useState<Item[]>([]),[cursor,setCursor]=useState({run:0,worksheet:0}),[previous,setPrevious]=useState<{run:number;worksheet:number}[]>([]),[loading,setLoading]=useState(false),[filter,setFilter]=useState("all");
  const ids=[...[...(catalog?.worksheets??[])].reverse().map(id=>({id,kind:"worksheet" as const})),...[...(catalog?.runs??[])].reverse().map(id=>({id,kind:"run" as const}))];
  const filtered=ids.filter(i=>filter==="all"||i.kind===filter),identity=JSON.stringify(filtered),limit=compact?4:20;
  useEffect(()=>{setCursor({run:0,worksheet:0});setPrevious([]);},[identity,compact]);
  useEffect(()=>{
    if(!active)return;let live=true;setLoading(true);setItems([]);
    const selected=[...filtered.filter(i=>i.kind==="worksheet").slice(cursor.worksheet,cursor.worksheet+limit),...filtered.filter(i=>i.kind==="run").slice(cursor.run,cursor.run+limit)];
    void api().then(async c=>Promise.all(selected.map(async item=>{try{return {...item,value:item.kind==="run"?await c.run(item.id):await c.worksheet(item.id)};}catch{return {...item,value:null};}}))).then(value=>{if(live)setItems(value.sort((a,b)=>{const date=(i:Item)=>i.value?(i.kind==="worksheet"?(i.value as Worksheet).saved_at:(i.value as Run).started_at):"\uffff";return date(b).localeCompare(date(a));}).slice(0,limit));}).catch(()=>{if(live)setItems(selected.map(item=>({...item,value:null})));}).finally(()=>{if(live)setLoading(false);});
    return()=>{live=false;};
  },[identity,cursor.run,cursor.worksheet,limit,active]);
  const next={run:cursor.run+items.filter(i=>i.kind==="run").length,worksheet:cursor.worksheet+items.filter(i=>i.kind==="worksheet").length};
  const hasNext=next.run<filtered.filter(i=>i.kind==="run").length||next.worksheet<filtered.filter(i=>i.kind==="worksheet").length;
  return <section aria-label={compact?"Recent work":"Saved work library"} className="saved-library"><div className="section-heading"><h2>{compact?"Recent work":"Saved analyses & worksheets"}</h2><Help label="About saved work">These are immutable dated records, with creation times shown separately from analysis dates. Recent entries are merged by creation time across analyses and worksheets. Opening work does not recalculate or change current holdings.</Help></div>
    {!compact&&<label className="library-filter">Show saved work<select aria-label="Saved work type" value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All saved work</option><option value="worksheet">Manual worksheets</option><option value="run">Analyses and input reviews</option></select></label>}{loading&&<p role="status">Reading saved work…</p>}{catalog&&!loading&&!ids.length&&<div className="empty-state"><h3>Your work will be here</h3><p>Save an input review or worksheet to return to its original dated result.</p></div>}
    {!loading&&ids.length>0&&filtered.length===0&&<p>No saved work matches this type. Choose another type to see existing records.</p>}
    <div className="saved-list">{items.map(item=>{const record=item.value,worksheet=item.kind==="worksheet"&&record?record as Worksheet:null,run=item.kind==="run"&&record?record as Run:null;return <button type="button" key={`${item.kind}:${item.id}`} className="saved-item" onClick={()=>item.kind==="worksheet"?onWorksheet(item.id):onRun(item.id)} disabled={!record}><span className="saved-item-icon" aria-hidden="true">{worksheet?"▤":"◷"}</span><span><strong>{worksheet?"Manual worksheet":run?runName(run):"Record unavailable"}</strong><small>{worksheet?`Analysis ${worksheet.analysis_date} · ${worksheet.lines[0]?.account_alias??"Saved account"}`:run?`${run.model_version==="benchmark-proxy-v1"?`Source ${runContext(run).source??"date unavailable"}`:`Analysis ${runContext(run).analysis??"date unavailable"}`} · ${recordStatus(run)}`:"Refresh to retry reading this record"}</small><small>{worksheet?`Saved ${worksheet.saved_at.slice(0,16).replace("T"," ")} UTC`:run?`Created ${run.started_at.slice(0,16).replace("T"," ")} UTC`:""}</small></span><span className="saved-arrow" aria-hidden="true">→</span></button>;})}</div>
    {!compact&&(hasNext||previous.length>0)&&<div className="pagination"><button className="secondary" disabled={!previous.length||loading} onClick={()=>{setCursor(previous[previous.length-1]!);setPrevious(previous.slice(0,-1));}}>Previous saved work</button><span>Page {previous.length+1}</span><button className="secondary" disabled={!hasNext||loading} onClick={()=>{setPrevious([...previous,cursor]);setCursor(next);}}>Next saved work</button></div>}
  </section>;
}
