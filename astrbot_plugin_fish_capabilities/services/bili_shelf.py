"""Read bound owner's public shelf anonymously, without saving taste/memory."""
import asyncio
import re
from .policy import CapabilityError,bounded_int
from .bilibili import bvid,plain
from .bili_social import uid
from .http import PublicJSON

class ShelfBackend:
    async def likes(self,owner):
        value=await PublicJSON().get('https://api.bilibili.com/x/space/like/video?vmid='+owner,{'api.bilibili.com'})
        if value.get('code')!=0:raise CapabilityError('点赞清单未公开或接口暂不可用，没有尝试登录读取私密数据。')
        data=value.get('data') or {};return data.get('list',[]) if isinstance(data,dict) else []
    async def folders(self,owner):
        from bilibili_api import favorite_list
        return await favorite_list.get_video_favorite_list(int(owner),credential=None)
    async def content(self,folder,page):
        from bilibili_api import favorite_list
        return await favorite_list.get_video_favorite_list_content(int(folder),page=page,credential=None)


def public_folder(row,owner):
    return type(row.get('attr')) is int and row['attr']&1==0 and str(row.get('mid'))==owner


def compact(rows,limit):
    result=[]
    for row in rows:
        try:video=bvid(str(row.get('bvid') or row.get('bv_id') or ''))
        except CapabilityError:continue
        # Explicit allowlist: no like/favorite/publication timestamps or traces.
        result.append({'bvid':video,'title':plain(row.get('title'))[:200],
            'author':plain((row.get('owner') or row.get('upper') or {}).get('name') or row.get('author'))[:60],
            'duration':row.get('duration') if type(row.get('duration')) in (int,float) else None})
        if len(result)>=limit:break
    return result


class PublicShelf:
    def __init__(self,settings,backend=None):self.settings=settings;self.backend=backend or ShelfBackend()
    async def read(self,kind='likes',folder_id='',limit=6,page=1):
        if kind not in ('likes','folders','favorites'):raise CapabilityError('公开清单类型只能是likes、folders或favorites。')
        bounded_int(limit,1,6,'公开条目数');bounded_int(page,1,5,'页码')
        owner=uid(self.settings.get('bili_owner_uid',''));start=(page-1)*limit
        result={'kind':kind,'scope':'仅主人公开清单，不代表小鲸自己的兴趣','saved_to_video_memory':False,'page':page,
            'instruction':'这是主人明确要求私聊查看的公开清单，只是翻书架。不要用它作为小鲸的推荐种子、口味证据、视频记忆或长期记忆；不带到群或公开评论。不返回点赞或收藏时间。只列出不代表看过，超10分钟视频仍不能深读，私密/未公开数据不碰。'}
        if kind=='likes':
            rows=await asyncio.wait_for(self.backend.likes(owner),20)
            return dict(result,videos=compact(rows[start:start+limit],limit),available_count=len(rows),complete_history=False)
        folders=await asyncio.wait_for(self.backend.folders(owner),20)
        public=[r for r in (folders.get('list') or []) if public_folder(r,owner)]
        if kind=='folders':
            return dict(result,folders=[{'folder_id':str(r['id']),'title':plain(r.get('title'))[:120],'media_count':r.get('media_count')} for r in public[start:start+limit]],complete_history=False)
        folder=uid(folder_id)
        if folder not in {str(r['id']) for r in public}:raise CapabilityError('该收藏夹不在主人当前公开清单中，未读取内容。')
        rows=[];offset=start%20;upstream=start//20+1
        for index in range(upstream,upstream+2):
            data=await asyncio.wait_for(self.backend.content(folder,index),20);info=data.get('info') or {}
            if not public_folder(info,owner) or str(info.get('id'))!=folder:raise CapabilityError('收藏夹归属或公开状态未核实，未返回内容。')
            rows.extend((data.get('medias') or [])[offset:]);offset=0
            if len(rows)>=limit or not data.get('has_more'):break
        return dict(result,folder_id=folder,videos=compact(rows,limit),complete_history=False)


def shelf_requested(text):
    text=str(text or '')
    if re.search(r'(?:别|不要|不许|不想|先不).{0,8}(?:看|查|翻|读|列|展示)',text):return False
    return bool(re.search(r'点赞|收藏|书架|清单|收藏夹',text) and re.search(r'看|读|列|翻|查|展示|给我',text))
