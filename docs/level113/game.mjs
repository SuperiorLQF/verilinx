import {COLORS,SHAPES,fresh,allowed,cells,canMove,move,receiver,ready,finish,settle,key,legalMoves} from './core.mjs';
const $=id=>document.getElementById(id),canvas=$('board'),ctx=canvas.getContext('2d'),C=80,X=60,Y=300;
let state=fresh(),history=[],selected=null,drag=null,started=false,remaining=180,last=performance.now(),paused=false,ended=false,particles=[],flashes=[],sound=false,audio,toastTimer,hintCell=null,hintUntil=0;
const modal=$('modal'),initialBody=$('modalBody').innerHTML;
const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
const copy=x=>structuredClone(x);
function toast(text){$('announcement').textContent=text;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('announcement').textContent='',4200);}
function tone(freq=540){if(!sound)return;try{audio ||= new(window.AudioContext||window.webkitAudioContext)();const o=audio.createOscillator(),g=audio.createGain();o.connect(g);g.connect(audio.destination);o.type='sine';o.frequency.setValueAtTime(freq,audio.currentTime);g.gain.setValueAtTime(.045,audio.currentTime);g.gain.exponentialRampToValueAtTime(.001,audio.currentTime+.14);o.start();o.stop(audio.currentTime+.15);}catch{}}
function remember(){history.push({state:copy(state),remaining});if(history.length>150)history.shift();}
function refresh(){ $('progress').textContent=`已填满 ${state.cleared} / 15`;$('moves').textContent=`${state.moves} 步`;$('undo').disabled=!history.length;}
function reset(){state=fresh();history=[];selected=null;drag=null;particles=[];flashes=[];remaining=180;ended=false;hintCell=null;refresh();toast('两股沙流就绪，先观察下一种颜色。');}
function showHelp(first=false){paused=true;$('modalTitle').textContent='把颜色，归还给沙子。';$('modalBody').innerHTML=initialBody;$('play').textContent=first?'开始挑战 →':'继续挑战 →';$('close').hidden=true;modal.showModal();}
$('help').onclick=()=>showHelp(!started);
$('play').onclick=()=>{if(ended){reset();}started=true;paused=false;last=performance.now();modal.close();};
modal.addEventListener('cancel',e=>{e.preventDefault();modal.close();started=true;paused=false;last=performance.now();});
$('restart').onclick=()=>{reset();started=true;paused=false;};
$('undo').onclick=()=>{const prev=history.pop();if(!prev){toast('还没有可以撤回的操作。');return;}state=prev.state;remaining=prev.remaining;selected=null;drag=null;ended=false;particles=[];hintCell=null;refresh();toast('已撤回到上一步，沙流状态也已恢复。');};
$('time').onclick=()=>{if(ended){toast('点击「再玩一次」重新挑战。');return;}remaining+=60;tone(700);toast('已增加 60 秒，慢慢来。');};
$('sound').onclick=()=>{sound=!sound;$('sound').textContent=`音效 ${sound?'开':'关'}`;tone();};
$('hint').onclick=()=>{if(ended)return;if([0,1].some(i=>ready(state,i))){toast('同色沙正在填充，等容器消失后再移动。');return;}const solution=nextHint();if(solution){selected=solution.id;hintCell=solution;hintUntil=performance.now()+5500;toast(`发光容器向${solution.dx>0?'右':solution.dx<0?'左':solution.dy>0?'下':'上'}移动一格。`);}else toast('暂未找到短路径；可以撤回几步，或重开尝试。');};
function nextHint(){const root=copy(state);settle(root);const size=root.pieces.length,q=[{s:root,first:null}],seen=new Set([key(root)]);let head=0;while(head<q.length&&head<7000){const {s,first}=q[head++];for(const m of legalMoves(s)){const next=copy(s);move(next,m.id,m.dx,m.dy);settle(next);const f=first||m;if(next.pieces.length<size)return f;const k=key(next);if(!seen.has(k)){seen.add(k);q.push({s:next,first:f});}}}return null;}
function attempt(id,dx,dy){if(!started||paused||ended)return false;if(canMove(state,id,dx,dy)){remember();move(state,id,dx,dy);selected=id;hintCell=null;refresh();tone(350);return true;}tone(140);toast('这里被挡住了；↕ 容器只能上下移动。');return false;}
function local(e){const r=canvas.getBoundingClientRect();return {x:(e.clientX-r.left)*600/r.width,y:(e.clientY-r.top)*1100/r.height};}
function hit(pos){const x=Math.floor((pos.x-X)/C),y=Math.floor((pos.y-Y)/C);return state.pieces.find(p=>cells(p).some(([a,b])=>a===x&&b===y));}
canvas.addEventListener('pointerdown',e=>{if(!started||paused||ended||drag)return;e.preventDefault();canvas.focus({preventScroll:true});const pos=local(e),p=hit(pos);
 if(p){selected=p.id;drag={id:p.id,start:pos,pos,pointer:e.pointerId};canvas.setPointerCapture(e.pointerId);}
 else if(selected){const p=state.pieces.find(p=>p.id===selected);if(p){const dx=Math.floor((pos.x-X)/C)-p.x,dy=Math.floor((pos.y-Y)/C)-p.y;if(dx&&dy){toast('请沿水平或竖直方向移动。');return;}attempt(selected,dx,dy);}}
});
canvas.addEventListener('pointermove',e=>{if(!drag||drag.pointer!==e.pointerId)return;drag.pos=local(e);});
canvas.addEventListener('pointerup',e=>{if(!drag||drag.pointer!==e.pointerId)return;const d=drag;drag=null;const pos=local(e),rx=(pos.x-d.start.x)/C,ry=(pos.y-d.start.y)/C;let dx=0,dy=0;const p=state.pieces.find(p=>p.id===d.id);if(!p)return;
 if(p.axis==='v'){if(Math.abs(ry)>.4)dy=Math.round(ry);}else if(Math.max(Math.abs(rx),Math.abs(ry))>.4){if(Math.abs(rx)>Math.abs(ry))dx=Math.round(rx);else dy=Math.round(ry);}
 if(dx||dy){let n=Math.max(Math.abs(dx),Math.abs(dy));while(n>0&&!canMove(state,d.id,Math.sign(dx)*n,Math.sign(dy)*n))n--;if(n)attempt(d.id,Math.sign(dx)*n,Math.sign(dy)*n);else toast('容器不能穿过其他方块或白色边框。');}
});
canvas.addEventListener('pointercancel',()=>{drag=null;});canvas.addEventListener('lostpointercapture',()=>{drag=null;});
canvas.addEventListener('keydown',e=>{const dirs={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};if(dirs[e.key]&&selected){e.preventDefault();attempt(selected,...dirs[e.key]);}});
document.addEventListener('visibilitychange',()=>{last=performance.now();});
function round(x,y,w,h,r,fill,stroke,width=1){ctx.beginPath();ctx.roundRect(x,y,w,h,r);if(fill){ctx.fillStyle=fill;ctx.fill();}if(stroke){ctx.lineWidth=width;ctx.strokeStyle=stroke;ctx.stroke();}}
function text(t,x,y,size=18,color='#fff',align='left',weight=800){ctx.font=`${weight} ${size}px system-ui,sans-serif`;ctx.fillStyle=color;ctx.textAlign=align;ctx.fillText(t,x,y);}
function pathShape(p,inset=0,ox=0,oy=0){const shape=SHAPES[p.shape];ctx.beginPath();for(const [a,b]of shape)ctx.rect(X+(p.x+a)*C+inset+ox,Y+(p.y+b)*C+inset+oy,C-2*inset,C-2*inset);}
function shapeOutline(p){const set=new Set(SHAPES[p.shape].map(([a,b])=>`${a},${b}`));ctx.beginPath();for(const [a,b]of SHAPES[p.shape]){const x=X+(p.x+a)*C,y=Y+(p.y+b)*C;if(!set.has(`${a},${b-1}`)){ctx.moveTo(x,y);ctx.lineTo(x+C,y);}if(!set.has(`${a+1},${b}`)){ctx.moveTo(x+C,y);ctx.lineTo(x+C,y+C);}if(!set.has(`${a},${b+1}`)){ctx.moveTo(x+C,y+C);ctx.lineTo(x,y+C);}if(!set.has(`${a-1},${b}`)){ctx.moveTo(x,y+C);ctx.lineTo(x,y);}}}
function piece(p,time){const color=COLORS[p.color],shape=SHAPES[p.shape],x=X+p.x*C,y=Y+p.y*C,w=(Math.max(...shape.map(c=>c[0]))+1)*C,h=(Math.max(...shape.map(c=>c[1]))+1)*C;
 ctx.save();if(p.shape==='la'||p.shape==='lb'){
 shapeOutline(p);ctx.lineJoin='round';ctx.lineWidth=13;ctx.strokeStyle='#e7f732';ctx.shadowColor='#ddeb20';ctx.shadowBlur=7;ctx.stroke();ctx.shadowBlur=0;
 pathShape(p);ctx.fillStyle=color;ctx.fill();ctx.save();pathShape(p);ctx.clip();round(x+10,y+10,w-20,h-20,10,'#13568b');ctx.restore();shapeOutline(p);ctx.strokeStyle=color;ctx.lineWidth=8;ctx.stroke();
 }else{
 ctx.shadowColor=color+'70';ctx.shadowBlur=12;ctx.shadowOffsetY=3;const g=ctx.createLinearGradient(x,y,x+w,y+h);g.addColorStop(0,color);g.addColorStop(.48,color);g.addColorStop(1,'#542777');round(x+3,y+3,w-6,h-6,9,g,'#ffffff65',2);ctx.shadowBlur=0;ctx.shadowOffsetY=0;
 round(x+13,y+22,w-26,h-34,5,'#25184499',color+'88',2);round(x+15,y+9,w-30,15,5,'#ffffff21');
 }
 ctx.save();pathShape(p,6);ctx.clip();if(p.fill>0){const top=y+h*(1-p.fill);ctx.fillStyle=color;ctx.globalAlpha=.85;ctx.fillRect(x,top,w,h*p.fill);ctx.globalAlpha=1;for(let k=0;k<Math.min(80,p.fill*100);k++){const px=x+((k*47.13)%w),py=top+((k*23.31+time*.025)%(Math.max(1,h*p.fill)));ctx.fillStyle=k%2?'#ffffff5c':'#180a2733';ctx.fillRect(px,py,3,3);}}
 ctx.restore();let labelX=x+17;if(p.shape==='lb')labelX=x+C+12;text(`${Math.floor(p.fill*100)}%`,labelX,y+28,15,'#fff');
 if(p.axis==='v'&&p.fill<.85){const cx=x+w/2,ya=y+45,yb=y+h-24;ctx.strokeStyle='#eee0c4c9';ctx.lineWidth=8;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(cx,ya);ctx.lineTo(cx,yb);ctx.moveTo(cx-9,ya+10);ctx.lineTo(cx,ya);ctx.lineTo(cx+9,ya+10);ctx.moveTo(cx-9,yb-10);ctx.lineTo(cx,yb);ctx.lineTo(cx+9,yb-10);ctx.stroke();}
 if(selected===p.id){shapeOutline(p);ctx.strokeStyle='#fff3b7';ctx.lineWidth=4;ctx.shadowColor='#fff';ctx.shadowBlur=14;ctx.stroke();ctx.shadowBlur=0;}
 if(hintCell?.id===p.id&&time<hintUntil){text(hintCell.dx>0?'→':hintCell.dx<0?'←':hintCell.dy>0?'↓':'↑',x+w/2,y+h/2+17,49,'#fff','center');}
 ctx.restore();}
function reservoir(side,time){const sx=side===0?X+C:X+3*C,sy=142,w=2*C,h=139;round(sx-8,sy-8,w+16,h+16,14,'#e0dcff','#aeb5ff',3);round(sx,sy,w,h,7,'#261a54','#a47ddf',5);
 const next=state.queues[side][0],col=COLORS[next]||'#626090';ctx.save();round(sx+6,sy+6,w-12,h-12,4,null);ctx.clip();const gr=ctx.createLinearGradient(sx,sy,sx+w,sy+h);gr.addColorStop(0,col);gr.addColorStop(1,'#35235e');ctx.fillStyle=gr;ctx.fillRect(sx,sy,w,h);
 for(let k=0;k<190;k++){const a=(k*39.71)%w,b=(k*21.37+time*.012)%h;ctx.fillStyle=k%3===0?'#ffffff4d':'#150e2633';ctx.fillRect(sx+a,sy+b,4+(k%3),3);}
 ctx.restore();text(next?'出沙口':'已完成',sx+12,sy+23,12,'#fff');
 for(let i=1;i<Math.min(6,state.queues[side].length);i++){const cc=COLORS[state.queues[side][i]];round(sx+9+(i-1)*27,sy+h-23,21,13,4,cc,'#ffffff55');}
 const cx=sx+w/2;round(cx-25,-20,50,151,9,'#ffffff1e','#d6c3f985',3);ctx.save();round(cx-21,0,42,130,0,null);ctx.clip();ctx.fillStyle=col;ctx.globalAlpha=.6;ctx.fillRect(cx-20,-10,40,150);ctx.globalAlpha=1;for(let k=0;k<35;k++){ctx.fillStyle=k%2?'#fff5':col;ctx.fillRect(cx-17+(k*17)%34,((k*27+time*.05)%140)-10,4,8);}ctx.restore();}
function draw(time){ctx.clearRect(0,0,600,1100);
 reservoir(0,time);reservoir(1,time);
 round(200,40,200,72,32,'#4c226f','#d4a1fb88',3);round(211,49,178,53,25,'#281747');const minutes=Math.floor(remaining/60),seconds=Math.floor(remaining%60);text(`${String(minutes).padStart(2,'0')}:${String(seconds).padStart(2,'0')}`,300,88,40,remaining<30?'#ff707c':'#f2dcff','center',900);
 // Union of board cells with a softly raised porcelain perimeter.
 ctx.save();ctx.shadowColor='#99afff80';ctx.shadowBlur=8;ctx.shadowOffsetY=8;ctx.fillStyle='#bdc7ff';for(let y=0;y<9;y++)for(let x=0;x<6;x++)if(allowed(x,y))round(X+x*C-13,Y+y*C-13,C+26,C+26,12,'#dae4ff');ctx.restore();
 ctx.fillStyle='#2c2357';for(let y=0;y<9;y++)for(let x=0;x<6;x++)if(allowed(x,y))ctx.fillRect(X+x*C-2,Y+y*C-2,C+4,C+4);
 for(let y=0;y<9;y++)for(let x=0;x<6;x++)if(allowed(x,y)){const g=ctx.createLinearGradient(0,Y+y*C,0,Y+(y+1)*C);g.addColorStop(0,'#382d67');g.addColorStop(1,'#262044');round(X+x*C+2,Y+y*C+2,C-4,C-4,6,g,'#55497655',2);}
 // Outlet rays end at the first physical container, including wrong colors.
 for(let side=0;side<2;side++){const r=receiver(state,side),next=state.queues[side][0],col=side===0?1:4;const cx=X+col*C+C/2,top=Y-15,bottom=r?Y+r.y*C+8:Y+9*C;const flowing=ready(state,side)&&started&&!paused&&!drag&&!ended;
 if(next){ctx.save();ctx.strokeStyle=COLORS[next]+(flowing?'a0':'35');ctx.lineWidth=flowing?5:2;ctx.setLineDash(flowing?[]:[4,8]);ctx.beginPath();ctx.moveTo(cx,top);ctx.lineTo(cx,bottom);ctx.stroke();ctx.restore();if(flowing&&!reduce){for(let k=0;k<16;k++){const yy=top+((time*.36+k*29)%(Math.max(1,bottom-top)));ctx.fillStyle=k%3?'#ffffffc0':COLORS[next];ctx.fillRect(cx-8+((k*7)%14),yy,3,5);}}}
 }
 for(const p of state.pieces)piece(p,time);
 if(drag){const p=state.pieces.find(p=>p.id===drag.id);if(p){const dx=drag.pos.x-drag.start.x,dy=drag.pos.y-drag.start.y;const mx=p.axis==='v'?0:Math.abs(dx)>Math.abs(dy)?Math.round(dx/C):0,my=p.axis==='v'||Math.abs(dy)>=Math.abs(dx)?Math.round(dy/C):0;if(mx||my){ctx.save();ctx.globalAlpha=.4;const ghost={...p,x:p.x+mx,y:p.y+my};shapeOutline(ghost);ctx.strokeStyle=canMove(state,p.id,mx,my)?'#c7ffcf':'#ff7d95';ctx.lineWidth=6;ctx.stroke();ctx.restore();}}}
 for(const f of flashes){ctx.globalAlpha=f.life;round(f.x-8*(1-f.life),f.y-8*(1-f.life),f.w+16*(1-f.life),f.h+16*(1-f.life),15,null,'#fff',4);}ctx.globalAlpha=1;
 for(const p of particles){ctx.fillStyle=p.color;ctx.globalAlpha=p.life;ctx.fillRect(p.x,p.y,p.size,p.size);}ctx.globalAlpha=1;
 text('113',300,1071,12,'#c5a6df','center',600);
}
function celebrate(p){const shape=SHAPES[p.shape],w=(Math.max(...shape.map(c=>c[0]))+1)*C,h=(Math.max(...shape.map(c=>c[1]))+1)*C;flashes.push({x:X+p.x*C,y:Y+p.y*C,w,h,life:1});if(!reduce)for(let i=0;i<25;i++)particles.push({x:X+(p.x+.5)*C,y:Y+(p.y+.5)*C,vx:(Math.random()-.5)*180,vy:-Math.random()*190,color:COLORS[p.color],life:1,size:3+Math.random()*4});tone(650+state.cleared*22);}
function ending(win){ended=true;paused=true;drag=null;$('modalTitle').textContent=win?'颜色归位，关卡完成！':'沙漏暂时停下了。';$('modalBody').innerHTML=win?`<p>15 个容器全部填满。你用了 <strong>${state.moves} 步</strong>，还剩 <strong>${Math.ceil(remaining)} 秒</strong>。</p><p>再挑战一次，试试看更少的步数。</p>`:'<p>时间到了。重新开始，观察沙流的下一种颜色，再为它腾出通道。</p>';$('play').textContent='再玩一次 →';modal.showModal();}
function tick(now){const dt=Math.min(1,(now-last)/1000);last=now;const active=started&&!paused&&!ended&&!document.hidden;
 if(active){remaining=Math.max(0,remaining-dt);if(!drag){for(let side=0;side<2;side++){const r=ready(state,side);if(r){r.p.fill=Math.min(1,r.p.fill+dt*.68);if(r.p.fill>=1){const p=copy(r.p);finish(state,p.id,side);if(selected===p.id)selected=null;celebrate(p);refresh();}}}}
 if(!state.pieces.length)ending(true);else if(remaining<=0)ending(false);}
 for(const p of particles){p.x+=p.vx*dt;p.y+=p.vy*dt;p.vy+=260*dt;p.life-=dt*.9;}particles=particles.filter(p=>p.life>0);for(const f of flashes)f.life-=dt*2;flashes=flashes.filter(f=>f.life>0);
 draw(now);requestAnimationFrame(tick);
}
refresh();showHelp(true);requestAnimationFrame(tick);
