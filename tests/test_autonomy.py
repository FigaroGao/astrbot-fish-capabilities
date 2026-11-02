import asyncio,json,sqlite3
from datetime import datetime,timezone,timedelta
from unittest.mock import AsyncMock
from types import SimpleNamespace
import pytest
from astrbot_plugin_fish_capabilities.services.autonomy import Autonomy
from astrbot_plugin_fish_capabilities.services.owner_notebook import OwnerNotebook
from astrbot_plugin_fish_capabilities.services.meme_wiki import MemeWiki
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_astrbot_binding import plugin,Event

def stamp(hour=12):return datetime(2026,11,2,hour,tzinfo=timezone(timedelta(hours=8))).timestamp()
def make(tmp_path,choices,execute=None,clock=None):
 return Autonomy(tmp_path/'a.db',{'autonomy_enabled':True,'initiative_start_hour':11,'initiative_end_hour':4},
  AsyncMock(side_effect=[json.dumps(c) for c in choices]),AsyncMock(return_value={}),execute or AsyncMock(return_value={'state':'ok'}),clock or (lambda:stamp()))

async def test_completion_relative_cooldown_survives_new_instance(tmp_path):
 now=[stamp()]
 async def execute(*a):now[0]+=120;return {'state':'done'}
 a=make(tmp_path,[{'action':'review_notes'}],execute,lambda:now[0])
 assert (await a.tick())['state']=='completed'
 assert a.status()['next_decision_at']==now[0]+600
 now[0]+=599
 b=make(tmp_path,[{'action':'quiet'}],clock=lambda:now[0])
 assert (await b.tick())['state']=='cooldown' and not b.generate.called
 now[0]+=1
 assert (await b.tick())['state']=='completed'

@pytest.mark.parametrize('hour,awake',[(3,True),(4,False),(10,False),(11,True),(23,True)])
async def test_sleep_boundary_does_not_judge(tmp_path,hour,awake):
 a=make(tmp_path,[{'action':'quiet'}],clock=lambda:stamp(hour))
 assert a.awake()==awake
 assert (await a.tick())['state']==('completed' if awake else 'sleeping')
 assert a.generate.called==awake

async def test_chain_max_three_and_no_repeat(tmp_path):
 a=make(tmp_path,[{'action':x,'continue':True} for x in ['shelf','review_notes','meme','learn']])
 assert len((await a.tick())['steps'])==3 and a.execute.await_count==3

async def test_weather_daily_budget_and_failed_attempt_not_replayed(tmp_path):
 now=[stamp()];a=make(tmp_path,[{'action':'weather'},{'action':'weather'}],clock=lambda:now[0])
 await a.tick();now[0]+=601;r=await a.tick()
 assert r['steps'][0]['result']['state']=='daily_limit' and a.execute.await_count==1

async def test_failed_weather_attempt_is_reserved_and_not_looped(tmp_path):
 now=[stamp()];a=make(tmp_path,[{'action':'weather'},{'action':'weather'}],AsyncMock(side_effect=TimeoutError()),lambda:now[0])
 assert (await a.tick())['state']=='failed_TimeoutError'
 now[0]+=601
 assert (await a.tick())['steps'][0]['result']['state']=='daily_limit'
 assert a.execute.await_count==1

async def test_public_search_rejects_private_query_without_network():
 from astrbot_plugin_fish_capabilities.services.public_search import search
 review=AsyncMock()
 with pytest.raises(CapabilityError):await search({},'主人的住址和手机号',review)
 assert not review.called
 review.return_value='{"public_topic":false}'
 with pytest.raises(CapabilityError):await search({},'关于某个人的经历',review)
 assert review.await_count==1

async def test_no_overlapping_ticks_and_cancel_has_cooldown(tmp_path):
 entered=asyncio.Event()
 async def execute(*a):entered.set();await asyncio.Event().wait()
 a=make(tmp_path,[{'action':'learn'}],execute)
 task=asyncio.create_task(a.tick());await entered.wait()
 b=make(tmp_path,[])
 assert (await b.tick())['state']=='running'
 task.cancel()
 with pytest.raises(asyncio.CancelledError):await task
 assert (await b.tick())['state']=='cooldown'

def test_notebook_sources_revision_subjective_and_archive(tmp_path):
 n=OwnerNotebook(tmp_path/'n.db');source='我最近喜欢去菜市场看看'
 r=n.save('impression','菜市场','我觉得他对日常生活有好奇心','喜欢去菜市场',source)
 assert r['subjective'] and n.search()['notes'][0]['source']=='subjective_inference'
 with pytest.raises(CapabilityError):n.save('correction','x','y','不存在的原话',source)
 r2=n.save('impression','菜市场','只是这次想去，不能推成长期爱好','喜欢去菜市场',source,r['id'])
 assert n.search()['notes'][0]['previous']==r['id']
 n.archive(r2['id']);assert not n.search()['notes']
 with sqlite3.connect(n.path) as d:assert d.execute('select count(*) from notes').fetchone()[0]==2

def test_meme_wiki_readonly_precise_no_casual_injection(tmp_path):
 path=tmp_path/'memes.db'
 with sqlite3.connect(path) as d:
  d.execute('create table memes(title,summary,usage,origin)');d.execute('insert into memes values(?,?,?,?)',('去码头整点薯条','fixture','fixture','fixture'))
 w=MemeWiki(path)
 assert w.prelookup('好的') is None
 assert w.prelookup('今天去码头看看') is None
 assert w.prelookup('去码头是什么梗')['entries'][0]['title']=='去码头整点薯条'
 assert not w.search('不存在')['entries']

async def test_notebook_tool_private_owner_boundary(plugin):
 plugin.config['owner_notes_enabled']=True
 assert json.loads(await plugin.owner_notebook_tool(Event(private=False)))['ok'] is False
 assert json.loads(await plugin.owner_notebook_tool(Event(sender='999')))['ok'] is False
 assert 'notes' in json.loads(await plugin.owner_notebook_tool(Event()))

async def test_match_discovery_baseline_then_new_batch_no_direct_sends(plugin):
 plugin.config['valorant_enabled']=True
 a=make(plugin.root,[]);plugin.autonomy=a
 plugin.private_ping=SimpleNamespace(offer=AsyncMock())
 # offer is a synchronous local enqueue in production, not a sender.
 offered=[];plugin.private_ping.offer=offered.append
 data={'matches':[{'match_ref':'old'}]}
 plugin.valorant_records=SimpleNamespace(read=AsyncMock(side_effect=lambda *a:data))
 assert (await plugin.poll_new_matches())['new_count']==0
 data['matches'].insert(0,{'match_ref':'new'})
 assert (await plugin.poll_new_matches())['new_count']==1
 assert len(offered)==1
 assert (await plugin.poll_new_matches())['new_count']==0 and len(offered)==1

def test_upgrade_existing_timetable_adds_match_watch_once(plugin,monkeypatch):
 from astrbot_plugin_fish_capabilities.services.timetable import Timetable
 old=Timetable(plugin.root/'timetable.sqlite3',{})
 old.seed([])  # Already deployed tables must not rely on initial seeding again.
 monkeypatch.setattr(Timetable,'start',lambda *a:None)
 plugin.config.update(autonomy_enabled=True)
 plugin.context=SimpleNamespace(cron_manager=SimpleNamespace(scheduler=None))
 plugin.companion=SimpleNamespace(task_gate=None)
 plugin.start_timetable();plugin.start_timetable()
 with plugin.timetable.db() as db:
  assert db.execute("SELECT count(*) FROM tasks WHERE action='matches_watch'").fetchone()[0]==1
