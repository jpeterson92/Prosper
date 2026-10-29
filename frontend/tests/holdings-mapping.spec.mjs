import { dismissDetails, navigate, reveal, advancedImport, savedRecords, historyTools, workspaceTools, prepareUpload, sourceDetails } from "../tools/workspace.mjs";
test.beforeEach(({page})=>page.setDefaultTimeout(10000));
import {test,expect} from "@playwright/test";
import {readFile,mkdir} from "node:fs/promises";
import path from "node:path";
import {runtime,root} from "../tools/runtime.mjs";

const dist=path.join(root,"frontend/dist");
const raw=await readFile(path.join(root,"examples/synthetic/fidelity/benchmark-holdings.csv"));
const observed=JSON.parse(await readFile(path.join(root,"examples/synthetic/blackrock/current-observation.json"),"utf8"));
const metadata=await readFile(path.join(root,"examples/synthetic/blackrock/metadata.html"));
const status=page=>page.getByRole("status",{name:"Workspace status",exact:true});
const panel=page=>page.getByRole("region",{name:"Holdings stock mapping",exact:true});
async function api(server,route,body){const token=await server.session();const response=await fetch(server.origin+route,{method:body?"POST":"GET",headers:{Origin:server.origin,Authorization:`Bearer ${token}`,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});expect(response.ok).toBe(true);return response.json();}
async function open(page,server){await page.goto(server.origin);await navigate(page,"Holdings");await expect(status(page)).toContainText("Workspace read");}
async function seed(page,server){
  await open(page,server);await prepareUpload(page,"Declared combined-lot CSV");await page.getByLabel("Declared combined-lot CSV",{exact:true}).setInputFiles({name:"fictional-holdings.csv",mimeType:"text/csv",buffer:raw});await page.getByLabel("Source account identifier",{exact:true}).fill("000SYNTH001");await page.getByLabel("Source snapshot date",{exact:true}).fill("2026-10-20");await page.getByRole("button",{name:"Review imported holdings",exact:true}).click();await expect(panel(page)).toContainText("Select this reviewed source snapshot");
  await page.getByLabel("I reviewed this snapshot and its unknowns",{exact:true}).check();await page.getByRole("button",{name:"Select reviewed snapshot",exact:true}).click();await expect(status(page)).toContainText("revision 1");
  await api(server,"/api/v1/benchmarks/import",observed);
  const review=await api(server,"/api/v1/benchmarks/prepare",{observation_id:observed.request.observation_id,metadata_response:{collected_at:"2026-10-22T12:00:00Z",response_url:"https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf",content_type:"text/html",http_status:200,body_complete:true,source_base64:metadata.toString("base64")}});
  await api(server,"/api/v1/benchmarks/diagnostics",{run_id:"benchmark",expected_revision:1,as_of:new Date().toISOString(),review});await api(server,"/api/v1/benchmarks/select",{run_id:"benchmark",expected_revision:1,command_key:"benchmark"});
  await dismissDetails(page);await page.getByRole("button",{name:"Refresh workspace",exact:true}).click();await expect(status(page)).toContainText("Workspace read");expect((await api(server,"/api/v1/current")).revision).toBe(2);
  const money=page.getByRole("article",{name:/^Holding treatment /}).filter({has:page.getByRole("heading",{name:"Fictional Money Market Fund / FMMXX",exact:true})});await money.getByRole("button",{name:"Mark as Cash equivalent",exact:true}).click();await expect(status(page)).toContainText("revision 3");
}

test("benchmark-backed mappings stage without manual identity fields and retain source/cash/recovery",async({page})=>{
  const server=await runtime({dist});const target=await runtime({dist});try{
    await seed(page,server);const before=await api(server,"/api/v1/current");const original=await api(server,`/api/v1/previews/${before.snapshot_id}`);
    const saved=await api(server,"/api/v1/diagnostics",{run_id:"source-before",expected_revision:3,as_of:new Date().toISOString()});const selected=await api(server,"/api/v1/current");
    await panel(page).getByRole("button",{name:"Prepare stock mappings",exact:true}).click();await expect(status(page)).toContainText("Holdings mapping preview staged");await expect(panel(page)).toContainText("2 mapped; 0 supplied identities preserved; 1 excluded; 1 cash-treated");await expect(panel(page)).toContainText("FIAA");await expect(panel(page)).toContainText("123.4568 bps");await expect(panel(page)).toContainText("Aggregate exclusions exceed 100 bps");expect(await api(server,"/api/v1/current")).toEqual(selected);
    await page.getByLabel("I reviewed this snapshot and its unknowns",{exact:true}).check();await page.getByRole("button",{name:"Select reviewed snapshot",exact:true}).click();await expect(status(page)).toContainText("revision 4");
    const after=await api(server,"/api/v1/current");const prepared=await api(server,`/api/v1/previews/${after.snapshot_id}`);expect(prepared.snapshot.cash_treatments).toEqual(original.snapshot.cash_treatments);expect(prepared.snapshot.lots.map(({security_id,...row})=>row)).toEqual(original.snapshot.lots.map(({security_id,...row})=>row));expect(prepared.snapshot.securities.slice(0,2).map(s=>s.classification.value)).toEqual([null,null]);expect(await api(server,"/api/v1/runs/source-before")).toEqual(saved);
    const waiting=page.waitForEvent("download");await navigate(page,"Settings");await page.getByRole("button",{name:"Download workspace backup",exact:true}).click();const backup=await readFile(await (await waiting).path());await open(page,target);await prepareUpload(page,"Current workspace backup (up to 64 MiB)");await page.getByLabel("Current workspace backup (up to 64 MiB)",{exact:true}).setInputFiles({name:"workspace.sqlite3",mimeType:"application/octet-stream",buffer:backup});await page.getByRole("button",{name:"Restore into empty workspace",exact:true}).click();await expect(status(page)).toContainText("restored");await navigate(page,"Holdings");await page.getByRole("button",{name:"Review current holdings",exact:true}).click();await expect(panel(page)).toContainText("2 mapped;");expect(await api(target,`/api/v1/previews/${after.snapshot_id}`)).toEqual(prepared);expect(await api(target,"/api/v1/runs/source-before")).toEqual(saved);
    await mkdir(path.join(root,".local/mvp110"),{recursive:true});await panel(page).screenshot({path:path.join(root,".local/mvp110/fictional-holdings-mapping.png")});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.reload();await navigate(page,"Holdings");await expect(status(page)).toContainText("Workspace read");await navigate(page,"Holdings");await page.getByRole("button",{name:"Review current holdings",exact:true}).click();await expect(panel(page)).toContainText("2 mapped;");
  }finally{await server.stop();await target.stop();}
});

test("explicit exclusions and identical preview retry cannot overwrite a newer cash treatment",async({page})=>{
  const server=await runtime({dist});try{
    await seed(page,server);const original=await api(server,"/api/v1/current");
    await panel(page).getByText("Advanced mapping exclusions",{exact:true}).click();await panel(page).getByLabel("Exclusion reason for FIBB",{exact:true}).fill("Investor excluded this stock");
    const bodies=[];let first=true;await page.route("**/api/v1/holdings/mapping-preview",async route=>{bodies.push(route.request().postDataJSON());if(first){first=false;expect((await route.fetch()).ok()).toBe(true);await route.abort();}else await route.continue();});
    await panel(page).getByRole("button",{name:"Prepare stock mappings",exact:true}).click();await expect(panel(page).getByRole("alert")).toBeVisible();await panel(page).getByRole("button",{name:"Retry identical mapping preparation",exact:true}).click();await expect(panel(page)).toContainText("1 mapped;");await expect(panel(page)).toContainText("Investor excluded this stock");expect(bodies).toHaveLength(2);expect(bodies[0]).toEqual(bodies[1]);
    const source=await api(server,`/api/v1/previews/${original.snapshot_id}`);const cash=source.snapshot.cash_treatments[0].security_id;await api(server,"/api/v1/holdings/cash-treatment",{snapshot_id:original.snapshot_id,security_id:cash,kind:"cash",expected_revision:3,command_key:"other-window"});const newer=await api(server,"/api/v1/current");
    await dismissDetails(page);await page.getByRole("button",{name:"Refresh workspace",exact:true}).click();await expect(status(page)).toContainText("Workspace read");expect((await api(server,"/api/v1/current")).revision).toBe(4);await page.getByLabel("I reviewed this snapshot and its unknowns",{exact:true}).check();await page.getByRole("button",{name:"Select reviewed snapshot",exact:true}).click();await expect(status(page)).toContainText("prepared_snapshot_stale");expect(await api(server,"/api/v1/current")).toEqual(newer);await expect(page.getByRole("button",{name:"Refresh workspace",exact:true})).toBeEnabled();
  }finally{await server.stop();}
});
