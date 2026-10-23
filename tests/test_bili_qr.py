from email.message import Message
import pytest
from astrbot_plugin_fish_capabilities.services.bili_qr import WebQR,trusted

def test_legacy_query_cookie_format():
    q=WebQR();v=q.exchange({'exchange_url':'https://passport.biligame.com/crossDomain?SESSDATA=fake%2Csession&bili_jct=fakecsrf&DedeUserID=42'})
    assert v['sessdata']=='fake,session' and v['bili_jct']=='fakecsrf' and v['dedeuserid']=='42'

def test_ticket_cookie_response_format(monkeypatch):
    q=WebQR();calls=[]
    def fetch(url,as_json):
        calls.append(url)
        headers=Message()
        headers.add_header('Set-Cookie','SESSDATA=fake%2Csession; Domain=.bilibili.com; Secure; HttpOnly')
        headers.add_header('Set-Cookie','bili_jct=fakecsrf; Path=/')
        headers.add_header('Set-Cookie','DedeUserID=42; Path=/')
        q.capture(headers)
    monkeypatch.setattr(q,'fetch',fetch)
    v=q.exchange({'exchange_url':'https://passport.biligame.com/x/passport-login/web/crossDomain?ticket=synthetic'})
    assert len(calls)==1 and v['sessdata']=='fake%2Csession' and v['dedeuserid']=='42'

def test_missing_cookie_never_claims_authenticated(monkeypatch):
    q=WebQR();monkeypatch.setattr(q,'fetch',lambda *a:None)
    with pytest.raises(RuntimeError,match='not_received'):q.exchange({'exchange_url':'https://passport.biligame.com/x/passport-login/web/crossDomain?ticket=synthetic'})

@pytest.mark.parametrize('url',['https://evil.example/?ticket=private','http://passport.bilibili.com/','https://passport.bilibili.com.evil.example/','https://a:b@passport.bilibili.com/','https://passport.bilibili.com:8080/'])
def test_auth_redirect_allowlist(url):
    with pytest.raises(RuntimeError):trusted(url)
