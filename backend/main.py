"""Local API and static serving for the React block editor."""
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
app = FastAPI(title='Verilinx API', version='0.1.6')
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
    project = import_files(ImportRequest(directory=str(BASE / 'demo' / 'example001')))
    project['name'] = 'example001_top'
    project['parameters'] = 'parameter int PERIOD = 25_000_000'

    for name, kind, x, y in (
        ('clk', 'input', 0, -65),
        ('rst_n', 'input', 0, 335),
        ('led_out', 'output', 1130, 120),
    ):
        source = kind == 'input'
        project['nodes'].append({
            'id': name, 'name': name, 'kind': kind, 'position': {'x': x, 'y': y},
            'ports': [{'name': 'out' if source else 'in', 'role': 'source' if source else 'target',
                       'shape': {'packed': [], 'unpacked': [], 'atom_width': 1}}],
        })
    for name, x, overrides in (
        ('counter', 380, {'PERIOD': 'PERIOD'}),
        ('led', 770, {}),
    ):
        node = {
            'id': name, 'kind': 'module', 'name': f'U_{name}', 'module': name,
            'overrides': overrides, 'count': '1', 'position': {'x': x, 'y': 120},
            'portLayout': {'clk': {'side': 'top', 'offset': .45},
                           'rst_n': {'side': 'bottom', 'offset': .45}},
        }
        project['nodes'].append(instance(project, node))

    project['edges'] = [
        {'id': f'{source}_{source_port}_{target}_{target_port}', 'source': source,
         'sourcePort': source_port, 'target': target, 'targetPort': target_port}
        for source, source_port, target, target_port in (
            ('clk', 'out', 'counter', 'clk'),
            ('clk', 'out', 'led', 'clk'),
            ('rst_n', 'out', 'counter', 'rst_n'),
            ('rst_n', 'out', 'led', 'rst_n'),
            ('counter', 'tick', 'led', 'tick'),
            ('led', 'led_out', 'led_out', 'in'),
        )
    ]
    return project


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


if (BASE/'frontend/dist').is_dir():
    app.mount('/',StaticFiles(directory=BASE/'frontend/dist',html=True),name='editor')
else:
    @app.get('/')
    def index():return {'message':'Build frontend first: npm --prefix frontend run build'}
