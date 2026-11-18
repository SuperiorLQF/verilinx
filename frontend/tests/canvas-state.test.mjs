import { test } from 'node:test';
import assert from 'node:assert/strict';
import { applyNodeChanges, getNodesBounds } from '@xyflow/react';
import { reconcileCanvasNodes } from '../.test-dist/canvas-state.js';

const handlers = { onEdit() {}, onToggle() {} };
const block = { id: 'processor', kind: 'module', module: 'processor', name: 'U_processor_0', position: { x: 400, y: 180 } };
const measure = nodes => applyNodeChanges([
  { id: 'processor', type: 'dimensions', dimensions: { width: 248, height: 206 } },
], nodes);

test('measured dimensions survive domain updates and selection', () => {
  const initial = reconcileCanvasNodes([block], [], handlers, null);
  const measured = measure(initial);
  const updated = { ...block, view: 'expanded', overrides: { WIDTH: '16' } };
  const next = reconcileCanvasNodes([updated], measured, handlers, 'processor');
  assert.deepEqual(next[0].measured, { width: 248, height: 206 });
  assert.deepEqual(getNodesBounds(next), { x: 400, y: 180, width: 248, height: 206 });
  assert.equal(next[0].data.block, updated);
  assert.equal(next[0].selected, true);
});

test('adding a node keeps existing measurements; new dimensions are retained', () => {
  const first = measure(reconcileCanvasNodes([block], [], handlers, null));
  const added = { ...block, id: 'new', name: 'U_processor_1', position: { x: 700, y: 180 } };
  const next = reconcileCanvasNodes([block, added], first, handlers, null);
  assert.equal(next[0].measured.width, 248);
  const allMeasured = applyNodeChanges([{ id: 'new', type: 'dimensions', dimensions: { width: 248, height: 150 } }], next);
  const refreshed = reconcileCanvasNodes([block, added], allMeasured, handlers, null);
  assert.equal(refreshed[1].measured.height, 150);
  assert.equal(getNodesBounds(refreshed).width, 548);
});

test('drag position survives updates; reopening uses the saved project position', () => {
  const measured = measure(reconcileCanvasNodes([block], [], handlers, null));
  const moved = applyNodeChanges([{ id: block.id, type: 'position', position: { x: 120, y: 90 } }], measured);
  assert.deepEqual(reconcileCanvasNodes([block], moved, handlers, null)[0].position, { x: 120, y: 90 });
  const restored = reconcileCanvasNodes([block], moved, handlers, null, true);
  assert.deepEqual(restored[0].position, block.position);
  assert.equal(restored[0].measured.width, 248);
});

test('expand/collapse accepts a new size and deleting a node removes its state', () => {
  const measured = measure(reconcileCanvasNodes([block], [], handlers, null));
  const expanded = reconcileCanvasNodes([{ ...block, view: 'expanded' }], measured, handlers, null);
  const resized = applyNodeChanges([{ id: block.id, type: 'dimensions', dimensions: { width: 248, height: 900 } }], expanded);
  const collapsed = reconcileCanvasNodes([{ ...block, view: 'stacked' }], resized, handlers, null);
  assert.equal(collapsed[0].measured.height, 900);
  assert.equal(reconcileCanvasNodes([], collapsed, handlers, null).length, 0);
});
