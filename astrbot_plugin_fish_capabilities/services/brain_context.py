"""One stable identity source; task prompts and memory services stay separate."""
from .cold_memory import resolve_persona
from .companionship import COMPANION_STYLE,BILI_COMMENT_STYLE

CHARACTER_TASKS={'private_initiative','autonomy_decision','bili_dynamic_draft','bili_reply_draft',
                 'bili_selection_or_reflection','screenmate_intent'}

class BrainContext:
    def __init__(self,cap):self.cap=cap
    async def identity(self):
        cap=self.cap;scope=str(cap.config.get('bili_private_session',''))
        if not scope:return ''
        manager=cap.context.conversation_manager
        cid=await manager.get_curr_conversation_id(scope)
        conv=await manager.get_conversation(scope,cid) if cid else None
        persona=await resolve_persona(cap.context,scope,conv)
        if not persona:return ''
        value=cap.context.persona_manager.get_persona_v3_by_id(persona)
        return str(value.get('prompt') or '') if isinstance(value,dict) else ''
    async def compose(self,kind,task):
        if kind not in CHARACTER_TASKS:return task
        # Reload the existing persona instead of preserving a divergent copy.
        try:identity=await self.identity()
        except (AttributeError,KeyError):identity=''
        parts=[identity] if identity else [task]
        if self.cap.config.get('companionship_enabled',False):parts.append(COMPANION_STYLE)
        parts.append(self.cap.brain.prompt())
        if kind in ('bili_reply_draft','bili_selection_or_reflection'):parts.append(BILI_COMMENT_STYLE)
        if identity:parts.append('[Task-specific constraints; permissions and public review still apply]\n'+task)
        return '\n'.join(parts)
