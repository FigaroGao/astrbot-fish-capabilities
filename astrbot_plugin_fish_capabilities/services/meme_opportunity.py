"""Local optional image candidates; never selects or sends on the model's behalf."""
import json
import re
import time
from .tone_diagnostics import scene_for

SCENES=(('goodnight',r'晚安|睡啦|睡了|准备睡'),('comfort',r'累|委屈|难过|抱抱|摸摸|呜呜'),
        ('happy',r'哈哈|笑死|好耶|开心|高兴|太好笑|乐了'),('tease',r'摸鱼|嘴硬|笨鱼|偷懒'),
        ('greeting',r'早安|早上好|中午好|晚上好|你在吗'),('acknowledge',r'谢谢|辛苦啦|收到|好哒'))

def opportunity(cap,scope,text,*,requested=False,now=None):
    if not isinstance(text,str) or not text.strip() or len(text)>600:return None
    if re.search(r'别发.{0,3}(图|表情)|不要.{0,3}(图|表情)|不用.{0,3}(图|表情)',text):return None
    if not requested and (scene_for(text) in ('steps','explain','compare','data') or re.search(r'自杀|去世|病危|葬礼',text)):return None
    categories=[name for name,pattern in SCENES if re.search(pattern,text)]
    if not categories and not requested:return None
    now=time.time() if now is None else now
    with cap.ledger.connect() as db:
        used=db.execute('SELECT COUNT(*) FROM reservations WHERE scope=? AND stamp>?',(scope,now-3600)).fetchone()[0]
        last=db.execute('SELECT MAX(stamp) FROM reservations WHERE scope=?',(scope,)).fetchone()[0]
        if used>=int(cap.config.get('media_hourly_limit',6)):return None
        if not requested and last is not None and now-last<int(cap.config.get('media_cooldown_seconds',180)):return None
        gap=int(cap.config.get('meme_min_reply_gap',3))
        if gap>0 and not requested:
            last_image=db.execute("SELECT MAX(stamp) FROM reservations WHERE scope=? AND kind='image'",(scope,)).fetchone()[0]
            if last_image is not None and db.execute('SELECT COUNT(*) FROM reply_turns WHERE scope=? AND stamp>=?',(scope,last_image)).fetchone()[0]<gap:return None
    excluded=cap.ledger.recent_assets(scope)
    memes=[m for m in cap.memes.catalog() if m.sha256 not in excluded and (not categories or m.category in categories)]
    if not memes:return None
    memes.sort(key=lambda m:(categories.index(m.category) if m.category in categories else 99,m.id))
    # Rotate deterministically among matching, reviewed descriptions; no random
    # send probability and no extra embedding/vision/model request.
    start=int(now//300)%len(memes);pool=memes[start:]+memes[:start]
    chosen=pool[:3]
    payload=[{'id':m.id,'category':m.category,'meaning':m.description[:80],'image_text':m.image_text[:70],'use_when':m.usage_notes[:70]} for m in chosen]
    return '[当前为已核验主人私聊；本轮可选图库表情，不是发送要求]\n'+json.dumps(payload,ensure_ascii=False)+'\n调用表情工具也是一种聊天表达，不是必须等主人布置的任务；可以一张图回应，或配一句短话。若其中一张更适合这次情绪，可以自行用fish_meme(category,meme_id)选一张，不用等主人索要，也不用先查一遍目录；它们已来自审核图库。也可不发。图片表情不同于装饰性的emoji/颜文字，不要求凑满次数；别连续机械配图，不拿表情代替认真倾听。仍由原发送链检查一轮一张、每小时上限及重复限制。仅是文字候选，不代表已经发图。'
