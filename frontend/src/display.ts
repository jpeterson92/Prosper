/** Presentation only. Authoritative values remain strings and are never rewritten. */
export function decimalDisplay(value: string, rounded: boolean, places = 2): string {
  if (!Number.isInteger(places) || places < 0 || places > 12) throw new Error("invalid_display_precision");
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value);
  if (!match) return value;
  let whole = match[2]!;
  let fraction = match[3] ?? "";
  let negative = match[1] === "-";
  if (rounded) {
    let scaled = BigInt(whole + fraction.slice(0, places).padEnd(places, "0"));
    const discarded = fraction.slice(places);
    const first = discarded[0] ?? "0";
    if (first > "5" || (first === "5" && (/[1-9]/.test(discarded.slice(1)) || scaled % 2n === 1n))) scaled += 1n;
    const text = scaled.toString().padStart(places + 1, "0");
    whole = places ? text.slice(0, -places) : text;
    fraction = places ? text.slice(-places) : "";
    if (scaled === 0n) negative = false;
  }
  return `${negative ? "-" : ""}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${fraction ? "." + fraction : ""}`;
}

export function locationText(path: readonly (string | number)[]): string {
  return path.length ? path.map((part) => typeof part === "number" ? `[${part}]` : part).join(" / ") : "Bundle root";
}

/** Compact display with an explicit sign when a nonzero value rounds to zero. */
export function compactValue(value:string|number,kind:"number"|"money"|"weight"="number",precision?:number):string {
  const raw=String(value);
  const places=precision??(kind==="number"?4:2);
  let display=kind==="weight"&&typeof value==="number"?(value*100).toLocaleString(undefined,{maximumFractionDigits:2})+"%":decimalDisplay(raw,true,places);
  if((kind==="weight"?Number(value)!==0&&Number(display.replace("%", ""))===0:/[1-9]/.test(raw)&&/^0(?:\.0*)?$/.test(display.replaceAll(",",""))))display=`${raw.startsWith("-")?">-":"<"}${places===0?"1":"0."+"0".repeat(places-1)+"1"}${kind==="weight"?"%":""}`;
  if(kind==="number"&&display.includes("."))display=display.replace(/(\.\d*?)0+$/,"$1").replace(/\.$/,"");
  return display;
}

/** Exact decimal shift for a display preview; the supplied fraction is never changed. */
export function percentPreview(raw:string):string {
  const match=/^(-?)(\d+)(?:\.(\d+))?$/.exec(raw);
  if(!match)return "Enter a decimal fraction";
  const fraction=match[3]??"",digits=match[2]!+fraction.padEnd(2,"0"),point=match[2]!.length+2;
  return decimalDisplay(`${match[1]}${digits.slice(0,point)}${digits.length>point?"."+digits.slice(point):""}`,true,4).replace(/(\.\d*?)0+$/,"$1").replace(/\.$/,"")+"%";
}
