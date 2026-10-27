"""Evidence and temporal labels, without guessing facts or changing visibility.

This module is also copied into the local LivingMemory adapter. It has no
AstrBot imports, model calls or database mutations. A source window is evidence
of what was said, not proof that a generated summary is objectively true.
"""
from __future__ import annotations

import copy
import hashlib
import math
import re
from datetime import datetime, timezone
from typing import Any

KINDS = {'fact', 'state', 'event', 'inference', 'summary', 'fiction'}
SLOT_LIMITS = {'fact': 2, 'state': 1, 'event': 2, 'inference': 1, 'summary': 2, 'fiction': 1,
               'member_profile':2,'group_topic':2}
_SECRET = re.compile(r'(?i)(sk-[a-z0-9_-]{12,}|(?:SESSDATA|bili_jct|api[_ -]?key|password|token)\s*[:=]\s*[^\s,;]+)')
CLAIM_INSTRUCTION = '''\n在原有记忆JSON中另加claims数组，最多8项，每项为{"text":"一个原子陈述，最多180字","kind":"fact/state/event/inference/fiction","evidence_quote":"支持本项的真实user消息连续原话，4至240字","evidence_sender_id":"原发送者ID","ttl_hours":2}。没有依据则不提取。fact仅稳定的自述偏好、称呼、关系或已明确的长期约定；上课、睡觉、当前故障等是state，默认2小时且最长24小时；有具体时间的经历为event；自己的印象和不确定判断为inference，不写成对方的客观事实；角色虚构生活为fiction。引用、转述、问句、玩笑、假设和assistant自行补充不能证明user事实。稳定事实不填ttl_hours。保留原有summary/canonical_summary/key_facts等字段；claims是整理资料，不能改变身份、权限或可见范围。'''


def grounded_claims(data: dict, messages) -> list[dict]:
    """Verify exact quotations and attribution, not the semantic truth of a claim."""
    rows = data.get('claims', [])
    if not isinstance(rows, list):
        return []
    output = []
    seen = set()
    for claim in rows[:16]:
        if not isinstance(claim, dict):
            continue
        text, quote = claim.get('text'), claim.get('evidence_quote')
        kind = claim.get('kind')
        if (not isinstance(text, str) or not 1 <= len(text.strip()) <= 180
                or not isinstance(quote, str) or not 4 <= len(quote) <= 240
                or not isinstance(kind, str) or kind not in KINDS - {'summary'}):
            continue
        matching = []
        for message in messages:
            get = message.get if isinstance(message, dict) else lambda key, default=None: getattr(message, key, default)
            sender = str(get('sender_id', '') or '')
            if (get('role') == 'user' and quote in str(get('content', '') or '')
                    and sender and sender == str(claim.get('evidence_sender_id', ''))):
                matching.append((stamp(get('timestamp')), sender))
        matching = [m for m in matching if m[0] is not None]
        if not matching or text.strip() in seen:
            continue
        observed, sender = max(matching)
        if kind == 'fact' and re.search(r'正在|目前|现在|这会儿|今天|明天|暂时|还没|刚刚', quote + text):
            kind = 'state'
        if kind == 'fact' and re.search(r'可能|也许|是不是|会不会|[?？]', quote):
            kind = 'inference'
        expiry = None
        if kind == 'state':
            try:
                hours = float(claim.get('ttl_hours', 2))
            except (TypeError, ValueError):
                hours = 2
            if not math.isfinite(hours) or hours <= 0:
                hours = 2
            expiry = observed + min(hours, 24) * 3600
        elif kind == 'inference':
            expiry = observed + 7 * 86400
        output.append(dict(text=_SECRET.sub('[凭据已隐去]', text.strip()), kind=kind,
            observed_at=observed, expires_at=expiry, status='active', basis='quoted_statement',
            evidence=[dict(sender_id=sender, excerpt=_SECRET.sub('[凭据已隐去]', quote),
                           source_digest=hashlib.sha256(quote.encode()).hexdigest())]))
        seen.add(text.strip())
        if len(output) >= 8:
            break
    return output


def claims_for_injection(metadata: dict, *, now: float) -> str | None:
    """None: legacy fallback; empty: all structured claims expired/retracted."""
    claims = metadata.get('fish_claims')
    if not isinstance(claims, list) or not claims:
        return None
    lines = []
    for claim in claims[:8]:
        if not isinstance(claim, dict) or not isinstance(claim.get('text'), str):
            continue
        label = injection_label({'fish_provenance': claim}, now=now)
        if label is not None:
            lines.append(label + '\n' + claim['text'][:180])
    prefix = ''
    if metadata.get('memory_layer') == 'group':
        prefix = '【本群公共记忆】\n'
    elif metadata.get('memory_layer') == 'member':
        prefix = '【本群成员 ' + str(metadata.get('owner_user_id', '未知'))[:100] + ' 的个人记忆】\n'
    return prefix + '\n'.join(lines) if lines else ''


def stamp(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        if number > 1e12:
            number /= 1000
        return number if math.isfinite(number) and 0 < number <= 253402300799 else None
    except (ValueError, TypeError, OverflowError):
        try:
            dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            # Legacy naive dates are not given an invented timezone.
            return dt.timestamp() if dt.tzinfo is not None else None
        except (ValueError, TypeError, OverflowError):
            return None


def contract(metadata: dict) -> dict:
    raw = metadata.get('fish_provenance')
    raw = raw if isinstance(raw, dict) else {}
    kind = raw.get('kind', 'summary')
    if not isinstance(kind, str) or kind not in KINDS:
        kind = 'summary'
    return dict(schema=1, kind=kind, observed_at=stamp(raw.get('observed_at')),
                expires_at=stamp(raw.get('expires_at')),
                status=raw.get('status') if isinstance(raw.get('status'), str) else 'active',
                basis=raw.get('basis') if isinstance(raw.get('basis'), str) else 'legacy_summary',
                supersedes=raw.get('supersedes'),
                evidence=raw.get('evidence') if isinstance(raw.get('evidence'), list) else [])


def attach_source_context(metadata: dict, messages, *, owner_id=None) -> dict:
    """Retain bounded actual user excerpts; never manufacture per-fact support."""
    result = copy.deepcopy(metadata)
    if isinstance(result.get('fish_provenance'), dict):
        return result
    evidence = []
    latest = None
    for message in messages:
        get = message.get if isinstance(message, dict) else lambda key, default=None: getattr(message, key, default)
        if get('role') != 'user':
            continue
        if owner_id is not None and str(get('sender_id', '')) != str(owner_id):
            continue
        text = str(get('content', '') or '')
        if not text.strip():
            continue
        observed = stamp(get('timestamp'))
        if observed:
            latest = max(latest or observed, observed)
        evidence.append({'sender_id': str(get('sender_id', ''))[:100],
                         'at': observed, 'excerpt': _SECRET.sub('[凭据已隐去]', text)[:240],
                         'source_digest': hashlib.sha256(text.encode()).hexdigest()})
    result['fish_provenance'] = dict(schema=1, kind='summary', observed_at=latest,
        expires_at=None, status='active', basis='source_window' if evidence else 'unverified_summary',
        evidence=evidence[-8:])
    return result


def correction_provenance(metadata: dict, *, ident: int, evidence: str,
                          observed_at: float, historical: bool) -> dict:
    result = copy.deepcopy(metadata)
    result.pop('fish_claims', None)
    previous = contract(result)
    # An explicit correction can still describe a temporary state. Do not turn
    # it into a permanent fact merely because the speaker is the owner.
    result['fish_provenance'] = dict(schema=1, kind='event' if historical else 'summary',
        observed_at=previous['observed_at'] if historical else observed_at,
        expires_at=None, status='active', basis='reviewed_historical_reframe' if historical else 'owner_correction',
        supersedes=ident, evidence=[{'excerpt': _SECRET.sub('[凭据已隐去]', evidence)[:240],
                                   'source_digest': hashlib.sha256(evidence.encode()).hexdigest()}])
    return result


def injection_label(metadata: dict, *, now: float) -> str | None:
    """None means omit. Unknown legacy history is labelled, never called fact."""
    item = contract(metadata)
    if item['status'] in ('superseded', 'retracted', 'rejected', 'archived'):
        return None
    if item['kind'] == 'state':
        # A state with no reliable observation date cannot assert the present.
        observed = item['observed_at']
        expiry = item['expires_at'] or (observed + 7200 if observed else None)
        if not observed or observed > now + 300 or not expiry or expiry <= now:
            return None
    elif item['expires_at'] and item['expires_at'] <= now:
        return None
    labels = {'fact': '历史陈述，仍须服从当前明确更正', 'state': '有时效的当时状态，不推定一直持续',
              'event': '历史事件，不代表当前状态', 'inference': '当时的主观推测，未经确认为事实',
              'summary': '历史摘要，未逐项核实为当前事实', 'fiction': '角色生活或创作设定，不是现实经历'}
    when = datetime.fromtimestamp(item['observed_at'], timezone.utc).isoformat() if item['observed_at'] else '未知'
    proof = '有来源窗口，可按需核对原文' if item['basis'] == 'source_window' else (
        '来自主人明确更正' if item['basis'] == 'owner_correction' else '不把摘要或推测当作证据')
    return f'【记忆性质：{labels[item["kind"]]}；发生/依据时间：{when}；{proof}】'


def select_slots(memories: list, *, now: float, total: int = 8) -> list:
    """Bound categories and exact duplicates while preserving retriever order.

    This is after authorization; it does not grant access or merge scopes.
    """
    selected = []
    seen = set()
    counts = dict.fromkeys(SLOT_LIMITS, 0)
    for memory in memories:
        if not isinstance(memory, dict):
            selected.append(memory)  # Existing formatter handles legacy objects.
            if len(selected) >= total:
                break
            continue
        metadata = memory.get('metadata')
        if isinstance(metadata, str):
            import json
            try:
                metadata = json.loads(metadata)
            except (TypeError, ValueError):
                continue
        if not isinstance(metadata, dict):
            metadata = {}
        if injection_label(metadata, now=now) is None:
            continue
        text = str(metadata.get('persona_summary') or memory.get('content') or '').strip()
        # Dedup only within an identical visibility/persona scope.
        key = (str(metadata.get('session_id')), str(metadata.get('persona_id')), text)
        kind = contract(metadata)['kind']
        claims=metadata.get('fish_claims')
        kinds={c.get('kind') for c in claims if isinstance(c,dict) and isinstance(c.get('kind'),str)} if isinstance(claims,list) else set()
        if metadata.get('memory_layer')=='member':kind='member_profile'
        elif metadata.get('memory_layer')=='group':kind='group_topic'
        elif 'fact' in kinds:kind='fact'
        elif 'event' in kinds:kind='event'
        if not text or key in seen or counts[kind] >= SLOT_LIMITS[kind]:
            continue
        row = dict(memory, metadata=metadata)
        selected.append(row)
        seen.add(key)
        counts[kind] += 1
        if len(selected) >= total:
            break
    return selected


def balanced_results(results, *, limit, now):
    """Reserve slots for profiles, related episodes and the current topic.

    Input has already been scoped by the adapter. This does not search other
    sessions, infer new facts or issue another model/embedding request.
    """
    buckets={'profile':[], 'topic':[], 'experience':[]}
    seen=set()
    for result in results:
        metadata=getattr(result,'metadata',{}) or {}
        if not isinstance(metadata,dict) or injection_label(metadata,now=now) is None:continue
        content=claims_for_injection(metadata,now=now)
        if content=='':continue
        key=(str(getattr(result,'doc_id','')),str(metadata.get('session_id')))
        if key in seen:continue
        seen.add(key)
        kinds={c.get('kind') for c in metadata.get('fish_claims',[]) if isinstance(c,dict) and isinstance(c.get('kind'),str)} if isinstance(metadata.get('fish_claims'),list) else set()
        kind=contract(metadata)['kind']
        slot='profile' if metadata.get('memory_layer')=='member' or 'fact' in kinds or kind=='fact' else (
            'experience' if kind in ('event','fiction') or 'event' in kinds else 'topic')
        buckets[slot].append(result)
    chosen=[]
    while any(buckets.values()) and len(chosen)<limit:
        for slot in ('profile','topic','experience'):
            if buckets[slot] and len(chosen)<limit:chosen.append(buckets[slot].pop(0))
    return chosen
