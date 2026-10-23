/** Compile-time regressions against the actual generated schema. No runtime arithmetic. */
import type { components, paths } from "./generated/api";
type Known = components["schemas"]["KnownValue"];
type Unknown = components["schemas"]["UnknownValue"];
type Commit = components["schemas"]["CommitRequest"];

// @ts-expect-error Book values must never become JS numbers.
const numeric: Known["value"] = 319;
// @ts-expect-error Unknown values are null, never a fabricated zero.
const zero: Unknown["value"] = 0;
// @ts-expect-error API version is a closed literal.
const version: Commit["schema_version"] = "other";
// @ts-expect-error Original uploads are bytes, not JSON/text serialization.
const textUpload: NonNullable<paths["/api/v1/previews"]["post"]["requestBody"]>["content"]["application/octet-stream"] = "json";
void [numeric, zero, version, textUpload];
