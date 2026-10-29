import { useEffect, useState } from "react";
import { InvestorSettings } from "./investor-settings";
import { DetailsPanel, ExactValue, Help, SecurityName } from "./ui";
import type { connect, Current, LotDiagnosticRequest, LotResult, LotSettings, LotSettingsRequest, Preview, Run, Security } from "./client";

export type LotAction = { kind: "lot-settings"; body: LotSettingsRequest } | { kind: "lot-diagnostic"; body: LotDiagnosticRequest };
type API = Awaited<ReturnType<typeof connect>>;
type Estimate = { value: number | null; reason?: string | null };
const money = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
function Amount({ fact }: { fact: Estimate }) {
  return fact.value === null ? <span className="unknown">Unavailable <small>{fact.reason}</small></span> : <span className="number" title={`Unrounded estimate: ${fact.value}`}>{money.format(fact.value)}</span>;
}

export function LotView({ run }: { run: Run }) {
  if (run.outputs?.kind !== "lot-opportunities-v1") return null;
  const result = run.outputs as unknown as LotResult;
  return <section aria-label="Lot opportunity results">
    <h3>Conditional lot estimates</h3><p>Each row is an isolated hypothetical sale. Price/basis loss and net-proceeds P&amp;L are different estimates. Display rounding does not change saved values.</p>
    <p>Computed conditional price-loss subtotal (USD): <Amount fact={result.conditional_price_loss_subtotal} />. This subtotal covers the conditional rows shown; blocked and unavailable lots remain in the table.</p>
    <div className="table-scroll" tabIndex={0}><table><thead><tr><th>Lot / security / source</th><th>Held quantity / proposed whole shares</th><th>Term</th><th>Allocated basis (USD)</th><th>Price/basis loss (USD)</th><th>Net proceeds / indicative tax P&amp;L (USD)</th><th>Status and blockers</th></tr></thead><tbody>{result.rows.map(row => <tr key={row.lot_id}>
      <th><SecurityName id={row.security_id}/><DetailsPanel title="Lot and source details"><p>Lot {row.lot_id}</p><p>{row.source_ref}</p></DetailsPanel></th>
      <td>{row.quantity.value ?? "Unknown"}<small>{row.quantity.reason}</small><p>{row.proposed_whole_shares ?? "No available whole-share portion"}</p><small>Remaining: {row.remaining_quantity ?? "Unavailable"}</small></td>
      <td>{row.term.value ?? "Unknown"}<small>{row.term.reason}</small></td><td><Amount fact={row.allocated_basis} /></td><td><Amount fact={row.price_basis_loss} /></td><td><Amount fact={row.indicative_net_proceeds} /><small>Tax P&amp;L estimate</small><Amount fact={row.indicative_tax_pnl} /><small>Modeled cost</small><Amount fact={row.modeled_cost} /></td>
      <td>{row.status}<ul>{row.blockers.map((reason, i) => <li key={i}>{reason}</li>)}</ul>{row.warnings.map((warning, i) => <small key={i}>{warning}</small>)}</td>
    </tr>)}</tbody></table></div>
    {result.buy_screens.length > 0 && <><h3>Requested replacement screens</h3><ul>{result.buy_screens.map(row => <li key={row.security_id}>{row.security_id}: {row.status}<ul>{row.blockers.map((b,i) => <li key={i}>{b}</li>)}</ul></li>)}</ul></>}
    <p>No orders, deductible-loss clearance, tax-dollar savings or validated suggestions are produced.</p>
  </section>;
}

export function LotControls({ current, disabled, api, onPreview, onMutate, preparedMarks = [] }: { current: Current | null; disabled: boolean; api: () => Promise<API>; onPreview: (preview: Preview) => void; onMutate: (command: LotAction) => void; preparedMarks?: LotSettings["marks"] }) {
  const [csv, setCsv] = useState<File | null>(null);
  const [context, setContext] = useState<File | null>(null);
  const [sourceAccount, setSourceAccount] = useState("");
  const [sourceDate, setSourceDate] = useState("");
  const [recordedAt, setRecordedAt] = useState(new Date().toISOString());
  const [cfg, setCfg] = useState<LotSettings | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [securities, setSecurities] = useState<Security[]>([]);
  const [name, setName] = useState("");
  const [resolved, setResolved] = useState("");
  const [quantities, setQuantities] = useState("{}");
  const [buys, setBuys] = useState("");
  useEffect(() => { setReviewed(false); }, [current?.revision]);
  const locked = disabled || loading;
  async function read(action: () => Promise<void>) {
    if (loading) return; setLoading(true); setError(null);
    try { await action(); } catch { setError("The lot source/context or settings request is invalid or unavailable. Check its schema, checksum and reviewed facts; no selection was changed."); }
    finally { setLoading(false); }
  }
  function update(value: LotSettings) { setCfg(value); setReviewed(false); }
  return <section aria-label="Source-shaped lot workflow">
    {error && <p role="alert">{error}</p>}<p role="status" aria-label="Lot input status">{message}</p>
    <details open={!current?.snapshot_id}><summary>{current?.snapshot_id?"Import refreshed holdings":"Import holdings file"}</summary><h2>Import holdings</h2>
    <p>Choose a combined lot CSV, then review your holdings before selecting the snapshot.<Help label="About supported holdings files">The current importer supports a Fidelity-shaped combined-lot export for one U.S. taxable USD account. Original rows and amounts are retained; missing identity, basis or activity facts stay explicit.</Help></p>
    <div className="upload-area" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(!locked){const file=e.dataTransfer.files[0];if(file){setCsv(file);setRecordedAt(new Date().toISOString());}}}}><label>Holdings file (.csv)<input aria-label="Declared combined-lot CSV" disabled={locked} type="file" accept=".csv" onChange={e => {setCsv(e.target.files?.[0] ?? null); setRecordedAt(new Date().toISOString());}} /></label><small>{csv?csv.name:"Drop a CSV here or choose a file"}</small></div>
    <label>Source account identifier<input disabled={locked} value={sourceAccount} onChange={e=>setSourceAccount(e.target.value)} /></label>
    <label>Source snapshot date<input type="date" disabled={locked} value={sourceDate} onChange={e=>setSourceDate(e.target.value)} /></label>
    <details><summary>Advanced reviewed context (optional)</summary><label>Reviewed lot context JSON<input disabled={locked} type="file" accept=".json" onChange={e => setContext(e.target.files?.[0] ?? null)} /></label></details>
    <button disabled={locked || !csv || (!context && (!sourceAccount.trim() || !sourceDate))} onClick={() => void read(async () => {
      if (!csv || csv.size > 2 * 1024 * 1024 || (context && context.size > 2 * 1024 * 1024)) throw new Error("source_limit");
      const bytes = new Uint8Array(await csv.arrayBuffer()); let binary = "";
      for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
      const client = await api();
      const result = context ? await client.stageFidelity(btoa(binary), await context.text()) : await client.openFidelity({source_base64:btoa(binary),source_account:sourceAccount,source_as_of:sourceDate,account_alias:"Selected taxable account",currency:"USD",recorded_at:recordedAt});
      setMessage(result.issues.length ? `Source findings: ${result.issues.map(i => `${i.code} at record ${i.record ?? "unknown"} / ${i.column ?? "source"}`).join("; ")}` : "Source-shaped preview staged. Review the source and unknowns before selecting it.");
      if (result.preview) onPreview(result.preview);
    })}>Review imported holdings</button>
    </details><InvestorSettings value={cfg} current={current} disabled={locked} api={api} onPrepared={(value,names)=>{update(value);setSecurities(names);setMessage("Cash and costs ready for explicit review; nothing has been saved.");}} onDirty={()=>{setReviewed(false);setCfg(null);}} preparedMarks={preparedMarks}/>
    <details><summary>Advanced settings file import</summary><label>Explicit lot settings JSON<input disabled={locked} type="file" accept=".json" onChange={e => {
      const file = e.target.files?.[0]; if (file) void read(async () => {
        if (file.size > 2 * 1024 * 1024) throw new Error("settings_limit");
        const client = await api(); update(await client.previewLotSettings(`{"settings":${await file.text()}}`));
        const state = await client.current(); if (state.snapshot_id) setSecurities((await client.preview(state.snapshot_id)).snapshot.securities);
        setMessage("Lot settings loaded for review; current settings are unchanged.");
      });
    }} /></label></details>
    {cfg && <>
      <div className="cash-review"><h3>Review your cash and cost settings</h3><p>Analysis date {cfg.analysis_date}. Additional cash budget USD <ExactValue value={cfg.cash_to_invest}/>.</p><p>Selling fee USD {cfg.sell_fee_per_isolated_order.value??"Unknown"}; price discount {cfg.sell_discount_bps.value??"Unknown"} bps. Funding: {cfg.funding_assumption.value??cfg.funding_assumption.reason}.</p><p>Final cash target: {cfg.final_cash_target.enabled?`USD ${cfg.final_cash_target.amount??"Unknown"}, tolerance ${cfg.final_cash_target.investor_tolerance??"Unknown"}`:"Explicitly disabled"}.</p><label><input disabled={locked} type="checkbox" checked={cfg.cash_budget_reviewed} onChange={e=>update({...cfg,cash_budget_reviewed:e.target.checked})}/>I reviewed the selected cash budget; it is separate from imported balances</label><p>{cfg.history_coverage.value??cfg.history_coverage.reason}</p></div>
      <label>Recent or restricted name<input disabled={locked} value={name} onChange={e => setName(e.target.value)} /></label>
      <label>Explicit reviewed security mapping<select disabled={locked} value={resolved} onChange={e => setResolved(e.target.value)}><option value="">Unresolved name</option>{securities.map(s => <option key={s.id} value={s.id}>{s.ticker} / {s.id}</option>)}</select></label>
      <button disabled={locked || !name.trim()} onClick={() => { const security = securities.find(s => s.id === resolved); update({ ...cfg, manual_restrictions: [...(cfg.manual_restrictions ?? []), { name: name.trim(), identity: security?.identity ?? { value: null, reason: "Manual name has no reviewed security mapping" }, source_ref: "Reviewed manual name input", start: null, end: null, side: "both" }] }); setName(""); }}>Add restriction on both legs</button>
      <ul>{cfg.manual_restrictions?.map((restriction, i) => <li key={i}>{restriction.name} / {restriction.identity.value ?? "Unresolved - affected scope blocked"}<button disabled={locked} onClick={() => update({ ...cfg, manual_restrictions: cfg.manual_restrictions!.filter((_, index) => index !== i) })}>Remove manual restriction {i + 1}</button></li>)}</ul>
      <p>Removing a manual entry cannot clear known imported or retained conflicts. Names are never resolved from ticker text alone.</p>
      <details><summary>Review all lot settings and supplied activity</summary><pre>{JSON.stringify(cfg, null, 2)}</pre></details>
      <label><input disabled={locked} type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I reviewed the lot marks, costs, coverage and funding settings</label>
      <button disabled={locked || !reviewed} onClick={() => onMutate({ kind: "lot-settings", body: { settings: cfg, command_key: crypto.randomUUID(), expected_revision: current!.revision } })}>Save reviewed lot settings</button>
    </>}
    <details><summary>Advanced lot inspection controls</summary>
    <label>Optional whole-share portions by lot ID (JSON)<textarea rows={3} disabled={locked} value={quantities} onChange={e => setQuantities(e.target.value)} /></label>
    <label>Replacement security IDs to screen (comma separated)<input disabled={locked} value={buys} onChange={e => setBuys(e.target.value)} /></label>
    <p>Without an explicit portion, each lot is inspected separately using its available whole shares. Fractional remainders stay in holdings. Explicit portions and replacement IDs are screened for same-batch conflicts; no trade is proposed.</p>
    </details>
    <button disabled={locked || !current?.snapshot_id} onClick={() => {
      try { const values: unknown = JSON.parse(quantities); if (values === null || Array.isArray(values) || typeof values !== "object" || !Object.values(values).every(v => typeof v === "number" && Number.isSafeInteger(v) && v > 0)) throw new Error("quantities_invalid");
        onMutate({ kind: "lot-diagnostic", body: { run_id: crypto.randomUUID(), expected_revision: current!.revision, as_of: new Date().toISOString(), sale_quantities: values as Record<string, number>, replacement_security_ids: buys.split(",").map(v => v.trim()).filter(Boolean) } });
      } catch { setError("Lot portions must be a JSON object of lot IDs and positive safe whole-share integers."); }
    }}>Save loss opportunity review</button>
  </section>;
}
