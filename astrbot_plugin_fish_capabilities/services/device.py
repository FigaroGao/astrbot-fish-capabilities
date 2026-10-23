"""PC-only experimental ADB adapter. Not registered as an AstrBot tool.

No network listener, wireless pairing, generic shell, text input, installs,
messages, settings changes or root. Default dry-run; no command runs in that mode.
"""
from __future__ import annotations

import asyncio
import base64
import subprocess
import time
from pathlib import Path

from .policy import Actor, CapabilityError, bounded_int, require_owner


class DeviceBridge:
    def __init__(self, adb: Path, serial: str, owners: list[str], *, width: int = 2560,
                 height: int = 1600, allowed_apps: dict[str, str] | None = None,
                 dry_run: bool = True, runner=None):
        if not serial or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_' for c in serial):
            raise CapabilityError('请配置唯一的 ADB 设备序列号。')
        self.adb = str(adb)
        self.serial = serial
        self.owners = owners
        self.width = bounded_int(width, 100, 10000, '屏幕宽度')
        self.height = bounded_int(height, 100, 10000, '屏幕高度')
        self.allowed_apps = allowed_apps or {}
        self.dry_run = dry_run
        self.runner = runner or subprocess.run
        self.lock = asyncio.Lock()
        self.last: float | None = None

    def command(self, action: str, params: dict) -> list[str]:
        if action == 'screenshot': return ['exec-out', 'screencap', '-p']
        if action == 'status': return ['get-state']
        if action in ('back', 'home'):
            return ['shell', 'input', 'keyevent', '4' if action == 'back' else '3']
        if action == 'tap':
            x = bounded_int(params.get('x'), 0, self.width - 1, 'x')
            y = bounded_int(params.get('y'), 0, self.height - 1, 'y')
            return ['shell', 'input', 'tap', str(x), str(y)]
        if action == 'swipe':
            coords = [bounded_int(params.get(k), 0, bound - 1, k)
                      for k, bound in [('x1', self.width), ('y1', self.height), ('x2', self.width), ('y2', self.height)]]
            ms = bounded_int(params.get('duration', 400), 100, 1000, '滑动毫秒数')
            return ['shell', 'input', 'swipe', *map(str, coords), str(ms)]
        if action == 'open_app':
            # Package is operator configuration, never a free-form model argument.
            package = self.allowed_apps.get(params.get('app'))
            if not package or not all(c.isalnum() or c in '._' for c in package):
                raise CapabilityError('这个 App 尚未加入实验白名单。')
            return ['shell', 'monkey', '-p', package, '-c', 'android.intent.category.LAUNCHER', '1']
        raise CapabilityError('未开放这个设备动作。')

    async def execute(self, actor: Actor, action: str, params: dict | None = None):
        require_owner(actor, self.owners)
        command = [self.adb, '-s', self.serial, *self.command(action, params or {})]
        if self.dry_run:
            return {'dry_run': True, 'command': command, 'device_modified': False}
        async with self.lock:
            if self.last is not None and time.monotonic() - self.last < 2:
                raise CapabilityError('设备动作过快，请观察上一步结果再继续。')
            self.last = time.monotonic()
            try:
                result = await asyncio.to_thread(self.runner, command, capture_output=True,
                                                 timeout=12, check=True)
                data = result.stdout
            except Exception as exc:
                raise CapabilityError('ADB 实验动作失败，未尝试自动重连或重复点击。') from exc
            if action == 'screenshot':
                if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) > 15_000_000:
                    raise CapabilityError('截图返回内容异常。')
                return {'png_base64': base64.b64encode(data).decode(), 'private_device_data': True}
            return {'ok': True, 'action': action}
