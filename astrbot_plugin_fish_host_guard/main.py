import asyncio,os
from astrbot.api.star import Star
from astrbot.api import logger

class FishHostGuard(Star):
 async def initialize(self):
  self.task=asyncio.create_task(self.loop())
 async def loop(self):
  while True:
   process=None
   try:
    env=dict(os.environ);env.pop('LD_PRELOAD',None)
    process=await asyncio.create_subprocess_exec('/data/data/com.termux/files/usr/bin/python','/data/data/com.termux/files/home/.napcat-recovery/ensure_services.py',stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,env=env)
    await asyncio.wait_for(process.wait(),40)
   except asyncio.CancelledError:raise
   except Exception as exc:logger.warning('Fish host guard check failed: %s',type(exc).__name__)
   finally:
    if process is not None and process.returncode is None:
     process.kill();await process.wait()
   await asyncio.sleep(60)
 async def terminate(self):
  self.task.cancel()
  try:await self.task
  except asyncio.CancelledError:pass
