"""Optional capability-link access for temporary HTTPS test deployments."""
import os
import secrets
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

COOKIE = 'verilinx_test_access'


async def access_gate(request: Request, call_next):
    key = os.environ.get('VERILINX_ACCESS_TOKEN','')
    if not key or request.url.path=='/healthz':
        return await call_next(request)
    def valid(value):
        return secrets.compare_digest((value or '').encode(),key.encode())
    if request.method=='GET' and valid(request.query_params.get('access')):
        query=urlencode([(k,v) for k,v in request.query_params.multi_items() if k!='access'])
        response=RedirectResponse(str(request.url.replace(query=query)),status_code=303)
        response.set_cookie(COOKIE,key,secure=True,httponly=True,samesite='strict',max_age=86400)
    elif valid(request.cookies.get(COOKIE)) or valid(request.headers.get('authorization','').removeprefix('Bearer ')):
        response=await call_next(request)
    elif request.url.path.startswith('/api/'):
        response=JSONResponse({'detail':'Open the complete test link to authorize this browser.'},status_code=401)
    else:
        response=HTMLResponse('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Verilinx</title><main style="font:16px system-ui;max-width:540px;margin:15vh auto;padding:24px"><h1>Verilinx 测试入口</h1><p>请使用对话中提供的完整测试链接打开此页面。</p></main>',status_code=401)
    response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Robots-Tag']='noindex, nofollow'
    return response
