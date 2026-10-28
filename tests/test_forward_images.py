import json
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.forward_records import ForwardRecords
from astrbot_plugin_fish_capabilities.services import forward_images as fi
from astrbot_plugin_fish_capabilities.services.activity_timeline import ActivityTimeline

async def test_images_keep_nested_location_and_do_not_expose_tickets():
    inner={'type':'forward','data':{'content':[{'type':'node','data':{'name':'B','content':[{'type':'image','data':{'url':'https://gchat.qpic.cn/a?private-ticket'}}]}}]}}
    reader=ForwardRecords(object())
    text=await reader.read([{'type':'forward','data':{'content':[{'type':'node','data':{'name':'A','content':[inner,{'type':'image','data':{'file':'secret-handle'}}]}}]}}])
    assert [x['depth'] for x in reader.images]==[2,1]
    assert [x['node'] for x in reader.images]==[2,1]
    assert 'F2 第1层·发言人 A' in text
    assert '[F1' in text and '[F2' in text and 'private-ticket' not in text and 'secret-handle' not in text

async def test_bad_image_source_fails_without_model_or_ticket_leak(tmp_path):
    generate=AsyncMock();client=type('C',(),{'call':AsyncMock()})()
    result=await fi.describe([{'label':'F1','data':{'url':'http://127.0.0.1/secret'}}],client,generate,tmp_path)
    assert '读取失败' in result and '127.0' not in result
    generate.assert_not_called();assert list(tmp_path.iterdir())==[]

async def test_downloaded_image_is_temporary_and_labelled(monkeypatch,tmp_path):
    def fake_download(url,path):path.write_bytes(b'fixture')
    monkeypatch.setattr(fi,'download',fake_download)
    async def generate(path,label):
        assert path.exists() and label=='F2';return '可读文字：测试'
    result=await fi.describe([{'label':'F2','data':{'url':'https://gchat.qpic.cn/a'}}],object(),generate,tmp_path)
    assert 'F2' in result and '测试' in result and list(tmp_path.iterdir())==[]

def test_sent_records_exclude_reading_private_chat_and_expired_events(tmp_path):
    now=[10000000.0];t=ActivityTimeline(tmp_path/'t.db',clock=lambda:now[0])
    t.add('bili_reply','1','实际回复',state='submitted',details={'receipt':'1'})
    t.add('qq_private_sent','2','私聊原文');t.add('bili_read','3','读了视频')
    t.add('bili_dynamic_reply','4','动态回应',state='submitted')
    rows=t.sent()['records'];assert {r['text'] for r in rows}=={'实际回复','动态回应'}
    now[0]+=31*86400;assert t.sent()['records']==[]

@pytest.mark.parametrize('url',['file:///a','https://gchat.qpic.cn.evil.test/x','https://user:pass@gchat.qpic.cn/x','https://gchat.qpic.cn:8181/x'])
def test_untrusted_image_urls_rejected(url):
    with pytest.raises(ValueError):fi.checked_url(url)
