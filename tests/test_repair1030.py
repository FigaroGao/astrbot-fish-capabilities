import pytest
from PIL import Image
from astrbot_plugin_fish_capabilities.services.bili_gallery import collect
from astrbot_plugin_fish_capabilities.services.valorant import MvalHTTP
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError

def test_overflow_keeps_tail_not_only_opening(tmp_path,monkeypatch):
    import astrbot_plugin_fish_capabilities.services.bili_gallery as gallery
    monkeypatch.setattr(gallery,'same_page',lambda a,b:False)
    for i in range(80):Image.new('RGB',(12,12),(i,0,0)).save(tmp_path/f'frame-{i:06d}.jpg')
    pages,status=collect(tmp_path)
    assert len(pages)==48 and pages[0]['time']==0 and pages[-1]['time']==39.5
    assert status['page_limit_reached'] and status['selection_method']=='whole_timeline_budget_samples'

async def test_read_timeout_retried_once_but_not_login():
    h=MvalHTTP();calls=[]
    def request(*args):
        calls.append(args)
        if len(calls)==1:raise CapabilityError('timeout') from TimeoutError()
        return {'result':0}
    h.request=request
    assert (await h.post('/go/agame/career/record/list',{}))['result']==0 and len(calls)==2
    calls.clear()
    with pytest.raises(CapabilityError):await h.post('/go/auth/login_by_wechat',{})
    assert len(calls)==1
