import { lanePorts, ports, type Block, type Port, type PortAnchor, type PortSide } from './api.js';

export type DisplayPort = Port & { id: string; group: string; anchor: PortAnchor; hidden?: boolean };
export const blockWidth = 272;
const sides: PortSide[] = ['left', 'right', 'top', 'bottom'];
const clamp = (value: number, low: number, high: number) => Math.min(high, Math.max(low, value));

export function validAnchor(value: PortAnchor | undefined, fallback: PortAnchor): PortAnchor {
  return value && sides.includes(value.side) && Number.isFinite(value.offset)
    ? { side: value.side, offset: clamp(value.offset, 0.025, 0.975) } : fallback;
}

export function blockPorts(block: Block) {
  const count = block.analysis?.count ?? 1;
  const expanded = count > 1 && (block.view === 'expanded' || block.analysis?.homogeneous === false);
  const groups: { label: string; ports: Port[]; lane?: number }[] = [];
  const aggregate = ports(block);
  if (aggregate.length) groups.push({ label: expanded ? '聚合端口' : '', ports: aggregate });
  if (expanded) for (let lane = 0; lane < count; lane++)
    groups.push({ label: `lane ${lane}`, ports: lanePorts(block, lane), lane });
  const header = 58 + (count > 1 ? 28 : 0);
  let cursor = header;
  const entries: { port: Port; id: string; group: string; y: number }[] = [];
  const labels: { label: string; top: number }[] = [];
  for (const group of groups) {
    if (group.label) { labels.push({ label: group.label, top: cursor + 3 }); cursor += 25; }
    for (const role of ['target', 'source'] as const) {
      group.ports.filter(p => p.role === role).forEach((port, i) => {
        entries.push({ port, id: port.name + (group.lane === undefined ? '' : '@' + group.lane), group: group.label, y: cursor + 22 + i * 34 });
      });
    }
    cursor += Math.max(1, ...(['target', 'source'] as const).map(role => group.ports.filter(p => p.role === role).length)) * 34 + 15;
  }
  const height = Math.max(cursor + 30, 140);
  const visible: DisplayPort[] = entries.map(({ port, id, group, y }) => ({
    ...port, id, group,
    anchor: validAnchor(block.portLayout?.[id], { side: port.role === 'target' ? 'left' : 'right', offset: y / height }),
  }));
  // Collapsed lanes retain their existing endpoints at the aggregate anchor.
  const hidden: DisplayPort[] = [];
  if (count > 1 && !expanded && block.analysis?.homogeneous !== false) {
    for (let lane = 0; lane < count; lane++) for (const port of lanePorts(block, lane)) {
      const aggregatePort = visible.find(p => p.id === port.name);
      if (aggregatePort) hidden.push({ ...port, id: port.name + '@' + lane, group: '', anchor: aggregatePort.anchor, hidden: true });
    }
  }
  return { visible, hidden, labels, height, header, expanded };
}

/** Project a client coordinate onto the closest border; works at any canvas zoom. */
export function projectToBorder(x: number, y: number, rect: { left: number; top: number; width: number; height: number }): PortAnchor {
  const width = Math.max(rect.width, 1), height = Math.max(rect.height, 1);
  const localX = clamp(x - rect.left, 0, width), localY = clamp(y - rect.top, 0, height);
  const distances: [PortSide, number][] = [['left', Math.abs(x - rect.left)], ['right', Math.abs(x - rect.left - width)], ['top', Math.abs(y - rect.top)], ['bottom', Math.abs(y - rect.top - height)]];
  distances.sort((a, b) => a[1] - b[1]);
  const side = distances[0][0];
  return { side, offset: clamp(side === 'left' || side === 'right' ? localY / height : localX / width, 0.025, 0.975) };
}

/** Rotate a right-pointing arrow to show signal flow relative to the module. */
export function arrowAngle(side: PortSide, role: Port['role']) {
  const outward = { right: 0, bottom: 90, left: 180, top: 270 }[side];
  return (outward + (role === 'target' ? 180 : 0)) % 360;
}

/** Keyboard movement follows the perimeter clockwise/counterclockwise. */
export function slideAnchor(anchor: PortAnchor, clockwise: boolean, step = 0.025): PortAnchor {
  const order: PortSide[] = ['top', 'right', 'bottom', 'left'];
  const index = order.indexOf(anchor.side);
  const forward = anchor.side === 'top' || anchor.side === 'right';
  let progress = (forward ? anchor.offset : 1 - anchor.offset) + (clockwise ? step : -step);
  let nextIndex = index;
  if (progress > 0.975) { nextIndex = (index + 1) % 4; progress = 0.025; }
  if (progress < 0.025) { nextIndex = (index + 3) % 4; progress = 0.975; }
  const side = order[nextIndex];
  return { side, offset: side === 'top' || side === 'right' ? progress : 1 - progress };
}
