"""Web QR authentication: retain Set-Cookie and exchange official cross-domain tickets."""
import http.cookiejar
import json
import urllib.parse
import urllib.request
from http.cookies import SimpleCookie

HOSTS={'passport.bilibili.com','passport.biligame.com','www.bilibili.com'}
UA='Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'

def trusted(url):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.hostname not in HOSTS or p.port not in (None,443) or p.username or p.password:
        raise RuntimeError('untrusted_login_destination')
    return url

class Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self,capture):super().__init__();self.capture=capture
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        trusted(newurl)
        self.capture(headers)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

class WebQR:
    def __init__(self):
        self.jar=http.cookiejar.CookieJar()
        self.received={}
        self.opener=urllib.request.build_opener(Redirects(self.capture),urllib.request.HTTPCookieProcessor(self.jar))
    def capture(self,headers):
        for row in headers.get_all('Set-Cookie',[]):
            parsed=SimpleCookie();parsed.load(row)
            for name in ('SESSDATA','bili_jct','DedeUserID','buvid3'):
                if name in parsed:self.received[name]=parsed[name].value
    def fetch(self,url,as_json=True):
        request=urllib.request.Request(trusted(url),headers={'User-Agent':UA,'Referer':'https://www.bilibili.com/'})
        with self.opener.open(request,timeout=15) as response:
            self.capture(response.headers);body=response.read(512000)
        return json.loads(body) if as_json else None
    def generate(self):
        r=self.fetch('https://passport.bilibili.com/x/passport-login/web/qrcode/generate')
        if r.get('code')!=0:raise RuntimeError('qr_generation_rejected')
        return r['data']
    def poll(self,key):
        r=self.fetch('https://passport.bilibili.com/x/passport-login/web/qrcode/poll?'+urllib.parse.urlencode({'qrcode_key':key}))
        if r.get('code')!=0:raise RuntimeError('qr_poll_rejected')
        return r['data']
    def values(self,event):
        result=dict(event)
        fields={'SESSDATA':'sessdata','bili_jct':'bili_jct','DedeUserID':'dedeuserid','buvid3':'buvid3'}
        url=event.get('exchange_url','')
        if url:
            trusted(url)
            query=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            for key,target in fields.items():
                if query.get(key):result[target]=query[key][0]
        for cookie in sorted(self.jar,key=lambda c:c.domain.endswith('bilibili.com')):
            if cookie.name in fields:result[fields[cookie.name]]=cookie.value
        for name,value in self.received.items():result[fields[name]]=value
        return result
    def exchange(self,pending):
        values=self.values(pending)
        if not values.get('sessdata') or not values.get('bili_jct'):
            url=values.get('exchange_url')
            if not url:raise RuntimeError('missing_cross_domain_ticket')
            self.fetch(url,False)
            values=self.values(values)
        if not values.get('sessdata') or not values.get('bili_jct'):raise RuntimeError('login_cookie_not_received')
        return values
