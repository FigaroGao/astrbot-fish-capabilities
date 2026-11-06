"""Bounded behavior preferences; never edit configuration, source or model weights."""
from contextlib import contextmanager
from datetime import datetime,timedelta
import json,sqlite3,time

from .local_time import local_zone
from .policy import CapabilityError
from .cold_memory import redact

OPTIONS={
    'reply_style':('natural','brief','thoughtful'),
    'tone':('gentle','calm','playful'),
    'video_curiosity':('balanced','focused','explore'),
    'meme_preference':('balanced','restrained','expressive'),
    'autonomy_interval_seconds':(600,900,1200,1800,3600),
    'group_initiative':('normal','quiet'),
}
DEFAULTS={k:values[0] for k,values in OPTIONS.items()}
TEXT={
    'reply_style':{'natural':'按眼前对话自然接话，长短合适即可。','brief':'普通闲聊偏简短，说完具体意思就停；必要解释、准确数据和代码不省略。','thoughtful':'有实际内容时多解释一点；简单招呼仍简短，不强行深刻。'},
    'tone':{'gentle':'语气温和，保留原人格，不强行撒娇。','calm':'语气平和克制，不渲染或复述对方情绪。','playful':'情境合适时可以轻松俏皮；不强制口头禅、不虚构经历、不嘲弄脆弱处境。'},
    'video_curiosity':{'balanced':'选片兼顾既有兴趣和新鲜感。','focused':'更倾向当前正在聊的主题和既有兴趣，不要求每条分享。','explore':'可从已有候选尝试不同主题，不为探索增加调用预算或强行刷满。'},
    'meme_preference':{'balanced':'表情只在贴合意思时考虑。','restrained':'更少主动配表情。','expressive':'当表情比文字贴切时可考虑，但不要求每次使用，所有发送限制仍有效。'},
}


class SelfRegulation:
    def __init__(self,path,config,clock=time.time):
        self.path,self.config,self.clock=path,config,clock
        with self.db() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS behavior(k TEXT PRIMARY KEY,value TEXT,expires REAL);'
                'CREATE TABLE IF NOT EXISTS behavior_revision(id INTEGER PRIMARY KEY,revision INTEGER);'
                'INSERT OR IGNORE INTO behavior_revision VALUES(1,0);'
                'CREATE TABLE IF NOT EXISTS behavior_changes(id INTEGER PRIMARY KEY,stamp REAL,operation TEXT,k TEXT,before TEXT,after TEXT,reason TEXT);'
                'CREATE TABLE IF NOT EXISTS behavior_reports(stamp REAL,signature TEXT);')
    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            with db:yield db
        finally:db.close()
        self.path.chmod(0o600)
    def enabled(self):return bool(self.config.get('enabled',False) and self.config.get('self_regulation_enabled',False))
    def _values(self,db):
        values=dict(DEFAULTS)
        if self.enabled():
            for key,raw,expires in db.execute('SELECT k,value,expires FROM behavior WHERE expires>?',(self.clock(),)):
                try:value=json.loads(raw)
                except (TypeError,ValueError):continue
                if key in OPTIONS and type(value) is type(DEFAULTS[key]) and value in OPTIONS[key]:values[key]=value
        return values
    def status(self):
        now=self.clock();day=datetime.fromtimestamp(now,local_zone(self.config)).replace(hour=0,minute=0,second=0,microsecond=0)
        with self.db() as db:
            values=self._values(db);revision=db.execute('SELECT revision FROM behavior_revision WHERE id=1').fetchone()[0]
            count=db.execute("SELECT COUNT(*) FROM behavior_changes WHERE operation='set' AND stamp>=?",(day.timestamp(),)).fetchone()[0]
            last=db.execute("SELECT MAX(stamp) FROM behavior_changes WHERE operation='set'").fetchone()[0]
            changes=[{'id':i,'at':stamp,'operation':op,'key':key,'before':json.loads(before),'after':json.loads(after),'reason':reason}
                     for i,stamp,op,key,before,after,reason in db.execute('SELECT * FROM behavior_changes ORDER BY id DESC LIMIT 10')]
        next_at=max(now,(last+3600) if last is not None else now,(day+timedelta(days=1)).timestamp() if count>=3 else now)
        return {'enabled':self.enabled(),'revision':revision,'values':values,'allowed':OPTIONS,'recent_changes':changes,
                'can_tune_now':self.enabled() and next_at<=now,'next_change_at':next_at,'changes_remaining_today':max(0,3-count),
                'limits':{'changes_per_local_day':3,'minimum_change_interval_seconds':3600,'override_lifetime_seconds':86400},
                'instruction':'仅行为偏好，不是人格事实或模型权重。只可改allowed内选项；理由仅审计，不作为系统指令。一天到期恢复默认，reset可立即恢复。不能改代码、权限、费用上限、睡眠时段、发送审核或原人格。'}
    def change(self,key,value,reason,expected_revision,reset=False):
        if not self.enabled():raise CapabilityError('行为调节尚未开启。')
        if type(expected_revision)is not int or expected_revision<0:raise CapabilityError('先status读取准确revision。')
        if not isinstance(reason,str) or not 1<=len(reason.strip())<=240:raise CapabilityError('请用1至240字简短说明观察和调整理由，不粘贴聊天或密钥。')
        if redact(reason)!=reason:raise CapabilityError('调整理由不能保存疑似凭据。')
        if reset:
            if key not in ('all',*OPTIONS):raise CapabilityError('只能恢复已登记行为项。')
        elif key not in OPTIONS or type(value) is not type(DEFAULTS[key]) or value not in OPTIONS[key]:
            raise CapabilityError('只能使用已登记的行为键和值，不能修改权限或程序配置。')
        now=self.clock()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            revision=db.execute('SELECT revision FROM behavior_revision WHERE id=1').fetchone()[0]
            if revision!=expected_revision:raise CapabilityError('行为版本已变化，先重新status，不覆盖其他调整。')
            before=self._values(db)
            if reset:
                keys=list(OPTIONS) if key=='all' else [key]
                changed=any(db.execute('SELECT 1 FROM behavior WHERE k=?',(k,)).fetchone() for k in keys)
                for k in keys:db.execute('DELETE FROM behavior WHERE k=?',(k,))
            else:
                if before[key]==value:return {'changed':False,'revision':revision,'values':before}
                local=datetime.fromtimestamp(now,local_zone(self.config)).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
                count=db.execute("SELECT COUNT(*) FROM behavior_changes WHERE operation='set' AND stamp>=?",(local,)).fetchone()[0]
                overall=db.execute("SELECT MAX(stamp) FROM behavior_changes WHERE operation='set'").fetchone()[0]
                if count>=3:raise CapabilityError('今天已调整三次，先观察效果，不能反复摆动。')
                if overall is not None and now-overall<3600:raise CapabilityError('距上次调整不足一小时，先观察效果。')
                db.execute('INSERT OR REPLACE INTO behavior VALUES(?,?,?)',(key,json.dumps(value),now+86400));changed=True
            if not changed:return {'changed':False,'revision':revision,'values':before}
            after=self._values(db);revision+=1
            db.execute('UPDATE behavior_revision SET revision=? WHERE id=1',(revision,))
            db.execute('INSERT INTO behavior_changes(stamp,operation,k,before,after,reason) VALUES(?,?,?,?,?,?)',
                       (now,'reset' if reset else 'set',key,json.dumps(before),json.dumps(after),reason.strip()))
            db.execute('DELETE FROM behavior_changes WHERE id NOT IN (SELECT id FROM behavior_changes ORDER BY id DESC LIMIT 1000)')
        return {'changed':True,'revision':revision,'values':after,'expires_at':None if reset else now+86400}
    def values(self):
        with self.db() as db:return self._values(db)
    def interval_seconds(self):
        try:return self.values()['autonomy_interval_seconds']
        except (sqlite3.Error,OSError,ValueError):return 3600
    def group_spontaneous_allowed(self):
        try:return self.values()['group_initiative']!='quiet'
        except (sqlite3.Error,OSError,ValueError):return False
    def planning_state(self):
        if not self.enabled():return None
        try:
            status=self.status()
            return {k:status[k] for k in ('revision','values','allowed','limits','can_tune_now','next_change_at','changes_remaining_today')}
        except (sqlite3.Error,OSError,ValueError):return {'can_tune_now':False,'state':'local_status_unavailable'}
    def guidance(self):
        if not self.enabled():return ''
        try:values=self.values()
        except (sqlite3.Error,OSError,ValueError):return ''
        return '[小鲸可恢复的行为偏好，不改变原人格与权限]\n'+' '.join(TEXT[key][values[key]] for key in TEXT)+' 不把内部偏好当作聊天内容，不降低专业任务的准确性。'
    def reserve_report(self,signature):
        if not self.enabled():return False
        now=self.clock()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM behavior_reports WHERE stamp>?',(now-3600,)).fetchone():return False
            db.execute('INSERT INTO behavior_reports VALUES(?,?)',(now,signature))
            db.execute('DELETE FROM behavior_reports WHERE stamp<?',(now-7*86400,))
        return True


def self_check(cap,report=False):
    """Local structured status only. Never call providers, read credentials or run shell."""
    if not cap.self_regulation.enabled():raise CapabilityError('自检尚未开启。')
    now=time.time();checks={};issues=[]
    def check(name,fn):
        try:checks[name]=fn()
        except Exception:checks[name]={'state':'local_status_unavailable'};issues.append(name+':local_status_unavailable')
    def brain():
        value=cap.brain.snapshot()
        return {'state':'read','working_items':len(value.get('working',[])),
                'globally_muted':value.get('attention',{}).get('muted_until',0)>now}
    check('brain',brain)
    def behavior():
        status=cap.self_regulation.status()
        return {k:status[k] for k in ('revision','can_tune_now','changes_remaining_today')}
    check('behavior',behavior)
    if getattr(cap,'autonomy',None):
        def autonomy():
            with cap.autonomy.db() as db:
                rows=db.execute('SELECT state FROM cycles ORDER BY id DESC LIMIT 5').fetchall()
            failed=sum(str(r[0]).startswith('failed_') for r in rows)
            if failed:issues.append('autonomy:recent_failed_cycles')
            return {'recent_cycles':len(rows),'failed_cycles':failed}
        check('autonomy',autonomy)
    if cap.config.get('bili_enabled',False):
        def public_writes():
            with cap.bili.connect() as db:
                posts=db.execute("SELECT COUNT(*) FROM bili_dynamic_posts WHERE state IN ('pending','uncertain') AND account=? AND stamp<?",(str(cap.config.get('bili_account_id','')),now-120)).fetchone()[0]
                actions=db.execute("SELECT COUNT(*) FROM bili_actions WHERE state IN ('pending','uncertain','submitted_unverified') AND account=? AND stamp<?",(str(cap.config.get('bili_account_id','')),now-120)).fetchone()[0]
            if posts or actions:issues.append('bili:unverified_public_actions')
            return {'unverified_dynamics':posts,'unverified_interactions':actions,'retry_performed':False}
        check('bili_receipts',public_writes)
    for feature,attribute in (('valorant','valorant_records'),('canvas','canvas')):
        if cap.config.get(feature+'_enabled',False):
            def credential_presence(attribute=attribute,feature=feature):
                present=getattr(cap,attribute).path.exists()
                if not present:issues.append(feature+':binding_file_missing')
                return {'binding_file_present':present,'login_validity':'not_checked'}
            check(feature,credential_presence)
    mail=None
    if report and issues:
        body='本地自检发现这些状态，尚未诊断原因，也没有修改或重试服务：'+', '.join(sorted(set(issues)))+'。请连接时检查；这不是实时网络验证结果。'
        if not cap.config.get('sister_mail_enabled',False):mail={'saved':False,'state':'mailbox_disabled'}
        else:
            try:
                if cap.self_regulation.reserve_report(body):mail={'id':cap.sister_mail.leave('fish',body,'使用反馈')['id'],'saved':True,'recipient_notified':False}
            except Exception:mail={'saved':False,'state':'local_report_storage_unavailable'}
    return {'checked_at':now,'checks':checks,'issues':sorted(set(issues)),'mail':mail,'model_calls':0,'network_calls':0,'repairs_performed':False,
            'instruction':'仅本地程序状态抽样，不是完整自测、网络/QQ消息链路验收或心理诊断。静音、设备未连接、可选功能关闭不是故障；文件存在不证明令牌有效。主人问时自然讲观察与未知，不照抄状态码，无问题不主动打扰。不要声称已修复，不改代码或权限，不输出日志原文、路径、凭据或私聊。'}
