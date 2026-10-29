import { dismissDetails, navigate, reveal, advancedImport, savedRecords, historyTools, workspaceTools, prepareUpload, sourceDetails } from "../tools/workspace.mjs";
test.beforeEach(({page})=>page.setDefaultTimeout(10000));
import { test, expect } from "@playwright/test";
import { spawnSync } from "node:child_process";
import { readFile, mkdir, mkdtemp, writeFile, rename } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { runtime, root, refreshHistory } from "../tools/runtime.mjs";

// Deliberate installed-artifact check, not an automatic artifact build/model study.
// An explicit path binds evidence to the built candidate rather than a stale default.
const artifact=process.env.PROSPER_TEST_ARTIFACT;
test.skip(!artifact,"Set PROSPER_TEST_ARTIFACT to the freshly built local artifact");
const fixture=path.join(root,"examples/synthetic/candidates/application");
const load=async name=>JSON.parse(await readFile(path.join(fixture,name)));
async function api(server,route,body,expected=200) {
  const token=await server.session();const response=await fetch(server.origin+route,{method:body?"POST":"GET",headers:{Origin:server.origin,Authorization:`Bearer ${token}`,...(body?{"Content-Type":"application/json"}:{})},body:body?JSON.stringify(body):undefined});
  expect(response.status).toBe(expected);return response.json();
}
function initialize(directory) {
  const result=spawnSync("powershell.exe",["-NoProfile","-File",path.join(artifact,"Launch.ps1"),"-Command","initialize","-Workspace",directory],{cwd:artifact,windowsHide:true,encoding:"utf8"});
  expect(result.status,result.stderr).toBe(0);
}

test("installed artifact serves offline UI, fits in its worker and preserves recovery after interruption",async({page})=>{
  test.setTimeout(90000);
  const evidence="mvp-reset";
  await mkdir(path.join(root,".local",evidence),{recursive:true});
  // Fictional-only research runtime deliberately outside the checkout/artifact.
  const area=await mkdtemp(path.join(tmpdir(),"prosper-mvp-fixture-"));await mkdir(area,{recursive:true});
  const directory=path.join(area,"source");const restoredDirectory=path.join(area,"restored");initialize(directory);initialize(restoredDirectory);
  const open=options=>runtime({artifact,...options});
  let source=await open({directory});let target;
  const external=[];
  try {
    await page.route("**/*",route=>{const url=route.request().url();if(!url.startsWith(source.origin+"/")){external.push(url);return route.abort();}return route.continue();});
    await page.setViewportSize({width:390,height:844});
    await page.goto(source.origin);await advancedImport(page);await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("Workspace read");
    await expect(page.getByRole("status",{name:"Workspace purpose"})).toContainText("Exploratory estimates; financial use unauthorized");
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    expect(await api(source,"/runtime")).toEqual({purpose:"exploratory",financial_use_authorized:false});
    expect(await page.locator("body").innerText()).not.toContain(directory);
    expect(external).toEqual([]);
    const initial=await api(source,"/api/v1/current");expect(initial.revision).toBe(0);
    const raw=await readFile(path.join(fixture,"lifecycle/initial.csv"));
    const context=JSON.parse(await readFile(path.join(fixture,"lifecycle/initial-context.json")));
    const staged=await api(source,"/api/v1/fidelity/previews",{context,source_base64:raw.toString("base64")});
    const snapshot=staged.preview.snapshot;const lot=snapshot.lots[0].id;
    await api(source,"/api/v1/select",{snapshot_id:staged.preview.id,command_key:"holdings",expected_revision:0});
    await api(source,"/api/v1/benchmarks/import",await load("benchmark.json"));
    await api(source,"/api/v1/benchmarks/diagnostics",{run_id:"benchmark",expected_revision:1,as_of:"2026-10-25T23:00:00Z",review:await load("benchmark-review.json")});
    await api(source,"/api/v1/benchmarks/select",{run_id:"benchmark",command_key:"benchmark",expected_revision:1});
    await api(source,"/api/v1/lots/settings",{settings:await load("lot-settings.json"),command_key:"settings",expected_revision:2});
    await refreshHistory(source,await load("history.json"));
    await api(source,"/api/v1/inputs/diagnostics",{...await load("modeled.json"),run_id:"inputs",expected_revision:4,as_of:"2026-10-25T23:00:00Z"});
    const command=await load("command.json");command.controls.sale_bounds={[lot]:2};
    await api(source,"/api/v1/candidates/start",command);
    await expect.poll(async()=>(await api(source,"/api/v1/runs/candidate")).outputs.outcome,{timeout:65000}).toBe("checked");
    const run=await api(source,"/api/v1/runs/candidate");expect(run.outputs.search.best.metrics.price_loss).toBe(4);expect(run.outputs.search.best.metrics.final_cash).toBe(20);
    const saved=await api(source,"/api/v1/worksheets",{id:"installed-worksheet",parent_id:null,run_id:"candidate",expected_revision:4,as_of:new Date().toISOString(),no_external_changes:true,orders:{sales:[{lot_id:lot,shares:1}],buys:[]}});
    expect(saved.check.metrics.price_loss).toBe(2);expect(saved.check.metrics.final_quantities).toEqual([1.5,0]);
    const token=await source.session();const backupResponse=await fetch(source.origin+"/api/v1/backup",{headers:{Origin:source.origin,Authorization:`Bearer ${token}`}});expect(backupResponse.ok).toBe(true);const backup=Buffer.from(await backupResponse.arrayBuffer());
    // Graceful restart followed by a real process-tree interruption. Workers
    // have completed here; in-flight cancellation/rollback has focused pytest.
    await source.stop();source=await open({directory});expect(await api(source,"/api/v1/runs/candidate")).toEqual(run);
    await source.interrupt();source=await open({directory});expect(await api(source,"/api/v1/runs/candidate")).toEqual(run);
    await page.unroute("**/*");await page.goto(source.origin);await advancedImport(page);await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("Workspace read");
    await navigate(page,"Worksheets");await reveal(page,"Advanced worksheet lookup");await page.getByRole("combobox",{name:"Saved manual worksheet",exact:true}).selectOption("installed-worksheet");await expect(page.getByRole("article",{name:"Saved manual worksheet",exact:true})).toContainText("$2.00");
    const unauthorized=await fetch(source.origin+"/api/v1/current",{headers:{Origin:source.origin}});expect(unauthorized.status).toBe(401);
    const foreign=await fetch(source.origin+"/session",{method:"POST",headers:{Origin:"http://127.0.0.1:1","X-Prosper-Bootstrap":"1"}});expect(foreign.status).toBe(403);
    target=await open({directory:restoredDirectory});const targetToken=await target.session();
    const restore=await fetch(target.origin+"/api/v1/restore",{method:"POST",headers:{Origin:target.origin,Authorization:`Bearer ${targetToken}`,"Content-Type":"application/octet-stream"},body:backup});expect(restore.ok).toBe(true);
    expect(await api(target,"/api/v1/runs/candidate")).toEqual(run);expect(await api(target,"/api/v1/worksheets/installed-worksheet")).toEqual(saved);
    await writeFile(path.join(area,"backup.sqlite3"),backup);
    // Query the installed stores without recalculating historical results;
    // compare every original source BLOB, including history/benchmark sources.
    const inspected=spawnSync(path.join(artifact,".venv/Scripts/python.exe"),["-I","-c","import sqlite3,sys,json,hashlib; from pathlib import Path; from prosper.source_blob import unpack; paths=[Path(p)/'.local/workspace/advisory-v1.sqlite3' for p in sys.argv[1:]]; rows=[[(digest,unpack(digest,size,data)) for digest,size,data in sqlite3.connect(p).execute('SELECT sha256,original_size,zlib_bytes FROM sources ORDER BY sha256')] for p in paths]; assert rows[0]==rows[1]; assert all(hashlib.sha256(raw).hexdigest()==digest for digest,raw in rows[0]); print(json.dumps({'source_count':len(rows[0]),'source_bytes_equal':True}))",directory,restoredDirectory],{windowsHide:true,encoding:"utf8"});
    expect(inspected.status,inspected.stderr).toBe(0);const sources=JSON.parse(inspected.stdout);expect(sources.source_count).toBe(5);
    await writeFile(path.join(root,".local",evidence,"installed-browser.json"),JSON.stringify({artifact,directory,restoredDirectory,backup:path.join(area,"backup.sqlite3"),external_requests:external,...sources,candidate_loss:4,worksheet_loss:2,snapshot_id:staged.preview.id,source_sha256:snapshot.source_sha256},null,2)+"\n");
  } finally {await source.stop();if(target)await target.stop();}
  // Removing/replacing application assets must not remove independent data.
  const ui=path.join(artifact,"ui");await rename(ui,ui+"-held");
  try {
    const failed=spawnSync("powershell.exe",["-NoProfile","-File",path.join(artifact,"Launch.ps1"),"-Command","start","-Workspace",directory],{cwd:artifact,windowsHide:true,encoding:"utf8",timeout:15000});
    expect(failed.status).not.toBe(0);expect(failed.stderr).toContain("local_launch_refused");
  }finally{await rename(ui+"-held",ui);}
  const reopened=await open({directory});try{expect((await api(reopened,"/api/v1/catalog")).worksheets).toEqual(["installed-worksheet"]);}finally{await reopened.stop();}
});


test("installed minimal CSV opening preserves unknowns, original bytes and recovery",async({page})=>{
  test.setTimeout(60000);
  const area=await mkdtemp(path.join(tmpdir(),"prosper-import-"));
  const directory=path.join(area,"source"),destination=path.join(area,"restored");
  initialize(directory);initialize(destination);
  let source=await runtime({artifact,directory});let target;
  const external=[];
  try {
    await page.route("**/*",route=>{const url=route.request().url();if(!url.startsWith(source.origin+"/")){external.push(url);return route.abort();}return route.continue();});
    await page.goto(source.origin);await advancedImport(page);
    await expect(page.getByRole("status",{name:"Workspace status"})).toContainText("Workspace read");
    await expect(page.getByLabel("History file (up to 64 MiB; staged in bounded parts)",{exact:true})).toBeEnabled();
    const raw=await readFile(path.join(fixture,"lifecycle/initial.csv"));
    await prepareUpload(page,"Declared combined-lot CSV");await page.getByLabel("Declared combined-lot CSV",{exact:true}).setInputFiles({name:"invented.csv",mimeType:"text/csv",buffer:raw});
    await page.getByLabel("Source account identifier",{exact:true}).fill("000SYNTH001");
    await page.getByLabel("Source snapshot date",{exact:true}).fill("2026-10-23");
    await page.getByRole("button",{name:"Review imported holdings",exact:true}).click();
    await expect(page.getByRole("status",{name:"Lot input status"})).toContainText("preview staged");
    await expect(page.getByRole("status",{name:"Workspace purpose"})).toContainText("Exploratory estimates");
    const catalog=await api(source,"/api/v1/catalog");const id=catalog.snapshots[0].id;
    const preview=await api(source,"/api/v1/previews/"+id);expect(preview.snapshot).not.toHaveProperty("fictional");
    await api(source,"/api/v1/select",{snapshot_id:id,command_key:"purpose-select",expected_revision:0});
    const run=await api(source,"/api/v1/diagnostics",{run_id:"purpose-diagnostic",expected_revision:1,as_of:new Date().toISOString()});
    expect(run.outputs).not.toHaveProperty("fictional");expect(run.outputs.financial_metrics).toBe(null);expect(run.outputs.financial_use_authorized).toBe(false);
    await source.interrupt();source=await runtime({artifact,directory});
    expect(await api(source,"/api/v1/runs/"+run.id)).toEqual(run);
    const token=await source.session();const response=await fetch(source.origin+"/api/v1/backup",{headers:{Origin:source.origin,Authorization:`Bearer ${token}`}});expect(response.ok).toBe(true);const bytes=Buffer.from(await response.arrayBuffer());
    target=await runtime({artifact,directory:destination});
    const targetToken=await target.session();
    const restore=()=>fetch(target.origin+"/api/v1/restore",{method:"POST",headers:{Origin:target.origin,Authorization:`Bearer ${targetToken}`,"Content-Type":"application/octet-stream"},body:bytes});
    const restored=await restore();expect(restored.ok).toBe(true);const receipt=await restored.json();expect(await (await restore()).json()).toEqual(receipt);
    expect(await api(target,"/api/v1/runs/"+run.id)).toEqual(run);
    expect(await api(target,"/api/v1/previews/"+id)).toEqual(preview);
    const python=path.join(artifact,".venv/Scripts/python.exe");
    const check=spawnSync(python,["-I","-c","import sys; from pathlib import Path; from prosper.advisory_store import AdvisoryStore; from prosper.source_blob import unpack; import prosper.fidelity_import as module; import sqlite3; p=Path(sys.argv[1]); c=sqlite3.connect(p); row=c.execute('SELECT sha256,original_size,zlib_bytes FROM sources').fetchone(); print(module.__file__); sys.stdout.flush(); sys.stdout.buffer.write(unpack(row[0],row[1],row[2]))",path.join(destination,".local/workspace/advisory-v1.sqlite3")],{windowsHide:true,encoding:null});
    expect(check.status,check.stderr.toString()).toBe(0);expect(check.stdout.toString()).toContain("site-packages");expect(check.stdout.subarray(check.stdout.indexOf(10)+1)).toEqual(raw);
    expect(external).toEqual([]);expect(await page.locator("body").innerText()).not.toContain(directory);
    await mkdir(path.join(root,".local/input-contracts"),{recursive:true});await writeFile(path.join(root,".local/input-contracts/installed.json"),JSON.stringify({artifact,directory,destination,snapshot_id:id,case:"fictitious CSV import",schema_version:11,source_bytes:raw.length,diagnostic:run.id,checks:["UI label","installed parser","interruption reopen","identical restore retry","original bytes","no fit","no external UI requests"]},null,2)+"\n");
  } finally {await source.stop();if(target)await target.stop();}
});
