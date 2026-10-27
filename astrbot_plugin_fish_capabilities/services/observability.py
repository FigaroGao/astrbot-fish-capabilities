"""Read-only bounded metrics and an isolated decision replay with no transports."""
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from .policy import CapabilityError


def usage_report(path,*,since=0):
    groups=defaultdict(lambda:{'calls':0,'known_usage_calls':0,'input_other':0,'input_cached':0,'output':0,'duration_ms':0})
    for file in (Path(path).with_suffix('.previous.jsonl'),Path(path)):
        if not file.is_file():continue
        with file.open(encoding='utf-8') as stream:
            for line in stream:
                if len(line)>20000:continue
                try:row=json.loads(line)
                except (ValueError,TypeError):continue
                if not isinstance(row,dict) or not isinstance(row.get('at'),(float,int)) or row['at']<since:continue
                stage=str(row.get('stage','unknown'))[:60];g=groups[stage];g['calls']+=1
                numeric=lambda k:row[k] if type(row.get(k))in(int,float) and row[k]>=0 else 0
                if any(type(row.get(k))is int for k in ('input_other','input_cached','output')):g['known_usage_calls']+=1
                for key in ('input_other','input_cached','output','duration_ms'):g[key]+=numeric(key)
                for key in ('history_chars','memory_chars','tool_chars','original_chars','prepared_chars'):
                    if type(row.get(key))in(int,float):g[key]=g.get(key,0)+numeric(key)
    output={}
    for stage,g in groups.items():
        if not g['known_usage_calls']:
            for key in ('input_other','input_cached','output'):g[key]=None
        known=(g.get('input_other') or 0)+(g.get('input_cached') or 0)
        g['cache_hit_ratio']=g['input_cached']/known if known else None
        output[stage]=g
    return {'stages':output,'currency_cost':None,'instruction':'只统计实际已记录的用量；缺失为未知。字符数不是计费token，费用不是服务商账单。历史/记忆/工具字符分类依据片段标记估计，可能重叠，不能反推精确计费分摊。'}


async def replay(intent,scenario,*,use_model=False):
    if not isinstance(scenario,dict):raise CapabilityError('模拟输入须为对象。')
    rows=scenario.get('messages',[])
    if not isinstance(rows,list) or not 1<=len(rows)<=12:raise CapabilityError('模拟需要1至12条消息。')
    safe=[]
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('text'),str) or len(row['text'])>500:
            raise CapabilityError('模拟消息文本最多500字。')
        safe.append({'role':'user','sender_id':'member','text':row['text'],'targets':
            [{'kind':'At','id':row.get('target')}] if row.get('target') in ('bot','other') else []})
    if scenario.get('muted') is True:decision=False;reason='quiet_window'
    elif safe[-1]['targets'] and safe[-1]['targets'][0]['id']=='other':decision=False;reason='addressed_to_others'
    elif use_model:
        # An isolated shallow runtime copy uses a synthetic scope and independent
        # diagnostics. No run(), no send guard and no QQ/Bili client are invoked.
        import copy
        local=copy.copy(intent);local.last_decisions={};local.bot_id='bot'
        verdict=await local.judge('simulation',safe)
        decision=verdict is True;reason='model_preview'
    else:
        decision=bool(safe[-1]['targets'] and safe[-1]['targets'][0]['id']=='bot')
        reason='direct_rule' if decision else 'needs_intent_judgment'
    return {'should_reply':decision,'reason':reason,'mode':'model_preview' if use_model else 'rule_replay',
        'captured_actions':[],'qq_messages_sent':0,'bili_actions':0,'changed_live_state':False,
        'instruction':'规则回放不等于模型判断；模型预览只判断是否接话，不能调用工具或执行发送。'}
