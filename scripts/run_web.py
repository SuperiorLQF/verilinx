"""Production launcher for a container host. Credentials come from its secret store."""
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn

if __name__=='__main__':
    if len(os.environ.get('VERILINX_ACCESS_TOKEN',''))<24:
        raise SystemExit('Set VERILINX_ACCESS_TOKEN to a random secret of at least 24 characters')
    uvicorn.run('backend.main:app',host='0.0.0.0',port=int(os.environ.get('PORT','3000')),access_log=False)
