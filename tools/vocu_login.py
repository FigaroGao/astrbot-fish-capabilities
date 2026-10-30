"""Local hidden API-key input. No remote synthesis or spending during setup."""
from pathlib import Path
import getpass,json,os,re,shutil
BASE=Path(os.environ.get('ASTRBOT_ROOT','/data/data/com.termux/files/home/AstrBot'))
def private_write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
    tmp.chmod(0o600);tmp.replace(path)
def main():
    try:
        root=BASE/'data/plugin_data/astrbot_plugin_fish_capabilities'
        settings=json.loads((root/'vocu-setup.private.json').read_text(encoding='utf-8'))
        if not re.fullmatch(r'(?:market:)?[a-fA-F0-9-]{36}',settings['voice_id']) or not 0.5<=settings['speed']<=2:raise ValueError('settings')
        if not shutil.which('ffmpeg') and not Path('/data/data/com.termux/files/usr/bin/ffmpeg').is_file():raise ValueError('ffmpeg')
        key=getpass.getpass('Vocu API Key（输入隐藏，粘贴后回车）：').strip()
        if not 10<=len(key)<=2048 or any(c.isspace() for c in key):raise ValueError('key')
        private_write(root/'vocu.credentials.json',dict(api_key=key,voice_id=settings['voice_id'],speed=settings['speed']))
        cp=BASE/'data/config/astrbot_plugin_fish_capabilities_config.json'
        cfg=json.loads(cp.read_text(encoding='utf-8-sig'));cfg.update(tts_provider='vocu',tts_enabled=True)
        private_write(cp,cfg)
        print('密钥已保存在本机。请重载小鲸能力插件；可私聊说“用语音说一句你好”。本次未调用付费合成；首次生成还需验证账号、音色权限与QQ发送。')
    except (KeyboardInterrupt,EOFError):print('已取消。')
    except Exception:print('设置未完成，请检查预设文件、ffmpeg及密钥格式；没有输出敏感错误。')
if __name__=='__main__':main()
