"""Request rate limiting for the endpoint that spends LLM quota (POST /api/query).

Two sliding windows, both checked before the agent makes any LLM call:

* per client: RATE_LIMIT_PER_MINUTE requests per client address per minute;
* global: RATE_LIMIT_PER_DAY requests across all clients per 24 hours, a ceiling on LLM spend
  that holds even when a caller rotates addresses.

A request counts against the windows only when it is let through, so a client that keeps
retrying while limited does not extend its own wait or use up the global budget. 0 turns a
window off.

Windows live in memory, per process: with several workers or instances each enforces its own,
so the effective limits multiply by their number.

The client address is the TCP peer unless TRUSTED_PROXY_HOPS says how many reverse proxies in
front of the app append to X-Forwarded-For. Only the entries those proxies added are used;
anything further left was sent by the client and is never trusted.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from fastapi import Request

MINUTE = 60.0
DAY = 24 * 60 * 60.0


@dataclass(frozen=True)
class Decision:
    allowed: bool
    scope: Literal["client", "global"] | None = None
    retry_after_seconds: int = 0


ALLOWED = Decision(allowed=True)


def _wait(hits: deque[float], limit: int, window: float, now: float) -> float:
    """Seconds until one more hit fits in the window (0: it fits now). Drops expired hits."""
    while hits and hits[0] <= now - window:
        hits.popleft()
    if limit and len(hits) >= limit:
        return hits[0] + window - now
    return 0.0


class RateLimiter:
    def __init__(
        self,
        per_client: int,
        global_limit: int,
        *,
        client_window: float = MINUTE,
        global_window: float = DAY,
        max_clients: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.per_client = per_client
        self.global_limit = global_limit
        self.client_window = client_window
        self.global_window = global_window
        self.max_clients = max_clients
        self._clock = clock
        self._lock = threading.Lock()  # sync endpoints run in a thread pool
        self._clients: dict[str, deque[float]] = {}
        self._global: deque[float] = deque()

    def hit(self, client: str) -> Decision:
        """Count a request from `client` if both windows have room; otherwise say which is full."""
        with self._lock:
            now = self._clock()
            hits = self._clients.get(client)
            if hits is not None and (wait := _wait(hits, self.per_client, self.client_window, now)):
                return Decision(False, "client", math.ceil(wait))
            if wait := _wait(self._global, self.global_limit, self.global_window, now):
                return Decision(False, "global", math.ceil(wait))

            if self.per_client:
                if hits is None:
                    self._make_room(now)
                    hits = self._clients[client] = deque()
                hits.append(now)
            if self.global_limit:
                self._global.append(now)
            return ALLOWED

    def tracked_clients(self) -> int:
        with self._lock:
            return len(self._clients)

    def _make_room(self, now: float) -> None:
        """Keep the client table bounded: drop idle clients, then the oldest if still full."""
        if len(self._clients) < self.max_clients:
            return
        idle = now - self.client_window
        for key in [k for k, hits in self._clients.items() if not hits or hits[-1] <= idle]:
            del self._clients[key]
        while len(self._clients) >= self.max_clients:
            del self._clients[next(iter(self._clients))]


def client_address(request: Request, trusted_proxy_hops: int) -> str:
    """The address to rate-limit: the TCP peer, or the one the outermost trusted proxy saw."""
    peer = request.client.host if request.client else "unknown"
    if trusted_proxy_hops == 0:
        return peer
    forwarded = [
        part.strip()
        for header in request.headers.getlist("x-forwarded-for")
        for part in header.split(",")
        if part.strip()
    ]
    if len(forwarded) < trusted_proxy_hops:
        return peer  # not behind as many proxies as configured: do not trust the header
    return forwarded[-trusted_proxy_hops]
