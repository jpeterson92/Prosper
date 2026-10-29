import type { Page, Stage } from "./app-shell";

export type Location = {page:Page;stage:Stage};
export function readLocation():Location {
  const [page,stage]=window.location.hash.slice(1).split("/");
  return {page:["overview","holdings","analysis","worksheets","settings"].includes(page??"")?page as Page:"overview",stage:["benchmark","review","proposals"].includes(stage??"")?stage as Stage:"benchmark"};
}
export function writeLocation(value:Location) {
  const hash=`#${value.page}${value.page==="analysis"?`/${value.stage}`:""}`;
  if(window.location.hash!==hash)window.history.pushState(null,"",hash);
}
