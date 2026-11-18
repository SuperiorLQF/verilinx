import { useLayoutEffect, useRef, useState, type CSSProperties, type PointerEvent } from 'react';
import { Handle, Position, useUpdateNodeInternals, type NodeProps } from '@xyflow/react';
import { Box, GitBranch, Layers, Settings2, ArrowRight } from 'lucide-react';
import type { BlockNode } from './canvas-state';
import type { PortAnchor } from './api';
import { shapeText } from './api';
import { arrowAngle, blockPorts, blockWidth, projectToBorder, slideAnchor, type DisplayPort } from './port-layout';

const position = { left: Position.Left, right: Position.Right, top: Position.Top, bottom: Position.Bottom };
function anchorStyle(anchor: PortAnchor): CSSProperties {
  const vertical = anchor.side === 'left' || anchor.side === 'right';
  const x = vertical ? (anchor.side === 'left' ? '0%' : '100%') : anchor.offset * 100 + '%';
  const y = vertical ? anchor.offset * 100 + '%' : anchor.side === 'top' ? '0%' : '100%';
  return { left: x, top: y, '--anchor-x': x, '--anchor-y': y } as CSSProperties;
}

export function BlockView({ id, data, selected }: NodeProps<BlockNode>) {
  const block = data.block, frame = useRef<HTMLDivElement>(null);
  const layout = blockPorts(block), count = block.analysis?.count ?? 1;
  const updateInternals = useUpdateNodeInternals();
  const [preview, setPreview] = useState<{ id: string; anchor: PortAnchor } | null>(null);
  const moving = useRef<{ id: string; pointer: number; anchor: PortAnchor } | null>(null);
  const geometryKey = JSON.stringify([layout.height, [...layout.visible, ...layout.hidden].map(p => [p.id, p.role, p.anchor]), preview]);
  useLayoutEffect(() => { updateInternals(id); }, [id, geometryKey, updateInternals]);

  function start(event: PointerEvent<HTMLDivElement>, port: DisplayPort) {
    if(data.wiring){event.preventDefault();event.stopPropagation();return;}
    if (!event.shiftKey && !data.layoutMode) return;
    event.preventDefault(); event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    moving.current = { id: port.id, pointer: event.pointerId, anchor: port.anchor };
    setPreview({ id: port.id, anchor: port.anchor });
  }
  function move(event: PointerEvent<HTMLDivElement>) {
    const drag = moving.current;
    if (!drag || drag.pointer !== event.pointerId || !frame.current) return;
    event.preventDefault(); event.stopPropagation();
    drag.anchor = projectToBorder(event.clientX, event.clientY, frame.current.getBoundingClientRect());
    setPreview({ id: drag.id, anchor: drag.anchor });
  }
  function finish(event: PointerEvent<HTMLDivElement>, cancel = false) {
    const drag = moving.current;
    if (!drag || drag.pointer !== event.pointerId) return;
    event.preventDefault(); event.stopPropagation();
    moving.current = null;
    if (!cancel) data.onPortMove?.(id, drag.id, drag.anchor);
    setPreview(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }
  function renderPort(port: DisplayPort) {
    const anchor = preview?.id === port.id ? preview.anchor : port.anchor;
    const activate = (element:HTMLDivElement) => {
      const rect=element.getBoundingClientRect();
      data.onPortClick?.({nodeId:id,portId:port.id,role:port.role,side:anchor.side,client:{x:rect.left+rect.width/2,y:rect.top+rect.height/2}});
    };
    return <div className={'border-port side-' + anchor.side + (port.hidden ? ' hidden-port' : '')} key={port.id} aria-hidden={port.hidden || undefined}>
      <Handle id={port.id} type={port.role} position={position[anchor.side]}
        className={'arrow-handle nodrag nopan ' + port.role + (data.layoutMode ? ' arranging' : '')}
        style={anchorStyle(anchor)} role="button" tabIndex={port.hidden ? -1 : 0}
        aria-label={`${block.name}.${port.id} ${port.role === 'target' ? '输入' : '输出'}端口`}
        title={`${port.id} ${shapeText(port.shape)}\n点击端口开始 / 完成手动布线；Shift+拖动沿边框移动；Shift+方向键微调`}
        isConnectable={false} isConnectableStart={false} isConnectableEnd={false}
        onPointerDownCapture={event => start(event, port)} onPointerMove={move}
        onPointerUp={event => finish(event)} onPointerCancel={event => finish(event, true)}
        onMouseDownCapture={event => {event.preventDefault();event.stopPropagation();}}
        onClickCapture={event => {event.preventDefault();event.stopPropagation();if(!event.shiftKey&&!data.layoutMode&&!port.hidden)activate(event.currentTarget);}}
        onDoubleClick={event => event.stopPropagation()}
        onKeyDown={event => {
          if(!data.layoutMode&&!port.hidden&&['Enter',' '].includes(event.key)){event.preventDefault();event.stopPropagation();activate(event.currentTarget);return;}
          if(data.wiring)return;
          if (!event.shiftKey || !['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key)) return;
          event.preventDefault(); event.stopPropagation();
          data.onPortMove?.(id, port.id, slideAnchor(anchor, event.key === 'ArrowRight' || event.key === 'ArrowDown'));
        }}>
        <svg className="port-arrow" viewBox="0 0 24 24" aria-hidden="true" style={{ transform: `rotate(${arrowAngle(anchor.side, port.role)}deg)` }}><path d="M3 8H13V3L22 12L13 21V16H3Z"/></svg>
      </Handle>
      {!port.hidden && <span className={'border-label label-' + anchor.side} style={anchorStyle(anchor)}><b>{port.id}</b><small>{shapeText(port.shape)}</small></span>}
    </div>;
  }
  return <div ref={frame} className={`block perimeter-block ${selected ? 'selected' : ''} ${block.kind} ${count > 1 && !layout.expanded ? 'stacked' : ''} ${data.layoutMode ? 'port-layout-mode' : ''}`} style={{ width: blockWidth, height: layout.height }}>
    <div className="block-title"><span className="block-icon">{block.kind === 'module' ? <Box size={15}/> : block.kind === 'input' || block.kind === 'output' ? <ArrowRight size={15}/> : <GitBranch size={15}/>}</span><div><b title={block.name}>{block.name}</b><small>{block.module || block.kind.toUpperCase()}</small></div><button className="nodrag tiny" title="配置" onClick={() => data.onEdit(id)}><Settings2 size={14}/></button></div>
    {count > 1 && <button className="nodrag generate-tag" disabled={block.analysis?.homogeneous === false} onClick={() => data.onToggle(id)}><Layers size={12}/> generate × {count}<span>{block.analysis?.homogeneous === false ? '逐路接口' : layout.expanded ? '收起' : '展开'}</span></button>}
    {layout.labels.map(label => <div className="perimeter-group" key={label.label} style={{ top: label.top }}>{label.label}</div>)}
    {layout.visible.map(renderPort)}{layout.hidden.map(renderPort)}
    <div className="block-footer perimeter-footer">{block.kind === 'module' ? Object.entries(block.overrides ?? {}).map(([k,v]) => `${k} = ${v}`).join(' · ') || '默认参数' : ['split','concat','reshape'].includes(block.kind) ? '声明顺序 → MSB first' : block.kind.toUpperCase()}<span>SV</span></div>
  </div>;
}
