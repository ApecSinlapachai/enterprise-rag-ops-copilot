"""Thread-safe IP-hashed (SHA-256) sliding-window rate limiter."""

from __future__ import annotations

import hashlib
import math
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, Request, status

MINUTE_WINDOW_SECONDS = 60.0
DAY_WINDOW_SECONDS = 86_400.0


def extract_client_ip(request: Request) -> str:
    """Read the first hop of X-Forwarded-For behind Render/Vercel proxies, else client.host."""
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        first_hop = forwarded.split(",", 1)[0].strip()
        if first_hop:
            return first_hop
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def hash_client_ip(request: Request) -> str:
    """Return a privacy-preserving SHA-256 hex digest of the client IP."""
    client_ip = extract_client_ip(request)
    return hashlib.sha256(client_ip.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Outcome of a sliding-window rate limit check."""

    allowed: bool
    retry_after_seconds: int
    limit_window: Literal["minute", "day"] | None
    remaining_minute: int
    remaining_day: int


class SlidingWindowRateLimiter:
    """In-memory, thread-safe sliding-window rate limiter keyed by SHA-256 IP hash."""

    def __init__(
        self,
        *,
        per_min: int = 15,
        per_day: int = 60,
        max_tracked_keys: int = 10_000,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if per_min < 1:
            raise ValueError("per_min must be >= 1")
        if per_day < 1:
            raise ValueError("per_day must be >= 1")
        if max_tracked_keys < 1:
            raise ValueError("max_tracked_keys must be >= 1")
        self.per_min = per_min
        self.per_day = per_day
        self.max_tracked_keys = max_tracked_keys
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def _evict_stale_or_oldest(self, day_cutoff: float) -> None:
        """Remove keys whose 24h window is empty, then oldest keys if still at capacity."""
        stale_keys = [
            existing_key
            for existing_key, dq in self._hits.items()
            if not dq or dq[-1] <= day_cutoff
        ]
        for stale_key in stale_keys:
            del self._hits[stale_key]

        while len(self._hits) >= self.max_tracked_keys:
            oldest_key = next(iter(self._hits))
            del self._hits[oldest_key]

    def check_and_consume(self, key: str) -> RateLimitDecision:
        """Check minute and day windows for key; consume a slot if allowed."""
        now = self._clock()
        minute_cutoff = now - MINUTE_WINDOW_SECONDS
        day_cutoff = now - DAY_WINDOW_SECONDS

        with self._lock:
            dq = self._hits.get(key)
            if dq is None:
                if len(self._hits) >= self.max_tracked_keys:
                    self._evict_stale_or_oldest(day_cutoff)
                dq = deque()
                self._hits[key] = dq
            else:
                while dq and dq[0] <= day_cutoff:
                    dq.popleft()
                if not dq:
                    # Re-insert empty deque so insertion order reflects recency.
                    del self._hits[key]
                    self._hits[key] = dq

            day_count = len(dq)
            min_count = 0
            for ts in reversed(dq):
                if ts > minute_cutoff:
                    min_count += 1
                else:
                    break

            if min_count >= self.per_min:
                oldest_min_ts = dq[day_count - self.per_min]
                retry_after = max(1, math.ceil((oldest_min_ts + MINUTE_WINDOW_SECONDS) - now))
                return RateLimitDecision(
                    allowed=False,
                    retry_after_seconds=retry_after,
                    limit_window="minute",
                    remaining_minute=0,
                    remaining_day=max(0, self.per_day - day_count),
                )

            if day_count >= self.per_day:
                oldest_day_ts = dq[0]
                retry_after = max(1, math.ceil((oldest_day_ts + DAY_WINDOW_SECONDS) - now))
                return RateLimitDecision(
                    allowed=False,
                    retry_after_seconds=retry_after,
                    limit_window="day",
                    remaining_minute=max(0, self.per_min - min_count),
                    remaining_day=0,
                )

            dq.append(now)
            return RateLimitDecision(
                allowed=True,
                retry_after_seconds=0,
                limit_window=None,
                remaining_minute=max(0, self.per_min - (min_count + 1)),
                remaining_day=max(0, self.per_day - (day_count + 1)),
            )


def enforce_rate_limit(request: Request) -> str:
    """Enforce per-IP sliding-window rate limits and return the SHA-256 IP hash."""
    ip_hash = hash_client_ip(request)
    limiter: SlidingWindowRateLimiter | None = getattr(request.app.state, "rate_limiter", None)
    if limiter is not None:
        decision = limiter.check_and_consume(ip_hash)
        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded ({decision.limit_window} window). "
                    f"Please retry after {decision.retry_after_seconds} seconds."
                ),
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )
    return ip_hash
