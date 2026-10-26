"""Private persistent match cache, partitioned by bound account and role."""
import json,sqlite3,time,hashlib
from contextlib import contextmanager

def sanitized(value):
    if isinstance(value,dict):
        return {k:sanitized(v) for k,v in value.items() if not any(x in k.lower() for x in ('scene','token','cookie','openid','intent','req_id','credential')) and k not in ('tid','userId')}
    if isinstance(value,list):return [sanitized(v) for v in value]
    if isinstance(value,str) and value.startswith(('http:','https:','valpage:')):return None
    return value

class MatchCache:
    def __init__(self,path):
        path.parent.mkdir(parents=True,exist_ok=True);self.path=path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS matches(account TEXT,battle TEXT,played REAL,payload TEXT,PRIMARY KEY(account,battle))')
            db.execute('CREATE TABLE IF NOT EXISTS details(account TEXT,battle TEXT,part TEXT,payload TEXT,stamp REAL,version INTEGER,PRIMARY KEY(account,battle,part))')
            db.execute('CREATE TABLE IF NOT EXISTS sync(account TEXT PRIMARY KEY,stamp REAL,latest TEXT,exhausted INTEGER)')
        path.chmod(0o600)
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=5)
        try:
            with db:yield db
        finally:db.close()
    @staticmethod
    def key(row,index=0):
        return str(row.get('battle_id') or row.get('match_id') or hashlib.sha256((json.dumps(row,sort_keys=True)+str(index)).encode()).hexdigest())
    def keys(self,account):
        with self.connect() as db:return {r[0] for r in db.execute('SELECT battle FROM matches WHERE account=?',(account,))}
    def ingest(self,account,rows,offset=0):
        with self.connect() as db:
            for i,row in enumerate(rows):
                if not isinstance(row,dict):continue
                ts=row.get('ts');ts=ts if isinstance(ts,(int,float)) else time.time()-offset-i
                db.execute('INSERT INTO matches VALUES(?,?,?,?) ON CONFLICT(account,battle) DO UPDATE SET played=excluded.played,payload=excluded.payload',(account,self.key(row,i),ts,json.dumps(sanitized(row),ensure_ascii=False)))
    def rows(self,account,limit=30):
        with self.connect() as db:return [json.loads(r[0]) for r in db.execute('SELECT payload FROM matches WHERE account=? ORDER BY played DESC,battle DESC LIMIT ?',(account,limit))]
    def get_row(self,account,battle):
        with self.connect() as db:r=db.execute('SELECT payload FROM matches WHERE account=? AND battle=?',(account,battle)).fetchone()
        return json.loads(r[0]) if r else None
    def state(self,account):
        with self.connect() as db:
            r=db.execute('SELECT stamp,latest,exhausted FROM sync WHERE account=?',(account,)).fetchone()
        return r
    def synced(self,account,latest,exhausted):
        with self.connect() as db:db.execute('INSERT OR REPLACE INTO sync VALUES(?,?,?,?)',(account,time.time(),latest,int(exhausted)))
    def detail(self,account,battle,part):
        with self.connect() as db:r=db.execute('SELECT payload FROM details WHERE account=? AND battle=? AND part=? AND version=1',(account,battle,part)).fetchone()
        return json.loads(r[0]) if r else None
    def save_detail(self,account,battle,part,data):
        with self.connect() as db:db.execute('INSERT OR REPLACE INTO details VALUES(?,?,?,?,?,1)',(account,battle,part,json.dumps(sanitized(data),ensure_ascii=False),time.time()))
