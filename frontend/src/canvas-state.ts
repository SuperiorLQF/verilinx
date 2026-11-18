import type { Node } from '@xyflow/react';
import type { Block } from './api';

export type BlockNode = Node<{
  block: Block;
  onEdit: (id: string) => void;
  onToggle: (id: string) => void;
}, 'block'>;

type Handlers = Pick<BlockNode['data'], 'onEdit' | 'onToggle'>;

/** Keep React Flow's measured dimensions when domain data is refreshed.
 * Dropping `measured` resets React Flow's initialization and hides every node.
 */
export function reconcileCanvasNodes(
  blocks: Block[], previous: BlockNode[], handlers: Handlers,
  selected: string | null, resetPositions = false,
): BlockNode[] {
  const existing = new Map(previous.map(node => [node.id, node]));
  return blocks.map(block => {
    const current = existing.get(block.id);
    return {
      ...current,
      id: block.id,
      type: 'block',
      position: resetPositions ? block.position : current?.position ?? block.position,
      selected: block.id === selected,
      data: { block, ...handlers },
    };
  });
}
