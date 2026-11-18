#!/usr/bin/env python3
"""Start a capability-link protected API for an HTTPS reverse tunnel.

Read the access token from a hidden prompt. Do not log request URLs / access links.
"""
import getpass
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn

if __name__=='__main__':
    token=getpass.getpass('Test access token (hidden): ').strip()
    if len(token)<24:
        raise SystemExit('Use a random token with at least 24 characters')
    os.environ['VERILINX_ACCESS_TOKEN']=token
    uvicorn.run('backend.main:app',host='127.0.0.1',port=3100,access_log=False)
