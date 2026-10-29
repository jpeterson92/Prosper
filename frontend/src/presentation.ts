import type { Run } from "./client";

export function recordStatus(run:Run):string {
  if(run.status==="running")return "In progress";
  if(run.status==="partial")return "Saved review";
  return run.status.replaceAll("_"," ");
}
export function readableDate(value:string):string {
  // Preserve the supplied calendar date; do not shift a date across time zones.
  return value.slice(0,10);
}
export function warningGroups(values:readonly string[]) {
  const groups=new Map<string,string[]>();
  for(const value of values) {
    const lower=value.toLowerCase();
    const group=lower.includes("exclusion")||lower.includes("excluded")?"Coverage and exclusions":lower.includes("broker")||lower.includes("execution")||lower.includes("funding")||lower.includes("refreshed")?"Manual execution and funding":lower.includes("risk")||lower.includes("model")||lower.includes("calibrat")?"Risk and model limitations":"Estimate assumptions";
    groups.set(group,[...(groups.get(group)??[]),value]);
  }
  return [...groups];
}
