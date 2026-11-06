"""Use scoped summary/source links as an index, never dates as proof."""
import asyncio,json
from .cold_memory import redact,RULE


async def summary_fallback(cold,engine,scope,persona,query,result,limit=2):
    if result.get('state')!='no_match' or not result.get('lookup_performed'):return result
    out=dict(result,summary_hits=[],source_candidates=[],summary_lookup='completed')
    try:
        hits=await asyncio.wait_for(engine.search_memories(query,k=3,session_id=scope,persona_id=persona),15)
        for hit in hits[:3]:
            ident=int(hit.doc_id)
            row=await asyncio.wait_for(engine.get_memory_record(ident),5)
            if not isinstance(row,dict):continue
            metadata=row.get('metadata') or {}
            if isinstance(metadata,str):metadata=json.loads(metadata)
            if metadata.get('session_id')!=scope or metadata.get('persona_id')!=persona:continue
            summary={'memory_id':ident,'summary':redact(str(row.get('text') or ''))[:600],
                     'linked_original_found':False,'original_text_verified':False,'date_verified':False,'summary_equivalence_verified':False}
            out['summary_hits'].append(summary)
            sources=await asyncio.wait_for(engine.get_memory_source(ident),5)
            if not isinstance(sources,list):sources=[]
            # Older summaries may retain quoted source windows even when the
            # source-message table is empty. These are pointers, not originals.
            evidence=(metadata.get('fish_provenance') or {}).get('evidence') or []
            pointers=[]
            for source in sources[:30]:
                if not isinstance(source,dict) or source.get('role') not in ('user','assistant'):continue
                if source.get('session_id',scope)!=scope or source.get('persona_id',persona)!=persona:continue
                if source['role']=='user' and str(source.get('sender_id',''))!=scope.rsplit(':',1)[-1]:continue
                text=source.get('content')
                if isinstance(text,str) and text.strip():pointers.append((text,source['role'],'stored_source'))
            for source in evidence[:8]:
                if isinstance(source,dict) and str(source.get('sender_id',''))==scope.rsplit(':',1)[-1] and isinstance(source.get('excerpt'),str):
                    pointers.append((source['excerpt'],'user','summary_evidence_pointer'))
            for text,role,basis in pointers[:38]:
                text=redact(text)
                if not any(term in text for term in query.split()[:5]):continue
                if len(text.strip())<4:continue
                # Verify exact content against the immutable archive, within
                # this same scope/persona and speaker. No summary date window.
                quote=text[:240]
                escaped=quote.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
                with cold.db() as db:
                    rows=db.execute("SELECT * FROM chunks WHERE scope=? AND persona=? AND role=? AND text LIKE ? ESCAPE '\\' ORDER BY stamp DESC LIMIT 2",(scope,persona,role,'%'+escaped+'%')).fetchall()
                for archived in rows:
                    excerpt=cold.excerpt(archived)
                    if any(x['id']==excerpt['id'] for x in out['excerpts']):continue
                    out['excerpts'].append(excerpt);summary['linked_original_found']=True
                    if len(out['excerpts'])>=limit:break
                if basis=='stored_source' and len(out['source_candidates'])<2:
                    out['source_candidates'].append({'memory_id':ident,'role':role,'text':text[:1000],
                        'basis':basis,'original_text_verified':False,'date_verified':False,
                        'summary_equivalence_verified':False})
                if len(out['excerpts'])>=limit:break
            if len(out['excerpts'])>=limit:break
    except asyncio.CancelledError:raise
    except Exception:
        out['summary_lookup']='unavailable_or_partial'
    out['state']='found_via_summary' if out['excerpts'] else 'summary_only' if out['summary_hits'] else 'no_match'
    out['original_text_verified']=bool(out['excerpts'])
    out['existence_conclusion']='matching_archive_found' if out['excerpts'] else 'summary_original_unverified' if out['summary_hits'] else 'undetermined' if out['summary_lookup']!='completed' else 'no_match_in_this_query'
    out['instruction']=RULE+' 摘要仅作索引；source_candidates是关联来源候选，不保证与概括是同一件事，summary_equivalence_verified=false，须核对说话人和内容。只有excerpts经冷档校验；只有time_quality=message_time可称记录的消息时间已核验，仍不证明事件发生时间。没有原文就明确说摘要命中但原文未确认，不根据摘要日期挑同一天另一段话。'
    return out
