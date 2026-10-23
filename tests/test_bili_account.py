import json
import pytest
from astrbot_plugin_fish_capabilities.services.bili_account import verify_account

class Response:
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):return json.dumps(self.data).encode()

@pytest.mark.parametrize('variant',['ok','logged_out','mismatch','malformed_cookie'])
def test_fixed_identity_endpoint(monkeypatch,variant):
    requests=[]
    class Opener:
        def open(self,request,timeout):
            requests.append(request)
            return Response({'code':0,'data':{'isLogin':variant!='logged_out','mid':42,'uname':'test'}})
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    value={'sessdata':'synthetic','dedeuserid':'99' if variant=='mismatch' else '42'}
    if variant=='malformed_cookie':value['sessdata']='bad\r\nheader'
    if variant=='ok':assert verify_account(value)=={'mid':42,'name':'test'}
    else:
        with pytest.raises(RuntimeError):verify_account(value)
    if requests:assert requests[0].full_url=='https://api.bilibili.com/x/web-interface/nav'
    if variant=='malformed_cookie':assert not requests
