import { useViewport } from '@xyflow/react';
import type { Guide } from './arrange';

export function AlignmentGuides({ guides }: { guides: Guide[] }) {
  const { x, y, zoom } = useViewport();
  return <svg className="alignment-guides" aria-hidden="true">{guides.map(g => g.axis === 'x'
    ? <line key={g.axis} x1={g.coordinate * zoom + x} x2={g.coordinate * zoom + x} y1={g.start * zoom + y} y2={g.end * zoom + y}/>
    : <line key={g.axis} y1={g.coordinate * zoom + y} y2={g.coordinate * zoom + y} x1={g.start * zoom + x} x2={g.end * zoom + x}/>)}</svg>;
}
