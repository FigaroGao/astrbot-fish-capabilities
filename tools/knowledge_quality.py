"""Read-only quality inventory; findings are review leads, not automatic edits."""
import json,re
from collections import Counter,defaultdict
from datetime import date

def audit(entries):
    ids=Counter(str(e.get('id','')) for e in entries)
    aliases=defaultdict(set);issues=[]
    for e in entries:
        ident=str(e.get('id',''));flags=[]
        if not ident:flags.append('missing_id')
        if not str(e.get('text','')).strip():flags.append('empty_text')
        if not re.match(r'https?://',str(e.get('source',''))):flags.append('source_needs_review')
        try:date.fromisoformat(e.get('checked_at',''))
        except (ValueError,TypeError):flags.append('date_needs_review')
        for a in e.get('aliases',[]):
            if isinstance(a,str) and a.strip():aliases[a.strip().casefold()].add(ident)
        if flags:issues.append({'id':ident,'flags':flags})
    return {'entry_count':len(entries),'duplicate_ids':[i for i,c in ids.items() if c>1],
            'alias_conflicts':{a:sorted(v) for a,v in aliases.items() if len(v)>1},'review_items':issues,
            'note':'仅审计，不自动合并或改写；别名相同未必错误，无URL可能是本地整理来源，须人工核对。'}
