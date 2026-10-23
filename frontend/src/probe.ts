import source from "../../examples/synthetic/F001.json?raw";
import { connect } from "./client";
import type { Preview } from "./client";

function requireFact(condition: unknown): asserts condition {
  if (!condition) throw new Error("transport_check_failed");
}

function known(preview: Preview, text = "90", quantum = "1") {
  requireFact(preview.planning_ready === false);
  const basis = preview.inspection?.total_basis;
  requireFact(basis?.state === "known" && basis.value === "2181");
  const cash = preview.inspection?.cash[0]?.settled;
  requireFact(cash?.state === "known" && cash.value === "319");
  const nav = preview.inspection?.settled_cash_nav;
  requireFact(nav?.state === "known" && nav.value === "2399");
  const price = preview.source?.source_values.find((value) => value.path.join(".") === "quotes.0.price.value");
  requireFact(price?.exact.value === "90" && price.exact.original_text === text && price.exact.source_quantum === quantum);
}

/** Fixed fictional fixtures only. No file upload UI, financial formatting or commit controls. */
export async function runProbe(origin = window.location.origin): Promise<number> {
  const client = await connect(origin);
  const before = await client.current();
  const raw = new TextEncoder().encode(source);
  const preview = await client.stage(raw);
  const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", raw))]
    .map((byte) => byte.toString(16).padStart(2, "0")).join("");
  requireFact(preview.receipt.raw_sha256 === digest && preview.receipt.byte_length === raw.length);
  known(preview);
  known(await client.preview(digest));
  const precise = JSON.parse(source);
  precise.quotes[0].price.value = "90.00";
  known(await client.stage(new TextEncoder().encode(JSON.stringify(precise))), "90.00", "0.01");
  // The JSON document is synthetic source data, not the authority for financial calculations.
  const incomplete = JSON.parse(source);
  incomplete.metadata.bundle_id = "F004-BROWSER";
  incomplete.lots[1].basis = { value: null, reason: "synthetic_missing_basis" };
  const unknown = await client.stage(new TextEncoder().encode(JSON.stringify(incomplete)));
  requireFact(unknown.inspection?.total_basis.state === "unknown");
  requireFact(unknown.inspection.total_basis.value === null);
  requireFact(unknown.inspection.total_basis.reasons.includes("synthetic_missing_basis"));
  const after = await client.current();
  requireFact(JSON.stringify(before) === JSON.stringify(after));
  if (after.checkpoint) {
    requireFact(after.generation > 0);
    const basis = after.checkpoint.inspection.total_basis;
    requireFact(basis.state === "known" && basis.value === "2181");
  } else { requireFact(after.generation === 0); }
  return after.generation;
}
