"""Independent local style hints: read-only, scoped and never an AI detector.

Inspired by dsh-fish-tone's context-sensitive diagnosis; no upstream code copied.
Stored reports contain rule IDs, offsets and counts, never conversation text.
"""
import hashlib
import json
import re
import sqlite3
import time
from .policy import CapabilityError

SCENES={'auto','chat','empathy','explain','steps','compare','data','public'}
RULES={
    'receipt':('空泛认可开头',r'(?:^|[。！？\n])\s*(?:这一点我认|这点我认|你说得对|我理解你的感受|你说得很有道理)(?=[，,。！!\s]|$)','这句认可是否增加了信息？能否直接接对方说的具体事情？'),
    'priority':('没有被要求的重点排序',r'真要只挑一件|最(?:重要|关键|值得注意)的(?:一点|事情)?是','当前真的需要比较或挑出一个重点吗？'),
    'contrast':('否定再转折',r'不是[^。！？\n]{1,36}?而是','前文是否真的有人持有被否定的说法？'),
    'sensory_mirror':('渲染式复述感受',r'(?:疼|痛|难过|委屈)得(?:特别|很|太)?(?:实在|真实)','这句是在关心眼前处境，还是把对方的感受改写成感悟？轻微吐槽是否只需自然接一句？'),
    'sequence':('先后框架',r'先[^。！？\n]{1,36}?再','这两个动作是否真的有顺序？只是闲聊时需要安排步骤吗？'),
    'roadmap':('目录与收尾',r'首先|其次|综上所述|总而言之|总结一下','这次对话需要目录和总结吗？说完具体内容能否就停？'),
}
PROTECTED=re.compile(r'```[\s\S]*?```|`[^`\n]*`|https?://[^\s<>]+|“[^”\n]*”|「[^」\n]*」|『[^』\n]*』|‘[^’\n]*’|"[^"\n]*"|(?m:^\s*>[^\n]*$)|(?m:^\s*(?:\$\s|npm\s|git\s|python\s|[A-Za-z]:\\|~/|\./)[^\n]*$)|(?<![0-9A-Za-z])\d[\d.:/%+-]*(?:元|点|分|秒|小时)?')

def scene_for(message):
    if re.search(r'步骤|教程|怎么安装|怎么部署|操作流程|列.{0,5}(清单|步骤)',message):return 'steps'
    if re.search(r'对比|比较|优缺点|选哪|哪个好|挑一件|选一个',message):return 'compare'
    if re.search(r'天气|每日商店|今日商店|战绩|爆头率|多少钱|几[点时]|日期',message):return 'data'
    if re.search(r'解释|原理|为什么|详细|分析一下|什么意思|讲讲',message):return 'explain'
    if re.search(r'难过|伤心|委屈|害怕|崩溃|想哭',message):return 'empathy'
    return 'chat'

def analyze(text,context='',scene='auto'):
    if not isinstance(text,str) or not text.strip() or len(text)>6000 or not isinstance(context,str) or len(context)>1200 or not isinstance(scene,str) or scene not in SCENES:
        raise CapabilityError('诊断限1至6000字，当前语境最多1200字，场景须使用已登记选项。')
    chosen=scene_for(context) if scene=='auto' else scene
    mask=list(text);protected=0
    for match in PROTECTED.finditer(text):
        mask[match.start():match.end()]=[' ']*(match.end()-match.start());protected+=1
    visible=''.join(mask);hits=[]
    for code,(label,pattern,question) in RULES.items():
        for match in re.finditer(pattern,visible):
            supported=(chosen in ('steps','data') or
                       (code=='priority' and chosen=='compare') or
                       (code=='receipt' and bool(re.search(r'纠正|误会|你错了|不对|更正',context))) or
                       (code=='contrast' and bool(re.search(r'以为|有人说|听说|误会|是不是',context))))
            hits.append({'code':code,'label':label,'start':match.start(),'end':match.end(),
                         'assessment':'context_supported' if supported else 'check','question':question})
    hits.sort(key=lambda h:(h['start'],h['end']))
    clusters=[]
    checks=[h for h in hits if h['assessment']=='check']
    for hit in checks:
        near=[h for h in checks if hit['start']<=h['start']<hit['start']+100]
        codes=sorted({h['code'] for h in near})
        if len(codes)>=3:
            clusters.append({'start':hit['start'],'end':min(len(text),hit['start']+100),'different_frames':codes});break
    return {'scene':chosen,'chars':len(text),'protected_spans':protected,'offset_units':'unicode_codepoints','hits':hits[:16],'clusters':clusters,
            'opening_codes':sorted({h['code'] for h in checks if h['start']<24}),
            'status':'hints_found' if checks else 'no_rule_hints','model_calls':0,'text_changed':False,
            'instruction':'这是本地规则线索，不是人味评分或语义结论。context_supported也不保证表达合适；没有命中不代表一定自然。只定位，不改字、不自动重写、不把诊断当作主人偏好。'}

class ToneDiagnostics:
    def __init__(self,path,clock=time.time):
        self.path,self.clock=path,clock
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY,scope TEXT,stamp REAL,digest TEXT,report TEXT)')
            db.execute('CREATE INDEX IF NOT EXISTS tone_scope_stamp ON reports(scope,stamp)')
        path.chmod(0o600)

    def record(self,scope,text,context='',scene='auto'):
        if not isinstance(scope,str) or not scope:raise CapabilityError('诊断需要明确会话范围。')
        result=analyze(text,context,scene);now=self.clock()
        digest=hashlib.sha256((text+'\0'+result['scene']).encode()).hexdigest()
        with sqlite3.connect(self.path) as db:
            if db.execute('SELECT 1 FROM reports WHERE scope=? AND digest=? AND stamp>?',(scope,digest,now-300)).fetchone():return result
            previous=[json.loads(r[0]) for r in db.execute('SELECT report FROM reports WHERE scope=? ORDER BY id DESC LIMIT 5',(scope,))]
            repeats=[{'code':code,'previous_turns':sum(code in r['opening_codes'] for r in previous)} for code in result['opening_codes']]
            result['recent_opening_repeats']=[r for r in repeats if r['previous_turns']>=2]
            db.execute('INSERT INTO reports(scope,stamp,digest,report) VALUES(?,?,?,?)',(scope,now,digest,json.dumps(result,ensure_ascii=False)))
            db.execute('DELETE FROM reports WHERE stamp<?',(now-14*86400,))
            db.execute('DELETE FROM reports WHERE id NOT IN (SELECT id FROM reports ORDER BY id DESC LIMIT 2000)')
        return result

    def recent(self,scope,limit=8):
        with sqlite3.connect(self.path) as db:
            rows=db.execute('SELECT id,stamp,report FROM reports WHERE scope=? ORDER BY id DESC LIMIT ?',(scope,max(1,min(20,limit)))).fetchall()
        return {'records':[{'id':i,'at':stamp,**json.loads(raw)} for i,stamp,raw in rows],
                'instruction':'仅本会话生成草稿的规则记录，不是送达回执；不保存原文，不自动改字。觉得哪句别扭，可到表达与观察保存具体建议。'}
