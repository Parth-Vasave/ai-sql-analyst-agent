from __future__ import annotations

from typing import Any

import pytest
from starlette.requests import Request

from app.api.rate_limit import DAY, MINUTE, RateLimiter, client_address


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def test_client_limit_blocks_the_request_over_the_limit_and_says_when_to_retry(clock: FakeClock) -> None:
    limiter = RateLimiter(3, 0, clock=clock)
    assert all(limiter.hit("a").allowed for _ in range(3))
    clock.advance(20)
    decision = limiter.hit("a")
    assert not decision.allowed
    assert decision.scope == "client"
    assert decision.retry_after_seconds == 40  # the first hit leaves the window at t+60


def test_window_slides(clock: FakeClock) -> None:
    limiter = RateLimiter(2, 0, clock=clock)
    limiter.hit("a")
    clock.advance(30)
    limiter.hit("a")
    clock.advance(30)  # the first hit has left the window, the second has not
    assert limiter.hit("a").allowed
    assert not limiter.hit("a").allowed


def test_clients_are_limited_independently(clock: FakeClock) -> None:
    limiter = RateLimiter(1, 0, clock=clock)
    assert limiter.hit("a").allowed
    assert not limiter.hit("a").allowed
    assert limiter.hit("b").allowed


def test_global_limit_holds_across_clients(clock: FakeClock) -> None:
    limiter = RateLimiter(10, 3, clock=clock)
    assert [limiter.hit(f"client-{i}").allowed for i in range(4)] == [True, True, True, False]
    decision = limiter.hit("someone-new")
    assert decision.scope == "global"
    assert decision.retry_after_seconds == DAY
    clock.advance(DAY)
    assert limiter.hit("someone-new").allowed


def test_refused_requests_do_not_count(clock: FakeClock) -> None:
    limiter = RateLimiter(1, 2, clock=clock)
    assert limiter.hit("a").allowed
    for _ in range(5):  # a client hammering while limited
        assert not limiter.hit("a").allowed
    assert limiter.hit("b").allowed  # the global budget was not used up by the refusals
    clock.advance(MINUTE)
    decision = limiter.hit("a")
    assert not decision.allowed and decision.scope == "global"


def test_zero_turns_a_limit_off(clock: FakeClock) -> None:
    assert all(RateLimiter(0, 0, clock=clock).hit("a").allowed for _ in range(1000))
    only_global = RateLimiter(0, 5, clock=clock)
    assert sum(only_global.hit("a").allowed for _ in range(10)) == 5


def test_retry_after_is_at_least_one_second(clock: FakeClock) -> None:
    limiter = RateLimiter(1, 0, clock=clock)
    limiter.hit("a")
    clock.advance(MINUTE - 0.2)
    assert limiter.hit("a").retry_after_seconds == 1


def test_client_table_stays_bounded(clock: FakeClock) -> None:
    limiter = RateLimiter(5, 0, max_clients=100, clock=clock)
    for i in range(100):
        limiter.hit(f"old-{i}")
    clock.advance(MINUTE)  # all idle now
    limiter.hit("new")
    assert limiter.tracked_clients() == 1
    for i in range(500):  # a burst of distinct addresses within one window
        limiter.hit(f"burst-{i}")
    assert limiter.tracked_clients() <= 100


def make_request(peer: str | None, forwarded: list[str] | None = None) -> Request:
    headers = [(b"x-forwarded-for", value.encode()) for value in forwarded or []]
    scope: dict[str, Any] = {"type": "http", "method": "POST", "path": "/", "headers": headers}
    if peer is not None:
        scope["client"] = (peer, 50000)
    return Request(scope)


def test_client_address_ignores_forwarded_for_by_default() -> None:
    request = make_request("10.0.0.1", ["1.2.3.4"])
    assert client_address(request, 0) == "10.0.0.1"


def test_client_address_uses_the_entry_added_by_the_trusted_proxy() -> None:
    # The client sent a forged first entry; the proxy appended the real address.
    request = make_request("10.0.0.1", ["6.6.6.6, 203.0.113.7"])
    assert client_address(request, 1) == "203.0.113.7"
    two_proxies = make_request("10.0.0.1", ["6.6.6.6, 203.0.113.7, 10.0.0.9"])
    assert client_address(two_proxies, 2) == "203.0.113.7"


def test_client_address_joins_repeated_forwarded_for_headers() -> None:
    request = make_request("10.0.0.1", ["6.6.6.6", "203.0.113.7"])
    assert client_address(request, 1) == "203.0.113.7"


def test_client_address_falls_back_to_the_peer_when_the_header_is_short_or_missing() -> None:
    assert client_address(make_request("10.0.0.1"), 1) == "10.0.0.1"
    assert client_address(make_request("10.0.0.1", ["203.0.113.7"]), 2) == "10.0.0.1"
    assert client_address(make_request(None), 0) == "unknown"
