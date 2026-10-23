"""Install only the recovery manager in native Termux; never restart QQ."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    prefix = Path('/data/data/com.termux/files/usr')
    home = Path('/data/data/com.termux/files/home')
    if Path(sys.prefix).resolve() != prefix.resolve():
        raise SystemExit('Run with native Termux Python, outside Ubuntu/proot.')
    if not (prefix/'bin/sv').is_file():
        raise SystemExit('Install termux-services first: pkg install termux-services')
    account = input('QQ account / QQ号: ').strip()
    if not account.isdigit() or not 5 <= len(account) <= 12:
        raise SystemExit('Invalid QQ account.')
    root = home/'.napcat-recovery'
    service = prefix/'var/service/fish-recovery'
    if service.exists():
        raise SystemExit('Existing service: back it up and review manually; installer will not overwrite it.')
    os.umask(0o077)
    root.mkdir(mode=0o700,exist_ok=True)
    root.chmod(0o700)
    source = Path(__file__).resolve().parent
    manager = (source/'napcat_recovery.py').read_text(encoding='utf-8')
    # Check the default path before installing a manager that cannot reach NapCat.
    import ast
    web = None
    for node in ast.walk(ast.parse(manager)):
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='WEB' for t in node.targets):
            web = Path(ast.literal_eval(node.value.args[0]))
    if web is None or not web.is_file():
        raise SystemExit('NapCat webui.json not found. Adapt WEB in napcat_recovery.py first.')
    for src,dest in [('napcat_recovery.py','manager.py'),('ensure_services.py','ensure_services.py')]:
        target=root/dest
        if target.exists():
            raise SystemExit('Existing recovery files: review manually before upgrading.')
    for src,dest in [('napcat_recovery.py','manager.py'),('ensure_services.py','ensure_services.py')]:
        shutil.copyfile(source/src,root/dest)
        (root/dest).chmod(0o600)
    settings=root/'settings.json'
    settings.write_text(json.dumps({'account':account})+'\n',encoding='utf-8')
    settings.chmod(0o600)
    service.mkdir(parents=True,mode=0o700)
    (service/'log').mkdir(mode=0o700)
    logdir=prefix/'var/log/sv/fish-recovery'
    logdir.mkdir(parents=True,mode=0o700,exist_ok=True)
    scripts={
        service/'run':f'#!{prefix}/bin/sh\numask 077\nexport HOME={home}\nexport PREFIX={prefix}\nexport PATH={prefix}/bin:/system/bin\nunset LD_PRELOAD\nexec 2>&1\nexec {prefix}/bin/python {root}/manager.py run\n',
        service/'finish':f'#!{prefix}/bin/sh\numask 077\nprintf "%s exit=%s signal=%s\\n" "$(date -Iseconds)" "$1" "$2" >> {root}/service-exits.log\nsleep 5\n',
        service/'log/run':f'#!{prefix}/bin/sh\numask 077\nexec {prefix}/bin/svlogd -tt {logdir}\n',
    }
    for path,content in scripts.items():
        path.write_text(content,encoding='utf-8')
        path.chmod(0o700)
    subprocess.run([str(prefix/'bin/service-daemon'),'start'],check=True)
    subprocess.run([str(prefix/'bin/sv'),'up',str(service)],check=True)
    print('Installed fish-recovery. QQ was not restarted. Check manager.py status locally.')


if __name__=='__main__':
    main()
