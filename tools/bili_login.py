"""Run locally inside the AstrBot Ubuntu environment; never via an LLM tool."""
import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
import time
import io
import math
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE=Path(os.environ.get('ASTRBOT_ROOT','/data/data/com.termux/files/home/AstrBot'))
DATA=BASE/'data/plugin_data/astrbot_plugin_fish_capabilities'
CONFIG=BASE/'data/config/astrbot_plugin_fish_capabilities_config.json'
STAGE='starting'

def write_private(path,data):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    temp.replace(path)

def reload_plugin():
    print('凭据已保存；请在 AstrBot WebUI 手动重载能力插件。')


def compact_qr(png):
    from PIL import Image
    image=Image.open(io.BytesIO(png)).convert('L')
    if image.width!=image.height or image.width>2000:raise ValueError('Invalid QR image')
    scale=0
    for y in range(image.height):
        previous=image.getpixel((0,y))<128;length=0
        for x in range(image.width):
            black=image.getpixel((x,y))<128
            if black==previous:length+=1
            else:scale=math.gcd(scale,length);previous=black;length=1
        scale=math.gcd(scale,length)
    scale=max(1,scale);size=image.width//scale
    matrix=[[image.getpixel((x*scale+scale//2,y*scale+scale//2))<128 for x in range(size)] for y in range(size)]
    lines=[]
    glyphs={(False,False):' ',(True,False):'▀',(False,True):'▄',(True,True):'█'}
    for y in range(0,size,2):
        lines.append('\x1b[30;107m'+''.join(glyphs[(matrix[y][x],matrix[y+1][x] if y+1<size else False)] for x in range(size))+'\x1b[0m')
    return '\n'.join(lines),size,len(lines)

def qr_viewer(png):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/qr.png':body=png;content='image/png'
            elif self.path=='/':
                body=b'<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bilibili login QR</title><body style="margin:0;min-height:100vh;display:grid;place-items:center;background:white"><img src="/qr.png" style="width:min(86vw,86vh,600px);height:auto;image-rendering:pixelated" alt="Bilibili login QR"></body>';content='text/html; charset=utf-8'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',content);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server

def verify_saved_account(values):
    import sys
    sys.path.insert(0,str(BASE/'data/plugins'))
    from astrbot_plugin_fish_capabilities.services.bili_account import verify_account
    return verify_account(values)

async def login(enable_comments,image_only=False):
    global STAGE
    import sys
    import qrcode
    sys.path.insert(0,str(BASE/'data/plugins'))
    from astrbot_plugin_fish_capabilities.services.bili_qr import WebQR
    web=WebQR()
    pending=DATA/'bilibili.login-pending.json'
    values=json.loads(pending.read_text()) if pending.exists() else {}
    if values and not values.get('sessdata') and not values.get('exchange_url'):
        pending.rename(pending.with_name('bilibili.empty-pending-'+str(int(time.time()))+'.json'))
        print('旧版只留下了空Cookie，已移作私有备份；需要重新扫码一次。',flush=True)
        values={}
    if not values:
        STAGE='generate_qr'
        generated=await asyncio.to_thread(web.generate)
        image=qrcode.make(generated['url']);buffer=io.BytesIO();image.save(buffer,format='PNG');png=buffer.getvalue()
        server=qr_viewer(png)
        print('用准备给小鲸使用的B站账号扫码并在手机确认。',flush=True)
        print('图片版：在平板浏览器打开 http://127.0.0.1:'+str(server.server_port)+'/',flush=True)
        if not image_only:
            rendered,width,height=compact_qr(png)
            columns,rows=shutil.get_terminal_size((80,40))
            if width<columns and height+5<rows:print(rendered,flush=True)
            else:print('终端空间不足，请打开图片版。',flush=True)
        deadline=time.monotonic()+180
        STAGE='receive_scan_confirmation'
        while time.monotonic()<deadline:
            event=await asyncio.to_thread(web.poll,generated['qrcode_key'])
            code=event.get('code')
            if code==0:
                values=web.values({'exchange_url':event.get('url',''),'ac_time_value':event.get('refresh_token','')})
                write_private(pending,values)
                break
            if code==86038:raise RuntimeError('qr_expired')
            if code not in (86101,86090):raise RuntimeError('unknown_qr_status')
            if code==86090:print('已扫码，请在手机确认登录。',flush=True)
            await asyncio.sleep(2)
        else:raise RuntimeError('qr_wait_timeout')
    STAGE='exchange_login_ticket'
    print('正在接收登录Cookie……',flush=True)
    try:values=await asyncio.to_thread(web.exchange,values)
    finally:write_private(pending,web.values(values))
    STAGE='verify_account'
    print('已收到登录凭据，正在核对账号。',flush=True)
    info=await asyncio.to_thread(verify_saved_account,values)
    return complete_login(values,info,enable_comments,pending)

def complete_login(values,info,enable_comments,pending):
    global STAGE
    STAGE='local_account_confirmation'
    account=str(info['mid'])
    print('将绑定 B站账号：'+str(info.get('name',''))+'，UID '+account)
    if input('确认使用这个账号？输入 yes：').strip().lower()!='yes':
        print('未保存，也未启用评论。');return
    write_private(DATA/'bilibili.credentials.json',values)
    STAGE='save_account_binding'
    config=json.loads(CONFIG.read_text(encoding='utf-8-sig'))
    config.update(bili_enabled=True,bili_account_id=account,bili_comment_enabled=bool(enable_comments))
    write_private(CONFIG,config)
    pending.unlink(missing_ok=True)
    print('账号已保存至私有目录；评论'+('已启用，最多2条/24小时。' if enable_comments else '未启用。'))
    reload_plugin()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--enable-comments',action='store_true',help='绑定扫码账号后授权小鲸自行公开评论')
    parser.add_argument('--image',action='store_true',help='只显示图片版地址，适合终端屏幕较小的情况')
    args=parser.parse_args()
    os.umask(0o077)
    try:asyncio.run(login(args.enable_comments,args.image))
    except Exception as e:
        record={'at':time.time(),'stage':STAGE,'error_type':type(e).__name__}
        code=getattr(e,'code',None)
        if type(code) is int:record['http_or_api_code']=code
        write_private(DATA/'bili-login-diagnostic.json',record)
        pending=(DATA/'bilibili.login-pending.json').exists()
        print(('扫码凭据已保留，但账号核对/保存还未完成：' if pending else '接收扫码登录还未完成：')+type(e).__name__+'。')
        print('请重新执行同一命令；已暂存凭据时会继续核对，不要求重新扫码。' if pending else '尚未收到可保存的凭据，请保留错误类型供排查。')
        print('失败阶段：'+STAGE)

if __name__=='__main__':main()
