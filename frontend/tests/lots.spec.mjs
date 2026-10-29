import { dismissDetails, navigate, reveal, advancedImport, savedRecords, historyTools, workspaceTools, prepareUpload, sourceDetails } from "../tools/workspace.mjs";
test.beforeEach(({page})=>page.setDefaultTimeout(10000));
import { test, expect } from "@playwright/test";
import { readFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { runtime, root } from "../tools/runtime.mjs";

const dist = path.join(root, "frontend/dist");
const csv = await readFile(path.join(root, "examples/synthetic/fidelity/combined-stocks.csv"));
const context = await readFile(path.join(root, "examples/synthetic/fidelity/current-context.json"));
const settings = await readFile(path.join(root, "examples/synthetic/fidelity/current-lot-settings.json"));
const status = page => page.getByRole("status", { name: "Workspace status" });
async function open(page, server) { await page.goto(server.origin);await navigate(page,"Holdings"); await expect(status(page)).toContainText("Workspace read"); }
async function upload(page, label, buffer, mimeType = "application/json") { await prepareUpload(page,label);
  await expect(page.getByLabel(label, {exact:true})).toBeEnabled();
  await page.getByLabel(label, {exact:true}).setInputFiles({name: mimeType === "text/csv" ? "lots.csv" : "facts.json", mimeType, buffer});
}
async function seed(page) {
  await upload(page, "Declared combined-lot CSV", csv, "text/csv");
  await upload(page, "Reviewed lot context JSON", context);
  await page.getByRole("button", {name:"Review imported holdings"}).click();
  await expect(page.getByRole("article", {name:"Snapshot review"})).toBeVisible();
  await page.getByLabel("I reviewed this snapshot and its unknowns").check();
  await page.getByRole("button", {name:"Select reviewed snapshot"}).click();
  await expect(status(page)).toContainText("revision 1");
  await upload(page, "Explicit lot settings JSON", settings);
  await expect(page.getByRole("status", {name:"Lot input status"})).toContainText("Lot settings loaded");
}
async function saveSettings(page) {
  await expect(page.getByLabel("I reviewed the lot marks, costs, coverage and funding settings")).toBeEnabled();
  await page.getByLabel("I reviewed the lot marks, costs, coverage and funding settings").check();
  await page.getByRole("button", {name:"Save reviewed lot settings"}).click();
}
async function api(server, route) {
  const token=await server.session(); const response=await fetch(server.origin+route,{headers:{Origin:server.origin, Authorization:`Bearer ${token}`}});
  expect(response.ok).toBe(true); return response.json();
}

test("reviewed source lots show conditional losses, IRA conflicts and recovered immutable results", async ({page}) => {
  const source=await runtime({dist}); const target=await runtime({dist});
  try {
    await open(page,source); await seed(page); await saveSettings(page); await expect(status(page)).toContainText("revision 2");
    await page.getByRole("button", {name:"Save loss opportunity review", exact:true}).click();
    await expect(status(page)).toContainText("lot diagnostics saved");
    await navigate(page,"Worksheets");const result=page.getByRole("region", {name:"Lot opportunity results"});
    await expect(result).toContainText("subtotal (USD): 10.00");
    await expect(result).toContainText("known_acquisition_conflict");
    await expect(result).toContainText("0.125");
    await expect(result.locator("tbody tr")).toHaveCount(5);
    const current=await api(source,"/api/v1/current"); const saved=await api(source,`/api/v1/runs/${current.current_run_id}`);
    expect(saved.outputs.rows[3].price_basis_loss.value).toBe(10);
    expect(saved.outputs.rows[3].indicative_net_proceeds.value).toBeCloseTo(88.91,10);
    expect(saved.outputs.rows[3].indicative_tax_pnl.value).toBeCloseTo(-11.09,10);
    await navigate(page,"Holdings");await page.getByRole("button",{name:"Edit cash settings",exact:true}).click();await page.getByLabel("Additional cash budget (USD)").fill("25.00");await page.getByRole("button",{name:"Review cash settings",exact:true}).click();await page.getByLabel("I reviewed the selected cash budget; it is separate from imported balances",{exact:true}).check(); await saveSettings(page); await expect(status(page)).toContainText("revision 3");
    expect((await api(source,"/api/v1/current")).current_run_id).toBeNull();
    expect(await api(source,`/api/v1/runs/${saved.id}`)).toEqual(saved);
    const waiting=page.waitForEvent("download"); await navigate(page,"Settings");await page.getByRole("button",{name:"Download workspace backup"}).click(); const download=await waiting;
    const bytes=await readFile(await download.path()); await open(page,target);
    await upload(page,"Current workspace backup (up to 64 MiB)",bytes,"application/octet-stream");
    await page.getByRole("button",{name:"Restore into empty workspace"}).click(); await expect(status(page)).toContainText("restored");
    expect(await api(target,`/api/v1/runs/${saved.id}`)).toEqual(saved);
    await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption(saved.id);
    await expect(result).toContainText("subtotal (USD): 10.00");
    await expect(page.getByRole("article",{name:"Saved diagnostic"})).toContainText("historical inputs");
    await mkdir(path.join(root,".local/t005.1"),{recursive:true});
    await page.screenshot({path:path.join(root,".local/t005.1/recovered-lots-desktop.png"),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:path.join(root,".local/t005.1/recovered-lots-narrow.png"),fullPage:true});
  } finally { await source.stop(); await target.stop(); }
});

test("lost settings and lot responses retry identical requests without duplicate changes",async ({page})=>{
  const server=await runtime({dist});
  try {
    await open(page,server); await seed(page);
    for (const [route,button] of [["settings","Save reviewed lot settings"],["diagnostics","Save loss opportunity review"]]) {
      const bodies=[]; let first=true;
      await page.route(`**/api/v1/lots/${route}`,async interception=>{bodies.push(interception.request().postData()); if(first){first=false;await interception.fetch();await interception.abort();}else await interception.continue();});
      if(route==="settings") await saveSettings(page); else {await expect(page.getByRole("button",{name:button,exact:true})).toBeEnabled();await page.getByRole("button",{name:button,exact:true}).click();}
      await expect(page.getByRole("button",{name:"Retry identical action"})).toBeVisible();
      await page.getByRole("button",{name:"Retry identical action"}).click();
      await expect(page.getByRole("region",{name:"Pending action"})).toHaveCount(0);
      expect(bodies).toHaveLength(2); expect(bodies[0]).toEqual(bodies[1]);
      const current=await api(server,"/api/v1/current"); expect(current.revision).toBe(2);
      if(route==="diagnostics") {expect(current.current_run_id).not.toBeNull(); await expect(status(page)).toContainText("lot diagnostics saved");}
    }
  } finally {await server.stop();}
});

test("manual name mappings block both legs, explicit portions screen same-batch buys and invalid files stay private",async ({page})=>{
  const server=await runtime({dist});
  try {
    await open(page,server); await seed(page);
    await page.getByLabel("Recent or restricted name",{exact:true}).fill("reviewed B");
    await page.getByLabel("Explicit reviewed security mapping").selectOption("security-fbbb");
    await page.getByRole("button",{name:"Add restriction on both legs"}).click();
    await saveSettings(page); await expect(status(page)).toContainText("revision 2");
    const current=await api(server,"/api/v1/current"); const preview=await api(server,`/api/v1/previews/${current.snapshot_id}`); const lot=preview.snapshot.lots[3];
    await expect(page.getByLabel("Optional whole-share portions by lot ID (JSON)")).toBeEnabled();
    await navigate(page,"Holdings");await reveal(page,"Advanced lot inspection controls");await page.getByLabel("Optional whole-share portions by lot ID (JSON)").fill(JSON.stringify({[lot.id]:1}));
    await page.getByLabel("Replacement security IDs to screen (comma separated)").fill("security-fbbb");
    await page.getByRole("button",{name:"Save loss opportunity review",exact:true}).click(); await expect(status(page)).toContainText("lot diagnostics saved");
    await navigate(page,"Worksheets");await expect(page.getByRole("region",{name:"Lot opportunity results"})).toContainText("same_batch_sale_and_purchase");
    const saved=await api(server,`/api/v1/runs/${(await api(server,"/api/v1/current")).current_run_id}`);
    expect(saved.outputs.rows[3].blockers).toContain("manual_restriction:Reviewed manual name input");
    expect(saved.outputs.buy_screens[0].blockers).toContain("manual_restriction:Reviewed manual name input");
    const before=await api(server,"/api/v1/current");
    await upload(page,"Explicit lot settings JSON",Buffer.from('{"sensitive-key":"do-not-echo"}'));
    await expect(page.getByRole("alert")).toContainText("invalid"); await expect(page.locator("body")).not.toContainText("do-not-echo");
    expect(await api(server,"/api/v1/current")).toEqual(before);
  } finally {await server.stop();}
});
