from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request
import urllib.error

from .policy import CapabilityError


class PublicRequestError(CapabilityError):
    """Safe transport status; no URL, query, response body or credentials."""
    def __init__(self, status=None):
        self.http_status=status
        if status==412:message='B站/公共服务返回HTTP 412（请求被站点拒绝），不是画面数不够；本次未取得资料，不自动连续重试。'
        elif status==429:message='公共服务返回HTTP 429（请求过频），本次停止，稍后再试。'
        elif status:message=f'公共服务返回HTTP {status}，本次未取得资料。'
        else:message='公共服务连接或响应失败，本次未取得资料；不能据此断言是登录或模型故障。'
        super().__init__(message)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CapabilityError('服务返回了重定向，本次请求未跟随。')


class PublicJSON:
    def __init__(self, *, max_bytes: int = 1_000_000, timeout: float = 12, user_agent: str = 'FishCapabilitiesDraft/0.1'):
        self.max_bytes=max_bytes; self.timeout=timeout
        self.user_agent=user_agent

    def _get(self, url: str, allowed_hosts: set[str]):
        try:
            parsed=urllib.parse.urlsplit(url)
            if parsed.scheme!='https' or parsed.hostname not in allowed_hosts or parsed.username or parsed.password or parsed.port not in (None,443):
                raise CapabilityError('请求地址不在已配置的公共服务范围内。')
            req=urllib.request.Request(url,headers={'User-Agent':self.user_agent})
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=self.timeout) as response:
                data=response.read(self.max_bytes+1)
            if len(data)>self.max_bytes: raise CapabilityError('服务返回内容过大。')
            return json.loads(data)
        except CapabilityError: raise
        except urllib.error.HTTPError as exc:
            raise PublicRequestError(exc.code) from exc
        except Exception as exc:
            raise PublicRequestError() from exc

    async def get(self, url: str, allowed_hosts: set[str]):
        return await asyncio.to_thread(self._get,url,allowed_hosts)
