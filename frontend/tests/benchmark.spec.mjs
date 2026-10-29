import { dismissDetails, navigate, reveal, advancedImport, savedRecords, historyTools, workspaceTools, prepareUpload, sourceDetails } from "../tools/workspace.mjs";
test.beforeEach(({page})=>page.setDefaultTimeout(10000));
import { test, expect } from "@playwright/test";
import { readFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { runtime, root } from "../tools/runtime.mjs";

const dist = path.join(root, "frontend/dist");
const holdings = await readFile(path.join(root, "examples/synthetic/advisory-workspace.json"));
const observation = await readFile(path.join(root, "examples/synthetic/benchmark/current-observation.json"));
const review = await readFile(path.join(root, "examples/synthetic/benchmark/current-review.json"));
const status = page => page.getByRole("status", { name: "Workspace status" });
async function open(page, server) { await page.goto(server.origin);await navigate(page,"Analysis","Benchmark"); await expect(status(page)).toContainText("Workspace read"); }
async function upload(page, label, buffer) { await prepareUpload(page,label); await expect(page.getByLabel(label, {exact:true})).toBeEnabled(); await page.getByLabel(label, {exact:true}).setInputFiles({ name:"fictional.json", mimeType:"application/json", buffer }); }
async function seed(page) {
  await upload(page, "Normalized snapshot JSON file (up to 2 MiB)", holdings);
  await page.getByRole("button", {name:"Stage preview",exact:true}).click(); await expect(status(page)).toContainText("Preview staged");
  await page.getByLabel("I reviewed this snapshot and its unknowns").check(); await page.getByRole("button", {name:"Select reviewed snapshot"}).click(); await expect(status(page)).toContainText("revision 1");
  await navigate(page,"Analysis","Benchmark");await page.getByText("Import saved benchmark response", {exact:true}).click(); await upload(page,"Saved benchmark response JSON",observation);
  await expect(page.getByRole("article",{name:"Benchmark observation"})).toContainText("2000-01-03");
  await expect(page.getByRole("combobox",{name:"Retained benchmark observation",exact:true})).toHaveValue(JSON.parse(observation).request.observation_id);
  await upload(page,"Reviewed benchmark mapping and metadata JSON",review);
  await expect(page.getByRole("article",{name:"Benchmark proxy review"})).toContainText("8 source rows; 2 included equities; 6 excluded");
}
async function api(server, route) { const token=await server.session(); const response=await fetch(server.origin+route,{headers:{Origin:server.origin, Authorization:`Bearer ${token}`}}); expect(response.ok).toBe(true); return response.json(); }
async function save(page) { await page.getByLabel("I reviewed fund identity, reporting date, row accounting and exclusions").check(); await page.getByRole("button",{name:"Save reviewed benchmark result"}).click(); await expect(status(page)).toContainText("benchmark result saved"); }

test("explicit benchmark review, selection, restart and recovery preserve original rows and output", async ({page}) => {
  const source=await runtime({dist}); const target=await runtime({dist});
  try {
    await open(page,source); await expect(page.getByRole("button",{name:"Fetch full holdings"})).toBeDisabled(); await seed(page);
    await page.getByRole("button",{name:"Read original benchmark response"}).click(); await expect(page.getByText("Original retained response",{exact:true})).toBeVisible();
    const before=await api(source,"/api/v1/current"); expect(before.settings.benchmark_run_id).toBeUndefined();
    await save(page); await navigate(page,"Analysis","Benchmark");await page.getByRole("button",{name:"Select this reviewed benchmark"}).click(); await expect(status(page)).toContainText("revision 2");
    const current=await api(source,"/api/v1/current"); const saved=await api(source,`/api/v1/runs/${current.settings.benchmark_run_id}`);
    expect(saved.outputs.weights[0]).toBeCloseTo(2/3,14); expect(saved.outputs.weights[1]).toBeCloseTo(1/3,14); expect(saved.outputs.ledger[1].raw_percentage).toBe(""); expect(saved.outputs.ledger).toHaveLength(8);
    await page.reload();await navigate(page,"Analysis","Benchmark"); await expect(status(page)).toContainText("Workspace read"); await expect(page.getByRole("region",{name:"Standard benchmark"})).toContainText("Selected: VTI - holdings 2000-01-03");
    await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption(current.settings.benchmark_run_id);
    const downloadEvent=page.waitForEvent("download"); await navigate(page,"Settings");await page.getByRole("button",{name:"Download workspace backup"}).click(); const download=await downloadEvent; const bytes=await readFile(await download.path());
    await open(page,target); await upload(page,"Current workspace backup (up to 64 MiB)",bytes); await page.getByRole("button",{name:"Restore into empty workspace"}).click(); await expect(status(page)).toContainText("restored");
    expect(await api(target,`/api/v1/runs/${saved.id}`)).toEqual(saved);
    await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption(saved.id); await navigate(page,"Analysis","Benchmark");await expect(page.getByRole("button",{name:"Select this reviewed benchmark"})).toBeEnabled();
    await mkdir(path.join(root,".local/t006.1.8.3"),{recursive:true}); await page.getByRole("region",{name:"Standard benchmark"}).screenshot({path:path.join(root,".local/t006.1.8.3/benchmark-desktop.png")});
    await page.setViewportSize({width:390,height:844}); expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true); await page.getByRole("region",{name:"Standard benchmark"}).screenshot({path:path.join(root,".local/t006.1.8.3/benchmark-narrow.png")});
  } finally { await source.stop(); await target.stop(); }
});

test("lost review and selection responses retry original requests without duplicate work", async ({page}) => {
  const server=await runtime({dist}); try {
    await open(page,server); await seed(page);
    for (const [route,action,message] of [["diagnostics",()=>save(page),"benchmark result saved"],["select",()=>page.getByRole("button",{name:"Select this reviewed benchmark"}).click(),"revision 2"]]) {
      const bodies=[]; let first=true;
      await page.route(`**/api/v1/benchmarks/${route}`,async request=>{bodies.push(request.request().postData()); if(first){first=false;await request.fetch();await request.abort();}else await request.continue();});
      if(route==="diagnostics") { await page.getByLabel("I reviewed fund identity, reporting date, row accounting and exclusions").check(); await page.getByRole("button",{name:"Save reviewed benchmark result"}).click(); } else await action();
      await expect(page.getByRole("button",{name:"Retry identical action"})).toBeVisible(); await page.getByRole("button",{name:"Retry identical action"}).click(); await expect(status(page)).toContainText(message);
      expect(bodies).toHaveLength(2); expect(bodies[0]).toBe(bodies[1]);
    }
    expect((await api(server,"/api/v1/current")).revision).toBe(2);
  } finally { await server.stop(); }
});

test("fund and date picker sends explicit request and retries identical lost fetch", async ({page}) => {
  const server=await runtime({dist}); try {
    await open(page,server); const requests=[]; let first=true;
    await page.route("**/api/v1/benchmarks/fetch",async route=>{
      const request=route.request().postDataJSON(); requests.push(request);
      const fixture=JSON.parse(observation); fixture.request=request;
      const body=JSON.parse(Buffer.from(fixture.source_base64,"base64")); body.latestEffectiveDate="2000-01-03"; fixture.source_base64=Buffer.from(JSON.stringify(body)).toString("base64");
      fixture.response_url="https://advisors.vanguard.com/investments/products/api/funds/0968/holdings/latest";
      const response=await route.fetch({url:server.origin+"/api/v1/benchmarks/import",postData:JSON.stringify(fixture)});
      if(first){first=false;await route.abort();}else await route.fulfill({response});
    });
    await page.getByRole("combobox",{name:"Benchmark provider",exact:true}).selectOption("Vanguard"); await page.getByRole("combobox",{name:"Vanguard fund",exact:true}).selectOption("VOO"); await page.getByRole("combobox",{name:"Holdings date request",exact:true}).selectOption("latest"); await page.getByRole("button",{name:"Fetch full holdings"}).click();
    await expect(page.getByRole("button",{name:"Retry identical benchmark fetch"})).toBeVisible(); await page.getByRole("button",{name:"Retry identical benchmark fetch"}).click();
    await expect(page.getByRole("article",{name:"Benchmark observation"})).toContainText("VOO; observed"); expect(requests).toHaveLength(2); expect(requests[0]).toEqual(requests[1]); expect(requests[0].requested_date).toBeNull(); expect(requests[0].ticker).toBe("VOO");
    await expect(page.getByRole("combobox",{name:"Retained benchmark observation",exact:true})).toHaveValue(requests[0].observation_id);
    expect((await api(server,"/api/v1/current")).settings.benchmark_run_id).toBeUndefined();
  } finally { await server.stop(); }
});

test("iShares defaults to explicit fund choice and CSV review survives save and reopen", async ({page}) => {
  const server=await runtime({dist}); try {
    const token=await server.session();
    async function post(route,body) {const response=await fetch(server.origin+route,{method:"POST",headers:{Origin:server.origin,Authorization:`Bearer ${token}`,"Content-Type":"application/json"},body:JSON.stringify(body)});expect(response.ok).toBe(true);return response.json();}
    const staged=await post("/api/v1/previews",JSON.parse(await readFile(path.join(root,"examples/synthetic/advisory-workspace.json"))));
    await post("/api/v1/select",{snapshot_id:staged.id,command_key:"holdings",expected_revision:0});
    await open(page,server);
    await expect(page.getByRole("combobox",{name:"Benchmark provider",exact:true})).toHaveValue("BlackRock iShares");
    await expect(page.getByRole("combobox",{name:"iShares fund",exact:true})).toHaveValue("");
    await expect(page.getByRole("button",{name:"Fetch full holdings",exact:true})).toBeDisabled();
    const fixture=JSON.parse(await readFile(path.join(root,"examples/synthetic/blackrock/current-observation.json")));
    const mapping=JSON.parse(await readFile(path.join(root,"examples/synthetic/blackrock/current-review.json")));
    await page.route("**/api/v1/benchmarks/fetch",async route=>{
      const request=route.request().postDataJSON();expect(request.ticker).toBe("IVV");expect(request.requested_date).toBe("2026-10-20");
      fixture.request=request;mapping.observation_id=request.observation_id;
      const response=await route.fetch({url:server.origin+"/api/v1/benchmarks/import",postData:JSON.stringify(fixture)});await route.fulfill({response});
    });
    await page.getByRole("combobox",{name:"iShares fund",exact:true}).selectOption("IVV");
    await page.getByRole("combobox",{name:"Holdings date request",exact:true}).selectOption("historical");
    await page.getByLabel("Reported holdings date",{exact:true}).fill("2026-10-20");
    await page.getByRole("button",{name:"Fetch full holdings",exact:true}).click();
    await expect(page.getByRole("article",{name:"Benchmark observation",exact:true})).toContainText("IVV; observed");
    await upload(page,"Reviewed benchmark mapping and metadata JSON",Buffer.from(JSON.stringify(mapping)));
    await expect(page.getByRole("article",{name:"Benchmark proxy review",exact:true})).toContainText("6 source rows; 2 included equities; 4 excluded");
    expect((await api(server,"/api/v1/current")).settings.benchmark_run_id).toBeUndefined();
    await save(page);await navigate(page,"Analysis","Benchmark");await page.getByRole("button",{name:"Select this reviewed benchmark",exact:true}).click();await expect(status(page)).toContainText("revision 2");
    const state=await api(server,"/api/v1/current");const saved=await api(server,`/api/v1/runs/${state.settings.benchmark_run_id}`);
    await page.reload();await navigate(page,"Analysis","Benchmark");await expect(status(page)).toContainText("Workspace read");
    await expect(page.getByRole("region",{name:"Standard benchmark",exact:true})).toContainText("Selected: IVV - holdings 2026-10-20");
    expect(await api(server,`/api/v1/runs/${saved.id}`)).toEqual(saved);
    await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption(saved.id);
    await navigate(page,"Analysis","Benchmark");await expect(page.getByRole("article",{name:"Benchmark proxy review",exact:true})).toContainText("6 source rows; 2 included equities; 4 excluded");
  } finally {await server.stop();}
});

test("malformed and wrong fund reviews fail safely while incomplete reviews remain unselectable", async ({page}) => {
  const server=await runtime({dist}); try {
    await open(page,server); await seed(page); const current=await api(server,"/api/v1/current");
    await upload(page,"Reviewed benchmark mapping and metadata JSON",Buffer.from('{"secret-field":"DO-NOT-ECHO"}')); await expect(page.getByRole("alert")).toContainText("Invalid benchmark"); await expect(page.locator("body")).not.toContainText("DO-NOT-ECHO");
    const bad=JSON.parse(review); bad.metadata_ticker="VOO"; await upload(page,"Reviewed benchmark mapping and metadata JSON",Buffer.from(JSON.stringify(bad))); await expect(page.getByRole("alert")).toContainText("Invalid benchmark");
    const partial=JSON.parse(review); partial.policy.decisions.pop(); await upload(page,"Reviewed benchmark mapping and metadata JSON",Buffer.from(JSON.stringify(partial))); await expect(page.getByRole("article",{name:"Benchmark proxy review"})).toContainText("incomplete"); await save(page); await expect(page.getByRole("button",{name:"Select this reviewed benchmark"})).toBeDisabled();
    expect((await api(server,"/api/v1/current")).settings).toEqual(current.settings);
  } finally { await server.stop(); }
});
