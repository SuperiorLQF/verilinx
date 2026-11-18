import {test} from 'node:test';
import assert from 'node:assert/strict';
import {alignNodes,snapNodes,removeGraphItems} from '../.test-dist/arrange.js';
import {reconcileCanvasNodes} from '../.test-dist/canvas-state.js';
const node=(id,x,y,width=100,height=80)=>({id,position:{x,y},measured:{width,height}});
const nodes=[node('a',10,20,100,80),node('b',220,180,200,160),node('outside',800,600)];
const selected=new Set(['a','b']);

test('all six alignments use measured bounds, including different node heights',()=>{
 const left=alignNodes(nodes,selected,'left');assert.equal(left[0].position.x,left[1].position.x);assert.equal(left[0].position.x,10);
 const right=alignNodes(nodes,selected,'right');assert.equal(right[0].position.x+100,right[1].position.x+200);assert.equal(right[1].position.x,220);
 const center=alignNodes(nodes,selected,'center');assert.equal(center[0].position.x+50,center[1].position.x+100);assert.equal(center[0].position.x+50,215);
 const top=alignNodes(nodes,selected,'top');assert.equal(top[0].position.y,20);assert.equal(top[1].position.y,20);
 const bottom=alignNodes(nodes,selected,'bottom');assert.equal(bottom[0].position.y+80,bottom[1].position.y+160);assert.equal(bottom[1].position.y,180);
 const middle=alignNodes(nodes,selected,'middle');assert.equal(middle[0].position.y+40,middle[1].position.y+80);assert.equal(middle[0].position.y+40,180);
 for(const output of [left,right,center,top,bottom,middle]){assert.equal(output[2],nodes[2]);assert.equal(output[0].measured,nodes[0].measured);}
 assert.deepEqual(nodes[0].position,{x:10,y:20});
 assert.equal(alignNodes(nodes,new Set(['a']),'left'),nodes);
});

test('snap tolerance stays constant in screen pixels and guides span both blocks',()=>{
 const input=[node('a',4,205),node('b',0,0)];
 const snapped=snapNodes(input,new Set(['a']),1);
 assert.equal(snapped.nodes[0].position.x,0);assert.equal(snapped.nodes[0].position.y,205);
 assert.deepEqual(snapped.guides,[{axis:'x',coordinate:0,start:-18,end:303}]);
 assert.equal(snapNodes(input,new Set(['a']),2).guides.length,0);
 const zoomed=snapNodes([node('a',12,205),node('b',0,0)],new Set(['a']),.5);
 assert.equal(zoomed.nodes[0].position.x,0);
});

test('group snapping preserves relative positions and never snaps to selected peers',()=>{
 const input=[node('a',5,10),node('b',155,210),node('c',0,500)];
 const result=snapNodes(input,selected,1);
 assert.equal(result.nodes[0].position.x,0);assert.equal(result.nodes[1].position.x,150);
 assert.equal(result.nodes[1].position.y-result.nodes[0].position.y,200);
 assert.equal(result.nodes[2],input[2]);
 assert.deepEqual(snapNodes(input,new Set(['a','b','c']),1),{nodes:input,guides:[]});
});

test('bulk deletion removes incident and explicitly selected edges atomically',()=>{
 const project={nodes:[{id:'a'},{id:'b'},{id:'c'},{id:'d'}],edges:[
  {id:'ab',source:'a',target:'b'}, {id:'bc',source:'b',target:'c'},
  {id:'cd',source:'c',target:'d'}, {id:'dc',source:'d',target:'c'},
 ]};
 const result=removeGraphItems(project,new Set(['a','b']),new Set(['cd']));
 assert.deepEqual(result.nodes.map(n=>n.id),['c','d']);assert.deepEqual(result.edges.map(e=>e.id),['dc']);
 assert.equal(project.edges.length,4);
 assert.deepEqual(removeGraphItems(project,new Set(),new Set(['cd'])).nodes,project.nodes);
});

test('multi-selection survives domain refresh, measurement and layout-mode changes',()=>{
 const blocks=nodes.map(n=>({...n,kind:'module',name:n.id}));
 const measured=blocks.map(n=>({...n,type:'block',data:{block:n},selected:selected.has(n.id)}));
 const output=reconcileCanvasNodes(blocks,measured,{onEdit(){},onToggle(){},layoutMode:true},selected);
 assert.deepEqual(output.map(n=>n.selected),[true,true,false]);assert.equal(output[0].measured.width,100);
 assert.equal(output[0].draggable,false);assert.equal(output[0].connectable,false);
});
