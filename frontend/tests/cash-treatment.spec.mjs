import { dismissDetails, navigate, reveal, advancedImport, savedRecords, historyTools, workspaceTools, prepareUpload, sourceDetails } from "../tools/workspace.mjs";
test.beforeEach(({page})=>page.setDefaultTimeout(10000));
import {test,expect} from "@playwright/test";
import {readFile,mkdir} from "node:fs/promises";
import path from "node:path";
import {runtime,root} from "../tools/runtime.mjs";

const dist=path.join(root,"frontend/dist");
const csv=await readFile(path.join(root,"examples/synthetic/fidelity/cash-holdings.csv"));
const status=page=>page.getByRole("status",{name:"Workspace status",exact:true});
const money=page=>page.getByRole("article",{name:/^Holding treatment /}).filter({has:page.getByRole("heading",{name:"Fictional Money Market Fund / FMMXX",exact:true})});
async function api(server,route,body){const token=await server.session();const response=await fetch(server.origin+route,{method:body?"POST":"GET",headers:{Origin:server.origin,Authorization:`Bearer ${token}`,...(body?{"Content-Type":"application/json"}:{})},...(body?{body:JSON.stringify(body)}:{})});expect(response.ok).toBe(true);return response.json();}
async function open(page,server){await page.goto(server.origin);await navigate(page,"Holdings");await expect(status(page)).toContainText("Workspace read");}
async function seed(page,server){
  await open(page,server);
  await prepareUpload(page,"Declared combined-lot CSV");await page.getByLabel("Declared combined-lot CSV",{exact:true}).setInputFiles({name:"fictional-cash.csv",mimeType:"text/csv",buffer:csv});
  await page.getByLabel("Source account identifier",{exact:true}).fill("000SYNTH001");await page.getByLabel("Source snapshot date",{exact:true}).fill("2026-10-23");
  await page.getByRole("button",{name:"Review imported holdings",exact:true}).click();await expect(money(page)).toContainText("100.00");
  await expect(money(page).getByRole("button",{name:"Mark as Cash equivalent",exact:true})).toBeDisabled();
  await page.getByLabel("I reviewed this snapshot and its unknowns",{exact:true}).check();await page.getByRole("button",{name:"Select reviewed snapshot",exact:true}).click();await expect(status(page)).toContainText("revision 1");
}

test("ordinary holding cash treatment preserves values, funding, undo and recovered history",async({page})=>{
  const server=await runtime({dist});const target=await runtime({dist});try{
    await seed(page,server);const original=await api(server,"/api/v1/current");
    await api(server,"/api/v1/settings",{settings:{additional_cash:"7.00"},command_key:"funding",expected_revision:1});
    const saved=await api(server,"/api/v1/diagnostics",{run_id:"before",expected_revision:2,as_of:new Date().toISOString()});
    await dismissDetails(page);await page.getByRole("button",{name:"Refresh workspace",exact:true}).click();await expect(status(page)).toContainText("Workspace read");expect((await api(server,"/api/v1/current")).revision).toBe(2);
    const unknown=page.getByRole("article",{name:/^Holding treatment /}).filter({has:page.getByRole("heading",{name:"Fictional Unknown Value Fund / FUNK",exact:true})});await expect(unknown).toContainText("Reported value (USD)");await expect(unknown).toContainText("Unknown");
    await money(page).getByRole("button",{name:"Mark as Cash equivalent",exact:true}).click();await expect(status(page)).toContainText("Cash treatment: changed; revision 3");await expect(money(page)).toContainText("Effective treatment: Cash equivalent");
    const current=await api(server,"/api/v1/current");expect(current.snapshot_id).not.toBe(original.snapshot_id);expect(current.settings).toEqual({additional_cash:"7.00"});expect(current.current_run_id).toBeNull();expect(await api(server,"/api/v1/runs/before")).toEqual(saved);
    const changed=await api(server,`/api/v1/previews/${current.snapshot_id}`);const initial=await api(server,`/api/v1/previews/${original.snapshot_id}`);expect(changed.snapshot.lots).toEqual(initial.snapshot.lots);expect(changed.snapshot.cash).toEqual([]);
    await money(page).getByRole("button",{name:"Mark as Cash",exact:true}).click();await expect(status(page)).toContainText("revision 4");await expect(money(page)).toContainText("Effective treatment: Cash");
    await money(page).getByRole("button",{name:"Undo cash treatment",exact:true}).click();await expect(status(page)).toContainText("revision 5");expect((await api(server,"/api/v1/current")).snapshot_id).toBe(original.snapshot_id);
    await money(page).getByRole("button",{name:"Mark as Cash equivalent",exact:true}).click();await expect(status(page)).toContainText("revision 6");
    const waiting=page.waitForEvent("download");await navigate(page,"Settings");await page.getByRole("button",{name:"Download workspace backup",exact:true}).click();const bytes=await readFile(await (await waiting).path());
    await open(page,target);await prepareUpload(page,"Current workspace backup (up to 64 MiB)");await page.getByLabel("Current workspace backup (up to 64 MiB)",{exact:true}).setInputFiles({name:"workspace.sqlite3",mimeType:"application/octet-stream",buffer:bytes});await page.getByRole("button",{name:"Restore into empty workspace",exact:true}).click();await expect(status(page)).toContainText("restored");
    await navigate(page,"Holdings");await page.getByRole("button",{name:"Review current holdings",exact:true}).click();await expect(money(page)).toContainText("Effective treatment: Cash equivalent");expect((await api(target,"/api/v1/current")).settings).toEqual({additional_cash:"7.00"});expect(await api(target,"/api/v1/runs/before")).toEqual(saved);
    await mkdir(path.join(root,".local/mvp19"),{recursive:true});await page.getByRole("region",{name:"Personal cash treatment",exact:true}).screenshot({path:path.join(root,".local/mvp19/fictional-cash-treatment.png")});
    await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.reload();await navigate(page,"Holdings");await expect(status(page)).toContainText("Workspace read");await navigate(page,"Holdings");await page.getByRole("button",{name:"Review current holdings",exact:true}).click();await expect(money(page)).toContainText("Effective treatment: Cash equivalent");
    const selectedAfterRestore=(await api(target,"/api/v1/current")).snapshot_id;
    await prepareUpload(page,"Declared combined-lot CSV");await page.getByLabel("Declared combined-lot CSV",{exact:true}).setInputFiles({name:"refreshed-fictional.csv",mimeType:"text/csv",buffer:csv});await page.getByLabel("Source account identifier",{exact:true}).fill("000SYNTH001");await page.getByLabel("Source snapshot date",{exact:true}).fill("2026-10-23");await page.getByRole("button",{name:"Review imported holdings",exact:true}).click();await expect(money(page)).toContainText("Original source treatment");await expect(money(page).getByRole("button",{name:"Mark as Cash equivalent",exact:true})).toBeDisabled();expect((await api(target,"/api/v1/current")).snapshot_id).toBe(selectedAfterRestore);
  }finally{await server.stop();await target.stop();}
});

test("lost mutation response retries the identical command and stale source cannot be changed",async({page})=>{
  const server=await runtime({dist});try{
    await seed(page,server);let first=true;const bodies=[];
    await page.route("**/api/v1/holdings/cash-treatment",async route=>{bodies.push(route.request().postDataJSON());if(first){first=false;const response=await route.fetch();expect(response.ok()).toBe(true);await route.abort();}else await route.continue();});
    await money(page).getByRole("button",{name:"Mark as Cash equivalent",exact:true}).click();await expect(page.getByRole("region",{name:"Pending action",exact:true})).toBeVisible();await expect(money(page).getByRole("button",{name:"Mark as Cash",exact:true})).toBeDisabled();
    await page.getByRole("button",{name:"Retry identical action",exact:true}).click();await expect(status(page)).toContainText("revision 2");await expect(money(page)).toContainText("Effective treatment: Cash equivalent");expect(bodies).toHaveLength(2);expect(bodies[1]).toEqual(bodies[0]);
    const state=await api(server,"/api/v1/current");await api(server,"/api/v1/settings",{settings:{additional_cash:"9.00"},command_key:"other-window",expected_revision:state.revision});
    await money(page).getByRole("button",{name:"Mark as Cash",exact:true}).click();await expect(status(page)).toContainText("stale_revision");expect((await api(server,"/api/v1/current")).revision).toBe(3);await expect(money(page)).toContainText("Effective treatment: Cash equivalent");
  }finally{await server.stop();}
});
