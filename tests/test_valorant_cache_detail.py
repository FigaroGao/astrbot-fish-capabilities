import json,time
from pathlib import Path
import pytest
from astrbot_plugin_fish_capabilities.services.valorant import ValorantRecords,private_save
from test_astrbot_binding import plugin,Event
from unittest.mock import AsyncMock

class Backend:
    def __init__(self):
        self.calls=[]
        self.rows=[{'battle_id':str(i),'match_id':'match-'+str(i),'ts':10000-i,'hero_name':'零','game_enum':'competitive','game_mode':'竞技模式','kda':'12/10/3','score_avg':'210','performance_score':'262','round_won':2,'round_fail':1} for i in range(30)]
    async def post(self,path,data,auth=None):
        self.calls.append((path,data))
        if path=='/go/account/get_main_role_raw':return {'result':0,'data':{'list':[{'game_role_id':'owner-role','scene':'secret-scene','role_name':'owner'}]}}
        if path=='/go/agame/career/record/list':
            page=data['page_no'];return {'result':0,'data':{'battle_list':self.rows[(page-1)*10:page*10],'next_baton':'synthetic'}}
        if '/scoreboard?' in path:return {'result':0,'data':{'scoreboard':[
            {'is_me':1,'role_id':'owner-role','team':'Blue','score_avg':'210','performance_score':'262','head_shots_rate':'29.73%','scene':'secret-scene'},
            {'is_me':0,'role_id':'other','team':'Blue','user_name':'teammate','kda':'15/11/4'},
            {'is_me':0,'role_id':'enemy','team':'Red','user_name':'opponent','kda':'18/10/2'}]}}
        if '/roundoverview?' in path:return {'result':0,'data':{'weapons':[{'used_gun':{'name':'狂徒'},'kills':7,'head_shot_rate':'25%'}],'opponents':[{'role_id':'enemy','used_agent':{'name':'捷风'},'kills':4,'deaths':2}]}}
        if '/rounds?' in path:return {'result':0,'data':{'rounds':[{'round_num':-1,'kills':12},{'round_num':0,'kills':3},{'round_num':1,'kills':4},{'round_num':2,'kills':5}]}}
        raise AssertionError(path)

def prepare(tmp_path):
    path=tmp_path/'credentials.json';private_save(path,{'userId':'synthetic','tid':'private-ticket','login_type':'wechat'});return path

async def test_persistent_incremental_sync_reuses_old_twenty_and_adds_only_new_head(tmp_path):
    path=prepare(tmp_path);http=Backend();first=await ValorantRecords(path,http).profile(20)
    assert first['sampled_matches']==20 and first['sync']['list_requests']==2
    assert first['average_acs']==210 and first['average_performance_score']==262
    restored=ValorantRecords(path,http);second=await restored.profile(20)
    assert second['sync']['list_requests']==0 and second['sync']['stored_matches']==20
    with restored.store.connect() as db:db.execute('UPDATE sync SET stamp=0')
    http.rows.insert(0,dict(http.rows[0],battle_id='new',match_id='new-match',ts=20000))
    third=await ValorantRecords(path,http).profile(20)
    assert third['sync']['list_requests']==1 and third['sync']['new_matches']==1 and third['sync']['stored_matches']==21
    raw=json.dumps(restored.store.rows(restored.account({'userId':'synthetic'},{'game_role_id':'owner-role'})))
    assert 'private-ticket' not in raw and 'secret-scene' not in raw

async def test_full_match_uses_official_acs_exact_multikills_and_persistent_details(tmp_path):
    path=prepare(tmp_path);http=Backend();reader=ValorantRecords(path,http)
    packet=await reader.match(1)
    assert packet['official_acs']==210 and packet['performance_score']==262
    assert packet['multi_kill_rounds']=={'3':1,'4':1,'5':1} and packet['multi_kill_data_complete']
    assert [p['side'] for p in packet['players']]==['self','teammate','opponent']
    assert packet['weapons'][0]['name']=='狂徒' and packet['self']['head_shots_rate']=='29.73%'
    assert packet['detail_requests']==3 and 'secret-scene' not in json.dumps(packet)
    second=await ValorantRecords(path,http).match(1)
    assert second['detail_requests']==0 and set(second['parts_status'].values())=={'cached'}
    account=reader.account({'userId':'synthetic'},{'game_role_id':'owner-role'})
    assert 'secret-scene' not in json.dumps(reader.store.detail(account,'0','scoreboard'))

async def test_account_change_cannot_read_other_account_cache(tmp_path):
    path=prepare(tmp_path);http=Backend();await ValorantRecords(path,http).profile(20)
    private_save(path,{'userId':'different','tid':'different-ticket','login_type':'wechat'})
    result=await ValorantRecords(path,http).profile(20)
    assert result['sync']['list_requests']==2

async def test_missing_rounds_or_partial_details_are_not_fabricated_zero(tmp_path):
    class Partial(Backend):
        async def post(self,path,data,auth=None):
            if '/rounds?' in path:return {'result':0,'data':{}}
            return await super().post(path,data,auth)
    path=prepare(tmp_path);http=Partial();result=await ValorantRecords(path,http).match()
    assert result['multi_kill_rounds'] is None and result['parts_status']['rounds']=='unavailable'
    http.calls.clear();await ValorantRecords(path,http).match()
    # Failed/empty parts are not permanently cached, successful parts are reused.
    assert not any('/scoreboard?' in p for p,d in http.calls)

async def test_detail_tool_stays_owner_private(plugin):
    plugin.config['valorant_enabled']=True;plugin.valorant_records.match=AsyncMock(return_value={'official_acs':210})
    assert json.loads(await plugin.valorant_match(Event(private=False)))['ok'] is False
    assert json.loads(await plugin.valorant_match(Event(sender='other',admin=False)))['ok'] is False
    plugin.valorant_records.match.assert_not_awaited()
    assert json.loads(await plugin.valorant_match(Event()))['official_acs']==210


async def test_seeded_first_match_does_not_cause_extra_third_page(tmp_path):
    path=prepare(tmp_path);http=Backend();reader=ValorantRecords(path,http)
    account=reader.account({'userId':'synthetic'},{'game_role_id':'owner-role'})
    reader.store.ingest(account,http.rows[:1])
    result=await reader.profile(20)
    assert result['sampled_matches']==20 and result['sync']['list_requests']==2
