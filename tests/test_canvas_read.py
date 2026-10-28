import json
import pytest
from astrbot_plugin_fish_capabilities.services import canvas_read as cr
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_astrbot_binding import plugin,Event

def test_no_arbitrary_endpoint_or_write():
    for path in ['/api/v1/users/12','/api/v1/courses/1/submissions','https://evil.test','/api/v1/courses/1/../assignments']:
        with pytest.raises(CapabilityError):cr.get('not-real',path)

async def test_courses_are_bounded_and_no_token_exposed(tmp_path,monkeypatch):
    p=tmp_path/'token.json';p.write_text(json.dumps({'base_url':cr.BASE,'token':'test-fixture-only'}))
    seen=[]
    def get(token,path,params):seen.append((path,params));return [{'id':1,'name':'course','secret':'not exposed'}],True
    monkeypatch.setattr(cr,'get',get)
    result=await cr.CanvasRead(p).query();assert result['has_more'] and result['items'][0]['id']==1
    assert 'test-fixture-only' not in json.dumps(result) and 'secret' not in json.dumps(result)
    with pytest.raises(CapabilityError):await cr.CanvasRead(p).query('submit','1')
    with pytest.raises(CapabilityError):await cr.CanvasRead(p).query('assignments','1/evil')

async def test_submission_unknown_is_not_submitted(tmp_path,monkeypatch):
    p=tmp_path/'token.json';p.write_text(json.dumps({'base_url':cr.BASE,'token':'test-fixture-only'}))
    monkeypatch.setattr(cr,'get',lambda *a:([{'id':1,'has_submitted_submissions':True,'description':'<script>evil()</script><p>Hello</p>'}],False))
    result=await cr.CanvasRead(p).query('assignments','1');row=result['items'][0]
    assert row['my_submission']['workflow_state'] is None and 'has_submitted_submissions' not in row and 'evil' not in row['description']

async def test_canvas_tool_closed_by_default_and_owner_only(plugin):
    assert json.loads(await plugin.canvas_tool(Event()))['ok'] is False
    plugin.config['canvas_enabled']=True
    assert json.loads(await plugin.canvas_tool(Event(private=False)))['ok'] is False
    assert json.loads(await plugin.canvas_tool(Event(sender='outsider')))['ok'] is False
