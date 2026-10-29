import { expect } from "@playwright/test";

// Exercise the same explicit navigation and disclosure controls as an investor.
export async function dismissDetails(page) {for(const dialog of await page.getByRole("dialog").all())if(await dialog.isVisible())await dialog.getByRole("button",{name:/^Close /}).click();}
export async function navigate(page, destination, stage) {
  for(const dialog of await page.getByRole("dialog").all())if(await dialog.isVisible())await dialog.getByRole("button",{name:/^Close /}).click();
  await page.getByRole("navigation",{name:"Main navigation",exact:true}).getByRole("button",{name:destination,exact:true}).count().then(async count=>{
    if(count)await page.getByRole("navigation",{name:"Main navigation",exact:true}).getByRole("button",{name:destination,exact:true}).click();
    else await page.getByRole("button",{name:destination,exact:true}).click();
  });
  if(stage)await page.getByRole("navigation",{name:"Analysis stages",exact:true}).getByRole("button",{name:new RegExp(stage+"$")}).click();
  if(stage==="Benchmark"){const summary=page.locator("summary").filter({hasText:/^(Change benchmark or inspect retained sources|Choose benchmark and reporting date)$/});await expect(summary).toBeVisible();if(await summary.evaluate(el=>!el.parentElement.open))await summary.click();}
  await expect(page.getByRole("heading",{name:destination,exact:true,level:1})).toBeVisible();
}
export async function reveal(page, text) {
  let summary=page.locator("summary").filter({hasText:text}).filter({visible:true});
  if(!await summary.count()&&await page.getByRole("button",{name:"Edit inputs",exact:true}).isVisible())await page.getByRole("button",{name:"Edit inputs",exact:true}).click();
  await expect(summary).toBeVisible();if(await summary.evaluate(el=>!el.parentElement.open))await summary.click();
}
export async function sourceDetails(page, label) {await page.getByRole("button",{name:label,exact:true}).click();}
export async function advancedImport(page) {await navigate(page,"Holdings");await reveal(page,"Advanced import and retained snapshots");}
export async function savedRecords(page) {await navigate(page,"Worksheets");await reveal(page,"Saved analysis details");await reveal(page,"Advanced saved-record tools");}
export async function historyTools(page) {await navigate(page,"Settings");await reveal(page,"Market history and source tools");}
export async function workspaceTools(page) {await navigate(page,"Settings");await page.getByRole("button",{name:"Advanced workspace tools",exact:true}).click();}
export async function prepareUpload(page,label) {
  if(label.startsWith("Normalized snapshot"))return advancedImport(page);
  if(label==="Explicit lot settings JSON"){await navigate(page,"Holdings");return reveal(page,"Advanced settings file import");}
  if(label==="Declared combined-lot CSV"||label==="Reviewed lot context JSON"){await navigate(page,"Holdings");await reveal(page,/^(Import refreshed holdings|Import holdings file)$/);if(label==="Reviewed lot context JSON")await reveal(page,"Advanced reviewed context (optional)");return;}
  if(label==="Modeled input/profile JSON"){await navigate(page,"Analysis","Review inputs");return reveal(page,"Advanced supplied input configuration");}
  if(label==="Candidate controls JSON"){await navigate(page,"Analysis","Proposals");return reveal(page,"Advanced proposal controls file");}
  if(label.startsWith("Current workspace backup")){await navigate(page,"Settings");return reveal(page,"Restore a backup into an empty workspace");}
  if(label.startsWith("History file")||label==="Required history window JSON")return historyTools(page);
  if(label==="Saved benchmark response JSON"||label==="Reviewed benchmark mapping and metadata JSON"){await navigate(page,"Analysis","Benchmark");return reveal(page,label==="Saved benchmark response JSON"?"Import saved benchmark response":"Import a prepared benchmark review");}
}
