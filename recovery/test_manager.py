"""Isolated state-machine tests. No QQ, network, credentials, or process signals."""
import importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
if sys.platform=='win32':sys.modules['fcntl']=types.SimpleNamespace(LOCK_EX=1,LOCK_NB=2,flock=lambda *a:None)
spec=importlib.util.spec_from_file_location('manager_under_test',Path(__file__).with_name('napcat_recovery.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class API:
 def __init__(self):self.data={'isLogin':False,'coreReady':False,'loginPhase':'idle'};self.calls=[];self.fail=False;self.login_result={'code':0,'data':{}};self.status_code=0
 def call(self,route,data=None):
  self.calls.append((route,data))
  if route.endswith('CheckLoginStatus'):return {'code':self.status_code,'data':self.data}
  if self.fail:raise TimeoutError('synthetic timeout')
  return self.login_result

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.patch=patch.object(m,'ROOT',self.root);self.patch.start()
  self.api=API();self.state={'offline_since':1000};self.settings={'account':'12345'}
 def tearDown(self):self.patch.stop();self.temp.cleanup()
 def recovery(self,password=None):return m.Recovery(self.api,self.state,self.settings,password)
 def actions(self):return [r for r,d in self.api.calls if not r.endswith('CheckLoginStatus')]
 def test_online_clears_current_round(self):
  self.state.update(quick_attempts=2,password_attempts=1,manual_required=True);self.api.data={'isLogin':True,'coreReady':True}
  self.recovery().tick(2000)
  self.assertEqual(self.state['phase'],'online');self.assertEqual(self.state['quick_attempts'],0);self.assertFalse(self.state['manual_required']);self.assertEqual(self.actions(),[])
 def test_initial_wait(self):
  self.recovery().tick(1119);self.assertEqual(self.state['phase'],'waiting_native_recovery');self.assertEqual(self.actions(),[])
 def test_ready_is_required(self):
  self.api.data={'isLogin':True,'coreReady':False,'loginPhase':'initializing'};self.recovery().tick(5000)
  self.assertNotEqual(self.state['phase'],'online');self.assertEqual(self.actions(),[])
 def test_native_in_progress_is_not_competed_with(self):
  for phase in ['reconnecting','initializing','qrcode_scanned']:
   self.api.data['loginPhase']=phase;self.recovery().tick(5000)
  self.assertEqual(self.actions(),[])
 def test_two_quick_one_password_then_manual(self):
  r=self.recovery('synthetic-digest')
  for now in [1120,1420,1720,2020]:r.tick(now)
  self.assertEqual(self.actions(),['/QQLogin/SetQuickLogin','/QQLogin/SetQuickLogin','/QQLogin/PasswordLogin'])
  self.assertEqual(self.state['phase'],'waiting_manual_login');self.assertTrue(self.state['manual_required'])
 def test_without_password_wait_for_scan(self):
  self.state.update(quick_attempts=2);self.recovery().tick(2000)
  self.assertEqual(self.state['phase'],'waiting_scan_password_not_configured');self.assertEqual(self.actions(),[])
 def test_timeout_reserves_attempt_before_action_and_survives_restart(self):
  self.api.fail=True
  with self.assertRaises(TimeoutError):self.recovery().tick(1120)
  stored=json.loads((self.root/'state.json').read_text());self.assertEqual(stored['quick_attempts'],1)
  self.state=stored;self.api.fail=False;self.api.calls=[];self.recovery().tick(1121)
  self.assertEqual(self.actions(),[]);self.recovery().tick(1420);self.assertEqual(self.state['quick_attempts'],2)
 def test_human_verification_stops_before_login(self):
  for signal in [{'needCaptcha':True},{'needNewDevice':True},{'message':'安全验证'},{'loginError':'密码错误'}]:
   self.state={'offline_since':1000};self.api.data=signal;self.recovery('synthetic-digest').tick(2000)
   self.assertTrue(self.state['manual_required'])
  self.assertEqual(self.actions(),[])
 def test_challenge_on_quick_response_stops_later_attempts(self):
  self.api.login_result={'code':0,'data':{'needCaptcha':True}}
  r=self.recovery();r.tick(1120);r.tick(2000)
  self.assertEqual(len(self.actions()),1);self.assertTrue(self.state['manual_required'])
 def test_unreachable_status_does_not_login(self):
  self.api.status_code=500
  with self.assertRaises(RuntimeError):self.recovery().tick(2000)
  self.assertEqual(self.actions(),[])
 def test_missing_account_stops(self):
  self.settings={};self.recovery().tick(2000)
  self.assertEqual(self.state['phase'],'account_not_configured');self.assertEqual(self.actions(),[])
 def test_cooldown_before_next_quick_request(self):
  r=self.recovery();r.tick(1120);r.tick(1419)
  self.assertEqual(len(self.actions()),1)

if __name__=='__main__':unittest.main()
