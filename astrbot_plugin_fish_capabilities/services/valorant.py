"""Owner-only mainland VALORANT data, requiring an explicit local WeChat login.

Protocol flow and payload structure adapted from GuJi08233/astrbot_plugin_val_shop
(AGPL-3.0); record fields referenced wuche-2453198/astrbot_plugin_valorant_analysis.
No third-party credentials, certificate bypasses, purchases, or endpoint enumeration.
"""
import asyncio
from collections import Counter
import base64
import hashlib
import math
import json
import os
import re
import secrets
import time
import urllib.parse
import urllib.request
import urllib.error
from .http import NoRedirect
from .valorant_cache import MatchCache
from .policy import CapabilityError, bounded_int

HOST = 'app.mval.qq.com'
APP_ID = 'wxcbb49f1f39656c2a'
UA = 'mval/2.6.0.10062 Channel/3 Manufacturer/Redmi Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 Chrome/110.0.0.0 Mobile Safari/537.36'
PATHS = {'/go/auth/get_sdk_ticket','/go/auth/login_by_wechat',
         '/go/account/get_main_role_raw','/go/agame/career/record/list',
         '/go/agame/career/record/scoreboard','/go/agame/career/record/player/roundoverview','/go/agame/career/record/player/rounds',
         '/go/mlol_store/agame/user_store'}


def private_save(path, data):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    tmp=path.with_suffix('.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False)
    tmp.replace(path)


def cookie(credentials):
    fields={k:str(credentials.get(k,'')) for k in ['userId','tid']}
    if not all(fields.values()) or any(re.search(r'[\r\n;]',v) for v in fields.values()):
        raise CapabilityError('战绩登录凭据不完整，请在本机重新绑定。')
    return 'clientType=9; '+'; '.join(k+'='+v for k,v in fields.items())


class MvalHTTP:
    def request(self, url, data=None, auth=None):
        p=urllib.parse.urlsplit(url)
        if p.scheme!='https' or p.port not in (None,443) or p.username or p.password:
            raise CapabilityError('战绩接口地址不合法。')
        allowed=(p.hostname==HOST and p.path in PATHS) or (
            p.hostname=='open.weixin.qq.com' and p.path=='/connect/sdk/qrconnect') or (
            p.hostname=='long.open.weixin.qq.com' and p.path=='/connect/l/qrconnect')
        if not allowed:raise CapabilityError('战绩请求不在已核验的官方接口范围内。')
        headers={'User-Agent':UA,'Accept':'application/json','Content-Type':'application/json'}
        if auth:
            if p.hostname!=HOST:raise CapabilityError('登录凭据不能发送到这个服务。')
            headers['Cookie']=cookie(auth)
        req=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=35 if p.hostname=='long.open.weixin.qq.com' else 15) as response:
                raw=response.read(512001)
            if len(raw)>512000:raise CapabilityError('战绩服务返回内容过大。')
            text=raw.decode('utf-8')
            if p.hostname=='long.open.weixin.qq.com':return parse_poll(text)
            value=json.loads(text)
            if not isinstance(value,dict):raise CapabilityError('战绩服务格式发生变化。')
            return value
        except CapabilityError:raise
        except Exception as e:
            # Long polling can time out normally before anyone scans. Only this
            # read-only endpoint may become 'still waiting'; never replay exchange.
            cause=e.reason if isinstance(e,urllib.error.URLError) else e
            if p.hostname=='long.open.weixin.qq.com' and isinstance(cause,TimeoutError):
                return {'wx_errcode':408,'local_wait_timeout':True}
            raise CapabilityError('官方服务请求未完成；可能是网络或接口变化，没有关闭证书校验或自动重试登录。') from e

    async def post(self,path,data,auth=None):
        return await asyncio.to_thread(self.request,'https://'+HOST+path,data,auth)


def payload():
    return {'clienttype':9,'config_params':{'client_dev_name':'22041216C','lang_type':0},
            'mappid':10200,'mcode':'69028af6dca2c107f4f58290100011b1a303',
            'source_game_zone':'agame','game_zone':'agame'}


def parse_poll(text):
    try:
        result=json.loads(text)
        if isinstance(result,dict):return result
    except ValueError:pass
    status=re.search(r'\bwx_errcode\s*=\s*(\d+)',text)
    code=re.search(r"\bwx_code\s*=\s*['\"]([A-Za-z0-9_-]+)['\"]",text)
    if not status:raise CapabilityError('微信扫码状态格式变化，请检查后再试。')
    return {'wx_errcode':int(status.group(1)),'wx_code':code.group(1) if code else ''}


class WeChatLogin:
    def __init__(self,http=None):self.http=http or MvalHTTP()

    async def generate(self):
        data=await self.http.post('/go/auth/get_sdk_ticket',dict(payload(),sdk_appid=APP_ID))
        ticket=(data.get('data') or {}).get('ticket','')
        if not ticket:raise CapabilityError('掌瓦未返回微信登录票据；不能生成二维码。')
        nonce=secrets.token_hex(6);stamp=str(int(time.time()))
        sig=hashlib.sha1(f'appid={APP_ID}&noncestr={nonce}&sdk_ticket={ticket}&timestamp={stamp}'.encode()).hexdigest()
        qs=urllib.parse.urlencode(dict(appid=APP_ID,noncestr=nonce,timestamp=stamp,scope='snsapi_userinfo',signature=sig))
        value=await asyncio.to_thread(self.http.request,'https://open.weixin.qq.com/connect/sdk/qrconnect?'+qs)
        image=(value.get('qrcode') or {}).get('qrcodebase64','')
        if value.get('errcode')!=0 or not value.get('uuid') or not image:
            raise CapabilityError('微信未返回可用二维码。')
        try:raw=base64.b64decode(image.split(',')[-1],validate=True)
        except Exception as e:raise CapabilityError('二维码编码异常。') from e
        if not (raw.startswith(b'\x89PNG\r\n\x1a\n') or (raw.startswith(b'\xff\xd8\xff') and raw.endswith(b'\xff\xd9'))) or len(raw)>500000:
            raise CapabilityError('二维码图像格式异常。')
        return {'uuid':str(value['uuid']),'image':raw}

    async def poll(self,uuid,last=None):
        if not re.fullmatch(r'[A-Za-z0-9_-]{4,100}',uuid):raise CapabilityError('扫码会话不合法。')
        query={'f':'json','uuid':uuid}
        if type(last) is int and last in (0,404,408):query['last']=last
        return await asyncio.to_thread(self.http.request,'https://long.open.weixin.qq.com/connect/l/qrconnect?'+urllib.parse.urlencode(query))

    async def exchange(self,code):
        if not isinstance(code,str) or not re.fullmatch(r'[A-Za-z0-9_-]{4,200}',code):raise CapabilityError('微信授权码不合法。')
        value=await self.http.post('/go/auth/login_by_wechat',dict(payload(),login_info={
            'appid':APP_ID,'check_third_type':1,'code':code,'wx_info_type':1}))
        info=(value.get('data') or {}).get('login_info') or {}
        if value.get('result') not in (None,0) or info.get('result') not in (None,0) or not info.get('user_id') or not info.get('wt'):
            raise CapabilityError('掌瓦未接受微信授权，尚未绑定。')
        return {'userId':str(info['user_id']),'tid':str(info['wt']),'login_type':'wechat','bound_at':time.time()}


def clean(value,limit=100):
    return re.sub(r'<[^>]*>','',str(value or '')).replace('\x00','')[:limit]


class ValorantRecords:
    def __init__(self,path,http=None):self.path=path;self.http=http or MvalHTTP();self.cache=None;self.profile_cache=None;self.shop_cache=None;self.lock=asyncio.Lock();self.store=MatchCache(path.with_name('valorant-matches.sqlite3'))

    def credentials(self):
        try:data=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):raise CapabilityError('无畏契约尚未绑定。请主人在平板执行 fish-val-login，用微信扫码。')
        if data.get('login_type')!='wechat':raise CapabilityError('绑定方式与主人选择的微信账号不符。')
        cookie(data)
        return data

    async def role(self,credentials):
        result=await self.http.post('/go/account/get_main_role_raw',{'_t':int(time.time())},credentials)
        if result.get('result')!=0:raise CapabilityError('掌瓦登录已失效或角色读取失败，需要主人重新核验绑定。')
        roles=(result.get('data') or {}).get('list') or []
        if len(roles)!=1:raise CapabilityError('未取得唯一游戏角色，不能自行猜选账号；请检查掌瓦角色绑定。')
        role=roles[0]
        if not role.get('game_role_id') or not role.get('scene'):raise CapabilityError('角色缺少战绩授权字段，未确认战绩可用。')
        return role

    async def shop(self):
        async with self.lock:
            credentials=self.credentials()
            fingerprint=hashlib.sha256(cookie(credentials).encode()).hexdigest()
            now=time.time()
            if self.shop_cache and self.shop_cache[0]==fingerprint and now<self.shop_cache[1]:
                return dict(self.shop_cache[2],cached=True)
            await self.role(credentials)
            value=await self.http.post('/go/mlol_store/agame/user_store',{'_t':int(now)},credentials)
            if value.get('result')!=0:raise CapabilityError('每日商店读取失败，可能需要重新登录掌瓦；未购买或重试。')
            data=value.get('data')
            if isinstance(data,list):
                sections=[x for x in data if isinstance(x,dict) and x.get('key')=='dailystore']
                data=sections[0] if len(sections)==1 else None
            if isinstance(data,dict) and data.get('key') not in (None,'dailystore'):data=None
            if not isinstance(data,dict) or not isinstance(data.get('list'),list):raise CapabilityError('商店数据格式变化，未猜测商品。')
            items=[]
            for row in data['list'][:8]:
                if not isinstance(row,dict) or not row.get('goods_name'):continue
                items.append({'name':clean(row['goods_name']),'price_text':clean(row.get('rmb_price'))})
            expires=number(data.get('end_ts'))
            result={'items':items,'fetched_at':now,'expires_at':expires,'cached':False,
                    'instruction':'这是绑定微信角色的官方每日商店，只读，不购买、不兑换。price_text保留接口rmb_price显示值，不换算VP或猜折扣；登录失效时需要重新绑定。只在主人私聊展示，不带入公开评论。'}
            ttl=min(now+300,expires) if expires and expires>now else now+60
            self.shop_cache=(fingerprint,ttl,result)
            return result

    async def read(self,limit=3):
        bounded_int(limit,1,5,'战绩场次')
        async with self.lock:
            credentials=self.credentials()
            fingerprint=hashlib.sha256(cookie(credentials).encode()).hexdigest()
            if self.cache and self.cache[0]==fingerprint and time.time()-self.cache[1]<600:
                return dict(self.cache[2],matches=self.cache[2]['matches'][:limit],cached=True)
            role=await self.role(credentials)
            account,rows,sync=await self.sync(credentials,role,5)
            matches=[]
            for row in rows[:5]:
                matches.append({'result':clean(row.get('result_title')),'agent':clean(row.get('hero_name')),
                                'mode':clean(row.get('game_mode')),'map':clean((row.get('used_map') or {}).get('name') or row.get('content')),
                                'kda':clean(row.get('kda')),'acs':number(row.get('score_avg')),'performance_score':number(row.get('performance_score')),'score_labels':{'acs':'平均战斗评分，score_avg','performance_score':'表现分，performance_score，不是ACS'},
                                'played_at':clean(row.get('time')),'match_ref':clean(row.get('battle_id'),128),'rounds_won':number(row.get('round_won')),'rounds_lost':number(row.get('round_fail')),'timestamp':row.get('ts') if type(row.get('ts')) is int else None})
            result={'game':'国服无畏契约PC','account':clean(role.get('role_name')),'rank':clean(role.get('tier_text')),
                    'matches':matches,'sync':sync,'fetched_at':time.time(),'cached':False,'source':'掌瓦非公开接口，可能延迟或变化',
                    'instruction':'只读主人自己的近期战绩，不是实时对局或完整生涯；空字段不猜。少量对局不足以判断长期能力或人格。结合主人话题自然简短回应，不逐场写长报告，不将私聊战绩发到群。'}
            self.cache=(fingerprint,time.time(),result)
            return dict(result,matches=matches[:limit])


    async def profile(self,sample_size=20,mode='competitive'):
        bounded_int(sample_size,1,30,'统计样本场次')
        if mode not in ('competitive','all','unrated','deathmatch'):raise CapabilityError('统计模式只能是competitive、all、unrated或deathmatch。')
        async with self.lock:
            credentials=self.credentials();fingerprint=hashlib.sha256(cookie(credentials).encode()).hexdigest()
            if self.profile_cache and self.profile_cache[:2]==(fingerprint,(sample_size,mode)) and time.time()-self.profile_cache[2]<600:
                return dict(self.profile_cache[3],cached=True)
            role=await self.role(credentials)
            account,records,sync=await self.sync(credentials,role,sample_size)
            observed=records[:sample_size]
            observed_modes=Counter(mode_of(r) for r in observed)
            by_mode=[]
            for name,count in observed_modes.items():
                group=[r for r in observed if mode_of(r)==name]
                by_mode.append({'mode':name,'matches':count,'share':round(count/len(observed),4),
                    'average_acs':average([number(r.get('score_avg')) for r in group]) if name in ('competitive','unrated') else None,
                    'note':'模式单独统计，乱斗及未知模式分数字段不当作可比较的回合制ACS'})
            records=[r for r in observed if mode=='all' or mode_of(r)==mode]
            acs_comparable=bool(records) and len({mode_of(r) for r in records})==1 and mode_of(records[0]) in ('competitive','unrated')
            agents=Counter();modes=Counter();k=d=a=valid_kda=wins=losses=draws=0
            acs=[];recent=[]
            for row in records:
                agent=clean(row.get('hero_name'));row_mode=clean(row.get('game_mode'))
                if agent:agents[agent]+=1
                if row_mode:modes[row_mode]+=1
                parts=re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*',str(row.get('kda','')))
                if parts:
                    ki,de,ass=map(int,parts.groups());k+=ki;d+=de;a+=ass;valid_kda+=1
                result=clean(row.get('result_title'))
                wins+=result in ('获胜','胜利','win','WIN');losses+=result in ('失败','战败','loss','LOSS');draws+=result in ('平局','draw','DRAW')
                score=str(row.get('score_avg',''))
                if re.fullmatch(r'\d+(?:\.\d+)?',score):acs.append(float(score))
                if len(recent)<3:recent.append({'agent':agent,'kda':clean(row.get('kda')),'result':result,'mode':row_mode,'map':clean((row.get('used_map') or {}).get('name')),'played_at':clean(row.get('time')),'match_ref':clean(row.get('battle_id'),128)})
            output={'game':'国服无畏契约PC','account':clean(role.get('role_name')),'rank':clean(role.get('tier_text')),
                'requested_matches':sample_size,'observed_matches':len(observed),'mode_filter':mode,'observed_modes':dict(observed_modes),'by_mode':by_mode,'sampling_scope':'从最近已捕获样本中按模式筛选，没有额外翻页凑满筛选后场数','sampled_matches':len(records),'kda_valid_matches':valid_kda,
                'kills':k if valid_kda else None,'deaths':d if valid_kda else None,'assists':a if valid_kda else None,
                'kd':round(k/d,3) if valid_kda and d else None,'kd_note':'累计击杀/累计死亡；缺KDA不计入，零死亡时不虚构比值',
                'wins':wins,'losses':losses,'draws':draws,'known_result_matches':wins+losses+draws,
                'win_rate_excluding_draws':round(wins/(wins+losses),4) if wins+losses else None,
                'average_acs':round(sum(acs)/len(acs),1) if acs and acs_comparable else None,'acs_valid_matches':len(acs),
                'acs_definition':'仅同一种回合制模式的官方score_avg取样本算术平均，混合模式或乱斗不提供整体ACS。不是官方赛季全量ACS，表现分另列',
                'average_performance_score':average([number(r.get('performance_score')) for r in records]),'sync':sync,
                'most_used_agents':[{'agent':name,'matches':count} for name,count in agents.most_common(5)],
                'modes':dict(modes),'recent_matches':recent,'fetched_at':time.time(),'cached':False,
                'instruction':'仅已读取的近期对局样本，可能混合模式；不是完整生涯、官方赛季总计或实时对局。常用特工只指这个样本。不能凭胜负评判人格或整体水平；自然简短聊，主人要求再详细。不向群聊或公开信箱复制私人战绩。'}
            self.profile_cache=(fingerprint,(sample_size,mode),time.time(),output)
            return output


    @staticmethod
    def account(credentials,role):
        return hashlib.sha256((str(credentials['userId'])+':'+str(role['game_role_id'])).encode()).hexdigest()

    async def sync(self,credentials,role,needed):
        account=self.account(credentials,role);known=self.store.keys(account);state=self.store.state(account)
        if state and time.time()-state[0]<300 and (len(known)>=needed or state[2]):
            return account,self.store.rows(account,needed),{'list_requests':0,'new_matches':0,'stored_matches':len(known),'used_local_cache':True,'last_sync':state[0]}
        pages=set();baton='';added=set();requests=0;exhausted=False;latest='';reached_known=False
        for page in range(1,4):
            body=dict(payload(),game_role_id=role['game_role_id'],scene=role['scene'],page_no=page,page_size=10,_t=int(time.time()))
            if baton:body['baton']=baton
            value=await self.http.post('/go/agame/career/record/list',body,credentials);requests+=1
            if value.get('result')!=0:raise CapabilityError('战绩列表未读取成功；本地已保存的对局没有删除，也未返回虚构数据。')
            data=value.get('data') or {};rows=data.get('battle_list') or data.get('list') or []
            if not isinstance(rows,list):raise CapabilityError('掌瓦战绩列表结构发生变化。')
            signature=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
            if not rows or signature in pages:exhausted=True;break
            pages.add(signature);rows=rows[:10]
            keys={self.store.key(r,i) for i,r in enumerate(rows) if isinstance(r,dict)}
            if not latest:latest=self.store.key(rows[0])
            overlap=bool(keys&known);reached_known |= overlap;added.update(keys-known);self.store.ingest(account,rows,offset=(page-1)*10)
            total=len(self.store.keys(account))
            if len(rows)<10:exhausted=True;break
            if total>=needed and (reached_known or not known):break
            baton=data.get('next_baton') or ''
            if not isinstance(baton,str) or len(baton)>4000:raise CapabilityError('掌瓦分页状态异常。')
        self.store.synced(account,latest,exhausted)
        return account,self.store.rows(account,needed),{'list_requests':requests,'new_matches':len(added),'stored_matches':len(self.store.keys(account)),'used_local_cache':False,'last_sync':time.time(),'note':'每次刷新仍需查最新列表才能发现新对局，已保存对局和详情按比赛ID复用；不是全生涯已同步'}

    async def match(self,recent_index=1,view='summary',match_ref='',top_players=2):
        bounded_int(recent_index,1,30,'近期对局序号')
        bounded_int(top_players,0,5,'每方展示人数')
        if view not in ('summary','full','rounds','weapons'):raise CapabilityError('详情视图只能是summary、full、rounds或weapons。')
        if match_ref and (not isinstance(match_ref,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',match_ref)):raise CapabilityError('比赛引用格式不合法。')
        async with self.lock:
            credentials=self.credentials();role=await self.role(credentials)
            if match_ref:
                account=self.account(credentials,role);row=self.store.get_row(account,match_ref)
                if row is None:raise CapabilityError('本账号缓存中不存在这场比赛，不能拿他人比赛编号查询。')
                sync={'used_local_cache':True,'list_requests':0,'selected_by':'match_ref'}
            else:
                account,rows,sync=await self.sync(credentials,role,max(20,recent_index))
                if recent_index>len(rows):raise CapabilityError('本地及接口中没有该序号的近期比赛。')
                row=rows[recent_index-1]
            battle=row.get('battle_id');match_id=row.get('match_id')
            if not battle or not match_id:raise CapabilityError('该场缺少详情编号，不能猜测请求。')
            parts={};status={};requests=0
            for name,path in [('scoreboard','/go/agame/career/record/scoreboard'),('roundoverview','/go/agame/career/record/player/roundoverview'),('rounds','/go/agame/career/record/player/rounds')]:
                data=self.store.detail(account,battle,name)
                if data is not None:parts[name]=data;status[name]='cached';continue
                try:
                    body={'battle_id':battle,'match_id':match_id,'scene':role['scene'],'game_role_id':role['game_role_id'],'_t':int(time.time())}
                    requests+=1
                    response=await self.http.post(path+'?source_game_zone=agame&game_zone=agame',body,credentials)
                    if response.get('result')!=0 or not isinstance(response.get('data'),dict):
                        status[name]='unavailable';continue
                    data=response['data']
                    if not data or (name=='scoreboard' and not data.get('scoreboard')) or (name=='rounds' and not data.get('rounds')) or (name=='roundoverview' and not (data.get('weapons') or data.get('opponents'))):
                        status[name]='unavailable';continue
                    self.store.save_detail(account,battle,name,data);parts[name]=data;status[name]='fetched'
                except CapabilityError:status[name]='unavailable'
            return detail_view(detail_packet(row,parts,role,status,requests,sync),view,top_players)


def number(value):
    if isinstance(value,bool):return None
    if isinstance(value,(int,float)) and math.isfinite(value) and value>=0:return value
    if isinstance(value,str) and re.fullmatch(r'\d+(?:\.\d+)?',value.strip()):return float(value)
    return None


def average(values):
    values=[v for v in values if v is not None]
    return round(sum(values)/len(values),1) if values else None


def player_packet(p):
    return {'name':clean(p.get('user_name')),'agent':clean((p.get('used_agent') or {}).get('name')),
        'team':clean(p.get('team')),'is_me':p.get('is_me')==1,'rank':clean(p.get('tier_name')),
        **{k:number(p.get(k)) for k in ['kill','death','assist','score_avg','performance_score','first_kill_count','plant_count','defuse_count','total_head_shots','total_body_shots','total_leg_shots','clutch','ace','economy']},
        'kda':clean(p.get('kda')),'head_shots_rate':clean(p.get('head_shots_rate')),
        'damage':number(p.get('damage')),'is_friend':p.get('is_friend')==1}


def detail_packet(row,parts,role,status,requests,sync):
    board=parts.get('scoreboard',{});raw_players=board.get('scoreboard') or []
    me=next((p for p in raw_players if p.get('is_me')==1 or p.get('role_id')==role.get('game_role_id')),None)
    own_team=me.get('team') if me else None
    players=[]
    for p in raw_players[:10]:
        output=player_packet(p)
        output['side']='self' if p is me else ('teammate' if own_team and p.get('team')==own_team else ('opponent' if own_team and p.get('team') else 'unknown'))
        players.append(output)
    round_data=parts.get('rounds',{});rounds=[r for r in (round_data.get('rounds') or []) if type(r.get('round_num')) is int and r['round_num']>=0]
    expected=(number(row.get('round_won')) or 0)+(number(row.get('round_fail')) or 0)
    complete=bool(rounds) and expected==len({r['round_num'] for r in rounds}) and all(number(r.get('kills')) is not None for r in rounds)
    multi={str(n):sum(r.get('kills')==n for r in rounds) for n in [3,4,5]} if complete else None
    overview=parts.get('roundoverview',{})
    weapons=[{'name':clean((w.get('used_gun') or {}).get('name')),'kills':number(w.get('kills')),'damage':number(w.get('damage')),'head_shot_rate':clean(w.get('head_shot_rate'))} for w in (overview.get('weapons') or [])[:15]]
    pairs=[{'agent':clean((p.get('used_agent') or {}).get('name')),'rank':clean(p.get('tier_name')),**{k:number(p.get(k)) for k in ['kills','deaths','assists','damage','damaged']}} for p in (overview.get('opponents') or [])[:5]]
    acs=number(me.get('score_avg')) if me else None
    acs_source='scoreboard.score_avg'
    if acs is None:acs=number((round_data.get('match') or {}).get('score_avg'));acs_source='rounds.match.score_avg'
    if acs is None:acs=number(row.get('score_avg'));acs_source='list.score_avg'
    return {'game':'国服无畏契约PC','match_ref':clean(row.get('battle_id'),128),'played_at':clean(row.get('time')),'map':clean((row.get('used_map') or {}).get('name')),'mode':clean(row.get('game_mode')),'result':clean(row.get('result_title')),
        'rounds_won':number(row.get('round_won')),'rounds_lost':number(row.get('round_fail')),
        'official_acs':acs,'acs_source':acs_source,'performance_score':number(me.get('performance_score')) if me else number(row.get('performance_score')),
        'score_explanation':'ACS=官方score_avg，平均战斗评分；performance_score=表现分，两者分别报告。不要用总战斗分或表现分代替ACS。',
        'self':player_packet(me) if me else None,'players':players,'weapons':weapons,'head_to_head':pairs,
        'multi_kill_rounds':multi,'multi_kill_data_complete':complete,'expected_round_count':expected,'multi_kill_definition':'只数单回合恰好3、4、5杀的回合；不包含round_num=-1的全局汇总；5杀不重复计为四杀或三杀。缺逐回合数据返回null，不当成0。',
        'round_count':len(rounds),'rounds':[{'round_num':r.get('round_num'),**{k:number(r.get(k)) for k in ['kills','deaths','assists','damage']},'is_attack':r.get('is_attack'),'is_win':r.get('is_win')} for r in rounds[:60]],
        'parts_status':status,'detail_requests':requests,'sync':sync,
        'instruction':'仅主人这场比赛可见的数据；双方是本局表现，不是他人完整历史战绩。未知字段不补0，区别爆头命中率与爆头击杀率。按问题挑重点自然简短说，不一次把十人整张表和所有回合倾倒给主人。不要发到群、B站或给Codex的留言里。'}


def mode_of(row):
    value=row.get('game_enum')
    if value in ('competitive','unrated','deathmatch'):return value
    return {'竞技模式':'competitive','普通模式':'unrated','非竞技模式':'unrated','乱斗模式':'deathmatch'}.get(row.get('game_mode'),'unknown')


def detail_view(packet,view,top_players):
    output=dict(packet,view=view,available_views=['summary','full','rounds','weapons'])
    output['total_players']=len(packet['players'])
    if view=='full':return output
    if view=='summary':
        others=[]
        for side in ('teammate','opponent'):
            group=[p for p in packet['players'] if p['side']==side]
            others.extend(sorted(group,key=lambda p:(p.get('score_avg') is not None,p.get('score_avg') or 0),reverse=True)[:top_players])
        selected=[p for p in packet['players'] if p['side']=='self']+others
        output['players']=[{k:p[k] for k in ['name','agent','side','rank','kda','score_avg','performance_score']} for p in selected]
        output['player_selection']='主人及双方按本局ACS排序的前'+str(top_players)+'名其他玩家，不据此判定整场责任'
        output.pop('rounds',None);output['weapons']=packet['weapons'][:5]
    elif view=='rounds':
        for key in ('players','weapons','head_to_head'):output.pop(key,None)
    elif view=='weapons':
        for key in ('players','rounds','head_to_head'):output.pop(key,None)
    return output
