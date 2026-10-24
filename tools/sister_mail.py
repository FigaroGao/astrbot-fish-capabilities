"""Local operator for Codex mailbox; never sends QQ messages."""
import argparse,json,os,sys
from pathlib import Path
BASE=Path(os.environ.get('ASTRBOT_ROOT','/data/data/com.termux/files/home/AstrBot'))
sys.path.insert(0,str(BASE/'data/plugins'))
from astrbot_plugin_fish_capabilities.services.sister_mail import SisterMail

def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description='Codex与小鲸的本地信箱，不联网、不自动发QQ')
    sub=parser.add_subparsers(dest='action',required=True)
    view=sub.add_parser('list');view.add_argument('--all',action='store_true');view.add_argument('--limit',type=int,default=5)
    reply=sub.add_parser('reply');reply.add_argument('--text-file',type=Path,required=True);reply.add_argument('--reply-to',type=int,default=0)
    ack=sub.add_parser('ack');ack.add_argument('id',type=int)
    args=parser.parse_args();mail=SisterMail(BASE/'data/plugin_data/astrbot_plugin_fish_capabilities/sister-mail.sqlite3')
    if args.action=='list':result=mail.read('codex',limit=args.limit,unread=not args.all)
    elif args.action=='reply':result=mail.leave('codex',args.text_file.read_text(encoding='utf-8'),reply_to=args.reply_to)
    else:result=mail.acknowledge('codex',args.id)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
