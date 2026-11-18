export const COLORS={cyan:'#27dcf1',purple:'#a64cf7',pink:'#f35be7',green:'#18ee68',blue:'#3ca8ff'};
export const SHAPES={square:[[0,0],[1,0],[0,1],[1,1]],single:[[0,0]],tall:[[0,0],[0,1]],la:[[0,0],[1,0],[0,1]],lb:[[1,0],[0,1],[1,1]]};
export const INITIAL=[
 ['c1','cyan',1,0,'la'],['c2','cyan',1,1,'lb'],['p1','purple',4,0,'single'],
 ['p2','purple',0,1,'single'],['m1','pink',3,1,'square','v'],['p3','purple',5,1,'single'],
 ['p4','purple',1,3,'square','v'],['b1','blue',0,4,'single'],['b2','blue',5,4,'single'],
 ['g1','green',1,5,'square'],['g2','green',3,5,'square'],
 ['b3','blue',0,7,'tall'],['p5','purple',1,7,'square','v'],['m2','pink',3,7,'square','v'],['b4','blue',5,7,'tall']
];
// Each queue has one dose for each container in the reference solution.
export const QUEUES=[['cyan','purple','cyan','green','purple','purple','blue','blue'],['purple','pink','blue','green','pink','purple','blue']];
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
export function receiver(s,side){const col=side===0?1:4;return s.pieces.flatMap(p=>cells(p).filter(([x])=>x===col).map(([,y])=>({p,y}))).sort((a,b)=>a.y-b.y)[0]||null;}
export function ready(s,side){const r=receiver(s,side);return r&&r.p.color===s.queues[side][0]?r:null;}
export function finish(s,id,side){const r=ready(s,side);if(!r||r.p.id!==id)return false;s.pieces=s.pieces.filter(p=>p.id!==id);s.queues[side].shift();s.cleared++;return true;}
export function legalMoves(s){return s.pieces.flatMap(p=>[[1,0],[-1,0],[0,1],[0,-1]].filter(([dx,dy])=>canMove(s,p.id,dx,dy)).map(([dx,dy])=>({id:p.id,dx,dy})));}
export function key(s){return JSON.stringify([s.pieces.map(p=>[p.id,p.x,p.y]),s.queues]);}
export function settle(s){const removed=[];let changed=true;while(changed){changed=false;for(let side=0;side<2;side++){const r=ready(s,side);if(r){removed.push(r.p.id);finish(s,r.p.id,side);changed=true;}}}return removed;}
