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
