"""Local-only mainland VALORANT WeChat binding. No passwords or chat credentials.

Flow adapted from GuJi08233/astrbot_plugin_val_shop (AGPL-3.0).
Run inside the Python environment running AstrBot, not native Android Python.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE=Path(os.environ.get('ASTRBOT_ROOT','/data/data/com.termux/files/home/AstrBot'))
ROOT=BASE/'data/plugin_data/astrbot_plugin_fish_capabilities'
sys.path.insert(0,str(BASE/'data/plugins'))


def viewer(image):
    key=secrets.token_urlsafe(24)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/'+key+'/qr.png':body=image;content='image/png' if image.startswith(b'\x89PNG') else 'image/jpeg'
            elif self.path=='/'+key+'/':
                body=b'<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>VALORANT WeChat login</title><body style="background:white;text-align:center;font:18px sans-serif"><p>WeChat / \xe5\xbe\xae\xe4\xbf\xa1: \xe6\x8e\x8c\xe4\xb8\x8a\xe6\x97\xa0\xe7\x95\x8f\xe5\xa5\x91\xe7\xba\xa6</p><img src="qr.png" style="width:min(82vw,72vh,500px);height:auto"></body>';content='text/html; charset=utf-8'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',content)
            self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server,'http://127.0.0.1:'+str(server.server_port)+'/'+key+'/'


async def login():
    from astrbot_plugin_fish_capabilities.services.valorant import WeChatLogin,ValorantRecords,private_save
    flow=WeChatLogin();pending=ROOT/'valorant-wechat.pending.json';server=None
    stage='load_pending';started=time.monotonic();last=None
    try:
        creds=json.loads(pending.read_text(encoding='utf-8')) if pending.exists() else None
        if not creds:
            stage='generate_qr'
            qr=await flow.generate();server,url=viewer(qr['image'])
            print('请在这台平板的浏览器打开下方本地地址，用绑定国服无畏契约的微信扫码确认：',flush=True)
            print(url,flush=True)
            print('二维码较快过期；本轮最多等待180秒。显示过期后重新运行命令。',flush=True)
            deadline=time.monotonic()+180;stage='wait_scan';waiting_notice=False
            while time.monotonic()<deadline:
                try:status=await asyncio.wait_for(flow.poll(qr['uuid'],last),max(.1,deadline-time.monotonic()))
                except TimeoutError:
                    stage='qr_timeout';raise RuntimeError('qr_timeout') from None
                code=status.get('wx_errcode');last=code
                if status.get('local_wait_timeout') and not waiting_notice:
                    print('微信正在等待扫码，继续保持二维码页面打开；一次等待超时不会终止登录。',flush=True);waiting_notice=True
                if code==404:print('微信已扫码，请在手机上确认授权。',flush=True)
                if code in (0,405) and status.get('wx_code'):
                    stage='exchange_authorization'
                    creds=await flow.exchange(status['wx_code']);private_save(pending,creds);break
                if code not in (0,404,408):
                    stage='qr_expired_or_cancelled';raise RuntimeError('qr_expired_or_cancelled')
                await asyncio.sleep(2)
            else:
                stage='qr_timeout';raise RuntimeError('qr_timeout')
        stage='verify_role'
        role=await ValorantRecords(ROOT/'valorant-wechat.credentials.json').role(creds)
        print('已核验掌瓦角色：'+str(role.get('role_name') or '未提供名称'))
        stage='confirm_role'
        if input('确认这是你的角色？输入 yes 才保存绑定：').strip().lower()!='yes':
            pending.unlink(missing_ok=True);print('未绑定。');return
        stage='save_binding'
        private_save(ROOT/'valorant-wechat.credentials.json',creds)
        path=BASE/'data/config/astrbot_plugin_fish_capabilities_config.json'
        config=json.loads(path.read_text(encoding='utf-8-sig'));config['valorant_enabled']=True;private_save(path,config)
        pending.unlink(missing_ok=True)
        print('已绑定。请在AstrBot WebUI重载大肥鱼能力插件，再在主人私聊让她查最近3局。')
        print('角色核验不等于战绩接口已通过；首次读取会单独检查。')
    except Exception as exc:
        private_save(ROOT/'valorant-login-diagnostic.json',{'at':time.time(),'error_type':type(exc).__name__,'pending_saved':pending.exists(),'stage':stage,'elapsed_seconds':round(time.monotonic()-started,1),'last_scan_status':last if type(last) is int else None})
        labels={'load_pending':'加载本机待验证绑定','generate_qr':'生成微信二维码','wait_scan':'等待微信扫码结果','exchange_authorization':'换取掌瓦授权','verify_role':'核验游戏角色','confirm_role':'确认角色','save_binding':'保存绑定','qr_expired_or_cancelled':'二维码已过期或被取消','qr_timeout':'本轮扫码等待结束'}
        print('本轮未完成绑定，阶段：'+labels.get(stage,stage)+'；错误类型：'+type(exc).__name__+'。')
        print('诊断不包含授权码或凭据。二维码过期可重新运行 fish-val-login。')
        if pending.exists():print('已暂存扫码凭据，下次运行先继续角色核验；不要公开这个目录。')
        raise SystemExit(1)
    finally:
        if server:server.shutdown();server.server_close()


if __name__=='__main__':
    os.umask(0o077)
    parser=argparse.ArgumentParser(description='本机微信扫码绑定国服无畏契约');parser.parse_args()
    asyncio.run(login())
