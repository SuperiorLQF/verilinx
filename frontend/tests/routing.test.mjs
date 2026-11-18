import {test} from 'node:test';
import assert from 'node:assert/strict';
import {polylinePath,routePoint,appendBend,insertBend,MAX_BENDS} from '../.test-dist/routing.js';

test('polyline follows only user-authored bends, with no synthesized elbows',()=>{
 const points=[{x:45,y:7},{x:45,y:90},{x:-15,y:90}];
 assert.equal(polylinePath({x:1,y:7},points,{x:-15,y:120}),'M 1 7 L 45 7 L 45 90 L -15 90 L -15 120');
 assert.equal(polylinePath({x:0,y:0},[],{x:77,y:93}),'M 0 0 L 77 93');
 assert.deepEqual(points,[{x:45,y:7},{x:45,y:90},{x:-15,y:90}]);
});
test('click commits one bend; duplicates are ignored and authored collinear points remain',()=>{
 const start={x:0,y:0};const one=appendBend([],start,{x:10,y:0});
 const two=appendBend(one,start,{x:20,y:0});assert.equal(two.length,2);
 assert.equal(appendBend(two,start,{x:20,y:0}),two);
 assert.deepEqual(two.slice(0,-1),one);
 assert.equal(appendBend(Array.from({length:MAX_BENDS},(_,x)=>({x,y:1})),start,{x:999,y:1}).length,MAX_BENDS);
});
test('axis assist uses screen pixels; Shift constrains without introducing corners',()=>{
 const start={x:10,y:20};
 assert.deepEqual(routePoint(start,{x:14,y:90},1),{x:10,y:90});
 assert.deepEqual(routePoint(start,{x:14,y:90},2),{x:14,y:90});
 assert.deepEqual(routePoint(start,{x:80,y:55},1,true),{x:80,y:20});
 assert.deepEqual(routePoint(start,{x:55,y:80},1,true),{x:10,y:80});
 assert.deepEqual(routePoint(start,{x:80,y:55},1),{x:80,y:55});
});
test('adding a point splits the nearest segment in the existing manual path',()=>{
 const start={x:0,y:0},points=[{x:100,y:0},{x:100,y:100}],end={x:200,y:100};
 assert.deepEqual(insertBend(start,points,end,{x:100,y:55}),[{x:100,y:0},{x:100,y:55},{x:100,y:100}]);
 assert.deepEqual(insertBend(start,points,end,{x:40,y:0})[0],{x:40,y:0});
 assert.deepEqual(insertBend(start,points,end,{x:150,y:100}).at(-1),{x:150,y:100});
});
