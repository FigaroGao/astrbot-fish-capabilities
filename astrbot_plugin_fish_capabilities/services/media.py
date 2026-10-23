from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from .policy import CapabilityError, Ledger


@dataclass(frozen=True)
class Pending:
    kind: str
    data: bytes
    text: str
    stamp: float
    reservation: int


class MediaQueue:
    """One decoration per input turn, not one media item per text bubble.

    Claim before a paid call. Keep the ledger reservation after handoff: a QQ
    timeout does not prove that QQ did not receive the message. No blind resend.
    """

    def __init__(self, ledger: Ledger, *, ttl: float = 300, capacity: int = 64):
        self.ledger = ledger
        self.ttl = ttl
        self.capacity = capacity
        self.pending: dict[tuple[str, str], Pending] = {}
        self.lock = asyncio.Lock()

    async def claim(self, scope: str, turn: str, kind: str, *, cooldown: float,
                    hourly: int, asset: str = '', min_reply_gap: int = 0, requested: bool = False) -> int:
        async with self.lock:
            self._expire()
            if len(self.pending) >= self.capacity:
                raise CapabilityError('待发送媒体较多，这次保持文字。')
            return self.ledger.reserve(scope, kind, turn, cooldown=cooldown,
                                       hourly=hourly, asset=asset,min_reply_gap=min_reply_gap,requested=requested)

    def _expire(self):
        now = time.time()
        for key, item in list(self.pending.items()):
            if now - item.stamp > self.ttl:
                del self.pending[key]
                self.ledger.release(item.reservation)  # Never handed to the sender.

    async def enqueue(self, scope: str, turn: str, reservation: int, kind: str,
                      data: bytes, text: str = ''):
        if kind not in ('image', 'record') or not isinstance(data, bytes) or not 1 <= len(data) <= 4_000_000:
            self.ledger.release(reservation)
            raise CapabilityError('媒体数据无效。')
        async with self.lock:
            self._expire()
            if (scope, turn) in self.pending or len(self.pending) >= self.capacity:
                self.ledger.release(reservation)
                raise CapabilityError('本轮已有媒体或待发队列已满。')
            self.pending[(scope, turn)] = Pending(kind, data, text, time.time(), reservation)

    async def take(self, scope: str, turn: str) -> Pending | None:
        async with self.lock:
            self._expire()
            return self.pending.pop((scope, turn), None)

    def cancel_unsent(self, reservation: int):
        self.ledger.release(reservation)
