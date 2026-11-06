import json
import pytest
from astrbot_plugin_fish_capabilities.services.context_budget import compact_tool,slim


@pytest.mark.parametrize('material',[{'bvid':'BVexample','description':'资料'*2000},{'memories':[],'details':'资料'*2000},{'items':['资料'*2000]}])
def test_long_failed_results_keep_failure_outcome(material):
    # Flags deliberately occur after the long payload in serialized order.
    value=dict(material,ok=False,state='query_failed',reason='权限不足，未执行')
    compact=json.loads(compact_tool(json.dumps(value,ensure_ascii=False)))
    assert compact['ok'] is False and compact['state']=='query_failed'
    assert compact['reason']=='权限不足，未执行'


def test_large_receipt_does_not_turn_submission_into_verified_visibility():
    value={'details':'说明'*2000,'submitted':True,'confirmed':False,'publicly_visible_verified':False,'notification_received_verified':False}
    compact=json.loads(compact_tool(json.dumps(value,ensure_ascii=False)))
    assert compact['submitted'] is True and compact['confirmed'] is False
    assert compact['publicly_visible_verified'] is False and compact['notification_received_verified'] is False
    assert compact['truncated'] and '不是完整结构' in compact['note']


def test_malformed_optional_evidence_does_not_break_history_preparation():
    value={'bvid':'BVexample','description':'说明'*2000,'evidence':None,'ok':False}
    row={'role':'tool','tool_call_id':'id','content':json.dumps(value,ensure_ascii=False)}
    compact=json.loads(slim([{'role':'user','content':'query'},row,{'role':'assistant','content':'失败说明'}])[1]['content'])
    assert compact['evidence']==[] and compact['evidence_status']=='invalid_or_unavailable'
    assert compact['ok'] is False


def test_current_failed_result_is_still_original_not_compacted_early():
    text=json.dumps({'details':'资料'*2000,'ok':False,'reason':'本轮需要完整查看的错误细节'},ensure_ascii=False)
    rows=[{'role':'user','content':'查一下'},{'role':'assistant','tool_calls':[{'id':'x'}]}, {'role':'tool','tool_call_id':'x','content':text}]
    assert slim(rows)[-1]['content']==text
