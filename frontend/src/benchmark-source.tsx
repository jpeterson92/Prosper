import { useEffect, useState } from "react";
import type { BenchmarkObservation, BenchmarkSourcePage, connect } from "./client";

type Api = () => ReturnType<typeof connect>;
type Filters = { section: string; query: string; issue: string; offset: number };
type Cell = BenchmarkSourcePage["rows"][number]["cells"][number];

function value(cell: Cell | undefined) {
  if (!cell) return <span className="unknown">Absent</span>;
  if (cell.kind === "null") return <span className="unknown">Null (unknown)</span>;
  if (cell.kind === "string" && cell.value === "") return <span className="unknown">Blank (unknown)</span>;
  return <span className="source-value">{cell.value}</span>;
}

export function BenchmarkSourceView({ observation, api }: { observation: BenchmarkObservation; api: Api }) {
  const [filters, setFilters] = useState<Filters>({ section: "", query: "", issue: "", offset: 0 });
  const [draft, setDraft] = useState({ section: "", query: "", issue: "" });
  const [page, setPage] = useState<BenchmarkSourcePage | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true); setError(false); setPage(null);
    void (async () => {
      try {
        const result = await (await api()).benchmarkRows(observation.request.observation_id, filters);
        if (active) setPage(result);
      } catch { if (active) setError(true); }
      finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
    // The caller supplies a session factory each render; identity/filters own this read.
  }, [observation.request.observation_id, filters, retry]);
  return <section aria-label="Retained source diagnostics">
    <h3>Retained source diagnostics</h3>
    <p>Inspect original disclosed values before supplying a reviewed mapping. Source rows can include alternate representations; their count is not an economic holding count. Published percentages are source facts; no analysis-date drift or benchmark weights are calculated here.</p>
    <p>Blank, null and absent fields remain unknown. A supplied dash stays visible as “-”; it is a source placeholder, never a zero. Expand a row to inspect every field and its type.</p>
    <dl className="source-facts"><dt>Provider</dt><dd>{observation.request.ticker === "IVV" || observation.request.ticker === "ITOT" ? "BlackRock iShares" : "Vanguard"}</dd><dt>Requested holdings date</dt><dd>{observation.request.requested_date ?? "Latest reported"}</dd><dt>Reported holdings date</dt><dd>{observation.effective_date ?? "Unavailable"}</dd><dt>Collected at</dt><dd>{observation.collected_at}</dd><dt>Response</dt><dd>HTTP {observation.http_status ?? "unavailable"}; {observation.content_type ?? "unknown content type"}; {observation.body_complete ? "complete body" : "incomplete body"}</dd><dt>Source URL</dt><dd>{observation.response_url ?? "Unavailable"}</dd><dt>Source SHA-256</dt><dd>{observation.source_sha256 ?? "Unavailable"}</dd></dl>
    {loading && <p role="status">Reading retained source rows…</p>}
    {error && <><p role="alert">Retained source rows could not be read. No empty source is assumed.</p><button onClick={() => setRetry(n => n + 1)}>Retry source inspection</button></>}
    {page && <>
      {!page.rows_available && <p>Source rows unavailable for this {observation.status} observation. No benchmark or empty holdings are inferred.</p>}
      {page.rows_available && <><h4>Source sections</h4><ul>{Object.entries(page.section_counts).map(([name, count]) => <li key={name}>{name}: {count} source rows</li>)}</ul><p>{page.total_rows} total source rows across retained sections.</p></>}
      <h4>Acquisition issues</h4>
      {page.issue_groups.length === 0 ? <p>No acquisition issues reported. This does not establish financial completeness.</p> : <div className="table-scroll"><table><caption>Grouped acquisition issues</caption><thead><tr><th>Issue</th><th>Occurrences</th><th>Located rows</th><th>Original details</th></tr></thead><tbody>{page.issue_groups.map(group => <tr key={group.code}><th>{group.code}</th><td>{group.occurrences}</td><td>{group.affected_rows}</td><td><details><summary>Inspect issue locations</summary><ul>{group.details.map((detail, i) => <li key={i}>{detail}</li>)}</ul></details></td></tr>)}</tbody></table></div>}
      {page.rows_available && <>
        <form onSubmit={e => { e.preventDefault(); setFilters({ ...draft, offset: 0 }); }}>
          <label>Source section<select value={draft.section} onChange={e => setDraft({ ...draft, section: e.target.value })}><option value="">All sections</option>{Object.entries(page.section_counts).map(([name, count]) => <option key={name} value={name}>{name} ({count})</option>)}</select></label>
          <label>Search original source fields<input type="search" maxLength={200} value={draft.query} onChange={e => setDraft({ ...draft, query: e.target.value })} /></label>
          <label>Located source issue<select value={draft.issue} onChange={e => setDraft({ ...draft, issue: e.target.value })}><option value="">All rows</option>{page.issue_groups.map(group => <option key={group.code} value={group.code}>{group.code} ({group.affected_rows} located rows)</option>)}</select></label>
          <button type="submit">Apply source filters</button><button type="button" onClick={() => { setDraft({section:"", query:"", issue:""}); setFilters({section:"", query:"", issue:"", offset:0}); }}>Clear source filters</button>
        </form>
        <p role="status">{page.matched_rows} matching source rows of {page.total_rows}; showing {page.rows.length ? page.offset + 1 : 0}–{page.offset + page.rows.length}.</p>
        {page.rows.length === 0 ? <p>No source rows match these filters. An empty section or search result does not mean an empty benchmark.</p> : <div className="table-scroll"><table><caption>Original retained source rows</caption><thead><tr><th>Locator</th><th>Source identity</th><th>Market value</th><th>Published percentage</th><th>All fields</th><th>Located issues</th></tr></thead><tbody>{page.rows.map(row => {
          const supplied = row.cells.filter(c => c.origin === "source");
          const find = (...names: string[]) => supplied.find(c => names.includes(c.name));
          return <tr key={`${row.section}:${row.index}`}><th>{row.section}:{row.index}{row.source_ref && <p>{row.source_ref}</p>}</th><td>{[{label:"Ticker", cell:find("Ticker", "ticker")}, {label:"Name", cell:find("Name", "holdingName")}, {label:"CUSIP", cell:find("cusip", "CUSIP")}].map(({label, cell}) => <p key={label}>{label}: {value(cell)}</p>)}</td><td>{value(find("Market Value", "marketValue"))}</td><td>{value(find("Market Weight", "Weight (%)", "percentOfFunds"))}</td><td><details><summary>Inspect {row.cells.length} fields</summary><table><caption>{row.section}:{row.index} field values</caption><thead><tr><th>Field</th><th>Exact value</th><th>Type / origin</th></tr></thead><tbody>{row.cells.map(cell => <tr key={cell.name}><th>{cell.name}</th><td>{value(cell)}</td><td>{cell.kind} / {cell.origin === "adapter" ? "adapter alias or locator" : "source"}</td></tr>)}</tbody></table></details></td><td>{row.issues.length ? <ul>{row.issues.map(detail => <li key={detail}>{detail}</li>)}</ul> : "No located issue reported"}</td></tr>;
        })}</tbody></table></div>}
        <button disabled={page.offset === 0} onClick={() => setFilters({ ...filters, offset: Math.max(0, page.offset - page.limit) })}>Previous source rows</button><button disabled={page.matched_rows === null || page.offset + page.limit >= page.matched_rows} onClick={() => setFilters({ ...filters, offset: page.offset + page.limit })}>Next source rows</button>
      </>}
    </>}
  </section>;
}
