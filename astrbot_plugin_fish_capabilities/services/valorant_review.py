"""Small, deterministic match comparisons; never infer blame from a scoreboard."""
import re
from .valorant import number,average,mode_of,player_packet

def hs(player):
    if not player:return None
    counts=[number(player.get(k)) for k in ('total_head_shots','total_body_shots','total_leg_shots')]
    if all(x is not None for x in counts) and sum(counts)>0:return round(counts[0]/sum(counts)*100,2)
    raw=str(player.get('head_shots_rate','')).strip()
    if re.fullmatch(r'\d+(?:\.\d+)?%',raw):
        value=float(raw[:-1]);return value if 0<=value<=100 else None
    return None

def comparison(current,values):
    values=[v for v in values if v is not None];mean=average(values)
    return {'current':current,'previous_average':mean,'sample_count':len(values),'delta':round(current-mean,2) if current is not None and mean is not None else None}

def brief(packet,row,prior,store,account,role):
    mode=mode_of(row);comparable=mode in ('competitive','unrated');acs=[];rates=[];refs=[]
    for old in prior:
        board=store.detail(account,old['battle_id'],'scoreboard') or {}
        me=next((p for p in board.get('scoreboard',[]) if p.get('is_me')==1 or p.get('role_id')==role.get('game_role_id')),None)
        score=number(me.get('score_avg')) if me else None
        acs.append(score if score is not None else number(old.get('score_avg')))
        rates.append(hs(me));refs.append(str(old['battle_id']))
    sides={}
    for side in ('teammate','opponent'):
        rows=[p for p in packet.get('players',[]) if p.get('side')==side and number(p.get('score_avg')) is not None]
        def short(p):return {k:p.get(k) for k in ('name','agent','kda','score_avg')}
        sides[side]={'highest_acs':[short(p) for p in rows if p['score_avg']==max(x['score_avg'] for x in rows)],'lowest_acs':[short(p) for p in rows if p['score_avg']==min(x['score_avg'] for x in rows)]} if rows else {'highest_acs':[],'lowest_acs':[]}
    return {'match':{k:packet.get(k) for k in ('match_ref','played_at','map','mode','result','rounds_won','rounds_lost')},
            'self':{k:(packet.get('self') or {}).get(k) for k in ('agent','kda','head_shots_rate')},
            'acs':comparison(packet.get('official_acs'),acs) if comparable else {'current':packet.get('official_acs'),'previous_average':None,'sample_count':0,'delta':None},
            'head_hit_percent':comparison(hs(packet.get('self')),rates) if comparable else comparison(hs(packet.get('self')),[]),
            'baseline':{'mode':mode,'matches_selected':len(prior),'match_refs':refs,'headshot_policy':'只复用已缓存详情，不额外为前五局拉完整详情；无可比较值就缺失，不填0。'},
            'players_by_current_acs':sides,'multi_kill_rounds':packet.get('multi_kill_rounds'),'parts_status':packet.get('parts_status'),
            'instruction':'仅主人私聊。用几句自然话给最近这局简版复盘，不倾倒整表。最高/最低仅指本局ACS，包含并列，不等于谁最坑或责任归属；不据此辱骂或判人格。ACS是官方score_avg而非表现分。爆头是命中百分比，delta单位为百分点，不是爆头击杀率。比较排除本局，只选更早同模式最多五局；明确各指标有效样本数，样本少不作长期结论。未知说缺数据；不能把最新已同步对局当刚结束的实时对局，先核对比赛时间。'}
