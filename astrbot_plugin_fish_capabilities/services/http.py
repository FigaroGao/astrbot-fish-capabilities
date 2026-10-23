from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request

from .policy import CapabilityError


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CapabilityError('服务返回了重定向，本次请求未跟随。')


class PublicJSON:
    def __init__(self, *, max_bytes: int = 1_000_000, timeout: float = 12):
        self.max_bytes=max_bytes; self.timeout=timeout

    def _get(self, url: str, allowed_hosts: set[str]):
        try:
            parsed=urllib.parse.urlsplit(url)
            if parsed.scheme!='https' or parsed.hostname not in allowed_hosts or parsed.username or parsed.password or parsed.port not in (None,443):
                raise CapabilityError('请求地址不在已配置的公共服务范围内。')
            req=urllib.request.Request(url,headers={'User-Agent':'FishCapabilitiesDraft/0.1'})
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=self.timeout) as response:
                data=response.read(self.max_bytes+1)
            if len(data)>self.max_bytes: raise CapabilityError('服务返回内容过大。')
            return json.loads(data)
        except CapabilityError: raise
        except Exception as exc:
            raise CapabilityError('公共服务请求失败，请稍后重试；没有返回编造数据。') from exc

    async def get(self, url: str, allowed_hosts: set[str]):
        return await asyncio.to_thread(self._get,url,allowed_hosts)
