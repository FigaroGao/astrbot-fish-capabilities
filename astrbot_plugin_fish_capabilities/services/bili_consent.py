import re,secrets,time
from .policy import CapabilityError
from .bilibili import bvid

class Consent:
    def __init__(self,reader):
        self.reader=reader
        with reader.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS group_video_consent(code TEXT PRIMARY KEY,owner TEXT,scope TEXT,bvid TEXT,expires REAL,used INTEGER)')
    def request(self,owner,scope,video):
        video=bvid(video);code=secrets.token_hex(3)
        with self.reader.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM group_video_consent WHERE expires<?',(time.time(),))
            if db.execute('SELECT 1 FROM group_video_consent WHERE owner=? AND scope=? AND bvid=? AND used=0',(owner,scope,video)).fetchone():return None
            if db.execute('SELECT COUNT(*) FROM group_video_consent WHERE owner=? AND scope=?',(owner,scope)).fetchone()[0]>=3:raise CapabilityError('本群最近5分钟已请求3次，先等主人处理。')
            db.execute('INSERT INTO group_video_consent VALUES(?,?,?,?,?,0)',(code,owner,scope,video,time.time()+300))
        return code
    def consume(self,owner,scope,text):
        match=re.search(r'确认看视频\s*([a-f0-9]{6})\b',text)
        if not match:raise CapabilityError('需要主人在当前群发送“确认看视频 六位确认码”。')
        with self.reader.connect() as db:
            db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT bvid FROM group_video_consent WHERE code=? AND owner=? AND scope=? AND expires>? AND used=0',(match[1],owner,scope,time.time())).fetchone()
            if not row:raise CapabilityError('确认码无效、已用过或超过5分钟。')
            db.execute('UPDATE group_video_consent SET used=1 WHERE code=?',(match[1],))
        return row[0]

    def approve(self,owner,scope,video=None):
        if video:video=bvid(video)
        with self.reader.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=db.execute('SELECT code,bvid FROM group_video_consent WHERE owner=? AND scope=? AND expires>? AND used=0',(owner,scope,time.time())).fetchall()
            if video:rows=[row for row in rows if row[1]==video]
            if not rows:raise CapabilityError('当前群没有对应的有效看视频申请，可能已处理或超过5分钟。')
            if len(rows)!=1:raise CapabilityError('有多个视频待确认，请回复对应的询问消息说“看吧”或“同意”。')
            db.execute('UPDATE group_video_consent SET used=1 WHERE code=?',(rows[0][0],))
        return rows[0][1]
