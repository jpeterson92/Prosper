import { test, expect } from "@playwright/test";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import path from "node:path";
import { runtime, root } from "../tools/runtime.mjs";
const dist = path.join(root, "frontend", "dist");
async function localPage() {
  const server = createServer((_, response) => {
    response.setHeader("Content-Type", "text/html");
    response.end("<!doctype html><title>Untrusted local origin</title>");
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return { origin: `http://127.0.0.1:${server.address().port}`, stop: () => new Promise((resolve) => server.close(resolve)) };
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
      await page.reload();
      await expect(page.getByRole("status", { name: "Workspace status" })).toContainText("Workspace read.");
    } finally { await restarted.stop(); }
  } finally { if (!stopped) await server.stop(); await foreign.stop(); }
});

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
    const revision = await page.evaluate(async (origin) => {
      const { connect } = await import("/src/client.ts");
      const client = await connect(origin);
      return (await client.current()).revision;
    }, server.origin);
    expect(revision).toBe(0);
  } finally { await server.stop(); vite.kill(); }
});
