import { dismissDetails, navigate, reveal, advancedImport, savedRecords, historyTools, workspaceTools, prepareUpload, sourceDetails } from "../tools/workspace.mjs";
test.beforeEach(({page})=>page.setDefaultTimeout(10000));
import { test, expect } from "@playwright/test";
import { readFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { runtime, root, python, refreshHistory } from "../tools/runtime.mjs";
const dist=path.join(root,"frontend/dist");
const load=async file=>JSON.parse(await readFile(path.join(root,"examples/synthetic",file)));
const inputs=await load("modeled-inputs/current.json");
const status=page=>page.getByRole("status",{name:"Workspace status"});
async function api(server,route,body) {const token=await server.session();const response=await fetch(server.origin+route,{method:body?"POST":"GET",headers:{Origin:server.origin,Authorization:`Bearer ${token}`, ...(body?{"Content-Type":"application/json"}:{})},body:body?JSON.stringify(body):undefined});expect(response.ok).toBe(true);return response.json();}
async function seed(server) {
  const staged=await api(server,"/api/v1/previews",await load("advisory-workspace.json"));
  await api(server,"/api/v1/select",{snapshot_id:staged.id,command_key:"holdings",expected_revision:0});
  await api(server,"/api/v1/benchmarks/import",await load("modeled-inputs/benchmark.json"));
  await api(server,"/api/v1/benchmarks/diagnostics",{run_id:"benchmark",expected_revision:1,as_of:"2026-10-25T22:00:00Z",review:await load("modeled-inputs/benchmark-review.json")});
  await api(server,"/api/v1/benchmarks/select",{run_id:"benchmark",command_key:"benchmark",expected_revision:1});
  await api(server,"/api/v1/lots/settings",{settings:await load("modeled-inputs/lot-settings.json"),command_key:"lot-settings",expected_revision:2});
  await refreshHistory(server,await load("modeled-inputs/history.json"));
}
async function open(page,server) {await page.goto(server.origin);await navigate(page,"Analysis","Review inputs");await expect(status(page)).toContainText("Workspace read");await page.getByText("Advanced supplied input configuration",{exact:true}).click();}
async function review(page,data=inputs,supplied=true) {await prepareUpload(page,"Modeled input/profile JSON");await page.getByLabel("Modeled input/profile JSON",{exact:true}).setInputFiles({name:"fictional.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(data))});await expect(page.getByRole("article",{name:"Modeled input coverage",exact:true})).toBeVisible();if(supplied){await page.getByText("Advanced settings",{exact:true}).click();await page.getByRole("button",{name:"Use supplied risk settings",exact:true}).click();await expect(page.getByRole("region",{name:"Complete modeled inputs",exact:true}).getByRole("article",{name:"Effective risk settings"})).toContainText("Custom risk settings");}}
async function save(page) {await page.getByLabel("I reviewed the complete union, source coverage, profile and investor settings").check();await page.getByRole("button",{name:"Save modeled input diagnostics",exact:true}).click();}

test("history exclusions remain explicit through browser save and restored original inputs",async({page})=>{
  const source=await runtime({dist}), target=await runtime({dist});try{
    const code="import sys;from pathlib import Path;from tests.test_modeled_sleeve import seed_missing;from tests.test_modeled_inputs import service;seed_missing(service(Path(sys.argv[1])),{'FICTIONAL-0','security-a','security-b'})";
    const seeded=spawnSync(python,["-c",code,source.directory],{cwd:root,encoding:"utf8",windowsHide:true});expect(seeded.status,seeded.stderr).toBe(0);
    await open(page,source);await review(page);
    const coverage=page.getByRole("article",{name:"Modeled input coverage",exact:true});
    await expect(coverage).toContainText("Inputs ready for exploratory calculation");await expect(coverage).toContainText("2 retained securities - 3 required sessions");
    await expect(coverage).toContainText("5 names reviewed; 3 excluded for inadequate history");
    await coverage.getByRole("button",{name:"View included and excluded holdings",exact:true}).click();const rows=page.getByRole("dialog",{name:"History decisions",exact:true}).getByRole("table",{name:"History decisions"}).getByRole("row");
    await expect(rows.filter({hasText:"FICTIONAL-0"})).toContainText("Excluded");await expect(rows.filter({hasText:"ABC"})).toContainText("Excluded");
    await expect(rows.filter({hasText:"FICTIONAL-1"})).toContainText("Retained");
    await dismissDetails(page);await save(page);await expect(status(page)).toContainText("modeled input diagnostics saved");
    const current=await api(source,"/api/v1/current"),saved=await api(source,`/api/v1/runs/${current.current_run_id}`);
    expect(saved.outputs.members.map(m=>m.benchmark_weight)).toEqual([1,0]);expect(saved.outputs.sleeve.decisions).toHaveLength(5);
    expect(saved.inputs.modeled_request.bundle.candidate_security_ids).toEqual(inputs.bundle.candidate_security_ids);
    const event=page.waitForEvent("download");await navigate(page,"Settings");await page.getByRole("button",{name:"Download workspace backup",exact:true}).click();const bytes=await readFile(await (await event).path());
    await open(page,target);await prepareUpload(page,"Current workspace backup (up to 64 MiB)");await page.getByLabel("Current workspace backup (up to 64 MiB)").setInputFiles({name:"current.sqlite3",mimeType:"application/octet-stream",buffer:bytes});await page.getByRole("button",{name:"Restore into empty workspace",exact:true}).click();await expect(status(page)).toContainText("restored");
    await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption(saved.id);
    const restored=page.getByRole("article",{name:"Saved modeled inputs",exact:true});await expect(restored).toContainText("5 names reviewed; 3 excluded");expect(await api(target,`/api/v1/runs/${saved.id}`)).toEqual(saved);
    await mkdir(path.join(root,".local/mvp221"),{recursive:true});await restored.screenshot({path:path.join(root,".local/mvp221/sleeve-desktop.png")});
    await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await restored.screenshot({path:path.join(root,".local/mvp221/sleeve-narrow.png")});
  }finally{await source.stop();await target.stop();}
});

test("complete union, explicit profile and recovered historical input grid remain visible",async({page})=>{
  const source=await runtime({dist});const target=await runtime({dist});try{
    await seed(source);await open(page,source);await review(page);
    const coverage=page.getByRole("article",{name:"Modeled input coverage",exact:true});await expect(coverage).toContainText("Inputs ready for exploratory calculation");await expect(coverage).toContainText("5 retained securities - 3 required sessions");
    await expect(coverage).toContainText("total-return drift from reported holdings 2026-10-20 to 2026-10-23");
    await save(page);await expect(status(page)).toContainText("modeled input diagnostics saved");
    await navigate(page,"Analysis","Review inputs");await page.getByRole("button",{name:"Reuse saved input configuration",exact:true}).click();await expect(coverage).toContainText("Inputs ready for exploratory calculation");await expect(page.getByLabel("I reviewed the complete union, source coverage, profile and investor settings")).not.toBeChecked();
    const state=await api(source,"/api/v1/current");const saved=await api(source,`/api/v1/runs/${state.current_run_id}`);expect(saved.outputs.security_ids).toEqual(["FICTIONAL-0","FICTIONAL-1","security-a","security-b","security-c"]);expect(saved.outputs.risk_available).toBe(false);expect(saved.outputs.members[2].held_quantity).toBe(12.5);
    await historyTools(page);await page.getByLabel("Remove reusable history cache; keep all saved-run inputs and outputs").check();await page.getByRole("button",{name:"Clear reusable history cache"}).click();await expect(status(page)).toContainText("revision 5");
    await navigate(page,"Analysis","Review inputs");await page.getByRole("button",{name:"Recheck current modeled inputs"}).click();await expect(coverage).toContainText("empty_modeled_union");await expect(coverage).toContainText("5 names reviewed; 5 excluded for inadequate history");expect(await api(source,`/api/v1/runs/${saved.id}`)).toEqual(saved);
    const event=page.waitForEvent("download");await navigate(page,"Settings");await page.getByRole("button",{name:"Download workspace backup"}).click();const downloaded=await event;const bytes=await readFile(await downloaded.path());
    await open(page,target);await prepareUpload(page,"Current workspace backup (up to 64 MiB)");await page.getByLabel("Current workspace backup (up to 64 MiB)").setInputFiles({name:"current.sqlite3",mimeType:"application/octet-stream",buffer:bytes});await page.getByRole("button",{name:"Restore into empty workspace"}).click();await expect(status(page)).toContainText("restored");
    await savedRecords(page);await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption(saved.id);const restored=page.getByRole("article",{name:"Saved modeled inputs",exact:true});await expect(restored).toContainText("Inputs ready for exploratory calculation");await expect(restored).toContainText("total-return drift from reported holdings 2026-10-20 to 2026-10-23");expect(await api(target,`/api/v1/runs/${saved.id}`)).toEqual(saved);
    await mkdir(path.join(root,".local/t006.1.6"),{recursive:true});await restored.screenshot({path:path.join(root,".local/t006.1.6/inputs-desktop.png")});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await restored.screenshot({path:path.join(root,".local/t006.1.6/inputs-narrow.png")});
  }finally{await source.stop();await target.stop();}
});

test("lost input result response retries identical frozen request",async({page})=>{
  const server=await runtime({dist});try{await seed(server);await open(page,server);await review(page,inputs,false);const bodies=[];let first=true;
    await page.route("**/api/v1/inputs/diagnostics",async route=>{bodies.push(route.request().postData());if(first){first=false;await route.fetch();await route.abort();}else await route.continue();});
    await save(page);await expect(page.getByRole("button",{name:"Retry identical action"})).toBeVisible();await page.getByRole("button",{name:"Retry identical action"}).click();await expect(status(page)).toContainText("modeled input diagnostics saved");expect(bodies).toHaveLength(2);expect(bodies[0]).toBe(bodies[1]);
    // The success message precedes the workspace refresh. Let it finish before
    // stopping the runtime so teardown cannot sever the catalog request.
    await expect(page.getByRole("button",{name:"Refresh workspace",exact:true})).toBeEnabled();
    await expect(page.getByRole("alert")).toHaveCount(0);
  }finally{await server.stop();}
});

test("standard R1 is visible by default; optional overrides, saved settings and invalid edits are explicit",async({page})=>{
  const server=await runtime({dist});try{
    const minimal=structuredClone(inputs);for(const key of ["model","model_reference","variant","lookback_sessions","minimum_history_sessions","horizon_sessions","annualization_sessions","require_full_window_validation"])delete minimal.bundle.profile[key];delete minimal.bundle.history.profile;
    await seed(server);await open(page,server);await review(page,minimal,false);
    const section=page.getByRole("region",{name:"Complete modeled inputs",exact:true});
    const settings=section.getByRole("article",{name:"Effective risk settings"});
    await expect(settings).toContainText("Standard R1");await expect(settings).toContainText("1260 required sessions");await expect(settings).toContainText("Explicit overrides: None");
    await expect(page.getByLabel("Risk parameter overrides JSON")).not.toBeVisible();
    await expect(section).toContainText("history_length_mismatch");
    await mkdir(path.join(root,".local/mvp21"),{recursive:true});
    await section.screenshot({path:path.join(root,".local/mvp21/risk-standard-desktop.png")});
    await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await section.screenshot({path:path.join(root,".local/mvp21/risk-standard-narrow.png")});await page.setViewportSize({width:1280,height:900});
    await section.getByText("Advanced settings",{exact:true}).click();
    await expect(page.getByRole("button",{name:"Use supplied risk settings",exact:true})).toBeDisabled();
    await page.getByLabel("Risk parameter overrides JSON").fill('{"horizon_sessions":1}');
    await expect(page.getByRole("button",{name:"Save modeled input diagnostics",exact:true})).toHaveCount(0);
    await page.getByRole("button",{name:"Apply standard preset and overrides",exact:true}).click();
    await expect(settings).toContainText("1-session projection");await expect(settings).toContainText('"horizon_sessions":1');
    await save(page);await expect(status(page)).toContainText("modeled input diagnostics saved");
    const current=await api(server,"/api/v1/current"), saved=await api(server,`/api/v1/runs/${current.current_run_id}`);
    const bundle=saved.inputs.modeled_request.bundle;
    expect(bundle.profile.preset).toEqual({identity:"standard-r1-v1",overrides:{horizon_sessions:1}});
    expect(bundle.investor_controls).toEqual(inputs.bundle.investor_controls.map(c=>({group:null,kind:null,...c})));expect(bundle.history.sessions).toEqual(inputs.bundle.history.sessions);
    await navigate(page,"Worksheets");await expect(page.getByRole("article",{name:"Saved diagnostic",exact:true}).getByRole("article",{name:"Effective risk settings"})).toContainText('"horizon_sessions":1');
    await navigate(page,"Analysis","Review inputs");await page.getByRole("button",{name:"Reuse saved input configuration",exact:true}).click();await expect(settings).toContainText("1-session projection");
    await page.getByLabel("Risk parameter overrides JSON").fill('{"horizon_sessions":null}');
    await page.getByRole("button",{name:"Apply standard preset and overrides",exact:true}).click();await expect(section.getByRole("alert")).toContainText("invalid");
    await expect(page.getByRole("button",{name:"Save modeled input diagnostics",exact:true})).toHaveCount(0);
    await page.getByLabel("Risk parameter overrides JSON").fill('{"horizon_sessions":1,"horizon_sessions":21}');
    await page.getByRole("button",{name:"Apply standard preset and overrides",exact:true}).click();await expect(section.getByRole("alert")).toContainText("invalid");
    await page.getByLabel("Risk parameter overrides JSON").fill('{}');await page.getByRole("button",{name:"Apply standard preset and overrides",exact:true}).click();await expect(settings).toContainText("21-session projection");
    expect(await api(server,`/api/v1/runs/${saved.id}`)).toEqual(saved);
  }finally{await server.stop();}
});

test("risk preset preparation cannot publish over a refreshed workspace revision",async({page})=>{
  const server=await runtime({dist});let release;const held=new Promise(resolve=>{release=resolve;});try{
    await seed(server);await open(page,server);
    let started;const pending=new Promise(resolve=>{started=resolve;});
    await page.route("**/api/v1/inputs/risk-preset",async route=>{started();await held;await route.continue();});
    await prepareUpload(page,"Modeled input/profile JSON");await page.getByLabel("Modeled input/profile JSON",{exact:true}).setInputFiles({name:"fictional.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(inputs))});
    await pending;await api(server,"/api/v1/history/clear",{command_key:"other-window",expected_revision:4});
    const refreshed=page.waitForResponse(response=>response.url().endsWith("/api/v1/catalog") && response.ok());
    await dismissDetails(page);await page.getByRole("button",{name:"Refresh workspace",exact:true}).click();await refreshed;await expect(page.getByRole("button",{name:"Refresh workspace",exact:true})).toBeEnabled();
    release();await expect(page.getByRole("alert")).toContainText("Inputs changed while");
    await expect(page.getByRole("article",{name:"Modeled input coverage",exact:true})).toHaveCount(0);
    await expect(page.getByRole("button",{name:"Save modeled input diagnostics",exact:true})).toHaveCount(0);
  }finally{release();await server.stop();}
});

test("missing inputs stay located and malformed files do not echo private values",async({page})=>{
  const server=await runtime({dist});try{await seed(server);await open(page,server);const changed=structuredClone(inputs);changed.bundle.classifications[0].industry={value:null,reason:"Unknown fictional industry"};changed.bundle.marks.pop();await review(page,changed);const coverage=page.getByRole("article",{name:"Modeled input coverage",exact:true});await expect(coverage).toContainText("classification_unknown");await expect(coverage).toContainText("mark_missing");await expect(coverage).toContainText("5 retained securities");await save(page);await expect(status(page)).toContainText("modeled input diagnostics saved");
    await prepareUpload(page,"Modeled input/profile JSON");await page.getByLabel("Modeled input/profile JSON",{exact:true}).setInputFiles({name:"bad.json",mimeType:"application/json",buffer:Buffer.from('{"PRIVATE-KEY":"DO-NOT-ECHO"}')});await expect(page.getByRole("alert")).toContainText("invalid");await expect(page.locator("body")).not.toContainText("DO-NOT-ECHO");
  }finally{await server.stop();}
});

test("refreshed workspace cannot silently save an older reviewed input revision",async({page})=>{
  const server=await runtime({dist});try{await seed(server);await open(page,server);await review(page);await api(server,"/api/v1/history/clear",{command_key:"other-window",expected_revision:4});await dismissDetails(page);await page.getByRole("button",{name:"Refresh workspace",exact:true}).click();await expect(status(page)).toContainText("Workspace read");await save(page);await expect(status(page)).toContainText("Action refused");expect((await api(server,"/api/v1/current")).revision).toBe(5);
  }finally{await server.stop();}
});


test("alignment resource refusal keeps sources and reports the risk blocker",async({page})=>{
  const server=await runtime({dist});try{
    await seed(server);await open(page,server);await review(page);
    await page.route("**/api/v1/inputs/diagnostics",route=>route.fulfill({status:413,contentType:"application/json",body:JSON.stringify({error:"history_alignment_size_limit",issues:[]})}));
    await save(page);await expect(page.getByRole("alert")).toContainText("Retained sources remain available; risk diagnostics are blocked");
    expect((await api(server,"/api/v1/current")).revision).toBe(4);
    expect((await api(server,"/api/v1/catalog")).snapshots).toHaveLength(1);
  }finally{await server.stop();}
});
