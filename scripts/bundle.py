#!/usr/bin/env python3
"""Create a path->text JSON input bundle for the mobile HTML client."""
import argparse
import json
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory',type=Path)
parser.add_argument('output',type=Path)
args=parser.parse_args()
root=args.directory.resolve()
if not root.is_dir():
    parser.error('directory must exist')
files={}
for p in sorted(root.rglob('*')):
    if not p.is_file() or p.is_symlink() or p.resolve()==args.output.resolve():
        continue
    if any(x in {'.git','.venv','node_modules','dist','.runtime','__pycache__'} for x in p.relative_to(root).parts):
        continue
    try:
        data=p.read_text(encoding='utf-8')
        if '\x00' not in data:
            files[str(p.relative_to(root))]=data
    except UnicodeError:
        continue
if sum(len(x.encode()) for x in files.values())>16*1024*1024:
    parser.error('bundle exceeds 16 MiB; select a smaller input directory')
args.output.write_text(json.dumps(files,ensure_ascii=False,indent=2))
print(f'Wrote {len(files)} text files to {args.output}')
