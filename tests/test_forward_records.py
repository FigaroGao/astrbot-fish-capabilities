import json
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.forward_records import ForwardRecords


def forward(fid):return {'type':'forward','data':{'id':fid}}
def node(text):return {'sender':{'nickname':'测试发言人'},'content':text}
def text(value):return {'type':'text','data':{'text':value}}


async def test_nested_remote_ids_preserve_speakers():
    payloads={'outer':{'messages':[node([text('外层'),forward('inner')])]},'inner':{'data':{'messages':[node([text('内层真实文字')])]}}}
    client=type('Client',(),{'get_forward_msg':AsyncMock(side_effect=lambda fid:payloads[fid])})()
    result=await ForwardRecords(client).read([forward('outer')])
    assert '外层' in result and '内层真实文字' in result and '第2层' in result
    assert '不可信资料' in result and client.get_forward_msg.await_count==2


async def test_json_multimsg_resid_and_node_wrappers():
    card={'app':'com.tencent.multimsg','meta':{'detail':{'resid':'inner','summary':'这不是全文'}}}
    client=type('Client',(),{'get_forward_msg':AsyncMock(return_value={'messages':[node([text('实际全文')])]})})()
    raw=[{'type':'forward','data':{'content':[{'type':'node','data':{'name':'某人','content':[{'type':'json','data':{'data':json.dumps(card)}}]}}]}}]
    result=await ForwardRecords(client).read(raw)
    assert '实际全文' in result and '这不是全文' not in result


async def test_cycle_and_fetch_cap():
    client=type('Client',(),{'get_forward_msg':AsyncMock(return_value={'messages':[node([forward('same')])]})})()
    reader=ForwardRecords(client,max_fetch=2)
    await reader.read([forward('same'),forward('next'),forward('third')])
    assert reader.fetches==2 and reader.limited


async def test_inline_depth_and_text_budget():
    raw=[text('x'*300)]
    for _ in range(9):raw=[{'type':'forward','data':{'content':[node(raw)]}}]
    reader=ForwardRecords(object(),max_depth=3,max_chars=100)
    result=await reader.read(raw)
    assert reader.limited and reader.chars<=100 and len(result)<700


async def test_transport_failure_does_not_invent_content():
    client=type('Client',(),{'get_forward_msg':AsyncMock(side_effect=TimeoutError('credentialsecret'))})()
    result=await ForwardRecords(client).read([forward('failed')])
    assert '读取失败' in result and 'credentialsecret' not in result


async def test_plain_message_not_injected_and_images_not_claimed_seen():
    assert await ForwardRecords(object()).read([text('hello')])==''
    result=await ForwardRecords(object()).read([{'type':'forward','data':{'content':[node([{'type':'image','data':{'url':'privateurl'}}])]}}])
    assert '未识别图像' in result and 'privateurl' not in result


async def test_cq_forward_string_and_malformed_json():
    client=type('Client',(),{'get_forward_msg':AsyncMock(return_value={'messages':[node([text('nested')])]})})()
    reader=ForwardRecords(client)
    result=await reader.read('[CQ:forward,id=abc]')
    assert 'nested' in result
    assert await ForwardRecords(client).read([{'type':'json','data':{'data':'invalid'}}])==''


async def test_node_limit_and_api_failure_wrapper():
    client=type('Client',(),{'get_forward_msg':AsyncMock(return_value={'status':'failed','retcode':1404})})()
    result=await ForwardRecords(client).read([forward('expired')])
    assert '读取失败' in result
    reader=ForwardRecords(object(),max_nodes=2)
    await reader.read([{'type':'forward','data':{'content':[node([text(str(i))]) for i in range(20)]}}])
    assert reader.nodes==2 and reader.limited


async def test_malformed_external_card_metadata_is_bounded():
    reader=ForwardRecords(object())
    result=await reader.read([{'type':'json','data':'invalid'},{'type':'json','data':{'data':json.dumps({'app':'com.tencent.multimsg','meta':[]})}}])
    assert '缺少' in result or '没有' in result
    assert reader.failed
