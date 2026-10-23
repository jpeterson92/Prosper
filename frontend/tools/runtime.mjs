import { spawn } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

export const root = fileURLToPath(new URL("../../", import.meta.url));
export const python = process.env.PROSPER_BROWSER_PYTHON ?? path.join(root, ".venv", "Scripts", "python.exe");

export async function runtime({ dist, port, developmentPort, directory } = {}) {
  directory ??= path.join(root, ".local", "browser", randomUUID());
  await mkdir(path.dirname(directory), { recursive: true });
  const args = ["-I", "-m", "prosper.local_api", "--source-root", root, "--synthetic-runtime", directory];
  if (dist) args.push("--ui-dist", dist);
  if (port) args.push("--port", String(port));
  if (developmentPort) args.push("--development-port", String(developmentPort));
  const child = spawn(python, args, { cwd: root, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  let output = "";
  let errors = "";
  let first = true;
  const origin = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { child.kill(); reject(new Error("runtime_start_timeout")); }, 15000);
    child.once("error", (error) => { clearTimeout(timer); reject(error); });
    child.once("exit", () => { clearTimeout(timer); reject(new Error("runtime_start_failed")); });
    child.stderr.on("data", (chunk) => { errors += chunk; });
    let buffer = "";
    child.stdout.on("data", (chunk) => {
      buffer += chunk;
      if (first && buffer.includes("\n")) {
        const index = buffer.indexOf("\n");
        const parsed = JSON.parse(buffer.slice(0, index));
        buffer = buffer.slice(index + 1);
        first = false;
        clearTimeout(timer);
        resolve(parsed.origin);
      }
      if (!first) { output += buffer; buffer = ""; }
    });
  });
  // Public origin is printed just before ASGI startup. Fetch retries only connection failures.
  async function session() {
    let last;
    for (let attempt = 0; attempt < 30; attempt++) {
      try {
        const response = await fetch(`${origin}/session`, {
          method: "POST", headers: { Origin: origin, "X-Prosper-Bootstrap": "1" },
        });
        if (!response.ok) throw new Error("session_failed");
        return (await response.json()).token;
      } catch (error) { last = error; await new Promise((resolve) => setTimeout(resolve, 50)); }
    }
    throw last;
  }
  async function stop() {
    if (child.exitCode === null) {
      const token = await session();
      const exited = new Promise((resolve) => child.once("exit", resolve));
      await fetch(`${origin}/shutdown`, { method: "POST", headers: { Origin: origin, Authorization: `Bearer ${token}` } });
      const timeout = setTimeout(() => child.kill(), 8000);
      await exited;
      clearTimeout(timeout);
    }
    if (child.exitCode !== 0 || output || errors) throw new Error("runtime_output_or_exit_failure");
  }
  return { origin, directory, session, stop };
}
