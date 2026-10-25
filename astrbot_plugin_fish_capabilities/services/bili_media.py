"""Bilibili emote codes and approved public-pack images; no arbitrary paths."""
import asyncio
import json
import re
import time
from .policy import CapabilityError
from .bili_comments import CommentBackend

FREE={'[doge]','[笑哭]','[妙啊]','[微笑]','[吃瓜]','[呲牙]','[滑稽]','[捂脸]','[点赞]','[给心心]','[打call]','[嗑瓜子]','[喜极而泣]','[惊讶]','[大哭]','[委屈]','[辣眼睛]','[热词系列_知识增加]'}


class CommentMedia:
    def __init__(self,backend,library,config):
        self.backend,self.library,self.config=backend,library,config
        self.cache=None

    async def codes(self):
        if not self.config.get('bili_emote_enabled',False):return []
        credential=self.backend.credential()
        account=str(getattr(credential,'dedeuserid','') or '')
        if not account or account!=str(self.config.get('bili_account_id','')):raise CapabilityError('表情账号与绑定账号不一致。')
        if self.cache and self.cache[0]==account and time.time()-self.cache[1]<1800:return self.cache[2]
        if await CommentBackend(self.backend).identity()!=account:raise CapabilityError('表情账号核验失败。')
        from bilibili_api import emoji
        data=await asyncio.wait_for(emoji.get_emoji_list('reply',credential=credential),15)
        values=[]
        for package in data.get('packages') or []:
            for row in package.get('emote') or []:
                text=row.get('text','')
                free=text in FREE or (package.get('text')=='tv_小电视' and text.startswith('[tv_'))
                unlocked=(row.get('flags') or {}).get('unlocked') is True
                if (free or unlocked) and re.fullmatch(r'\[[^\[\]@\r\n]{1,50}\]',text):values.append(text)
        values=list(dict.fromkeys(values))[:100]
        self.cache=(account,time.time(),values);return values

    async def validate(self,text):
        codes=re.findall(r'\[[^\[\]\r\n]+\]',text)
        if len(codes)>2:raise CapabilityError('单条B站评论最多两个站内表情。')
        if codes and not set(codes)<=set(await self.codes()):raise CapabilityError('使用了当前账号未确认可用的站内表情，请先查目录。')

    def image(self,meme_id,_meme=None,_row=None):
        if not self.config.get('bili_comment_image_enabled',False):raise CapabilityError('图库图片评论尚未启用。')
        if _row is None:
            raw=json.loads((self.library.root/'manifest.json').read_text(encoding='utf-8'))
            row=next((x for x in raw if x.get('id')==meme_id),None)
        else:row=_row
        if not row or row.get('approved') is not True or row.get('visually_reviewed') is not True:
            raise CapabilityError('只允许图库中已批准且逐图核对过的公开表情。')
        repository=str(row.get('source_repository','')).removesuffix('.git').rstrip('/')
        if repository!='https://github.com/the-beating-light-of-the-nail/deepseek-chan-meme-pack':
            raise CapabilityError('图片没有核验过的公开表情包来源，不上传私人图片。')
        meme=_meme or next((x for x in self.library.catalog() if x.id==meme_id),None)
        if not meme or meme.path.suffix.lower() not in ('.png','.jpg','.jpeg'):raise CapabilityError('目前只发送已核验PNG/JPEG静态表情。')
        data=self.library.bytes_for(meme)
        from PIL import Image
        import io
        with Image.open(io.BytesIO(data)) as img:
            if img.getexif():raise CapabilityError('图片带EXIF元数据，未直接上传。')
        return meme

    async def catalog(self):
        images=[]
        if self.config.get('bili_comment_image_enabled',False):
            index={x.get('id'):x for x in json.loads((self.library.root/'manifest.json').read_text(encoding='utf-8'))}
            for meme in self.library.catalog():
                try:item=self.image(meme.id,_meme=meme,_row=index.get(meme.id))
                except CapabilityError:continue
                images.append({'meme_id':item.id,'description':item.description,'image_text':item.image_text})
        return {'emotes':await self.codes(),'images':images[:80], 'instruction':'正文可使用目录中的站内表情代码，一条至多两个；配图库图片时用meme_id，一条至多一张，必须经过图片与文字审核；不能上传截图、相册或任意路径，不购买表情。'}
