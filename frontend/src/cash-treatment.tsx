import type { CashTreatmentRequest, Current, Preview } from "./client";

export type CashAction = { kind: "cash-treatment"; body: CashTreatmentRequest };

export function CashTreatments({preview,current,disabled,onMutate}:{preview:Preview;current:Current|null;disabled:boolean;onMutate:(action:CashAction)=>void}) {
  const selected=current?.snapshot_id===preview.id;
  function apply(security_id:string,kind:CashTreatmentRequest["kind"]) {
    if(!current || !selected)return;
    onMutate({kind:"cash-treatment",body:{snapshot_id:preview.id,security_id,kind,command_key:crypto.randomUUID(),expected_revision:current.revision}});
  }
  return <section aria-label="Personal cash treatment"><h3>Cash and cash equivalent treatment</h3>
    <p>Mark an unmapped or unsupported holding as Cash or Cash equivalent, for example a money-market fund. This saves your classification for this source holding and keeps it outside stock trades and equity history. Original rows, source findings and known restrictions remain retained.</p>
    <p>Reported values below are shown once per holding. They do not set the amount selected for investment, prove buying power or redeem a fund. Missing or contradictory values stay unknown.</p>
    {!selected && <p>Select this reviewed snapshot before applying a treatment.</p>}
    {(preview.cash_holdings??[]).map(row=><article key={row.security_id} aria-label={`Holding treatment ${row.security_id}`}>
      <h4>{row.name.value??row.ticker} / {row.ticker}</h4>
      <p>Reported value ({row.currency}), as of {preview.snapshot.source_as_of}: {row.reported_value.value===null?<span className="unknown">Unknown — {row.reported_value.reason}</span>:<span className="number">{row.reported_value.value}</span>}</p>
      <p>Effective treatment: {row.treatment?.kind==="cash"?"Cash":row.treatment?.kind==="cash-equivalent"?"Cash equivalent":"Original source treatment; unresolved stock facts remain"}</p>
      {row.treatment && <p>{row.treatment.assertion}. Recorded {row.treatment.recorded_at}.</p>}
      <div className="cash-treatment-actions"><button disabled={disabled || !selected || row.treatment?.kind==="cash"} onClick={()=>apply(row.security_id,"cash")}>Mark as Cash</button>
      <button disabled={disabled || !selected || row.treatment?.kind==="cash-equivalent"} onClick={()=>apply(row.security_id,"cash-equivalent")}>Mark as Cash equivalent</button>
      <button disabled={disabled || !selected || !row.treatment} onClick={()=>apply(row.security_id,null)}>Undo cash treatment</button></div>
      <details><summary>Original holding references</summary><p>{preview.snapshot.account_id} / {row.security_id}</p><ul>{row.source_refs.map(ref=><li key={ref}>{ref}</li>)}</ul></details>
    </article>)}
    {preview.cash_holdings?.length===0 && <p>No unmapped or unsupported personal holdings require cash treatment.</p>}
  </section>;
}
