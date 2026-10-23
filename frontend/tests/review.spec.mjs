import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { randomUUID, createHash } from "node:crypto";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { runtime, root, python } from "../tools/runtime.mjs";
import { decimalDisplay } from "../src/display.ts";

const raw = await readFile(path.join(root, "examples/synthetic/F001.json"));
const dist = path.join(root, "frontend", "dist");
const results = path.join(root, ".local", "review-evidence");
const reviewStatus = (page) => page.getByRole("status", { name: "Review status" });
function inspect(directory, operation = "inspect") {
  return JSON.parse(execFileSync(python, ["-I", path.join(root, "scripts", "browser_fixture.py"), operation, directory], { windowsHide: true }));
}
async function open(page, server) {
  await page.goto(server.origin);
  await expect(reviewStatus(page)).toContainText("Current checkpoint read.");
}
async function stage(page, bytes, name = "fictional.json") {
  await page.getByLabel("Synthetic JSON file (up to 2 MiB)").setInputFiles({ name, mimeType: "application/json", buffer: bytes });
  await page.getByRole("button", { name: "Stage preview", exact: true }).click();
  await expect(reviewStatus(page)).toContainText("Preview retained for inspection.");
  return page.getByRole("article", { name: "Selected preview review" });
}

test("display-only decimal rounding has independently specified ties, signs and large integer outcomes", () => {
  for (const [value, expected] of [
    ["2.345", "2.34"], ["2.355", "2.36"], ["-2.345", "-2.34"], ["-2.355", "-2.36"],
    ["9.999", "10.00"], ["0.005", "0.00"], ["-0.005", "0.00"], ["0.000000000001", "0.00"],
    ["9007199254740993.125", "9,007,199,254,740,993.12"], ["319", "319.00"],
  ]) expect(decimalDisplay(value, true)).toBe(expected);
  expect(decimalDisplay("9007199254740993.125", false)).toBe("9,007,199,254,740,993.125");
});

for (const seeded of [false, true]) {
  test(`real review preserves ${seeded ? "populated" : "empty"} current state across staging, rounding and retrieval`, async ({ page, context, browser }) => {
    const directory = path.join(root, ".local", "browser", randomUUID());
    if (seeded) inspect(directory, "seed");
    const server = await runtime({ dist, directory });
    const destinations = [], unexpected = [], logs = [], tokens = [];
    page.on("console", (message) => logs.push(message.text()));
    page.on("pageerror", (error) => logs.push(error.message));
    page.on("response", async (response) => { if (response.ok() && response.url().endsWith("/session")) tokens.push((await response.json()).token); });
    await context.route("**/*", async (route) => {
      const url = new URL(route.request().url()); destinations.push(url.pathname);
      if (url.origin !== server.origin || url.search || url.username || url.password) { unexpected.push("unexpected request"); await route.abort(); }
      else await route.continue();
    });
    try {
      await open(page, server);
      const before = inspect(directory);
      const preview = await stage(page, raw);
      await expect(preview.getByRole("heading", { name: "Source & checkpoint boundary" })).toBeVisible();
      await expect(preview).toContainText("2026-10-22T16:00:00-04:00");
      await expect(preview).toContainText("Closing checkpoint includes BUY-001");
      await expect(preview.locator(".metrics")).toContainText("2,399");
      await expect(preview.locator(".metrics")).toContainText("2,181");
      const positions = preview.getByRole("region", { name: "Positions", exact: true });
      await expect(positions.getByRole("row", { name: /SEC-FAAA/ })).toContainText("12");
      await expect(positions.getByRole("row", { name: /SEC-FBBB/ })).toContainText("5");
      const cash = preview.getByRole("region", { name: "Cash buckets" });
      await expect(cash.getByRole("row", { name: /DEMO-TAXABLE-1/ }).getByRole("cell")).toHaveText(["319", "319", "0"]);
      await expect(preview).toContainText("Financial planning remains unavailable.");
      const retainedBefore = inspect(directory);
      await page.getByLabel("Round displayed numeric values to 2 decimals").check();
      await expect(preview.locator(".metrics")).toContainText("2,399.00");
      await expect(cash.getByRole("row", { name: /DEMO-TAXABLE-1/ }).getByRole("cell")).toHaveText(["319.00", "319.00", "0.00"]);
      expect(inspect(directory)).toEqual(retainedBefore);
      await preview.getByText(/Exact & source values/).click();
      await expect(preview.getByRole("region", { name: "Exact source values table" })).toContainText("quotes / [0] / price / value");
      await page.getByRole("button", { name: "Current checkpoint", exact: true }).click();
      const active = page.getByRole("article", { name: "Current checkpoint review" });
      if (seeded) { await expect(active).toContainText("Active generation 1"); await expect(active.locator(".metrics")).toContainText("2,181.00"); }
      else await expect(active).toContainText("No active checkpoint");
      await mkdir(results, { recursive: true });
      await page.screenshot({ path: path.join(results, `current-${seeded ? "populated" : "empty"}-desktop.png`), fullPage: true });
      await page.getByRole("button", { name: "Refresh current state" }).click();
      await expect(reviewStatus(page)).toContainText("Current checkpoint read.");
      expect(inspect(directory).current).toEqual(before.current);
      const identity = createHash("sha256").update(raw).digest("hex");
      await page.reload(); await expect(reviewStatus(page)).toContainText("Current checkpoint read.");
      await page.getByText("Retrieve a retained preview", { exact: true }).click();
      await page.getByLabel("Original-byte SHA-256", { exact: true }).fill(identity);
      await page.getByRole("button", { name: "Retrieve preview", exact: true }).click();
      await expect(reviewStatus(page)).toContainText("Retained preview retrieved.");
      await expect(preview).toContainText(identity);
      await expect(page.getByRole("button", { name: /commit|reject|approve.*trade/i })).toHaveCount(0);
      const after = inspect(directory);
      expect(after.current).toEqual(before.current);
      for (const table of ["checkpoints", "import_commands", "import_activations"]) expect(after.counts[table]).toBe(before.counts[table]);
      expect(after.counts.import_previews).toBe(1);
      expect(unexpected).toEqual([]); expect(logs).toEqual([]);
      expect(tokens.length > 0 && tokens.every((token) => !logs.join("").includes(token))).toBe(true);
      expect(await page.evaluate(() => [localStorage.length, sessionStorage.length, document.cookie])).toEqual([0, 0, ""]);
      await mkdir(results, { recursive: true });
      await page.screenshot({ path: path.join(results, `review-${seeded ? "populated" : "empty"}-desktop.png`), fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: path.join(results, `review-${seeded ? "populated" : "empty"}-narrow.png`), fullPage: true });
      await writeFile(path.join(results, `requests-${seeded}.json`), JSON.stringify({ browser: browser.version(), destinations, unexpected, counts: after.counts }, null, 2) + "\n");
    } finally { await server.stop(); }
  });
}

for (const kind of ["F003", "F004", "F009"]) {
  test(`real ${kind} review keeps contradictions and unknown reasons visible`, async ({ page }) => {
    const server = await runtime({ dist });
    try {
      await open(page, server);
      const document = JSON.parse(raw);
      if (kind === "F003") document.lots[0].quantity.value = "11";
      if (kind === "F004") document.lots[1].basis = { value: null, reason: "synthetic_missing_basis" };
      if (kind === "F009") { document.coverage[0].status = "unknown"; document.coverage[0].evidence = { value: null, reason: "coverage_unknown" }; }
      const preview = await stage(page, Buffer.from(JSON.stringify(document)), `${kind}.json`);
      const readiness = preview.getByRole("region", { name: "Readiness and findings" });
      if (kind === "F003") { await expect(readiness).toContainText("Not inspection-valid"); await expect(readiness).toContainText("contradictory"); await expect(readiness).toContainText("position_lot_quantity_mismatch"); }
      if (kind === "F004") { await expect(preview.locator(".metrics")).toContainText("Unknown"); await expect(preview.locator(".metrics")).toContainText("synthetic_missing_basis"); }
      if (kind === "F009") { await expect(readiness).toContainText("incomplete"); await expect(readiness).toContainText("coverage_unknown"); }
      await expect(readiness).toContainText("Financial planning remains unavailable.");
      expect(inspect(server.directory).current.generation).toBe(0);
      await mkdir(results, { recursive: true });
      await page.screenshot({ path: path.join(results, `${kind}-desktop.png`), fullPage: true });
    } finally { await server.stop(); }
  });
}

test("source precision, fractional rounding and hostile imported text remain data", async ({ page, context }) => {
  const server = await runtime({ dist }); const unexpected = [], logs = [];
  page.on("console", (message) => logs.push(message.text())); page.on("pageerror", (error) => logs.push(error.message));
  await context.route("**/*", async (route) => { if (new URL(route.request().url()).origin !== server.origin) { unexpected.push(true); await route.abort(); } else await route.continue(); });
  try {
    await open(page, server);
    const document = JSON.parse(raw);
    const hostile = '<img src="https://example.invalid/leak" onerror="window.__importedExecuted=true"> =HYPERLINK("https://example.invalid")';
    document.metadata.inclusion.value = hostile;
    document.accounts[0].alias = '<script>window.__importedExecuted=true</script>';
    document.quotes[0].price.value = "90.005";
    document.positions[0].quantity.value = "12.125";
    document.lots[0].quantity.value = "10.125";
    const preview = await stage(page, Buffer.from(JSON.stringify(document)));
    await expect(preview.getByRole("region", { name: "Source and inclusion" })).toContainText(hostile);
    await preview.getByText("Source assertions and coverage", { exact: true }).click();
    await expect(preview.getByRole("region", { name: "Source and inclusion" })).toContainText('<script>window.__importedExecuted=true</script>');
    expect(await page.evaluate(() => window.__importedExecuted === undefined)).toBe(true);
    await expect(page.locator("img")).toHaveCount(0);
    const before = inspect(server.directory);
    await page.getByLabel("Round displayed numeric values to 2 decimals").check();
    await expect(preview.getByRole("region", { name: "Positions", exact: true }).getByRole("row", { name: /SEC-FAAA/ })).toContainText("90.00");
    await expect(preview.getByRole("region", { name: "Positions", exact: true }).getByRole("row", { name: /SEC-FAAA/ })).toContainText("12.12");
    await preview.getByText(/Exact & source values/).click();
    const row = preview.getByRole("region", { name: "Exact source values table" }).getByRole("row", { name: /quotes \/ \[0\] \/ price \/ value/ });
    await expect(row.getByRole("cell")).toHaveText(["90.005", "90.005", "0.001"]);
    await expect(preview.getByRole("region", { name: "Exact source values table" }).getByRole("row", { name: /positions \/ \[0\] \/ quantity \/ value/ }).getByRole("cell")).toHaveText(["12.125", "12.125", "0.001"]);
    expect(inspect(server.directory)).toEqual(before); expect(unexpected).toEqual([]); expect(logs).toEqual([]);
  } finally { await server.stop(); }
});

test("malformed and truncated parser locations are visible without injected markup", async ({ page }) => {
  const server = await runtime({ dist });
  try {
    await open(page, server);
    const malformed = await stage(page, Buffer.from('{"broken":'));
    await expect(malformed).toContainText("Bundle could not be parsed");
    await expect(malformed).toContainText("byte offset");
    const document = JSON.parse(raw); document['<img onerror="window.__importedExecuted=true">' + "X".repeat(300)] = "ignored";
    const located = await stage(page, Buffer.from(JSON.stringify(document)));
    await expect(located).toContainText("location truncated");
    expect(await page.evaluate(() => window.__importedExecuted === undefined)).toBe(true);
    await expect(page.locator("img")).toHaveCount(0);
    expect(inspect(server.directory).current.generation).toBe(0);
  } finally { await server.stop(); }
});

test("oversize file is blocked before upload, and missing preview retrieval is explicit", async ({ page }) => {
  const server = await runtime({ dist }); let uploaded = false;
  page.on("request", (request) => { if (request.method() === "POST" && request.url().endsWith("/api/v1/previews")) uploaded = true; });
  try {
    await open(page, server);
    await page.getByLabel("Synthetic JSON file (up to 2 MiB)").setInputFiles({ name: "oversize.json", mimeType: "application/json", buffer: Buffer.alloc(2 * 1024 * 1024 + 1) });
    await expect(page.getByRole("alert")).toContainText("exceeds the 2 MiB");
    await expect(page.getByRole("button", { name: "Stage preview", exact: true })).toBeDisabled(); expect(uploaded).toBe(false);
    await page.getByText("Retrieve a retained preview", { exact: true }).click();
    await page.getByLabel("Original-byte SHA-256", { exact: true }).fill("0".repeat(64));
    await page.getByRole("button", { name: "Retrieve preview", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("No retained preview was found");
  } finally { await server.stop(); }
});

test("expired session requires explicit retry and refresh removes unavailable current data", async ({ page }) => {
  const server = await runtime({ dist });
  try {
    await open(page, server);
    await stage(page, raw);
    let denied = false;
    await page.route("**/api/v1/current", (route) => {
      if (!denied) { denied = true; return route.fulfill({ status: 401, contentType: "application/json", body: '{"error":"session_denied"}' }); }
      return route.continue();
    });
    await page.getByRole("button", { name: "Current checkpoint", exact: true }).click();
    await page.getByRole("button", { name: "Refresh current state" }).click();
    await expect(page.getByRole("alert")).toContainText("session expired");
    await expect(page.getByRole("article", { name: "Current checkpoint review" })).toContainText("Current state unavailable");
    await page.getByRole("button", { name: "Refresh current state" }).click();
    await expect(reviewStatus(page)).toContainText("Current checkpoint read.");
    await expect(page.getByRole("alert")).toHaveCount(0);
  } finally { await server.stop(); }
});

test("interrupted upload response is retrieved by digest without automatic restaging", async ({ page }) => {
  const server = await runtime({ dist }); let posts = 0;
  try {
    await open(page, server);
    const handler = async (route) => {
      if (route.request().method() === "POST") {
        posts++; const response = await route.fetch(); expect(response.status()).toBe(200);
        await route.abort("failed");
      } else await route.continue();
    };
    await page.route("**/api/v1/previews", handler);
    await page.getByLabel("Synthetic JSON file (up to 2 MiB)").setInputFiles({ name: "F001.json", mimeType: "application/json", buffer: raw });
    await page.getByRole("button", { name: "Stage preview", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText("request could not be completed");
    expect(posts).toBe(1);
    const state = inspect(server.directory);
    expect(state.counts.import_previews).toBe(1); expect(state.current.generation).toBe(0);
    await page.unroute("**/api/v1/previews", handler);
    await page.getByText("Retrieve a retained preview", { exact: true }).click();
    expect(await page.getByLabel("Original-byte SHA-256", { exact: true }).inputValue()).toBe(createHash("sha256").update(raw).digest("hex"));
    await page.getByRole("button", { name: "Retrieve preview", exact: true }).click();
    await expect(reviewStatus(page)).toContainText("Retained preview retrieved.");
    expect(posts).toBe(1); expect(inspect(server.directory)).toEqual(state);
  } finally { await server.stop(); }
});

test("initial session failure recovers on explicit refresh without persisting credentials", async ({ page }) => {
  const server = await runtime({ dist }); let refused = false;
  try {
    await page.route("**/session", (route) => {
      if (!refused) { refused = true; return route.fulfill({ status: 503, contentType: "text/plain", body: "synthetic refusal" }); }
      return route.continue();
    });
    await page.goto(server.origin);
    await expect(page.getByRole("alert")).toContainText("request could not be completed");
    await mkdir(results, { recursive: true });
    await page.screenshot({ path: path.join(results, "review-error-desktop.png"), fullPage: true });
    await page.getByRole("button", { name: "Refresh current state" }).click();
    await expect(reviewStatus(page)).toContainText("Current checkpoint read.");
    expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
  } finally { await server.stop(); }
});
