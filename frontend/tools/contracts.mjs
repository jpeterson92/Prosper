import openapiTS, { astToString } from "openapi-typescript";
import ts from "typescript";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { runtime, root } from "./runtime.mjs";

const server = await runtime();
try {
  const token = await server.session();
  const response = await fetch(`${server.origin}/openapi.json`, {
    headers: { Origin: server.origin, Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("schema_unavailable");
  const schema = await response.json();
  const json = JSON.stringify(schema, null, 2) + "\n";
  const generated = "/** Generated from the protected running API. Do not edit. */\n" + astToString(await openapiTS(schema, {
    // OpenAPI binary strings denote bytes on the wire, not JSON or UTF-16 text.
    transform(value) {
      if (value.type === "string" && (value.format === "binary" || value.contentMediaType === "application/octet-stream")) {
        return ts.factory.createTypeReferenceNode("Uint8Array", [ts.factory.createTypeReferenceNode("ArrayBuffer")]);
      }
    },
  }));
  const override = process.env.PROSPER_CONTRACT_CHECK_ROOT;
  if (override && (!path.isAbsolute(override) || !path.relative(path.join(root, ".local"), override).startsWith("contract-negative-"))) {
    throw new Error("invalid_contract_check_root");
  }
  if (override && process.argv.includes("--write")) throw new Error("check_only_override");
  const base = override ?? path.join(root, "frontend");
  const directory = path.join(base, "src", "generated");
  const contract = path.join(base, "openapi.json");
  const types = path.join(directory, "api.ts");
  if (process.argv.includes("--write")) {
    await mkdir(directory, { recursive: true });
    await writeFile(contract, json);
    await writeFile(types, generated);
    console.log("Actual protected OpenAPI and generated types written.");
  } else {
    if (await readFile(contract, "utf8") !== json || await readFile(types, "utf8") !== generated) {
      throw new Error("contract_drift");
    }
    console.log("Actual protected OpenAPI and generated client contract match.");
  }
} finally { await server.stop(); }
