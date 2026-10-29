import { dismissDetails, navigate, reveal, advancedImport, savedRecords, historyTools, workspaceTools, prepareUpload, sourceDetails } from "../tools/workspace.mjs";
test.beforeEach(({page})=>page.setDefaultTimeout(10000));
import { test, expect } from "@playwright/test";
import { readFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { runtime, root } from "../tools/runtime.mjs";

const dist=path.join(root,"frontend/dist");
const load=async file=>JSON.parse(await readFile(path.join(root,"examples/synthetic",file)));
const csv=await load("blackrock/current-observation.json");
const mapping=await load("blackrock/current-review.json");
const vanguard=await load("benchmark/current-observation.json");
const vanguardMapping=await load("benchmark/current-review.json");
const form=page=>page.getByRole("region",{name:"Prepare benchmark review",exact:true});
const result=page=>page.getByRole("article",{name:"Benchmark proxy review",exact:true});
const status=page=>page.getByRole("status",{name:"Workspace status"});
async function api(server,route,body) {const token=await server.session();const r=await fetch(server.origin+route,{method:body?"POST":"GET",headers:{Origin:server.origin,Authorization:`Bearer ${token}`,...(body?{"Content-Type":"application/json"}:{})},body:body?JSON.stringify(body):undefined});expect(r.ok).toBe(true);return r.json();}
async function open(page,server,id) {await page.goto(server.origin);await navigate(page,"Analysis","Benchmark");await expect(status(page)).toContainText("Workspace read");await page.getByRole("combobox",{name:"Retained benchmark observation",exact:true}).selectOption(id);await expect(form(page).getByRole("button",{name:"Preview prepared benchmark review",exact:true})).toBeVisible();}
async function metadata(page,review=mapping) {
  const view=form(page);const ev=review.stipulation.fund_assertion;
  if(!await view.getByLabel("Fund metadata file (up to 4 MiB)",{exact:true}).isVisible())await view.getByText("Advanced fund metadata",{exact:true}).click();
  await prepareUpload(view,"Fund metadata file (up to 4 MiB)");await view.getByLabel("Fund metadata file (up to 4 MiB)",{exact:true}).setInputFiles({name:"fictional-metadata.txt",mimeType:"text/plain",buffer:Buffer.from(review.metadata_base64,"base64")});
  for(const [label,value] of [["Metadata fund ticker",review.metadata_ticker],["Metadata portfolio ID",review.metadata_port_id],["Metadata fund CUSIP",review.metadata_cusip]])await view.getByRole("combobox",{name:label,exact:true}).selectOption(value);
  await view.getByLabel("Metadata holdings date",{exact:true}).fill(review.metadata_as_of);
  const evidence=view.getByRole("group",{name:"Fund identity evidence",exact:true});
  await evidence.getByRole("combobox",{name:"Evidence source",exact:true}).selectOption("metadata");
  await evidence.getByLabel("Evidence reference",{exact:true}).fill(ev.reference);
  await evidence.getByLabel("Evidence effective date",{exact:true}).fill(ev.effective);
  await evidence.getByLabel("Evidence recorded date",{exact:true}).fill(ev.recorded);
  await evidence.getByLabel("Evidence valid through",{exact:true}).fill(ev.valid_through);
  await view.getByLabel("I reviewed this metadata file for the declared fund identity and holdings date",{exact:true}).check();
}
async function preview(page) {await form(page).getByRole("button",{name:"Preview prepared benchmark review",exact:true}).click();}
async function completeCsv(page) {
  const view=form(page);await metadata(page);
  await view.getByText("Benchmark cash declaration",{exact:true}).click();
  await view.getByLabel("Benchmark cash raw amount",{exact:true}).fill("0");
  await view.getByRole("combobox",{name:"Benchmark cash convention",exact:true}).selectOption("decimal");
  await view.getByRole("button",{name:"Use fund evidence for cash",exact:true}).click();
  await view.locator("summary").filter({hasText:"holdings: 6 rows"}).click();
  const section=view.getByRole("group",{name:"Section holdings",exact:true});
  await section.getByRole("combobox",{name:"Section role",exact:true}).selectOption("primary");
  await section.getByLabel("Published weight field",{exact:true}).fill("percentOfFunds");
  await section.getByRole("combobox",{name:"Published weight convention",exact:true}).selectOption("percent");
  await section.getByLabel("Source market value field",{exact:true}).fill("marketValue");
  await section.getByRole("combobox",{name:"Value currency",exact:true}).selectOption("USD");
  await section.getByRole("button",{name:"Use fund evidence for this section",exact:true}).click();
  await view.getByLabel("Select this page for explicit bulk edits",{exact:true}).check();
  await view.getByLabel("Exclusion reason for selected rows",{exact:true}).fill("Reviewed unsupported instrument; excluded value is not cash");
  await view.getByRole("button",{name:"Exclude selected rows with this reason",exact:true}).click();
  await view.getByRole("button",{name:"Apply fund evidence to selected rows",exact:true}).click();
  for(let index=0;index<2;index++) {
    const row=view.getByRole("article",{name:`Review row holdings:${index}`,exact:true});await row.locator("summary").click();
    await row.getByRole("combobox",{name:"Primary row decision",exact:true}).selectOption("include");
    await row.getByLabel("Decision reason",{exact:true}).fill("Explicit reviewed ordinary equity");
    await row.getByLabel("Canonical security ID",{exact:true}).fill(`FICTIONAL-${index}`);
    await row.getByLabel("Security currency",{exact:true}).fill("USD");await row.getByLabel("Security asset type",{exact:true}).fill("stock");
  }
}

test("form creates a source-bound reviewed benchmark without review JSON and preserves save/restore output",async({page})=>{
  const server=await runtime({dist});const target=await runtime({dist});try {
    const staged=await api(server,"/api/v1/previews",await load("advisory-workspace.json"));await api(server,"/api/v1/select",{snapshot_id:staged.id,command_key:"holdings",expected_revision:0});
    await api(server,"/api/v1/benchmarks/import",csv);await open(page,server,csv.request.observation_id);
    let submitted;await page.route("**/api/v1/benchmarks/review",async route=>{submitted=route.request().postDataJSON();await route.continue();});
    await expect(form(page).getByRole("combobox",{name:"Metadata fund ticker",exact:true,includeHidden:true})).toHaveValue("");
    await completeCsv(page);await preview(page);
    await expect(result(page)).toContainText("estimated-equity-benchmark");await expect(result(page)).toContainText("6 source rows; 2 included equities; 4 excluded");
    expect(submitted.stipulation.raw_sha256).toBe(mapping.stipulation.raw_sha256);
    expect(submitted.stipulation.rows.map(r=>r.row_sha256)).toEqual(mapping.stipulation.rows.map(r=>r.row_sha256));
    expect((await api(server,"/api/v1/current")).settings.benchmark_run_id).toBeUndefined();
    await page.getByLabel("I reviewed fund identity, reporting date, row accounting and exclusions",{exact:true}).check();
    await page.getByRole("button",{name:"Save reviewed benchmark result",exact:true}).click();await expect(status(page)).toContainText("benchmark result saved");
    await navigate(page,"Analysis","Benchmark");await page.getByRole("button",{name:"Select this reviewed benchmark",exact:true}).click();await expect(status(page)).toContainText("revision 2");
    const current=await api(server,"/api/v1/current");const saved=await api(server,`/api/v1/runs/${current.settings.benchmark_run_id}`);
    expect(saved.outputs.equity_value_total).toBe("90000.0");expect(saved.outputs.weights[0]).toBeCloseTo(2/3,14);expect(saved.outputs.weights[1]).toBeCloseTo(1/3,14);expect(saved.outputs.ledger[1].raw_percentage).toBeNull();
    const download=page.waitForEvent("download");await navigate(page,"Settings");await page.getByRole("button",{name:"Download workspace backup",exact:true}).click();const bytes=await readFile(await (await download).path());
    await page.goto(target.origin);await navigate(page,"Analysis","Benchmark");await expect(status(page)).toContainText("Workspace read");await prepareUpload(page,"Current workspace backup (up to 64 MiB)");await page.getByLabel("Current workspace backup (up to 64 MiB)",{exact:true}).setInputFiles({name:"workspace.sqlite3",mimeType:"application/octet-stream",buffer:bytes});
    await page.getByRole("button",{name:"Restore into empty workspace",exact:true}).click();await expect(status(page)).toContainText("restored");expect(await api(target,`/api/v1/runs/${saved.id}`)).toEqual(saved);
    await page.reload();await navigate(page,"Analysis","Benchmark");await expect(status(page)).toContainText("Workspace read");await page.getByRole("combobox",{name:"Retained benchmark observation",exact:true}).selectOption(csv.request.observation_id);
    await expect(form(page).getByRole("combobox",{name:"Metadata fund ticker",exact:true,includeHidden:true})).toHaveValue("");
    await mkdir(path.join(root,".local/mvp13"),{recursive:true});await form(page).screenshot({path:path.join(root,".local/mvp13/review-form.png")});
    await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  }finally{await server.stop();await target.stop();}
});

test("partial and stale evidence stays incomplete; contradictions and edits cannot reuse an older preview",async({page})=>{
  const server=await runtime({dist});try {
    await api(server,"/api/v1/benchmarks/import",csv);await api(server,"/api/v1/benchmarks/import",vanguard);await open(page,server,csv.request.observation_id);
    await expect(form(page).getByRole("button",{name:"Preview prepared benchmark review",exact:true})).toBeDisabled();
    await metadata(page);await preview(page);await expect(result(page)).toContainText("incomplete");await expect(result(page)).toContainText("6 source rows; 2 included equities; 4 excluded");await expect(result(page)).toContainText("benchmark_cash");
    await form(page).getByRole("combobox",{name:"Metadata fund ticker",exact:true}).selectOption("ITOT");await expect(result(page)).toHaveCount(0);await expect(form(page).getByRole("button",{name:"Preview prepared benchmark review",exact:true})).toBeDisabled();
    await form(page).getByLabel("I reviewed this metadata file for the declared fund identity and holdings date",{exact:true}).check();await preview(page);
    await expect(page.getByRole("region",{name:"Standard benchmark",exact:true}).getByRole("alert").filter({hasText:"Invalid benchmark"})).toBeVisible();
    await form(page).getByRole("combobox",{name:"Metadata fund ticker",exact:true}).selectOption("IVV");
    await form(page).getByRole("group",{name:"Fund identity evidence",exact:true}).getByLabel("Evidence valid through",{exact:true}).fill("2026-10-19");
    await form(page).getByLabel("I reviewed this metadata file for the declared fund identity and holdings date",{exact:true}).check();
    await preview(page);await expect(result(page)).toContainText("incomplete");await expect(result(page)).toContainText("independent_stipulated_fund_assertion_required");
    await page.getByRole("combobox",{name:"Retained benchmark observation",exact:true}).selectOption(vanguard.request.observation_id);
    await expect(form(page).getByRole("combobox",{name:"Metadata fund ticker",exact:true,includeHidden:true})).toHaveValue("");await expect(result(page)).toHaveCount(0);
    await expect(form(page)).toContainText("8 retained rows; 0 prepared or edited");expect((await api(server,"/api/v1/current")).revision).toBe(0);
  }finally{await server.stop();}
});

test("failed or superseded review-context reads never supply an empty or wrong draft",async({page})=>{
  const server=await runtime({dist});let release=()=>{};try {
    await api(server,"/api/v1/benchmarks/import",csv);await api(server,"/api/v1/benchmarks/import",vanguard);
    await page.route("**/api/v1/benchmarks/review-context",route=>route.abort());
    await page.goto(server.origin);await navigate(page,"Analysis","Benchmark");await expect(status(page)).toContainText("Workspace read");await page.getByRole("combobox",{name:"Retained benchmark observation",exact:true}).selectOption(csv.request.observation_id);
    await expect(form(page).getByRole("alert")).toContainText("No empty source is assumed");await expect(form(page).getByRole("button",{name:"Preview prepared benchmark review",exact:true})).toHaveCount(0);
    await page.unroute("**/api/v1/benchmarks/review-context");await form(page).getByRole("button",{name:"Retry review preparation",exact:true}).click();await expect(form(page)).toContainText("6 retained rows; 6 prepared or edited");
    let started;const waiting=new Promise(resolve=>started=resolve);const gate=new Promise(resolve=>release=resolve);
    await page.route("**/api/v1/benchmarks/review-context",async route=>{if(route.request().postDataJSON().observation_id===vanguard.request.observation_id){started();await gate;}await route.continue();});
    await page.getByRole("combobox",{name:"Retained benchmark observation",exact:true}).selectOption(vanguard.request.observation_id);await waiting;
    await page.getByRole("combobox",{name:"Retained benchmark observation",exact:true}).selectOption(csv.request.observation_id);await expect(form(page)).toContainText("6 retained rows; 6 prepared or edited");release();
    await expect(form(page)).toContainText("Review for IVV / 2026-10-20");await expect(form(page)).not.toContainText("8 retained rows");
  }finally{release();await server.stop();}
});

test("paged selected row edits retain untouched rows and explicit link targets stay subject to validation",async({page})=>{
  const server=await runtime({dist});try {
    const source=structuredClone(vanguard);source.request.observation_id="paged-review";
    const document={"2000-01-03":{equity:Array.from({length:23},(_,i)=>({holdingName:`Fictional ${i}`,ticker:`F${i}`,currency:"USD",marketValue:"1.00",percentOfFunds:"1"}))}};
    source.source_base64=Buffer.from(JSON.stringify(document)).toString("base64");await api(server,"/api/v1/benchmarks/import",source);await open(page,server,"paged-review");
    const view=form(page);await metadata(page,vanguardMapping);
    await view.getByLabel("Select this page for explicit bulk edits",{exact:true}).check();await view.getByLabel("Exclusion reason for selected rows",{exact:true}).fill("Explicitly reviewed exclusion");
    await view.getByRole("button",{name:"Exclude selected rows with this reason",exact:true}).click();await view.getByRole("button",{name:"Apply fund evidence to selected rows",exact:true}).click();
    await view.getByRole("button",{name:"Next review rows",exact:true}).click();await expect(view.getByRole("status")).toContainText("20 selected across pages");
    const row=view.getByRole("article",{name:"Review row equity:20",exact:true});await row.locator("summary").click();await row.getByLabel("Linked primary section",{exact:true}).fill("equity");await row.getByLabel("Linked primary row index",{exact:true}).fill("999");
    let submitted;await page.route("**/api/v1/benchmarks/review",async route=>{submitted=route.request().postDataJSON();await route.continue();});
    await preview(page);await expect(result(page)).toContainText("incomplete");await expect(result(page)).toContainText("23 source rows");expect(submitted.stipulation.rows).toHaveLength(21);expect(submitted.policy.decisions).toHaveLength(20);expect(submitted.stipulation.rows[20].target).toEqual({section:"equity",index:999});
    await expect(result(page)).toContainText("row_disposition_missing");expect((await api(server,"/api/v1/current")).settings).toEqual({});
  }finally{await server.stop();}
});

test("IVV preparation fills source-bound rows and exclusions without manual row authoring",async({page})=>{
  const server=await runtime({dist});try {
    await api(server,"/api/v1/benchmarks/import",csv);await open(page,server,csv.request.observation_id);
    const view=form(page);const coverage=view.getByRole("region",{name:"Prepared mapping coverage",exact:true});
    await expect(coverage).toContainText("2 mapped equities; 4 explicit exclusions");
    await expect(coverage).toContainText("Exclusion coverage unavailable");await expect(coverage).toContainText("1 unknown USD values");
    await expect(coverage).toContainText("History and tax eligibility: not assessed");
    await metadata(page);await view.getByText("Benchmark cash declaration",{exact:true}).click();
    await view.getByLabel("Benchmark cash raw amount",{exact:true}).fill("0");await view.getByRole("combobox",{name:"Benchmark cash convention",exact:true}).selectOption("decimal");await view.getByRole("button",{name:"Use fund evidence for cash",exact:true}).click();
    let submitted;await page.route("**/api/v1/benchmarks/review",async route=>{submitted=route.request().postDataJSON();await route.continue();});
    await preview(page);await expect(result(page)).toContainText("estimated-equity-benchmark");await expect(result(page)).toContainText("6 source rows; 2 included equities; 4 excluded");
    expect(submitted.stipulation.rows.map(row=>row.security?.security_id??null)).toEqual(["FIAA","FIBB",null,null,null,null]);
    expect(submitted.policy.decisions.map(row=>row.action)).toEqual(["include","include","exclude","exclude","exclude","exclude"]);
    const first=view.getByRole("article",{name:"Review row holdings:0",exact:true});await first.locator("summary").click();
    await first.getByRole("combobox",{name:"Primary row decision",exact:true}).selectOption("exclude");await first.getByLabel("Decision reason",{exact:true}).fill("Explicit owner exclusion");await expect(result(page)).toHaveCount(0);
    await preview(page);await expect(result(page)).toContainText("6 source rows; 1 included equities; 5 excluded");
    expect((await api(server,"/api/v1/current")).settings).toEqual({});
    await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  }finally{await server.stop();}
});

test("official metadata and proxy cash prepare without manual fields and survive retry/save/restore",async({page})=>{
  const server=await runtime({dist});const target=await runtime({dist});try {
    const raw=await readFile(path.join(root,"examples/synthetic/blackrock/metadata.html"));
    const supplied={collected_at:"2026-10-22T12:00:00Z",response_url:"https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf",content_type:"text/html",http_status:200,body_complete:true,source_base64:raw.toString("base64")};
    const staged=await api(server,"/api/v1/previews",await load("advisory-workspace.json"));await api(server,"/api/v1/select",{snapshot_id:staged.id,command_key:"holdings",expected_revision:0});await api(server,"/api/v1/benchmarks/import",csv);
    let attempts=0;await page.route("**/api/v1/benchmarks/prepare",async route=>{attempts++;if(attempts===1){await route.abort();return;}await route.continue({postData:JSON.stringify({...route.request().postDataJSON(),metadata_response:supplied})});});
    await open(page,server,csv.request.observation_id);const view=form(page);const official=view.getByRole("region",{name:"Official fund preparation",exact:true});
    await official.getByRole("button",{name:"Prepare official fund metadata",exact:true}).click();await expect(official.getByRole("alert")).toContainText("No alternate source or date");
    await official.getByRole("button",{name:"Prepare official fund metadata",exact:true}).click();await expect(official).toContainText("Automatically checked: IVV, CUSIP 464287200, holdings date 2026-10-20");await expect(official).toContainText("Modeled benchmark cash: 0");
    await expect(view.getByLabel("I reviewed this metadata file for the declared fund identity and holdings date",{exact:true})).not.toBeChecked();
    await preview(page);await expect(result(page)).toContainText("estimated-equity-benchmark");
    await page.getByText("Supplied review decisions and evidence",{exact:true}).click();const download=page.waitForEvent("download");await page.getByRole("button",{name:"Download supplied fund metadata",exact:true}).click();expect(await readFile(await (await download).path())).toEqual(raw);
    await page.getByLabel("I reviewed fund identity, reporting date, row accounting and exclusions",{exact:true}).check();await page.getByRole("button",{name:"Save reviewed benchmark result",exact:true}).click();await expect(status(page)).toContainText("benchmark result saved");await navigate(page,"Analysis","Benchmark");await page.getByRole("button",{name:"Select this reviewed benchmark",exact:true}).click();await expect(status(page)).toContainText("revision 2");
    const current=await api(server,"/api/v1/current");const saved=await api(server,`/api/v1/runs/${current.settings.benchmark_run_id}`);expect(saved.outputs.equity_value_total).toBe("90000.0");
    const backup=page.waitForEvent("download");await navigate(page,"Settings");await page.getByRole("button",{name:"Download workspace backup",exact:true}).click();const bytes=await readFile(await (await backup).path());
    await page.goto(target.origin);await navigate(page,"Analysis","Benchmark");await expect(status(page)).toContainText("Workspace read");await prepareUpload(page,"Current workspace backup (up to 64 MiB)");await page.getByLabel("Current workspace backup (up to 64 MiB)",{exact:true}).setInputFiles({name:"workspace.sqlite3",mimeType:"application/octet-stream",buffer:bytes});await page.getByRole("button",{name:"Restore into empty workspace",exact:true}).click();await expect(status(page)).toContainText("restored");
    await page.unroute("**/api/v1/benchmarks/prepare");await navigate(page,"Analysis","Benchmark");await page.getByRole("combobox",{name:"Retained benchmark observation",exact:true}).selectOption(csv.request.observation_id);await expect(form(page).getByRole("region",{name:"Official fund preparation",exact:true})).toContainText("Automatically checked: IVV");expect(await api(target,`/api/v1/runs/${saved.id}`)).toEqual(saved);
    await preview(page);await expect(result(page)).toContainText("estimated-equity-benchmark");
    await mkdir(path.join(root,".local/mvp18"),{recursive:true});await form(page).getByRole("region",{name:"Official fund preparation",exact:true}).screenshot({path:path.join(root,".local/mvp18/fictional-preparation.png")});
    await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  }finally{await server.stop();await target.stop();}
});
