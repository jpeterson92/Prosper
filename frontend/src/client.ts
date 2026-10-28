import createClient from "openapi-fetch";
import type { paths, components } from "./generated/api";

export type Current = components["schemas"]["CurrentResponse"];
export type Preview = components["schemas"]["PreviewResponse"];
export type SelectRequest = components["schemas"]["SelectRequest"];
export type SettingsRequest = components["schemas"]["SettingsRequest"];
export type CashTreatmentRequest = components["schemas"]["CashTreatmentRequest"];
export type HoldingsMappingRequest = components["schemas"]["HoldingsMappingRequest"];
export type DiagnosticRequest = components["schemas"]["DiagnosticRequest"];
export type Run = components["schemas"]["AnalysisRun"];
export type Catalog = components["schemas"]["CatalogResponse"];
export type HistoryManifest = components["schemas"]["HistoryManifest"];
export type HistoryReview = { manifest: HistoryManifest; parts: components["schemas"]["HistoryPartReceipt"][] };
export type HistoryRequest = components["schemas"]["HistoryRequest"];
export type HistoryDiagnosticRequest = components["schemas"]["HistoryDiagnosticRequest"];
export type Alignment = components["schemas"]["Alignment"];
export type LotSettings = components["schemas"]["LotSettings"];
export type LotSettingsRequest = components["schemas"]["LotSettingsRequest"];
export type LotDiagnosticRequest = components["schemas"]["LotDiagnosticRequest"];
export type LotResult = components["schemas"]["LotResult"];
export type Security = Preview["snapshot"]["securities"][number];
export type BenchmarkFetch = components["schemas"]["BenchmarkFetch"];
export type BenchmarkObservation = components["schemas"]["BenchmarkObservation"];
export type BenchmarkImport = components["schemas"]["BenchmarkImport"];
export type BenchmarkDiagnostic = components["schemas"]["BenchmarkDiagnostic"];
export type BenchmarkSelect = components["schemas"]["BenchmarkSelect"];
export type BenchmarkReview = components["schemas"]["BenchmarkReview"];
export type BenchmarkResult = components["schemas"]["BenchmarkResult"];
export type BenchmarkSourcePage = components["schemas"]["BenchmarkSourcePage"];
export type BenchmarkReviewContext = components["schemas"]["BenchmarkReviewContext"];
export type ModeledUpload = components["schemas"]["ModeledUpload"];
export type ModeledResult = components["schemas"]["ModeledResult"];
export type ModeledDiagnostic = components["schemas"]["ModeledDiagnostic"];
export type CandidateStart = components["schemas"]["CandidateStart"];
export type CandidateOutput = components["schemas"]["CandidateOutput"];
export type Worksheet = components["schemas"]["Worksheet"];
export type WorksheetSave = components["schemas"]["WorksheetSave"];
export type WorksheetCheck = components["schemas"]["WorksheetCheck"];
export type WorksheetPreview = components["schemas"]["WorksheetPreview"];
type Upload = components["schemas"]["Upload"];

export class ClientError extends Error {
  constructor(readonly status?: number, readonly code?: string) { super("local_request_failed"); }
}
function revision(value: number) {
  if (!Number.isSafeInteger(value) || value < 0) throw new ClientError();
}
function data<T>(result: { data?: T; response: Response; error?: unknown }): T {
  if (result.data === undefined) {
    const error = result.error;
    const code = typeof error === "object" && error !== null && "error" in error && typeof error.error === "string" ? error.error : undefined;
    throw new ClientError(result.response.status, code);
  }
  return result.data;
}

// JSON.parse alone discards duplicate object keys before the server can reject
// them. Check the local history file's object keys while skipping string bodies.
function historyDocument(raw: string): Record<string, unknown> {
  const value: unknown = JSON.parse(raw);
  const objects: (Set<string> | null)[] = [];
  for (let i = 0; i < raw.length; i++) {
    const c = raw[i];
    if (c === "{" || c === "[") objects.push(c === "{" ? new Set() : null);
    else if (c === "}" || c === "]") objects.pop();
    else if (c === '"') {
      const start = i++;
      while (i < raw.length && raw[i] !== '"') { if (raw[i] === "\\") i++; i++; }
      let next = i + 1; while (/\s/.test(raw[next] ?? "x")) next++;
      if (raw[next] === ":") {
        const key = JSON.parse(raw.slice(start, i + 1)) as string;
        const keys = objects.at(-1);
        if (!keys || keys.has(key)) throw new ClientError(422);
        keys.add(key);
      }
    }
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new ClientError(422);
  return value as Record<string, unknown>;
}

/** Session remains in this closure; only the trusted launcher's origin is accepted. */
export async function connect(origin = window.location.origin) {
  const url = new URL(origin);
  if (url.origin !== origin || url.protocol !== "http:" || url.hostname !== "127.0.0.1" || !url.port) throw new ClientError();
  const response = await fetch(`${origin}/session`, {
    method: "POST", headers: { "X-Prosper-Bootstrap": "1" }, credentials: "omit", cache: "no-store",
  });
  if (!response.ok) throw new ClientError(response.status);
  const session: unknown = await response.json();
  if (typeof session !== "object" || session === null || !("token" in session) || typeof session.token !== "string" || session.token.length < 43) throw new ClientError();
  const headers = { Authorization: `Bearer ${session.token}` };
  const client = createClient<paths>({ baseUrl: origin, credentials: "omit", cache: "no-store", headers });
  return {
    async runtime() { return data(await client.GET("/runtime")); },
    async current() {
      const result = data(await client.GET("/api/v1/current")); revision(result.revision); return result;
    },
    async treatCash(body: CashTreatmentRequest) { return data(await client.POST("/api/v1/holdings/cash-treatment", { body })); },
    async prepareHoldings(body: HoldingsMappingRequest) { return data(await client.POST("/api/v1/holdings/mapping-preview", { body })); },
    async startCandidate(body: CandidateStart) { return data(await client.POST("/api/v1/candidates/start", { body })); },
    async checkWorksheet(body: WorksheetCheck) { return data(await client.POST("/api/v1/worksheets/check", { body })); },
    async saveWorksheet(body: WorksheetSave) { return data(await client.POST("/api/v1/worksheets", { body })); },
    async worksheet(identity: string) { return data(await client.GET("/api/v1/worksheets/{identity}", { params: { path: { identity } } })); },
    async exportWorksheet(identity: string) {
      const response = await fetch(`${origin}/api/v1/worksheets/${encodeURIComponent(identity)}/export`, {headers,credentials:"omit",cache:"no-store"});
      if(!response.ok) throw new ClientError(response.status); return response.blob();
    },
    async cancelCandidate(body: {run_id: string}) { return data(await client.POST("/api/v1/candidates/cancel", { body })); },
    async openFidelity(body: components["schemas"]["FidelityOpening"]) { return data(await client.POST("/api/v1/fidelity/opening", { body })); },
    async stageFidelity(source_base64: string, context: string) {
      const raw = `{"source_base64":${JSON.stringify(source_base64)},"context":${context}}`;
      return data(await client.POST("/api/v1/fidelity/previews", { body: raw as unknown as components["schemas"]["FidelityUpload"], bodySerializer: value => value as unknown as string, headers: { "Content-Type": "application/json" } }));
    },
    async previewLotSettings(raw: string) {
      return data(await client.POST("/api/v1/lots/settings/preview", { body: raw as unknown as components["schemas"]["LotSettingsInput"], bodySerializer: value => value as unknown as string, headers: { "Content-Type": "application/json" } }));
    },
    async configureLots(body: LotSettingsRequest) { return data(await client.POST("/api/v1/lots/settings", { body })); },
    async diagnoseLots(body: LotDiagnosticRequest) { return data(await client.POST("/api/v1/lots/diagnostics", { body })); },
    async catalog() { return data(await client.GET("/api/v1/catalog")); },
    async stage(raw: string) {
      // Keep the original JSON body so duplicate keys reach the protected decoder.
      return data(await client.POST("/api/v1/previews", {
        body: raw as unknown as Upload, bodySerializer: (value) => value as unknown as string,
        headers: { "Content-Type": "application/json" },
      }));
    },
    async preview(identity: string) { return data(await client.GET("/api/v1/previews/{identity}", { params: { path: { identity } } })); },
    async select(body: SelectRequest) { revision(body.expected_revision); return data(await client.POST("/api/v1/select", { body })); },
    async configure(body: SettingsRequest) { revision(body.expected_revision); return data(await client.POST("/api/v1/settings", { body })); },
    async diagnose(body: DiagnosticRequest) { revision(body.expected_revision); return data(await client.POST("/api/v1/diagnostics", { body })); },
    async run(identity: string) { return data(await client.GET("/api/v1/runs/{identity}", { params: { path: { identity } } })); },
    async reject(identity: string) { return data(await client.POST("/api/v1/reject", { body: { snapshot_id: identity } })); },
    async backup() {
      const result = await fetch(`${origin}/api/v1/backup`, { headers, credentials: "omit", cache: "no-store" });
      if (!result.ok) throw new ClientError(result.status); return result.blob();
    },
    async restore(raw: Uint8Array<ArrayBuffer>) {
      return data(await client.POST("/api/v1/restore", { body: raw, bodySerializer: (value) => value, headers: { "Content-Type": "application/octet-stream" } }));
    },
    async refreshHistory(body: HistoryManifest) { return data(await client.POST("/api/v1/history/refresh", { body })); },
    async discardHistory(body: HistoryManifest) { return data(await client.POST("/api/v1/history/discard", { body })); },
    async previewHistory(raw: string): Promise<HistoryReview> {
      let document: Record<string, unknown>;
      try { document = historyDocument(raw); } catch { throw new ClientError(422); }
      if (Object.keys(document).some(k => !["version","part_count","parts","command_key","expected_revision"].includes(k)) || document.version !== "advisory-history-upload-v2" || !Array.isArray(document.parts) || document.part_count !== document.parts.length || document.parts.length < 1 || document.parts.length > 500) throw new ClientError(422);
      const parts: HistoryReview["parts"] = [];
      for (const part of document.parts) {
        parts.push(data(await client.POST("/api/v1/history/parts", { body: part as components["schemas"]["HistoryPart"] })));
      }
      const manifest: HistoryManifest = {version:"advisory-history-manifest-v1",part_count:parts.length,part_ids:parts.map(p=>p.id),command_key:crypto.randomUUID(),expected_revision:0};
      await client.POST("/api/v1/history/preview", {body:manifest}).then(data);
      return {manifest,parts};
    },
    async planHistoryDocument(raw: string) { return data(await client.POST("/api/v1/history/plan", { body: raw as unknown as { request: HistoryRequest }, bodySerializer: value => value as unknown as string, headers: { "Content-Type": "application/json" } })); },
    async historyRows(body: components["schemas"]["HistoryRowsRequest"]) { return data(await client.POST("/api/v1/history/rows", { body })); },
    async planHistory(request: HistoryRequest) { return data(await client.POST("/api/v1/history/plan", { body: { request } })); },
    async diagnoseHistory(body: HistoryDiagnosticRequest) { return data(await client.POST("/api/v1/history/diagnostics", { body })); },
    async historyInput(identity: string) { return data(await client.GET("/api/v1/input-records/{identity}", { params: { path: { identity } } })); },
    async clearHistory(body: { command_key: string; expected_revision: number }) { return data(await client.POST("/api/v1/history/clear", { body })); },
    async fetchBenchmark(body: BenchmarkFetch) { return data(await client.POST("/api/v1/benchmarks/fetch", { body })); },
    async importBenchmark(body: BenchmarkImport) { return data(await client.POST("/api/v1/benchmarks/import", { body })); },
    async benchmarkObservation(identity: string) { return data(await client.GET("/api/v1/benchmarks/observations/{identity}", { params: { path: { identity } } })); },
    async benchmarkRows(identity: string, filters: {section: string; query: string; issue: string; offset: number}) { return data(await client.POST("/api/v1/benchmarks/rows", {body: {observation_id: identity, ...filters, limit: 50}})); },
    async benchmarkReviewContext(observation_id: string) { return data(await client.POST("/api/v1/benchmarks/review-context", {body:{observation_id}})); },
    async prepareBenchmark(observation_id: string) { return data(await client.POST("/api/v1/benchmarks/prepare", {body:{observation_id}})); },
    async benchmarkSource(identity: string) {
      const response = await fetch(`${origin}/api/v1/benchmarks/observations/${encodeURIComponent(identity)}/source`, { headers, credentials: "omit", cache: "no-store" });
      if (!response.ok) throw new ClientError(response.status); return response.text();
    },
    async previewBenchmark(raw: string) { return data(await client.POST("/api/v1/benchmarks/review", { body: raw as unknown as BenchmarkReview, bodySerializer: value => value as unknown as string, headers: { "Content-Type": "application/json" } })); },
    async diagnoseBenchmark(body: BenchmarkDiagnostic) { return data(await client.POST("/api/v1/benchmarks/diagnostics", { body })); },
    async selectBenchmark(body: BenchmarkSelect) { return data(await client.POST("/api/v1/benchmarks/select", { body })); },
    async previewInputs(raw: string) { return data(await client.POST("/api/v1/inputs/preview", { body: raw as unknown as ModeledUpload, bodySerializer: value => value as unknown as string, headers: { "Content-Type": "application/json" } })); },
    async diagnoseInputs(body: ModeledDiagnostic) { return data(await client.POST("/api/v1/inputs/diagnostics", { body })); },
  };
}
