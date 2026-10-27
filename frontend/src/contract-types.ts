/** Supplied decimals stay text across the generated HTTP boundary. */
import type { components, paths } from "./generated/api";
type Decimal = components["schemas"]["DecimalFact"];
type Upload = components["schemas"]["Upload"];
// @ts-expect-error Supplied decimal values cannot become JS numbers.
const numeric: Decimal["value"] = 319;
// @ts-expect-error The current upload format is a closed literal.
const version: Upload["version"] = "other";
// @ts-expect-error Recovery uploads are bytes, never JSON serialization.
const text: NonNullable<paths["/api/v1/restore"]["post"]["requestBody"]>["content"]["application/octet-stream"] = "json";
void [numeric, version, text];
