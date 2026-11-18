import type { Point } from './api.js';

export type PortClick = {nodeId:string;portId:string;role:'source'|'target';client:Point};
export type WireDraft = {source:string;sourcePort:string;start:Point;points:Point[];cursor:Point;edgeId?:string;target?:string;targetPort?:string};
export const MAX_BENDS = 256;
export const samePoint = (a:Point,b:Point) => Math.abs(a.x-b.x)<0.001 && Math.abs(a.y-b.y)<0.001;
export function polylinePath(start:Point,points:Point[],end:Point) {
  return `M ${start.x} ${start.y}` + [...points,end].map(p=>` L ${p.x} ${p.y}`).join('');
}
/** Snap near horizontal/vertical, or constrain with Shift; never insert hidden bends. */
export function routePoint(origin:Point,point:Point,zoom:number,constrain=false):Point {
  let {x,y}=point;
  const dx=Math.abs(x-origin.x),dy=Math.abs(y-origin.y),tolerance=6/Math.max(zoom,.01);
  if(constrain || Math.min(dx,dy)<=tolerance) {if(dx<dy)x=origin.x;else y=origin.y;}
  return {x:Number(x.toFixed(3)),y:Number(y.toFixed(3))};
}
export function appendBend(points:Point[],start:Point,point:Point):Point[] {
  return points.length>=MAX_BENDS || samePoint(points.at(-1)??start,point) ? points : [...points,point];
}
export function insertBend(start:Point,points:Point[],end:Point,point:Point):Point[] {
  if(points.length>=MAX_BENDS)return points;
  const vertices=[start,...points,end];let best=Infinity,index=0;
  for(let i=0;i<vertices.length-1;i++) {
    const a=vertices[i],b=vertices[i+1],dx=b.x-a.x,dy=b.y-a.y;
    const t=Math.max(0,Math.min(1,((point.x-a.x)*dx+(point.y-a.y)*dy)/(dx*dx+dy*dy||1)));
    const distance=(point.x-a.x-t*dx)**2+(point.y-a.y-t*dy)**2;
    if(distance<best){best=distance;index=i;}
  }
  return [...points.slice(0,index),point,...points.slice(index)];
}
