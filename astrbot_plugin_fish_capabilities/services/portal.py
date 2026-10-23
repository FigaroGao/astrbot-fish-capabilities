"""Standalone-tablet candidate transport for Mobilerun Portal.

Uses its documented local HTTP API; does not implement an accessibility service.
Not registered in AstrBot, not connected to a tablet. Dry-run by default.
"""
from __future__ import annotations

import asyncio
import base64
import json
import urllib.parse
import urllib.request
from pathlib import Path

from .device import DeviceBridge
from .http import NoRedirect
from .policy import CapabilityError, require_owner


class PortalTransport:
    def __init__(self, token: str, port: int = 8080):
        if not token or '\r' in token or '\n' in token:
            raise CapabilityError('尚未配置有效的 Portal 本地访问令牌。')
        if type(port) is not int or not 1024 <= port <= 65535:
            raise CapabilityError('本地 Portal 端口无效。')
        self.token = token
        self.base = f'http://127.0.0.1:{port}'

    async def request(self, path: str, params: dict | None):
        def run():
            data = urllib.parse.urlencode(params).encode() if params is not None else None
            req = urllib.request.Request(self.base + path, data=data,
                                          headers={'Authorization': 'Bearer ' + self.token,
                                                   'Content-Type': 'application/x-www-form-urlencoded'})
            # Do not route authenticated loopback traffic through system proxies.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
            try:
                with opener.open(req, timeout=12) as response:
                    body = response.read(15_000_001)
                if len(body) > 15_000_000: raise CapabilityError('Portal 返回内容过大。')
                if path.startswith('/screenshot'):
                    if not body.startswith(b'\x89PNG\r\n\x1a\n'): raise CapabilityError('Portal 截图不是 PNG。')
                    return {'png_base64': base64.b64encode(body).decode(), 'private_device_data': True}
                payload = json.loads(body)
                if not isinstance(payload, dict) or payload.get('status') != 'success':
                    raise CapabilityError('Portal 未确认本次动作成功。')
                return payload
            except CapabilityError: raise
            except Exception as exc: raise CapabilityError('Portal 本地请求失败，未重试或记录令牌。') from exc
        return await asyncio.to_thread(run)


class PortalBridge(DeviceBridge):
    def __init__(self, owners: list[str], transport=None, *, width=2560, height=1600,
                 allowed_apps=None, dry_run=True):
        super().__init__(Path('unused'), 'local_portal', owners, width=width, height=height,
                         allowed_apps=allowed_apps, dry_run=dry_run)
        self.transport = transport
        self.actions = 0

    def request_plan(self, action: str, params: dict):
        command = self.command(action, params)  # Same coordinate/package validation.
        if action == 'status': return '/version', None
        if action == 'screenshot': return '/screenshot?hideOverlay=true', None
        if action == 'tap': return '/tap', {'x': int(command[-2]), 'y': int(command[-1])}
        if action == 'swipe':
            return '/swipe', dict(zip(('startX','startY','endX','endY','duration'), map(int, command[-5:])))
        if action in ('back', 'home'): return '/global', {'action': 1 if action == 'back' else 2}
        if action == 'open_app': return '/app', {'package': self.allowed_apps[params['app']], 'stopBeforeLaunch': 'false'}
        raise CapabilityError('未开放此 Portal 动作。')

    async def execute(self, actor, action: str, params: dict | None = None):
        require_owner(actor, self.owners)
        path, data = self.request_plan(action, params or {})
        if self.dry_run:
            return {'dry_run': True, 'loopback_path': path, 'params': data, 'device_modified': False}
        if self.transport is None:
            raise CapabilityError('尚未配置 Portal 传输。')
        async with self.lock:
            # Experimental sessions are intentionally short and require a new
            # operator-created bridge instance after three modifying actions.
            modifying = action not in ('status', 'screenshot')
            if modifying and self.actions >= 3:
                raise CapabilityError('本次设备实验已到三步上限，请先人工检查结果。')
            if modifying: self.actions += 1  # Ambiguous timeouts also count.
            return await self.transport.request(path, data)
