import { dismissDetails, navigate, reveal, advancedImport, savedRecords, historyTools, workspaceTools, prepareUpload, sourceDetails } from "../tools/workspace.mjs";
import { test, expect } from "@playwright/test";
import { readFile, mkdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import { runtime, root, refreshHistory } from "../tools/runtime.mjs";
const folder=path.join(root,"examples/synthetic/candidates/application"), dist=path.join(root,"frontend/dist");
const load=async name=>JSON.parse(await readFile(path.join(folder,name)));
const modeled=(await load("modeled.json")).bundle;
const status=page=>page.getByRole("status",{name:"Workspace status"});
const panel=page=>page.getByRole("region",{name:"Prepare EOD inputs",exact:true});
test.beforeEach(({page})=>{page.setDefaultTimeout(10000);});
async function api(server,route,body) {const token=await server.session();const response=await fetch(server.origin+"/api/v1"+route,{method:body?"POST":"GET",headers:{Origin:server.origin,Authorization:`Bearer ${token}`,...(body?{"Content-Type":"application/json"}:{})},body:body?JSON.stringify(body):undefined});expect(response.ok,await response.clone().text()).toBe(true);return response.json();}
async function seed(server,{saved=false}={}) {
  const holdings=await load("holdings.json");
  // A declared high-basis lot makes the observed EOD close a loss without changing history or model fitting.
  const bytes=Buffer.from(Buffer.from(holdings.source_base64,"base64").toString().replace("30.00","400.00"));
  holdings.source_base64=bytes.toString("base64");holdings.snapshot.source_sha256=createHash("sha256").update(bytes).digest("hex");holdings.snapshot.observations.lot_context.source_sha256=holdings.snapshot.source_sha256;holdings.snapshot.lots[0].total_basis.value="400.00";
  const preview=await api(server,"/previews",holdings);
  await api(server,"/select",{snapshot_id:preview.id,command_key:"holdings",expected_revision:0});
  await api(server,"/benchmarks/import",await load("benchmark.json"));
  await api(server,"/benchmarks/diagnostics",{run_id:"benchmark",expected_revision:1,as_of:"2026-10-25T23:00:00Z",review:await load("benchmark-review.json")});
  await api(server,"/benchmarks/select",{run_id:"benchmark",command_key:"benchmark",expected_revision:1});
  await api(server,"/lots/settings",{settings:await load("lot-settings.json"),command_key:"settings",expected_revision:2});
  await refreshHistory(server,await load("history.json"));
  if(saved)await api(server,"/inputs/diagnostics",{...await load("modeled.json"),run_id:"facts",expected_revision:4,as_of:"2026-10-25T23:00:00Z"});
  return preview;
}
async function open(page,server) {await page.goto(server.origin);await navigate(page,"Analysis","Review inputs");await expect(status(page)).toContainText("Workspace read");}
async function context(page) {await panel(page).getByRole("button",{name:"Load selected input sources",exact:true}).click();await expect(panel(page).getByRole("button",{name:"Prepare and review EOD inputs",exact:true})).toBeVisible();}
async function window(page) {
  const p=panel(page);await p.getByLabel("Completed EOD session",{exact:true}).fill(modeled.analysis_date);await reveal(page,"Analysis time and source details");await p.getByLabel("Analysis knowledge time (ISO UTC)",{exact:true}).fill("2026-10-25T23:00:00Z");
  await p.getByRole("checkbox",{name:/Use history/}).check();await p.getByText("Declare calendar and exact window",{exact:true}).click();await p.getByRole("button",{name:/Use session grid from/}).click();
  await expect(p.getByLabel("Required sessions (one date per line)",{exact:true})).toHaveValue([modeled.history.predecessor,...modeled.history.sessions].join("\n"));
  await p.getByLabel("Required sessions (one date per line)",{exact:true}).fill(modeled.history.sessions.join("\n"));
  await p.getByLabel("Predecessor session",{exact:true}).fill(modeled.history.predecessor);await p.getByLabel("History knowledge time (ISO UTC)",{exact:true}).fill(modeled.history.known_at);await p.getByLabel("Calendar evidence",{exact:true}).fill(modeled.history.calendar_evidence);
}
async function declarations(page,server,preview) {
  const p=panel(page);await p.getByLabel("Taxonomy name",{exact:true}).fill(modeled.taxonomy_name);await p.getByLabel("Taxonomy version",{exact:true}).fill(modeled.taxonomy_version);
  await p.getByText("Declare unresolved source permissions and validity",{exact:true}).click();
  await p.getByRole("button",{name:`Declare source ${preview.snapshot.source_sha256}`,exact:true}).click();
  const evidence={source_ref:"source holdings review",provider:"Fictional fixture owner",dataset:"Fictional stock and taxonomy declaration",permission_scope:"Fictional local verification",effective:"2026-10-23",valid_through:"2026-10-23",recorded_at:"2026-10-23T20:00:00Z"};
  for(const [k,v]of Object.entries(evidence))await p.getByLabel(`${k.replaceAll("_"," ")} source 1`,{exact:true}).fill(v);
  await p.getByText("Resolve identity and taxonomy exceptions",{exact:true}).click();
  for(const [i,c]of modeled.classifications.entries()) {
    await p.getByRole("button",{name:"Add unresolved security facts",exact:true}).click();
    for(const [k,v]of Object.entries({security_id:c.security_id,sector:c.sector.value,industry:c.industry.value,source_ref:`classifications/${c.security_id}`}))await p.getByLabel(`${k.replaceAll("_"," ")} ${i+1}`,{exact:true}).fill(v);
    await p.getByLabel(`Evidence source ${i+1}`,{exact:true}).selectOption(preview.snapshot.source_sha256);
  }
  await reveal(page,"Review data freshness settings");
  const labels=["Maximum mark age days","Maximum snapshot age days","Maximum benchmark age days","Maximum history age days","Maximum universe size"];
  const keys=["max_mark_age_days","max_snapshot_age_days","max_benchmark_age_days","max_history_age_days","maximum_universe_size"];
  for(let i=0;i<keys.length;i++)await p.getByLabel(labels[i],{exact:true}).fill(String(modeled.profile[keys[i]]));
  const names=["Annual tracking error","Maximum orders","Turnover","Minimum trade notional","Maximum trade notional","Maximum position weight","Sector exposure","Industry exposure"];
  for(const [i,c]of modeled.investor_controls.entries()) {
    await p.getByText(`${names[i]}: Unresolved`,{exact:true}).click();await p.getByLabel(`${names[i]} choice`,{exact:true}).selectOption(c.enabled?"enabled":"disabled");
    if(c.enabled)await p.getByLabel(new RegExp(`^${names[i]} value`)).fill(c.value.value);
    await p.getByLabel(`${names[i]} declaration reference`,{exact:true}).fill(c.reference);
  }
  expect((await api(server,"/inputs/context")).fact_run_ids).toEqual([]);
}
const prepare=page=>panel(page).getByRole("button",{name:"Prepare and review EOD inputs",exact:true}).click();
const confirm=page=>panel(page).getByLabel("I reviewed the prepared sources, exclusions, settings and unresolved exceptions",{exact:true}).check();

test("native EOD preparation resolves conflicts, saves identical retry and hands off to candidate worksheet and recovery",async({page})=>{
  test.setTimeout(120000);const source=await runtime({dist}),target=await runtime({dist});try {
    const preview=await seed(source);await open(page,source);await context(page);await window(page);await declarations(page,source,preview);await prepare(page);
    await expect(panel(page).getByRole("article",{name:"Preparation exceptions",exact:true})).toContainText("lot_mark_conflict");
    await expect(panel(page).getByRole("article",{name:"Effective risk settings",exact:true})).toContainText("Standard R1");
    const reviewBox=await panel(page).locator(".preparation-review").boundingBox();expect(reviewBox.y).toBeGreaterThanOrEqual(60);expect(reviewBox.y).toBeLessThan(900);await panel(page).getByRole("button",{name:"Review and save inputs",exact:true}).click();await expect(panel(page).getByLabel("I reviewed the prepared sources, exclusions, settings and unresolved exceptions",{exact:true})).toBeFocused();await confirm(page);await panel(page).getByRole("button",{name:"Use reviewed EOD marks in lot settings",exact:true}).click();await expect(status(page)).toContainText("revision 5");
    await expect(panel(page).getByRole("button",{name:"Save prepared input diagnostics",exact:true})).toHaveCount(0);
    await context(page);await prepare(page);await expect(panel(page).getByRole("article",{name:"Prepared input coverage",exact:true})).toContainText("Inputs ready for exploratory calculation");
    const evidence=path.join(root,".local/mvp223");await mkdir(evidence,{recursive:true});
    // Observe the ordinary collapsed form and consolidated review at both widths.
    for(const summary of await panel(page).locator("details[open] > summary").all())await summary.click();
    for(const [width,name]of [[1280,"desktop"],[390,"narrow"]]) {await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await panel(page).screenshot({path:path.join(evidence,`preparation-${name}.png`)});}
    await page.setViewportSize({width:1280,height:900});
    const bodies=[];let first=true;await page.route("**/api/v1/inputs/diagnostics",async route=>{bodies.push(route.request().postData());if(first){first=false;await route.fetch();await route.abort();}else await route.continue();});
    await confirm(page);await panel(page).getByRole("button",{name:"Save prepared input diagnostics",exact:true}).click();await expect(page.getByRole("button",{name:"Retry identical action",exact:true})).toBeVisible();await page.getByRole("button",{name:"Retry identical action",exact:true}).click();await expect(status(page)).toContainText("input diagnostics saved");await expect(page.getByRole("button",{name:"Refresh workspace",exact:true})).toBeEnabled();expect(bodies).toHaveLength(2);expect(bodies[0]).toBe(bodies[1]);
    const state=await api(source,"/current"),saved=await api(source,`/runs/${state.current_run_id}`);expect(saved.inputs.modeled_request.bundle.assembly.history_batch_ids).toHaveLength(1);expect(saved.outputs.security_ids).toEqual(["security-faaa","security-fbbb"]);
    const command=await load("command.json");command.input_run_id="requires-explicit-handoff";command.expected_revision=5;command.controls.buy_bounds={"security-faaa":0,"security-fbbb":0};
    await prepareUpload(page,"Candidate controls JSON");await page.getByLabel("Candidate controls JSON",{exact:true}).setInputFiles({name:"controls.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(command))});await page.getByRole("button",{name:"Use this saved input run",exact:true}).click();await expect(page.getByLabel("Candidate input run ID",{exact:true})).toHaveValue(saved.id);await page.getByLabel("I reviewed the saved inputs, costs, funding and bounded search controls",{exact:true}).check();await page.getByRole("button",{name:"Create exploratory proposals",exact:true}).click();
    await expect(page.getByRole("article",{name:"Checked candidate result",exact:true})).toContainText("Checked whole-share incumbent",{timeout:65000});
    await navigate(page,"Worksheets");const worksheets=page.getByRole("region",{name:"Comparison and manual worksheet",exact:true});await worksheets.getByRole("button",{name:"Review proposal 1",exact:true}).click();await worksheets.getByRole("button",{name:"Check worksheet quantities",exact:true}).click();await expect(worksheets.getByRole("article",{name:"Worksheet final checks",exact:true})).toBeVisible();await worksheets.getByLabel("I confirm no external account changes since this snapshot; after external changes I will import refreshed holdings",{exact:true}).check();await worksheets.getByRole("button",{name:"Save dated manual worksheet",exact:true}).click();await expect.poll(async()=>(await api(source,"/catalog")).worksheets.length).toBe(1);
    const id=(await api(source,"/catalog")).worksheets[0],worksheet=await api(source,`/worksheets/${id}`);expect(worksheet.check.metrics.price_loss).toBeCloseTo(2*(160-125.49071432455037),10);expect(worksheet.check.metrics.final_cash).toBeCloseTo(2*125.49071432455037,10);
    const downloaded=page.waitForEvent("download");await worksheets.getByRole("button",{name:"Download dated text worksheet",exact:true}).click();expect((await readFile(await (await downloaded).path())).toString()).toContain(id);
    const backup=page.waitForEvent("download");await navigate(page,"Settings");await page.getByRole("button",{name:"Download workspace backup",exact:true}).click();const bytes=await readFile(await (await backup).path());
    await open(page,target);await prepareUpload(page,"Current workspace backup (up to 64 MiB)");await page.getByLabel("Current workspace backup (up to 64 MiB)",{exact:true}).setInputFiles({name:"current.sqlite3",mimeType:"application/octet-stream",buffer:bytes});await page.getByRole("button",{name:"Restore into empty workspace",exact:true}).click();await expect(status(page)).toContainText("restored");
    expect(await api(target,`/runs/${saved.id}`)).toEqual(saved);expect(await api(target,`/previews/${preview.id}`)).toEqual(await api(source,`/previews/${preview.id}`));expect(await api(target,`/worksheets/${id}`)).toEqual(worksheet);
    await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption(saved.id);await expect(page.getByRole("article",{name:"Saved modeled inputs",exact:true})).toContainText("Inputs ready for exploratory calculation");
  }finally{await source.stop();await target.stop();}
});

test("unavailable preparation and malformed declarations stay explicit without a bundle or private echo",async({page})=>{
  const server=await runtime({dist});try {
    await open(page,server);await context(page);await panel(page).getByLabel("Completed EOD session",{exact:true}).fill(modeled.analysis_date);await prepare(page);
    await expect(panel(page).getByRole("article",{name:"Preparation exceptions",exact:true})).toContainText("selected_snapshot_required");await expect(panel(page)).toContainText("retained pool unavailable");await panel(page).getByRole("button",{name:"Edit inputs",exact:true}).click();await expect(panel(page)).toContainText("No imported history is available");
    await expect(panel(page).getByRole("button",{name:"Save prepared input diagnostics",exact:true})).toHaveCount(0);
    await panel(page).getByText("Advanced preparation settings",{exact:true}).click();await panel(page).getByLabel("Preparation risk overrides JSON",{exact:true}).fill('{"horizon_sessions":1,"horizon_sessions":2}');await prepare(page);await expect(panel(page).getByRole("alert")).toContainText("refused");
    await panel(page).getByLabel("Preparation risk overrides JSON",{exact:true}).fill('{"PRIVATE":"DO-NOT-ECHO"');await prepare(page);await expect(panel(page).getByRole("alert")).toContainText("Check dates");await expect(panel(page).getByRole("alert")).not.toContainText("DO-NOT-ECHO");
    expect((await api(server,"/current")).revision).toBe(0);
  }finally{await server.stop();}
});

test("explicit saved declarations retain limits and preset; source and settings changes clear review",async({page})=>{
  const server=await runtime({dist});try {
    await seed(server,{saved:true});await open(page,server);await context(page);await window(page);
    await panel(page).getByLabel("Saved identity and taxonomy facts",{exact:true}).selectOption("facts");await panel(page).getByRole("button",{name:"Reuse saved window and investor declarations",exact:true}).click();const sent=page.waitForRequest(r=>r.url().endsWith("/inputs/prepare"));await prepare(page);expect((await sent).postDataJSON().investor_controls).toEqual(modeled.investor_controls.map(c=>({group:null,kind:null,...c})));
    await expect(panel(page).getByRole("article",{name:"Effective risk settings",exact:true})).toContainText("Standard R1");await confirm(page);
    await reveal(page,"Review data freshness settings");await panel(page).getByLabel("Maximum mark age days",{exact:true}).fill("-1");await expect(panel(page).getByRole("button",{name:"Save prepared input diagnostics",exact:true})).toHaveCount(0);await prepare(page);await expect(panel(page).getByRole("alert")).toContainText("Check dates");
    await reveal(page,"Review data freshness settings");await panel(page).getByLabel("Maximum mark age days",{exact:true}).fill("3");await prepare(page);await confirm(page);await panel(page).getByRole("button",{name:"Edit inputs",exact:true}).click();await panel(page).getByRole("checkbox",{name:/Use history/}).uncheck();await expect(panel(page).getByRole("button",{name:"Save prepared input diagnostics",exact:true})).toHaveCount(0);await prepare(page);await expect(panel(page).getByRole("article",{name:"Preparation exceptions",exact:true})).toContainText("history_selection_required");
  }finally{await server.stop();}
});

test("late preparation response cannot publish over a refreshed revision",async({page})=>{
  const server=await runtime({dist});let release;const gate=new Promise(resolve=>{release=resolve;});try {
    await seed(server,{saved:true});await open(page,server);await context(page);await window(page);await panel(page).getByLabel("Saved identity and taxonomy facts",{exact:true}).selectOption("facts");await panel(page).getByRole("button",{name:"Reuse saved window and investor declarations",exact:true}).click();
    let entered;const started=new Promise(resolve=>{entered=resolve;});await page.route("**/api/v1/inputs/prepare",async route=>{const response=await route.fetch();entered();await gate;await route.fulfill({response});});
    await prepare(page);await started;await api(server,"/history/clear",{command_key:"other-window",expected_revision:4});await dismissDetails(page);await page.getByRole("button",{name:"Refresh workspace",exact:true}).click();await expect(panel(page)).toContainText("Load current sources after changing");release();await expect(panel(page).getByRole("article",{name:"Preparation exceptions",exact:true})).toHaveCount(0);await expect(panel(page).getByRole("button",{name:"Save prepared input diagnostics",exact:true})).toHaveCount(0);
  }finally{release();await server.stop();}
});

test("invalid selected lot settings remain a located preparation blocker",async({page})=>{
  const server=await runtime({dist});try {
    await seed(server,{saved:true});const state=await api(server,"/current");
    await api(server,"/settings",{settings:{...state.settings,lot_opportunities:{}},command_key:"invalid-lot-settings",expected_revision:4});
    await open(page,server);await context(page);await window(page);await panel(page).getByLabel("Saved identity and taxonomy facts",{exact:true}).selectOption("facts");await panel(page).getByRole("button",{name:"Reuse saved window and investor declarations",exact:true}).click();await prepare(page);
    await expect(panel(page).getByRole("article",{name:"Preparation exceptions",exact:true})).toContainText("Add cash and cost settings");await expect(panel(page).getByRole("article",{name:"Prepared settings and funding",exact:true})).toContainText("Selected cash budget USD Unknown");await expect(panel(page).getByRole("button",{name:"Use reviewed EOD marks in lot settings",exact:true})).toHaveCount(0);
    await panel(page).locator(".issue-item").filter({has:page.getByText("Add cash and cost settings",{exact:true})}).getByRole("button",{name:"Review this question",exact:true}).click();await expect(page.getByRole("heading",{level:1,name:"Holdings",exact:true})).toBeVisible();await page.getByRole("button",{name:"Return to input preparation",exact:true}).click();await expect(panel(page).getByRole("article",{name:"Preparation exceptions",exact:true})).toBeVisible();await expect(page.getByRole("button",{name:"Refresh workspace",exact:true})).toBeEnabled();
  }finally{await server.stop();}
});
