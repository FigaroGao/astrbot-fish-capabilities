import json
import pytest
from astrbot_plugin_fish_capabilities.services.course_progress import CourseProgress
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_astrbot_binding import plugin,Event

def test_record_recall_correct_and_preserve_history(tmp_path):
    p=CourseProgress(tmp_path/'c.db');first=p.record('XAI','SHAP的局部解释','今天XAI讲到SHAP的局部解释')
    assert p.record('XAI','SHAP的局部解释','今天XAI讲到SHAP的局部解释')['duplicate']
    p.record('XAI','LIME而不是SHAP','XAI实际讲到LIME而不是SHAP',first['id'])
    assert [x['progress'] for x in p.search('XAI')['notes']]==['LIME而不是SHAP']
    import sqlite3
    with sqlite3.connect(p.path) as db:assert db.execute('SELECT COUNT(*) FROM notes').fetchone()[0]==2
    assert p.search('不存在')['notes']==[]

def test_guesses_and_other_course_corrections_rejected(tmp_path):
    p=CourseProgress(tmp_path/'c.db')
    with pytest.raises(CapabilityError):p.record('XAI','已经掌握SHAP','今天讲XAI')
    first=p.record('点云','配准','点云讲到配准')
    with pytest.raises(CapabilityError):p.record('XAI','归因','XAI讲到归因',first['id'])
    with pytest.raises(CapabilityError):p.search('',100)

async def test_private_owner_authorization_and_current_speech(plugin):
    plugin.config['history_enabled']=True
    e=Event();e.get_message_str=lambda:'今天XAI讲到SHAP'
    result=json.loads(await plugin.course_progress_tool(e,'record',course='XAI',progress='SHAP'));assert result['saved']
    outsider=Event(sender='999');outsider.get_message_str=e.get_message_str
    assert json.loads(await plugin.course_progress_tool(outsider))['ok'] is False
    group=Event(private=False);group.get_message_str=e.get_message_str
    assert json.loads(await plugin.course_progress_tool(group))['ok'] is False

def test_confirmed_schedule_weekday_alias_and_missing(tmp_path):
    p=CourseProgress(tmp_path/'c.db')
    assert not p.schedule()['confirmed']
    data={'semester':'fixture','timezone':'Asia/Hong_Kong','confirmed_by_owner_on':'2026-10-29','lectures':[{'course':'CS1234','name':'生成式AI／GAI','weekday':1,'start':'20:00','end':'21:50','room':'fixture'},{'course':'CS5678','name':'可解释AI／XAI','weekday':3,'start':'19:00','end':'20:50','room':'fixture'}]}
    p.path.with_name('owner-lecture-schedule.private.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    assert len(p.schedule()['lectures'])==2
    assert p.schedule('周三几点上课')['lectures'][0]['course']=='CS5678'
    assert p.schedule('GAI在哪上课')['lectures'][0]['course']=='CS1234'
    assert p.schedule('星期六')['lectures']==[]
    assert p.schedule('不存在')['lectures']==[]
    p.bind('1234',{'id':'9','name':'fixture','course_code':'202609CS1234'},'1234对应9')
    assert p.schedule('1234')['lectures'][0]['course']=='CS1234'

async def test_schedule_uses_owner_private_gate(plugin):
    plugin.config['history_enabled']=True
    assert json.loads(await plugin.course_progress_tool(Event(),'schedule'))['confirmed'] is False
    assert json.loads(await plugin.course_progress_tool(Event(private=False),'schedule'))['ok'] is False
    assert json.loads(await plugin.course_progress_tool(Event(sender='999'),'schedule'))['ok'] is False
