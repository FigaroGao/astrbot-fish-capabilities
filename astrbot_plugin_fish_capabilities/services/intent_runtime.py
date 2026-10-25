"""One decision boundary around GCP's existing async reply generator.

The lock spans its yields: AstrBot's onion pipeline completes generation,
tools, decoration and segmented delivery before resuming this generator.
No second incoming-message listener and no independent QQ sender.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from .intent import JUDGE_PROMPT
from .group_tasks import skip_group_task, task_reason
from .meme_request import explicit_meme_request


def capability(gcp):
    star = gcp.context.get_registered_star('astrbot_plugin_fish_capabilities')
    return getattr(star, 'star_cls', None)


def observe_group(gcp, event):
    cap = capability(gcp)
    if cap and cap.intent.enabled(event):
        cap.intent.observe(event)


async def route_group(gcp, event):
    cap = capability(gcp)
    if cap and cap.intent.enabled(event):
        async for result in cap.intent.run(gcp, event):
            yield result
    else:
        async for result in gcp._process_message(event):
            yield result


class IntentRuntime:
    def __init__(self, cap, *, clock=time.time, sleep=asyncio.sleep):
        self.cap=cap; self.clock=clock; self.sleep=sleep
        self.records=defaultdict(lambda:deque(maxlen=20))
        self.revisions=defaultdict(int); self.last_input={}; self.latest_direct={}
        self.locks=defaultdict(asyncio.Lock); self.last_judge={}; self.closed=False
        self.active_tasks=set(); self.last_decisions={}
        # Context survives plugin hot reload. Keep the same synchronization
        # boundary while an older instance finishes its last segmented answer.
        if getattr(cap,'context',None) is not None:
            shared=getattr(cap.context,'_fish_intent_shared',None)
            fields=('records','revisions','last_input','latest_direct','locks','last_judge','active_tasks','last_decisions')
            if shared is None:
                setattr(cap.context,'_fish_intent_shared',{name:getattr(self,name) for name in fields})
            else:
                for name in fields:setattr(self,name,shared[name])
        with cap.ledger.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS intent_turns(scope TEXT,stamp REAL,spontaneous INTEGER)')
            db.execute('CREATE INDEX IF NOT EXISTS intent_turn_scope ON intent_turns(scope,stamp)')

    def enabled(self,event):
        return (not self.closed and self.cap.config.get('enabled',False)
                and self.cap.config.get('intent_enabled',False) and not event.is_private_chat()
                and event.unified_msg_origin in self.cap.config.get('allowed_group_sessions',[]))

    @staticmethod
    def targets(event):
        bot=str(event.get_self_id()); directed=False; other=False; targets=[]
        for part in event.get_messages():
            kind=part.__class__.__name__
            if kind=='At':target=str(getattr(part,'qq',''))
            elif kind=='Reply':target=str(getattr(part,'sender_id','') or '')
            else:continue
            targets.append({'kind':kind,'id':target or 'unknown'})
            directed |= target==bot
            other |= target not in ('','0','all',bot)
        # AtAll never counts as inviting this bot individually.
        return directed,other,targets

    def direct(self,event):
        directed,other,_=self.targets(event)
        return directed or (not other and bool(getattr(event,'is_at_or_wake_command',False))) or explicit_meme_request(event)

    def observe(self,event):
        if event.get_extra('fish_intent_observed'):return
        scope=event.unified_msg_origin
        self.revisions[scope]+=1; self.last_input[scope]=self.clock()
        event.set_extra('fish_intent_observed',self.revisions[scope])
        _,_,targets=self.targets(event)
        self.records[scope].append({'role':'user','sender_id':str(event.get_sender_id()),
            'text':event.get_message_str()[:600], 'targets':targets,
            'has_image':any(p.__class__.__name__=='Image' for p in event.get_messages())})
        if self.direct(event):self.latest_direct[scope]=self.revisions[scope]

    def eligible(self,scope,now):
        day=datetime.fromtimestamp(now,timezone(timedelta(hours=8))).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
        with self.cap.ledger.connect() as db:
            last=db.execute('SELECT MAX(stamp) FROM intent_turns WHERE scope=?',(scope,)).fetchone()[0]
            hourly,daily=db.execute('SELECT COALESCE(SUM(stamp>?),0),COALESCE(SUM(stamp>=?),0) FROM intent_turns WHERE scope=? AND spontaneous=1', (now-3600,day,scope)).fetchone()
        return ((last is None or now-last>=int(self.cap.config.get('intent_cooldown_seconds',180)))
                and hourly<int(self.cap.config.get('intent_hourly_limit',6))
                and daily<int(self.cap.config.get('intent_daily_limit',20)))

    def diagnostic(self,scope,decision):
        # No chat contents or model reasoning in diagnostics.
        self.last_decisions[scope]={'at':self.clock(),'decision':decision}

    async def judge(self,scope,rows):
        response=await asyncio.wait_for(self.cap.context.llm_generate(
            chat_provider_id=str(self.cap.config.get('intent_provider_id','deepseek/deepseek-flash')),
            prompt=json.dumps({'bot_id':self.bot_id,'recent_group_messages':rows},ensure_ascii=False),
            contexts=[],system_prompt=JUDGE_PROMPT+('\n本群不接算术、做题、证明、调试或复杂专业求解任务，遇到此类请求should_reply=false；游戏、生活和认真交流不因话题有深度而自动拒绝。' if self.cap.config.get('group_skip_complex_tasks',False) else ''),max_tokens=350,
            thinking={'type':'disabled'}),
            timeout=float(self.cap.config.get('intent_timeout_seconds',12)))
        text=response.completion_text.strip()
        if text.startswith('```'):
            text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
        parsed=json.loads(text)
        return (isinstance(parsed,dict) and parsed.get('should_reply') is True
                and type(parsed.get('addressed_to_bot')) is bool
                and isinstance(parsed.get('reason'),str) and 0<len(parsed['reason'])<=160)

    async def run(self,gcp,event):
        self.observe(event)
        quiet=getattr(self.cap,'group_quiet',None)
        if quiet and quiet.suppress(event):
            event.call_llm=True
            self.diagnostic(event.unified_msg_origin,'owner_quiet');return
        reason=skip_group_task(self.cap.config,event)
        if reason:
            event.call_llm=True
            self.diagnostic(event.unified_msg_origin,'skip_task_'+reason)
            return
        scope=event.unified_msg_origin; direct=self.direct(event)
        lock=self.locks[scope]; revision=event.get_extra('fish_intent_observed')
        # Suppress the default fallback too; capture/other plugin hooks may continue.
        event.call_llm=True
        if lock.locked() and not direct:
            self.diagnostic(scope,'merged_while_busy'); return
        # Only the latest directly addressed event survives a backlog. Earlier
        # messages remain in the bounded group snapshot; they are not answered one by one.
        task=asyncio.current_task();self.active_tasks.add(task)
        started=False
        try:
            async with lock:
                if self.closed:return
                if quiet and quiet.suppress(event):return
                if direct and self.latest_direct.get(scope)!=revision:
                    self.diagnostic(scope,'merged_direct');return
                if not direct:
                    if not self.eligible(scope,self.clock()):
                        self.diagnostic(scope,'cooldown_or_budget');return
                    begin=self.clock(); quiet=float(self.cap.config.get('intent_quiet_seconds',20))
                    while self.clock()-self.last_input[scope]<quiet:
                        if self.closed or self.clock()-begin>=60 or self.latest_direct.get(scope,0)>revision:
                            self.diagnostic(scope,'quiet_wait_cancelled');return
                        await self.sleep(min(1,quiet))
                    revision=self.revisions[scope]; rows=list(self.records[scope])
                    if self.closed:return
                    # Last input is a conversation between other people, or a
                    # sticker-only stream: don't spend a judgment request on it.
                    last=rows[-1]
                    if self.cap.config.get('group_skip_complex_tasks',False) and task_reason(last.get('text','')):
                        self.diagnostic(scope,'skip_task_latest');return
                    bot=str(event.get_self_id());self.bot_id=bot
                    ts=last.get('targets',[])
                    if any(t['id'] not in ('unknown','0','all',bot) for t in ts) and not any(t['id']==bot for t in ts):
                        self.diagnostic(scope,'addressed_to_others');return
                    if not any(r['role']=='user' and r['text'].strip() and r['text'].strip() not in ('[图片]','[表情]') for r in rows[-3:]):
                        self.diagnostic(scope,'no_text');return
                    if self.clock()-self.last_judge.get(scope,0)<30:
                        self.diagnostic(scope,'judge_interval');return
                    self.last_judge[scope]=self.clock()
                    try:
                        verdict=await self.judge(scope,rows)
                    except asyncio.CancelledError:raise
                    except Exception:
                        self.diagnostic(scope,'judge_error_silent');return
                    if not verdict or revision!=self.revisions[scope] or not self.eligible(scope,self.clock()):
                        self.diagnostic(scope,'no_or_stale');return
                else:
                    rows=list(self.records[scope])
                event.set_extra('fish_intent_approved',True)
                event.set_extra('fish_intent_group_snapshot',rows)
                self.diagnostic(scope,'direct' if direct else 'intent_yes')
                async for result in gcp._process_message(event):
                    if quiet and quiet.suppress(event):return
                    started=True
                    yield result
        finally:
            if started:
                # A yielded LLM request may already have produced QQ messages;
                # reserve this turn even if network/delivery status is uncertain.
                with self.cap.ledger.connect() as db:
                    db.execute('INSERT INTO intent_turns VALUES(?,?,?)',(scope,self.clock(),int(not direct)))
                    db.execute('DELETE FROM intent_turns WHERE stamp<?',(self.clock()-86400*35,))
            self.active_tasks.discard(task)

    async def close(self):
        self.closed=True
        # Don't cancel an already generating/sending answer. Hot reload is only
        # installed when no target turn is active; callers can inspect this set.

