export const COLORS={cyan:'#67d4f5',purple:'#a64cf7',pink:'#f35be7',green:'#18ee68',blue:'#3479ec'};
export const SHAPES={square:[[0,0],[1,0],[0,1],[1,1]],single:[[0,0]],tall:[[0,0],[0,1]],la:[[0,0],[1,0],[0,1]],lb:[[1,0],[0,1],[1,1]]};
export const INITIAL=[
 ['c1','cyan',1,0,'la'],['c2','cyan',1,1,'lb'],['p1','purple',4,0,'single'],
 ['p2','purple',0,1,'single'],['m1','pink',3,1,'square','v'],['p3','purple',5,1,'single'],
 ['p4','purple',1,3,'square','v'],['b1','blue',0,4,'single'],['b2','blue',5,4,'single'],
 ['g1','green',1,5,'square'],['g2','green',3,5,'square'],
 ['b3','blue',0,7,'tall'],['p5','purple',1,7,'square','v'],['m2','pink',3,7,'square','v'],['b4','blue',5,7,'tall']
];
// A reservoir holds finite runs of up to CAPACITY color runs. A color
// remains available until its current stock is exhausted; later runs stay in pipes.
export const CAPACITY=[2,1];
export const QUEUES=[['blue','green','cyan','cyan','purple','purple','purple','blue'],['pink','blue','green','pink','purple','purple','blue']];
export function fresh(){return {pieces:INITIAL.map(([id,color,x,y,shape,axis])=>({id,color,x,y,shape,axis:axis||'both',fill:0})),queues:QUEUES.map(q=>[...q]),moves:0,cleared:0};}
export function allowed(x,y){return Number.isInteger(x)&&Number.isInteger(y)&&y>=0&&y<9&&((x>=1&&x<=4)||((x===0||x===5)&&[1,4,5,7,8].includes(y)));}
export function cells(p){return SHAPES[p.shape].map(([x,y])=>[p.x+x,p.y+y]);}
export function canMove(s,id,dx,dy){const p=s.pieces.find(p=>p.id===id);if(!p||(!dx&&!dy)||!Number.isInteger(dx)||!Number.isInteger(dy)||p.axis==='v'&&dx)return false;
 if(dx&&dy)return false;
 const occupied=new Set(s.pieces.filter(q=>q.id!==id).flatMap(cells).map(([x,y])=>`${x},${y}`));
 const steps=Math.max(Math.abs(dx),Math.abs(dy));
 for(let i=1;i<=steps;i++)for(const [x,y]of cells(p)){const a=x+Math.sign(dx)*i,b=y+Math.sign(dy)*i;if(!allowed(a,b)||occupied.has(`${a},${b}`))return false;}
 return true;}
export function move(s,id,dx,dy){if(!canMove(s,id,dx,dy))return false;const p=s.pieces.find(p=>p.id===id);p.x+=dx;p.y+=dy;s.moves++;return true;}
// A reservoir spans two columns. Only a container cell directly against its
// bottom edge (board row zero) can open the outlet; air gaps never transmit sand.
export function sourceStock(s,side){const stock=[];let previous=null,runs=0;for(const color of s.queues[side]){if(color!==previous){if(runs===CAPACITY[side])break;runs++;previous=color;}stock.push(color);}return stock;}
export function sourceColors(s,side){return [...new Set(sourceStock(s,side))];}
export function receiver(s,side){
 const columns=side===0?[1,2]:[3,4];
 const touching=s.pieces.flatMap(p=>{const contact=cells(p).find(([x,y])=>y===0&&columns.includes(x));return contact?[{p,x:contact[0],y:0}]:[];});
 return touching.find(r=>sourceColors(s,side).includes(r.p.color))||touching[0]||null;
}
export function ready(s,side){const r=receiver(s,side);return r&&sourceColors(s,side).includes(r.p.color)?r:null;}
export function finish(s,id,side){const r=ready(s,side);if(!r||r.p.id!==id)return false;s.pieces=s.pieces.filter(p=>p.id!==id);s.queues[side].splice(s.queues[side].indexOf(r.p.color),1);s.cleared++;return true;}
export function legalMoves(s){const result=[];for(const p of s.pieces)for(const [dx,dy]of [[1,0],[-1,0],[0,1],[0,-1]])for(let distance=1;distance<=8;distance++){if(!canMove(s,p.id,dx*distance,dy*distance))break;result.push({id:p.id,dx:dx*distance,dy:dy*distance});}return result;}
export function key(s){return JSON.stringify([s.pieces.map(p=>[p.id,p.x,p.y]),s.queues]);}
export function settle(s){const removed=[];let changed=true;while(changed){changed=false;for(let side=0;side<2;side++){const r=ready(s,side);if(r){removed.push(r.p.id);finish(s,r.p.id,side);changed=true;}}}return removed;}

// Weighted A* finds a move toward the next fill; geometry and stock use the
// same rules as play. This also handles the initial multi-move rearrangement.
export function findHint(state,limit=7000){
 const root=structuredClone(state);settle(root);const size=root.pieces.length;
 function heuristic(s){const active=[sourceColors(s,0),sourceColors(s,1)];let best=1000;
  for(const p of s.pieces)for(let side=0;side<2;side++)if(active[side].includes(p.color))for(let x=0;x<6;x++){
   if(p.axis==='v'&&x!==p.x)continue;const target={...p,x,y:0},positions=cells(target),columns=side===0?[1,2]:[3,4];
   if(!positions.every(([a,b])=>allowed(a,b))||!positions.some(([a,b])=>b===0&&columns.includes(a)))continue;
   const occupied=new Set(s.pieces.filter(q=>q.id!==p.id).flatMap(cells).map(([a,b])=>`${a},${b}`));
   const blocked=positions.filter(([a,b])=>occupied.has(`${a},${b}`)).length;
   best=Math.min(best,Math.abs(p.x-x)+p.y+blocked*4);
  }return best;
 }
 const heap=[];function push(entry){heap.push(entry);let i=heap.length-1;while(i>0){const parent=(i-1)>>1;if(heap[parent].priority<=entry.priority)break;heap[i]=heap[parent];i=parent;}heap[i]=entry;}
 function pop(){const first=heap[0],last=heap.pop();if(heap.length){let i=0;while(i*2+1<heap.length){let child=i*2+1;if(child+1<heap.length&&heap[child+1].priority<heap[child].priority)child++;if(heap[child].priority>=last.priority)break;heap[i]=heap[child];i=child;}heap[i]=last;}return first;}
 const seen=new Map([[key(root),0]]);push({s:root,g:0,first:null,priority:heuristic(root)*2});let count=0;
 while(heap.length&&count<limit){const current=pop();if(current.g!==seen.get(key(current.s)))continue;count++;
  for(const m of legalMoves(current.s)){const next=structuredClone(current.s);move(next,m.id,m.dx,m.dy);settle(next);const first=current.first||m;if(next.pieces.length<size)return first;
   const k=key(next),g=current.g+1;if(g>=(seen.get(k)??Infinity))continue;seen.set(k,g);push({s:next,g,first,priority:g+heuristic(next)*2});}
 }return null;
}
