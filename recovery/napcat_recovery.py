"""Private on-device login recovery. No process killing and no public listener."""
import argparse
import fcntl
import getpass
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

HOME = Path('/data/data/com.termux/files/home')
ROOT = HOME / '.napcat-recovery'
WEB = Path('/data/data/com.termux/files/usr/var/lib/proot-distro/containers/napcat/rootfs/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/webui.json')

def save(path, value):
    tmp = path.with_suffix('.tmp')
    fd = os.open(tmp, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f)
    tmp.replace(path)

def load(path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default

def needs_human(data):
    text = str(data.get('loginError', '')) + str(data.get('message', ''))
    return bool(data.get('needCaptcha') or data.get('needNewDevice') or any(
        x in text for x in ('验证码', '身份验证', '安全验证', '扫码验证', '密码错误', '冻结', '140022008', '140022010', '140022011')))

class API:
    def __init__(self):
        self.auth = None
        self.auth_at = 0

    def raw(self, route, data, authenticated=True):
        headers = {'Content-Type': 'application/json'}
        if authenticated:
            headers['Authorization'] = 'Bearer ' + self.auth
        request = urllib.request.Request('http://127.0.0.1:6099/api' + route,
            data=json.dumps(data).encode(), headers=headers)
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    def call(self, route, data=None):
        if not self.auth or time.time() - self.auth_at > 1800:
            token = load(WEB, {})['token']
            result = self.raw('/auth/login', {'hash': hashlib.sha256((token + '.napcat').encode()).hexdigest()}, False)
            self.auth = result['data']['Credential']
            self.auth_at = time.time()
        result = self.raw(route, data or {})
        if result.get('code') != 0:
            # Never expose raw responses: they may contain account or challenge data.
            self.auth = None
        return result

class Recovery:
    def __init__(self, api, state, settings, password):
        self.api, self.state, self.settings, self.password = api, state, settings, password

    def tick(self, now):
        result = self.api.call('/QQLogin/CheckLoginStatus')
        if result.get('code') != 0:
            raise RuntimeError('status_unavailable')
        d = result['data']
        s = self.state
        s['checked_at'] = now
        if d.get('isLogin') and d.get('coreReady'):
            was_offline = bool(s.get('offline_since'))
            if was_offline:
                s['last_recovery'] = {'at': now, 'offline_since': s['offline_since'], 'quick_attempts': s.get('quick_attempts', 0), 'password_attempts': s.get('password_attempts', 0)}
            s.update(phase='online', offline_since=None, quick_attempts=0, password_attempts=0, manual_required=False)
            return
        s.setdefault('offline_since', now)
        if s['offline_since'] is None:
            s['offline_since'] = now
        if needs_human(d):
            s.update(phase='manual_verification', manual_required=True)
        if s.get('manual_required'):
            return
        s['phase'] = 'waiting_native_recovery'
        if now - s['offline_since'] < 120 or d.get('loginPhase') in ('reconnecting', 'initializing', 'qrcode_scanned'):
            return
        if now - s.get('last_attempt', 0) < 300:
            return
        account = self.settings.get('account')
        if not account:
            s.update(phase='account_not_configured', manual_required=True)
            return
        quick = s.get('quick_attempts', 0)
        if quick < 2:
            # Persist budget BEFORE the action. A timeout may mean it was accepted.
            s.update(quick_attempts=quick + 1, last_attempt=now, phase='quick_login_requested')
            save(ROOT / 'state.json', s)
            response = self.api.call('/QQLogin/SetQuickLogin', {'uin': account})
            if needs_human(response) or needs_human(response.get('data') or {}):
                s.update(phase='manual_verification', manual_required=True)
            return
        if not self.password:
            s.update(phase='waiting_scan_password_not_configured', manual_required=True)
            return
        if s.get('password_attempts', 0) >= 1:
            s.update(phase='waiting_manual_login', manual_required=True)
            return
        s.update(password_attempts=1, last_attempt=now, phase='password_login_requested')
        save(ROOT / 'state.json', s)
        response = self.api.call('/QQLogin/PasswordLogin', {'uin': account, 'passwordMd5': self.password})
        if response.get('code') != 0 or needs_human(response.get('data') or {}):
            s.update(phase='waiting_manual_login', manual_required=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'status', 'resume', 'set-password', 'remove-password'))
    args = parser.parse_args()
    ROOT.mkdir(mode=0o700, exist_ok=True)
    ROOT.chmod(0o700)
    if args.command == 'set-password':
        print('仅在本机输入。保存的是可用于登录的密码摘要，仍属于敏感凭据。')
        password = getpass.getpass('QQ 密码：')
        if not password:
            raise SystemExit('未设置')
        save(ROOT / 'password.json', {'md5': hashlib.md5(password.encode()).hexdigest()})
        print('已保存；恢复器在下一次状态检查时读取。')
        return
    if args.command == 'remove-password':
        (ROOT / 'password.json').unlink(missing_ok=True)
        return
    if args.command == 'status':
        print(json.dumps(load(ROOT / 'state.json', {}), ensure_ascii=False, indent=2))
        return
    if args.command == 'resume':
        # Handled by the daemon under the same lock; never start a second login flow.
        (ROOT / 'resume.request').touch(mode=0o600)
        print('已请求重新检查；不会立即重启或退出 QQ。')
        return
    with (ROOT / 'manager.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('恢复器已在运行')
        state = load(ROOT / 'state.json', {})
        api = API()
        while True:
            if (ROOT / 'resume.request').exists():
                state.update(manual_required=False, quick_attempts=0, password_attempts=0, offline_since=time.time(), last_attempt=time.time())
                (ROOT / 'resume.request').unlink()
            before = state.get('phase')
            try:
                recovery = Recovery(api, state, load(ROOT / 'settings.json', {}), load(ROOT / 'password.json', {}).get('md5'))
                recovery.tick(time.time())
            except Exception:
                api.auth = None
                state.update(phase='webui_unreachable', checked_at=time.time())
                # An unavailable API is not proof of QQ being offline. No restarts.
            save(ROOT / 'state.json', state)
            if before != state.get('phase'):
                with (ROOT / 'events.jsonl').open('a') as f:
                    f.write(json.dumps({'at': time.time(), 'phase': state.get('phase'), 'quick_attempts': state.get('quick_attempts', 0), 'password_attempts': state.get('password_attempts', 0)}) + '\n')
                (ROOT / 'events.jsonl').chmod(0o600)
            time.sleep(30)

if __name__ == '__main__':
    main()
