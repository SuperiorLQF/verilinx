import {useViewport} from '@xyflow/react';
import type {WireDraft} from './routing';
import {polylinePath} from './routing';

export function WirePreview({wire}:{wire:WireDraft|null}) {
  const {x,y,zoom}=useViewport();
  if(!wire)return null;
  const screen=(p:{x:number;y:number})=>({x:x+p.x*zoom,y:y+p.y*zoom});
  return <svg className="wire-preview" aria-hidden="true"><path d={polylinePath(screen(wire.start),wire.points.map(screen),screen(wire.cursor))}/>{wire.points.map((p,i)=><circle key={i} cx={screen(p).x} cy={screen(p).y} r={3}/>)}<circle cx={screen(wire.start).x} cy={screen(wire.start).y} r={4}/></svg>;
}
