"""Local-only shop observations and wishlist, partitioned by bound role."""
import hashlib,json,time
from datetime import datetime
from .local_time import local_zone
from .policy import CapabilityError


class ShopNotes:
    def __init__(self,store):
        self.store=store
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS shop_observations(account TEXT,id TEXT,stamp REAL,packet TEXT,PRIMARY KEY(account,id))')
            db.execute('CREATE TABLE IF NOT EXISTS shop_wishlist(account TEXT,name TEXT,stamp REAL,PRIMARY KEY(account,name))')
    def capture(self,account,packet):
        digest=hashlib.sha256(json.dumps([packet.get('expires_at'),packet['items']],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        with self.store.connect() as db:
            db.execute('INSERT OR IGNORE INTO shop_observations VALUES(?,?,?,?)',(account,digest,packet['fetched_at'],json.dumps(packet,ensure_ascii=False)))
            db.execute('DELETE FROM shop_observations WHERE account=? AND stamp<?',(account,time.time()-90*86400))
    def names(self,account):
        with self.store.connect() as db:return [r[0] for r in db.execute('SELECT name FROM shop_wishlist WHERE account=? ORDER BY stamp,name',(account,))]
    def change(self,account,action,name,owner_message):
        if not isinstance(name,str) or not 1<=len(name.strip())<=80 or name not in owner_message:
            raise CapabilityError('请主人明确给出愿望单商品名称；不根据模型猜测添加或删除。')
        name=name.strip()
        with self.store.connect() as db:
            if action=='add':
                count=db.execute('SELECT COUNT(*) FROM shop_wishlist WHERE account=?',(account,)).fetchone()[0]
                exists=db.execute('SELECT 1 FROM shop_wishlist WHERE account=? AND name=?',(account,name)).fetchone()
                if count>=50 and not exists:raise CapabilityError('本地愿望单最多50项。')
                db.execute('INSERT OR IGNORE INTO shop_wishlist VALUES(?,?,?)',(account,name,time.time()))
            elif action=='remove':db.execute('DELETE FROM shop_wishlist WHERE account=? AND name=?',(account,name))
            else:raise CapabilityError('不支持的愿望单操作。')
    def history(self,account):
        with self.store.connect() as db:rows=db.execute('SELECT stamp,packet FROM shop_observations WHERE account=? ORDER BY stamp DESC LIMIT 14',(account,)).fetchall()
        return [{'observed_at':t,'items':json.loads(p)['items'],'expires_at':json.loads(p).get('expires_at')} for t,p in rows]


async def query(reader,action='list',name='',owner_message=''):
    if action not in ('list','add','remove','check','history'):raise CapabilityError('愿望单操作为list、add、remove、check或history。')
    packet=await reader.shop() if action=='check' else None
    async with reader.lock:
        credentials=reader.credentials();role=await reader.role(credentials);account=reader.account(credentials,role)
        notes=ShopNotes(reader.store)
        if action in ('add','remove'):notes.change(account,action,name,owner_message)
        if packet and packet.get('account_ref')!=account:raise CapabilityError('商店读取后绑定角色已变化，请重新查询。')
        names=notes.names(account)
        return {'action':action,'wishlist':names,'matches':[x for x in (packet or {}).get('items',[]) if any(n.casefold() in x['name'].casefold() for n in names)],
                'shop':packet,'history':notes.history(account) if action=='history' else None,
                'instruction':'仅主人私聊，本机愿望单和实际观察过的商店，不是官方出货历史或预测；商品名称按包含关系匹配，需核对是否同款。不购买，不新建轮询或主动提醒任务，价格保留接口原文。'}
