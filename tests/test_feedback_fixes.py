import json
import pytest
from astrbot_plugin_fish_capabilities.services.valorant import ValorantRecords
from astrbot_plugin_fish_capabilities.services.sister_mail import SisterMail
from test_valorant_cache_detail import Backend,prepare

async def test_competitive_default_and_all_never_mix_deathmatch_acs(tmp_path):
    path=prepare(tmp_path);http=Backend()
    for row in http.rows[16:20]:row.update(game_enum='deathmatch',game_mode='乱斗模式',score_avg='3600',kda='40/30/0')
    reader=ValorantRecords(path,http);result=await reader.profile(20)
    assert result['observed_matches']==20 and result['sampled_matches']==16
    assert result['average_acs']==210 and result['mode_filter']=='competitive'
    assert result['observed_modes']=={'competitive':16,'deathmatch':4}
    assert (await reader.profile(20))['cached']
    all_modes=await reader.profile(20,mode='all')
    assert all_modes['sampled_matches']==20 and all_modes['average_acs'] is None
    assert next(x for x in all_modes['by_mode'] if x['mode']=='competitive')['average_acs']==210
    assert next(x for x in all_modes['by_mode'] if x['mode']=='deathmatch')['average_acs'] is None

async def test_default_detail_shorter_and_stable_reference_reuses_same_match(tmp_path):
    path=prepare(tmp_path);http=Backend();reader=ValorantRecords(path,http)
    compact=await reader.match()
    full=await reader.match(view='full')
    assert 'rounds' not in compact and 'rounds' in full
    assert len(json.dumps(compact))<len(json.dumps(full))
    reference=compact['match_ref']
    # Newer match must not change a previously issued stable reference.
    http.rows.insert(0,dict(http.rows[0],battle_id='newer',match_id='newer-match',ts=20000))
    with reader.store.connect() as db:db.execute('UPDATE sync SET stamp=0')
    await reader.profile(20)
    same=await ValorantRecords(path,http).match(match_ref=reference,view='weapons')
    assert same['match_ref']==reference and same['detail_requests']==0
    assert same['sync']['list_requests']==0 and 'rounds' not in same and 'players' not in same


def test_mail_receipt_is_saved_not_failed_and_unread_queue_has_counts(tmp_path):
    mail=SisterMail(tmp_path/'mail.db')
    result=mail.leave('fish','反馈')
    assert result['saved'] and result['storage_status']=='已存入平板本地信箱'
    assert result['recipient_notified'] is False and 'delivered_to_codex' not in result
    for n in range(6):mail.leave('fish','反馈'+str(n))
    inbox=mail.read('codex',limit=2)
    assert inbox['unread_count']==7 and inbox['unread_not_shown']==5
    assert [r['id'] for r in inbox['letters']]==[1,2]
    for letter in inbox['letters']:mail.acknowledge('codex',letter['id'])
    next_page=mail.read('codex',limit=2)
    assert next_page['unread_count']==5 and [r['id'] for r in next_page['letters']]==[3,4]
