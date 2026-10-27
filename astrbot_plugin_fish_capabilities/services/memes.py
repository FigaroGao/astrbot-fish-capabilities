from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from .policy import CapabilityError, contained_file


CATEGORIES={'happy','comfort','tease','confused','greeting','goodnight','sad','acknowledge'}
CATEGORY_FOLDERS={'happy':'开心','comfort':'安慰','tease':'吐槽调侃','confused':'疑惑','greeting':'打招呼','goodnight':'晚安','sad':'难过','acknowledge':'收到回应'}


def image_signature(data: bytes) -> bool:
    return (data.startswith(b'\x89PNG\r\n\x1a\n') or data.startswith(b'\xff\xd8\xff')
            or data.startswith((b'GIF87a',b'GIF89a'))
            or (data[:4]==b'RIFF' and data[8:12]==b'WEBP'))


@dataclass(frozen=True)
class Meme:
    id: str
    category: str
    path: Path
    tags: tuple[str,...]
    sha256: str
    description: str = ''
    image_text: str = ''
    usage_notes: str = ''


class MemeLibrary:
    def __init__(self, root: Path):
        self.root=root
        self.used: dict[tuple[str,str],float]={}
        self.verified: dict[tuple, str]={}

    def manageable(self):
        self.catalog()  # Validate every existing entry/path/hash before editing.
        if not (self.root/'manifest.json').exists():return {'version':'','entries':[]}
        raw=(self.root/'manifest.json').read_bytes()
        return {'version':hashlib.sha256(raw).hexdigest(),'entries':json.loads(raw)}

    def review_preview(self,meme_id):
        data=self.manageable();row=next((r for r in data['entries'] if str(r.get('id'))==meme_id),None)
        if row is None:raise CapabilityError('图片ID不存在。')
        path=contained_file(self.root,str(row['file']),suffixes={'.png','.jpg','.jpeg','.gif','.webp'})
        meme=Meme(str(row['id']),str(row['category']),path,(),str(row['sha256']))
        return self.bytes_for(meme),path.suffix.lower()

    def edit(self,meme_id,version,*,description,image_text,usage_notes,tags,category,approved):
        fields=((description,160),(image_text,300),(usage_notes,240))
        if any(not isinstance(v,str) or len(v)>n for v,n in fields) or category not in CATEGORIES:
            raise CapabilityError('描述、文字或场景超长，或分类无效。')
        if not isinstance(tags,list) or len(tags)>8 or any(not isinstance(t,str) or len(t)>40 for t in tags) or type(approved)is not bool:
            raise CapabilityError('标签最多8个、每个40字，审核状态必须为布尔值。')
        data=self.manageable()
        if data['version']!=version:raise CapabilityError('图库已变化，请刷新后再修改。')
        rows=data['entries'];target=next((r for r in rows if str(r.get('id'))==meme_id),None)
        if target is None:raise CapabilityError('表情ID不存在。')
        target.update(description=description,image_text=image_text,usage_notes=usage_notes,tags=tags,category=category,approved=approved)
        manifest=self.root/'manifest.json';backup=self.root/'manifest.before-edit.json'
        backup.write_bytes(manifest.read_bytes());backup.chmod(0o600)
        tmp=manifest.with_suffix('.edit');tmp.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');tmp.chmod(0o600);tmp.replace(manifest)
        return {'saved':True,'version':hashlib.sha256(manifest.read_bytes()).hexdigest()}

    def catalog(self) -> list[Meme]:
        manifest=self.root/'manifest.json'
        if not manifest.is_file(): return []
        if manifest.is_symlink() or manifest.stat().st_size>200_000:
            raise CapabilityError('表情目录清单异常。')
        rows=json.loads(manifest.read_text(encoding='utf-8'))
        if not isinstance(rows,list) or len(rows)>500: raise CapabilityError('表情清单最多 500 条。')
        entries=[];ids=set()
        for row in rows:
            if not isinstance(row,dict): raise CapabilityError('表情清单条目必须是对象。')
            category=row.get('category'); asset_id=str(row.get('id',''))
            if category not in CATEGORIES or not asset_id or asset_id in ids:
                raise CapabilityError('表情分类或 ID 重复，请先整理清单。')
            path=contained_file(self.root,str(row.get('file','')),suffixes={'.png','.jpg','.jpeg','.gif','.webp'})
            stat=path.stat()
            if not 1<=stat.st_size<=4_000_000: raise CapabilityError('单个表情必须小于 4MB。')
            signature=(str(path),stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
            digest=self.verified.get(signature)
            if digest is None:
                data=path.read_bytes()
                if not image_signature(data): raise CapabilityError('文件没有支持的图片标识，拒绝当作表情发送。')
                digest=hashlib.sha256(data).hexdigest()
                if len(self.verified)>1000: self.verified.clear()
                self.verified[signature]=digest
            if digest!=row.get('sha256'): raise CapabilityError('表情文件与导入清单不一致，请重新导入。')
            ids.add(asset_id)
            if row.get('approved') is not True: continue
            if not isinstance(row.get('tags',[]),list): raise CapabilityError('表情标签必须是数组。')
            entries.append(Meme(asset_id,category,path,tuple(str(x)[:40] for x in row.get('tags',[])[:8]),digest,
                                str(row.get('description',''))[:160],str(row.get('image_text',''))[:300],str(row.get('usage_notes',''))[:240]))
        return entries

    def choose(self, category: str, scope: str, *, tags: list[str] | None = None,
               excluded: set[str] | None = None, meme_id: str = '') -> Meme:
        if category not in CATEGORIES: raise CapabilityError('请选择已有表情分类。')
        candidates=[m for m in self.catalog() if m.category==category and m.sha256 not in (excluded or set())]
        if not candidates: raise CapabilityError('这个分类还没有主人导入并确认的表情。')
        if meme_id:
            candidates=[m for m in candidates if m.id==meme_id]
            if not candidates:raise CapabilityError('所选表情不存在、不属于此分类或仍在重复冷却中。')
        elif len(candidates)>1:
            raise CapabilityError('请先查表情目录，根据含义选择具体 meme_id，不随机代选。')
        tags=set(tags or [])
        candidates.sort(key=lambda m:(-len(tags.intersection(m.tags)),self.used.get((scope,m.id),0),m.id))
        chosen=candidates[0]
        return chosen

    def bytes_for(self, meme: Meme) -> bytes:
        # Recheck the chosen bytes at handoff, including changes after selection.
        relative=str(meme.path.relative_to(self.root.resolve()))
        path=contained_file(self.root,relative,suffixes={'.png','.jpg','.jpeg','.gif','.webp'})
        if path.stat().st_size>4_000_000: raise CapabilityError('表情在选取后发生变化。')
        data=path.read_bytes()
        if not image_signature(data) or hashlib.sha256(data).hexdigest()!=meme.sha256:
            raise CapabilityError('表情在选取后发生变化，未发送。')
        return data

    def mark(self, scope: str, meme: Meme):
        self.used[(scope,meme.id)]=time.time()
        if len(self.used)>2000:
            oldest=sorted(self.used,key=self.used.get)[:500]
            for key in oldest: del self.used[key]
