/** Deliberate failures use isolated synthetic copies, never edit the authored contracts. */
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { root } from "./runtime.mjs";

const directory = path.join(root, ".local", `contract-negative-${randomUUID()}`);
const typesPath = path.join(directory, "src", "generated", "api.ts");
const schemaPath = path.join(directory, "openapi.json");
await mkdir(path.dirname(typesPath), { recursive: true });
const types = await readFile(path.join(root, "frontend", "src", "generated", "api.ts"), "utf8");
const schema = await readFile(path.join(root, "frontend", "openapi.json"), "utf8");
const check = () => spawnSync(process.execPath, [path.join(root, "frontend", "tools", "contracts.mjs")], {
  cwd: root, windowsHide: true, encoding: "utf8", env: { ...process.env, PROSPER_CONTRACT_CHECK_ROOT: directory },
});
for (const kind of ["schema", "types"]) {
  await writeFile(schemaPath, kind === "schema" ? schema.replace('"openapi": "3.1.0"', '"openapi": "3.1.1"') : schema);
  // Avoid depending on a particular FastAPI OpenAPI minor version for the deliberate edit.
  if (kind === "schema") {
    const changed = JSON.parse(schema); changed.info.title = "Deliberately changed synthetic schema";
    await writeFile(schemaPath, JSON.stringify(changed, null, 2) + "\n");
  }
  await writeFile(typesPath, kind === "types" ? types + "// deliberate drift\n" : types);
  const result = check();
  if (result.status !== 1 || !result.stderr.includes("contract_drift")) throw new Error(`negative_${kind}_check_failed`);
}
await writeFile(typesPath, types);
await writeFile(path.join(directory, "src", "contract-types.ts"), await readFile(path.join(root, "frontend", "src", "contract-types.ts")));
const config = path.join(directory, "tsconfig.json");
await writeFile(config, JSON.stringify({ compilerOptions: { target: "ES2022", module: "ESNext", moduleResolution: "bundler", strict: true, noEmit: true, skipLibCheck: true, types: [] }, include: ["src"] }));
const compile = () => spawnSync(process.execPath, [path.join(root, "frontend", "node_modules", "typescript", "bin", "tsc"), "--project", config], { encoding: "utf8", windowsHide: true });
if (compile().status !== 0) throw new Error("negative_type_baseline_failed");
const numeric = types.replace(/(KnownValue: \{[\s\S]*?value:) string;/, "$1 number;");
if (numeric === types) throw new Error("numeric_mutation_missing");
await writeFile(typesPath, numeric);
const failed = compile();
if (failed.status !== 2 || !failed.stdout.includes("Unused '@ts-expect-error'")) throw new Error("numeric_drift_not_detected");
console.log("Negative checks passed: changed schema, generated artifact and numeric book-value type each rejected.");
