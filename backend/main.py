"""Shared local API for the React editor and buildless HTML review client."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from .engine import (WORKER, worker_command, MAX_BYTES, safe_path, worker, instance, evaluate,
                     compile_project, encode_project, decode_project, validate_project, validate_node)

BASE = Path(__file__).resolve().parents[1]
app = FastAPI(title='Verilinx API', version='0.1.4')
from .access import access_gate
app.middleware('http')(access_gate)


@app.exception_handler(ValueError)
async def invalid(_, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422, content={'detail': str(exc)})


@app.exception_handler(subprocess.TimeoutExpired)
async def timeout(_, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=422, content={'detail':'slang analysis exceeded the 25 second time limit'})


class ImportRequest(BaseModel):
    filelist: str = 'project.f'
    directory: str | None = None
    files: dict[str,str] = Field(default_factory=dict)
    env: dict[str,str] = Field(default_factory=dict)


class ProjectRequest(BaseModel):
    project: dict

    @field_validator('project')
    @classmethod
    def validate_contract(cls,p):
        validate_project(p)
        return p


class InstanceRequest(ProjectRequest):
    node: dict

    @field_validator('node')
    @classmethod
    def validate_contract_node(cls,n):
        validate_node(n)
        return n


class TextRequest(BaseModel):
    text: str


def catalog_directory(root, entry, env):
    request = {'root': str(root), 'entry':entry, 'mode':'catalog'}
    result = subprocess.run(worker_command(),input=json.dumps(request),
                            text=True,capture_output=True,timeout=25,env={**os.environ,**env})
    if result.returncode:
        raise ValueError('slang worker failed: '+result.stderr[-2000:])
    data = json.loads(result.stdout)
    if not data.get('ok'):
        raise ValueError(data.get('error') or data.get('diagnostics'))
    return data


@app.get('/healthz')
def healthz():
    return {'ok': True}


@app.get('/api/health')
def health():
    import pyslang
    return {'ok':True,'slang':pyslang.__version__}


@app.post('/api/import')
def import_files(req: ImportRequest):
    if req.files:
        if sum(len(x.encode()) for x in req.files.values()) > MAX_BYTES:
            raise ValueError('Input bundle exceeds 16 MiB')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name,text in req.files.items():
                p = safe_path(root,name);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
            safe_path(root,req.filelist)
            data = catalog_directory(root,req.filelist,req.env)
            files = req.files
    else:
        if not req.directory:
            raise ValueError('Select a source directory / JSON bundle, or specify a server project directory')
        root = Path(req.directory).resolve()
        if not root.is_dir():
            raise ValueError('Project directory does not exist')
        safe_path(root,req.filelist)
        data = catalog_directory(root,req.filelist,req.env)
        files = {}
        for name in data['dependencies']:
            p = Path(name)
            if not p.is_relative_to(root):
                raise ValueError('Dependency outside project root; choose a common parent project directory: '+name)
            files[str(p.relative_to(root))] = p.read_text()
        if sum(len(x.encode()) for x in files.values()) > MAX_BYTES:
            raise ValueError('Input bundle exceeds 16 MiB')
    project = {'schema':1,'name':'verilinx_top','parameters':'parameter int WIDTH = 8\nparameter int LANES = 6',
            'inputs':{'entry':req.filelist,'files':files,'env':req.env,'singleUnit':True},
            'modules':data['modules'],'nodes':[],'edges':[],'viewport':{'x':0,'y':0,'zoom':1},
            'compiler':{'name':'slang','version':data['version']}}
    worker(project,'catalog')  # Prove the captured bundle compiles without external files.
    return project


@app.get('/api/demo')
def demo():
    p = import_files(ImportRequest(directory=str(BASE/'examples')))
    def sh(w,lanes=0):
        return {'packed':[[w-1,0]] if w>1 else [],'unpacked':[[0,lanes-1]] if lanes else [],'atom_width':1,'signed':False}
    def port(name,shape,role):return {'name':name,'shape':shape,'role':role}
    n = {'id':'processor','kind':'module','name':'U_processor_0','module':'processor','overrides':{'WIDTH':'WIDTH'},
         'count':'LANES','view':'stacked','position':{'x':400,'y':180}}
    instance(p,n)
    p['nodes'] = [
        n,
        {'id':'split','kind':'split','name':'lane_split','ports':[port('in',sh(8,6),'target')]+[port('lane'+str(i),sh(8),'source') for i in range(6)],'position':{'x':750,'y':100}},
        {'id':'reshape','kind':'reshape','name':'pack_to_vector','ports':[port('in',sh(8,6),'target'),port('out',sh(48),'source')],'position':{'x':750,'y':470}},
        {'id':'bus','kind':'output','name':'data_bus','ports':[port('in',sh(48),'target')],'position':{'x':1060,'y':480}},
        {'id':'din','kind':'input','name':'data_in','ports':[port('out',sh(8,6),'source')],'position':{'x':50,'y':380}},
        {'id':'clocks','kind':'reshape','name':'clock_lanes','ports':[port('in',sh(6),'target'),port('out',sh(1,6),'source')],'position':{'x':220,'y':-150}},
        {'id':'clock_const','kind':'constant','name':'clock_ties','expression':"6'b111111",'ports':[port('out',sh(6),'source')],'position':{'x':-30,'y':-150}},
        {'id':'resets','kind':'reshape','name':'reset_lanes','ports':[port('in',sh(6),'target'),port('out',sh(1,6),'source')],'position':{'x':220,'y':620}},
        {'id':'reset_const','kind':'constant','name':'reset_ties','expression':"6'b111111",'ports':[port('out',sh(6),'source')],'position':{'x':-30,'y':620}}
    ]
    # Keep the demo meaningful: clock/reset are array ports for six generated instances.
    p['nodes'] = [x for x in p['nodes'] if x['id'] not in ('clock_const','reset_const')]
    p['nodes'] += [
        {'id':'clock_const','kind':'input','name':'clk_lanes','ports':[port('out',sh(6),'source')],'position':{'x':-30,'y':-150}},
        {'id':'reset_const','kind':'input','name':'rst_lanes','ports':[port('out',sh(6),'source')],'position':{'x':-30,'y':620}}]
    def edge(s,sp,t,tp):return {'id':f'{s}_{sp}_{t}_{tp}','source':s,'sourcePort':sp,'target':t,'targetPort':tp}
    p['edges'] = [edge('din','out','processor','data_in'),edge('processor','data_out','split','in'),
                  edge('processor','data_out','reshape','in'),edge('reshape','out','bus','in'),
                  edge('clock_const','out','clocks','in'),edge('clocks','out','processor','clk'),
                  edge('reset_const','out','resets','in'),edge('resets','out','processor','rst_n')]
    return p


@app.post('/api/instance')
def analyze_instance(req: InstanceRequest):
    if any(n['name']==req.node['name'] and n['id']!=req.node['id'] for n in req.project['nodes']):
        raise ValueError('Duplicate instance name')
    return instance(req.project,copy.deepcopy(req.node))


@app.post('/api/component')
def analyze_component(req: InstanceRequest):
    if req.node['kind']=='module':
        raise ValueError('Use /api/instance for modules')
    if any(n['name']==req.node['name'] and n['id']!=req.node['id'] for n in req.project['nodes']):
        raise ValueError('Duplicate node name')
    p=copy.deepcopy(req.project)
    p['nodes']=[copy.deepcopy(req.node)]
    p['edges']=[]
    rtl,_=compile_project(p)
    worker(p,'validate',text=rtl,top=p['name'])
    return p['nodes'][0]


@app.post('/api/parameters')
def parameters(req: ProjectRequest):
    evaluate(req.project,[])
    return {'ok':True}


@app.post('/api/analyze')
def analyze(req: ProjectRequest):
    p = copy.deepcopy(req.project)
    evaluate(p,[])
    rtl,warnings = compile_project(p)
    result = worker(p,'validate',text=rtl,top=p['name'])
    return {'project':p,'rtl':rtl,'warnings':warnings,'diagnostics':result['diagnostics'],'ok':True}


@app.post('/api/export')
def export(req: ProjectRequest):
    result = analyze(req)
    if result['warnings']:
        raise ValueError('Connect all required inputs before exporting:\n'+'\n'.join(result['warnings']))
    # Write no server file: browser downloads the returned text.
    return {'filename':result['project']['name']+'.sv','text':result['rtl']+'\n'+encode_project(result['project']),
            'diagnostics':result['diagnostics']}


@app.post('/api/restore')
def restore(req: TextRequest):
    p = decode_project(req.text.replace('\r\n','\n'))
    validate_project(p)
    # Validate restored inputs using the same native filelist parser.
    worker(p,'catalog')
    return p


app.mount('/review',StaticFiles(directory=BASE/'review',html=True),name='review')
if (BASE/'frontend/dist').is_dir():
    app.mount('/',StaticFiles(directory=BASE/'frontend/dist',html=True),name='editor')
else:
    @app.get('/')
    def index():return {'message':'Build frontend first: npm --prefix frontend run build','review':'/review/'}
