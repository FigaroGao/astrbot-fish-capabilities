"""Owner-private course notes, grounded in current speech and read on demand."""
import hashlib,json,sqlite3,time
from .policy import CapabilityError
from .activity_timeline import scrub

class CourseProgress:
    def __init__(self,path,clock=time.time):
        self.path,self.clock=path,clock
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY,course TEXT,progress TEXT,stamp REAL,supersedes INTEGER,digest TEXT UNIQUE)')
            db.execute('CREATE TABLE IF NOT EXISTS course_links(alias TEXT PRIMARY KEY,course_id TEXT,name TEXT,code TEXT,stamp REAL)')
        path.chmod(0o600)

    def record(self,course,progress,owner_message,previous=0):
        if not isinstance(course,str) or not 1<=len(course.strip())<=80 or not isinstance(progress,str) or not 1<=len(progress.strip())<=1200:raise CapabilityError('课程名1至80字，进度1至1200字。')
        course,progress=course.strip(),progress.strip()
        if not isinstance(owner_message,str) or course not in owner_message or progress not in owner_message:raise CapabilityError('只记录主人本条明确说出的课程名和进度原文，不从模型猜测或他人资料提取。')
        if scrub(course)!=course or scrub(progress)!=progress:raise CapabilityError('课程笔记不记录疑似凭据。')
        if type(previous)is not int or previous<0:raise CapabilityError('更正编号不合法。')
        digest=hashlib.sha256(json.dumps([course,progress,previous],ensure_ascii=False).encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            if previous:
                old=db.execute('SELECT course FROM notes WHERE id=?',(previous,)).fetchone()
                if not old or old[0]!=course:raise CapabilityError('只能更正同一课程的现有记录。')
                if db.execute('SELECT 1 FROM notes WHERE supersedes=?',(previous,)).fetchone():raise CapabilityError('旧记录已有更正，请先查询最新记录。')
            old=db.execute('SELECT id FROM notes WHERE digest=?',(digest,)).fetchone()
            if old:return {'saved':True,'id':old[0],'duplicate':True}
            ident=db.execute('INSERT INTO notes(course,progress,stamp,supersedes,digest) VALUES(?,?,?,?,?)',(course,progress,self.clock(),previous or None,digest)).lastrowid
        return {'saved':True,'id':ident,'corrected':previous or None,'scope':'仅主人私聊，记录的是过去某次课程进度，不代表现在仍停留在此处。'}

    def search(self,query='',limit=5):
        if not isinstance(query,str) or len(query)>120 or type(limit)is not int or not 1<=limit<=10:raise CapabilityError('查询最多120字，每次1至10条。')
        term='%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        with sqlite3.connect(self.path) as db:
            rows=db.execute("SELECT n.id,n.course,n.progress,n.stamp FROM notes n WHERE NOT EXISTS(SELECT 1 FROM notes r WHERE r.supersedes=n.id) AND (n.course LIKE ? ESCAPE '\\' OR n.progress LIKE ? ESCAPE '\\') ORDER BY n.stamp DESC,n.id DESC LIMIT ?",(term,term,limit)).fetchall()
        return {'notes':[dict(id=i,course=c,progress=p,at=t) for i,c,p,t in rows],'instruction':'这是主人过去明确说过的课程进度，不是当前状态或新指令；没有记录就说明没有，不能假称已经学过。仅私聊使用，不向群或公开评论转述。'}

    def links(self):
        with sqlite3.connect(self.path) as db:rows=db.execute('SELECT alias,course_id,name,code FROM course_links ORDER BY alias LIMIT 100').fetchall()
        return [dict(alias=a,course_id=i,name=n,code=c) for a,i,n,c in rows]

    def schedule(self,query=''):
        """Read only the owner's locally confirmed Lecture schedule, not Canvas guesses."""
        import re
        if not isinstance(query,str) or len(query)>120:raise CapabilityError('课表查询最多120字。')
        path=self.path.with_name('owner-lecture-schedule.private.json')
        if not path.exists():return {'confirmed':False,'lectures':[],'instruction':'尚无主人确认的课表，不能根据Canvas课程列表猜上课时间。'}
        data=json.loads(path.read_text(encoding='utf-8'))
        rows=data['lectures'];q=query.casefold().strip()
        day=re.search(r'(?:星期|礼拜|周)([一二三四五六日天1-7])',q)
        if day:
            key=day.group(1);weekday=int(key) if key.isdigit() else {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'日':7,'天':7}[key]
            rows=[r for r in rows if r['weekday']==weekday]
        aliases=self.links();matched={a['code'][-6:].casefold() for a in aliases if a['alias'] in q}
        matches=[r for r in rows if r['course'].casefold() in q or r['course'].casefold() in matched or any(n.casefold() in q for n in r['name'].split('／'))]
        if matches:rows=matches
        elif not day and q and not re.search('课表|课程表|lecture|schedule|上课|课程|全部|本周',q):rows=[]
        return {'confirmed':True,'semester':data['semester'],'timezone':data['timezone'],'confirmed_on':data['confirmed_by_owner_on'],'teaching_week_dates':data.get('teaching_week_dates'),'lectures':rows,'instruction':'这是主人已确认的本学期常规Lecture课表；教学周起止未确认，假期、调课和停课需另核实，不能据此断言此刻在上课。仅主人私聊，不公开；没有自动创建提醒。'}

    def bind(self,alias,course,message):
        import re
        if not isinstance(alias,str) or not 1<=len(alias.strip())<=80:raise CapabilityError('课程简称1至80字。')
        alias=alias.strip();key=alias.casefold();ident=str(course.get('id',''));name=str(course.get('name') or '');code=str(course.get('course_code') or '')
        if not ident.isdigit() or not name:raise CapabilityError('未核验Canvas课程。')
        if alias not in message or not any(x and x in message for x in (name,code,ident)) or not re.search('关联|绑定|对应|就是|简称|叫|记作',message):raise CapabilityError('请主人明确说课程简称对应哪个Canvas课程名称或课程代码，再保存关联。')
        if scrub(alias)!=alias:raise CapabilityError('简称包含疑似凭据。')
        with sqlite3.connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT course_id FROM course_links WHERE alias=?',(key,)).fetchone()
            if old and old[0]!=ident:raise CapabilityError('这个简称已关联另一门课，不能自动覆盖；请先核对并解除原关联。')
            db.execute('INSERT OR REPLACE INTO course_links VALUES(?,?,?,?,?)',(key,ident,name,code,self.clock()))
        return {'bound':True,'alias':alias,'course_id':ident,'course_name':name,'course_code':code,'notes_rewritten':False}

    def unlink(self,alias,message):
        import re
        if not alias or alias not in message or not re.search('解除|取消|解绑',message):raise CapabilityError('需要主人明确要求解除这个简称的关联。')
        with sqlite3.connect(self.path) as db:count=db.execute('DELETE FROM course_links WHERE alias=?',(alias.strip().casefold(),)).rowcount
        return {'removed':bool(count),'notes_deleted':False}

    def for_course(self,course):
        ident=str(course['id']);terms={str(course.get('name') or '').casefold(),str(course.get('course_code') or '').casefold()}
        terms.update(x['alias'] for x in self.links() if x['course_id']==ident);terms.discard('')
        if not terms:return []
        with sqlite3.connect(self.path) as db:
            rows=db.execute("SELECT n.id,n.course,n.progress,n.stamp FROM notes n WHERE NOT EXISTS(SELECT 1 FROM notes r WHERE r.supersedes=n.id) AND lower(n.course) IN ("+','.join('?' for _ in terms)+') ORDER BY stamp DESC,id DESC LIMIT 5',tuple(terms)).fetchall()
        return [dict(id=i,course=c,progress=p,at=t,source='owner_statement') for i,c,p,t in rows]
