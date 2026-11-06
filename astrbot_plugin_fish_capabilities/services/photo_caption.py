"""Join an owner-private QQ photo and its immediately following caption."""
import asyncio
from collections.abc import Mapping


def is_sticker(event):
    raw = getattr(event.message_obj, 'raw_message', None)
    segments = raw.get('message', []) if hasattr(raw, 'get') else []
    for segment in segments if isinstance(segments, list) else ():
        if not isinstance(segment, Mapping):
            continue
        data = segment.get('data') or {}
        if segment.get('type') in ('face', 'mface'):
            return True
        if segment.get('type') == 'image' and isinstance(data, Mapping):
            if (str(data.get('sub_type', '0')) in ('1', '7') or data.get('emoji_id')
                    or data.get('emoji_package_id') or data.get('type') == 'show'
                    or '表情' in str(data.get('summary', ''))):
                return True
    return False


class PhotoCaption:
    def __init__(self):
        self.pending = {}

    async def observe(self, event, seconds):
        key = (event.unified_msg_origin, str(event.get_sender_id()))
        parts = event.get_messages()
        kinds = [type(part).__name__ for part in parts]
        waiting = self.pending.get(key)
        if not parts or is_sticker(event):
            return
        if all(kind == 'Image' for kind in kinds):
            if waiting:
                # Keep the first photo's deadline, even for an album.
                waiting[0].get_messages().extend(parts)
                event.stop_event()
                return
            ready = asyncio.Event()
            self.pending[key] = (event, ready)
            try:
                try:
                    await asyncio.wait_for(ready.wait(), seconds)
                except asyncio.TimeoutError:
                    pass
            finally:
                if self.pending.get(key, (None,))[0] is event:
                    self.pending.pop(key)
        elif waiting and all(kind == 'Plain' for kind in kinds):
            text = event.get_message_str().strip()
            if not text or text.startswith(('/', '!', '！')) or len(text)>600:
                return
            photo, ready = self.pending.pop(key)
            parts[:0] = photo.get_messages()
            photo.stop_event()
            ready.set()

    def close(self):
        for _, ready in self.pending.values():
            ready.set()
        self.pending.clear()
