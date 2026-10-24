import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { runtime, root, python } from "../tools/runtime.mjs";

function fixture(operation, directory, extra = []) {
  return JSON.parse(execFileSync(python, ["-I", path.join(root, "scripts/browser_fixture.py"), operation, directory, ...extra], { windowsHide: true }));
}

test("browser mutations survive complete backup/restore with original receipts, exact values and unknowns", async ({ page, context, browser }) => {
  const base = path.join(root, ".local/integrated-candidate", randomUUID());
  const directory = path.join(base, "runtime"), backup = path.join(base, "backup"), restored = path.join(base, "restored");
  const raw = await readFile(path.join(root, "examples/synthetic/F001.json"));
  const doc = JSON.parse(raw);
  doc.metadata.bundle_id = "F001-INTEGRATED";
  for (const group of ["positions", "lots", "cash", "quotes"]) for (const row of doc[group]) {
    if ("checkpoint_id" in row) row.checkpoint_id = doc.metadata.bundle_id;
  }
  doc.quotes[0].price.value = "90.005";
  doc.positions[0].quantity.value = "12.125";
  doc.lots[0].quantity.value = "10.125";
  doc.lots[1].basis = { value: null, reason: "synthetic_missing_basis" };
  doc.coverage[0].status = "unknown";
  doc.coverage[0].evidence = { value: null, reason: "synthetic_coverage_unknown" };
  const precise = Buffer.from(JSON.stringify(doc));
  const dist = path.join(root, "frontend/dist");
  let server = await runtime({ dist, directory });
  let allowedOrigin = server.origin;
  const unexpected = [], logs = [], commands = [], receipts = [];
  page.on("console", (event) => logs.push(event.text()));
  page.on("pageerror", (error) => logs.push(error.message));
  page.on("request", (request) => { if (request.url().endsWith("/api/v1/commit")) commands.push(request.postDataJSON()); });
  page.on("response", async (response) => { if (response.ok() && response.url().endsWith("/api/v1/commit")) receipts.push(await response.json()); });
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== allowedOrigin || url.search || url.username || url.password) { unexpected.push(url.pathname); await route.abort(); }
    else await route.continue();
  });
  const status = () => page.getByRole("status", { name: "Review status" });
  const receipt = () => page.getByRole("status", { name: "Command receipt" });
  async function stage(bytes) {
    await page.getByLabel("Synthetic JSON file (up to 2 MiB)").setInputFiles({ name: "fictional.json", mimeType: "application/json", buffer: bytes });
    await page.getByRole("button", { name: "Stage preview", exact: true }).click();
    await expect(status()).toContainText("Preview retained for inspection.");
  }
  async function commit() {
    await page.getByLabel("I reviewed this preview, its readiness reasons and the current checkpoint.").check();
    await page.getByRole("button", { name: "Commit reviewed preview", exact: true }).click();
    await expect(receipt()).toContainText("Recorded outcome: committed");
    await expect(status()).toContainText("Present state read separately.");
  }
  try {
    await page.goto(server.origin); await expect(status()).toContainText("Current checkpoint read.");
    await stage(raw); await commit();
    const first = fixture("inspect", directory);
    expect(first.current.generation).toBe(1);
    expect(first.current.checkpoint.inspection.total_basis.value).toBe("2181");
    expect(first.current.checkpoint.inspection.settled_cash_nav.value).toBe("2399");
    expect(first.current.checkpoint.source.document.cash[0].settled.value).toBe("319");
    await stage(precise); await commit();
    // A rejected malformed preview is also required evidence, although never active.
    await stage(Buffer.from("{synthetic invalid"));
    await page.getByLabel("I reviewed this preview, its readiness reasons and the current checkpoint.").check();
    await page.getByRole("button", { name: "Reject reviewed preview", exact: true }).click();
    await expect(status()).toContainText("Preview rejected.");
    const before = fixture("inspect", directory);
    expect(before.current.generation).toBe(2);
    expect(before.counts).toEqual({ checkpoints: 2, import_activations: 2, import_commands: 2, import_previews: 3 });
    expect(before.current.planning_ready).toBe(false);
    expect(before.current.checkpoint.inspection.total_basis).toEqual({ state: "unknown", value: null, reasons: ["synthetic_missing_basis"] });
    const price = before.current.checkpoint.source.source_values.find((item) => item.path.join(".") === "quotes.0.price.value");
    expect(price.exact).toEqual({ state: "known", value: "90.005", original_text: "90.005", source_quantum: "0.001" });
    expect(before.current.checkpoint.source.document.positions[0].quantity.value).toBe("12.125");
    expect(receipts).toHaveLength(2);
    const originalReceipt = receipts[0], originalCommand = commands[0];
    await server.stop(); server = null;
    const manifest = fixture("backup", directory, ["--destination", backup, "--candidate", "T004.5.1-bbea971705b67889"]);
    expect(manifest.state).toEqual({ checkpoints: 2, previews: 3, commands: 2, generation: 2 });
    expect(manifest.evidence).toHaveLength(3);
    expect(fixture("restore", backup, ["--destination", restored])).toEqual(manifest);
    expect(fixture("inspect", restored)).toEqual(before);
    server = await runtime({ dist, directory: restored }); allowedOrigin = server.origin;
    await page.goto(server.origin); await expect(status()).toContainText("Active generation: 2");
    await page.getByRole("button", { name: "Current checkpoint", exact: true }).click();
    await expect(page.getByRole("article", { name: "Current checkpoint review" })).toContainText("synthetic_missing_basis");
    await expect(page.getByRole("article", { name: "Current checkpoint review" })).toContainText("synthetic_coverage_unknown");
    await page.getByText("Retrieve a retained preview", { exact: true }).click();
    await page.getByLabel("Original-byte SHA-256", { exact: true }).fill(createHash("sha256").update(raw).digest("hex"));
    await page.getByRole("button", { name: "Retrieve preview", exact: true }).click();
    await expect(status()).toContainText("Retained preview retrieved.");
    await page.getByText("Resume a commit after reload", { exact: true }).click();
    await page.getByLabel("Saved command key").fill(originalCommand.command_key);
    await page.getByLabel("Original expected generation").fill("0");
    await page.getByLabel("I reviewed this preview, its readiness reasons and the current checkpoint.").check();
    await page.getByRole("button", { name: "Resume saved commit command", exact: true }).click();
    await expect(status()).toContainText("Present state read separately.");
    await expect(receipt()).toContainText("Original activation generation: 1");
    expect(receipts.at(-1)).toEqual(originalReceipt);
    expect(commands.at(-1)).toEqual(originalCommand);
    expect(fixture("inspect", restored)).toEqual(before);
    expect(fixture("inspect", directory)).toEqual(before);
    expect(unexpected).toEqual([]); expect(logs).toEqual([]);
    expect(await page.evaluate(() => [localStorage.length, sessionStorage.length, document.cookie])).toEqual([0, 0, ""]);
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await mkdir(base, { recursive: true });
    await page.screenshot({ path: path.join(base, "restored-narrow.png"), fullPage: true });
    await writeFile(path.join(base, "qualification.json"), JSON.stringify({ browser: browser.version(), counts: before.counts, state: manifest.state, implementation: manifest.implementation_sha256, unexpected, consoleErrors: logs.length, restoredReceiptIdentical: true }, null, 2) + "\n");
  } finally { if (server) await server.stop(); }
});
