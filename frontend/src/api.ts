export type Shape = {packed:number[][];unpacked:number[][];atom_width:number;signed?:boolean};
export type Port = {name:string;shape:Shape;role:'source'|'target';type?:string};
export type PortSide = 'left'|'right'|'top'|'bottom';
export type PortAnchor = {side:PortSide;offset:number};
export type Block = {portLayout?:Record<string,PortAnchor>;id:string;kind:string;name:string;module?:string;overrides?:Record<string,string>;count?:string;view?:string;position:{x:number;y:number};ports?:Port[];expression?:string;analysis?:{count:number;homogeneous?:boolean;variants?:{ports:{name:string;direction:string;shape:Shape;type:string}[]}[];resolved:Record<string,string>;parameters:{name:string;literal:string;display:string}[];ports:{name:string;direction:string;shape:Shape;type:string}[]}};
export type Edge = {id:string;source:string;target:string;sourcePort:string;targetPort:string};
export type Project = {schema:number;name:string;parameters:string;inputs:{entry:string;files:Record<string,string>};modules:{name:string;declaration:string}[];nodes:Block[];edges:Edge[];viewport?:{x:number;y:number;zoom:number;saved?:boolean}};
export async function api(path:string,body?:unknown){const r=await fetch('/api/'+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');return d;}
export function ports(n:Block):Port[]{return n.kind==='module'?(n.analysis?.homogeneous===false?[]:n.analysis?.ports||[]).map(p=>({...p,role:p.direction==='Out'?'source':'target',shape:{...p.shape,unpacked:(n.analysis!.count>1?[[0,n.analysis!.count-1]]:[]).concat(p.shape.unpacked)}})):n.ports||[];}
export function width(s:Shape){return [...s.packed,...s.unpacked].reduce((n,[a,b])=>n*(Math.abs(a-b)+1),s.atom_width||1);}
export function shapeText(s:Shape){return (s.unpacked.length?s.unpacked.map(([a,b])=>`[${a}:${b}]`).join('')+' × ':'')+(s.packed.length?s.packed.map(([a,b])=>`[${a}:${b}]`).join(''):String(s.atom_width||1));}
export function vector(w:number,lanes=0):Shape{return {packed:w>1?[[w-1,0]]:[],unpacked:lanes?[[0,lanes-1]]:[],atom_width:1};}
export function download(name:string,text:string){const u=URL.createObjectURL(new Blob([text],{type:'text/plain'}));const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),5000);}

export function lanePorts(n:Block,i:number):Port[]{return (n.analysis?.variants?.[i]?.ports||n.analysis?.ports||[]).map(p=>({...p,role:p.direction==='Out'?'source':'target'}));}

export function uid(){return globalThis.crypto?.randomUUID?.()||'n_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2);}
