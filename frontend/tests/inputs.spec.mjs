import { test, expect } from "@playwright/test";
import { readFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { runtime, root, refreshHistory } from "../tools/runtime.mjs";
const dist=path.join(root,"frontend/dist");
const load=async file=>JSON.parse(await readFile(path.join(root,"examples/synthetic",file)));
const inputs=await load("modeled-inputs/current.json");
const status=page=>page.getByRole("status",{name:"Workspace status"});
async function api(server,route,body) {const token=await server.session();const response=await fetch(server.origin+route,{method:body?"POST":"GET",headers:{Origin:server.origin,Authorization:`Bearer ${token}`, ...(body?{"Content-Type":"application/json"}:{})},body:body?JSON.stringify(body):undefined});expect(response.ok).toBe(true);return response.json();}
async function seed(server) {
  const staged=await api(server,"/api/v1/previews",await load("advisory-workspace.json"));
  await api(server,"/api/v1/select",{snapshot_id:staged.id,command_key:"holdings",expected_revision:0});
  await api(server,"/api/v1/benchmarks/import",await load("benchmark/current-observation.json"));
  await api(server,"/api/v1/benchmarks/diagnostics",{run_id:"benchmark",expected_revision:1,as_of:"2026-10-25T22:00:00Z",review:await load("benchmark/current-review.json")});
  await api(server,"/api/v1/benchmarks/select",{run_id:"benchmark",command_key:"benchmark",expected_revision:1});
  await api(server,"/api/v1/lots/settings",{settings:await load("modeled-inputs/lot-settings.json"),command_key:"lot-settings",expected_revision:2});
  await refreshHistory(server,await load("modeled-inputs/history.json"));
}
async function open(page,server) {await page.goto(server.origin);await expect(status(page)).toContainText("Workspace read");}
async function review(page,data=inputs) {await page.getByLabel("Modeled input/profile JSON",{exact:true}).setInputFiles({name:"fictional.json",mimeType:"application/json",buffer:Buffer.from(JSON.stringify(data))});await expect(page.getByRole("article",{name:"Modeled input coverage",exact:true})).toBeVisible();}
async function save(page) {await page.getByLabel("I reviewed the complete union, source coverage, profile and investor settings").check();await page.getByRole("button",{name:"Save modeled input diagnostics",exact:true}).click();}

test("complete union, explicit profile and recovered historical input grid remain visible",async({page})=>{
  const source=await runtime({dist});const target=await runtime({dist});try{
    await seed(source);await open(page,source);await review(page);
    const coverage=page.getByRole("article",{name:"Modeled input coverage",exact:true});await expect(coverage).toContainText("Complete input coverage");await expect(coverage).toContainText("5 retained securities; 3 required sessions");
    await save(page);await expect(status(page)).toContainText("modeled input diagnostics saved");
    await page.getByRole("button",{name:"Reuse saved input configuration",exact:true}).click();await expect(coverage).toContainText("Complete input coverage");await expect(page.getByLabel("I reviewed the complete union, source coverage, profile and investor settings")).not.toBeChecked();
    const state=await api(source,"/api/v1/current");const saved=await api(source,`/api/v1/runs/${state.current_run_id}`);expect(saved.outputs.security_ids).toEqual(["FICTIONAL-0","FICTIONAL-1","security-a","security-b","security-c"]);expect(saved.outputs.risk_available).toBe(false);expect(saved.outputs.members[2].held_quantity).toBe(12.5);
    await page.getByLabel("Remove reusable history cache; keep all saved-run inputs and outputs").check();await page.getByRole("button",{name:"Clear reusable history cache"}).click();await expect(status(page)).toContainText("revision 5");
    await page.getByRole("button",{name:"Recheck current modeled inputs"}).click();await expect(coverage).toContainText("required_history_incomplete");expect(await api(source,`/api/v1/runs/${saved.id}`)).toEqual(saved);
    const event=page.waitForEvent("download");await page.getByRole("button",{name:"Download workspace backup"}).click();const downloaded=await event;const bytes=await readFile(await downloaded.path());
    await open(page,target);await page.getByLabel("Current workspace backup (up to 64 MiB)").setInputFiles({name:"current.sqlite3",mimeType:"application/octet-stream",buffer:bytes});await page.getByRole("button",{name:"Restore into empty workspace"}).click();await expect(status(page)).toContainText("restored");
    await page.getByRole("combobox",{name:"Saved diagnostic",exact:true}).selectOption(saved.id);const restored=page.getByRole("article",{name:"Saved modeled inputs",exact:true});await expect(restored).toContainText("Complete input coverage");expect(await api(target,`/api/v1/runs/${saved.id}`)).toEqual(saved);
    await mkdir(path.join(root,".local/t006.1.6"),{recursive:true});await restored.screenshot({path:path.join(root,".local/t006.1.6/inputs-desktop.png")});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await restored.screenshot({path:path.join(root,".local/t006.1.6/inputs-narrow.png")});
  }finally{await source.stop();await target.stop();}
});

test("lost input result response retries identical frozen request",async({page})=>{
  const server=await runtime({dist});try{await seed(server);await open(page,server);await review(page);const bodies=[];let first=true;
    await page.route("**/api/v1/inputs/diagnostics",async route=>{bodies.push(route.request().postData());if(first){first=false;await route.fetch();await route.abort();}else await route.continue();});
    await save(page);await expect(page.getByRole("button",{name:"Retry identical action"})).toBeVisible();await page.getByRole("button",{name:"Retry identical action"}).click();await expect(status(page)).toContainText("modeled input diagnostics saved");expect(bodies).toHaveLength(2);expect(bodies[0]).toBe(bodies[1]);
  }finally{await server.stop();}
});

test("missing inputs stay located and malformed files do not echo private values",async({page})=>{
  const server=await runtime({dist});try{await seed(server);await open(page,server);const changed=structuredClone(inputs);changed.bundle.classifications[0].industry={value:null,reason:"Unknown fictional industry"};changed.bundle.marks.pop();await review(page,changed);const coverage=page.getByRole("article",{name:"Modeled input coverage",exact:true});await expect(coverage).toContainText("classification_unknown");await expect(coverage).toContainText("mark_missing");await expect(coverage).toContainText("5 retained securities");await save(page);await expect(status(page)).toContainText("modeled input diagnostics saved");
    await page.getByLabel("Modeled input/profile JSON",{exact:true}).setInputFiles({name:"bad.json",mimeType:"application/json",buffer:Buffer.from('{"PRIVATE-KEY":"DO-NOT-ECHO"}')});await expect(page.getByRole("alert")).toContainText("invalid");await expect(page.locator("body")).not.toContainText("DO-NOT-ECHO");
  }finally{await server.stop();}
});

test("refreshed workspace cannot silently save an older reviewed input revision",async({page})=>{
  const server=await runtime({dist});try{await seed(server);await open(page,server);await review(page);await api(server,"/api/v1/history/clear",{command_key:"other-window",expected_revision:4});await page.getByRole("button",{name:"Refresh workspace",exact:true}).click();await expect(status(page)).toContainText("Workspace read");await save(page);await expect(status(page)).toContainText("Action refused");expect((await api(server,"/api/v1/current")).revision).toBe(5);
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
