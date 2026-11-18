import {test} from 'node:test';
import assert from 'node:assert/strict';
import {polylinePath,routePoint,appendBend,insertBend,orthogonalPoints,moveBend,handleEndpoint,MAX_BENDS} from '../.test-dist/routing.js';
const check=(start,points,end)=>{
 const path=[start,...points,end];for(let i=1;i<path.length;i++)assert.ok(Math.abs(path[i].x-path[i-1].x)<1e-9||Math.abs(path[i].y-path[i-1].y)<1e-9,`diagonal ${JSON.stringify([path[i-1],path[i]])}`);
};

test('every moving leg is axis-aligned without rounding the fixed coordinate',()=>{
 const start={x:10.123456789,y:20.987654321};
 for(const zoom of [.15,1,1.7])for(const invert of [false,true])for(const p of [{x:14,y:90},{x:80,y:55},{x:55,y:80}])check(start,[],routePoint(start,p,zoom,invert));
 assert.deepEqual(routePoint(start,{x:80,y:55}),{x:80,y:start.y});
 assert.deepEqual(routePoint(start,{x:80,y:55},1,true),{x:start.x,y:55});
});
test('final small misalignment moves the last corner onto the exact input row',()=>{
 const s={x:0,y:0},t={x:200,y:106.23456789},p=[{x:100,y:0},{x:100,y:100}];
 const fixed=orthogonalPoints(s,p,t,'right','left',8);
 assert.deepEqual(fixed,[{x:100,y:0},{x:100,y:t.y}]);check(s,fixed,t);
 assert.deepEqual(p,[{x:100,y:0},{x:100,y:100}]);
 const top={x:106.25,y:200};const v=orthogonalPoints(s,[{x:0,y:100},{x:100,y:100}],top,'bottom','top',8);
 assert.deepEqual(v,[{x:0,y:100},{x:top.x,y:100}]);check(s,v,top);
});
test('a larger final offset adds a local elbow and preserves the clicked corner',()=>{
 const s={x:0,y:0},t={x:200,y:160},p=[{x:100,y:0},{x:100,y:100}];
 const fixed=orthogonalPoints(s,p,t,'right','left',8);
 assert.deepEqual(fixed,[...p,{x:100,y:160}]);check(s,fixed,t);
});
test('old slanted paths and moved endpoints remain orthogonal and normalization is stable',()=>{
 const sides=['left','right','top','bottom'];
 for(let k=0;k<20;k++)for(const a of sides)for(const b of sides){
  const s={x:13.125+k,y:-7.333-k},t={x:300.25-k,y:190.75+k};
  for(const p of [[],[{x:80.21,y:33.78},{x:170.55,y:111.99}]]){
   const fixed=orthogonalPoints(s,p,t,a,b);check(s,fixed,t);
   assert.deepEqual(orthogonalPoints(s,fixed,t,a,b),fixed);
   assert.equal((polylinePath(s,fixed,t).match(/ L /g)||[]).length,fixed.length+1);
  }
 }
});
test('dragging a bend moves adjacent rows and columns while keeping both endpoints fixed',()=>{
 const s={x:0,y:0},t={x:200,y:200},p=[{x:50,y:0},{x:50,y:100},{x:150,y:100},{x:150,y:200}];
 const moved=moveBend(s,p,t,1,{x:70,y:130});
 assert.deepEqual(moved,[{x:70,y:0},{x:70,y:130},{x:150,y:130},{x:150,y:200}]);check(s,moved,t);
 check(s,moveBend(s,p,t,0,{x:90,y:50}),t);
 assert.deepEqual(s,{x:0,y:0});assert.deepEqual(t,{x:200,y:200});
});
test('new points are projected to a segment, duplicates are ignored, and the bend limit is retained',()=>{
 const s={x:0,y:0},p=[{x:100,y:0},{x:100,y:100}],t={x:200,y:100};
 const inserted=insertBend(s,p,t,{x:103,y:55});check(s,inserted,t);
 assert.deepEqual(inserted,[{x:100,y:0},{x:100,y:55},{x:100,y:100}]);
 const one=appendBend([],s,{x:10,y:0});assert.equal(appendBend(one,s,{x:10,y:0}),one);
 assert.equal(appendBend(Array.from({length:MAX_BENDS},(_,x)=>({x,y:1})),s,{x:999,y:1}).length,MAX_BENDS);
});
test('port clicks resolve to the same anchor that React Flow uses to render the final segment',()=>{
 const node={internals:{positionAbsolute:{x:10,y:20},handleBounds:{source:[{id:'out',x:84,y:34,width:32,height:32,position:'right'}],target:[{id:'in',x:-16,y:50,width:32,height:32,position:'left'}]}}};
 assert.deepEqual(handleEndpoint(node,'out','source'),{point:{x:126,y:70},side:'right'});
 assert.deepEqual(handleEndpoint(node,'in','target'),{point:{x:-6,y:86},side:'left'});
 assert.equal(handleEndpoint(node,'missing','target'),null);
});
