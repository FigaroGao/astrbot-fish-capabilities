"""Deterministic owner-private analysis of already captured matches.

No model call, guessed endpoint, per-player history request or remote write.
"""
import hashlib
import re
from collections import defaultdict
from datetime import datetime

from .local_time import local_zone
from .policy import CapabilityError, bounded_int
from .valorant import number, average, clean, mode_of


def summary(rows):
    k=d=a=valid=0;wins=losses=draws=0
    modes={mode_of(r) for r in rows}
    for r in rows:
        match=re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*',str(r.get('kda','')))
        if match:
            ki,de,ass=map(int,match.groups());k+=ki;d+=de;a+=ass;valid+=1
        result=str(r.get('result_title','')).casefold()
        wins+=result in ('获胜','胜利','win');losses+=result in ('失败','战败','loss');draws+=result in ('平局','draw')
    scores=[number(r.get('score_avg')) for r in rows]
    return {'matches':len(rows),'known_results':wins+losses+draws,'wins':wins,'losses':losses,'draws':draws,
            'win_rate':round(wins/(wins+losses),4) if wins+losses else None,
            'kills':k if valid else None,'deaths':d if valid else None,'assists':a if valid else None,
            'kda_samples':valid,'kd':round(k/d,3) if valid and d else None,
            'average_acs':average(scores) if len(modes)==1 and modes<={'competitive','unrated'} else None,
            'acs_samples':sum(s is not None for s in scores) if len(modes)==1 and modes<={'competitive','unrated'} else 0}


def select(rows,config,mode='competitive',agent='',map_name='',since='',until=''):
    if mode not in ('competitive','unrated','deathmatch','all'):raise CapabilityError('模式应为competitive、unrated、deathmatch或all。')
    for text in (agent,map_name,since,until):
        if not isinstance(text,str) or len(text)>100:raise CapabilityError('筛选条件格式不正确。')
    def boundary(value):
        if not value:return None
        try:
            dt=datetime.fromisoformat(value)
            return (dt if dt.tzinfo else dt.replace(tzinfo=local_zone(config))).timestamp()
        except ValueError:raise CapabilityError('日期使用ISO格式；until为不包含的上界。') from None
    start,end=boundary(since),boundary(until)
    if start is not None and end is not None and start>=end:raise CapabilityError('开始时间必须早于结束时间。')
    result=[];unknown=0
    for row in rows:
        if mode!='all' and mode_of(row)!=mode:continue
        if agent and agent.casefold() not in clean(row.get('hero_name')).casefold():continue
        if map_name and map_name.casefold() not in clean((row.get('used_map') or {}).get('name')).casefold():continue
        stamp=number(row.get('ts'))
        if start is not None or end is not None:
            if stamp is None:unknown+=1;continue
            if (start is not None and stamp<start) or (end is not None and stamp>=end):continue
        result.append(row)
    return result,unknown


def report(rows,view,store,account,role,config):
    if view not in ('overview','maps','agents','trend','weapons','teammates'):raise CapabilityError('不支持的统计视图。')
    base={'view':view,'sampled_matches':len(rows),
          'instruction':'仅绑定角色已缓存样本，非完整生涯或实时状态，不向群/B站公开。未知不填0；ACS不混合不同模式。描述数据，不据此辱骂玩家或推断人格。'}
    if view=='overview':return dict(base,summary=summary(rows))
    if view in ('maps','agents'):
        groups=defaultdict(list)
        for row in rows:
            label=clean((row.get('used_map') or {}).get('name')) if view=='maps' else clean(row.get('hero_name'))
            groups[label or '未知'].append(row)
        return dict(base,items=[dict(name=name,**summary(group)) for name,group in sorted(groups.items(),key=lambda x:-len(x[1]))[:15]])
    if view=='trend':
        split=min(10,len(rows)//2)
        recent,previous=summary(rows[:split]),summary(rows[split:split*2])
        comparable=split>=3 and len({mode_of(r) for r in rows[:split*2]})==1
        delta={key:round(recent[key]-previous[key],3) if comparable and recent[key] is not None and previous[key] is not None else None for key in ('average_acs','kd','win_rate')}
        return dict(base,recent=recent,previous=previous,comparable=comparable,delta=delta,
                    note='按缓存顺序比较最近与更早等量样本，每组最多10场、至少3场才报告差值；不是因果判断或长期水平。')
    groups={};covered=0
    for row in rows:
        battle=row.get('battle_id')
        if view=='weapons':
            data=store.detail(account,battle,'roundoverview') or {};weapons=data.get('weapons')
            if not isinstance(weapons,list):continue
            covered+=1;seen=set()
            for weapon in weapons[:30]:
                name=clean((weapon.get('used_gun') or {}).get('name'))
                if not name:continue
                g=groups.setdefault(name,{'name':name,'matches':0,'kills':0,'kill_samples':0,'damage':0,'damage_samples':0})
                if name not in seen:g['matches']+=1;seen.add(name)
                for key in ('kills','damage'):
                    value=number(weapon.get(key))
                    if value is not None:g[key]+=value;g['kill_samples' if key=='kills' else 'damage_samples']+=1
        else:
            data=store.detail(account,battle,'scoreboard') or {};players=data.get('scoreboard')
            if not isinstance(players,list):continue
            me=next((p for p in players if p.get('role_id')==role.get('game_role_id') or p.get('is_me')==1),None)
            if not me or not me.get('team'):continue
            covered+=1;seen=set()
            for player in players[:10]:
                ident=player.get('role_id')
                if not ident or player is me or ident==role.get('game_role_id') or player.get('team')!=me['team'] or str(ident) in seen:continue
                seen.add(str(ident));key=hashlib.sha256((account+':'+str(ident)).encode()).hexdigest()[:16]
                g=groups.setdefault(key,{'player_ref':key,'name':clean(player.get('user_name')),'shared_matches':0,'official_friend_observed':False,'scores':[]})
                g['shared_matches']+=1;g['official_friend_observed']|=player.get('is_friend')==1
                score=number(player.get('score_avg'))
                if score is not None and mode_of(row) in ('competitive','unrated'):g['scores'].append((mode_of(row),score))
    values=list(groups.values())
    if view=='weapons':
        for value in values:
            if not value['kill_samples']:value['kills']=None
            if not value['damage_samples']:value['damage']=None
        values.sort(key=lambda v:-(v['kills'] or 0))
    else:
        for value in values:
            scores=value.pop('scores');value['acs_samples']=len(scores)
            value['average_acs']=average([s for _,s in scores]) if len({m for m,_ in scores})==1 else None
        values.sort(key=lambda v:-v['shared_matches'])
    return dict(base,detail_matches=covered,items=values[:15],
                note='只复用已有详情，不为统计逐场拉取；缺详情不当0。共同出现不证明组队，命中率不作简单平均；不查询他人完整历史。')


async def query(reader,config,view='overview',mode='competitive',agent='',map_name='',since='',until='',page=1,refresh=False):
    bounded_int(page,1,100,'本地战绩页码')
    if type(refresh)is not bool:raise CapabilityError('refresh必须为布尔值。')
    async with reader.lock:
        credentials=reader.credentials();role=await reader.role(credentials);account=reader.account(credentials,role)
        sync=None
        if refresh:account,_,sync=await reader.sync(credentials,role,30)
        rows=reader.store.rows(account,2000)
        selected,unknown=select(rows,config,mode,agent,map_name,since,until)
        if view=='history':
            start=(page-1)*20
            result={'view':view,'page':page,'page_size':20,'filtered_matches':len(selected),'has_more':len(selected)>start+20,
                    'items':[{'match_ref':clean(r.get('battle_id'),128),'agent':clean(r.get('hero_name')),'map':clean((r.get('used_map') or {}).get('name')),
                              'mode':mode_of(r),'kda':clean(r.get('kda')),'result':clean(r.get('result_title')),'played_at':clean(r.get('time'))} for r in selected[start:start+20]],
                    'instruction':'仅本地缓存战绩，可用match_ref查详情；不代表全生涯或最新比赛。'}
        else:result=report(selected,view,reader.store,account,role,config)
        return dict(result,stored_sample=len(rows),local_scan_limit=2000,unknown_time_excluded=unknown,sync=sync,
                    last_sync=(reader.store.state(account) or [None])[0],filters={'mode':mode,'agent':agent,'map':map_name,'since':since,'until':until})
