import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Help, Icon } from "./ui";
export type Page="overview"|"holdings"|"analysis"|"worksheets"|"settings";
export type Stage="benchmark"|"review"|"proposals";
export const pages:[Page,string][]=[["overview","Overview"],["holdings","Holdings"],["analysis","Analysis"],["worksheets","Worksheets"],["settings","Settings"]];
export const stages:[Stage,string][]=[["benchmark","Benchmark"],["review","Review inputs"],["proposals","Proposals"]];
export function AppShell({page,stage,onNavigate,onStage,onRefresh,refreshing,loading,unavailable,account,date,children}:{page:Page;stage:Stage;onNavigate:(page:Page)=>void;onStage:(stage:Stage)=>void;onRefresh:()=>void;refreshing:boolean;loading:boolean;unavailable:boolean;account:string|null;date:string|null;children:ReactNode}) {
  const [appearance,setAppearance]=useState(()=>{try{return localStorage.getItem("prosper-appearance")??"system";}catch{return "system";}});
  useEffect(()=>{document.documentElement.dataset.appearance=["light","dark"].includes(appearance)?appearance:"system";try{localStorage.setItem("prosper-appearance",appearance);}catch{/* Appearance remains usable without storage. */}},[appearance]);
  return <div className="app-shell">
    <a className="skip-link" href="#workspace-content">Skip to workspace</a>
    <aside className="app-sidebar"><a className="brand" href="#overview" onClick={e=>{e.preventDefault();onNavigate("overview");}}><span className="brand-mark" aria-hidden="true">p</span>prosper<span className="brand-dot"/></a>
      <div className="workspace-identity"><span className="local-indicator"/>Local workspace<small>Private to this computer</small></div>
      <nav aria-label="Main navigation">{pages.filter(([id])=>id!=="settings").map(([id,label])=><button type="button" key={id} aria-current={page===id?"page":undefined} onClick={()=>onNavigate(id)}><Icon name={id}/>{label}</button>)}</nav>
      <div className="sidebar-bottom"><button type="button" aria-current={page==="settings"?"page":undefined} onClick={()=>onNavigate("settings")}><Icon name="settings"/>Settings</button></div>
    </aside>
    <div className="app-workspace"><header className="app-toolbar"><div className="account-context"><span>{loading?"Reading workspace...":unavailable?"Workspace unavailable":account??"No holdings selected"}</span><small>{loading?"Reading selected holdings":unavailable?"Refresh to read current holdings":date?`Current holdings - ${date.slice(0,10)}`:"Import a snapshot to begin"}</small></div><div className="toolbar-end"><button type="button" className="icon-button refresh-button" aria-label="Refresh workspace" disabled={refreshing} onClick={onRefresh}>↻</button><span className="qualification">Exploratory only<Help label="About financial-use status">These estimates are not approved for financial use. Independent tax/model review, source qualification and calibration remain separate requirements. No trades are placed.</Help></span></div></header>
      <main id="workspace-content"><header className="page-heading"><div><h1 tabIndex={-1}>{pages.find(([id])=>id===page)?.[1]}</h1></div></header>
        {page==="analysis"&&<nav className="analysis-stages" aria-label="Analysis stages">{stages.map(([id,label],i)=><button type="button" key={id} aria-current={stage===id?"step":undefined} onClick={()=>onStage(id)}><span>{i+1}</span>{label}</button>)}</nav>}
        {page==="settings"&&<section className="appearance-settings"><h2>Appearance</h2><p>Use your system preference or choose an appearance.</p><label className="appearance-control"><span className="sr-only">Appearance</span><select aria-label="Appearance" value={appearance} onChange={e=>setAppearance(e.target.value)}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label></section>}
        {children}
      </main>
    </div>
  </div>;
}
