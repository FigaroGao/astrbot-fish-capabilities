from tools.knowledge_quality import audit

def test_quality_flags_do_not_mutate_or_invent_facts():
    rows=[{'id':'one','text':'data','aliases':['same'],'source':'https://example.com','checked_at':'2026-11-06'},
          {'id':'two','text':'','aliases':['same'],'source':'local notes','checked_at':'unknown'}]
    result=audit(rows)
    assert result['alias_conflicts']['same']==['one','two']
    assert result['review_items'][0]['id']=='two' and not result['duplicate_ids']
    assert rows[1]['text']==''
