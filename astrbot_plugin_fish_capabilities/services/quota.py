from __future__ import annotations
import asyncio
import json
import time
import sqlite3
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
import urllib.parse
import urllib.request
from pathlib import Path
from .http import NoRedirect
from .policy import CapabilityError


class Quota:
    def __init__(self, config_path: Path, transport=None, *, state_path=None, stats_path=None, clock=time.time):
        self.path=config_path;self.transport=transport or self.fetch
        self.cached=None;self.lock=asyncio.Lock()
        self.state_path=state_path;self.stats_path=stats_path;self.clock=clock

    def usage(self, now):
        tz=timezone(timedelta(hours=8))
        day=datetime.fromtimestamp(now,tz).replace(hour=0,minute=0,second=0,microsecond=0)
        result={'date':day.date().isoformat(),'timezone':'Asia/Hong_Kong',
                'scope':'本 AstrBot 已记录的 DeepSeek 请求汇总；可能不含插件直接调用，不包含聊天内容',
                'status':'unavailable'}
        if not self.stats_path or not self.stats_path.exists():return result
        try:
            with sqlite3.connect(self.stats_path.as_uri()+'?mode=ro',uri=True) as db:
                row=db.execute('SELECT COUNT(*),COALESCE(SUM(token_input_other),0),COALESCE(SUM(token_input_cached),0),COALESCE(SUM(token_output),0) FROM provider_stats WHERE provider_id LIKE ? AND start_time>=? AND start_time<?',
                    ('deepseek/%',day.timestamp(),min(now,day.timestamp()+86400))).fetchone()
            result.update(status='recorded',requests=row[0],input_uncached=row[1],input_cached=row[2],output=row[3],total_tokens=sum(row[1:]))
        except sqlite3.Error:pass
        return result

    def track(self, rows, now):
        day=datetime.fromtimestamp(now,timezone(timedelta(hours=8))).date().isoformat()
        if not self.state_path:return {'status':'not_recording'}
        try:
            amounts={r['currency']:str(Decimal(r['total_balance'])) for r in rows}
            if not all(Decimal(v).is_finite() and Decimal(v)>=0 for v in amounts.values()):raise ValueError()
            state=json.loads(self.state_path.read_text()) if self.state_path.exists() else {'days':{}}
            days=state['days'];record=days.setdefault(day,{'first_at':now,'opening':amounts,'last':amounts,'increased':False})
            if amounts.keys()!=record['opening'].keys():record['increased']=True
            for currency,amount in amounts.items():
                if currency in record['last'] and Decimal(amount)>Decimal(record['last'][currency]):record['increased']=True
            record.update(last=amounts,last_at=now)
            state['days']={k:v for k,v in days.items() if k>= (datetime.fromtimestamp(now,timezone.utc)-timedelta(days=35)).date().isoformat()}
            self.state_path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.state_path.with_suffix('.tmp');temporary.write_text(json.dumps(state));temporary.chmod(0o600);temporary.replace(self.state_path)
            return {'status':'balance_increased_unreliable' if record['increased'] else 'partial_day_net_change',
                    'date':day,'timezone':'Asia/Hong_Kong','from':record['first_at'],'to':now,
                    'net_balance_decrease':[{'currency':c,'amount':str(Decimal(v)-Decimal(amounts.get(c,v)))} for c,v in record['opening'].items()],
                    'instruction':'仅今日首个采样至当前的账户余额净减少，不是官方今日账单，也不能归因给本机器人。今日首次采样前未知；采样间充值、赠额到期或其他程序消费会影响结果；不同币种不相加。检测到余额增加时不要把净减少当花费。'}
        except (ValueError,KeyError,TypeError,InvalidOperation,OSError):
            return {'status':'unavailable','instruction':'花费记录不可用，不猜测金额。'}

    @staticmethod
    async def fetch(key):
        def request():
            try:
                req=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+key})
                with urllib.request.build_opener(NoRedirect()).open(req,timeout=12) as response:
                    data=response.read(65537)
                if len(data)>65536:raise ValueError('response too large')
                return json.loads(data)
            except Exception:
                raise CapabilityError('DeepSeek 余额暂时查不到；未输出凭据或估算余额。') from None
        return await asyncio.to_thread(request)

    async def get(self):
        async with self.lock:
            now=self.clock()
            if self.cached and now-self.cached['queried_at']<60:
                return dict(self.cached,cached=True)
            config=json.loads(self.path.read_text(encoding='utf-8-sig'))
            sources=[s for s in config.get('provider_sources',[]) if s.get('id')=='deepseek' and s.get('enable',True)]
            if len(sources)!=1:raise CapabilityError('未找到唯一的 DeepSeek 服务配置。')
            source=sources[0]
            if urllib.parse.urlsplit(source.get('api_base','')).hostname!='api.deepseek.com':
                raise CapabilityError('当前不是 DeepSeek 官方服务，未向其他地址提交余额凭据。')
            keys=source.get('key',[])
            if isinstance(keys,str):keys=[keys]
            if len(keys)!=1 or not keys[0]:raise CapabilityError('余额查询需要明确使用哪一个已配置的 Key。')
            response=await self.transport(keys[0])
            rows=response.get('balance_infos')
            if not isinstance(rows,list) or not rows:raise CapabilityError('余额接口没有返回有效余额。')
            self.cached={'provider':'DeepSeek 官方余额','queried_at':now,
                'is_available':response.get('is_available'),
                'balances':[{k:row.get(k) for k in ('currency','total_balance','granted_balance','topped_up_balance')} for row in rows],
                'today_usage':self.usage(now),'today_balance_change':self.track(rows,now),
                'instruction':'仅查询 DeepSeek；这是账户资金余额，不是 token 数，不保证还能发多少条；不同币种不合并。不要编造官方今日花费。'}
            return self.cached
