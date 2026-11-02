from datetime import datetime
from types import SimpleNamespace
import pytest
from test_astrbot_binding import plugin,Event
from astrbot_plugin_fish_capabilities.services.vision_routing import peak,decision,ZONE
import astrbot_plugin_fish_capabilities.services.vision_routing as route

@pytest.mark.parametrize('day,clock,expected',[
 ('2026-11-02','08:59',False),('2026-11-02','09:00',True),('2026-11-02','11:59',True),
 ('2026-11-02','12:00',False),('2026-11-02','13:59',False),('2026-11-02','14:00',True),
 ('2026-11-02','17:59',True),('2026-11-02','18:00',False),('2026-10-31','10:00',False),
 ('2026-10-10','10:00',False),('2026-10-01','10:00',False)])
def test_schedule_boundaries_weekends_even_makeup_and_holiday(day,clock,expected):
 assert peak(datetime.fromisoformat(day+'T'+clock).replace(tzinfo=ZONE).timestamp()) is expected

def test_disabled_and_private_calendar(tmp_path):
 t=datetime(2027,1,1,10,tzinfo=ZONE).timestamp()
 assert decision({},tmp_path,t)=='existing'
 assert decision({'vision_peak_routing_enabled':True},tmp_path,t)=='qwen3.8-omni-flash'
 (tmp_path/'vision-routing-calendar.private.json').write_text('{"holidays":["2027-01-01"]}')
 assert decision({'vision_peak_routing_enabled':True},tmp_path,t)=='existing'

async def test_bounded_images_route_without_mutating_provider(plugin,monkeypatch):
 plugin.context=SimpleNamespace(get_config=lambda:{})
 monkeypatch.setattr(route,'decision',lambda *a:'qwen3.8-omni-flash')
 calls=[]
 async def qwen(*args):calls.append(args);return SimpleNamespace(completion_text='seen',usage=SimpleNamespace(input_other=10,input_cached=0,output=2))
 monkeypatch.setattr(route,'qwen',qwen)
 result=await plugin.bounded_generate('deepseek/deepseek-flash',prompt='p',system_prompt='s',image_urls=['test.png'],timeout=2,max_tokens=50)
 assert result.completion_text=='seen' and len(calls)==1
 assert calls[0][2:5]==('p','s',['test.png'])

async def test_image_preread_failure_keeps_original_images(plugin,monkeypatch):
 plugin.context=SimpleNamespace(get_config=lambda:{})
 monkeypatch.setattr(route,'decision',lambda *a:'qwen3.8-omni-flash')
 async def fail(*args):raise TimeoutError('private-not-logged')
 monkeypatch.setattr(route,'qwen',fail)
 request=SimpleNamespace(image_urls=['current.png'])
 e=Event();e.get_message_str=lambda:'看看'
 await plugin.peak_image_observation(e,request)
 assert request.image_urls==['current.png']

async def test_image_preread_success_adds_temporary_data_only(plugin,monkeypatch):
 import sys,types
 plugin.context=SimpleNamespace(get_config=lambda:{})
 monkeypatch.setattr(route,'decision',lambda *a:'qwen3.8-omni-flash')
 class Part:
  def __init__(self,*,text):self.text=text
  def mark_as_temp(self):self.temporary=True;return self
 monkeypatch.setitem(sys.modules,'astrbot.core.agent.message',types.SimpleNamespace(TextPart=Part))
 async def ok(*args):return SimpleNamespace(completion_text='actual image',usage=SimpleNamespace(input_other=10,input_cached=0,output=2))
 monkeypatch.setattr(route,'qwen',ok)
 request=SimpleNamespace(image_urls=['current.png'],system_prompt='original persona')
 e=Event();e.get_message_str=lambda:'看看'
 await plugin.peak_image_observation(e,request)
 assert not request.image_urls and request.extra_user_content_parts[0].temporary
 assert request.system_prompt=='original persona'

async def test_no_images_never_calls_qwen(plugin,monkeypatch):
 monkeypatch.setattr(route,'decision',lambda *a:(_ for _ in ()).throw(AssertionError('text must not route')))
 await plugin.peak_image_observation(Event(),SimpleNamespace(image_urls=[]))
