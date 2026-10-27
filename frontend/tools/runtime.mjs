import { spawn, spawnSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

export const root = fileURLToPath(new URL("../../", import.meta.url));
export const python = process.env.PROSPER_BROWSER_PYTHON ?? path.join(root, ".venv", "Scripts", "python.exe");

export async function refreshHistory(server, document) {
  const token=await server.session();
  async function post(route,body) {
    const response=await fetch(server.origin+route,{method:"POST",headers:{Origin:server.origin,Authorization:`Bearer ${token}`,"Content-Type":"application/json"},body:JSON.stringify(body)});
    if(!response.ok)throw new Error("history_fixture_request_failed");
    return response.json();
  }
  const ids=[];
  for(const part of document.parts)ids.push((await post("/api/v1/history/parts",part)).id);
  const manifest={version:"advisory-history-manifest-v1",part_count:document.part_count,part_ids:ids,command_key:document.command_key,expected_revision:document.expected_revision};
  await post("/api/v1/history/preview",manifest);
  return post("/api/v1/history/refresh",manifest);
}

export async function runtime({ dist, port, developmentPort, directory, artifact } = {}) {
  directory ??= path.join(root, ".local", "browser", randomUUID());
  await mkdir(path.dirname(directory), { recursive: true });
  const args = ["-I", "-m", "prosper.local_api", "--runtime", directory];
  if (!artifact) { try { await import("node:fs/promises").then(fs=>fs.access(path.join(directory,"advisory-v1.sqlite3"))); } catch { args.push("--initialize"); } }
  if (dist) args.push("--ui-dist", dist);
  if (port) args.push("--port", String(port));
  if (developmentPort) args.push("--development-port", String(developmentPort));
  const executable = artifact ? "powershell.exe" : python;
  const launchArgs = artifact ? ["-NoProfile", "-File", path.join(artifact,"Launch.ps1"), "-Command", "start", "-Workspace", directory] : args;
  const child = spawn(executable, launchArgs, { cwd: artifact ?? root, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
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
  async function interrupt() {
    if (child.exitCode !== null) throw new Error("runtime_already_stopped");
    const exited = new Promise(resolve => child.once("exit",resolve));
    const killed=spawnSync("taskkill.exe",["/PID",String(child.pid),"/T","/F"],{windowsHide:true,stdio:"ignore"});
    if(killed.status!==0)throw new Error("runtime_interrupt_failed");
    await exited;
  }
  return { origin, directory, session, stop, interrupt };
}
