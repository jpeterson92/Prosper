import { createContext, useContext, useEffect, useLayoutEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import type { Security } from "./client";
import { compactValue } from "./display";
import { warningGroups } from "./presentation";

export const SecurityLabels = createContext<Security[]>([]);
export function SecurityName({id}:{id:string}) {
  const securities=useContext(SecurityLabels),security=securities.find(s=>s.id===id);
  return <span>{security?.ticker??id}{security?.name?.value&&<small>{security.name.value}</small>}</span>;
}

export function Help({label,children,trigger}:{label:string;children:ReactNode;trigger?:ReactNode}) {
  const [open,setOpen]=useState(false),[position,setPosition]=useState({left:16,top:80}),root=useRef<HTMLSpanElement>(null),button=useRef<HTMLButtonElement>(null),popover=useRef<HTMLSpanElement>(null),id=useId();
  useEffect(()=>{
    if(!open)return;
    const outside=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setOpen(false);};
    document.addEventListener("pointerdown",outside);
    return()=>document.removeEventListener("pointerdown",outside);
  },[open]);
  useLayoutEffect(()=>{
    if(!open)return;const anchor=button.current?.getBoundingClientRect(),panel=popover.current?.getBoundingClientRect();
    if(anchor&&panel)setPosition({left:Math.max(16,Math.min(anchor.left,window.innerWidth-panel.width-16)),top:Math.max(16,Math.min(anchor.bottom+8,window.innerHeight-panel.height-16))});
    const dismiss=()=>setOpen(false);window.addEventListener("resize",dismiss);document.addEventListener("scroll",dismiss,true);
    return()=>{window.removeEventListener("resize",dismiss);document.removeEventListener("scroll",dismiss,true);};
  },[open]);
  return <span className="help" ref={root} onBlur={e=>{if(!e.currentTarget.contains(e.relatedTarget))setOpen(false);}} onKeyDown={e=>{if(e.key==="Escape"){setOpen(false);button.current?.focus();e.stopPropagation();}}}>
    <button type="button" className={trigger?"value-trigger":"help-trigger"} ref={button} aria-label={label} aria-expanded={open} aria-controls={id} onClick={()=>setOpen(!open)}>{trigger??"?"}</button>
    {open&&<span ref={popover} className="help-popover" style={position} id={id} role="note"><strong>{label.replace(/^About /,"")}</strong>{children}<button type="button" className="text-button" onClick={()=>{setOpen(false);button.current?.focus();}}>Close</button></span>}
  </span>;
}

export function DetailsPanel({title,children,label=title,dismissSignal}:{title:string;children:ReactNode;label?:string;dismissSignal?:unknown}) {
  const dialog=useRef<HTMLDialogElement>(null),id=useId();
  useEffect(()=>{dialog.current?.close();},[dismissSignal]);
  return <><button type="button" className="text-button detail-link" onClick={()=>dialog.current?.showModal()}>{label}<span aria-hidden="true"> ↗</span></button>
    <dialog className="detail-panel" ref={dialog} aria-labelledby={id} onClick={e=>{if(e.target===e.currentTarget)dialog.current?.close();}}>
      <div className="detail-sheet"><header><h2 id={id}>{title}</h2><button type="button" className="icon-button" aria-label={`Close ${title}`} onClick={()=>dialog.current?.close()}>×</button></header><div className="detail-body">{children}</div></div>
    </dialog></>;
}

export function ExactValue({value,kind="number",places}:{value:string|number|null|undefined;kind?:"number"|"money"|"weight";places?:number}) {
  if(value===null||value===undefined)return <span className="unknown">Unknown</span>;
  const raw=String(value);
  const display=compactValue(value,kind,places);
  return <span className="exact-value"><Help label={`${kind==="money"?"USD ":""}${display} - view exact value`} trigger={<span className="number">{kind==="money"?"$":""}{display}</span>}><span className="exact-original">{raw}</span><span>Display rounding does not change the source, saved amount or financial calculation.</span></Help></span>;
}

export function Icon({name}:{name:"overview"|"holdings"|"analysis"|"worksheets"|"settings"|"arrow"|"upload"|"check"}) {
  const paths={overview:"M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",holdings:"M4 20V10h4v10M10 20V4h4v16M16 20v-7h4v7M2 20h20",analysis:"M3 17l5-5 4 3 8-10M15 5h5v5",worksheets:"M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7",settings:"M4 6h16M4 12h16M4 18h16M8 3v6M16 9v6M10 15v6",arrow:"M4 12h16M14 6l6 6-6 6",upload:"M12 16V3M7 8l5-5 5 5M4 15v6h16v-6",check:"M5 12l4 4L19 6"};
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;
}

export const issueTitle=(code:string)=>({lot_mark_conflict:"Review updated prices",lot_settings_required:"Add cash and cost settings",settings_date_mismatch:"Review the analysis date",selected_snapshot_required:"Import your holdings",selected_benchmark_required:"Choose a benchmark",coverage_settings_required:"Confirm freshness settings",history_selection_required:"Choose imported market history",investor_controls_required:"Review investor limits",taxonomy_declaration_required:"Confirm the classification framework",source_declaration_required:"Confirm source permissions and dates",investor_control_unspecified:"Complete an investor limit",mark_missing:"A current price is missing",classification_unknown:"A classification needs review",empty_modeled_union:"No holdings have sufficient declared history",history_length_mismatch:"More market history is needed",identity_missing:"Confirm a security identity",history_context_ambiguous_or_missing:"Choose the matching history source"} as Record<string,string>)[code]??code.replaceAll("_"," ").replace(/^./,c=>c.toUpperCase());

export function Issues({issues}:{issues:readonly {code:string;reason:string;locator:string;scope:string;security_id?:string|null}[]}) {
  const groups=new Map<string,typeof issues[number][]>();
  for(const issue of issues)groups.set(issue.code,[...(groups.get(issue.code)??[]),issue]);
  return <div className="issue-list">{[...groups].map(([code,items])=><div className="issue-item" key={code}><span className="issue-dot" aria-hidden="true"/><div><strong>{issueTitle(code)}</strong><p>{items[0]?.reason}</p>{items.length>1&&<small>{items.length} affected items</small>}<DetailsPanel title={issueTitle(code)} label="View affected items">{items.map((i,n)=><div className="issue-detail" key={n}>{i.security_id&&<h3><SecurityName id={i.security_id}/></h3>}<p>{i.reason}</p><details><summary>Source details</summary><p>{i.scope} / {i.code}</p><p>{i.locator}</p></details></div>)}</DetailsPanel></div></div>)}</div>;
}


export function Warnings({values}:{values:readonly string[]}) {
  if(!values.length)return null;
  return <div className="warning-groups" aria-label="Assumptions and warnings">{warningGroups(values).map(([name,items])=><details key={name} open={name==="Coverage and exclusions"||items.some(value=>/unknown|incomplete|unverified|unavailable|missing/i.test(value))}><summary>{name} ({items.length})</summary><ul>{items.map((value,i)=><li key={i}>{value}</li>)}</ul></details>)}</div>;
}
