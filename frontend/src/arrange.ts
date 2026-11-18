import type { Project } from './api.js';

export type Alignment = 'left' | 'center' | 'right' | 'top' | 'middle' | 'bottom';
export type GeometryNode = { id: string; position: { x: number; y: number }; measured?: { width?: number; height?: number }; width?: number; height?: number };
export type Guide = { axis: 'x' | 'y'; coordinate: number; start: number; end: number };
const size = (n: GeometryNode) => ({ width: n.measured?.width ?? n.width ?? 272, height: n.measured?.height ?? n.height ?? 140 });
const bounds = (nodes: GeometryNode[]) => {
  const left = Math.min(...nodes.map(n => n.position.x)), top = Math.min(...nodes.map(n => n.position.y));
  const right = Math.max(...nodes.map(n => n.position.x + size(n).width)), bottom = Math.max(...nodes.map(n => n.position.y + size(n).height));
  return { left, top, right, bottom, center: (left + right) / 2, middle: (top + bottom) / 2 };
};

/** Align against the selection bounds, accounting for each node's actual size. */
export function alignNodes<T extends GeometryNode>(nodes: T[], ids: ReadonlySet<string>, alignment: Alignment): T[] {
  const selected = nodes.filter(n => ids.has(n.id));
  if (selected.length < 2) return nodes;
  const box = bounds(selected);
  return nodes.map(n => {
    if (!ids.has(n.id)) return n;
    const { width, height } = size(n);
    const position = { ...n.position };
    if (alignment === 'left') position.x = box.left;
    if (alignment === 'center') position.x = box.center - width / 2;
    if (alignment === 'right') position.x = box.right - width;
    if (alignment === 'top') position.y = box.top;
    if (alignment === 'middle') position.y = box.middle - height / 2;
    if (alignment === 'bottom') position.y = box.bottom - height;
    return { ...n, position };
  });
}

/** Magnetic guides use a constant screen-space tolerance and preserve group offsets. */
export function snapNodes<T extends GeometryNode>(nodes: T[], ids: ReadonlySet<string>, zoom: number, tolerance = 7): { nodes: T[]; guides: Guide[] } {
  const moving = nodes.filter(n => ids.has(n.id)), stationary = nodes.filter(n => !ids.has(n.id));
  if (!moving.length || !stationary.length) return { nodes, guides: [] };
  const box = bounds(moving), limit = tolerance / Math.max(zoom, 0.01);
  const candidates: Partial<Record<'x' | 'y', { delta: number; target: ReturnType<typeof bounds>; coordinate: number }>> = {};
  for (const n of stationary) {
    const target = bounds([n]);
    for (const axis of ['x', 'y'] as const) {
      const anchors = axis === 'x' ? ['left', 'center', 'right'] as const : ['top', 'middle', 'bottom'] as const;
      for (const from of anchors) for (const to of anchors) {
        const delta = target[to] - box[from], previous = candidates[axis];
        if (Math.abs(delta) <= limit && (!previous || Math.abs(delta) < Math.abs(previous.delta))) candidates[axis] = { delta, target, coordinate: target[to] };
      }
    }
  }
  const dx = candidates.x?.delta ?? 0, dy = candidates.y?.delta ?? 0;
  const guides: Guide[] = [];
  for (const axis of ['x', 'y'] as const) {
    const hit = candidates[axis];
    if (hit) guides.push({ axis, coordinate: hit.coordinate,
      start: axis === 'x' ? Math.min(box.top + dy, hit.target.top) - 18 : Math.min(box.left + dx, hit.target.left) - 18,
      end: axis === 'x' ? Math.max(box.bottom + dy, hit.target.bottom) + 18 : Math.max(box.right + dx, hit.target.right) + 18 });
  }
  return { nodes: nodes.map(n => ids.has(n.id) ? { ...n, position: { x: n.position.x + dx, y: n.position.y + dy } } : n), guides };
}

/** Delete nodes and their incident edges in one update, including explicit edge selections. */
export function removeGraphItems(project: Project, nodeIds: ReadonlySet<string>, edgeIds: ReadonlySet<string>): Project {
  return { ...project, nodes: project.nodes.filter(n => !nodeIds.has(n.id)),
    edges: project.edges.filter(e => !edgeIds.has(e.id) && !nodeIds.has(e.source) && !nodeIds.has(e.target)) };
}
