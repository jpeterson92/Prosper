import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import path from "node:path";
import { runtime, root, python } from "../tools/runtime.mjs";

const raw = await readFile(path.join(root, "examples/synthetic/F001.json"));
const dist = path.join(root, "frontend/dist");
const evidence = path.join(root, ".local/lifecycle-evidence");
const status = (page) => page.getByRole("status", { name: "Review status" });
const receipt = (page) => page.getByRole("status", { name: "Command receipt" });
const review = (page) => page.getByRole("article", { name: "Selected preview review" });
const acknowledge = (page) => page.getByLabel("I reviewed this preview, its readiness reasons and the current checkpoint.");
function inspect(directory) {
  return JSON.parse(execFileSync(python, ["-I", path.join(root, "scripts/browser_fixture.py"), "inspect", directory], { windowsHide: true }));
}
function variant(change) {
  const doc = JSON.parse(raw); change(doc);
  // A new fictional checkpoint keeps every snapshot record bound to its new identity.
  for (const group of ["positions", "lots", "cash", "quotes"]) for (const row of doc[group]) {
    if ("checkpoint_id" in row) row.checkpoint_id = doc.metadata.bundle_id;
  }
  return Buffer.from(JSON.stringify(doc));
}
async function open(page, server) { await page.goto(server.origin); await expect(status(page)).toContainText("Current checkpoint read."); }
async function stage(page, bytes = raw) {
  await page.getByLabel("Synthetic JSON file (up to 2 MiB)").setInputFiles({ name: "fictional.json", mimeType: "application/json", buffer: bytes });
  await page.getByRole("button", { name: "Stage preview", exact: true }).click();
  await expect(status(page)).toContainText("Preview retained for inspection.");
}
async function retrieve(page, bytes) {
  const details = page.locator("details.retrieval");
  if (!(await details.getAttribute("open")) && !(await details.evaluate((node) => node.open))) await details.locator("summary").click();
  await page.getByLabel("Original-byte SHA-256", { exact: true }).fill(createHash("sha256").update(bytes).digest("hex"));
  await page.getByRole("button", { name: "Retrieve preview", exact: true }).click();
  await expect(status(page)).toContainText("Retained preview retrieved.");
}
async function commit(page, outcome = "committed") {
  await acknowledge(page).check();
  await expect(page.getByRole("button", { name: "Commit reviewed preview", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Commit reviewed preview", exact: true }).click();
  await expect(receipt(page).getByRole("heading")).toHaveText(`Recorded outcome: ${outcome}`);
  await expect(status(page)).toContainText("Present state read separately.");
}
async function shot(page, name) { await mkdir(evidence, { recursive: true }); await page.screenshot({ path: path.join(evidence, name + ".png"), fullPage: true }); }

test("reviewed commit, exact retries and historical duplicates preserve current state and privacy", async ({ page, context, browser }) => {
  const server = await runtime({ dist }); const unexpected = [], logs = [], tokens = [], posts = [];
  page.on("console", (event) => logs.push(event.text())); page.on("pageerror", (error) => logs.push(error.message));
  page.on("response", async (response) => { if (response.ok() && response.url().endsWith("/session")) tokens.push((await response.json()).token); });
  page.on("request", (request) => { if (request.url().endsWith("/api/v1/commit")) posts.push(request.postDataJSON()); });
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== server.origin || url.search || url.username || url.password) { unexpected.push(true); await route.abort(); }
    else await route.continue();
  });
  try {
    await open(page, server); await stage(page);
    await expect(page.getByRole("button", { name: "Commit reviewed preview", exact: true })).toBeDisabled();
    await page.getByLabel("Round displayed numeric values to 2 decimals").check();
    await commit(page);
    expect(posts[0].expected_generation).toBe(0);
    await expect(receipt(page)).toContainText("Original activation generation: 1");
    await expect(review(page).locator(".badge").first()).toHaveText("committed");
    await expect(page.getByRole("button", { name: "Reject reviewed preview", exact: true })).toBeDisabled();
    const first = inspect(server.directory);
    expect(first.current.generation).toBe(1);
    expect(first.current.checkpoint.inspection.settled_cash_nav.value).toBe("2399");
    expect(first.current.checkpoint.inspection.total_basis.value).toBe("2181");
    expect(first.current.checkpoint.source.document.cash[0].settled.value).toBe("319");
    await page.getByRole("button", { name: "Retry same commit command", exact: true }).click();
    await expect(status(page)).toContainText("Present state read separately.");
    expect(posts[1]).toEqual(posts[0]); expect(inspect(server.directory)).toEqual(first);
    await commit(page, "duplicate");
    expect(posts[2].command_key).not.toBe(posts[0].command_key);
    expect(inspect(server.directory).counts.import_activations).toBe(1);
    const later = variant((doc) => { doc.metadata.bundle_id = "F001-LATER"; doc.quotes[0].price.value = "90.005"; doc.positions[0].quantity.value = "12.125"; doc.lots[0].quantity.value = "10.125"; });
    await stage(page, later); await commit(page);
    const second = inspect(server.directory);
    expect(second.current.generation).toBe(2);
    const exact = second.current.checkpoint.source.source_values.find((value) => value.path.join(".") === "quotes.0.price.value");
    expect(exact.exact).toEqual({ state: "known", value: "90.005", original_text: "90.005", source_quantum: "0.001" });
    await retrieve(page, raw); await commit(page, "duplicate");
    await expect(receipt(page)).toContainText("Observed generation at command: 2. Original activation generation: 1");
    await expect(receipt(page)).toContainText("an older checkpoint was not restored");
    expect(inspect(server.directory).current).toEqual(second.current);
    await shot(page, "duplicate-desktop");
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await shot(page, "duplicate-narrow");
    expect(unexpected).toEqual([]); expect(logs).toEqual([]);
    expect(tokens.length > 0 && tokens.every((token) => !logs.join("").includes(token))).toBe(true);
    expect(await page.evaluate(() => [localStorage.length, sessionStorage.length, document.cookie])).toEqual([0, 0, ""]);
    await expect(page.getByRole("button", { name: /approve.*trade|override/i })).toHaveCount(0);
    await writeFile(path.join(evidence, "qualification.json"), JSON.stringify({ browser: browser.version(), requests: posts.length, unexpected, counts: inspect(server.directory).counts }, null, 2) + "\n");
  } finally { await server.stop(); }
});

test("two windows receive stale receipts, require new review and recover original outcomes after reload and restart", async ({ page, context }) => {
  let server = await runtime({ dist }); const second = await context.newPage();
  try {
    await open(page, server); await open(second, server);
    await stage(page); await stage(second, variant((doc) => { doc.metadata.bundle_id = "SECOND"; }));
    await acknowledge(second).check(); await commit(page);
    await second.getByRole("button", { name: "Commit reviewed preview", exact: true }).click();
    await expect(receipt(second)).toContainText("Recorded outcome: stale_generation");
    await expect(status(second)).toContainText("Present state read separately.");
    await expect(acknowledge(second)).not.toBeChecked();
    await expect(second.getByRole("button", { name: "Commit reviewed preview", exact: true })).toBeDisabled();
    await shot(second, "stale-desktop");
    await second.getByRole("button", { name: "Refresh current state" }).click();
    await expect(status(second)).toContainText("Active generation: 1");
    await commit(second);
    expect(inspect(server.directory).current.generation).toBe(2);
    const details = page.getByRole("region", { name: "Last lifecycle command" });
    const key = await details.locator("dd").nth(0).innerText();
    await page.getByRole("button", { name: "Retry same commit command", exact: true }).click();
    await expect(status(page)).toContainText("Present state read separately.");
    await expect(receipt(page)).toContainText("Observed generation at command: 1");
    await expect(page.locator(".current-indicator")).toContainText("2");
    const before = inspect(server.directory);
    await page.reload(); await expect(status(page)).toContainText("Active generation: 2");
    await retrieve(page, raw);
    await page.getByText("Resume a commit after reload", { exact: true }).click();
    await page.getByLabel("Saved command key").fill(key);
    await page.getByLabel("Original expected generation").fill("0");
    await acknowledge(page).check();
    await page.getByRole("button", { name: "Resume saved commit command", exact: true }).click();
    await expect(receipt(page)).toContainText("Observed generation at command: 1");
    await expect(status(page)).toContainText("Present state read separately.");
    expect(inspect(server.directory)).toEqual(before);
    const { directory, origin } = server; await server.stop();
    server = await runtime({ dist, directory, port: Number(new URL(origin).port) });
    await server.session();
    await page.getByRole("button", { name: "Retry same commit command", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("session expired");
    await expect(receipt(page)).toHaveCount(0);
    await page.getByRole("button", { name: "Retry same commit command", exact: true }).click();
    await expect(status(page)).toContainText("Present state read separately.");
    await expect(receipt(page)).toContainText("Recorded outcome: committed");
    expect(inspect(server.directory)).toEqual(before);
  } finally { await second.close(); await server.stop(); }
});

test("reject is terminal, retained across reload and safe against concurrent commit", async ({ page, context }) => {
  const server = await runtime({ dist }); const second = await context.newPage();
  try {
    await open(page, server); await stage(page);
    await open(second, server); await stage(second);
    await acknowledge(page).check(); await page.getByRole("button", { name: "Reject reviewed preview", exact: true }).click();
    await expect(status(page)).toContainText("Preview rejected.");
    await expect(review(page)).toContainText("Rejected at");
    const rejected = inspect(server.directory);
    expect(rejected.current.generation).toBe(0); expect(rejected.counts.checkpoints).toBe(0);
    await commit(second, "preview_rejected");
    expect(inspect(server.directory).current).toEqual(rejected.current);
    const afterRejectedCommand = inspect(server.directory);
    await page.reload(); await expect(status(page)).toContainText("Current checkpoint read.");
    await retrieve(page, raw); await expect(review(page).locator(".badge").first()).toHaveText("rejected");
    await expect(page.getByRole("button", { name: "Commit reviewed preview", exact: true })).toBeDisabled();
    await stage(page); await expect(review(page).locator(".badge").first()).toHaveText("rejected");
    expect(inspect(server.directory)).toEqual(afterRejectedCommand);
    const fresh = variant((doc) => { doc.metadata.bundle_id = "FRESH"; });
    await stage(page, fresh); await acknowledge(page).check();
    await stage(second, fresh); await commit(second);
    const committed = inspect(server.directory);
    await page.getByRole("button", { name: "Reject reviewed preview", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("response is unresolved");
    expect(inspect(server.directory)).toEqual(committed);
    await page.getByRole("button", { name: "Resolve by fresh reads", exact: true }).click();
    await retrieve(page, fresh); await page.getByRole("button", { name: "Refresh current state" }).click();
    await expect(status(page)).toContainText("Current checkpoint read.");
    await expect(review(page).locator(".badge").first()).toHaveText("committed");
    await expect(page.getByRole("button", { name: "Reject reviewed preview", exact: true })).toBeDisabled();
  } finally { await second.close(); await server.stop(); }
});

for (const kind of ["source_conflict", "identity_review_required"]) {
  test(`${kind} is a durable reviewed outcome without an override`, async ({ page }) => {
    const server = await runtime({ dist });
    try {
      await open(page, server); await stage(page); await commit(page);
      const before = inspect(server.directory);
      const changed = variant((doc) => {
        if (kind === "source_conflict") {
          // Independently balanced changed event: 3 * 90 = 270, plus fee 1 => cash -271.
          doc.activity[0].quantity.value = "3";
          doc.activity[0].principal.value = "270";
          doc.activity[0].cash_movement.value = "-271";
        }
        else {
          doc.metadata.profile_id = "OTHER-SYNTHETIC-PROFILE";
          for (const account of doc.accounts) account.profile_id = doc.metadata.profile_id;
        }
      });
      await stage(page, changed); await commit(page, kind);
      expect(inspect(server.directory).current).toEqual(before.current);
      expect(inspect(server.directory).counts.checkpoints).toBe(before.counts.checkpoints);
      await shot(page, `${kind}-desktop`);
      await expect(page.getByRole("button", { name: /override|approve.*trade/ })).toHaveCount(0);
      const after = inspect(server.directory);
      await page.getByRole("button", { name: "Retry same commit command", exact: true }).click();
      await expect(status(page)).toContainText("Present state read separately.");
      expect(inspect(server.directory)).toEqual(after);
    } finally { await server.stop(); }
  });
}

for (const kind of ["missing-basis", "unknown-coverage", "contradiction", "malformed"]) {
  test(`${kind} retains reasons and only inspection-valid facts may activate`, async ({ page }) => {
    const server = await runtime({ dist });
    try {
      await open(page, server);
      const changed = kind === "malformed" ? Buffer.from("{broken") : variant((doc) => {
        if (kind === "missing-basis") doc.lots[1].basis = { value: null, reason: "synthetic_missing_basis" };
        if (kind === "unknown-coverage") { doc.coverage[0].status = "unknown"; doc.coverage[0].evidence = { value: null, reason: "synthetic_coverage_unknown" }; }
        if (kind === "contradiction") doc.lots[0].quantity.value = "11";
      });
      await stage(page, changed); await acknowledge(page).check();
      if (["contradiction", "malformed"].includes(kind)) {
        await expect(page.getByRole("button", { name: "Commit reviewed preview", exact: true })).toBeDisabled();
        await page.getByRole("button", { name: "Reject reviewed preview", exact: true }).click();
        await expect(status(page)).toContainText("Preview rejected.");
        expect(inspect(server.directory).current.generation).toBe(0);
      } else {
        await commit(page);
        await page.getByRole("button", { name: "Current checkpoint", exact: true }).click();
        const current = page.getByRole("article", { name: "Current checkpoint review" });
        await expect(current).toContainText(kind === "missing-basis" ? "synthetic_missing_basis" : "synthetic_coverage_unknown");
        await expect(current).toContainText("Financial planning remains unavailable.");
        expect(inspect(server.directory).current.planning_ready).toBe(false);
        if (kind === "missing-basis") expect(inspect(server.directory).current.checkpoint.inspection.total_basis.state).toBe("unknown");
        await shot(page, kind + "-committed");
      }
    } finally { await server.stop(); }
  });
}

for (const kind of ["commit", "reject"]) {
  test(`lost ${kind} response does not automatically retry or permit a replacement command`, async ({ page }) => {
    const server = await runtime({ dist }); let posts = 0; const payloads = [];
    try {
      await open(page, server); await stage(page);
      const handler = async (route) => { posts++; payloads.push(route.request().postDataJSON()); const response = await route.fetch(); expect(response.status()).toBe(200); await route.abort("failed"); };
      await page.route(`**/api/v1/${kind}`, handler);
      await acknowledge(page).check(); await page.getByRole("button", { name: kind === "commit" ? "Commit reviewed preview" : "Reject reviewed preview", exact: true }).click();
      await expect(page.getByRole("alert")).toContainText("response is unresolved");
      expect(posts).toBe(1); const before = inspect(server.directory);
      expect(before.current.generation).toBe(kind === "commit" ? 1 : 0);
      await expect(acknowledge(page)).toBeDisabled();
      await shot(page, kind + "-uncertain");
      await page.unroute(`**/api/v1/${kind}`, handler);
      await page.route(`**/api/v1/${kind}`, async (route) => { posts++; payloads.push(route.request().postDataJSON()); await route.continue(); });
      await page.getByRole("button", { name: kind === "commit" ? "Retry same commit command" : "Retry same rejection", exact: true }).click();
      await expect(status(page)).toContainText(kind === "commit" ? "Present state read separately." : "Preview rejected.");
      expect(posts).toBe(2); expect(payloads[1]).toEqual(payloads[0]); expect(inspect(server.directory)).toEqual(before);
    } finally { await server.stop(); }
  });
}

test("same-key changed payload is refused and post-commit read failure retains the durable receipt", async ({ page }) => {
  const server = await runtime({ dist });
  try {
    await open(page, server); await stage(page); await commit(page);
    const before = inspect(server.directory);
    const key = await page.getByRole("region", { name: "Last lifecycle command" }).locator("dd").first().innerText();
    await page.getByText("Resume a commit after reload", { exact: true }).click();
    await page.getByLabel("Saved command key").fill(key); await page.getByLabel("Original expected generation").fill("1");
    await acknowledge(page).check(); await page.getByRole("button", { name: "Resume saved commit command", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("bound to a different payload");
    expect(inspect(server.directory)).toEqual(before);
    await page.getByLabel("Original expected generation").fill("0"); await acknowledge(page).check();
    await page.getByRole("button", { name: "Resume saved commit command", exact: true }).click();
    await expect(status(page)).toContainText("Present state read separately.");
    expect(inspect(server.directory)).toEqual(before);
    await page.route("**/api/v1/current", (route) => route.fulfill({ status: 503, contentType: "application/json", body: '{"error":"synthetic_read_failure"}' }));
    await acknowledge(page).check(); await page.getByRole("button", { name: "Commit reviewed preview", exact: true }).click();
    await expect(receipt(page)).toContainText("Recorded outcome: duplicate");
    await expect(page.getByRole("alert")).toContainText("receipt is recorded. A follow-up read failed");
    await expect(page.locator(".current-indicator")).toContainText("Unavailable");
    expect(inspect(server.directory).current).toEqual(before.current);
  } finally { await server.stop(); }
});

test("mutation endpoints deny missing/invalid sessions and foreign browser origins without changes", async ({ page, context }) => {
  const server = await runtime({ dist });
  const foreign = createServer((_request, response) => response.end("<!doctype html><title>Untrusted local origin</title>"));
  await new Promise((resolve) => foreign.listen(0, "127.0.0.1", resolve));
  try {
    await open(page, server); await stage(page); const before = inspect(server.directory);
    const token = await server.session();
    const identity = createHash("sha256").update(raw).digest("hex");
    const codes = await page.evaluate(async ({ identity }) => {
      const values = [];
      for (const name of ["commit", "reject"]) for (const authorization of [null, "Bearer invalid"]) {
        const body = { schema_version: "synthetic-import-api-v1", preview_sha256: identity, ...(name === "commit" ? { command_key: "denied", expected_generation: 0 } : {}) };
        values.push((await fetch(`/api/v1/${name}`, { method: "POST", headers: { "Content-Type": "application/json", ...(authorization ? { Authorization: authorization } : {}) }, body: JSON.stringify(body) })).status);
      }
      return values;
    }, { identity });
    expect(codes).toEqual([401, 401, 401, 401]);
    const denied = await context.newPage(); await denied.goto(`http://127.0.0.1:${foreign.address().port}`);
    const blocked = await denied.evaluate(async ({ origin, token, identity }) => {
      const values = [];
      for (const name of ["commit", "reject"]) {
        try { await fetch(`${origin}/api/v1/${name}`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` }, body: JSON.stringify({ schema_version: "synthetic-import-api-v1", preview_sha256: identity, ...(name === "commit" ? { command_key: "foreign", expected_generation: 0 } : {}) }) }); values.push(false); }
        catch { values.push(true); }
      }
      return values;
    }, { origin: server.origin, token, identity });
    expect(blocked).toEqual([true, true]); await denied.close(); expect(inspect(server.directory)).toEqual(before);
  } finally { await server.stop(); await new Promise((resolve) => foreign.close(resolve)); }
});
