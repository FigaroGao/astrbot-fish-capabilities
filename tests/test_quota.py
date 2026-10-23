import json
import pytest
from astrbot_plugin_fish_capabilities.services.quota import Quota
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError

async def test_balance_uses_cache_and_does_not_expose_key(tmp_path):
    p=tmp_path/'config.json';p.write_text(json.dumps({'provider_sources':[{'id':'deepseek','api_base':'https://api.deepseek.com/v1','key':['test-key']}]}))
    calls=[]
    async def fetch(key):
        calls.append(key);return {'is_available':True,'balance_infos':[{'currency':'CNY','total_balance':'10','granted_balance':'0','topped_up_balance':'10'}]}
    quota=Quota(p,fetch)
    result=await quota.get();assert 'test-key' not in json.dumps(result)
    assert (await quota.get())['cached'] and len(calls)==1
    assert 'aliyun' not in result

async def test_daily_balance_is_partial_persistent_and_handles_topups(tmp_path):
    p=tmp_path/'config.json';p.write_text(json.dumps({'provider_sources':[{'id':'deepseek','api_base':'https://api.deepseek.com/v1','key':['test-key']}]}))
    now=[1792684800];amount=['10']
    async def fetch(key):return {'balance_infos':[{'currency':'CNY','total_balance':amount[0]}]}
    state=tmp_path/'state.json'
    q=Quota(p,fetch,state_path=state,clock=lambda:now[0])
    first=(await q.get())['today_balance_change']
    assert first['net_balance_decrease'][0]['amount']=='0'
    now[0]+=300;amount[0]='8.75'
    # Restart preserves the first sample of the day.
    q=Quota(p,fetch,state_path=state,clock=lambda:now[0])
    second=(await q.get())['today_balance_change']
    assert second['from']==first['from'] and second['net_balance_decrease'][0]['amount']=='1.25'
    now[0]+=300;amount[0]='20'
    assert (await q.get())['today_balance_change']['status']=='balance_increased_unreliable'
    now[0]+=86400
    tomorrow=(await q.get())['today_balance_change']
    assert tomorrow['status']=='partial_day_net_change' and tomorrow['from']==now[0]

def test_today_tokens_only_deepseek_and_current_day(tmp_path):
    import sqlite3
    p=tmp_path/'stats.db';now=1792688400
    with sqlite3.connect(p) as db:
        db.execute('CREATE TABLE provider_stats(provider_id TEXT,start_time REAL,token_input_other INT,token_input_cached INT,token_output INT)')
        db.executemany('INSERT INTO provider_stats VALUES(?,?,?,?,?)',[
            ('deepseek/flash',now-1,10,20,30),('other/model',now-1,100,100,100),('deepseek/flash',now-86400,200,200,200)])
    result=Quota(tmp_path/'config',stats_path=p).usage(now)
    assert result['requests']==1 and result['total_tokens']==60

def test_invalid_amount_does_not_create_history(tmp_path):
    q=Quota(tmp_path/'config',state_path=tmp_path/'history')
    assert q.track([{'currency':'CNY','total_balance':'NaN'}],1792684800)['status']=='unavailable'
    assert not q.state_path.exists()

async def test_balance_refuses_third_party(tmp_path):
    p=tmp_path/'config.json';p.write_text(json.dumps({'provider_sources':[{'id':'deepseek','api_base':'https://other.invalid/v1','key':['test-key']}]}))
    async def forbidden(key):raise AssertionError('Must not send credentials')
    with pytest.raises(CapabilityError):await Quota(p,forbidden).get()
