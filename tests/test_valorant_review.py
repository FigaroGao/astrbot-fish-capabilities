from unittest.mock import AsyncMock
import pytest,json
from astrbot_plugin_fish_capabilities.services.valorant_review import hs,brief
from astrbot_plugin_fish_capabilities.services.valorant import ValorantRecords
from astrbot_plugin_fish_capabilities.services.valorant_cache import MatchCache
from test_astrbot_binding import plugin,Event

def test_hs_missing_is_not_zero_and_fraction_is_not_guessed():
    assert hs({}) is None and hs({'head_shots_rate':'.25'}) is None
    assert hs({'head_shots_rate':'25%'})==25
    assert hs({'total_head_shots':2,'total_body_shots':6,'total_leg_shots':2})==20
    assert hs({'total_head_shots':0,'total_body_shots':0,'total_leg_shots':0}) is None

async def test_review_excludes_current_and_other_modes_and_uses_cached_details(tmp_path):
    r=ValorantRecords(tmp_path/'login.json');r.credentials=lambda:{};r.role=AsyncMock(return_value={'game_role_id':'mine'});r.account=lambda *a:'a'
    rows=[{'battle_id':'new','ts':4,'game_enum':'competitive','score_avg':250}, {'battle_id':'dm','ts':3,'game_enum':'deathmatch','score_avg':900}, {'battle_id':'old','ts':2,'game_enum':'competitive','score_avg':200}]
    r.store.ingest('a',rows);r.store.save_detail('a','old','scoreboard',{'scoreboard':[{'is_me':1,'score_avg':200,'head_shots_rate':'20%'}]})
    r.match=AsyncMock(return_value={'match_ref':'new','official_acs':250,'self':{'head_shots_rate':'25%'},'players':[]})
    result=await r.review()
    assert result['acs']=={'current':250,'previous_average':200.0,'sample_count':1,'delta':50.0}
    assert result['head_hit_percent']['delta']==5 and result['baseline']['match_refs']==['old']
    assert r.http is not None

def test_ties_and_missing_baseline_are_explicit(tmp_path):
    store=MatchCache(tmp_path/'c.db');p={'official_acs':100,'self':{},'players':[{'side':'teammate','name':n,'score_avg':100} for n in ['a','b']]}
    result=brief(p,{'game_enum':'competitive'},[],store,'a',{})
    assert len(result['players_by_current_acs']['teammate']['highest_acs'])==2
    assert result['acs']['delta'] is None and result['head_hit_percent']['current'] is None

async def test_review_tool_is_private_owner_only(plugin):
    plugin.config['valorant_enabled']=True;plugin.valorant_records.review=AsyncMock(return_value={'brief':True})
    assert json.loads(await plugin.valorant_review(Event()))['brief']
    assert json.loads(await plugin.valorant_review(Event(private=False)))['ok'] is False
    assert json.loads(await plugin.valorant_review(Event(sender='other')))['ok'] is False
