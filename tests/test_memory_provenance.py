from types import SimpleNamespace
from astrbot_plugin_fish_capabilities.services.memory_provenance import (
    attach_source_context, correction_provenance, injection_label, select_slots, stamp,
    grounded_claims, claims_for_injection)


def row(text, kind='summary', **extra):
    return {'content':text,'metadata':{'session_id':'private','persona_id':'fish',
        'fish_provenance':dict(kind=kind,observed_at=1000,**extra)}}


def test_source_window_uses_actual_user_evidence_and_redacts():
    messages=[SimpleNamespace(role='user',sender_id='one',content='我喜欢海洋',timestamp=1000),
              SimpleNamespace(role='assistant',sender_id='bot',content='主人是医生',timestamp=1001),
              SimpleNamespace(role='user',sender_id='two',content='token=secret',timestamp=1002)]
    original={'topics':['海洋']}
    data=attach_source_context(original,messages,owner_id='one')
    evidence=data['fish_provenance']['evidence']
    assert len(evidence)==1 and evidence[0]['excerpt']=='我喜欢海洋'
    assert data['fish_provenance']['kind']=='summary' and original=={'topics':['海洋']}
    assert 'secret' not in str(attach_source_context({},messages))


def test_expired_or_unknown_states_do_not_assert_present():
    assert injection_label(row('在上课','state')['metadata'],now=9000) is None
    assert injection_label({'fish_provenance':{'kind':'state'}},now=2000) is None
    assert injection_label(row('在上课','state')['metadata'],now=2000)
    assert injection_label(row('睡觉','state',expires_at=1500)['metadata'],now=1500) is None
    assert injection_label(row('旧事实','fact',status='superseded')['metadata'],now=2000) is None


def test_legacy_and_guesses_are_not_promoted_to_facts():
    assert '历史摘要' in injection_label({},now=2000)
    assert '主观推测' in injection_label(row('可能喜欢','inference')['metadata'],now=2000)
    assert '不是现实经历' in injection_label(row('虚构日常','fiction')['metadata'],now=2000)


def test_slots_bound_legacy_noise_and_preserve_other_channels():
    records=[row('旧摘要1'),row('旧摘要1'),row('旧摘要2'),row('旧摘要3'),
             row('稳定事实','fact'),row('在上课','state'),row('过期','state',expires_at=1900)]
    chosen=select_slots(records,now=2000)
    assert [r['content'] for r in chosen]==['旧摘要1','旧摘要2','稳定事实','在上课']
    assert len(records)==7


def test_correction_retains_explicit_supersession_and_actual_evidence():
    old={'fish_provenance':{'kind':'state','observed_at':1000}}
    fixed=correction_provenance(old,ident=12,evidence='现在已经下课了',observed_at=2000,historical=False)
    p=fixed['fish_provenance']
    assert p['supersedes']==12 and p['kind']=='summary' and p['basis']=='owner_correction'
    historical=correction_provenance(old,ident=12,evidence='当时在上课',observed_at=2000,historical=True)
    assert historical['fish_provenance']['observed_at']==1000
    assert old['fish_provenance']['kind']=='state'


def test_invalid_dates_do_not_become_fake_current_times():
    assert stamp(True) is None and stamp(float('nan')) is None
    assert stamp('2026-10-27 01:00:00') is None
    assert stamp('2026-10-27T01:00:00+08:00')
    assert stamp(1e100) is None


def test_malformed_metadata_does_not_break_the_entire_recall_hook():
    item={'content':'历史记录','metadata':{'session_id':[], 'persona_id':{},
        'fish_provenance':{'kind':[], 'status':{}, 'basis':[]}}}
    assert len(select_slots([item],now=2000))==1
    assert '历史摘要' in injection_label(item['metadata'],now=2000)


def test_atom_claims_require_real_user_quote_matching_sender_and_time():
    messages=[dict(role='user',sender_id='one',timestamp=1000,content='我喜欢海洋生物'),
              dict(role='assistant',sender_id='bot',timestamp=1001,content='他是医生')]
    base=dict(text='喜欢海洋生物',kind='fact',evidence_quote='我喜欢海洋生物',evidence_sender_id='one')
    claims=grounded_claims({'claims':[base,dict(base,evidence_sender_id='two'),
        dict(base,text='是医生',evidence_quote='他是医生',evidence_sender_id='bot')]},messages)
    assert len(claims)==1 and claims[0]['kind']=='fact'
    assert claims[0]['evidence'][0]['sender_id']=='one'


def test_expired_state_claim_does_not_hide_stable_preference_or_leak_old_claim():
    messages=[dict(role='user',sender_id='one',timestamp=1000,content='我喜欢海洋生物，现在在上课')]
    claims=grounded_claims({'claims':[
        dict(text='喜欢海洋生物',kind='fact',evidence_quote='我喜欢海洋生物',evidence_sender_id='one'),
        dict(text='现在在上课',kind='fact',evidence_quote='现在在上课',evidence_sender_id='one')]},messages)
    assert [c['kind'] for c in claims]==['fact','state']
    output=claims_for_injection({'fish_claims':claims},now=10000)
    assert '喜欢海洋生物' in output and '现在在上课' not in output
    assert claims_for_injection({'fish_claims':claims[1:]},now=10000)==''
    assert claims_for_injection({},now=10000) is None
