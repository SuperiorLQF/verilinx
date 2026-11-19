import type {Point,PortSide} from './api.js';

export type PortClick = {nodeId:string;portId:string;role:'source'|'target';client:Point;side?:PortSide};
export type PortEndpoint = {point:Point;side:PortSide};
export type WireDraft = {source:string;sourcePort:string;start:Point;sourceSide:PortSide;points:Point[];cursor:Point;edgeId?:string;target?:string;targetPort?:string};
export const MAX_BENDS=256;
const EPS=1e-9;
export const samePoint=(a:Point,b:Point)=>Math.abs(a.x-b.x)<EPS&&Math.abs(a.y-b.y)<EPS;
const horizontal=(side:PortSide)=>side==='left'||side==='right';
export function polylinePath(start:Point,points:Point[],end:Point) {
  return `M ${start.x} ${start.y}`+[...points,end].map(p=>` L ${p.x} ${p.y}`).join('');
}
/** The moving leg is always horizontal or vertical. Shift selects the other axis. */
export function routePoint(origin:Point,point:Point,_zoom=1,invert=false):Point {
  const alongX=(Math.abs(point.x-origin.x)>=Math.abs(point.y-origin.y))!==invert;
  return alongX?{x:point.x,y:origin.y}:{x:origin.x,y:point.y};
}
export function appendBend(points:Point[],start:Point,point:Point):Point[] {
  return points.length>=MAX_BENDS||samePoint(points.at(-1)??start,point)?points:[...points,point];
}
/** Rectify local legs only; no obstacle routing and no changes to module coordinates. */
export function orthogonalPoints(start:Point,points:Point[],end:Point,sourceSide:PortSide='right',targetSide:PortSide='left',tolerance=Infinity):Point[] {
  const result:Point[]=[];
  const push=(p:Point)=>{if(!samePoint(result.at(-1)??start,p))result.push({...p});};
  let previous=start,alongX=horizontal(sourceSide);
  for(const point of points) {
    if(Math.abs(previous.x-point.x)>EPS&&Math.abs(previous.y-point.y)>EPS) {
      const corner=alongX?{x:point.x,y:previous.y}:{x:previous.x,y:point.y};push(corner);previous=corner;
    }
    if(!samePoint(previous,point)){alongX=Math.abs(previous.y-point.y)<EPS;push(point);previous=point;}
  }
  if(!result.length) {
    if(Math.abs(start.x-end.x)<EPS||Math.abs(start.y-end.y)<EPS)return [];
    const sourceX=horizontal(sourceSide),targetX=horizontal(targetSide);
    if(sourceX&&targetX){const x=(start.x+end.x)/2;return [{x,y:start.y},{x,y:end.y}];}
    if(!sourceX&&!targetX){const y=(start.y+end.y)/2;return [{x:start.x,y},{x:end.x,y}];}
    return [sourceX?{x:end.x,y:start.y}:{x:start.x,y:end.y}];
  }
  const last=result.at(-1)!,before=result.length>1?result.at(-2)!:start,targetX=horizontal(targetSide);
  if(!samePoint(last,end)) {
    if(targetX&&Math.abs(last.y-end.y)>EPS) {
      if(Math.abs(last.y-end.y)<=tolerance&&Math.abs(before.x-last.x)<EPS)result[result.length-1]={x:last.x,y:end.y};
      else push({x:last.x,y:end.y});
    } else if(!targetX&&Math.abs(last.x-end.x)>EPS) {
      if(Math.abs(last.x-end.x)<=tolerance&&Math.abs(before.y-last.y)<EPS)result[result.length-1]={x:end.x,y:last.y};
      else push({x:end.x,y:last.y});
    }
  }
  // Keep collinear waypoints that continue forward. Drop a tip when the
  // next segment retraces it, including when the target lies on that segment.
  const clean:Point[]=[start];
  for(const p of [...result,end]) {
    while(clean.length>1) {
      const a=clean.at(-2)!,b=clean.at(-1)!;
      const reversesX=Math.abs(a.y-b.y)<EPS&&Math.abs(b.y-p.y)<EPS&&(b.x-a.x)*(p.x-b.x)<0;
      const reversesY=Math.abs(a.x-b.x)<EPS&&Math.abs(b.x-p.x)<EPS&&(b.y-a.y)*(p.y-b.y)<0;
      if(!reversesX&&!reversesY)break;
      clean.pop();
    }
    if(!samePoint(clean.at(-1)!,p))clean.push(p);
  }
  return clean.slice(1,-1);
}
/** Drag a corner by propagating the affected row/column, keeping endpoints fixed. */
export function moveBend(start:Point,points:Point[],end:Point,index:number,desired:Point):Point[] {
  const vertices=[start,...points,end].map(p=>({...p})),original=[start,...points,end],at=index+1;
  if(at<1||at>=vertices.length-1)return points;
  for(const coordinate of ['x','y'] as const) {
    let left=at,right=at;
    while(left>0&&Math.abs(original[left-1][coordinate]-original[left][coordinate])<EPS)left--;
    while(right<vertices.length-1&&Math.abs(original[right+1][coordinate]-original[right][coordinate])<EPS)right++;
    const value=left===0?start[coordinate]:right===vertices.length-1?end[coordinate]:desired[coordinate];
    for(let i=left;i<=right;i++)vertices[i][coordinate]=value;
  }
  return vertices.slice(1,-1);
}
export function insertBend(start:Point,points:Point[],end:Point,point:Point):Point[] {
  if(points.length>=MAX_BENDS)return points;
  const vertices=[start,...points,end];let best=Infinity,index=0,nearest=point;
  for(let i=0;i<vertices.length-1;i++) {
    const a=vertices[i],b=vertices[i+1],dx=b.x-a.x,dy=b.y-a.y;
    const t=Math.max(0,Math.min(1,((point.x-a.x)*dx+(point.y-a.y)*dy)/(dx*dx+dy*dy||1)));
    const candidate=dx===0?{x:a.x,y:Math.max(Math.min(a.y,b.y),Math.min(Math.max(a.y,b.y),point.y))}:dy===0?{x:Math.max(Math.min(a.x,b.x),Math.min(Math.max(a.x,b.x),point.x)),y:a.y}:{x:a.x+t*dx,y:a.y+t*dy};
    const distance=(point.x-candidate.x)**2+(point.y-candidate.y)**2;
    if(distance<best){best=distance;index=i;nearest=candidate;}
  }
  return [...points.slice(0,index),nearest,...points.slice(index)];
}
/** Match React Flow's actual edge anchor, not the centre of the handle hit area. */
type Handle={id?:string|null;x:number;y:number;width:number;height:number;position:string};
export function handleEndpoint(node:{internals:{positionAbsolute:Point;handleBounds?:{source?:Handle[]|null;target?:Handle[]|null}}},portId:string,role:'source'|'target'):PortEndpoint|null {
  const handle=node.internals.handleBounds?.[role]?.find(h=>h.id===portId);if(!handle)return null;
  const {x:ox,y:oy}=node.internals.positionAbsolute,{x,y,width,height}=handle,side=handle.position as PortSide;
  return {side,point:{x:ox+x+(side==='left'?0:side==='right'?width:width/2),y:oy+y+(side==='top'?0:side==='bottom'?height:height/2)}};
}
