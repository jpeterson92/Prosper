/** Presentation only. Authoritative values remain strings and are never rewritten. */
export function decimalDisplay(value: string, rounded: boolean): string {
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value);
  if (!match) return value;
  let whole = match[2]!;
  let fraction = match[3] ?? "";
  let negative = match[1] === "-";
  if (rounded) {
    let scaled = BigInt(whole + fraction.slice(0, 2).padEnd(2, "0"));
    const discarded = fraction.slice(2);
    const first = discarded[0] ?? "0";
    if (first > "5" || (first === "5" && (/[1-9]/.test(discarded.slice(1)) || scaled % 2n === 1n))) scaled += 1n;
    const text = scaled.toString().padStart(3, "0");
    whole = text.slice(0, -2);
    fraction = text.slice(-2);
    if (scaled === 0n) negative = false;
  }
  return `${negative ? "-" : ""}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${fraction ? "." + fraction : ""}`;
}

export function locationText(path: readonly (string | number)[]): string {
  return path.length ? path.map((part) => typeof part === "number" ? `[${part}]` : part).join(" / ") : "Bundle root";
}
