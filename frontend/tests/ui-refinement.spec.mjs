import { test,expect } from "@playwright/test";
import { spawnSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { runtime,root,python } from "../tools/runtime.mjs";
import { navigate,reveal } from "../tools/workspace.mjs";
const dist=path.join(root,"frontend/dist"),folder=path.join(root,"examples/synthetic/candidates/application");
const load=async name=>JSON.parse(await readFile(path.join(folder,name)));
async function api(server,route,body){const token=await server.session(),response=await fetch(server.origin+"/api/v1"+route,{method:body?"POST":"GET",headers:{Origin:server.origin,Authorization:`Bearer ${token}`,...(body?{"Content-Type":"application/json"}:{})},body:body?JSON.stringify(body):undefined});expect(response.ok,await response.clone().text()).toBe(true);return response.json();}
function seed(server){const result=spawnSync(python,["-c","import sys;from pathlib import Path;from tests.test_candidate_workflow import seed,service;seed(service(Path(sys.argv[1])),standard=True)",server.directory],{cwd:root,encoding:"utf8",windowsHide:true});expect(result.status,result.stderr).toBe(0);}
const ready=page=>expect(page.getByRole("button",{name:"Refresh workspace",exact:true})).toBeEnabled();
test.beforeEach(({page})=>page.setDefaultTimeout(10000));

test("saved documents separate analysis and knowledge dates and reopen original context without writes",async({page})=>{
 const server=await runtime({dist});try{
  seed(server);const original=await api(server,"/current"),saved=await api(server,"/runs/inputs");
  const upload=await load("holdings.json");upload.snapshot.account_alias="Different current account";
  const preview=await api(server,"/previews",upload);await api(server,"/select",{snapshot_id:preview.id,command_key:"different-current",expected_revision:original.revision});
  const before=await api(server,"/current"),writes=[];page.on("request",request=>{if(request.method()==="POST"&&!request.url().endsWith("/session"))writes.push(request.url());});
  await page.goto(server.origin);await ready(page);await navigate(page,"Worksheets");
  const item=page.getByRole("button",{name:/^Input review Analysis 2026-10-23/});await expect(item).toBeVisible();await expect(item).not.toContainText("2026-10-25");await item.click();
  await expect(page).toHaveURL(/#worksheets\/run\/inputs$/);const context=page.getByRole("region",{name:"Original saved context",exact:true});
  await expect(context).toContainText("Analysis date2026-10-23");await expect(context).toContainText("Fictional tiny taxable account");await expect(context).not.toContainText("Different current account");
  await expect(page.locator(".account-context")).toContainText("Different current account");await expect(page.getByRole("region",{name:"Saved work library",exact:true})).toBeHidden();await expect(page.getByRole("region",{name:"Comparison and manual worksheet",exact:true})).toBeHidden();
  await page.reload();await ready(page);await expect(context).toContainText("2026-10-23");await page.getByRole("button",{name:"Original references and knowledge time",exact:true}).click();await expect(page.getByRole("dialog")).toContainText(saved.as_of);await page.keyboard.press("Escape");
  await navigate(page,"Holdings");await expect(page.locator("body")).not.toContainText("Saved analysis opened");await page.goBack();await expect(context).toContainText("Fictional tiny taxable account");
  await page.getByRole("button",{name:"Back to saved work",exact:true}).click();await expect(item).toBeVisible();
  await page.getByRole("button",{name:/^Benchmark review Source 2026-10-23/}).click();await expect(context).toContainText("Analysis dateUnavailable in saved record");await expect(context).not.toContainText("Analysis date2026-10-25");
  await page.goto(server.origin+"/#worksheets/run/not-retained");await expect(page.getByRole("alert")).toContainText("could not be read");await expect(context).toHaveCount(0);
  expect(await api(server,"/current")).toEqual(before);expect(writes).toEqual([]);
 }finally{await server.stop();}
});

test("workspace loading, unavailable reads, running and cancelled results have distinct guidance",async({page})=>{
 const server=await runtime({dist});let release;const gate=new Promise(resolve=>release=resolve);try{
  seed(server);const state=await api(server,"/current"),input=await api(server,"/runs/inputs");
  await page.route("**/api/v1/current",async route=>{await gate;await route.continue();});await page.goto(server.origin);
  await expect(page.getByRole("button",{name:"Reading workspace",exact:true})).toBeDisabled();await expect(page.locator(".portfolio-context")).not.toContainText("No holdings selected");release();await ready(page);await page.unroute("**/api/v1/current");
  let outcome="running";await page.route("**/api/v1/current",route=>route.fulfill({json:{...state,current_run_id:"progress"}}));
  await page.route("**/api/v1/runs/progress",route=>route.fulfill({json:{...input,id:"progress",model_version:"candidate-workflow-v1",status:outcome==="running"?"running":"partial",inputs:{candidate_command:{input_run_id:"inputs"}},outputs:outcome==="running"?{phase:"fitting"}:{outcome:"cancelled",issues:[],search:null}}}));
  await page.getByRole("button",{name:"Refresh workspace",exact:true}).click();await expect(page.getByRole("button",{name:"View calculation",exact:true})).toBeVisible();await expect(page.locator(".welcome-panel")).not.toContainText("Comparison available");
  outcome="cancelled";await page.getByRole("button",{name:"Refresh workspace",exact:true}).click();await expect(page.getByRole("button",{name:"Review calculation",exact:true})).toBeVisible();
  await page.unroute("**/api/v1/runs/progress");await page.route("**/api/v1/runs/progress",route=>route.abort());await page.getByRole("button",{name:"Refresh workspace",exact:true}).click();await expect(page.getByRole("button",{name:"Refresh analysis state",exact:true})).toBeVisible();
 }finally{release?.();await server.stop();}
});

test("large sale lists retain explicit bounds across pages and find an unresolved lot",async({page})=>{
 const server=await runtime({dist});try{
  seed(server);const original=await api(server,"/current");
  const value=await api(server,`/previews/${original.snapshot_id}`),lot=value.snapshot.lots[0];value.snapshot.lots=Array.from({length:45},(_,i)=>({...lot,id:`lot-${i+1}`}));
  await page.route(`**/api/v1/previews/${original.snapshot_id}`,route=>route.fulfill({json:value}));
  await page.goto(server.origin);await ready(page);await navigate(page,"Analysis","Proposals");await page.getByRole("button",{name:"Set up a proposal",exact:true}).click();
  await expect(page.getByLabel(/^Maximum sale shares/)).toHaveCount(20);await page.getByLabel("Maximum sale shares lot-1",{exact:true}).fill("1");await page.getByRole("button",{name:"Next sale lots",exact:true}).click();await page.getByLabel("Maximum sale shares lot-21",{exact:true}).fill("0");await page.getByRole("button",{name:"Next sale lots",exact:true}).click();await expect(page.getByLabel(/^Maximum sale shares/)).toHaveCount(5);
  await page.getByRole("button",{name:"Go to first unresolved lot",exact:true}).click();await expect(page.getByLabel("Maximum sale shares lot-2",{exact:true})).toBeFocused();await expect(page.getByLabel("Maximum sale shares lot-1",{exact:true})).toHaveValue("1");
  await page.getByRole("button",{name:"Next sale lots",exact:true}).click();await expect(page.getByLabel("Maximum sale shares lot-21",{exact:true})).toHaveValue("0");expect(await api(server,"/current")).toEqual(original);
 }finally{await server.stop();}
});

test("a late document read cannot replace another destination or selected record",async({page})=>{
 const server=await runtime({dist});let release;const gate=new Promise(resolve=>release=resolve);try{
  seed(server);const input=await api(server,"/runs/inputs");await page.goto(server.origin);await ready(page);await expect(page.getByRole("button",{name:/^Input review Analysis/})).toBeVisible();
  await page.route("**/api/v1/runs/inputs",async route=>{await gate;await route.fulfill({json:input});});await page.getByRole("button",{name:/^Input review Analysis/}).click();await expect(page.getByText("Reading original saved document...",{exact:true})).toBeVisible();
  await navigate(page,"Holdings");release();await navigate(page,"Worksheets");await page.getByRole("button",{name:/^Benchmark review Source/}).click();await expect(page.getByRole("region",{name:"Original saved context",exact:true}).getByRole("heading",{name:"Benchmark review",exact:true})).toBeVisible();
 }finally{release?.();await server.stop();}
});

test("responsive evidence remains reachable by keyboard with unknown warnings visible",async({page})=>{
 const server=await runtime({dist});try{
  seed(server);const input=await api(server,"/runs/inputs");input.warnings.push("Unbounded exposure persists; a source fact needs review");await page.route("**/api/v1/runs/inputs",route=>route.fulfill({json:input}));
  await page.goto(server.origin);await ready(page);await page.emulateMedia({reducedMotion:"reduce"});
  for(const width of [1440,1280,768,390,320]) {await page.setViewportSize({width,height:900});await navigate(page,"Holdings");expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);}
  await page.setViewportSize({width:720,height:500});await navigate(page,"Overview");await page.getByRole("button",{name:/^Input review Analysis/}).click();await expect(page.getByText("Unbounded exposure persists; a source fact needs review",{exact:true}).filter({visible:true})).toBeVisible();
  const trigger=page.getByRole("button",{name:/^Full original warnings/});await trigger.focus();await page.keyboard.press("Enter");await expect(page.getByRole("dialog",{name:"Original assumptions and warnings",exact:true})).toContainText("Unbounded exposure persists");await page.keyboard.press("Escape");await expect(trigger).toBeFocused();
  await navigate(page,"Settings");await page.getByRole("combobox",{name:"Appearance",exact:true}).selectOption("dark");await navigate(page,"Overview");expect(await page.locator("html").getAttribute("data-appearance")).toBe("dark");expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 }finally{await server.stop();}
});
