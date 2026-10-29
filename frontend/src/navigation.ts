import type { Page, Stage } from "./app-shell";

export type RecordSelection = {kind:"run"|"worksheet";id:string};
export type Location = {page:Page;stage:Stage;record?:RecordSelection};
export function readLocation():Location {
  const [page,stage,encoded]=window.location.hash.slice(1).split("/");
  let record:RecordSelection|undefined;
  if(page==="worksheets"&&(stage==="run"||stage==="worksheet")&&encoded){try{record={kind:stage,id:decodeURIComponent(encoded)};}catch{/* Invalid record address stays in the library. */}}
  return {page:["overview","holdings","analysis","worksheets","settings"].includes(page??"")?page as Page:"overview",stage:["benchmark","review","proposals"].includes(stage??"")?stage as Stage:"benchmark",...(record?{record}:{})};
}
export function writeLocation(value:Location) {
  const hash=`#${value.page}${value.page==="analysis"?`/${value.stage}`:value.page==="worksheets"&&value.record?`/${value.record.kind}/${encodeURIComponent(value.record.id)}`:""}`;
  if(window.location.hash!==hash)window.history.pushState(null,"",hash);
}
