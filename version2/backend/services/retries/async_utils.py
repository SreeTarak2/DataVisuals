"""Simple async retry helper and in-memory circuit breaker.

Usage:
- await retry_async(coro_fn, *args, attempts=3)
- cb = CircuitBreaker(fail_threshold=5, reset_timeout=60)
- cb.record_success()/record_failure()
- cb.is_open() to short-circuit
"""
import asyncio
import time
import logging
from typing import Callable, Any, Iterable, Tuple

logger = logging.getLogger(__name__)


async def retry_async(
    fn: Callable, *args, attempts: int = 3, base_delay: float = 0.5, factor: float = 2.0, exceptions: Tuple = (Exception,), **kwargs
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


class CircuitBreaker:
    def __init__(self, fail_threshold: int = 5, reset_timeout: int = 60):
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self.last_failure = 0.0

    def record_success(self) -> None:
        self.failure_count = 0
        self.last_failure = 0.0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure = time.time()

    def is_open(self) -> bool:
        if self.failure_count >= self.fail_threshold:
            # if within reset_timeout, circuit remains open
            if time.time() - self.last_failure < self.reset_timeout:
                return True
            # else half-open: allow attempt but keep track
            return False
        return False
