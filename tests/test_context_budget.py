import copy,json
import pytest
from astrbot_plugin_fish_capabilities.services.context_budget import ContextBudget
from astrbot_plugin_fish_capabilities.services.delivery import segments

def history(n):
 return [m for i in range(n) for m in [{'role':'user','content':'主人事实 '+str(i)},{'role':'assistant','content':'回答 '+str(i)}]]

async def test_summary_keeps_eight_rounds_and_reuses_cached_prefix(tmp_path):
 calls=[]
 async def generate(prompt):calls.append(prompt);return '主人重要事实和未完成约定摘要'
 b=ContextBudget(tmp_path/'s.db',generate);rows=history(20);original=copy.deepcopy(rows)
 result,stats=await b.prepare('private|cid|persona',rows)
 assert result[2:]==rows[-16:] and rows==original and stats['outcome']=='summarized'
 result2,stats=await b.prepare('private|cid|persona',history(21))
 assert len(calls)==1 and result2[2:]==history(21)[24:]
 await b.prepare('group|cid|persona',rows)
 assert len(calls)==2

async def test_summary_failure_never_discards_chat(tmp_path):
 async def generate(prompt):raise TimeoutError()
 b=ContextBudget(tmp_path/'s.db',generate);rows=history(20)
 result,stats=await b.prepare('scope',rows)
 assert result==rows and stats['outcome']=='summary_failed'

async def test_old_images_not_in_summary_recent_images_retained(tmp_path):
 calls=[]
 async def generate(prompt):calls.append(prompt);return '仅已有文字事实'
 rows=history(20)
 rows[0]['content']=[{'type':'image_url','image_url':{'url':'data:image/png;base64,SECRETOLDIMAGE'}}]
 rows[-2]['content']=[{'type':'image_url','image_url':{'url':'data:image/png;base64,RECENTIMAGE'}}]
 b=ContextBudget(tmp_path/'s.db',generate);result,_=await b.prepare('scope',rows)
 assert 'SECRETOLDIMAGE' not in ''.join(calls) and 'RECENTIMAGE' in json.dumps(result)

async def test_reset_conversation_does_not_reuse_old_summary(tmp_path):
 async def generate(prompt):return '旧会话摘要'
 b=ContextBudget(tmp_path/'s.db',generate);await b.prepare('scope',history(20))
 rows=[{'role':'user','content':'完全新的对话'}]
 result,_=await b.prepare('scope',rows);assert result==rows

def test_proactive_segments_are_short_and_keep_video_link_whole():
 url='https://www.bilibili.com/video/BV1234567890'
 parts=segments('我看到一条鲸鱼视频。它的潜水方式挺有意思的！\n'+url)
 assert 1<=len(parts)<=3 and url in parts[-1]
 assert all('【小鲸的B站发现】' not in x for x in parts)


def test_long_proactive_text_is_split_even_without_punctuation():
    parts=segments('字'*180+'\nhttps://www.bilibili.com/video/BV1234567890')
    assert len(parts)==3 and all(len(p.split('\n')[0])<=90 for p in parts)


async def test_summary_failure_cooldown_and_partial_resume(tmp_path):
    calls=[]
    async def generate(prompt):
        calls.append(prompt)
        if len(calls)==2:raise TimeoutError()
        return '已完成部分事实摘要'
    b=ContextBudget(tmp_path/'s.db',generate);rows=history(40)
    for row in rows:row['content']+='内容'*300
    result,stats=await b.prepare('scope',rows)
    assert stats['outcome']=='summary_failed'
    _,stats=await b.prepare('scope',rows)
    assert stats['outcome']=='summary_failure_cooldown' and len(calls)==2
    with b.db() as db:
        progress=db.execute('SELECT offset FROM migrations WHERE scope=?',('scope',)).fetchone()[0]
        db.execute('UPDATE failed_attempts SET stamp=stamp-601')
    assert progress==16000
    result,stats=await b.prepare('scope',rows)
    assert stats['outcome']=='summarized' and len(result)==18
    with b.db() as db:assert not db.execute('SELECT 1 FROM migrations').fetchone()


async def test_reasoning_not_used_as_summary_facts_but_recent_protocol_preserved(tmp_path):
    seen=[]
    async def generate(prompt):seen.append(prompt);return '保留主人事实'
    rows=history(20);rows[1]['reasoning_content']='OLDREASONING';rows[-1]['reasoning_content']='RECENTREASONING'
    b=ContextBudget(tmp_path/'s.db',generate);result,_=await b.prepare('scope',rows)
    assert 'OLDREASONING' not in ''.join(seen)
    assert result[-1]['reasoning_content']=='RECENTREASONING'


def test_ordinary_dialogue_splits_without_truncating():
    from astrbot_plugin_fish_capabilities.services.delivery import dialog_segments
    text='这是一段需要完整保留的长回复。'*40
    parts=dialog_segments(text)
    assert len(parts)>1 and all(len(x)<=120 for x in parts)
    assert ''.join(parts)==text
    url='https://www.bilibili.com/video/BV1234567890'
    assert url in dialog_segments('看看这个\n'+url)
    code='```python\n'+('print(1)\n'*30)+'```'
    assert code in dialog_segments('代码如下：'+code)


def test_long_video_tool_keeps_claude_identity_and_visual_basis():
    from astrbot_plugin_fish_capabilities.services.context_budget import compact_tool
    packet={'bvid':'BVtest','visual_summary':'长'*2200,'character_matches':[{'character_id':'claude.orange-scholar','name':'Claude橙发形象','family':'Claude','confidence':.98,'visible_evidence':'画面橙发与太阳形头饰','frame_ids':['f2'],'account_identity_verified':True}],
            'character_meme_context':[{'kind':'community_usage','meaning':'不当作官方关系'}]}
    result=json.loads(compact_tool(json.dumps(packet,ensure_ascii=False)))
    assert result['character_matches'][0]['name']=='Claude橙发形象'
    assert '太阳' in result['character_matches'][0]['visible_evidence']
    assert result['character_matches'][0]['account_identity_verified'] is False
    nested=json.loads(compact_tool(json.dumps({'total_videos':1,'memories':[packet]},ensure_ascii=False)))
    assert nested['memories'][0]['character_matches'][0]['family']=='Claude'
    assert nested['memories'][0]['character_meme_context']
