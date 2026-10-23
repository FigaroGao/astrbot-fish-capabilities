"""A current, explicitly addressed request may bypass soft meme spacing."""
import re


def explicit_meme_request(event):
    try:
        parts=event.get_messages()
        text=''.join(p.text for p in parts if p.__class__.__name__=='Plain').strip()
        bot=str(event.get_self_id()); directed=False; other=False
        for p in parts:
            kind=p.__class__.__name__
            target=str(getattr(p,'qq','')) if kind=='At' else str(getattr(p,'sender_id','') or '') if kind=='Reply' else ''
            directed |= target==bot
            other |= target not in ('','0','all',bot)
        if other and not directed:return False
        addressed=(directed or event.is_private_chat() or bool(getattr(event,'is_at_or_wake_command',False))
                   or bool(re.match(r'^(?:小鲸|大肥鱼)[，,、\s：:!！]*',text)))
        if not addressed:return False
        if re.search(r'(?:别|不要|不用|不许|禁止|停止).{0,5}(?:发|来|表情|贴图)',text):return False
        # Quoted content is deliberately absent: only current Plain components.
        if re.search(r'(?:他说|她说|有人说|让别人|让他|让她|假如|例如|如果).{0,15}(?:表情|贴图|梗图)',text):return False
        return bool(re.search(r'(?:发|来|给|甩|丢|要).{0,12}(?:表情包?|贴图|梗图)',text)
                    or re.search(r'(?:表情包?|贴图|梗图).{0,8}(?:发|来|给)',text)
                    or re.search(r'(?:再发|再来|换|再换)[一1]?[张个]',text))
    except (AttributeError,TypeError):
        return False
