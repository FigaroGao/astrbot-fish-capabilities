import copy,json
from astrbot_plugin_fish_capabilities.services.context_budget import slim,compact_tool


def tool_chain():
    data={'bvid':'BVexample','visual_summary':'观察'*2000,
          'evidence':[{'evidence_id':'e'+str(i),'text':'资料'+str(i)*250} for i in range(8)],
          'gallery_pages':[{'id':'last','text':'当前问题需要的最后一页文字'}]}
    return [{'role':'user','content':'最后一页具体说了什么？'},
            {'role':'assistant','content':'','tool_calls':[{'id':'call-current'}],'reasoning_content':'active protocol'},
            {'role':'tool','tool_call_id':'call-current','content':json.dumps(data,ensure_ascii=False)}]


def test_unfinished_tool_result_is_not_compressed_before_answer():
    rows=tool_chain();before=copy.deepcopy(rows)
    out=slim(rows)
    assert out==rows and rows==before
    assert '最后一页文字' in out[-1]['content']
    assert len(json.loads(out[-1]['content'])['evidence'])==8
    assert out[-1]['tool_call_id']==out[-2]['tool_calls'][0]['id']


def test_completed_tool_history_is_compressed_after_answer():
    rows=tool_chain()+[{'role':'assistant','content':'最后一页写的是……'}]
    out=slim(rows)
    assert len(out[2]['content'])<len(rows[2]['content'])
    assert len(json.loads(out[2]['content'])['evidence'])==3
    assert out[2]['tool_call_id']=='call-current' and 'reasoning_content' not in out[1]
    assert out[-1]==rows[-1]


def test_old_video_compaction_keeps_separate_source_and_annotation_basis():
    memory={'bvid':'BVexample','reading_id':'new','source_fetched_at':1900.,'last_read':2000.,
            'visual_summary':'画面'*2000,'summary':'旧摘要',
            'annotation_sources':{'summary':{'reading_id':'old','fetched_at':900.,'known':True}}}
    out=json.loads(compact_tool(json.dumps({'memories':[memory]},ensure_ascii=False)))['memories'][0]
    assert out['reading_id']=='new' and out['source_fetched_at']==1900.
    assert out['last_read']==2000. and out['annotation_sources']['summary']['reading_id']=='old'
    assert '不代表来源新鲜' in out['note']
