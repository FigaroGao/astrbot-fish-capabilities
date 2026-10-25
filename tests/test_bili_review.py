import json
from unittest.mock import AsyncMock
import pytest
from astrbot_plugin_fish_capabilities.services.bili_review import PublicReview,hard_block
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_bili_replies import make_inbox
from test_astrbot_binding import plugin,Event


async def make(tmp_path,decision='allow'):
    i,b,j,n,t=await make_inbox(tmp_path)
    generate=AsyncMock(return_value={'decision':decision,'reason_code':'privacy','owner_question':'这句话好像说到了我们私聊的事，你觉得能发吗？'})
    review=PublicReview(i.reader,tmp_path,generate,n,i.config,clock=lambda:t[0])
    i.review=review;i.comments.reviewer=review
    return i,b,j,n,t,review,generate


async def test_free_reply_uses_private_reference_but_requires_separate_review(tmp_path):
    i,b,j,n,t,r,g=await make(tmp_path)
    r.capture('你是小鲸',[{'role':'user','content':'私聊事实只用于理解语气'},{'role':'tool','content':'must not capture'}],'最近私聊','召回的长期记忆')
    j.return_value={'decision':'reply','text':'寿'}
    await i.check()
    assert b.sent[0][-1]=='寿'
    assert g.call_args.args[0]['private_reference']['recalled_memory']=='召回的长期记忆'
    assert 'must not capture' not in json.dumps(r.context())


async def test_uncertain_draft_naturally_asks_and_exact_approval_is_one_use(tmp_path):
    i,b,j,n,t,r,g=await make(tmp_path,'ask_owner')
    j.return_value={'decision':'reply','text':'这条我也喜欢'}
    await i.check();assert not b.sent
    n.assert_awaited_once();message=n.call_args.args[0]
    assert '这条我也喜欢' in message and '你觉得可以吗' in message and 'https://' not in message
    kind,payload,draft=r.approve('')
    assert kind=='reply'
    await i.reply(payload['target'],draft)
    assert b.sent[0][-1]==draft and g.await_count==1
    with pytest.raises(CapabilityError):await i.reply(payload['target'],draft)


@pytest.mark.parametrize('draft',['sk-abcdefghijklmno','我的号码12345678','https://example.com','答案是42','搜索结果如下','a'*40,'藏\u200b字'])
async def test_hard_sensitive_outputs_never_reach_model_or_public_write(tmp_path,draft):
    i,b,j,n,t,r,g=await make(tmp_path)
    j.return_value={'decision':'reply','text':draft}
    await i.check();assert not b.sent;g.assert_not_called()


async def test_review_failure_is_fail_closed(tmp_path):
    i,b,j,n,t,r,g=await make(tmp_path)
    g.side_effect=TimeoutError('sensitive error')
    j.return_value={'decision':'reply','text':'哈哈'}
    await i.check();assert not b.sent
    assert r.list()['pending'] and 'sensitive error' not in str(r.list())


async def test_root_comments_use_same_review_gate(tmp_path):
    from test_bili_comments import prepared
    reader,p,w=await prepared(tmp_path)
    reviewer=AsyncMock();w.reviewer=reviewer
    reviewer.gate.side_effect=CapabilityError('等待主人')
    with pytest.raises(CapabilityError):await w.post(p['reading_id'],'我喜欢这个细节',[p['evidence'][0]['evidence_id']])
    assert w.backend.calls==0


async def test_private_capture_is_owner_session_scoped_and_scrubs_keys(plugin):
    plugin.config.update(bili_public_review_enabled=True,bili_private_session='qq_test:FriendMessage:10001')
    req=type('R',(),dict(system_prompt='角色',contexts=[{'role':'user','content':'sk-abcdefghijklmn'}],prompt='你好',extra_user_content_parts=[{'text':'长期记忆'}]))()
    for e in [Event(private=False),Event(sender='other'),Event(admin=False)]:await plugin.capture_bili_private_context(e,req)
    assert not plugin.public_review.context()
    await plugin.capture_bili_private_context(Event(),req)
    c=plugin.public_review.context()
    assert c['recalled_memory']=='长期记忆' and 'sk-abcdefghijklmn' not in str(c)


@pytest.mark.parametrize('message',['你觉得可以吗？','可以发布吗','这条可以发出吗','先别发','不确定','hello'])
async def test_approval_requires_actual_owner_confirmation(plugin,message):
    plugin.config['bili_public_review_enabled']=True
    e=Event();e.get_message_str=lambda:message
    assert json.loads(await plugin.bili_review_tool(e,'approve'))['ok'] is False


async def test_contextual_draft_removes_obsolete_closed_bank_hint(plugin):
    from types import SimpleNamespace
    plugin.config['bili_public_review_enabled']=True
    plugin.bounded_generate=AsyncMock(return_value=SimpleNamespace(completion_text='```json\n{"decision":"reply","text":"寿"}\n```'))
    result=await plugin.bili_reply_judge(json.dumps({'public_reply':'寿','allowed_responses':{'old':'fixed'}}))
    assert result['text']=='寿'
    payload=json.loads(plugin.bounded_generate.call_args.kwargs['prompt'])
    assert 'allowed_responses' not in payload['public_input']
    assert 'private_reference' in payload
