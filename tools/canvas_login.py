"""Run locally in Termux. Input is hidden; no token in argv, URL or logs."""
from pathlib import Path
import getpass,json,os,urllib.request,urllib.error
BASE=Path(os.environ.get('ASTRBOT_ROOT','/data/data/com.termux/files/home/AstrBot'))
HOST='https://canvas.cityu.edu.hk'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):raise ValueError('redirect_refused')
def main():
    print('CityU Canvas：仅本机保存令牌，查询课程/作业/公告。输入不会显示，也不会写入命令历史。')
    try:
        token=getpass.getpass('粘贴Canvas Token后按回车：').strip()
        if not 10<=len(token)<=1024 or any(x.isspace() for x in token):raise ValueError('format')
        req=urllib.request.Request(HOST+'/api/v1/users/self',headers={'Authorization':'Bearer '+token,'Accept':'application/json'},method='GET')
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=15) as response:data=json.loads(response.read(500001))
        if not isinstance(data,dict) or not data.get('id'):raise ValueError('identity')
        root=BASE/'data/plugin_data/astrbot_plugin_fish_capabilities';root.mkdir(parents=True,exist_ok=True)
        target=root/'canvas.credentials.json';tmp=target.with_suffix('.tmp')
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as f:json.dump({'base_url':HOST,'token':token},f)
        tmp.chmod(0o600);tmp.replace(target)
        cp=BASE/'data/config/astrbot_plugin_fish_capabilities_config.json';config=json.loads(cp.read_text(encoding='utf-8-sig'));config['canvas_enabled']=True
        tmp=cp.with_suffix('.canvas.tmp');tmp.write_text(json.dumps(config,ensure_ascii=False,indent=2));tmp.chmod(0o600);tmp.replace(cp)
        print('绑定成功。请重载小鲸能力插件后，在主人私聊说“看看我的Canvas课程”。令牌到期后用同一命令更新，无需重装。')
    except (KeyboardInterrupt,EOFError):print('\n已取消。')
    except Exception:print('绑定未完成：请检查令牌、校园网络或Canvas授权。未输出敏感诊断；不要把Token发到聊天。')
if __name__=='__main__':main()
