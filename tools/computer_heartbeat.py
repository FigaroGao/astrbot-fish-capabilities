"""Local PC -> explicitly selected tablet heartbeat. No listener or chat sender."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time


def send_once(config):
    # Only this existing ADB transport is selected. Never connect new addresses.
    serial=config.get('serial');adb=config.get('adb')
    if not isinstance(serial,str) or not serial or not isinstance(adb,str) or not Path(adb).is_file():
        raise ValueError('Explicit ADB executable and device serial required')
    native="""from pathlib import Path
import json,time,os
p=Path('/data/data/com.termux/files/home/AstrBot/data/plugin_data/astrbot_plugin_fish_capabilities/computer-link.json')
if not p.parent.is_dir():raise SystemExit(2)
if p.parent.is_dir():
 t=p.with_suffix('.heartbeat-tmp')
 t.write_text(json.dumps({'source':'local-computer-adb','at':time.time()}),encoding='utf-8')
 t.chmod(0o600)
 t.replace(p)
"""
    result=subprocess.run([adb,'-s',serial,'shell','-T','run-as','com.termux',
                           '/data/data/com.termux/files/usr/bin/python','-'],
                          input=native,text=True,encoding='utf-8',capture_output=True,timeout=15,
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return result.returncode==0


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    config=json.loads(args.config.read_text(encoding='utf-8-sig'))
    if args.once:
        return 0 if send_once(config) else 1
    # One worker per configuration, including user-startup and manual launches.
    lock=args.config.with_suffix('.lock').open('a+b')
    if os.name=='nt':
        import msvcrt
        lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return 0
    else:
        import fcntl
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:return 0
    while True:
        if args.config.with_suffix('.pause').exists():
            time.sleep(60);continue
        ok=False
        try:ok=send_once(config)
        except (OSError,ValueError,subprocess.TimeoutExpired):pass
        status={'at':time.time(),'last_attempt_ok':ok,'meaning':'device transport only; no reader notification'}
        path=args.config.with_suffix('.status.json');tmp=path.with_suffix('.tmp')
        tmp.write_text(json.dumps(status),encoding='utf-8');tmp.replace(path)
        time.sleep(60)


if __name__=='__main__':
    raise SystemExit(main())
