"""Async retry helpers, in-memory circuit breaker with three-state semantics,
and a global BreakerRegistry for dependency-scoped breakers.

Usage:
    # Retry
    await retry_async(coro_fn, attempts=3)

    # Circuit breaker (per-instance)
    cb = CircuitBreaker(fail_threshold=5, reset_timeout=60)
    if cb.is_allowed():
        try: ...; cb.record_success()
        except: cb.record_failure()

    # BreakerRegistry (global, named)
    BreakerRegistry.register("llm:primary", CircuitBreaker())
    if BreakerRegistry.get("llm:primary").is_allowed():
        ...
"""

import asyncio
import logging
import time
from collections.abc import Callable
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


async def retry_async(
    fn: Callable,
    *args,
    attempts: int = 3,
    base_delay: float = 0.5,
    factor: float = 2.0,
    exceptions: tuple = (Exception,),
    **kwargs,
) -> Any:
    last_exc = None
    delay = base_delay
    for attempt in range(1, attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except exceptions as e:
            last_exc = e
            logger.debug("retry_async attempt %d failed: %s", attempt, e)
            if attempt == attempts:
                break
            await asyncio.sleep(delay)
            delay *= factor
    raise last_exc


class BreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Three-state circuit breaker with error-rate window.

    State machine:
        CLOSED ──(fail_threshold exceeded)──→ OPEN
        OPEN ──(reset_timeout elapsed)──→ HALF_OPEN
        HALF_OPEN ──(success)──→ CLOSED
        HALF_OPEN ──(failure)──→ OPEN

    Maintains backward-compatible API:
        .is_open() — True if OPEN (not HALF_OPEN)
        .record_success()
        .record_failure()
    """

    def __init__(
        self,
        fail_threshold: int = 5,
        reset_timeout: float = 60.0,
        error_rate_window: float = 120.0,
    ):
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.error_rate_window = error_rate_window
        self.state = BreakerState.CLOSED
        self.failure_timestamps: list[float] = []
        self.last_open_time: float = 0.0
        self.total_successes: int = 0
        self.total_failures: int = 0

    # ── Public API ──────────────────────────────────────────────

    def record_success(self) -> None:
        self.total_successes += 1
        if self.state == BreakerState.HALF_OPEN:
            logger.info(
                "[Breaker] HALF_OPEN success → CLOSED (name=%s)", getattr(self, "_name", "?")
            )
            self.state = BreakerState.CLOSED
            self.failure_timestamps.clear()

    def record_failure(self) -> None:
        now = time.monotonic()
        self.failure_timestamps.append(now)
        self.total_failures += 1
        self._prune_old_failures(now)

        if self.state == BreakerState.HALF_OPEN:
            logger.warning(
                "[Breaker] HALF_OPEN failure → OPEN (name=%s)", getattr(self, "_name", "?")
            )
            self.state = BreakerState.OPEN
            self.last_open_time = time.time()
        elif len(self.failure_timestamps) >= self.fail_threshold:
            logger.warning(
                "[Breaker] CLOSED → OPEN (name=%s, failures=%d, threshold=%d)",
                getattr(self, "_name", "?"),
                len(self.failure_timestamps),
                self.fail_threshold,
            )
            self.state = BreakerState.OPEN
            self.last_open_time = time.time()

    def is_open(self) -> bool:
        """Backward-compatible: True only when circuit is OPEN (not HALF_OPEN)."""
        if self.state == BreakerState.OPEN:
            if time.time() - self.last_open_time >= self.reset_timeout:
                logger.info(
                    "[Breaker] OPEN timeout elapsed → HALF_OPEN (name=%s)",
                    getattr(self, "_name", "?"),
                )
                self.state = BreakerState.HALF_OPEN
                return False
            return True
        return False

    def is_allowed(self) -> bool:
        """True if the circuit is CLOSED or HALF_OPEN (allows one trial)."""
        if self.state == BreakerState.CLOSED:
            return True
        if self.state == BreakerState.OPEN:
            if time.time() - self.last_open_time >= self.reset_timeout:
                logger.info(
                    "[Breaker] OPEN timeout elapsed → HALF_OPEN (name=%s)",
                    getattr(self, "_name", "?"),
                )
                self.state = BreakerState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow one trial
        return True

    @property
    def state_name(self) -> str:
        return self.state.value

    # ── Private ─────────────────────────────────────────────────

    def _prune_old_failures(self, now: float) -> None:
        cutoff = now - self.error_rate_window
        self.failure_timestamps = [t for t in self.failure_timestamps if t > cutoff]


class BreakerRegistry:
    """Global registry of named circuit breakers (scoped by dependency)."""

    _breakers: dict[str, CircuitBreaker] = {}

    @classmethod
    def register(cls, name: str, breaker: CircuitBreaker) -> None:
        breaker._name = name
        cls._breakers[name] = breaker
        logger.info(
            "BreakerRegistry registered: %s (threshold=%d, timeout=%.0fs)",
            name,
            breaker.fail_threshold,
            breaker.reset_timeout,
        )

    @classmethod
    def get(cls, name: str) -> CircuitBreaker | None:
        return cls._breakers.get(name)

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._breakers.keys())

    @classmethod
    def status(cls) -> dict[str, str]:
        return {n: b.state_name for n, b in cls._breakers.items()}

    @classmethod
    def reset(cls) -> None:
        cls._breakers.clear()
