"""Cross-reference archived statements only inside identified historical material."""
def historical_blocks(req):
    blocks=[]
    for row in getattr(req,'contexts',[]) or []:
        if isinstance(row,dict) and row.get('role')=='user':
            text=row.get('content')
            if isinstance(text,str) and text.startswith('[历史摘要资料]'):blocks.append(('摘要',text))
    for part in getattr(req,'extra_user_content_parts',[]) or []:
        text=part.get('text','') if isinstance(part,dict) else getattr(part,'text','')
        if isinstance(text,str) and text.strip().startswith('<RAG-Faiss-Memory>') and text.strip().endswith('</RAG-Faiss-Memory>'):
            blocks.append(('长期记忆',text))
    return blocks

def amendments(blocks,links):
    found={}
    for old,new,stamp,source in links:
        if not isinstance(old,str) or len(old.strip())<6 or old==new:continue
        for kind,text in blocks:
            if old in text:
                found.setdefault((kind,old),{})[new]=(stamp,source)
    results=[]
    for (kind,old),versions in found.items():
        if len(versions)!=1:continue
        new,(stamp,source)=next(iter(versions.items()))
        results.append(dict(material=kind,old=old[:400],current=new[:800],corrected_at=stamp,source=source))
    return sorted(results,key=lambda r:-r['corrected_at'])[:3]
