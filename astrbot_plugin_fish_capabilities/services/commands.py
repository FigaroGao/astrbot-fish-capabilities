"""Owner-only command boundary before AstrBot parses/wakes a message.

Ordinary chat remains available. Scope is the operator's configured QQ adapter.
"""
from __future__ import annotations

import functools


class CommandGate:
    def __init__(self, owners: list[str], platforms: list[str]):
        self.owners = set(map(str, owners))
        self.platforms = set(platforms)

    def blocks(self, event, config, command_names=()) -> bool:
        if event.get_platform_id() not in self.platforms or str(event.get_sender_id()) in self.owners:
            return False
        parts = event.get_messages()
        text = ''.join(p.text for p in parts if p.__class__.__name__ == 'Plain').lstrip()
        if not text:
            text = str(event.message_str or '').lstrip()
        prefixes = set(config.get('wake_prefix', [])) | {'/', '!', '#', '／', '！', '＃'}
        if any(prefix and text.startswith(prefix) for prefix in prefixes):
            return True
        # Private chat and explicit @/quote can invoke a registered command even
        # without a slash. A normal group sentence mentioning 'help' isn't one.
        directly_addressed = event.is_private_chat() or any(
            (p.__class__.__name__ == 'At' and str(getattr(p,'qq','')) == str(event.get_self_id()))
            or (p.__class__.__name__ == 'Reply' and str(getattr(p,'sender_id','')) == str(event.get_self_id()))
            for p in parts)
        return bool(directly_addressed and text and text.split()[0] in command_names)


def install_gate(stage_class, gate, registry):
    """Reversible wrapper; existing stage instances resolve their class method.

    Standard message handlers run too late: argument errors/permission replies
    can already be sent inside waking-check. Keep this patch local to a plugin;
    never edit the core file. Refuse competing wrappers rather than stacking.
    """
    original = stage_class.process
    if getattr(original, '_fish_command_gate', False):
        raise RuntimeError('Fish command boundary is already installed')

    @functools.wraps(original)
    async def process(stage, event):
        names = set()
        for metadata in registry.star_handlers_map.values():
            for item in metadata.event_filters:
                name = getattr(item, 'command_name', None)
                if name: names.add(name)
                names.update(getattr(item, 'alias', ()) or ())
        if gate.blocks(event, stage.ctx.astrbot_config, names):
            event.set_extra('fish_command_blocked', True)
            event.clear_result()
            event.stop_event()
            return
        return await original(stage, event)

    process._fish_command_gate = True
    stage_class.process = process

    def uninstall():
        if stage_class.process is process:
            stage_class.process = original
    return uninstall
