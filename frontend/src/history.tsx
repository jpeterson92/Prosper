import { useEffect, useState } from "react";
import { connect } from "./client";
import type { Run } from "./client";
import type { components } from "./generated/api";

type Table = components["schemas"]["HistoryTable"];
type Page = components["schemas"]["HistoryRowsPage"];

export function HistoryRows({ table }: { table: Table }) {
  const [expanded, setExpanded] = useState(false);
  const [received, setPage] = useState<{table: Table; rows: Page} | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState(false);
  useEffect(() => { setOffset(0); }, [table.data]);
  useEffect(() => {
    setPage(null); setError(false);
    if (!expanded) return;
    let active = true;
    void connect().then(client => client.historyRows({table, offset, limit: 20})).then(value => {
      if (active) setPage({table, rows: value});
    }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [table, offset, expanded]);
  const page = received?.table === table && received.rows.offset === offset ? received.rows : null;
  const end = Math.min(offset + 20, table.row_count);
  return <details onToggle={event => setExpanded(event.currentTarget.open)}><summary>Inspect all retained history rows ({table.row_count})</summary>
    {error && <p role="alert">Unable to read this retained history table.</p>}
    {!page && !error && <p>Reading retained rows...</p>}
    {page && <><p>Rows {table.row_count ? offset + 1 : 0}-{end} of {table.row_count}. Empty values are explicit unknowns; reasons and source row locators are retained.</p>
      <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous history rows</button>
      <button disabled={end === table.row_count} onClick={() => setOffset(end)}>Next history rows</button>
      <div className="table-scroll" tabIndex={0}><table><thead><tr>{page.columns.map(name => <th key={name}>{name.replaceAll("_", " ")}</th>)}</tr></thead><tbody>
        {page.rows.map((row, index) => <tr key={offset + index}>{page.columns.map((name, column) => <td key={name}>{row[column] === null ? name.endsWith("_reason") ? "-" : "Unknown" : String(row[column])}</td>)}</tr>)}
      </tbody></table></div></>}
  </details>;
}

export function SavedHistory({ run }: { run: Run }) {
  const modeled = run.inputs.modeled_inputs;
  const facts = modeled && typeof modeled === "object" && !Array.isArray(modeled) ? modeled as Record<string, unknown> : null;
  const reference = typeof run.inputs.alignment_ref === "string" ? run.inputs.alignment_ref
    : facts && typeof facts.alignment_ref === "string" ? facts.alignment_ref : null;
  const [table, setTable] = useState<Table | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true; setTable(null); setError(false);
    if (reference) void connect().then(client => client.historyInput(reference)).then(value => {
      if (active) setTable(value.rows);
    }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [reference]);
  return <>{error && <p role="alert">Saved history input is unavailable.</p>}{table && <HistoryRows table={table} />}</>;
}
