import { test, expect } from "@playwright/test";
import { readFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { runtime, root } from "../tools/runtime.mjs";

const dist = path.join(root, "frontend/dist");
const holdings = await readFile(path.join(root, "examples/synthetic/advisory-workspace.json"));
const history = await readFile(path.join(root, "examples/synthetic/history/current-refresh.json"));
const window = await readFile(path.join(root, "examples/synthetic/history/current-request.json"));
const status = page => page.getByRole("status", { name: "Workspace status" });
async function open(page, server) { await page.goto(server.origin); await expect(status(page)).toContainText("Workspace read"); }
async function seed(page) {
  await page.getByLabel("Normalized snapshot JSON file (up to 2 MiB)").setInputFiles({ name: "fictional.json", mimeType: "application/json", buffer: holdings });
  await page.getByRole("button", { name: "Stage preview" }).click(); await expect(status(page)).toContainText("Preview staged");
  await page.getByLabel("I reviewed this snapshot and its unknowns").check(); await page.getByRole("button", { name: "Select reviewed snapshot" }).click(); await expect(status(page)).toContainText("revision 1");
}
async function readWindow(page) {
  await expect(page.getByLabel("Required history window JSON")).toBeEnabled();
  await page.getByLabel("Required history window JSON").setInputFiles({ name: "window.json", mimeType: "application/json", buffer: window });
  await expect(page.getByRole("button", { name: "Plan missing history" })).toBeVisible();
}
async function reviewHistory(page) {
  await expect(page.getByLabel("History file (up to 64 MiB; staged in bounded parts)")).toBeEnabled();
  await page.getByLabel("History file (up to 64 MiB; staged in bounded parts)").setInputFiles({ name: "history.json", mimeType: "application/json", buffer: history });
  await expect(page.getByText(/8 observations;/)).toBeVisible();
  await page.getByLabel("I reviewed the history source and conventions").check();
}
async function api(server, route) {
  const token = await server.session(); const result = await fetch(server.origin + route, { headers: { Origin: server.origin, Authorization: `Bearer ${token}` } });
  expect(result.ok).toBe(true); return result.json();
}

test("manual plans, refresh, ordered saved inputs and source recovery share the current workspace", async ({ page }) => {
  const source = await runtime({ dist }); const target = await runtime({ dist });
  try {
    await open(page, source); await seed(page); await readWindow(page);
    const coverage = page.getByRole("article", { name: "History coverage" });
    await page.getByRole("button", { name: "Plan missing history" }).click();
    await expect(coverage).toContainText("new-name"); await expect(coverage).toContainText("Required history incomplete");
    await reviewHistory(page); await page.getByRole("button", { name: "Refresh from reviewed source" }).click(); await expect(status(page)).toContainText("revision 2");
    await page.getByRole("button", { name: "Plan missing history" }).click(); await expect(coverage).toContainText("Required retained observations complete");
    await page.getByLabel("Selected security IDs for manual refresh").fill("security-a");
    await page.getByRole("button", { name: "Plan selected-name refresh" }).click(); await expect(coverage).toContainText("security-a: manual"); await expect(coverage).not.toContainText("security-b: manual");
    await page.getByRole("button", { name: "Plan full-window refresh" }).click(); await expect(coverage).toContainText("security-b: manual");
    await page.getByRole("button", { name: "Save history diagnostics" }).click(); await expect(status(page)).toContainText("history diagnostics saved");
    const current = await api(source, "/api/v1/current"); const saved = await api(source, `/api/v1/runs/${current.current_run_id}`);
    expect(saved.outputs.coverage_complete).toBe(true); expect(saved.outputs.ordered_securities).toEqual(["security-b", "security-a"]); expect(saved.outputs.financial_metrics).toBeNull();
    expect(saved.inputs.alignment_ref).toMatch(/^[a-f0-9]{64}$/);
    expect((await api(source, `/api/v1/input-records/${saved.inputs.alignment_ref}`)).rows.row_count).toBe(6);
    const savedView = page.getByRole("article", { name: "Saved diagnostic" });
    await savedView.getByText("Inspect all retained history rows (6)", { exact: true }).click();
    await expect(savedView.getByRole("table")).toBeVisible();
    await expect(savedView).toContainText("Rows 1-6 of 6");
    await expect(savedView.getByRole("columnheader", { name: "source ref", exact: true })).toBeVisible();
    await page.getByLabel("Remove reusable history cache; keep all saved-run inputs and outputs").check();
    await page.getByRole("button", { name: "Clear reusable history cache" }).click(); await expect(status(page)).toContainText("revision 3");
    await page.getByRole("button", { name: "Plan missing history" }).click(); await expect(coverage).toContainText("Required history incomplete");
    expect(await api(source, `/api/v1/runs/${current.current_run_id}`)).toEqual(saved);
    const pendingDownload = page.waitForEvent("download"); await page.getByRole("button", { name: "Download workspace backup" }).click(); const download = await pendingDownload;
    const bytes = await readFile(await download.path());
    await open(page, target);
    await page.getByLabel("Current workspace backup (up to 64 MiB)").setInputFiles({ name: "current.sqlite3", mimeType: "application/octet-stream", buffer: bytes });
    await page.getByRole("button", { name: "Restore into empty workspace" }).click(); await expect(status(page)).toContainText("restored");
    expect(await api(target, `/api/v1/runs/${current.current_run_id}`)).toEqual(saved);
    await page.getByRole("combobox", { name: "Saved diagnostic", exact: true }).selectOption(current.current_run_id);
    await expect(page.getByRole("article", { name: "Saved diagnostic" })).toContainText("history-inputs-v1");
    await mkdir(path.join(root, ".local/t019.4"), { recursive: true });
    await page.screenshot({ path: path.join(root, ".local/t019.4/recovered-history-desktop.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: path.join(root, ".local/t019.4/recovered-history-narrow.png"), fullPage: true });
  } finally { await source.stop(); await target.stop(); }
});

test("lost refresh response retries identical data without another revision", async ({ page }) => {
  const server = await runtime({ dist });
  try {
    await open(page, server); await seed(page); await expect(page.getByLabel("History file (up to 64 MiB; staged in bounded parts)")).toBeEnabled(); await reviewHistory(page);
    const bodies = []; let first = true;
    await page.route("**/api/v1/history/refresh", async route => { bodies.push(route.request().postData()); if (first) { first = false; await route.fetch(); await route.abort(); } else await route.continue(); });
    await page.getByRole("button", { name: "Refresh from reviewed source" }).click(); await expect(page.getByRole("button", { name: "Retry identical action" })).toBeVisible();
    await page.getByRole("button", { name: "Retry identical action" }).click(); await expect(status(page)).toContainText("revision 2");
    expect(bodies).toHaveLength(2); expect(bodies[0] === bodies[1]).toBe(true); expect((await api(server, "/api/v1/current")).revision).toBe(2);
  } finally { await server.stop(); }
});

test("malformed history and request files fail safely without changing selected work", async ({ page }) => {
  const server = await runtime({ dist });
  try {
    await open(page, server); await seed(page); const before = await api(server, "/api/v1/current");
    for (const label of ["History file (up to 64 MiB; staged in bounded parts)", "Required history window JSON"]) {
      await expect(page.getByLabel(label)).toBeEnabled();
      await page.getByLabel(label).setInputFiles({ name: "invalid.json", mimeType: "application/json", buffer: Buffer.from('{"sensitive-key":"do-not-echo"}') });
      await expect(page.getByRole("alert")).toContainText("invalid");
      expect(await api(server, "/api/v1/current")).toEqual(before);
      await expect(page.locator("body")).not.toContainText("do-not-echo");
    }
    await expect(page.getByRole("button", { name: "Save source diagnostics" })).toBeEnabled();
  } finally { await server.stop(); }
});


test("lost part response, restart and pending-source recovery do not activate inputs", async ({page})=>{
  let source=await runtime({dist});const target=await runtime({dist});
  try {
    await open(page,source);await seed(page);
    await expect(page.getByLabel("History file (up to 64 MiB; staged in bounded parts)")).toBeEnabled();
    let lost=true;
    await page.route("**/api/v1/history/parts",async route=>{if(lost){lost=false;await route.fetch();await route.abort();}else await route.continue();});
    await page.getByLabel("History file (up to 64 MiB; staged in bounded parts)").setInputFiles({name:"history.json",mimeType:"application/json",buffer:history});
    await expect(page.getByRole("alert")).toBeVisible();
    expect((await api(source,"/api/v1/current")).revision).toBe(1);
    const catalog=await api(source,"/api/v1/catalog");expect(catalog.pending_history_parts).toHaveLength(1);
    await page.unroute("**/api/v1/history/parts");
    const directory=source.directory;await source.stop();source=await runtime({dist,directory});
    await open(page,source);await expect(page.getByText(/1 pending history parts retained/)).toBeVisible();
    const downloaded=page.waitForEvent("download");await page.getByRole("button",{name:"Download workspace backup"}).click();
    const bytes=await readFile(await (await downloaded).path());
    await open(page,target);await page.getByLabel("Current workspace backup (up to 64 MiB)").setInputFiles({name:"pending.sqlite3",mimeType:"application/octet-stream",buffer:bytes});
    await page.getByRole("button",{name:"Restore into empty workspace"}).click();await expect(status(page)).toContainText("restored");
    expect((await api(target,"/api/v1/catalog")).pending_history_parts).toEqual(catalog.pending_history_parts);
    await page.getByRole("button",{name:"Discard pending history parts"}).click();await expect(page.getByText(/0 pending history parts retained/)).toBeVisible();
    expect((await api(target,"/api/v1/current")).revision).toBe(1);
    await open(page,source);await reviewHistory(page);await page.getByLabel("I reviewed the history source and conventions").check();await page.getByRole("button",{name:"Refresh from reviewed source"}).click();await expect(status(page)).toContainText("revision 2");
    expect((await api(source,"/api/v1/catalog")).pending_history_parts).toEqual([]);
  } finally {await source.stop();await target.stop();}
});

test("duplicate local history keys refuse before staging",async({page})=>{
  const server=await runtime({dist});
  try {
    await open(page,server);await seed(page);
    await expect(page.getByLabel("History file (up to 64 MiB; staged in bounded parts)")).toBeEnabled();
    const raw=history.toString("utf8").replace('"part_count":','"part_count":99,"part_count":');
    await page.getByLabel("History file (up to 64 MiB; staged in bounded parts)").setInputFiles({name:"duplicate.json",mimeType:"application/json",buffer:Buffer.from(raw)});
    await expect(page.getByRole("alert")).toContainText("invalid");
    expect((await api(server,"/api/v1/catalog")).pending_history_parts).toEqual([]);
    expect((await api(server,"/api/v1/current")).revision).toBe(1);
  }finally{await server.stop();}
});


test("protected history inspection pages retained source rows without activation", async ({ page }) => {
  const server = await runtime({ dist });
  try {
    await open(page, server); await seed(page);
    await expect(page.getByLabel("History file (up to 64 MiB; staged in bounded parts)")).toBeEnabled();
    const file = await readFile(path.join(root, "examples/synthetic/candidates/application/history.json"));
    await page.getByLabel("History file (up to 64 MiB; staged in bounded parts)").setInputFiles({name:"rows.json",mimeType:"application/json",buffer:file});
    const part = page.getByRole("article", {name:"History source part 1",exact:true});
    await part.getByText(/Inspect all retained history rows/).click();
    await expect(part).toContainText("Rows 1-20 of");
    await expect(part.locator("tbody tr")).toHaveCount(20);
    const first = await part.locator("tbody").innerText();
    await part.getByRole("button",{name:"Next history rows"}).click();
    await expect(part).toContainText("Rows 21-40 of");
    await expect(part.locator("tbody tr")).toHaveCount(20);
    expect(await part.locator("tbody").innerText()).not.toBe(first);
    await part.getByRole("button",{name:"Previous history rows"}).click();
    await expect(part).toContainText("Rows 1-20 of");
    expect(await part.locator("tbody").innerText()).toBe(first);
    expect((await api(server,"/api/v1/current")).revision).toBe(1);
  } finally { await server.stop(); }
});
