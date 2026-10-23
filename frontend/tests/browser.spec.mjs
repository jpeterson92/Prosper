import { test, expect } from "@playwright/test";
import { execFileSync, spawn } from "node:child_process";
import { createServer } from "node:http";
import { randomUUID, createHash } from "node:crypto";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { runtime, root, python } from "../tools/runtime.mjs";

const dist = path.join(root, "frontend", "dist");
const results = path.join(root, ".local", "browser-evidence");
function fixture(operation, directory) {
  return JSON.parse(execFileSync(python, ["-I", path.join(root, "scripts", "browser_fixture.py"), operation, directory], { windowsHide: true }));
}
async function localPage() {
  const server = createServer((_, response) => {
    response.setHeader("Content-Type", "text/html");
    response.end("<!doctype html><title>Untrusted local origin</title>");
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return { origin: `http://127.0.0.1:${server.address().port}`, stop: () => new Promise((resolve) => server.close(resolve)) };
}

for (const seeded of [false, true]) {
  test(`built offline probe preserves ${seeded ? "populated" : "empty"} active state and exact/unknown transport`, async ({ page, context, browser }) => {
    const directory = path.join(root, ".local", "browser", randomUUID());
    if (seeded) fixture("seed", directory);
    const server = await runtime({ dist, directory });
    const destinations = [], unexpected = [], consoleOutput = [], tokens = [], payloads = [];
    page.on("console", (message) => consoleOutput.push(message.text()));
    page.on("pageerror", (error) => consoleOutput.push(error.message));
    await context.route("**/*", async (route) => {
      const url = new URL(route.request().url());
      destinations.push(url.pathname);
      if (url.origin !== server.origin || url.search || url.username || url.password) { unexpected.push("unexpected_destination_or_query"); await route.abort(); }
      else await route.continue();
    });
    page.on("response", async (response) => {
      if (response.url().endsWith("/session") && response.ok()) tokens.push((await response.json()).token);
      if (response.url().endsWith("/api/v1/previews") && response.ok()) payloads.push(await response.json());
    });
    try {
      const token = await server.session();
      const before = fixture("inspect", directory);
      await page.goto(server.origin);
      await page.getByRole("button", { name: "Check connection" }).click();
      await expect(page.getByRole("status")).toContainText(`F001/F004 transport verified. Active generation: ${seeded ? 1 : 0}`);
      await expect(page.getByRole("button")).toHaveCount(1);
      const after = fixture("inspect", directory);
      expect(after.current).toEqual(before.current);
      expect(after.counts.checkpoints).toBe(before.counts.checkpoints);
      expect(after.counts.import_activations).toBe(before.counts.import_activations);
      expect(after.counts.import_commands).toBe(before.counts.import_commands);
      expect(payloads).toHaveLength(3);
      const raw = await readFile(path.join(root, "examples", "synthetic", "F001.json"));
      expect(payloads[0].receipt.raw_sha256).toBe(createHash("sha256").update(raw).digest("hex"));
      expect(payloads[0].inspection.total_basis).toEqual({ state: "known", value: "2181", original_text: "2181", source_quantum: "1" });
      const precise = payloads[1].source.source_values.find((value) => value.path.join(".") === "quotes.0.price.value");
      expect(precise.exact).toEqual({ state: "known", value: "90", original_text: "90.00", source_quantum: "0.01" });
      expect(payloads[2].inspection.total_basis).toEqual({ state: "unknown", value: null, reasons: ["synthetic_missing_basis"] });
      expect(unexpected).toEqual([]);
      expect(destinations.some((url) => url.includes("?") || url.includes("token"))).toBe(false);
      expect(await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length, cookies: document.cookie }))).toEqual({ local: 0, session: 0, cookies: "" });
      expect(consoleOutput).toEqual([]);
      expect(tokens.every((secret) => !consoleOutput.join("").includes(secret))).toBe(true);
      expect(consoleOutput.join("").includes("LOT-A-OLD")).toBe(false);
      await mkdir(results, { recursive: true });
      await page.screenshot({ path: path.join(results, `probe-${seeded ? "populated" : "empty"}-desktop.png`), fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: path.join(results, `probe-${seeded ? "populated" : "empty"}-narrow.png`), fullPage: true });
      await writeFile(path.join(results, `requests-${seeded}.json`), JSON.stringify({ browser: browser.version(), destinations, unexpected, counts: after.counts }, null, 2) + "\n");
      // No token in failures: compare booleans rather than secret-bearing headers.
      expect(tokens.length > 0 && token.length >= 43).toBe(true);
    } finally { await server.stop(); }
  });
}

test("real browser denies foreign origin, missing/invalid session and old token after restart", async ({ page, context }) => {
  const server = await runtime({ dist });
  const foreign = await localPage();
  let stopped = false;
  try {
    await page.goto(server.origin);
    const codes = await page.evaluate(async () => {
      const a = await fetch("/api/v1/current");
      const b = await fetch("/api/v1/current", { headers: { Authorization: "Bearer invalid" } });
      return [a.status, b.status];
    });
    expect(codes).toEqual([401, 401]);
    const oldToken = await server.session();
    const denied = await context.newPage();
    await denied.goto(foreign.origin);
    const result = await denied.evaluate(async (origin) => {
      try { await fetch(`${origin}/session`, { method: "POST", headers: { "X-Prosper-Bootstrap": "1" } }); return "unexpected"; }
      catch { return "blocked"; }
    }, server.origin);
    expect(result).toBe("blocked");
    await denied.close();
    const port = Number(new URL(server.origin).port);
    await server.stop(); stopped = true;
    const restarted = await runtime({ dist, directory: server.directory, port });
    try {
      await restarted.session();
      const status = await page.evaluate(async (token) => (await fetch("/api/v1/current", { headers: { Authorization: `Bearer ${token}` } })).status, oldToken);
      expect(status).toBe(401);
      await page.getByRole("button", { name: "Check connection" }).click();
      await expect(page.getByRole("status")).toContainText("transport verified");
    } finally { await restarted.stop(); }
  } finally { if (!stopped) await server.stop(); await foreign.stop(); }
});

test("diagnostic error status is safe and usable", async ({ page }) => {
  const server = await runtime({ dist });
  try {
    await page.goto(server.origin);
    await page.route("**/session", (route) => route.fulfill({ status: 503, contentType: "text/plain", body: "synthetic refusal" }));
    await page.getByRole("button", { name: "Check connection" }).click();
    await expect(page.getByRole("status")).toContainText("Connection unavailable.");
    await expect(page.getByRole("button")).toBeEnabled();
    await mkdir(results, { recursive: true });
    await page.screenshot({ path: path.join(results, "probe-error.png"), fullPage: true });
  } finally { await server.stop(); }
});

for (const kind of ["non-json", "unsafe-generation"]) {
  test(`diagnostic blocks ${kind} current-state response`, async ({ page }) => {
    const server = await runtime({ dist });
    try {
      await page.goto(server.origin);
      await page.route("**/api/v1/current", (route) => route.fulfill({
        status: 200,
        contentType: kind === "non-json" ? "text/plain" : "application/json",
        body: kind === "non-json" ? "synthetic protocol failure" : '{"generation":9007199254740993,"checkpoint":null,"planning_ready":false,"schema_version":"synthetic-import-api-v1"}',
      }));
      await page.getByRole("button", { name: "Check connection" }).click();
      await expect(page.getByRole("status")).toContainText("Connection unavailable.");
      await expect(page.getByRole("button")).toBeEnabled();
    } finally { await server.stop(); }
  });
}

test("explicit trusted Vite origin can preflight/bootstrap and use the generated client", async ({ page }) => {
  // No privileged test API is embedded in the production bundle. Import the actual
  // source client/probe via the explicitly trusted dev server in this test only.
  const vite = spawn(process.execPath, [path.join(root, "frontend", "node_modules", "vite", "bin", "vite.js"), "--host", "127.0.0.1", "--port", "5173", "--strictPort"], { cwd: path.join(root, "frontend"), windowsHide: true, stdio: "ignore" });
  const server = await runtime({ developmentPort: 5173 });
  try {
    let ready = false;
    for (let i = 0; i < 50; i++) {
      try { ready = (await fetch("http://127.0.0.1:5173")).ok; } catch {}
      if (ready) break;
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    expect(ready).toBe(true);
    await page.goto("http://127.0.0.1:5173");
    const generation = await page.evaluate(async (origin) => {
      const { runProbe } = await import("/src/probe.ts");
      return runProbe(origin);
    }, server.origin);
    expect(generation).toBe(0);
  } finally { await server.stop(); vite.kill(); }
});
