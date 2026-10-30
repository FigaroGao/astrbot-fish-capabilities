import asyncio,json
from types import SimpleNamespace
from test_astrbot_binding import plugin,Event

def sending_event(trace,**kwargs):
    e=Event(**kwargs);e.plain_result=lambda text:text
    async def send(text):trace.append(('sent',text))
    e.send=send
    return e

async def test_browse_ack_before_io_and_not_repeated_for_read(plugin):
    trace=[];e=sending_event(trace);plugin.config['bili_enabled']=True
    async def browse(*a,**k):
        assert len(trace)==1 and trace[0][0]=='sent'
        trace.append(('browse',None));return {'items':[]}
    async def read(*a,**k):trace.append(('read',None));return {'bvid':'fixture'}
    plugin.bili=SimpleNamespace(browse=browse,read=read)
    plugin.record_video_activity=lambda p:None
    assert json.loads(await plugin.bili_browse(e))=={'items':[]}
    await plugin.bili_read(e,'fixture')
    assert [x[0] for x in trace]==['sent','browse','read']
    await plugin.bili_read(sending_event(trace),'fixture')
    assert [x[0] for x in trace][-2:]==['sent','read']

async def test_ack_parallel_tools_and_private_owner_boundary(plugin):
    trace=[];e=sending_event(trace)
    await asyncio.gather(plugin.acknowledge_work(e,'我看看'),plugin.acknowledge_work(e,'稍等'))
    assert len(trace)==1
    assert not await plugin.acknowledge_work(sending_event(trace,private=False),'我看看')
    assert not await plugin.acknowledge_work(sending_event(trace,sender='999'),'我看看')
    plugin.config['bili_enabled']=False
    assert json.loads(await plugin.bili_browse(sending_event(trace)))['ok'] is False
    assert len(trace)==1

async def test_send_failure_does_not_repeat_or_prevent_read(plugin):
    attempts=[];e=sending_event([]);plugin.config['bili_enabled']=True
    async def fail(text):attempts.append(text);raise RuntimeError('transport failed')
    e.send=fail
    async def read(*a,**k):return {'bvid':'fixture'}
    plugin.bili=SimpleNamespace(read=read);plugin.record_video_activity=lambda p:None
    assert json.loads(await plugin.bili_read(e,'fixture'))['bvid']=='fixture'
    assert json.loads(await plugin.bili_read(e,'fixture'))['bvid']=='fixture'
    assert len(attempts)==1

async def test_backend_failure_is_not_reported_as_done(plugin):
    trace=[];e=sending_event(trace);plugin.config['bili_enabled']=True
    async def fail(*a,**k):raise RuntimeError('backend failed')
    plugin.bili=SimpleNamespace(read=fail)
    result=json.loads(await plugin.bili_read(e,'fixture'))
    assert result['ok'] is False
    assert len(trace)==1 and '看过' not in trace[0][1]
