"""Generic deployment settings: no real credentials, network or external messages."""
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from astrbot_plugin_fish_capabilities.services.local_time import local_zone, zone_name
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from astrbot_plugin_fish_capabilities.services.timing import activity_timing
from astrbot_plugin_fish_capabilities.services.timetable import Timetable
from astrbot_plugin_fish_capabilities.services.autonomy import Autonomy
from astrbot_plugin_fish_capabilities.services.quota import Quota
from astrbot_plugin_fish_capabilities.services import canvas_read as cr
from astrbot_plugin_fish_capabilities.services.weather import Weather


@pytest.mark.parametrize('value', ['UTC','UTC+05:30','UTC-07:00','Europe/Paris'])
def test_timezone_uses_explicit_setting(value):
    assert zone_name({'local_timezone':value}) == value
    assert local_zone({'local_timezone':value}) is not None


@pytest.mark.parametrize('value', ['','UTC+15:00','UTC+14:01','UTC+01:99','missing/timezone',None,123])
def test_bad_timezone_is_not_silently_reinterpreted(value):
    with pytest.raises(CapabilityError):local_zone({'local_timezone':value})


def test_activity_and_schedule_share_zone_without_global_mutation(tmp_path):
    stamp=datetime.fromisoformat('2026-11-06T10:00:00+00:00').timestamp()
    config={'local_timezone':'UTC-07:00','initiative_start_hour':9,'initiative_end_hour':17}
    assert not activity_timing(config,stamp)['allowed']
    assert activity_timing(dict(config,local_timezone='UTC'),stamp)['allowed']
    board=Timetable(tmp_path/'tasks.db',{'reminder':AsyncMock()},clock=lambda:stamp,config=config)
    trigger=board.trigger('at:2026-11-07T10:30:00')
    assert trigger.run_date.utcoffset()==timedelta(hours=-7)
    assert board.list()['timezone']=='UTC-07:00'
    # Explicit offsets remain absolute even if deployment timezone changes.
    assert board.trigger('at:2026-11-07T10:30:00+01:00').run_date.utcoffset()==timedelta(hours=1)


def test_dst_calendar_and_daily_budget_follow_config(tmp_path):
    config={'local_timezone':'Europe/Paris','initiative_start_hour':0,'initiative_end_hour':23}
    before=datetime.fromisoformat('2026-10-25T00:30:00+02:00').timestamp()
    after=datetime.fromisoformat('2026-10-25T23:30:00+01:00').timestamp()
    clock=[before]
    activity=Autonomy(tmp_path/'activity.db',config,AsyncMock(),AsyncMock(),AsyncMock(),clock=lambda:clock[0])
    assert activity.daily_once('weather')
    clock[0]=after
    assert not activity.daily_once('weather')  # 25-hour local day, still same day.
    clock[0]=after+3600
    assert activity.daily_once('weather')
    quota=Quota(tmp_path/'unused.json',config=config)
    assert quota.usage(before)['date']=='2026-10-25'
    assert quota.usage(before)['timezone']=='Europe/Paris'


@pytest.mark.parametrize('url', ['http://canvas.example.edu','https://user:secret@canvas.example.edu',
    'https://canvas.example.edu/api/v1','https://canvas.example.edu?token=secret',
    'https://canvas.example.edu/#fragment','https://canvas.example.edu:8443','https://localhost',
    'https://127.0.0.1',None])
def test_canvas_rejects_unbound_or_non_origin_urls(url):
    with pytest.raises(CapabilityError):cr.validate_base(url)


async def test_canvas_uses_only_origin_bound_with_token(tmp_path,monkeypatch):
    seen=[]
    class Response:
        headers={}
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):return b'[{"id":1,"name":"Course"}]'
    class Opener:
        def open(self,request,timeout):seen.append(request);return Response()
    monkeypatch.setattr(cr.urllib.request,'build_opener',lambda *args:Opener())
    file=tmp_path/'binding.json'
    file.write_text(json.dumps({'base_url':'https://learn.example.edu/','token':'fixture-not-a-secret'}))
    result=await cr.CanvasRead(file).query()
    assert seen[0].full_url.startswith('https://learn.example.edu/api/v1/courses?')
    assert seen[0].get_header('Authorization')=='Bearer fixture-not-a-secret'
    assert 'fixture-not-a-secret' not in json.dumps(result)
    assert result['items']==[{'id':1,'name':'Course','course_code':None,'workflow_state':None}]
    file.write_text(json.dumps({'token':'fixture-not-a-secret'}))
    with pytest.raises(CapabilityError):await cr.CanvasRead(file).query()
    assert len(seen)==1


async def test_missing_weather_city_never_calls_network():
    http=AsyncMock()
    with pytest.raises(CapabilityError):await Weather(http).get('')
    http.get.assert_not_called()
