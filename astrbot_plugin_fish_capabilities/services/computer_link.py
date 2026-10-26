"""Passive local heartbeat: a transport hint, never a reader presence claim."""
import json
import time


def link_status(path, clock=time.time):
    state = {'state': 'unknown', 'connected': False, 'reader_active': None,
             'reader_state': 'not_observed',
             'reader_notified': False, 'age_seconds': None,
             'instruction': '设备连接状态不代表Codex正在运行、已经读信或即将回复。'}
    try:
        if path.is_symlink() or path.stat().st_size > 2048:
            return state
        packet = json.loads(path.read_text(encoding='utf-8'))
        stamp = packet['at']
        if type(stamp) not in (int, float) or packet.get('source') != 'local-computer-adb':
            return state
        age = clock() - stamp
        if not -30 <= age < 366 * 86400:
            return state
        state.update(age_seconds=int(max(0, age)), connected=age < 600,
                     state='connected' if age < 600 else 'stale')
        return state
    except (OSError, ValueError, KeyError, TypeError):
        return state
