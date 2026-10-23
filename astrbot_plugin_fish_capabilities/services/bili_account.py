"""Read-only identity check against one fixed Bilibili endpoint."""
import json
import urllib.request

def verify_account(values):
    cookies={k:str(v) for k,v in {'SESSDATA':values.get('sessdata',''),'bili_jct':values.get('bili_jct',''),'DedeUserID':values.get('dedeuserid',''),'buvid3':values.get('buvid3','')}.items() if v}
    if not cookies.get('SESSDATA') or any('\r' in v or '\n' in v for v in cookies.values()):raise RuntimeError('invalid_saved_credentials')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    request=urllib.request.Request('https://api.bilibili.com/x/web-interface/nav',headers={
        'User-Agent':'Mozilla/5.0','Referer':'https://www.bilibili.com/',
        'Cookie':'; '.join(k+'='+v for k,v in cookies.items())})
    with urllib.request.build_opener(NoRedirect()).open(request,timeout=15) as response:raw=response.read(512000)
    result=json.loads(raw);info=result.get('data') or {}
    if result.get('code')!=0 or info.get('isLogin') is not True:raise RuntimeError('account_check_not_logged_in')
    expected=str(values.get('dedeuserid') or '')
    if expected and str(info.get('mid'))!=expected:raise RuntimeError('account_mismatch')
    return {'mid':info['mid'],'name':info.get('uname','')}
