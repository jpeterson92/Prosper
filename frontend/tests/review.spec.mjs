import { dismissDetails, navigate, reveal, advancedImport, savedRecords, historyTools, workspaceTools, prepareUpload, sourceDetails } from "../tools/workspace.mjs";
test.beforeEach(({page})=>page.setDefaultTimeout(10000));
import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { runtime, root, python } from "../tools/runtime.mjs";
import { compactValue, decimalDisplay, percentPreview } from "../src/display.ts";

const raw = await readFile(path.join(root, "examples/synthetic/advisory-workspace.json"));
const dist = path.join(root, "frontend/dist");
const status = (page) => page.getByRole("status", { name: "Workspace status" });
async function open(page, server) {
  await page.goto(server.origin);await advancedImport(page);
  await expect(status(page)).toContainText("Workspace read.", { timeout: 15000 });
}
async function stage(page, bytes = raw) {
  await prepareUpload(page,"Normalized snapshot JSON file (up to 2 MiB)");await page.getByLabel("Normalized snapshot JSON file (up to 2 MiB)").setInputFiles({ name: "fictional.json", mimeType: "application/json", buffer: bytes });
  await page.getByRole("button", { name: "Stage preview", exact: true }).click();
  await expect(status(page)).toContainText("Preview staged");
}
async function select(page) {
  await page.getByLabel("I reviewed this snapshot and its unknowns").check();
  await page.getByRole("button", { name: "Select reviewed snapshot" }).click();
  await expect(status(page)).toContainText("Action result: changed");
}
async function api(server, route, body) {
  const token = await server.session();
  const response = await fetch(server.origin + route, { method: body ? "POST" : "GET", headers: { Origin: server.origin, Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) });
  expect(response.ok).toBe(true); return response.json();
}

test("percentage previews shift decimal text without changing precision or units",()=>{
  for(const [raw,expected]of [["0.015","1.5%"],["1.0000","100%"],["0","0%"],["-0.0001","-0.01%"],["9007199254740993.0001","900,719,925,474,099,300.01%"],["1e-3","Enter a decimal fraction"]])expect(percentPreview(raw)).toBe(expected);
});

test("compact amounts preserve signs below the displayed precision", () => {
  for(const [value,kind,expected] of [["0.00001","number","<0.0001"],["-0.00001","number",">-0.0001"],["0.001","money","<0.01"],["-0.001","money",">-0.01"],[0.000001,"weight","<0.01%"],[-0.000001,"weight",">-0.01%"],[0,"weight","0%"],["-2.355","money","-2.36"]]) expect(compactValue(value,kind)).toBe(expected);
});

test("display rounding preserves independently specified signs, ties and large integers", () => {
  for (const [value, expected] of [["2.345", "2.34"], ["2.355", "2.36"], ["-2.355", "-2.36"], ["9.999", "10.00"], ["0.005", "0.00"], ["9007199254740993.125", "9,007,199,254,740,993.12"]]) expect(decimalDisplay(value, true)).toBe(expected);
});

test("normalized review, explicit settings and immutable dated diagnostics survive restart", async ({ page, context }) => {
  let server = await runtime({ dist });
  const directory = server.directory;
  const errors = [], foreign = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== server.origin || url.search) { foreign.push(url.pathname); await route.abort(); } else await route.continue();
  });
  try {
    await open(page, server);
    await stage(page);
    const review = page.getByRole("article", { name: "Snapshot review" });
    await expect(review).toContainText("12.5000");
    await expect(review).toContainText("basis not supplied");
    await expect(review).toContainText("row:2");
    expect((await api(server, "/api/v1/current")).snapshot_id).toBeNull();
    await page.getByLabel("Round displayed numeric values to 2 decimals").check();
    await expect(review).toContainText("12.50");
    await select(page);
    await workspaceTools(page);await page.getByRole("textbox", {name:"Settings JSON",exact:true}).fill('{"additional_cash":"100.00","risk_enabled":false}');
    await page.getByLabel("I reviewed these settings").check();
    await page.getByRole("button", { name: "Save reviewed settings" }).click();
    await expect(status(page)).toContainText("revision 2");
    await savedRecords(page);await page.getByRole("button", { name: "Save source diagnostics" }).click();
    await expect(status(page)).toContainText("Dated source diagnostics saved");
    const saved = page.getByRole("article", { name: "Saved diagnostic" });
    await expect(saved).toContainText('"financial_metrics": null');
    await expect(saved).toContainText("lots/lot-a/total_basis");
    await expect(saved).toContainText("unsupported_tax_class");
    const before = await api(server, "/api/v1/current");
    const id = before.current_run_id;
    const original = await api(server, `/api/v1/runs/${id}`);
    const results = path.join(root, ".local/t019.6"); await mkdir(results, { recursive: true });
    await page.screenshot({ path: path.join(results, "workspace-desktop.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(results, "workspace-narrow.png"), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.evaluate(() => [Object.keys(localStorage), localStorage.getItem("prosper-appearance"), sessionStorage.length, document.cookie])).toEqual([["prosper-appearance"], "system", 0, ""]);
    await server.stop(); server = await runtime({ dist, directory });
    await open(page, server);
    expect(await api(server, "/api/v1/current")).toEqual(before);
    await savedRecords(page);await page.getByRole("combobox", { name: "Saved diagnostic", exact: true }).selectOption(id);
    await expect(saved).toContainText("100.00");
    expect(await api(server, `/api/v1/runs/${id}`)).toEqual(original);
    expect(errors).toEqual([]); expect(foreign).toEqual([]);
  } finally { await server.stop(); }
});

for (const kind of ["select", "settings", "diagnostics"]) {
  test(`lost ${kind} response retries its identical durable request`, async ({ page }) => {
    const server = await runtime({ dist });
    try {
      await open(page, server); await stage(page);
      if (kind !== "select") await select(page);
      const bodies = []; let first = true;
      await page.route(`**/api/v1/${kind}`, async (route) => {
        bodies.push(route.request().postData());
        if (first) { first = false; await route.fetch(); await route.abort(); } else await route.continue();
      });
      if (kind === "select") {
        await page.getByLabel("I reviewed this snapshot and its unknowns").check();
        await page.getByRole("button", { name: "Select reviewed snapshot" }).click();
      } else if (kind === "settings") {
        await workspaceTools(page);await page.getByRole("textbox", {name:"Settings JSON",exact:true}).fill('{"selected_cash":"42.00"}');
        await page.getByLabel("I reviewed these settings").check();
        await page.getByRole("button", { name: "Save reviewed settings" }).click();
      } else {await savedRecords(page);await page.getByRole("button", { name: "Save source diagnostics" }).click();}
      await expect(page.getByRole("button", { name: "Retry identical action" })).toBeVisible();
      await page.getByRole("button", { name: "Retry identical action" }).click();
      await expect(page.getByRole("button", { name: "Retry identical action" })).toHaveCount(0);
      expect(bodies.length).toBe(2); expect(bodies[0] === bodies[1]).toBe(true);
      const current = await api(server, "/api/v1/current");
      expect(current.revision).toBe(kind === "settings" ? 2 : 1);
      expect((await api(server, "/api/v1/catalog")).runs.length).toBe(kind === "diagnostics" ? 1 : 0);
    } finally { await server.stop(); }
  });
}

test("two windows cannot replace newer settings using a stale reviewed revision", async ({ page, context }) => {
  const server = await runtime({ dist });
  try {
    await open(page, server); await stage(page); await select(page);
    const other = await context.newPage(); await open(other, server);
    await workspaceTools(other);await other.getByRole("textbox", {name:"Settings JSON",exact:true}).fill('{"selected_cash":"25.00"}');
    await other.getByLabel("I reviewed these settings").check();
    await other.getByRole("button", { name: "Save reviewed settings" }).click();
    await expect(status(other)).toContainText("revision 2");
    await workspaceTools(page);await page.getByRole("textbox", {name:"Settings JSON",exact:true}).fill('{"selected_cash":"99.00"}');
    await page.getByLabel("I reviewed these settings").check();
    await page.getByRole("button", { name: "Save reviewed settings" }).click();
    await expect(status(page)).toContainText("stale_revision");
    expect((await api(server, "/api/v1/current")).settings).toEqual({ selected_cash: "25.00" });
    await other.close();
  } finally { await server.stop(); }
});

test("download, clean restore and lost restore response preserve saved output and sources", async ({ page }) => {
  const source = await runtime({ dist }); const target = await runtime({ dist });
  try {
    await open(page, source); await stage(page); await select(page);
    await savedRecords(page);await page.getByRole("button", { name: "Save source diagnostics" }).click();
    await expect(status(page)).toContainText("diagnostics saved");
    const before = await api(source, "/api/v1/current");
    const downloadPromise = page.waitForEvent("download");
    await navigate(page,"Settings");await page.getByRole("button", { name: "Download workspace backup" }).click();
    const download = await downloadPromise; const bytes = await readFile(await download.path());
    await open(page, target);
    let first = true;
    await page.route("**/api/v1/restore", async (route) => {
      if (first) { first = false; await route.fetch(); await route.abort(); } else await route.continue();
    });
    await prepareUpload(page,"Current workspace backup (up to 64 MiB)");await page.getByLabel("Current workspace backup (up to 64 MiB)").setInputFiles({ name: "current.sqlite3", mimeType: "application/octet-stream", buffer: bytes });
    await page.getByRole("button", { name: "Restore into empty workspace" }).click();
    await expect(page.getByRole("button", { name: "Retry identical action" })).toBeVisible();
    await page.getByRole("button", { name: "Retry identical action" }).click();
    await expect(status(page)).toContainText("restored");
    expect(await api(target, "/api/v1/current")).toEqual(before);
    expect(await api(target, `/api/v1/runs/${before.current_run_id}`)).toEqual(await api(source, `/api/v1/runs/${before.current_run_id}`));
    await navigate(page,"Holdings");await page.getByRole("button", { name: "Review current holdings" }).click();
    await expect(page.getByRole("article", { name: "Snapshot review" })).toContainText("12.5000");
  } finally { await source.stop(); await target.stop(); }
});

test("invalid replacement and refused restore keep selected work usable", async ({ page }) => {
  const server = await runtime({ dist });
  try {
    await open(page, server); await stage(page); await select(page);
    const before = await api(server, "/api/v1/current");
    await prepareUpload(page,"Normalized snapshot JSON file (up to 2 MiB)");await page.getByLabel("Normalized snapshot JSON file (up to 2 MiB)").setInputFiles({ name: "bad.json", mimeType: "application/json", buffer: Buffer.from('{"secret":"do-not-echo"}') });
    await page.getByRole("button", { name: "Stage preview" }).click();
    await expect(page.getByRole("alert")).toContainText("invalid");
    expect(await api(server, "/api/v1/current")).toEqual(before);
    await prepareUpload(page,"Current workspace backup (up to 64 MiB)");await page.getByLabel("Current workspace backup (up to 64 MiB)").setInputFiles({ name: "corrupt.sqlite3", mimeType: "application/octet-stream", buffer: Buffer.from("corrupt") });
    await page.getByRole("button", { name: "Restore into empty workspace" }).click();
    await expect(status(page)).toContainText("Action refused");
    await expect(page.getByRole("button", { name: "Retry identical action" })).toHaveCount(0);
    await savedRecords(page);await expect(page.getByRole("button", { name: "Save source diagnostics" })).toBeEnabled();
    expect(await api(server, "/api/v1/current")).toEqual(before);
    await expect(page.locator("body")).not.toContainText("do-not-echo");
  } finally { await server.stop(); }
});


for (const kind of ["non-json", "unsafe-revision"]) {
  test(`unusable ${kind} state blocks mutation controls`, async ({ page }) => {
    const server = await runtime({ dist });
    try {
      await page.route("**/api/v1/current", (route) => route.fulfill({ status: 200,
        contentType: kind === "non-json" ? "text/plain" : "application/json",
        body: kind === "non-json" ? "unusable" : '{"revision":9007199254740993,"snapshot_id":null,"settings":{},"current_run_id":null}',
      }));
      await page.goto(server.origin);await advancedImport(page);
      await expect(page.getByRole("alert")).toContainText("local request failed");
      await expect(page.getByRole("button", { name: "Stage preview" })).toBeDisabled();
      await workspaceTools(page);await expect(page.getByRole("button", { name: "Save reviewed settings" })).toBeDisabled();
    } finally { await server.stop(); }
  });
}


test("an interrupted saved diagnostic can resume from its frozen inputs", async ({ page }) => {
  const directory = path.join(root, ".local/t019.6", randomUUID());
  const code = `
import sys
from pathlib import Path
from prosper.storage import RuntimeBoundary
from prosper.advisory_store import AdvisoryStore
from prosper.workspace import Workspace
from prosper.api_contracts import Upload
root=Path(sys.argv[1]); directory=Path(sys.argv[2])
s=AdvisoryStore(RuntimeBoundary(directory))
p=Workspace(s).stage(Upload.model_validate_json((root/'examples/synthetic/advisory-workspace.json').read_bytes()))
s.select(p.id,'seed',0)
s.start_run('interrupted',1,inputs={'diagnostic':'source-quality-v1'},application_version='prosper-advisory-v1',model_version='source-quality-v1',as_of='2026-10-25T20:00:00Z')
`;
  execFileSync(python, ["-I", "-c", code, root, directory], { windowsHide: true });
  const server = await runtime({ dist, directory });
  try {
    await open(page, server);
    await savedRecords(page);await page.getByRole("combobox", { name: "Saved diagnostic", exact: true }).selectOption("interrupted");
    await expect(page.getByRole("article", { name: "Saved diagnostic" })).toContainText("running");
    await page.getByRole("button", { name: "Resume saved diagnostic" }).click();
    await expect(page.getByRole("article", { name: "Saved diagnostic" })).toContainText("partial");
    expect((await api(server, "/api/v1/catalog")).runs).toEqual(["interrupted"]);
    expect((await api(server, "/api/v1/current")).current_run_id).toBe("interrupted");
  } finally { await server.stop(); }
});


test("a successful write with a failed state read preserves the known outcome and requires refresh", async ({ page }) => {
  const server = await runtime({ dist });
  try {
    await open(page, server); await stage(page);
    await page.route("**/api/v1/current", (route) => route.fulfill({ status: 503, contentType: "application/json", body: '{"error":"unavailable"}' }));
    await page.getByLabel("I reviewed this snapshot and its unknowns").check();
    await page.getByRole("button", { name: "Select reviewed snapshot" }).click();
    await expect(status(page)).toContainText("Action result: changed");
    await expect(page.getByRole("alert")).toContainText("Current state could not be refreshed");
    await expect(page.getByRole("button", { name: "Retry identical action" })).toHaveCount(0);
    await savedRecords(page);await expect(page.getByRole("button", { name: "Save source diagnostics" })).toBeDisabled();
    expect((await api(server, "/api/v1/current")).revision).toBe(1);
    await page.unroute("**/api/v1/current");
    await dismissDetails(page);await page.getByRole("button", { name: "Refresh workspace" }).click();
    await expect(status(page)).toContainText("Workspace read");
    await savedRecords(page);await expect(page.getByRole("button", { name: "Save source diagnostics" })).toBeEnabled();
  } finally { await server.stop(); }
});
