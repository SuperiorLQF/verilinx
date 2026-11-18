"""One isolated slang invocation. JSON stdin/stdout; never invoke a shell."""
import json
import os
from pathlib import Path
import sys
import tempfile
import pyslang as s


def quote(arg):
    return '"' + str(arg).replace('\\', '\\\\').replace('"', '\\"') + '"'


def constant(value):
    v = value.value
    if isinstance(v, s.SVInt):
        return {'literal': v.toString(s.LiteralBase.Hex, True),
                'value': None if v.hasUnknown else int(v), 'width': v.bitWidth,
                'signed': v.isSigned, 'display': str(value)}
    raise ValueError('Demo currently supports integral value parameters only (not type/string/real parameters)')


def shape(t):
    t = t.canonicalType
    packed, unpacked = [], []
    while t.isArray:
        if not t.isFixedSize:
            raise ValueError('Dynamic arrays and queues are not supported')
        (unpacked if t.isUnpackedArray else packed).append([t.fixedRange.left, t.fixedRange.right])
        t = t.elementType.canonicalType
    if not t.isIntegral or t.isStruct or t.isEnum:
        raise ValueError('Demo supports integral scalar / packed / fixed unpacked arrays only')
    # Integer atom widths (int/byte/etc) are retained, even without packed ranges.
    return {'packed': packed, 'unpacked': unpacked, 'atom_width': t.bitWidth,
            'signed': t.isSigned, 'four_state': t.isFourState}


def run(req):
    os.chdir(req['root'])
    d = s.driver.Driver()
    d.addStandardArgs()
    args = ['--single-unit', '-f', req['entry']]
    generated = None
    if req['mode'] in ('evaluate', 'validate'):
        fd, generated = tempfile.mkstemp(suffix='.sv', prefix='verilinx_')
        with os.fdopen(fd, 'w') as f:
            f.write(req['text'])
        args += [generated, '--top', req.get('top', '__verilinx_eval')]
    elif req['mode'] == 'instance':
        args += ['--top', req['module']]
        args += ['-G' + k + '=' + v for k, v in req.get('overrides', {}).items()]
    else:
        args += ['--lint-only']
    try:
        if not d.parseCommandLine('slang ' + ' '.join(quote(a) for a in args)) or not d.processOptions():
            raise ValueError('Invalid filelist/options: ' + d.textDiagClient.getString())
        if not d.parseAllSources():
            raise ValueError('Source parsing failed: ' + d.textDiagClient.getString())
        c = d.createCompilation()
        parse_diags = c.getParseDiagnostics()
        if any(x.isError() for x in parse_diags):
            raise ValueError(s.DiagnosticEngine.reportAll(c.sourceManager,parse_diags))
        result = {'version': s.__version__}
        if req['mode'] == 'catalog':
            result['modules'] = [{'name': x.name, 'declaration': str(x.syntax)}
                                 for x in c.getDefinitions() if x.definitionKind.name == 'Module']
            diags = c.getParseDiagnostics()
        else:
            root = c.getRoot()
            diags = c.getAllDiagnostics()
            if not c.hasIssuedErrors:
                inst = root.topInstances[0]
                if req['mode'] == 'evaluate':
                    result['values'] = {name: constant(inst.body.find(name).value) for name in req['names']}
                elif req['mode'] == 'instance':
                    result['parameters'] = [dict(name=p.name, type=str(p.type), explicit_type=(p.declaredType.typeSyntax is not None and p.declaredType.typeSyntax.kind.name != 'ImplicitType'), **constant(p.value))
                                            for p in inst.body.parameters
                                            if isinstance(p, s.ast.ParameterSymbol) and not p.isLocalParam]
                    result['ports'] = [{'name': p.name, 'direction': p.direction.name,
                                        'type': str(p.type), 'shape': shape(p.type)}
                                       for p in inst.body.portList]
        result['diagnostics'] = s.DiagnosticEngine.reportAll(c.sourceManager, diags)
        result['ok'] = not any(x.isError() for x in diags)
        paths = {Path(x) for x in d.commandFileMetadata}
        if c.sourceManager:
            paths |= {Path(c.sourceManager.getFullPath(b)) for b in c.sourceManager.getAllBuffers()}
        result['dependencies'] = [str(p.resolve()) for p in paths if p.is_file() and str(p) != generated]
        return result
    finally:
        if generated:
            Path(generated).unlink(missing_ok=True)


def cli():
    try:
        print(json.dumps(run(json.load(sys.stdin))))
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}))


if __name__ == '__main__':
    cli()
