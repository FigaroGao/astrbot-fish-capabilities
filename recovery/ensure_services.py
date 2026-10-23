"""Native Termux recovery supervisor repair. Never controls QQ processes."""
import fcntl,json,os,subprocess,time
from pathlib import Path
HOME=Path('/data/data/com.termux/files/home')
PREFIX=Path('/data/data/com.termux/files/usr')
ROOT=HOME/'.napcat-recovery'
def save(path,data):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data),encoding='utf-8');tmp.chmod(0o600);tmp.replace(path)
def locked(path):
 with path.open('a') as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return True
 return False
def run(name,*args):
 env=dict(os.environ,HOME=str(HOME),PREFIX=str(PREFIX),PATH=str(PREFIX/'bin')+':/system/bin',TMPDIR=str(PREFIX/'tmp'),SVDIR=str(PREFIX/'var/service'),LOGDIR=str(PREFIX/'var/log'))
 env.pop('LD_PRELOAD',None)
 return subprocess.run([str(PREFIX/'bin'/name),*args],env=env,capture_output=True,timeout=12).returncode
def daemon_alive():
 try:
  pid=int((PREFIX/'var/run/service-daemon.pid').read_text())
  if pid<=1:return False
  return 'runsvdir' in Path('/proc',str(pid),'cmdline').read_text(errors='replace')
 except (OSError,ValueError):return False

def ensure():
 ROOT.mkdir(mode=0o700,exist_ok=True)
 with (ROOT/'host-guard.lock').open('a') as guard:
  try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'phase':'another_check_running'}
  now=time.time();state={}
  try:state=json.loads((ROOT/'host-guard-state.json').read_text())
  except (OSError,ValueError):pass
  attempts=[t for t in state.get('attempts',[]) if now-t<3600]
  result={'checked_at':now,'attempts':attempts}
  def finish(phase):
   result['phase']=phase;save(ROOT/'host-guard-state.json',result);return result
  if (ROOT/'host-guard.pause').exists():return finish('paused')
  active=locked(ROOT/'manager.lock')
  try:age=now-(ROOT/'state.json').stat().st_mtime
  except OSError:age=999999
  daemon=daemon_alive()
  if active and age<180 and daemon:return finish('healthy')
  if len(attempts)>=3:return finish('retry_limit')
  if attempts and now-attempts[-1]<180:return finish('cooldown')
  attempts.append(now);result['attempts']=attempts;finish('repair_reserved')
  # Official start is idempotent. Existing down services remain down.
  run('service-daemon','start')
  time.sleep(2)
  service=str(PREFIX/'var/service/fish-recovery')
  if not active:run('sv','up',service)
  elif age>=180:run('sv','restart',service)
  # sv up may report success before Python has obtained its single-instance lock.
  for _ in range(8):
   if locked(ROOT/'manager.lock'):return finish('repair_started')
   time.sleep(1)
  return finish('repair_failed')
if __name__=='__main__':
 try:print(json.dumps(ensure()))
 except Exception as e:
  save(ROOT/'host-guard-error.json',{'at':time.time(),'error_type':type(e).__name__})
  raise SystemExit(1)
