import React,{useState,useEffect,useCallback,useRef} from 'react';
import {createRoot} from 'react-dom/client';
import {ReactFlow,Background,Controls,MiniMap,ReactFlowProvider,useNodesState,useNodesInitialized,useReactFlow,SelectionMode,type Connection,type EdgeChange,type OnSelectionChangeParams,type OnNodeDrag} from '@xyflow/react';
import {Layers,Box,Plus,Download,Upload,Check,Settings2,Move,PanelLeft,Code2,GitBranch,ChevronRight,X,Trash2,ArrowRight,FolderOpen,Smartphone,Scan,Magnet,MousePointer2,AlignStartVertical,AlignCenterVertical,AlignEndVertical,AlignStartHorizontal,AlignCenterHorizontal,AlignEndHorizontal} from 'lucide-react';
import {AdapterEditor} from './AdapterEditor';
import {BlockView} from './BlockView';
import {AlignmentGuides} from './AlignmentGuides';
import {alignNodes,snapNodes,removeGraphItems,type Alignment,type Guide} from './arrange';
import {connectionIssue} from './connections';
import {reconcileCanvasNodes,type BlockNode} from './canvas-state';
import '@xyflow/react/dist/style.css';import './style.css';
import {api,uid,ports,lanePorts,shapeText,vector,download,type Project,type Block,type Port,type PortAnchor} from './api';

const nodeTypes={block:BlockView};
const alignmentActions = [
 {value:'left',label:'左对齐',Icon:AlignStartVertical}, {value:'center',label:'水平居中对齐',Icon:AlignCenterVertical}, {value:'right',label:'右对齐',Icon:AlignEndVertical},
 {value:'top',label:'顶端对齐',Icon:AlignStartHorizontal}, {value:'middle',label:'垂直居中对齐',Icon:AlignCenterHorizontal}, {value:'bottom',label:'底端对齐',Icon:AlignEndHorizontal},
] as const;
function App(){
 const {fitView,setViewport,screenToFlowPosition,getNodes,getZoom,deleteElements}=useReactFlow<BlockNode>();
 const [p,setP]=useState<Project|null>(null),[status,setStatus]=useState('连接 slang…'),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [edit,setEdit]=useState<string|null>(null),[draft,setDraft]=useState<Block|null>(null),[overText,setOverText]=useState(''),[portsText,setPortsText]=useState('');
 const [tab,setTab]=useState('modules'),[search,setSearch]=useState(''),[rtl,setRtl]=useState(''),[bottom,setBottom]=useState('log'),[messages,setMessages]=useState<string[]>([]),[paramsOpen,setParamsOpen]=useState(false),[importOpen,setImportOpen]=useState(false),[paramDraft,setParamDraft]=useState(''),[rootPath,setRootPath]=useState(''),[entry,setEntry]=useState('project.f'),[bundle,setBundle]=useState<Record<string,string>>({});
 const [layoutMode,setLayoutMode]=useState(false);
 const movePort=useCallback((nodeId:string,portId:string,anchor:PortAnchor)=>{setP(current=>current?{...current,nodes:current.nodes.map(n=>n.id===nodeId?{...n,portLayout:{...n.portLayout,[portId]:anchor}}:n)}:current);setStatus('端口位置已更新 · 连线保持不变');},[]);
 useEffect(()=>{const key=(e:KeyboardEvent)=>{if((e.target as HTMLElement)?.closest('input,textarea,select,[contenteditable=true]'))return;if(e.key==='Escape')setLayoutMode(false);if(e.code==='KeyP'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!e.repeat){e.preventDefault();setLayoutMode(v=>!v);}};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key);},[]);
 const [health,setHealth]=useState('');
 const [selectedIds,setSelectedIds]=useState<string[]>([]),[selectedEdgeIds,setSelectedEdgeIds]=useState<string[]>([]);
 const selected=selectedIds.length===1?selectedIds[0]:null;
 const [boxSelect,setBoxSelect]=useState(true),[autoSnap,setAutoSnap]=useState(true),[guides,setGuides]=useState<Guide[]>([]);
const canvas=useRef<HTMLDivElement>(null);const serial=useRef(0);
 const job=async(fn:()=>Promise<void>)=>{setBusy(true);setError('');try{await fn();}catch(e){setError(String(e instanceof Error?e.message:e));setStatus('需要处理');}finally{setBusy(false);}};
 useEffect(()=>{api('health').then(h=>{setHealth(h.slang);setStatus('就绪');}).catch(e=>setError(String(e)));},[]);
 const log=(s:string)=>setMessages(m=>[s,...m].slice(0,40));
 const loadDemo=()=>job(async()=>{setP(await api('demo'));setStatus('示例已载入');log('载入 6 路 generate、数组分线与 48-bit 向量示例');});
 const openEdit=useCallback((id:string)=>{const n=p?.nodes.find(n=>n.id===id);if(n){setDraft(structuredClone(n));setOverText(Object.entries(n.overrides||{}).map(([k,v])=>`${k} = ${v}`).join('\n'));setPortsText(JSON.stringify(n.ports||[],null,2));setEdit(id);}},[p?.nodes]);
 const toggle=useCallback((id:string)=>setP(p=>p?({...p,nodes:p.nodes.map(n=>n.id===id?{...n,view:n.view==='expanded'?'stacked':'expanded'}:n)}):p),[]);
 const [flowNodes,setFlowNodes,onChanges]=useNodesState<BlockNode>([]);
 const nodesInitialized=useNodesInitialized();
 const sourceRef=useRef<Project['inputs']|null>(null);
 const pendingViewport=useRef<Project['viewport']|'fit'|null>(null);
 useEffect(()=>{
   const sourceChanged=sourceRef.current!==(p?.inputs??null);
   sourceRef.current=p?.inputs??null;
   if(sourceChanged){pendingViewport.current=p?.viewport?.saved?p.viewport:'fit';setSelectedIds([]);setSelectedEdgeIds([]);setGuides([]);}
   setFlowNodes(previous=>reconcileCanvasNodes(p?.nodes||[],previous,{onEdit:openEdit,onToggle:toggle,onPortMove:movePort,layoutMode},new Set(sourceChanged?[]:selectedIds),sourceChanged));
 },[p?.nodes,p?.inputs,selectedIds,openEdit,toggle,movePort,layoutMode,setFlowNodes]);
 useEffect(()=>{
   if(!p||!nodesInitialized||!pendingViewport.current||flowNodes.length!==p.nodes.length||flowNodes.some((n,i)=>n.data.block!==p.nodes[i]))return;
   const viewport=pendingViewport.current;
   const frame=requestAnimationFrame(()=>{pendingViewport.current=null;if(viewport==='fit')void fitView({padding:0.18});else if(viewport)void setViewport(viewport);});
   return()=>cancelAnimationFrame(frame);
 },[p?.nodes,flowNodes,nodesInitialized,fitView,setViewport]);
 const updateProject=(next:Project)=>{setP(next);setStatus('已修改 · 待检查');};
 const addModule=(module:string,position?:{x:number;y:number})=>{if(!p)return;job(async()=>{const used=new Set(p.nodes.map(n=>n.name));let i=0;while(used.has(`U_${module}_${i}`))i++;const node:Block={id:uid(),kind:'module',name:`U_${module}_${i}`,module,overrides:{},count:'1',view:'stacked',position:position||{x:250+serial.current++*35,y:100+serial.current*25}};const ready=await api('instance',{project:p,node});updateProject({...p,nodes:[...p.nodes,ready]});log(`添加 ${ready.name}，使用模块默认参数`);});};
 const addComponent=(kind:string)=>{if(!p)return;const id=uid(),w=8;const port=(name:string,shape=vector(w),role:Port['role']='target')=>({name,shape,role});let ps:Port[];
 if(kind==='split')ps=[port('in',vector(16)),port('high',vector(8),'source'),port('low',vector(8),'source')];
 else if(kind==='concat')ps=[port('high'),port('low'),port('out',vector(16),'source')];
 else if(kind==='reshape')ps=[port('in',vector(8,6)),port('out',vector(48),'source')];
 else ps=[port(kind==='output'?'in':'out',vector(w),kind==='output'?'target':'source')];
 let componentName=`${kind}_${serial.current++}`;while(p.nodes.some(n=>n.name===componentName))componentName=`${kind}_${serial.current++}`;const n:Block={id,kind,name:componentName,ports:ps,expression:"8'h00",position:{x:350,y:150}};updateProject({...p,nodes:[...p.nodes,n]});openEditLater(n);};
 function openEditLater(n:Block){setDraft(n);setPortsText(JSON.stringify(n.ports,null,2));setEdit(n.id);}
 const flowEdges=(p?.edges||[]).map(e=>({...e,selected:selectedEdgeIds.includes(e.id),sourceHandle:e.sourcePort,targetHandle:e.targetPort,type:'smoothstep',style:{stroke:'#68859c',strokeWidth:1.6}}));
 const connect=(c:Connection)=>{if(!p)return;const issue=connectionIssue(p,c);if(issue){setError(issue);setStatus('连线未建立');return;}const e={id:uid(),source:c.source,target:c.target,sourcePort:c.sourceHandle!,targetPort:c.targetHandle!};setP(current=>current&&!connectionIssue(current,c)?{...current,edges:[...current.edges,e]}:current);setError('');setStatus('连线已建立');log(`连接 ${p.nodes.find(n=>n.id===c.source)?.name}.${c.sourceHandle} → ${p.nodes.find(n=>n.id===c.target)?.name}.${c.targetHandle}`);};
 const selectionChanged=useCallback(({nodes,edges}:OnSelectionChangeParams<BlockNode>)=>{
   const ids=nodes.map(n=>n.id).sort(), edgeIds=edges.map(e=>e.id).sort();
   setSelectedIds(old=>old.join('|')===ids.join('|')?old:ids);
   setSelectedEdgeIds(old=>old.join('|')===edgeIds.join('|')?old:edgeIds);
 },[]);
 const edgeChanges=useCallback((changes:EdgeChange[])=>setSelectedEdgeIds(old=>{
   const ids=new Set(old);for(const change of changes){if(change.type==='select'){if(change.selected)ids.add(change.id);else ids.delete(change.id);}if(change.type==='remove')ids.delete(change.id);}return [...ids].sort();
 }),[]);
 const selectAll=()=>{if(!p||busy)return;setFlowNodes(nodes=>nodes.map(n=>({...n,selected:true})));setSelectedIds(p.nodes.map(n=>n.id).sort());setSelectedEdgeIds(p.edges.map(e=>e.id).sort());setStatus('已全选 · 可对齐或删除');};
 const deleteSelection=()=>{if(busy)return;void deleteElements({nodes:selectedIds.map(id=>({id})),edges:selectedEdgeIds.map(id=>({id}))});};
 const removeSelected=useCallback(({nodes,edges}:{nodes:{id:string}[];edges:{id:string}[]})=>{
   const ids=new Set(nodes.map(n=>n.id)),edgeIds=new Set(edges.map(e=>e.id));
   setP(current=>current?removeGraphItems(current,ids,edgeIds):current);
   setSelectedIds(old=>old.filter(id=>!ids.has(id)));setSelectedEdgeIds(old=>old.filter(id=>!edgeIds.has(id)));
   setGuides([]);setStatus(`已删除 ${nodes.length} 个节点、${edges.length} 条连线`);
 },[]);
 const storePositions=(nodes:BlockNode[])=>{const positions=new Map(nodes.map(n=>[n.id,n.position]));setP(current=>current?{...current,nodes:current.nodes.map(n=>({...n,position:positions.get(n.id)??n.position}))}:current);};
 const arrange=(alignment:Alignment)=>{
   const nodes=alignNodes(flowNodes,new Set(selectedIds),alignment);setFlowNodes(nodes);storePositions(nodes);setGuides([]);
   setStatus(`${selectedIds.length} 个节点 · ${alignmentActions.find(a=>a.value===alignment)?.label}`);
 };
 const dragNodes=(dragged:BlockNode[])=>{const moving=new Map(dragged.map(n=>[n.id,n.position]));return getNodes().map(n=>moving.has(n.id)?{...n,position:moving.get(n.id)!}:n);};
 const onDrag:OnNodeDrag<BlockNode>=(event,node,dragged)=>{
   const moving=dragged.length?dragged:[node],nodes=dragNodes(moving);
   if(!autoSnap||event.altKey){setGuides([]);return;}
   const snapped=snapNodes(nodes,new Set(moving.map(n=>n.id)),getZoom());setFlowNodes(snapped.nodes);setGuides(snapped.guides);
 };
 const onDragStop:OnNodeDrag<BlockNode>=(event,node,dragged)=>{
   const moving=dragged.length?dragged:[node],nodes=dragNodes(moving);
   const next=autoSnap&&!event.altKey?snapNodes(nodes,new Set(moving.map(n=>n.id)),getZoom()).nodes:nodes;
   setFlowNodes(next);storePositions(next);setGuides([]);setStatus('节点位置已更新');
 };
 const snapshot=()=>({...p!,nodes:p!.nodes.map(n=>({...n,position:flowNodes.find(node=>node.id===n.id)?.position||n.position}))});
 const validate=()=>{if(!p)return;job(async()=>{const r=await api('analyze',{project:snapshot()});setP(r.project);setRtl(r.rtl);setMessages([...r.warnings,r.diagnostics||'slang 编译通过，无诊断']);setStatus(r.warnings.length?'检查完成 · 有未连接端口':'检查通过');setBottom('log');});};
 const save=()=>{if(!p)return;job(async()=>{const r=await api('export',{project:snapshot()});download(r.filename,r.text);setRtl(r.text);setStatus('已导出顶层工程');log('RTL + 压缩工程信息已写入 '+r.filename);});};
 const restore=(file:File)=>job(async()=>{const project=await api('restore',{text:await file.text()});setP(project);setStatus('工程已恢复');log('从顶层专属注释区恢复完整工程');});
 const saveNode=()=>{if(!p||!draft)return;job(async()=>{let n={...draft};if(n.kind==='module'){const overrides:Record<string,string>={};for(const line of overText.split('\n').filter(x=>x.trim())){const idx=line.indexOf('=');if(idx<1)throw Error('参数格式：NAME = expression');overrides[line.slice(0,idx).trim()]=line.slice(idx+1).trim();}n=await api('instance',{project:p,node:{...n,overrides}});}else{n.ports=JSON.parse(portsText);n=await api('component',{project:p,node:n});}const next={...p,nodes:p.nodes.map(x=>x.id===n.id?n:x)};updateProject(next);setEdit(null);log(`更新 ${n.name}；现有连接将在检查时重新验证`);});};
 const importBundle=()=>job(async()=>{const next=await api('import',{filelist:entry,files:Object.keys(bundle).length?bundle:undefined,directory:rootPath||undefined});setP(next);setImportOpen(false);setStatus('filelist 已导入');log(`发现 ${next.modules.length} 个 module，保留 ${Object.keys(next.inputs.files).length} 个输入文件`);});
 return <div className="studio" onKeyDown={e=>{if((e.ctrlKey||e.metaKey)&&e.code==='KeyA'&&!edit&&!paramsOpen&&!importOpen&&!(e.target as HTMLElement).closest('input,textarea,select,[contenteditable=true]')){e.preventDefault();selectAll();}}}>
 <header><div className="brand"><span className="logo">V<span>▦</span></span>verilinx <span className="version">STUDIO / 0.1.3</span></div><div className="header-center"><span className="live-dot"/>slang {health||'…'} <span className="divider">/</span> SystemVerilog</div><a href="/review/" target="_blank"><Smartphone size={15}/> HTML 检视版</a><button onClick={()=>setImportOpen(true)} disabled={busy}><FolderOpen size={15}/>导入 filelist</button><label className="button"><Upload size={15}/>打开工程<input type="file" accept=".sv,.v" hidden onChange={e=>e.target.files?.[0]&&restore(e.target.files[0])}/></label><button className="primary" disabled={!p||busy} onClick={save}><Download size={15}/>导出顶层</button></header>
 <div className="workspace"><aside className="library"><div className="section-label">WORKSPACE <PanelLeft size={14}/></div><h2>设计资源</h2><div className="library-tabs"><button className={tab==='modules'?'active':''} onClick={()=>setTab('modules')}>模块库</button><button className={tab==='components'?'active':''} onClick={()=>setTab('components')}>信号组件</button></div><input className="search" placeholder="搜索模块…" value={search} onChange={e=>setSearch(e.target.value)}/>
 {tab==='modules'?<><div className="category"><ChevronRight size={12}/>RTL MODULES <span>{p?.modules.length||0}</span></div>{p?.modules.filter(m=>m.name.includes(search)).map(m=><div className="module-item" key={m.name} draggable onDragStart={e=>e.dataTransfer.setData('module',m.name)}><div className="module-symbol"><Box size={19}/></div><div><b>{m.name}</b><small>SystemVerilog module</small></div><button title="添加模块" disabled={busy} onClick={()=>addModule(m.name)}><Plus size={16}/></button></div>)}{!p&&<p className="muted library-empty">导入全量 filelist 后，模块会显示在这里。</p>}</>:['input','output','constant','split','concat','reshape'].map(k=><button className="component-item" key={k} onClick={()=>addComponent(k)} disabled={!p}><GitBranch size={17}/><div><b>{{input:'顶层输入',output:'顶层输出',constant:'常量',split:'分线器 / Split',concat:'集线器 / Concat',reshape:'数组 ↔ 向量'}[k]}</b><small>{k}</small></div><Plus size={15}/></button>)}
 <div className="library-note"><Layers size={17}/><b>结构与显示分离</b><p>叠放 / 展开保持相同网络。通过分线器指定 lane 与 bit 的映射。</p></div><button className="demo-button" onClick={loadDemo} disabled={busy}>载入六路示例 <ArrowRight size={14}/></button></aside>
 <main><div className="canvas-toolbar"><div><span className="file-icon"><GitBranch size={15}/></span><b>{p?.name||'未命名工程'}</b><span className="file-type">BLOCK DESIGN</span></div><div><button className={layoutMode?'layout-toggle active':'layout-toggle'} aria-pressed={layoutMode} disabled={!p} onClick={()=>setLayoutMode(v=>!v)} title="P 切换；也可 Shift+拖动单个端口"><Move size={14}/>端口布局</button><button disabled={!p||busy} onClick={()=>{setParamDraft(p?.parameters||'');setParamsOpen(true);}}><Code2 size={14}/>顶层参数</button><button onClick={validate} disabled={!p||busy}><Check size={15}/>检查设计</button></div></div>
 <div className="arrange-toolbar" role="toolbar" aria-label="画布选择与对齐">
 <button aria-pressed={boxSelect} title="空白处拖动框选；关闭后拖动画布" disabled={!p||busy} onClick={()=>setBoxSelect(v=>!v)}><MousePointer2 size={14}/>框选</button>
 <button title="全选节点与连线（Ctrl / ⌘ + A）" disabled={!p||busy} onClick={selectAll}><Scan size={14}/>全选</button>
 <button className="danger" title="删除选中的节点和连线（Delete / Backspace）" disabled={busy||(!selectedIds.length&&!selectedEdgeIds.length)} onClick={deleteSelection}><Trash2 size={14}/>删除选中</button>
 <span className="arrange-separator"/>
 {alignmentActions.map(({value,label,Icon})=><button key={value} aria-label={label} title={label} disabled={busy||selectedIds.length<2||layoutMode} onClick={()=>arrange(value)}><Icon size={16}/><span className="align-button-label">{label}</span></button>)}
 <select className="alignment-select" aria-label="批量对齐方式" value="" disabled={busy||selectedIds.length<2||layoutMode} onChange={e=>arrange(e.target.value as Alignment)}><option value="" disabled>对齐…</option>{alignmentActions.map(a=><option value={a.value} key={a.value}>{a.label}</option>)}</select>
 <span className="arrange-separator"/>
 <button aria-pressed={autoSnap} title="拖动时吸附边缘和中心，Alt 临时关闭" disabled={!p} onClick={()=>{setAutoSnap(v=>!v);setGuides([]);}}><Magnet size={14}/>自动对齐</button>
 <span className="selection-count" aria-live="polite">{selectedIds.length} 节点 · {selectedEdgeIds.length} 连线已选</span>
 </div>
 <div className="canvas" ref={canvas} tabIndex={0} aria-label="模块设计画布" onPointerDownCapture={()=>canvas.current?.focus({preventScroll:true})} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();const name=e.dataTransfer.getData('module');if(name)addModule(name,screenToFlowPosition({x:e.clientX,y:e.clientY}));}}>
 <ReactFlow nodes={flowNodes} edges={flowEdges} nodeTypes={nodeTypes} onNodesChange={onChanges} onEdgesChange={edgeChanges} onSelectionChange={selectionChanged} onDelete={removeSelected} onNodeDrag={onDrag} onNodeDragStop={onDragStop} onSelectionDrag={(e,nodes)=>onDrag(e.nativeEvent,nodes[0],nodes)} onSelectionDragStop={(e,nodes)=>onDragStop(e.nativeEvent,nodes[0],nodes)} selectionOnDrag={boxSelect&&!layoutMode} selectionKeyCode={null} selectionMode={SelectionMode.Partial} multiSelectionKeyCode={['Shift','Control','Meta']} panOnDrag={boxSelect?[1,2]:[0,1,2]} panActivationKeyCode="Space" onConnect={connect} nodesDraggable={!layoutMode} nodesConnectable={!layoutMode} connectionRadius={28} connectionDragThreshold={2} connectOnClick={true} onConnectStart={()=>{setError('');setStatus('拖动到输入箭头，或单击另一端口完成连线');}} onConnectEnd={(_,state)=>{if(!layoutMode&&state.fromHandle&&state.toHandle&&!state.isValid){setError('请连接输出箭头与输入箭头。');setStatus('连线未建立');}}} onNodeDoubleClick={(_,n)=>openEdit(n.id)} onMoveEnd={(_,v)=>setP(p=>p?({...p,viewport:{...v,saved:true}}):p)} minZoom={0.15} maxZoom={1.7} deleteKeyCode={busy||edit!==null||paramsOpen||importOpen?null:['Backspace','Delete']}><Background gap={20} size={1} color="#cbd7d6"/><Controls showInteractive={false}/><MiniMap nodeColor={n=>(n.data.block as Block).kind==='module'?'#128071':'#bbc9d3'} maskColor="#f5f8f6b8"/></ReactFlow>
 <AlignmentGuides guides={guides}/>
 {!p&&<div className="welcome"><div className="welcome-icon"><Layers size={32}/></div><span className="eyebrow">FROM RTL TO CONNECTIONS</span><h1>让模块连接，<br/>变得清晰。</h1><p>从一个 filelist 开始，搭建你的参数化 RTL 设计。</p><button className="primary" onClick={loadDemo} disabled={busy}>探索六路 generate 示例 <ArrowRight size={16}/></button><button onClick={()=>setImportOpen(true)}>导入自己的 filelist</button><small>slang 驱动分析 · 顶层文件即工程</small></div>}
 {p&&<div className="canvas-hint">{layoutMode?'端口布局：拖动箭头沿四边滑动 · P / Esc 退出':'空白拖动框选 · Shift 多选 · Space+拖动平移 · 拖箭头连线'}</div>}
 </div>
 <div className="console"><div className="console-tabs"><button className={bottom==='log'?'active':''} onClick={()=>setBottom('log')}>诊断与活动 <span>{messages.length}</span></button><button className={bottom==='rtl'?'active':''} onClick={()=>setBottom('rtl')}>生成的 RTL</button><span className="console-right">{busy?'slang 分析中…':'单编译单元 · --single-unit'}</span></div><pre>{bottom==='rtl'?(rtl||'检查设计后在此预览生成的 SystemVerilog。'):(messages.join('\n\n')||'准备就绪。导入 filelist 或载入示例开始。')}</pre></div>
 </main><aside className="inspector"><div className="section-label">INSPECTOR <Settings2 size={14}/></div><h2>设计概览</h2><div className="project-card"><span className="live-dot"/>当前工程<b>{p?.name||'等待导入'}</b><small>{p?.inputs.entry||'—'}</small></div><div className="stats"><div><strong>{p?.nodes.filter(n=>n.kind==='module').length||0}</strong><span>模块组</span></div><div><strong>{p?.edges.length||0}</strong><span>连接</span></div></div><h3>顶层 PARAMETERS</h3><pre className="param-summary">{p?.parameters||'尚未定义参数'}</pre><button className="wide" disabled={!p} onClick={()=>{setParamDraft(p?.parameters||'');setParamsOpen(true);}}>编辑参数 <Code2 size={14}/></button><h3>连接约定</h3><p className="muted">聚合端口保留数组形状。位拼接按组件端口列表从上到下排列，第一项对应最高位。</p><div className="legend"><i/>RTL module<i/>Signal adapter</div>{selected&&<><h3>已选节点</h3><b>{p?.nodes.find(n=>n.id===selected)?.name}</b><button className="wide" onClick={()=>openEdit(selected)}>配置节点 <Settings2 size={14}/></button><button className="wide" onClick={()=>setP(current=>current?{...current,nodes:current.nodes.map(n=>n.id===selected?{...n,portLayout:{}}:n)}:current)}>重置端口位置 <Move size={14}/></button><button className="wide danger" disabled={busy} onClick={deleteSelection}>删除节点 <Trash2 size={14}/></button></>}{selectedIds.length>1&&<><h3>已选节点</h3><b>{selectedIds.length} 个节点</b><p className="muted">使用上方工具栏对齐，或按 Delete 批量删除。Shift+单击可增减选中项。</p></>}</aside></div>
 <footer><span><span className={'live-dot '+(error?'bad':'')}/>{busy?'正在处理…':status}</span><span>{p?Object.keys(p.inputs.files).length+' 个输入文件 · ':''}表达式保留 / 常量展开</span><span>VERILINX · RTL COMPOSITION</span></footer>
 {error&&<div className="error-toast"><b>操作未完成</b><pre>{error}</pre><button onClick={()=>setError('')}><X size={16}/></button></div>}
 {edit&&draft&&<div className="modal-backdrop"><section className="modal"><div className="modal-heading"><div><span className="eyebrow">CONFIGURE BLOCK</span><h2>{draft.module||draft.kind}</h2></div><button onClick={()=>setEdit(null)}><X size={19}/></button></div><label>实例 / 节点名称<input value={draft.name} onChange={e=>setDraft({...draft,name:e.target.value})}/></label>{draft.kind==='module'?<><label>参数覆盖 · 每行 NAME = expression<textarea rows={5} value={overText} onChange={e=>setOverText(e.target.value)} placeholder="WIDTH = WIDTH\nOFFSET = 1"/></label><small>可填写数字、顶层参数、有效宏或常量表达式。留空使用模块默认值。</small><div className="two-cols"><label>generate 数量表达式<input value={draft.count||'1'} onChange={e=>setDraft({...draft,count:e.target.value})}/></label><label>显示方式<select value={draft.view||'stacked'} onChange={e=>setDraft({...draft,view:e.target.value})}><option value="stacked">叠放</option><option value="expanded">展开</option></select></label></div><div className="resolved">{draft.analysis?.parameters.map(x=><span key={x.name}>{x.name}<b>{x.display}</b></span>)}</div></>:<><AdapterEditor value={portsText} onChange={setPortsText}/><small>role: source / target；packed、unpacked 填写 [左界,右界]。列表顺序决定最高位到最低位的映射。</small>{draft.kind==='constant'&&<label>常量表达式<input value={draft.expression||''} onChange={e=>setDraft({...draft,expression:e.target.value})}/></label>}<button onClick={()=>{const ps=JSON.parse(portsText) as Port[];setPortsText(JSON.stringify([...ps].reverse(),null,2));}}>反转端口顺序</button></>}<div className="modal-actions"><button onClick={()=>setEdit(null)}>取消</button><button className="primary" onClick={saveNode} disabled={busy}>{busy?'解析中…':'确认并解析'}</button></div></section></div>}
 {paramsOpen&&<div className="modal-backdrop"><section className="modal"><div className="modal-heading"><h2>顶层参数</h2><button onClick={()=>setParamsOpen(false)}><X/></button></div><label>顶层模块名<input value={p?.name||''} onChange={e=>p&&setP({...p,name:e.target.value})}/></label><label>每行一条 parameter，不需要逗号或分号<textarea rows={9} value={paramDraft} onChange={e=>setParamDraft(e.target.value)} spellCheck={false}/></label><p className="muted">由 slang 解析。修改后重新求值所有实例，连接形状变化会在检查时报告。</p><div className="modal-actions"><button onClick={()=>setParamsOpen(false)}>取消</button><button className="primary" disabled={busy} onClick={()=>job(async()=>{const next={...snapshot(),parameters:paramDraft};await api('parameters',{project:next});for(let i=0;i<next.nodes.length;i++)if(next.nodes[i].kind==='module')next.nodes[i]=await api('instance',{project:next,node:next.nodes[i]});updateProject(next);setParamsOpen(false);})}>应用并重新分析</button></div></section></div>}
 {importOpen&&<div className="modal-backdrop"><section className="modal"><div className="modal-heading"><h2>导入全量 filelist</h2><button onClick={()=>setImportOpen(false)}><X/></button></div><p className="muted">选择源码目录，保留其中的嵌套 filelist。移动端也可通过 HTML 检视版上传文件包。</p><label>上传工程目录<input type="file" multiple {...({webkitdirectory:''} as any)} onChange={e=>job(async()=>{const files=Array.from(e.target.files||[]);const out:Record<string,string>={};for(const f of files){const rel=f.webkitRelativePath.split('/').slice(1).join('/')||f.name;out[rel]=await f.text();}setBundle(out);})}/></label><small>{Object.keys(bundle).length} 个文件已选择</small><label>入口 filelist（相对工程目录）<input value={entry} onChange={e=>setEntry(e.target.value)}/></label><details><summary>使用服务器现有目录</summary><label>服务器项目根目录<input placeholder="/workspace/verilinx/examples" value={rootPath} onChange={e=>setRootPath(e.target.value)}/></label></details><div className="modal-actions"><button onClick={()=>setImportOpen(false)}>取消</button><button className="primary" disabled={busy} onClick={importBundle}>解析 filelist</button></div></section></div>}
 </div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><ReactFlowProvider><App/></ReactFlowProvider></React.StrictMode>);
