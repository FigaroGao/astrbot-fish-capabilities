import json,sqlite3
from types import SimpleNamespace as NS
from astrbot_plugin_fish_capabilities.services.owner_notebook import OwnerNotebook
from astrbot_plugin_fish_capabilities.services.memory_editor import MemoryEditor
from astrbot_plugin_fish_capabilities.services.recall_corrections import historical_blocks,amendments

def test_cross_store_version_chain_and_scope(tmp_path):
    store=MemoryEditor(tmp_path/'edits.db',None)
    old='每周六上午都有训练';middle='每周三上午都有训练';new='每周五上午都有训练'
    with sqlite3.connect(store.path) as db:
        for a,b,x,y,state in [(1,2,old,middle,'completed'),(2,3,middle,new,'completed'),(3,4,new,'错误数据','failed')]:
            db.execute('INSERT INTO edits(stamp,old_id,new_id,scope,persona,before,after,state) VALUES(?,?,?,?,?,?,?,?)',(a,a,b,'s','p',json.dumps({'record':{'text':x}}),y,state))
    req=NS(contexts=[{'role':'user','content':'[历史摘要资料]'+old}],extra_user_content_parts=[NS(text='<RAG-Faiss-Memory>'+middle+'</RAG-Faiss-Memory>')])
    blocks=historical_blocks(req)
    result=amendments(blocks,store.correction_links('s','p'))
    assert len(result)==2 and all(r['current']==new for r in result)
    assert not amendments(blocks,store.correction_links('s','other'))
    assert not amendments([('摘要','他周六也有其他活动')],store.correction_links('s','p'))

def test_notebook_revisions_and_ambiguous_evidence(tmp_path):
    n=OwnerNotebook(tmp_path/'notes.db');old='原定每周六去游泳';new='改为每周三去游泳'
    first=n.save('correction','游泳',old,old,old)
    n.save('correction','游泳',new,new,new,first['id'])
    ref=n.study_save('s','游泳',old,{},'noted')
    n.study_save('s','游泳','改为每周五去游泳',{},'corrected',ref['id'],1)
    assert not amendments([('摘要',old)],n.correction_links('s'))
    assert not historical_blocks(NS(contexts=[{'role':'user','content':old}],extra_user_content_parts=[]))
