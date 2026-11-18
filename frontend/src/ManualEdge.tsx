import {BaseEdge,EdgeLabelRenderer,useReactFlow,useViewport,type Edge,type EdgeProps} from '@xyflow/react';
import type {Point} from './api';
import {insertBend,polylinePath} from './routing';

export type ManualFlowEdge = Edge<{points:Point[];disabled:boolean;onPointsChange:(id:string,points:Point[])=>void},'manual'>;
export function ManualEdge({id,sourceX,sourceY,targetX,targetY,data,selected,style}:EdgeProps<ManualFlowEdge>) {
  const {screenToFlowPosition}=useReactFlow();
  const {zoom}=useViewport();
  const points=data?.points??[],start={x:sourceX,y:sourceY},end={x:targetX,y:targetY};
  return <>
    <g onDoubleClick={event=>{if(data?.disabled)return;event.stopPropagation();data?.onPointsChange(id,insertBend(start,points,end,screenToFlowPosition({x:event.clientX,y:event.clientY})));}}>
      <BaseEdge id={id} path={polylinePath(start,points,end)} style={style} interactionWidth={18}/>
    </g>
    {selected&&!data?.disabled&&<EdgeLabelRenderer>{points.map((point,index)=><button key={index} className="wire-bend nodrag nopan" aria-label={`转折点 ${index+1}`} title="拖动调整；Alt+单击或 Delete 删除转折点；方向键微调"
      style={{transform:`translate(-50%,-50%) translate(${point.x}px,${point.y}px)`,width:24/zoom,height:24/zoom,'--bend-inverse':1/zoom} as React.CSSProperties}
      onPointerDown={event=>{event.preventDefault();event.stopPropagation();if(event.altKey){data?.onPointsChange(id,points.filter((_,i)=>i!==index));return;}event.currentTarget.setPointerCapture(event.pointerId);}}
      onPointerMove={event=>{if(!event.currentTarget.hasPointerCapture(event.pointerId))return;event.stopPropagation();const next=screenToFlowPosition({x:event.clientX,y:event.clientY});data?.onPointsChange(id,points.map((p,i)=>i===index?next:p));}}
      onPointerUp={event=>{event.stopPropagation();if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);}}
      onClick={event=>event.stopPropagation()} onDoubleClick={event=>event.stopPropagation()}
      onKeyDown={event=>{if(['Delete','Backspace'].includes(event.key)){event.preventDefault();event.stopPropagation();data?.onPointsChange(id,points.filter((_,i)=>i!==index));}else if(event.key.startsWith('Arrow')){event.preventDefault();event.stopPropagation();const step=event.shiftKey?10:1;data?.onPointsChange(id,points.map((p,i)=>i!==index?p:{x:p.x+(event.key==='ArrowRight'?step:event.key==='ArrowLeft'?-step:0),y:p.y+(event.key==='ArrowDown'?step:event.key==='ArrowUp'?-step:0)}));}}}
    />)}</EdgeLabelRenderer>}
  </>;
}
