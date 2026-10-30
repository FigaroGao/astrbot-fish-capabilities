import json,copy
from astrbot_plugin_fish_capabilities.services.context_budget import slim
from astrbot_plugin_fish_capabilities.services.bili_mentions import reply_material

def test_old_media_and_thoughts_removed_recent_protocol_preserved():
    rows=[{'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,OLD'}}]},
          {'role':'assistant','content':[{'type':'think','think':'OLD_THOUGHT'},{'type':'text','text':'已说明图片内容'}],'reasoning_content':'OLD_THOUGHT'},
          {'role':'user','content':'第二轮'},{'role':'assistant','content':'回答'},
          {'role':'user','content':'第三轮'},{'role':'assistant','content':'回答','reasoning_content':'CURRENT_PROTOCOL'}]
    original=copy.deepcopy(rows);out=slim(rows);text=json.dumps(out,ensure_ascii=False)
    assert 'base64,OLD' not in text and 'OLD_THOUGHT' not in text
    assert '已说明图片内容' in text and out[-1]['reasoning_content']=='CURRENT_PROTOCOL'
    assert original==rows

def test_invitation_never_cut_off_by_long_video():
    packet={'visual_summary':'画面'*30000,'description':'简介'*20000,'evidence':[{'evidence_id':'e1','text':'字幕'*30000}],'comments':['评论'*20000]}
    out=reply_material(packet,{'item':{'source_content':'@小鲸 这个和你像不像？'}})
    assert out['owner_public_comment']=='@小鲸 这个和你像不像？'
    encoded=json.dumps(out,ensure_ascii=False)
    assert json.loads(encoded)==out and len(encoded)<10000 and out['evidence'][0]['evidence_id']=='e1'

def test_image_lifecycle_completed_vs_unfinished_tool_turn():
    image={'role':'user','content':[{'type':'text','text':'看这张图'},{'type':'image_url','image_url':{'url':'data:image/png;base64,CURRENT'}}]}
    assert 'base64,CURRENT' in json.dumps(slim([image]))
    tool_turn=[image,{'role':'assistant','tool_calls':[{'id':'1'}],'content':''},{'role':'tool','content':'正在查询'}]
    assert 'base64,CURRENT' in json.dumps(slim(tool_turn))
    done=[image,{'role':'assistant','content':'图片里的文字是你好'}]
    clean=slim(done)
    assert 'base64,CURRENT' not in json.dumps(clean) and clean[-1]['content']=='图片里的文字是你好'
    assert 'base64,CURRENT' in json.dumps(done)
