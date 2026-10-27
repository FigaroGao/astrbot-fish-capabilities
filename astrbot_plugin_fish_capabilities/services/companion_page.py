"""Native AstrBot authenticated plugin view; no standalone HTTP listener."""
import asyncio
import base64
import json
import re
from .capability_registry import catalog
from .observability import replay
from .policy import CapabilityError


def current_request():
    try:
        from astrbot.api.web import request
    except ImportError:
        from quart import request
    return request


def query_values(request):
    query=getattr(request,'query',None)
    return query if query is not None else request.args


class CompanionPage:
    PREFIX='/astrbot_plugin_fish_capabilities/page'
    def __init__(self,cap,runtime):
        self.cap,self.runtime=cap,runtime;self.index_task=None;self.index_result=None

    def register(self):
        for path,handler,methods in [('state',self.state,['GET']),('action',self.action,['POST']),('image',self.image,['GET'])]:
            self.cap.context.register_web_api(self.PREFIX+'/'+path,handler,methods,'小鲸管理台（沿用AstrBot管理员鉴权）')

    def close(self):
        if self.index_task and not self.index_task.done():self.index_task.cancel()
        routes=getattr(self.cap.context,'registered_web_apis',None)
        if isinstance(routes,list):routes[:]=[r for r in routes if not str(r[0]).startswith(self.PREFIX+'/')]

    def scopes(self):
        private=str(self.cap.config.get('bili_private_session',''))
        return ([private] if private else [])+list(self.cap.config.get('allowed_group_sessions',[]))

    def scope(self,value=''):
        value=value or str(self.cap.config.get('bili_private_session',''))
        if value not in self.scopes():raise CapabilityError('管理范围未获授权。')
        return value

    async def state(self):
        try:
            request=current_request()
            scope=self.scope(query_values(request).get('scope',''))
            return {'status':'ok','data':{'scope':scope,'scopes':self.scopes(),
                'notes':self.runtime.learning.list(scope,limit=100),'feedback':self.runtime.learning.feedback_hints(scope),
                'recall_traces':self.runtime.learning.traces(scope),'videos':self.runtime.shelf(),
                'timeline':self.cap.timeline.search('',20),'usage':self.runtime.usage(),
                'tasks':self.cap.timetable.list() if self.cap.timetable else {'tasks':[]},
                'permissions':catalog(self.cap.config),'memes':self.cap.memes.manageable(),
                'semantic':self.runtime.semantic.status(),'indexing':bool(self.index_task and not self.index_task.done()),
                'initiative':self.runtime.initiative_state() if scope==str(self.cap.config.get('bili_private_session','')) else None,
                'tone':self.runtime.tone.recent(scope),
                'index_result':self.index_result,'intent_decisions':self.cap.intent.last_decisions}}
        except CapabilityError as exc:return {'status':'error','message':str(exc)}

    async def image(self):
        try:
            request=current_request()
            ident=query_values(request).get('id','')
            data,suffix=await asyncio.to_thread(self.cap.memes.review_preview,ident)
            mime={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.gif':'image/gif','.webp':'image/webp'}[suffix]
            return {'status':'ok','data':{'url':'data:'+mime+';base64,'+base64.b64encode(data).decode()}}
        except CapabilityError as exc:return {'status':'error','message':str(exc)}

    async def index(self):
        try:self.index_result=await self.runtime.semantic.index(30)
        except asyncio.CancelledError:raise
        except Exception:self.index_result={'state':'failed','reason':'索引未完成，已有索引仍可用。'}

    async def action(self):
        try:
            request=current_request()
            json_method=getattr(request,'json',None)
            payload=await json_method(default=None) if callable(json_method) else await request.get_json(silent=True)
            if not isinstance(payload,dict) or len(json.dumps(payload,ensure_ascii=False))>20000:
                raise CapabilityError('操作输入无效或过长。')
            return {'status':'ok','data':await self.perform(payload)}
        except CapabilityError as exc:return {'status':'error','message':str(exc)}
        except (ValueError,TypeError,OverflowError):return {'status':'error','message':'参数类型无效，操作未完成。'}

    async def perform(self,data):
        if not self.cap.config.get('enabled',False):raise CapabilityError('功能总开关已关闭。')
        operation=data.get('operation');scope=self.scope(data.get('scope',''))
        def integer(key,default=0):
            value=data.get(key,default)
            if type(value)is not int or value<0:raise CapabilityError('记录ID和版本必须是非负整数。')
            return value
        if operation=='note_save':
            return self.runtime.learning.save(scope,data.get('kind'),data.get('topic',''),data.get('text',''),
                {'kind':'owner_review','reviewed_in_dashboard':True},approved=True,note_id=integer('id'),revision=integer('revision'))
        if operation=='tone_diagnose':
            if not self.cap.config.get('tone_diagnostics_enabled',False):raise CapabilityError('表达诊断尚未开启。')
            from .tone_diagnostics import analyze
            return analyze(data.get('text',''),data.get('context',''),data.get('scene','auto'))
        if operation=='note_review':
            return self.runtime.learning.review(scope,integer('id'),data.get('state'),integer('revision'))
        if operation=='meme_save':
            result=self.cap.memes.edit(str(data.get('id','')),str(data.get('version','')),
                description=data.get('description',''),image_text=data.get('image_text',''),usage_notes=data.get('usage_notes',''),
                tags=data.get('tags',[]),category=data.get('category'),approved=data.get('approved'))
            self.runtime.semantic.cache.clear();return result
        if operation=='meme_index':
            if not self.index_task or self.index_task.done():self.index_task=asyncio.create_task(self.index())
            return {'state':'indexing','instruction':'后台每批最多30张，可刷新查看进度；不调用视觉模型。'}
        if operation=='meme_search':return await self.runtime.semantic.search(data.get('query',''))
        if operation=='simulate':
            return await replay(self.cap.intent,data.get('scenario',{}),use_model=data.get('use_model') is True)
        if operation=='task_pause':
            if self.cap.timetable is None:raise CapabilityError('时间表未启用。')
            if type(data.get('enabled'))is not bool:raise CapabilityError('启用状态必须为布尔值。')
            return self.cap.timetable.control(str(data.get('id','')),'resume' if data.get('enabled') is True else 'pause')
        if operation=='covers':return await self.runtime.refresh_covers()
        raise CapabilityError('没有注册这种管理操作。')
