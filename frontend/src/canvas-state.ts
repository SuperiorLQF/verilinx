import type { Node } from '@xyflow/react';
import type { Block, PortAnchor } from './api';

export type BlockNode = Node<{
  block: Block;
  onEdit: (id: string) => void;
  onToggle: (id: string) => void;
  layoutMode?: boolean;
  onPortMove?: (nodeId: string, portId: string, anchor: PortAnchor) => void;
}, 'block'>;

type Handlers = Pick<BlockNode['data'], 'onEdit' | 'onToggle' | 'layoutMode' | 'onPortMove'>;

/** Keep React Flow's measured dimensions when domain data is refreshed.
 * Dropping `measured` resets React Flow's initialization and hides every node.
 */
export function reconcileCanvasNodes(
  blocks: Block[], previous: BlockNode[], handlers: Handlers,
  selected: string | null | ReadonlySet<string>, resetPositions = false,
): BlockNode[] {
  const existing = new Map(previous.map(node => [node.id, node]));
  return blocks.map(block => {
    const current = existing.get(block.id);
    return {
      ...current,
      id: block.id,
      type: 'block',
      draggable: !handlers.layoutMode,
      connectable: !handlers.layoutMode,
      position: resetPositions ? block.position : current?.position ?? block.position,
      selected: typeof selected === 'string' ? block.id === selected : selected?.has(block.id) ?? false,
      data: { block, ...handlers },
    };
  });
}
