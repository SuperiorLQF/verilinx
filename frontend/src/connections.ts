import type { Connection } from '@xyflow/react';
import { lanePorts, ports, type Block, type Project, type Port } from './api.js';

function endpoint(node: Block, handle: string): Port | undefined {
  const match = /^(.*)@(\d+)$/.exec(handle);
  if (match && node.kind === 'module') {
    const lane = Number(match[2]);
    return (node.analysis?.count ?? 1) > 1 && lane < (node.analysis?.count ?? 1) ? lanePorts(node, lane).find(p => p.name === match[1]) : undefined;
  }
  return ports(node).find(p => p.name === handle);
}
function overlap(a: string, b: string) {
  const [baseA, laneA] = a.split('@'), [baseB, laneB] = b.split('@');
  return baseA === baseB && (laneA === undefined || laneB === undefined || laneA === laneB);
}
export function connectionIssue(project: Project, c: Connection): string | null {
  const sourceNode = project.nodes.find(n => n.id === c.source), targetNode = project.nodes.find(n => n.id === c.target);
  if (!sourceNode || !targetNode || !c.sourceHandle || !c.targetHandle) return '端口不存在，请重新选择。';
  const source = endpoint(sourceNode, c.sourceHandle), target = endpoint(targetNode, c.targetHandle);
  if (!source || !target) return '端口已变化，请重新选择对应的端口。';
  if (source.role !== 'source' || target.role !== 'target') return '请从输出箭头连接到输入箭头。';
  if (project.edges.some(e => e.target === c.target && overlap(e.targetPort, c.targetHandle!))) return '该输入已有驱动。请先删除原连线；聚合端口与单路端口不能重叠连接。';
  const shape = (p: Port) => JSON.stringify([p.shape.packed ?? [], p.shape.unpacked ?? [], p.shape.atom_width ?? 1]);
  if (shape(source) !== shape(target)) return '端口位宽或数组形状不一致，请插入分线器、集线器或数组转换组件。';
  return null;
}
