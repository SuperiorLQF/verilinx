import { test } from 'node:test';
import assert from 'node:assert/strict';
import { blockPorts, projectToBorder, arrowAngle, slideAnchor } from '../.test-dist/port-layout.js';
import { connectionIssue } from '../.test-dist/connections.js';
const shape = { packed:[[7,0]], unpacked:[], atom_width:1 };
const module = { id:'a',name:'U_a',kind:'module',module:'m',position:{x:0,y:0},analysis:{count:6,homogeneous:true,ports:[{name:'din',direction:'In',shape},{name:'dout',direction:'Out',shape}]}};

test('pointer projection reaches all four borders and is independent of zoom',()=>{
  const r={left:100,top:50,width:200,height:100};
  assert.deepEqual(projectToBorder(100,75,r),{side:'left',offset:.25});
  assert.deepEqual(projectToBorder(300,125,r),{side:'right',offset:.75});
  assert.deepEqual(projectToBorder(160,50,r),{side:'top',offset:.3});
  assert.deepEqual(projectToBorder(240,150,r),{side:'bottom',offset:.7});
  assert.deepEqual(projectToBorder(130,50,{left:100,top:50,width:100,height:50}),{side:'top',offset:.3});
  const nearCorner=projectToBorder(100,-200,r);
  assert.ok(nearCorner.offset>=.025&&nearCorner.offset<=.975);
});

test('input arrows point inward and output arrows outward on each edge',()=>{
  assert.equal(arrowAngle('left','target'),0);
  assert.equal(arrowAngle('left','source'),180);
  assert.equal(arrowAngle('right','target'),180);
  assert.equal(arrowAngle('right','source'),0);
  assert.equal(arrowAngle('top','target'),90);
  assert.equal(arrowAngle('bottom','source'),90);
});

test('saved layout overrides defaults; collapsed lane IDs remain available',()=>{
  const layout=blockPorts({...module,portLayout:{dout:{side:'top',offset:.7}}});
  assert.deepEqual(layout.visible.find(p=>p.id==='dout').anchor,{side:'top',offset:.7});
  assert.equal(layout.hidden.length,12);
  assert.deepEqual(layout.hidden.find(p=>p.id==='dout@5').anchor,{side:'top',offset:.7});
  const expanded=blockPorts({...module,view:'expanded',portLayout:{'din@2':{side:'bottom',offset:.4}}});
  assert.deepEqual(expanded.visible.find(p=>p.id==='din@2').anchor,{side:'bottom',offset:.4});
  assert.equal(expanded.hidden.length,0);
});

test('keyboard adjustment crosses corners and invalid layout falls back safely',()=>{
  assert.deepEqual(slideAnchor({side:'top',offset:.97},true),{side:'right',offset:.025});
  assert.deepEqual(slideAnchor({side:'left',offset:.03},true),{side:'top',offset:.025});
  const layout=blockPorts({...module,portLayout:{dout:{side:'unknown',offset:NaN}}});
  assert.equal(layout.visible.find(p=>p.id==='dout').anchor.side,'right');
});

const source={id:'s',name:'src',kind:'input',position:{x:0,y:0},ports:[{name:'out',role:'source',shape}]};
const target={id:'t',name:'dst',kind:'output',position:{x:0,y:0},ports:[{name:'in',role:'target',shape}]};
const connection={source:'s',target:'t',sourceHandle:'out',targetHandle:'in'};
const project={nodes:[source,target],edges:[]};

test('valid drag connection accepts fanout and rejects duplicate input drivers',()=>{
 assert.equal(connectionIssue(project,connection),null);
 const fanout={...target,id:'t2'};
 const connected={nodes:[source,target,fanout],edges:[{source:'s',target:'t',sourcePort:'out',targetPort:'in'}]};
 assert.equal(connectionIssue(connected,{...connection,target:'t2'}),null);
 assert.match(connectionIssue(connected,connection),/已有驱动/);
});

test('shape mismatch, wrong direction and aggregate/lane overlap explain failures',()=>{
 assert.match(connectionIssue({...project,nodes:[{...source,ports:[{...source.ports[0],shape:{...shape,unpacked:[[0,5]]}}]},target]},connection),/形状/);
 assert.match(connectionIssue(project,{source:'t',target:'s',sourceHandle:'in',targetHandle:'out'}),/输出/);
 const generated={...module,id:'g'};
 const p={nodes:[source,generated],edges:[{source:'s',target:'g',sourcePort:'out',targetPort:'din'}]};
 assert.match(connectionIssue(p,{source:'s',target:'g',sourceHandle:'out',targetHandle:'din@0'}),/重叠/);
 assert.equal(connectionIssue({...p,edges:[]},{source:'s',target:'g',sourceHandle:'out',targetHandle:'din@0'}),null);
});
