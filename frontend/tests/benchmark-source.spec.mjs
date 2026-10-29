import { dismissDetails, navigate, reveal, advancedImport, savedRecords, historyTools, workspaceTools, prepareUpload, sourceDetails } from "../tools/workspace.mjs";
test.beforeEach(({page})=>page.setDefaultTimeout(10000));
import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { runtime, root } from "../tools/runtime.mjs";

const dist = path.join(root, "frontend/dist");
const fixture = JSON.parse(await readFile(path.join(root, "examples/synthetic/benchmark/current-observation.json")));
const csv = JSON.parse(await readFile(path.join(root, "examples/synthetic/blackrock/current-observation.json")));
const region = page => page.getByRole("region", {name:"Retained source diagnostics", exact:true});
async function open(page, server) { await page.goto(server.origin);await navigate(page,"Analysis","Benchmark"); await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("Workspace read"); }
async function post(server, body) {
  const token=await server.session();
  const response=await fetch(server.origin+"/api/v1/benchmarks/import",{method:"POST",headers:{Origin:server.origin,Authorization:`Bearer ${token}`,"Content-Type":"application/json"},body:JSON.stringify(body)});
  expect(response.ok).toBe(true);return response.json();
}
async function inspect(page, identity) {
  await page.getByRole("combobox",{name:"Retained benchmark observation",exact:true}).selectOption(identity);
  await reveal(page,"View source holdings");await expect(region(page).getByRole("status")).toContainText("matching source rows");
  await expect(page.getByRole("combobox",{name:"Retained benchmark observation",exact:true})).toHaveValue(identity);
}
async function apply(page) { await region(page).getByRole("button",{name:"Apply source filters",exact:true}).click(); }

test("source rows are readable before any snapshot or mapping; filters preserve unknowns and empty sections", async ({page}) => {
  const server=await runtime({dist});try {
    await post(server,fixture);await open(page,server);await expect(page).toHaveTitle("Prosper | Local advisory workspace");
    await inspect(page,fixture.request.observation_id); const view=region(page);
    await expect(view.getByRole("status")).toHaveText("8 matching source rows of 8; showing 1\u20138.");
    await expect(view).toContainText("2000-01-03");await expect(view).toContainText("Blank (unknown)");
    await expect(view.getByRole("table",{name:"Grouped acquisition issues",exact:true})).toContainText("missing_ticker");
    await view.getByRole("combobox",{name:"Located source issue",exact:true}).selectOption("missing_ticker");await apply(page);
    await expect(view.getByRole("status")).toContainText("2 matching source rows of 8");
    await expect(view.getByRole("table",{name:"Original retained source rows",exact:true})).toContainText("equity:2");
    await view.getByRole("button",{name:"Clear source filters",exact:true}).click();await expect(view.getByRole("status")).toContainText("8 matching");
    await view.getByLabel("Search original source fields",{exact:true}).fill("fIaA");await apply(page);
    await expect(view.getByRole("status")).toContainText("1 matching source rows of 8");
    await view.getByText("Inspect 6 fields",{exact:true}).click();
    const fields=view.getByRole("table",{name:"equity:0 field values",exact:true});
    await expect(fields).toContainText("60.0000");await expect(fields).toContainText("number / source");
    await view.getByRole("button",{name:"Clear source filters",exact:true}).click();await expect(view.getByRole("status")).toContainText("8 matching");
    await view.getByRole("combobox",{name:"Source section",exact:true}).selectOption("fixedIncome");await apply(page);
    await expect(view.getByRole("status")).toContainText("1 matching");
    await view.getByRole("combobox",{name:"Source section",exact:true}).selectOption("shortTermReservesMoneyMarket");await apply(page);
    await expect(view).toContainText("No source rows match these filters");await expect(view.getByRole("status")).toContainText("showing 0\u20130");
    await expect(page.getByRole("button",{name:"Save reviewed benchmark result",exact:true})).toHaveCount(0);
    const token=await server.session();const current=await fetch(server.origin+"/api/v1/current",{headers:{Origin:server.origin,Authorization:`Bearer ${token}`}}).then(r=>r.json());
    expect(current.revision).toBe(0);expect(current.snapshot_id).toBeNull();expect(current.settings).toEqual({});
  } finally {await server.stop();}
});

test("CSV original cells and physical locators survive restart without a review", async ({page}) => {
  let server=await runtime({dist});try {
    await post(server,csv);await open(page,server);await inspect(page,csv.request.observation_id);
    const view=region(page);await expect(view).toContainText("csv:record:0:lines:6-7");await expect(view).toContainText("60,000.00");
    await view.getByRole("table",{name:"Original retained source rows",exact:true}).getByRole("row").filter({hasText:"holdings:0"}).getByText(/^Inspect \d+ fields$/).click();
    const fields=view.getByRole("table",{name:"holdings:0 field values",exact:true});
    await expect(fields).toContainText("Fictional\nAlpha");await expect(fields).toContainText("adapter alias or locator");
    await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    const directory=server.directory;await server.stop();server=await runtime({dist,directory});
    await open(page,server);await inspect(page,csv.request.observation_id);await expect(region(page)).toContainText("60,000.00");
    await expect(region(page)).toContainText("6 matching source rows of 6");
  } finally {await server.stop();}
});

test("source pages, unavailable observations and failed reads cannot display stale or empty holdings", async ({page}) => {
  const server=await runtime({dist});try {
    const many=structuredClone(fixture);many.request.observation_id="many-rows";
    const source={"2000-01-03":{equity:Array.from({length:123},(_,i)=>({ticker:`F${i}`,cusip:`id${i}`,marketValue:"1.00",percentOfFunds:"1"}))}};
    many.source_base64=Buffer.from(JSON.stringify(source)).toString("base64");await post(server,many);
    const failed=structuredClone(fixture);failed.request.observation_id="unavailable";failed.http_status=404;await post(server,failed);
    await open(page,server);await inspect(page,"many-rows");
    await reveal(page,"View source holdings");await expect(region(page).getByRole("status")).toContainText("showing 1\u201350");
    await region(page).getByRole("button",{name:"Next source rows",exact:true}).click();await expect(region(page).getByRole("status")).toContainText("showing 51\u2013100");
    await region(page).getByRole("button",{name:"Next source rows",exact:true}).click();await expect(region(page).getByRole("status")).toContainText("showing 101\u2013123");
    await expect(region(page).getByRole("button",{name:"Next source rows",exact:true})).toBeDisabled();
    await region(page).getByRole("button",{name:"Previous source rows",exact:true}).click();await expect(region(page).getByRole("status")).toContainText("showing 51\u2013100");
    let release;const gate=new Promise(resolve=>release=resolve);let started;const waiting=new Promise(resolve=>started=resolve);
    await page.route("**/api/v1/benchmarks/rows",async route=>{if(route.request().postDataJSON().observation_id==="many-rows"){started();await gate;}await route.continue();});
    await region(page).getByRole("button",{name:"Previous source rows",exact:true}).click();await waiting;
    await page.getByRole("combobox",{name:"Retained benchmark observation",exact:true}).selectOption("unavailable");
    await expect(region(page)).toContainText("Source rows unavailable for this unavailable observation");release();
    await expect(region(page)).toContainText("date_unavailable");await expect(region(page).getByRole("table",{name:"Original retained source rows",exact:true})).toHaveCount(0);
    await expect(page.getByRole("combobox",{name:"Retained benchmark observation",exact:true})).toHaveValue("unavailable");
    await page.unroute("**/api/v1/benchmarks/rows");await page.route("**/api/v1/benchmarks/rows",route=>route.abort());
    await page.getByRole("combobox",{name:"Retained benchmark observation",exact:true}).selectOption("many-rows");await expect(region(page).getByRole("alert")).toContainText("No empty source is assumed");
    await page.unroute("**/api/v1/benchmarks/rows");await region(page).getByRole("button",{name:"Retry source inspection",exact:true}).click();
    await reveal(page,"View source holdings");await expect(region(page).getByRole("status")).toContainText("123 matching source rows");
  } finally {await server.stop();}
});

test("failed observation switch keeps the displayed source and picker consistent", async ({page}) => {
  const server=await runtime({dist});try {
    await post(server,fixture);await post(server,csv);await open(page,server);
    const picker=page.getByRole("combobox",{name:"Retained benchmark observation",exact:true});
    await expect(picker).toHaveValue("");await inspect(page,fixture.request.observation_id);
    const route=`**/api/v1/benchmarks/observations/${csv.request.observation_id}`;
    await page.route(route,request=>request.abort());await picker.selectOption(csv.request.observation_id);
    await expect(page.getByRole("region",{name:"Standard benchmark",exact:true}).getByRole("alert")).toContainText("Benchmark request failed");
    await expect(picker).toHaveValue(fixture.request.observation_id);
    await reveal(page,"View source holdings");await expect(region(page).getByRole("status")).toContainText("8 matching source rows of 8");
    await page.unroute(route);await inspect(page,csv.request.observation_id);
    await expect(region(page)).toContainText("csv:record:0:lines:6-7");
  } finally {await server.stop();}
});
