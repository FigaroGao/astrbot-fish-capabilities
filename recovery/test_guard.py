import importlib.util,sys,types,unittest,tempfile,time,json
from pathlib import Path
from unittest.mock import patch
if sys.platform=='win32':sys.modules['fcntl']=types.SimpleNamespace(LOCK_EX=1,LOCK_NB=2,flock=lambda *a:None)
spec=importlib.util.spec_from_file_location('host_guard',Path(__file__).with_name('ensure_services.py'));g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.active=False;self.daemon=False;self.calls=[]
  self.patches=[patch.object(g,'ROOT',self.root),patch.object(g,'locked',side_effect=lambda p:self.active),patch.object(g,'daemon_alive',side_effect=lambda:self.daemon),patch.object(g,'run',side_effect=self.run_command),patch.object(g.time,'sleep')]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def run_command(self,*args):
  self.calls.append(args)
  if args[0]=='service-daemon':self.daemon=True
  else:self.active=True
  return 0
 def test_missing_both(self):
  self.assertEqual(g.ensure()['phase'],'repair_started');self.assertEqual([c[:2] for c in self.calls],[('service-daemon','start'),('sv','up')])
 def test_healthy(self):
  self.active=self.daemon=True;(self.root/'state.json').touch();self.assertEqual(g.ensure()['phase'],'healthy');self.assertFalse(self.calls)
 def test_manager_alive_daemon_missing(self):
  self.active=True;(self.root/'state.json').touch();self.assertEqual(g.ensure()['phase'],'repair_started');self.assertEqual(self.calls,[('service-daemon','start')])
 def test_stale_manager(self):
  self.active=self.daemon=True;self.assertEqual(g.ensure()['phase'],'repair_started');self.assertEqual(self.calls[-1][1],'restart')
 def test_pause(self):
  (self.root/'host-guard.pause').touch();self.assertEqual(g.ensure()['phase'],'paused');self.assertFalse(self.calls)
 def test_cooldown_and_budget(self):
  g.save(self.root/'host-guard-state.json',{'attempts':[time.time()]});self.assertEqual(g.ensure()['phase'],'cooldown')
  g.save(self.root/'host-guard-state.json',{'attempts':[time.time()-500,time.time()-400,time.time()-300]});self.assertEqual(g.ensure()['phase'],'retry_limit');self.assertFalse(self.calls)
if __name__=='__main__':unittest.main()
