import pytest,json
from astrbot_plugin_fish_capabilities.services.course_progress import CourseProgress
from astrbot_plugin_fish_capabilities.services.course_context import CourseContext
from astrbot_plugin_fish_capabilities.services.policy import CapabilityError
from test_astrbot_binding import plugin,Event

class Canvas:
    async def query(self,action,course_id='',page=1):
        return {'items':[{'id':1,'name':'Explainable AI','course_code':'CS100'}] if action=='courses' else [],'has_more':False,'page':page}

async def test_confirmed_alias_joins_old_notes_without_rewriting(tmp_path):
    notes=CourseProgress(tmp_path/'n.db');c=CourseContext(Canvas(),notes)
    notes.record('XAI','SHAP','XAI讲到SHAP')
    assert (await c.run('view','XAI','',''))['needs_course_confirmation']
    with pytest.raises(CapabilityError):await c.run('bind','XAI','1','看看XAI')
    await c.run('bind','XAI','1','XAI就是CS100')
    result=await c.run('view','xai','','')
    assert result['owner_progress'][0]['progress']=='SHAP' and 'assignments' in result['canvas']
    assert '不证明' in result['instruction']
    assert notes.unlink('XAI','解除XAI关联')['removed']
    assert notes.search('XAI')['notes'][0]['progress']=='SHAP'

def test_conflicts_do_not_rebind_silently(tmp_path):
    notes=CourseProgress(tmp_path/'n.db');notes.bind('XAI',{'id':1,'name':'A','course_code':'CS100'},'XAI对应CS100')
    with pytest.raises(CapabilityError):notes.bind('xai',{'id':2,'name':'B','course_code':'CS200'},'xai对应CS200')
    assert notes.links()[0]['course_id']=='1'

async def test_combined_tool_denies_other_people_and_groups(plugin):
    plugin.config.update(canvas_enabled=True,history_enabled=True)
    assert json.loads(await plugin.course_context_tool(Event(private=False)))['ok'] is False
    assert json.loads(await plugin.course_context_tool(Event(sender='other')))['ok'] is False
