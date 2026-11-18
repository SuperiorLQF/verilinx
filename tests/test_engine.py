import copy
import json
from pathlib import Path
import re
import pytest
from fastapi.testclient import TestClient
from backend.main import app, demo, analyze, export, ProjectRequest, import_files, ImportRequest
from backend.engine import (instance, evaluate, encode_project, decode_project,
                            compile_project, worker, atoms, declarations, safe_path)


@pytest.fixture(scope='module')
def example():
    return demo()


def simple(files, entry='project.f'):
    return import_files(ImportRequest(files=files,filelist=entry))


def node(module='m', **kw):
    return dict(id='a',kind='module',name='U_m_0',module=module,
                overrides={},count='1',position={'x':10,'y':20},**kw)


def test_nested_filelist_and_source_macro_scope():
    p=simple({'project.f':'defs.v\n-f sub.f\nundef.v\nlast.sv\n',
              'defs.v':'`define W 13\n', 'sub.f':'-F ip/files.f\n',
              'ip/files.f':'m.sv\n','ip/m.sv':'module m #(parameter int W=`W)(output logic [W-1:0] q); endmodule',
              'undef.v':'`undef W\n',
              'last.sv':'`ifdef W\nthis_is_invalid\n`endif\nmodule last; endmodule'})
    n=instance(p,node())
    assert n['analysis']['ports'][0]['shape']['packed']==[[12,0]]
    assert p['inputs']['files']['project.f']=='defs.v\n-f sub.f\nundef.v\nlast.sv\n'
    with pytest.raises(ValueError,match='unknown macro|Unknown macro|W'):
        evaluate(p,['`W'])


def test_filelist_D_U_are_global_not_brackets():
    with pytest.raises(ValueError,match='unknown macro'):
        simple({'project.f':'+define+W=9\n-f sub.f\n-UW\n',
                'sub.f':'m.sv', 'm.sv':'module m #(parameter int P=`W)(); endmodule'})


def test_parameter_expression_signed_width_and_unknown():
    p=simple({'project.f':'m.sv','m.sv':"module m #(parameter int P=1, parameter logic [7:0] MASK=0)(); endmodule"})
    p['parameters']='parameter int WIDTH = 16\nparameter int DOUBLE = WIDTH * 2 // no punctuation'
    n=node();n['overrides']={'P':"4'b1111 << 1",'MASK':"8'b10xz0011"}
    n=instance(p,n)
    values={v['name']:v for v in n['analysis']['parameters']}
    assert values['P']['value']==30 # target int context must precede shift
    assert values['MASK']['value'] is None
    assert values['MASK']['width']==8
    assert evaluate(p,['DOUBLE'])[0]['value']==32
    assert evaluate(p,["-8'sd3"])[0]['value']==-3


def test_parameter_dependent_type_recomputed():
    p=simple({'project.f':'m.sv','m.sv':'module m #(parameter int W=4, parameter logic [W-1:0] MASK=0)(); endmodule'})
    n=node();n['overrides']={'W':'8','MASK':"'1"}
    result=instance(p,n)
    mask=next(x for x in result['analysis']['parameters'] if x['name']=='MASK')
    assert mask['width']==8 and mask['value']==255


def test_unknown_override_and_bad_parameter_error(example):
    n=node('processor');n['overrides']={'NO_SUCH_PARAM':'3'}
    with pytest.raises(ValueError,match='Unknown parameter'):
        instance(example,n)
    p=copy.deepcopy(example);p['parameters']='parameter int WIDTH = ;'
    with pytest.raises(ValueError):
        evaluate(p,[])


def test_full_demo_export_and_lossless_restore(example):
    req=ProjectRequest(project=copy.deepcopy(example))
    result=export(req)
    assert 'for (genvar i=0; i<(LANES)' in result['text']
    assert '.WIDTH(WIDTH)' in result['text']
    assert '// verilinx prj begin' in result['text']
    p=decode_project(result['text'])
    assert p['nodes']==example['nodes']
    assert p['inputs']==example['inputs']
    assert not analyze(ProjectRequest(project=p))['warnings']
    assert worker(p,'validate',text=result['text'],top=p['name'])['ok']


def test_corrupt_project_checksum_and_size(example):
    saved=encode_project(example)
    damaged=re.sub(r'sha256:[0-9a-f]{64}','sha256:'+'0'*64,saved)
    with pytest.raises(ValueError,match='checksum'):
        decode_project(damaged)
    with pytest.raises(ValueError):
        decode_project(saved+saved)
    with pytest.raises(ValueError):
        decode_project(saved.replace('format: 1','format: 99'))


def test_shapes_and_bit_order():
    sh={'packed':[[7,0]],'unpacked':[[0,1]],'atom_width':1}
    assert atoms('x',sh)==[f'x[{lane}][{bit}]' for lane in range(2) for bit in range(7,-1,-1)]
    assert atoms('x',{'packed':[[0,2]],'unpacked':[],'atom_width':1})==['x[0]','x[1]','x[2]']


def test_adapter_mappings_use_msb_first(example):
    rtl,_=compile_project(copy.deepcopy(example))
    # Node 2 is reshape: unpacked lane 0 maps to highest vector byte.
    assert 'assign __vl_n2_p1[47] = __vl_n2_p0[0][7];' in rtl
    assert 'assign __vl_n2_p1[0] = __vl_n2_p0[5][0];' in rtl


def test_duplicate_driver_and_lane_overlap(example):
    p=copy.deepcopy(example);e=copy.deepcopy(p['edges'][0]);e['id']='duplicate';p['edges'].append(e)
    with pytest.raises(ValueError,match='Multiple drivers'):
        compile_project(p)
    p=copy.deepcopy(example)
    p['nodes'].append({'id':'single','name':'single','kind':'input','position':{'x':0,'y':0},
                       'ports':[{'name':'out','role':'source','shape':{'packed':[[7,0]],'unpacked':[],'atom_width':1}}]})
    p['edges'].append({'id':'extra','source':'single','sourcePort':'out','target':'processor','targetPort':'data_in@0'})
    with pytest.raises(ValueError,match='Multiple drivers'):
        compile_project(p)


def test_wrong_shape_and_missing_connection(example):
    p=copy.deepcopy(example);p['nodes'][0]['overrides']['WIDTH']='9'
    with pytest.raises(ValueError,match='shape mismatch'):
        compile_project(p)
    p=copy.deepcopy(example);p['edges']=p['edges'][1:]
    with pytest.raises(ValueError,match='Connect all required inputs'):
        export(ProjectRequest(project=p))


def test_generated_varying_width_and_index(example):
    p=copy.deepcopy(example);n=p['nodes'][0];n['overrides']={'WIDTH':'WIDTH+i'}
    p['nodes']=[n];p['edges']=[]
    result=analyze(ProjectRequest(project=p))
    a=result['project']['nodes'][0]['analysis']
    assert not a['homogeneous'] and len(a['variants'])==6
    widths=[next(x for x in v['ports'] if x['name']=='data_out')['shape']['packed'][0][0]+1 for v in a['variants']]
    assert widths==[8,9,10,11,12,13]
    assert 'if (i==5) begin : lane_5' in result['rtl']
    assert all('@' in x for x in result['warnings'])


def test_path_escape_and_duplicate_names(example,tmp_path):
    with pytest.raises(ValueError,match='escapes'):
        safe_path(tmp_path,'../escape')
    p=copy.deepcopy(example);p['nodes'][1]['name']=p['nodes'][0]['name']
    with pytest.raises(ValueError,match='Duplicate'):
        compile_project(p)


def test_http_shared_clients_and_export_roundtrip():
    with TestClient(app) as client:
        assert client.get('/api/health').json()['slang']=='12.1.0'
        assert client.get('/review/').status_code==200
        assert 'HTML REVIEW' in client.get('/review/').text
        assert client.get('/review/app.js').status_code==200
        assert client.get('/').status_code==200
        p=client.get('/api/demo').json()
        out=client.post('/api/export',json={'project':p})
        assert out.status_code==200,out.text
        restored=client.post('/api/restore',json={'text':out.json()['text']})
        assert restored.status_code==200
        assert restored.json()['inputs']==p['inputs']
        assert client.post('/api/restore',json={'text':'module fake; endmodule'}).status_code==422


def test_constant_keeps_context_and_expression(example):
    p=copy.deepcopy(example)
    p['nodes']=[{'id':'const','kind':'constant','name':'all_ones','expression':"'1",'position':{'x':0,'y':0},
                 'ports':[{'name':'out','role':'source','shape':{'packed':[[7,0]],'unpacked':[],'atom_width':1}}]}]
    p['edges']=[]
    r=analyze(ProjectRequest(project=p))
    assert "assign __vl_n0_p0 = '1;" in r['rtl']


def test_concat_order_and_ascending_ranges(example):
    p=copy.deepcopy(example)
    sh={'packed':[[0,7]],'unpacked':[],'atom_width':1}
    out={'packed':[[15,0]],'unpacked':[],'atom_width':1}
    p['nodes']=[{'id':'join','kind':'concat','name':'join','position':{'x':0,'y':0},'ports':[
        {'name':'first','role':'target','shape':sh},
        {'name':'second','role':'target','shape':sh},
        {'name':'out','role':'source','shape':out}]}]
    p['edges']=[]
    rtl,_=compile_project(p)
    assert 'assign __vl_n0_p2[15] = __vl_n0_p0[0];' in rtl
    assert 'assign __vl_n0_p2[0] = __vl_n0_p1[7];' in rtl
    assert worker(p,'validate',text=rtl,top=p['name'])['ok']


def test_invalid_component_payload_is_validation_error(example):
    p=copy.deepcopy(example);p['nodes'][1]['ports']={'invalid':'not a list'}
    with TestClient(app) as client:
        result=client.post('/api/analyze',json={'project':p})
        assert result.status_code==422


def test_optional_https_access_link(monkeypatch):
    monkeypatch.setenv('VERILINX_ACCESS_TOKEN','test-token-at-least-24-characters')
    with TestClient(app,base_url='https://testserver') as client:
        assert client.get('/healthz').json()=={'ok':True}
        assert client.get('/api/health').status_code==401
        login=client.get('/review/?access=test-token-at-least-24-characters',follow_redirects=False)
        assert login.status_code==303
        assert 'access=' not in login.headers['location']
        assert 'HttpOnly' in login.headers['set-cookie']
        assert 'Secure' in login.headers['set-cookie']
        assert client.get('/review/').status_code==200
        assert client.get('/api/health').status_code==200


def test_port_layout_roundtrip_does_not_change_rtl(example):
    p=copy.deepcopy(example)
    p['nodes'][0]['portLayout']={'clk':{'side':'top','offset':.3},'data_out':{'side':'bottom','offset':.72}}
    original=analyze(ProjectRequest(project=example))['rtl']
    result=export(ProjectRequest(project=p))
    assert result['text'].startswith(original)
    restored=decode_project(result['text'])
    assert restored['nodes'][0]['portLayout']==p['nodes'][0]['portLayout']


def test_frozen_worker_command(monkeypatch):
    import backend.engine as engine
    monkeypatch.setattr(engine.sys,'frozen',True,raising=False)
    assert engine.worker_command()==[engine.sys.executable,'--slang-worker']


def test_wire_bends_and_absolute_positions_saved_in_top_file(example):
    from backend.main import restore, TextRequest
    original,_=compile_project(copy.deepcopy(example))
    p=copy.deepcopy(example)
    positions=[{'x':-123.25+i*411.5,'y':88.125-i*34.75} for i in range(len(p['nodes']))]
    for n,position in zip(p['nodes'],positions):n['position']=position
    p['edges'][0]['points']=[{'x':-12.25,'y':130.5},{'x':42.75,'y':130.5},{'x':42.75,'y':240}]
    result=export(ProjectRequest(project=p))
    assert result['text'].startswith(original)
    assert '// verilinx prj begin' in result['text']
    loaded=restore(TextRequest(text=result['text']))
    assert [n['position'] for n in loaded['nodes']]==positions
    assert loaded['edges']==p['edges']
    assert loaded['inputs']==p['inputs']


def test_invalid_wire_geometry_is_rejected(example):
    from backend.engine import validate_project
    for points in [None,{},[{'x':True,'y':0}],[{'x':float('inf'),'y':0}],[{'x':0}],[{'x':10_000_001,'y':0}], [{'x':0,'y':0}]*257]:
        p=copy.deepcopy(example);p['edges'][0]['points']=points
        with pytest.raises(ValueError):validate_project(p)
