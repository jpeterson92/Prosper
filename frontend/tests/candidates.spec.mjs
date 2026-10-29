import { dismissDetails, navigate, reveal, advancedImport, savedRecords, historyTools, workspaceTools, prepareUpload, sourceDetails } from "../tools/workspace.mjs";
test.beforeEach(({page})=>page.setDefaultTimeout(10000));
import { test, expect } from "@playwright/test";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { runtime, root, refreshHistory } from "../tools/runtime.mjs";
const folder=path.join(root,"examples/synthetic/candidates/application");
const load=async name=>JSON.parse(await readFile(path.join(folder,name)));
const dist=path.join(root,"frontend/dist");
async function api(server,route,body,expected=200) {const token=await server.session();const response=await fetch(server.origin+route,{method:body?"POST":"GET",headers:{Origin:server.origin,Authorization:`Bearer ${token}`,...(body?{"Content-Type":"application/json"}:{})},body:body?JSON.stringify(body):undefined});expect(response.status).toBe(expected);return response.json();}
async function seed(server,accountAlias) {
  const upload=await load("holdings.json");if(accountAlias)upload.snapshot.account_alias=accountAlias;
  const p=await api(server,"/api/v1/previews",upload);
  await api(server,"/api/v1/select",{snapshot_id:p.id,command_key:"holdings",expected_revision:0});
  await seedSelected(server);
}
async function seedSelected(server) {
  await api(server,"/api/v1/benchmarks/import",await load("benchmark.json"));
  await api(server,"/api/v1/benchmarks/diagnostics",{run_id:"benchmark",expected_revision:1,as_of:"2026-10-25T23:00:00Z",review:await load("benchmark-review.json")});
  await api(server,"/api/v1/benchmarks/select",{run_id:"benchmark",command_key:"benchmark",expected_revision:1});
  await api(server,"/api/v1/lots/settings",{settings:await load("lot-settings.json"),command_key:"settings",expected_revision:2});
  await refreshHistory(server,await load("history.json"));
  const prepared=await api(server,"/api/v1/inputs/risk-preset",{upload:await load("modeled.json")});
  expect(prepared.bundle.profile.preset).toEqual({identity:"standard-r1-v1",overrides:{}});
  const inputs=await api(server,"/api/v1/inputs/diagnostics",{...prepared,run_id:"inputs",expected_revision:4,as_of:"2026-10-25T23:00:00Z"});expect(inputs.outputs.software_inputs_complete).toBe(true);
}

test("source-shaped advisory lifecycle retains original worksheets after a separately supplied refresh",async({page})=>{
  test.setTimeout(90000);
  const lifecycle=path.join(folder,"lifecycle");
  const initial=await readFile(path.join(lifecycle,"initial.csv"));
  const refreshed=await readFile(path.join(lifecycle,"refreshed.csv"));
  let source=await runtime({dist});const target=await runtime({dist});
  const open=async server=>{await page.goto(server.origin);await navigate(page,"Analysis","Proposals");await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("Workspace read");};
  async function importSource(name,bytes) {
    await prepareUpload(page,"Declared combined-lot CSV");await page.getByLabel("Declared combined-lot CSV",{exact:true}).setInputFiles({name:`${name}.csv`,mimeType:"text/csv",buffer:bytes});
    await prepareUpload(page,"Reviewed lot context JSON");await page.getByLabel("Reviewed lot context JSON",{exact:true}).setInputFiles(path.join(lifecycle,`${name}-context.json`));
    await page.getByRole("button",{name:"Review imported holdings",exact:true}).click();
    await expect(page.getByRole("article",{name:"Snapshot review",exact:true})).toBeVisible();
    await page.getByLabel("I reviewed this snapshot and its unknowns",{exact:true}).check();
    await page.getByRole("button",{name:"Select reviewed snapshot",exact:true}).click();
  }
  async function exportText(server,id) {
    const token=await server.session();const response=await fetch(server.origin+`/api/v1/worksheets/${id}/export`,{headers:{Origin:server.origin,Authorization:`Bearer ${token}`}});
    expect(response.ok).toBe(true);return response.text();
  }
  try {
    await open(source);await importSource("initial",initial);
    await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("revision 1");
    const firstState=await api(source,"/api/v1/current");
    const first=(await api(source,`/api/v1/previews/${firstState.snapshot_id}`)).snapshot;
    expect(first.source_type).toBe("fidelity-shaped-combined-lots");
    expect(first.lots[0].quantity.value).toBe("2.5000");expect(first.lots[0].total_basis.value).toBe("30.00");
    expect(first.observations.source_row_accounting.map(r=>r.disposition)).toEqual(["selected-lot","outside-selected-account"]);
    expect(first.exclusions.some(e=>e.code==="outside_selected_account")).toBe(true);
    expect(first.observations.lot_context.source_coverage.value).toBeNull();
    await seedSelected(source);
    const lots=await api(source,"/api/v1/lots/diagnostics",{run_id:"source-lots",expected_revision:4,as_of:"2026-10-26T00:00:00Z"});
    expect(lots.outputs.rows[0].price_basis_loss.value).toBe(4);
    const command=await load("command.json");command.controls.sale_bounds={[first.lots[0].id]:2};
    await api(source,"/api/v1/candidates/start",command);
    await expect.poll(async()=>(await api(source,"/api/v1/runs/candidate")).outputs.outcome,{timeout:65000}).toBe("checked");
    const candidate=await api(source,"/api/v1/runs/candidate");
    expect(candidate.outputs.search.best.metrics.price_loss).toBe(4);
    expect(candidate.outputs.search.best.metrics.final_quantities).toEqual([.5,0]);
    expect(candidate.outputs.search.best.metrics.final_cash).toBe(20);
    await open(source);await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption("candidate");
    const panel=page.getByRole("region",{name:"Comparison and manual worksheet"});
    await panel.getByRole("button",{name:"Review proposal 1",exact:true}).click();
    await panel.getByLabel(`Sell shares ${first.lots[0].id}`,{exact:true}).fill("1");
    await panel.getByRole("button",{name:"Check worksheet quantities",exact:true}).click();
    await expect(panel.getByRole("article",{name:"Worksheet final checks",exact:true})).toContainText("$2.00");
    await panel.getByLabel("I confirm no external account changes since this snapshot; after external changes I will import refreshed holdings",{exact:true}).check();
    await panel.getByRole("button",{name:"Save dated manual worksheet",exact:true}).click();
    await expect.poll(async()=>(await api(source,"/api/v1/catalog")).worksheets.length).toBe(1);
    const id=(await api(source,"/api/v1/catalog")).worksheets[0];
    const saved=await api(source,`/api/v1/worksheets/${id}`);const originalText=await exportText(source,id);
    expect(saved.check.metrics.final_cash).toBe(10);expect(saved.check.metrics.final_quantities).toEqual([1.5,0]);
    expect(saved.lines[0].source_ref).toContain("source:SYNTHETIC_initial_FAAA.csv/record:6");
    expect(saved.exclusions).toEqual(expect.arrayContaining(first.exclusions));
    // Saving intended trades cannot alter holdings or reconstruct executions.
    expect((await api(source,`/api/v1/previews/${firstState.snapshot_id}`)).snapshot).toEqual(first);
    const directory=source.directory;await source.stop();source=await runtime({dist,directory});await open(source);
    expect(await exportText(source,id)).toBe(originalText);
    await importSource("refreshed",refreshed);
    await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("revision 5");
    const current=await api(source,"/api/v1/current");expect(current.current_run_id).toBeNull();expect(current.snapshot_id).not.toBe(firstState.snapshot_id);
    const next=(await api(source,`/api/v1/previews/${current.snapshot_id}`)).snapshot;
    // Explicit new facts intentionally differ from every proposed worksheet state.
    expect(next.lots[0].quantity.value).toBe("3.2500");expect(next.lots[0].total_basis.value).toBe("42.00");
    expect(next.lots[0].term.value).toBeNull();expect(next.observations.source_row_accounting).toHaveLength(2);
    await api(source,"/api/v1/worksheets",{...saved.command,id:"stale-after-refresh"},409);
    expect(await api(source,"/api/v1/worksheets",saved.command)).toEqual(saved);
    await api(source,"/api/v1/candidates/start",{...command,run_id:"stale-candidate"},409);
    await api(source,"/api/v1/candidates/start",{...command,run_id:"old-inputs",expected_revision:5},409);
    const partial=await api(source,"/api/v1/lots/diagnostics",{run_id:"refreshed-lots",expected_revision:5,as_of:"2026-10-26T15:00:00Z"});
    expect(partial.outputs.rows[0].blockers.length).toBeGreaterThan(0); // settings/marks predate refreshed holdings
    expect(await api(source,"/api/v1/runs/candidate")).toEqual(candidate);
    expect(await api(source,`/api/v1/worksheets/${id}`)).toEqual(saved);expect(await exportText(source,id)).toBe(originalText);
    const token=await source.session();const response=await fetch(source.origin+"/api/v1/backup",{headers:{Origin:source.origin,Authorization:`Bearer ${token}`}});
    expect(response.ok).toBe(true);const bytes=await response.arrayBuffer();const targetToken=await target.session();
    const restored=await fetch(target.origin+"/api/v1/restore",{method:"POST",headers:{Origin:target.origin,Authorization:`Bearer ${targetToken}`,"Content-Type":"application/octet-stream"},body:bytes});expect(restored.ok).toBe(true);
    expect(await api(target,`/api/v1/previews/${firstState.snapshot_id}`)).toEqual(await api(source,`/api/v1/previews/${firstState.snapshot_id}`));
    expect(await api(target,`/api/v1/previews/${current.snapshot_id}`)).toEqual(await api(source,`/api/v1/previews/${current.snapshot_id}`));
    expect(await api(target,`/api/v1/worksheets/${id}`)).toEqual(saved);expect(await exportText(target,id)).toBe(originalText);
    await open(target);await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption("candidate");
    await expect(panel).toContainText("Historical candidate:");await expect(panel.getByRole("button",{name:"Review proposal 1",exact:true})).toBeDisabled();
    await navigate(page,"Worksheets");await reveal(page,"Advanced worksheet lookup");await page.getByRole("combobox",{name:"Saved manual worksheet",exact:true}).selectOption(id);
    await expect(panel.getByRole("article",{name:"Saved manual worksheet",exact:true})).toContainText("$2.00");
    const evidence=path.join(root,".local/t010.1.1");await mkdir(evidence,{recursive:true});
    await writeFile(path.join(evidence,"lifecycle-backup.sqlite3"),Buffer.from(bytes));
    await writeFile(path.join(evidence,"worksheet.txt"),originalText);
    await writeFile(path.join(evidence,"lifecycle.json"),JSON.stringify({worksheet_id:id,initial_snapshot_id:firstState.snapshot_id,refreshed_snapshot_id:current.snapshot_id,initial_source_sha256:first.source_sha256,refreshed_source_sha256:next.source_sha256},null,2)+"\n");
  } finally {await source.stop();await target.stop();}
});

test("complete HTTP history to fitted candidate, lost response retry and frozen recovery",async({page})=>{
  test.setTimeout(90000);
  const source=await runtime({dist});const target=await runtime({dist});
  try {
    await seed(source);await page.goto(source.origin);await navigate(page,"Analysis","Proposals");
    await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("Workspace read");
    await prepareUpload(page,"Candidate controls JSON");await page.getByLabel("Candidate controls JSON",{exact:true}).setInputFiles(path.join(folder,"command.json"));
    await page.getByLabel("I reviewed the saved inputs, costs, funding and bounded search controls").check();
    let first=true;const bodies=[];
    await page.route("**/api/v1/candidates/start",async route=>{bodies.push(route.request().postData());if(first){first=false;await route.fetch();await route.abort();}else await route.continue();});
    await page.getByRole("button",{name:"Create exploratory proposals",exact:true}).click();
    await expect(page.getByRole("button",{name:"Retry identical action",exact:true})).toBeVisible();
    await page.getByRole("button",{name:"Retry identical action",exact:true}).click();
    const runId=JSON.parse(bodies[0]).run_id;
    await expect.poll(async()=> (await api(source,`/api/v1/runs/${runId}`)).status,{timeout:65000}).not.toBe("running");
    const run=await api(source,`/api/v1/runs/${runId}`);
    expect(run.outputs.outcome,JSON.stringify(run.outputs.issues)).toBe("checked");
    expect(run.outputs.search.best.metrics.price_loss).toBe(4);
    expect(run.outputs.search.best.metrics.final_quantities).toEqual([.5,0]);
    expect(run.outputs.risk.kind).toBe("candidate-fit-v1");
    expect(run.outputs.risk.projection.annual_covariance_sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(run.outputs.risk.scalars.every(s=>s.starts.length===9 && !("data" in s) && !("path" in s))).toBe(true);
    expect(run.outputs.risk.security_ids).toEqual(["security-faaa","security-fbbb"]);
    expect(run.outputs.financial_use_authorized).toBe(false);
    const heuristicBody={...await load("command.json"),run_id:"heuristic",controls:{...(await load("command.json")).controls,method:"deterministic-loss-prefix-repair-v1"}};
    await api(source,"/api/v1/candidates/start",heuristicBody);
    await expect.poll(async()=> (await api(source,"/api/v1/runs/heuristic")).status,{timeout:65000}).not.toBe("running");
    const heuristic=await api(source,"/api/v1/runs/heuristic");
    expect(heuristic.outputs.outcome,JSON.stringify(heuristic.outputs.issues)).toBe("checked");
    expect(heuristic.outputs.search.method).toBe("deterministic-loss-prefix-repair-v1");
    expect(heuristic.outputs.search.outcome).toBe("feasible-incumbent");
    expect(heuristic.outputs.search.domain_states).toBeNull();
    expect(heuristic.outputs.search.candidates.length).toBeGreaterThan(0);

    expect(bodies[0]).toBe(bodies[1]);
    await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption(runId);
    const view=page.getByRole("article",{name:"Checked candidate result",exact:true});
    await expect(view).toContainText("$4.00");await expect(view.getByRole("table",{name:"Leading checked proposal"}).getByRole("row").filter({hasText:"Sell"})).toContainText("2");await expect(view).toContainText("Financial-use authorization: unavailable");
    await api(source,"/api/v1/history/clear",{command_key:"clear",expected_revision:4});
    expect(await api(source,`/api/v1/runs/${runId}`)).toEqual(run);
    const token=await source.session();const response=await fetch(source.origin+"/api/v1/backup",{headers:{Origin:source.origin,Authorization:`Bearer ${token}`}});expect(response.ok).toBe(true);const bytes=await response.arrayBuffer();
    const targetToken=await target.session();const restored=await fetch(target.origin+"/api/v1/restore",{method:"POST",headers:{Origin:target.origin,Authorization:`Bearer ${targetToken}`,"Content-Type":"application/octet-stream"},body:bytes});expect(restored.ok).toBe(true);
    expect(await api(target,`/api/v1/runs/${runId}`)).toEqual(run);
    await page.goto(target.origin);await navigate(page,"Analysis","Proposals");await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("Workspace read");
    await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption(runId);await expect(view).toContainText("$4.00");
    await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption("heuristic");await view.getByRole("button",{name:"Why these results?",exact:true}).click();await expect(page.getByRole("dialog")).toContainText("not enumerated");await expect(page.getByRole("dialog")).toContainText("feasible-incumbent");await dismissDetails(page);
    await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await mkdir(path.join(root,".local/t007.1.2"),{recursive:true});await view.screenshot({path:path.join(root,".local/t007.1.2/candidate-narrow.png")});
  } finally {await source.stop();await target.stop();}
});

test("invalid controls are redacted and stale inputs refuse before a worker",async({page})=>{
  const server=await runtime({dist});try{
    await seed(server);const controls=await load("command.json");
    await api(server,"/api/v1/candidates/start",{...controls,PRIVATE_KEY:"DO-NOT-ECHO"},422);
    await api(server,"/api/v1/history/clear",{command_key:"other-window",expected_revision:4});
    await api(server,"/api/v1/candidates/start",controls,409);
    await page.goto(server.origin);await navigate(page,"Analysis","Proposals");await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("Workspace read");
    await prepareUpload(page,"Candidate controls JSON");await page.getByLabel("Candidate controls JSON",{exact:true}).setInputFiles({name:"bad.json",mimeType:"application/json",buffer:Buffer.from('{"PRIVATE_KEY":"DO-NOT-ECHO"}')});await expect(page.getByRole("alert")).toContainText("invalid");await expect(page.locator("body")).not.toContainText("DO-NOT-ECHO");
  }finally{await server.stop();}
});

test("browser cancellation reaches a saved terminal result without publishing",async({page})=>{
  const server=await runtime({dist});try{
    await seed(server);await page.goto(server.origin);await navigate(page,"Analysis","Proposals");
    await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("Workspace read");
    await prepareUpload(page,"Candidate controls JSON");await page.getByLabel("Candidate controls JSON",{exact:true}).setInputFiles(path.join(folder,"command.json"));
    await page.getByLabel("I reviewed the saved inputs, costs, funding and bounded search controls").check();
    await page.getByRole("button",{name:"Create exploratory proposals",exact:true}).click();
    await page.getByRole("button",{name:"Cancel candidate calculation",exact:true}).click();
    await expect(page.getByRole("article",{name:"Checked candidate result",exact:true})).toContainText("Calculation cancelled",{timeout:10000});
    const catalog=await api(server,"/api/v1/catalog");const id=catalog.runs.at(-1);
    const state=await api(server,"/api/v1/current");expect(state.current_run_id).not.toBe(id);
    expect((await api(server,`/api/v1/runs/${id}`)).status).toBe("failed");
  }finally{await server.stop();}
});

test("compare, revise, retry, export and recover dated manual worksheets",async({page})=>{
  test.setTimeout(90000);
  const alias='=HYPERLINK("https://fictional.invalid")\n<img src=x onerror=alert(1)>\t';
  let source=await runtime({dist});const target=await runtime({dist});
  try {
    await seed(source,alias);await api(source,"/api/v1/candidates/start",await load("command.json"));
    await expect.poll(async()=>(await api(source,"/api/v1/runs/candidate")).outputs.outcome,{timeout:30000}).toBe("checked");
    await page.goto(source.origin);await navigate(page,"Analysis","Proposals");await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("Workspace read");
    await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption("candidate",{timeout:10000});
    const panel=page.getByRole("region",{name:"Comparison and manual worksheet"});
    await expect(panel.getByRole("table",{name:"Candidate comparison"})).toContainText("No changes");
    await expect(panel.getByRole("table",{name:"Candidate comparison"})).toContainText("Proposal 1");
    await panel.getByRole("button",{name:"Review proposal 1",exact:true}).click({timeout:10000});
    await panel.getByLabel("Sell shares lot-a",{exact:true}).fill("1");
    await panel.getByLabel("Buy shares security-fbbb",{exact:true}).fill("2");
    await panel.getByRole("button",{name:"Check worksheet quantities",exact:true}).click();
    const checks=panel.getByRole("article",{name:"Worksheet final checks",exact:true});
    await expect(checks).toContainText("Refused:");await expect(checks).toContainText("cash");
    await expect(panel.getByRole("button",{name:"Save dated manual worksheet",exact:true})).toBeDisabled();
    await panel.getByLabel("Buy shares security-fbbb",{exact:true}).fill("0");
    await expect(checks).toHaveCount(0);
    await panel.getByRole("button",{name:"Check worksheet quantities",exact:true}).click();
    await expect(checks).toContainText("$2.00");await expect(checks).toContainText("$10.00");
    await panel.getByLabel("I confirm no external account changes since this snapshot; after external changes I will import refreshed holdings",{exact:true}).check();
    const bodies=[];let first=true;
    await page.route("**/api/v1/worksheets",async route=>{bodies.push(route.request().postData());if(first){first=false;const response=await route.fetch();const result=await response.json();await route.abort();expect(response.status(),JSON.stringify(result)).toBe(200);}else await route.continue();});
    await panel.getByRole("button",{name:"Save dated manual worksheet",exact:true}).click();
    await expect(page.getByRole("button",{name:"Retry identical action",exact:true})).toBeVisible();
    await expect(page.getByRole("button",{name:"Retry identical action",exact:true})).toBeEnabled();
    expect((await api(source,"/api/v1/catalog")).worksheets).toHaveLength(1);
    await page.getByRole("button",{name:"Retry identical action",exact:true}).click();
    const savedView=panel.getByRole("article",{name:"Saved manual worksheet",exact:true});
    await expect(savedView).toContainText("checked-estimate");expect(bodies[0]).toBe(bodies[1]);
    const id=JSON.parse(bodies[0]).id;
    const saved=await api(source,`/api/v1/worksheets/${id}`);
    await api(source,"/api/v1/worksheets",{...saved.command,id:"spoofed",metrics:{price_loss:999}},422);
    await api(source,"/api/v1/worksheets/check",{run_id:"candidate",expected_revision:4,orders:{sales:[{lot_id:"lot-a",shares:1.5}],buys:[]}},422);
    expect(saved.check.metrics.price_loss).toBe(2);expect(saved.check.metrics.final_cash).toBe(10);
    expect(saved.lines[0].account_alias).toBe(alias);expect(saved.financial_use_authorized).toBe(false);
    expect(await page.locator('img[src="x"]').count()).toBe(0);
    const downloading=page.waitForEvent("download");await savedView.getByRole("button",{name:"Download dated text worksheet",exact:true}).click();
    const download=await downloading;expect(download.suggestedFilename()).toBe("prosper-manual-worksheet.txt");
    const text=await readFile(await download.path(),"utf8");
    expect(text).toContain(JSON.stringify(alias));expect(text).toContain('"lot_id": "lot-a"');
    expect(text).toContain('"shares": 1');expect(text).toContain("Financial-use authorization: unavailable");
    expect(text).toContain("refreshed holdings");expect(text).not.toContain("\n<img");
    await panel.getByRole("button",{name:"Compare and revise",exact:true}).click();await panel.getByRole("button",{name:"Revise saved worksheet quantities",exact:true}).click();
    await panel.getByLabel("Sell shares lot-a",{exact:true}).fill("2");
    await panel.getByRole("button",{name:"Check worksheet quantities",exact:true}).click();await expect(checks).toContainText("$4.00");
    await panel.getByLabel("I confirm no external account changes since this snapshot; after external changes I will import refreshed holdings",{exact:true}).check();
    await panel.getByRole("button",{name:"Save dated manual worksheet",exact:true}).click();
    await expect.poll(async()=>(await api(source,"/api/v1/catalog")).worksheets.length).toBe(2);
    const secondId=(await api(source,"/api/v1/catalog")).worksheets.at(-1);
    expect((await api(source,`/api/v1/worksheets/${secondId}`)).command.parent_id).toBe(id);
    expect(await api(source,`/api/v1/worksheets/${id}`)).toEqual(saved);
    // Native edits create a new candidate run and leave both the old result and worksheet frozen.
    await navigate(page,"Analysis","Proposals");await page.getByRole("button",{name:"Edit saved candidate controls",exact:true}).click();await reveal(page,"Review or edit prepared proposal controls");
    await page.getByLabel("Maximum modeled cost USD",{exact:true}).fill("0");
    await page.getByLabel("I reviewed the saved inputs, costs, funding and bounded search controls",{exact:true}).check();
    await page.getByRole("button",{name:"Create exploratory proposals",exact:true}).click();
    await expect.poll(async()=>{const c=await api(source,"/api/v1/catalog");return c.runs.at(-1);}).not.toBe("candidate");
    const revisedId=(await api(source,"/api/v1/catalog")).runs.at(-1);
    await expect.poll(async()=>(await api(source,`/api/v1/runs/${revisedId}`)).outputs.outcome,{timeout:30000}).toBe("checked");
    expect((await api(source,`/api/v1/runs/${revisedId}`)).inputs.candidate_command.controls.max_cost).toBe("0");
    expect(await api(source,`/api/v1/worksheets/${id}`)).toEqual(saved);
    // A strict zero-TE synthetic input has no whole-share solution here: final
    // benchmark targets require 1.25 shares/name. A breached baseline stays a diagnostic.
    const strict=await load("modeled.json");strict.bundle.investor_controls.find(c=>c.name==="tracking_error").value.value="0";
    await api(source,"/api/v1/inputs/diagnostics",{...strict,run_id:"strict-inputs",expected_revision:4,as_of:new Date().toISOString()});
    await navigate(page,"Analysis","Proposals");await page.getByRole("button",{name:"Edit saved candidate controls",exact:true}).click();await reveal(page,"Review or edit prepared proposal controls");
    await page.getByLabel("Candidate input run ID",{exact:true}).fill("strict-inputs");
    await page.getByLabel("I reviewed the saved inputs, costs, funding and bounded search controls",{exact:true}).check();
    await page.getByRole("button",{name:"Create exploratory proposals",exact:true}).click();
    await expect.poll(async()=>(await api(source,"/api/v1/catalog")).runs.at(-1)).not.toBe("strict-inputs");
    const strictId=(await api(source,"/api/v1/catalog")).runs.at(-1);
    await expect.poll(async()=>(await api(source,`/api/v1/runs/${strictId}`)).outputs.outcome,{timeout:30000}).toBe("checked");
    await navigate(page,"Worksheets");await expect(panel.getByRole("button",{name:"Review no changes",exact:true})).toBeEnabled();
    await panel.getByRole("button",{name:"Review no changes",exact:true}).click();
    await panel.getByRole("button",{name:"Check worksheet quantities",exact:true}).click();
    await expect(checks).toContainText("Breaches selected limits");await expect(checks).toContainText("no-trade diagnostic");
    await panel.getByLabel("I confirm no external account changes since this snapshot; after external changes I will import refreshed holdings",{exact:true}).check();
    await panel.getByRole("button",{name:"Save dated manual worksheet",exact:true}).click();
    await expect.poll(async()=>(await api(source,"/api/v1/catalog")).worksheets.length).toBe(3);
    const baselineId=(await api(source,"/api/v1/catalog")).worksheets.at(-1);
    const baseline=await api(source,`/api/v1/worksheets/${baselineId}`);
    expect(baseline.validation_outcome).toBe("baseline-diagnostic");expect(baseline.check.feasible).toBe(false);expect(baseline.lines).toEqual([]);
    // Restart the real application before historical reads and recovery.
    const directory=source.directory;await source.stop();source=await runtime({dist,directory});
    expect(await api(source,`/api/v1/worksheets/${id}`)).toEqual(saved);
    await api(source,"/api/v1/history/clear",{command_key:"clear",expected_revision:4});
    await api(source,"/api/v1/worksheets",{...saved.command,id:"stale-save"},409);
    expect(await api(source,"/api/v1/worksheets",saved.command)).toEqual(saved);
    const token=await source.session();const response=await fetch(source.origin+"/api/v1/backup",{headers:{Origin:source.origin,Authorization:`Bearer ${token}`}});expect(response.ok).toBe(true);
    const targetToken=await target.session();const restored=await fetch(target.origin+"/api/v1/restore",{method:"POST",headers:{Origin:target.origin,Authorization:`Bearer ${targetToken}`,"Content-Type":"application/octet-stream"},body:await response.arrayBuffer()});expect(restored.ok).toBe(true);
    expect(await api(target,`/api/v1/worksheets/${id}`)).toEqual(saved);
    await page.goto(target.origin);await navigate(page,"Analysis","Proposals");await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("Workspace read");
    await navigate(page,"Worksheets");await reveal(page,"Advanced worksheet lookup");await page.getByRole("combobox",{name:"Saved manual worksheet",exact:true}).selectOption(id);
    await expect(savedView).toContainText("$2.00");
    await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption("candidate",{timeout:10000});
    await expect(panel).toContainText("Historical candidate:");
    await expect(panel.getByRole("button",{name:"Review proposal 1",exact:true})).toBeDisabled();
    await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await mkdir(path.join(root,".local/t008.1"),{recursive:true});await reveal(page,"Advanced worksheet lookup");await page.getByRole("combobox",{name:"Saved manual worksheet",exact:true}).selectOption(id);await savedView.screenshot({path:path.join(root,".local/t008.1/worksheet-narrow.png")});
  } finally {await source.stop();await target.stop();}
});
