"""Project compiler: preserve expressions; resolve constants using slang, then -G."""
import base64
import hashlib
import itertools
import json
import math
import re
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

WORKER = Path(__file__).with_name('slang_worker.py')


def worker_command():
    # A frozen Linux app dispatches the same compiler worker without a Python install.
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--slang-worker']
    return [sys.executable, str(WORKER)]

MAX_BYTES = 16 * 1024 * 1024
IDENT = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_$]*$')


def identifier(name):
    if not IDENT.fullmatch(name) or name.startswith('vlx_internal_'):
        raise ValueError(f'Invalid / reserved identifier: {name}')
    return name


def validate_node(n):
    if not isinstance(n,dict) or any(not isinstance(n.get(k),str) for k in ('id','name','kind')):
        raise ValueError('Node requires string id, name and kind')
    if n['kind']=='module':
        if not isinstance(n.get('module'),str) or not isinstance(n.get('count','1'),str):
            raise ValueError('Module and count must be strings')
        if not isinstance(n.get('overrides',{}),dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in n.get('overrides',{}).items()):
            raise ValueError('Overrides must map parameter names to expression strings')
    else:
        if not isinstance(n.get('ports'),list) or not n['ports']:
            raise ValueError('Component ports must be a non-empty list')
        for p in n['ports']:
            if not isinstance(p,dict) or not isinstance(p.get('name'),str) or p.get('role') not in ('source','target') or not isinstance(p.get('shape'),dict):
                raise ValueError('Each component port needs a name, role and shape')
            validate_shape(p['shape'])


def validate_project(p):
    if p.get('schema')!=1 or not isinstance(p.get('name'),str) or not isinstance(p.get('parameters',''),str):
        raise ValueError('Invalid project schema, name or parameter text')
    inp=p.get('inputs',{})
    if not isinstance(inp.get('files'),dict) or not isinstance(inp.get('entry'),str):
        raise ValueError('Project must contain an input file bundle and entry filelist')
    if any(not isinstance(k,str) or not isinstance(v,str) for k,v in inp['files'].items()):
        raise ValueError('Input files must map paths to text')
    if not isinstance(p.get('nodes'),list) or not isinstance(p.get('edges'),list):
        raise ValueError('Nodes and edges must be lists')
    for n in p['nodes']:
        validate_node(n)
    for e in p['edges']:
        if not isinstance(e,dict) or any(not isinstance(e.get(k),str) for k in ('id','source','target','sourcePort','targetPort')):
            raise ValueError('Invalid connection record')
        if 'points' in e:
            points=e['points']
            if not isinstance(points,list) or len(points)>256:
                raise ValueError('Connection points must be a list of at most 256 bends')
            if any(not isinstance(point,dict) or any(type(point.get(axis)) not in (int,float)
                   or abs(point[axis])>10_000_000 or not math.isfinite(point[axis])
                   for axis in ('x','y')) for point in points):
                raise ValueError('Connection bend coordinates must be finite numbers within +/-10000000')


def safe_path(root, name):
    p = (root / name).resolve()
    if not p.is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes project root: {name}')
    return p


def worker(project, mode, **kwargs):
    with tempfile.TemporaryDirectory(prefix='verilinx_') as temp:
        root = Path(temp)
        for name, content in project['inputs']['files'].items():
            p = safe_path(root, name)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        import os
        req = dict(root=str(root), entry=project['inputs']['entry'], mode=mode, **kwargs)
        result = subprocess.run(worker_command(),input=json.dumps(req),text=True,
                                capture_output=True,timeout=25,
                                env={**os.environ,**project['inputs'].get('env',{})})
        if result.returncode:
            raise ValueError('slang worker failed: '+result.stderr[-2000:])
        result = json.loads(result.stdout)
        if not result.get('ok'):
            raise ValueError(result.get('error') or result.get('diagnostics') or 'slang failed')
        if any(not Path(dep).is_relative_to(root) for dep in result.get('dependencies',[])):
            raise ValueError('Dependency escapes archived project root. Use relative paths or bind filelist environment variables to relative paths.')
        result.pop('dependencies', None)
        return result


def declarations(text):
    """UI grammar: one parameter declaration per physical line, semicolon optional."""
    result = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('//'):
            result.append(line)
            continue
        code, sep, comment = line.partition('//')
        if not re.match(r'^\s*parameter\s+', code):
            raise ValueError('Each parameter line must begin with parameter')
        result.append(code.rstrip().rstrip(';') + ';' + ((' //' + comment) if sep else ''))
    return '\n'.join(result)


def evaluate(project, expressions, index=None, types=None):
    names = [f'vlx_internal_e{i}' for i in range(len(expressions))]
    text = 'module vlx_internal_eval;\n' + declarations(project.get('parameters', '')) + '\n'
    if index is not None:
        text += f'localparam int i = {index};\n'
    types = types or ['']*len(expressions)
    text += '\n'.join(f'localparam {t} {n} = ({e});' for n, e, t in zip(names, expressions, types))
    text += '\nendmodule\n'
    result = worker(project, 'evaluate', text=text, names=names)
    return [result['values'][n] for n in names]


def instance(project, node):
    validate_node(node)
    identifier(node['name']); identifier(node['module'])
    overrides = node.get('overrides', {})
    for k in overrides:
        identifier(k)
    count = evaluate(project,[node.get('count','1')])[0]['value']
    if count is None or not 1 <= count <= 64:
        raise ValueError('Generate count must resolve to an integer between 1 and 64')
    variants = []
    cache = {}
    prototype = worker(project,'instance',module=node['module'],overrides={})
    parameter_types = {p['name']:p['type'] if p['explicit_type'] else '' for p in prototype['parameters']}
    if set(overrides)-set(parameter_types):
        raise ValueError('Unknown parameter override')
    eval_cache = {}
    for lane in range(count):
        lane_key = lane if any(re.search(r'\bi\b',v) for v in overrides.values()) else 0
        if lane_key not in eval_cache:
            current_types = dict(parameter_types)
            for _ in range(4):
                values = evaluate(project,list(overrides.values()),index=lane if node.get('count','1').strip()!='1' else None,
                                  types=[current_types[k] for k in overrides])
                resolved = {k:v['literal'] for k,v in zip(overrides,values)}
                key = json.dumps(resolved,sort_keys=True)
                if key not in cache:
                    cache[key] = worker(project,'instance',module=node['module'],overrides=resolved)
                result = cache[key]
                new_types = {p['name']:p['type'] if p['explicit_type'] else '' for p in result['parameters']}
                if all(new_types[k]==current_types[k] for k in overrides):
                    break
                current_types = new_types
            else:
                raise ValueError('Parameter-dependent types did not stabilize')
            eval_cache[lane_key] = (resolved,result)
        resolved,result = eval_cache[lane_key]
        supported = {p['name'] for p in result['parameters']}
        if set(overrides)-supported:
            raise ValueError('Unknown parameter override')
        variants.append(dict(result,resolved=resolved))
    first = variants[0]
    homogeneous = all(v['ports']==first['ports'] for v in variants)
    node['analysis'] = dict(first,count=count,variants=variants,homogeneous=homogeneous)
    if not homogeneous:
        node['view']='expanded'

    return node


def validate_shape(sh):
    if not isinstance(sh.get('atom_width',1),int) or sh.get('atom_width',1)<1:
        raise ValueError('atom_width must be a positive integer')
    for key in ('packed','unpacked'):
        dims = sh.get(key,[])
        if len(dims)>4 or any(not isinstance(r,list) or len(r)!=2 or any(not isinstance(x,int) for x in r) for r in dims):
            raise ValueError('Dimensions must be arrays of [left,right] integer ranges (max 4 per kind)')
    if bits(sh)>65536:
        raise ValueError('Signal exceeds 65536 bit demo limit')


def product(dims):
    n = 1
    for a, b in dims:
        n *= abs(a-b)+1
    return n


def bits(shape):
    return shape.get('atom_width', 1) * product(shape.get('packed', [])) * product(shape.get('unpacked', []))


def indices(dims):
    return itertools.product(*(range(a, b + (1 if b >= a else -1), 1 if b >= a else -1) for a, b in dims))


def atoms(signal, sh):
    """MSB first: unpacked declaration order, then packed declaration order."""
    out = []
    for ix in indices(sh.get('unpacked', []) + sh.get('packed', [])):
        base = signal + ''.join(f'[{i}]' for i in ix)
        if sh.get('atom_width', 1) == 1:
            out.append(base)
        else:
            out.extend(base + f'[{i}]' for i in reversed(range(sh['atom_width'])))
    return out


def declaration(name, sh, kind='logic'):
    width = sh.get('atom_width', 1)
    packed = ''.join(f'[{a}:{b}]' for a, b in sh.get('packed', []))
    if width > 1:
        packed += f'[{width-1}:0]'
    unpacked = ''.join(f' [{a}:{b}]' for a, b in sh.get('unpacked', []))
    signed = ' signed' if sh.get('signed') else ''
    return f'{kind}{signed}{(" " + packed) if packed else ""} {name}{unpacked}'


def endpoint_shape(node, port):
    if node['kind'] == 'module':
        p = next((p for p in node['analysis']['ports'] if p['name'] == port), None)
        if not p:
            raise ValueError(f"Unknown port {node['name']}.{port}")
        if p['direction'] not in ('In','Out'):
            raise ValueError('Demo does not support inout/ref ports')
        sh = dict(p['shape'])
        if node['analysis']['count'] > 1:
            sh['unpacked'] = [[0, node['analysis']['count']-1]] + sh['unpacked']
        return sh, ('source' if p['direction'] == 'Out' else 'target')
    p = next((p for p in node.get('ports', []) if p['name'] == port), None)
    if not p:
        raise ValueError('Unknown component port')
    return p['shape'], p['role']


def compile_project(project):
    validate_project(project)
    identifier(project['name'])
    nodes = project.get('nodes', [])
    if any(n['kind']=='module' and n.get('count','1').strip()!='1' for n in nodes):
        if re.search(r'\bparameter\b[^;\n]*\bi\s*=',project.get('parameters','')):
            raise ValueError('i is reserved as the generate index when generate is used')
    if len(nodes) > 128:
        raise ValueError('Demo limit: 128 nodes')
    names, by_id = set(), {}
    for n in nodes:
        identifier(n['name'])
        if n['name'] in names or n['id'] in by_id:
            raise ValueError('Duplicate instance name or node ID')
        names.add(n['name']); by_id[n['id']] = n
        if n['kind'] == 'module':
            instance(project, n)
        elif n['kind'] not in ('split', 'concat', 'reshape', 'input', 'output', 'constant'):
            raise ValueError('Unknown component kind')
    # Namespace and all user expressions receive a final slang validation at export.
    lines = ['// Generated by Verilinx 0.1', '// Wiring dimensions are specialized to current defaults. Reopen the project to reconfigure.', f"module {project['name']}"]
    io = []
    for n in nodes:
        if n['kind'] in ('input', 'output'):
            if len(n['ports']) != 1:
                raise ValueError('Top-level IO has exactly one port')
            io.append(declaration(n['name'], n['ports'][0]['shape'], n['kind'] + ' wire'))
    lines[-1] += ' (\n' + ',\n'.join('    ' + x for x in io) + '\n);'
    lines.append(declarations(project.get('parameters', '')))
    declaration_start = len(lines)
    wires = {}
    endpoint = {}
    top_outputs = {n['id']: n['name'] for n in nodes if n['kind'] == 'output'}
    shared_outputs = {
        (edge['source'], edge['sourcePort'])
        for edge in project.get('edges', [])
        if top_outputs.get(edge['target']) == edge['sourcePort']
        and by_id.get(edge['source'], {}).get('kind') == 'module'
    }
    # Output port names are the public net names. Reserve the complete top-level
    # namespace first, then give source endpoints priority over input adapters.
    used_signals = names | set(re.findall(r'[a-zA-Z_][a-zA-Z0-9_$]*', project.get('parameters', '')))
    used_signals |= {f"g_{n['name']}" for n in nodes if n['kind'] == 'module'}
    preferred_outputs = {
        p['name'] for n in nodes if n['kind'] == 'module' and n['analysis'].get('homogeneous', True)
        for p in n['analysis']['ports'] if p['direction'] == 'Out'
    }
    signal_names = {}

    def allocate_signal(n, port, role, lane=None):
        base = port if role == 'source' else f"{n['name']}_{port}"
        if lane is not None:
            base += f'_lane{lane}'
        if role != 'source' or lane is not None:
            base = re.sub('_+', '_', base)
        candidate = base
        preferred = n['kind'] == 'module' and role == 'source' and lane is None
        if candidate in used_signals or (not preferred and candidate in preferred_outputs):
            candidate = stem = re.sub('_+', '_', f"{n['name']}_{base}")
            suffix = 2
            while candidate in used_signals or candidate in preferred_outputs:
                candidate = f'{stem.rstrip("_")}_{suffix}'
                suffix += 1
        used_signals.add(candidate)
        return candidate

    for role_priority in ('source', 'target'):
        for n in nodes:
            ports = n['analysis']['ports'] if n['kind'] == 'module' else n.get('ports', [])
            for p in ports:
                _, role = endpoint_shape(n, p['name'])
                if role != role_priority or n['kind'] in ('input', 'output'):
                    continue
                lanes = range(n['analysis']['count']) if n['kind'] == 'module' and not n['analysis'].get('homogeneous', True) else [None]
                for lane in lanes:
                    port = p['name']
                    signal_names[(n['id'], port, lane)] = (
                        port if role == 'source' and lane is None and (n['id'], port) in shared_outputs
                        else allocate_signal(n, port, role, lane)
                    )
    total_bits = 0
    for idx, n in enumerate(nodes):
        portnames = ([p['name'] for p in n['analysis']['ports']] if n['kind']=='module'
                     else [p['name'] for p in n.get('ports', [])])
        if len(portnames) != len(set(portnames)):
            raise ValueError('Duplicate component port names')
        for pidx, port in enumerate(portnames):
            identifier(port)
            sh, role = endpoint_shape(n, port)
            if n['kind']=='module' and not n['analysis'].get('homogeneous',True):
                for lane,variant in enumerate(n['analysis']['variants']):
                    vp = next(p for p in variant['ports'] if p['name']==port)
                    lane_sig = signal_names[(n['id'], port, lane)]
                    endpoint[(n['id'],port+'@'+str(lane))] = (lane_sig,vp['shape'],role)
                    wires[lane_sig] = declaration(lane_sig, vp['shape'], 'wire') + ';'
                continue
            validate_shape(sh)
            total_bits += bits(sh)
            if total_bits>262144:
                raise ValueError('Project signal expansion exceeds 262144 bits')
            if role not in ('source','target'):
                raise ValueError('Port role must be source or target')
            if n['kind'] in ('input','constant') and role!='source' or n['kind']=='output' and role!='target':
                raise ValueError('Invalid top-level or constant port role')
            if bits(sh) < 1 or bits(sh) > 65536:
                raise ValueError('Signal width must be 1..65536 bits')
            sig = n['name'] if n['kind'] in ('input','output') else signal_names[(n['id'], port, None)]
            endpoint[(n['id'], port)] = (sig, sh, role)
            if n['kind'] not in ('input','output') and (n['id'], port) not in shared_outputs:
                wires[sig] = declaration(sig, sh, 'wire') + ';'
    # Lane aliases share physical signal bits with the aggregate handle.
    for n in nodes:
        if n['kind']=='module' and n['analysis']['count']>1 and n['analysis'].get('homogeneous',True):
            for p in n['analysis']['ports']:
                sig,sh,role = endpoint[(n['id'],p['name'])]
                for lane in range(n['analysis']['count']):
                    lane_sh = dict(sh,unpacked=sh['unpacked'][1:])
                    endpoint[(n['id'],p['name']+'@'+str(lane))] = (sig+f'[{lane}]',lane_sh,role)
    driven = set()
    direct_inputs = {}
    def assign_bits(dst, src):
        if len(dst) != len(src):
            raise ValueError(f'Width mismatch: {len(src)} source bits → {len(dst)} target bits')
        lines.extend(f'assign {a} = {b};' for a, b in zip(dst, src))
    for e in project.get('edges', []):
        sk, tk = (e['source'],e['sourcePort']), (e['target'],e['targetPort'])
        if sk not in endpoint or tk not in endpoint:
            raise ValueError('Connection refers to a missing node or port')
        ss, sh, sr = endpoint[sk]; ts, th, tr = endpoint[tk]
        if sr != 'source' or tr != 'target':
            raise ValueError('Connections must go from an output to an input')
        target_bits = set(atoms(ts,th))
        if target_bits & driven:
            raise ValueError('Multiple drivers / overlapping lane and aggregate connections')
        if sh.get('packed',[]) != th.get('packed',[]) or sh.get('unpacked',[]) != th.get('unpacked',[]) or sh.get('atom_width',1) != th.get('atom_width',1):
            raise ValueError('Signal shape mismatch; insert a split / concat / reshape component')
        driven |= target_bits
        if by_id[tk[0]]['kind'] == 'module' and ts in wires:
            # A complete input can connect to its driver. Partial lane wiring
            # still uses an assembled net with an assignment for each lane.
            direct_inputs[ts] = ss
            del wires[ts]
        elif ts != ss:
            assign_bits(atoms(ts,th),atoms(ss,sh))
    lines[declaration_start:declaration_start] = wires.values()

    def emit_instance(node, ports, indent=''):
        prefix = indent + node['module']
        overrides = node.get('overrides', {})
        if overrides:
            lines.append(prefix + ' #(')
            lines.append(',\n'.join(f'{indent}    .{name}({value})' for name, value in overrides.items()))
            prefix = indent + ')'
        lines.append(f"{prefix} {node['name']} (")
        connections = ',\n'.join(f'{indent}    .{port}({signal})' for port, signal in ports)
        if connections:
            lines.append(connections)
        lines.append(indent + ');')

    warnings = []
    for n in nodes:
        eps = {p: v for (nid,p),v in endpoint.items() if nid == n['id'] and ('@' not in p or not n.get('analysis',{}).get('homogeneous',True))}
        if n['kind'] == 'module':
            if n['analysis']['count'] > 1 or n.get('count','1').strip()!='1':
                count_expr = n.get('count','1')
                lines.append(f"for (genvar i=0; i<({count_expr}); i++) begin : g_{n['name']}")
                if n['analysis'].get('homogeneous',True):
                    index = '[i]' if n['analysis']['count'] > 1 else ''
                    emit_instance(n, ((p, direct_inputs.get(sig, sig) + index) for p, (sig, _, _) in eps.items()), '    ')
                else:
                    for lane in range(n['analysis']['count']):
                        lines.append(f'    if (i=={lane}) begin : lane_{lane}')
                        ports = ((p.rsplit('@', 1)[0], direct_inputs.get(sig, sig))
                                 for p, (sig, _, _) in eps.items() if p.endswith('@' + str(lane)))
                        emit_instance(n, ports, '        ')
                        lines.append('    end')
                lines.append('end')
            else:
                emit_instance(n, ((p, direct_inputs.get(sig, sig)) for p, (sig, _, _) in eps.items()))
        elif n['kind'] in ('split','concat','reshape'):
            ins = [atoms(sig,sh) for sig,sh,role in eps.values() if role=='target']
            outs = [atoms(sig,sh) for sig,sh,role in eps.values() if role=='source']
            if not ins or not outs:
                raise ValueError('Adapter requires input and output ports')
            assign_bits(sum(outs,[]),sum(ins,[]))
        elif n['kind'] == 'constant':
            val = n.get('expression',"1'b0")
            for sig,sh,_ in eps.values():
                if sh.get('unpacked'):
                    raise ValueError('Use reshape to convert a vector constant to an array')
                lines.append(f'assign {sig} = {val};')
        for p,(sig,sh,role) in eps.items():
            if role == 'target' and not set(atoms(sig,sh)).issubset(driven):
                warnings.append(f"Unconnected input: {n['name']}.{p}")
    lines.append('endmodule\n')
    rtl = '\n'.join(lines)
    return rtl, warnings


def encode_project(project):
    raw = json.dumps(project, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()
    if len(raw) > MAX_BYTES:
        raise ValueError('Project exceeds 16 MiB limit')
    payload = base64.b64encode(zlib.compress(raw,9)).decode()
    digest = hashlib.sha256(raw).hexdigest()
    return ('// verilinx prj begin\n// format: 1 zlib+base64 sha256:' + digest + '\n' +
            '\n'.join('// '+payload[i:i+100] for i in range(0,len(payload),100)) + '\n// verilinx prj end\n')


def decode_project(text):
    blocks = re.findall(r'^// verilinx prj begin\n(.*?)^// verilinx prj end\s*$',text,re.S|re.M)
    if len(blocks) != 1:
        raise ValueError('Expected exactly one Verilinx project block')
    lines = blocks[0].splitlines()
    header = re.fullmatch(r'// format: 1 zlib\+base64 sha256:([0-9a-f]{64})',lines[0])
    if not header or any(not line.startswith('// ') for line in lines[1:]):
        raise ValueError('Unsupported or malformed project format')
    blob = base64.b64decode(''.join(line[3:] for line in lines[1:]),validate=True)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(blob, MAX_BYTES+1)
    if len(raw)>MAX_BYTES or not decoder.eof or decoder.unused_data:
        raise ValueError('Invalid or oversized compressed project')
    if hashlib.sha256(raw).hexdigest() != header[1]:
        raise ValueError('Project checksum mismatch')
    project = json.loads(raw)
    if project.get('schema') != 1 or not isinstance(project.get('inputs',{}).get('files'),dict):
        raise ValueError('Unsupported project schema')
    return project
