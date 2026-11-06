"""Per-installation timezone, without changing process-wide timezone state."""
import re
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .policy import CapabilityError

DEFAULT_TIMEZONE = 'UTC+08:00'


def local_zone(config=None):
    value = (config or {}).get('local_timezone', DEFAULT_TIMEZONE)
    if not isinstance(value, str):
        raise CapabilityError('local_timezone 必须为 IANA 时区或 UTC±HH:MM。')
    if value == 'UTC':
        return timezone.utc
    match = re.fullmatch(r'UTC([+-])(\d{2}):(\d{2})', value)
    if match:
        hours, minutes = int(match[2]), int(match[3])
        if hours > 14 or minutes > 59 or (hours == 14 and minutes):
            raise CapabilityError('时区偏移超出支持范围。')
        return timezone((1 if match[1] == '+' else -1) * timedelta(hours=hours, minutes=minutes))
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise CapabilityError('未知时区；请填写有效 IANA 名称或 UTC±HH:MM。') from None


def zone_name(config=None):
    local_zone(config)  # Validate before reporting the configured value.
    return (config or {}).get('local_timezone', DEFAULT_TIMEZONE)
