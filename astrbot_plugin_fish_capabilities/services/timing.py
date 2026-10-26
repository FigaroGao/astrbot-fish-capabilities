"""Shared Hong Kong activity windows and inexpensive maintenance timing."""
from datetime import datetime, timedelta, timezone
import time

HK = timezone(timedelta(hours=8))


def activity_timing(config, stamp):
    # Old installations without these fields retain their previous schedule.
    start = int(config.get('initiative_start_hour', 9))
    end = int(config.get('initiative_end_hour', 23))
    minutes = int(config.get('initiative_interval_minutes', 60))
    if not (0 <= start <= 23 and 0 <= end <= 23 and 1 <= minutes <= 1440):
        raise ValueError('Invalid activity schedule')
    local = datetime.fromtimestamp(stamp, HK)
    allowed = (start <= local.hour < end) if start < end else (local.hour >= start or local.hour < end)
    if start == end:
        allowed = True
    bucket = (local.hour * 60 + local.minute) // minutes
    slot = local.strftime('%Y-%m-%d ') + str(bucket)
    return {'local': local, 'allowed': allowed, 'slot': slot,
            'interval_seconds': minutes * 60,
            'description': f'香港{start:02d}:00至'+('次日' if start > end else '')+f'{end:02d}:00，每{minutes}分钟最多判断一次'}


def poll_interval(config):
    seconds = int(config.get('background_poll_seconds', 600))
    if not 60 <= seconds <= 86400:
        raise ValueError('Invalid background polling interval')
    return seconds


def poll_delay(config, stamp=None):
    seconds = poll_interval(config)
    return seconds - ((time.time() if stamp is None else stamp) % seconds)
