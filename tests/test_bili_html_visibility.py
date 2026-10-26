import hashlib
import types
from unittest.mock import AsyncMock

from astrbot_plugin_fish_capabilities.services.bili_comments import CommentBackend,comment_text_matches
from test_bili_replies import make_inbox


def test_html_escaped_reply_matches_original_without_normalizing_the_expected_text():
    assert comment_text_matches('关于&quot;记忆&quot; &amp; 内容',text='关于"记忆" & 内容')
    assert comment_text_matches('原文 &amp;quot;文字&amp;quot;',text='原文 &quot;文字&quot;')
    assert not comment_text_matches('原文 "文字"',text='原文 &quot;文字&quot;')
    assert not comment_text_matches('不一样的内容',text='原文')


def test_digest_matching_preserves_whitespace_and_does_not_double_decode():
    digest=hashlib.sha256('"一段话"'.encode()).hexdigest()
    assert comment_text_matches('&quot;一段话&quot;',digest=digest)
    assert not comment_text_matches('&amp;quot;一段话&amp;quot;',digest=digest)
    assert not comment_text_matches(' "一段话" ',digest=digest)


async def test_author_readback_still_checks_comment_id_and_author(monkeypatch):
    import sys
    response={'replies':[{'rpid':'123','member':{'mid':'42'},'content':{'message':'&quot;文字&quot;'}}]}
    api=types.SimpleNamespace(get_comments=AsyncMock(return_value=response),CommentResourceType=types.SimpleNamespace(VIDEO=1),OrderType=types.SimpleNamespace(TIME=0))
    monkeypatch.setitem(sys.modules,'bilibili_api',types.SimpleNamespace(comment=api))
    backend=CommentBackend(types.SimpleNamespace(credential=lambda:'synthetic'))
    assert await backend.verify(456,'123','42','"文字"')
    assert not await backend.verify(456,'123','other','"文字"')
    assert not await backend.verify(456,'wrong','42','"文字"')


async def test_anonymous_readback_decodes_only_returned_body(monkeypatch):
    class Public:
        async def get(self,*args):return {'code':0,'data':{'replies':[{'rpid':'123','member':{'mid':'42'},'content':{'message':'&quot;文字&quot;'}}]}}
    monkeypatch.setattr('astrbot_plugin_fish_capabilities.services.bili_comments.PublicJSON',Public)
    assert await CommentBackend(None).verify_public(456,'123','42','"文字"') is True


async def test_own_thread_root_validation_accepts_legacy_html_representation(tmp_path):
    inbox,backend,judge,notify,now=await make_inbox(tmp_path,choice={'decision':'ignore'})
    original='一个"具体"感受。'
    with inbox.reader.connect() as db:db.execute('UPDATE bili_comments SET text_hash=? WHERE key=?',(hashlib.sha256(original.encode()).hexdigest(),'original'))
    backend.root_body='一个&quot;具体&quot;感受。'
    result=await inbox.check()
    assert result['thread_errors']==0 and result['new']==1 and not backend.sent
