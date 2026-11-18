import {useCallback,useEffect,useRef,useState,type Dispatch,type SetStateAction} from 'react';
import {connectionIssue} from './connections';
import {uid,type Edge,type Point,type Project} from './api';
import {appendBend,MAX_BENDS,routePoint,orthogonalPoints,type PortEndpoint,type PortClick,type WireDraft} from './routing';

type Pointer = {clientX:number;clientY:number;shiftKey:boolean};
export function useManualWiring(project:Project|null,setProject:Dispatch<SetStateAction<Project|null>>,disabled:boolean,
  toFlow:(point:Point)=>Point,getZoom:()=>number,resolvePort:(node:string,port:string,role:'source'|'target')=>PortEndpoint|null,setStatus:(value:string)=>void,setError:(value:string)=>void) {
  const [wire,setWire]=useState<WireDraft|null>(null),current=useRef(wire),projectRef=useRef(project),disabledRef=useRef(disabled);
  projectRef.current=project;disabledRef.current=disabled;
  const change=useCallback((next:WireDraft|null)=>{current.current=next;setWire(next);},[]);
  const cancel=useCallback(()=>{if(current.current){change(null);setStatus('已取消布线，工程保持不变');}},[change,setStatus]);
  const undo=useCallback(()=>{if(current.current){const next={...current.current,points:current.current.points.slice(0,-1)};change(next);setStatus(`布线中 · ${next.points.length} 个转折点`);}},[change,setStatus]);
  useEffect(()=>{if(disabled)cancel();},[disabled,cancel]);
  useEffect(()=>{cancel();},[project?.inputs,cancel]);
  useEffect(()=>{
    const key=(event:KeyboardEvent)=>{
      if(!current.current||(event.target as HTMLElement)?.closest('input,textarea,select,[contenteditable=true]'))return;
      if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();cancel();}
      else if(event.key==='Backspace'||event.key==='Delete'){
        event.preventDefault();event.stopImmediatePropagation();undo();
      }
    };
    window.addEventListener('keydown',key,true);return()=>window.removeEventListener('keydown',key,true);
  },[undo,cancel]);
  const portClick=useCallback((port:PortClick)=>{
    const p=projectRef.current;if(!p||disabledRef.current)return;
    if(port.role==='source'){
      const endpoint=resolvePort(port.nodeId,port.portId,'source'),point=endpoint?.point??toFlow(port.client);change({source:port.nodeId,sourcePort:port.portId,start:point,sourceSide:endpoint?.side??port.side??'right',points:[],cursor:point});setError('');setStatus('布线中 · 单击画布放置转折点，单击输入端口完成');return;
    }
    const draft=current.current;if(!draft){setError('请先点击输出端口开始布线。');return;}
    if(draft.edgeId&&(port.nodeId!==draft.target||port.portId!==draft.targetPort)){setError('重画路径时请点击原来的输入端口；Esc 可以取消。');return;}
    const c={source:draft.source,sourceHandle:draft.sourcePort,target:port.nodeId,targetHandle:port.portId};
    const issue=connectionIssue({...p,edges:p.edges.filter(e=>e.id!==draft.edgeId)},c);
    if(issue){setError(issue);setStatus('布线未完成 · 可继续选择输入端口');return;}
    const endpoint=resolvePort(port.nodeId,port.portId,'target'),target=endpoint?.point??toFlow(port.client);
    const points=orthogonalPoints(draft.start,draft.points,target,draft.sourceSide,endpoint?.side??port.side??'left',8/Math.max(getZoom(),.01));
    if(points.length>MAX_BENDS){setError('补齐直角后转折点过多，请撤回部分点后再连接。');return;}
    const edge:Edge={id:draft.edgeId??uid(),source:draft.source,target:port.nodeId,sourcePort:draft.sourcePort,targetPort:port.portId,points};
    setProject(previous=>previous?{...previous,edges:draft.edgeId?previous.edges.map(e=>e.id===draft.edgeId?{...e,points}:e):[...previous.edges,edge]}:previous);
    change(null);setError('');setStatus(`手动布线已保存 · ${points.length} 个转折点`);
  },[toFlow,resolvePort,getZoom,change,setError,setStatus,setProject]);
  const pointerMove=(event:Pointer)=>{
    const draft=current.current;if(!draft)return;
    change({...draft,cursor:routePoint(draft.points.at(-1)??draft.start,toFlow({x:event.clientX,y:event.clientY}),getZoom(),event.shiftKey)});
  };
  const placeBend=(event:Pointer)=>{
    const draft=current.current;if(!draft)return;
    if(draft.points.length>=MAX_BENDS){setError(`每条连线最多 ${MAX_BENDS} 个转折点。`);return;}
    const point=routePoint(draft.points.at(-1)??draft.start,toFlow({x:event.clientX,y:event.clientY}),getZoom(),event.shiftKey);
    const points=appendBend(draft.points,draft.start,point);change({...draft,points,cursor:point});setStatus(`布线中 · ${points.length} 个转折点 · Backspace 撤回，Esc 取消`);
  };
  const redraw=(edge:Edge,start:Point)=>{if(disabledRef.current)return;const endpoint=resolvePort(edge.source,edge.sourcePort,'source');start=endpoint?.point??start;change({edgeId:edge.id,source:edge.source,sourcePort:edge.sourcePort,target:edge.target,targetPort:edge.targetPort,sourceSide:endpoint?.side??'right',start,cursor:start,points:[]});setError('');setStatus('重画路径 · 点击转折点，最后点击原输入端口完成；Esc 保留原线');};
  return {wire,portClick,pointerMove,placeBend,cancel,undo,redraw};
}
