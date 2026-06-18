"""Lightweight metrics wrapper with optional Prometheus support.

Provides:
- incr(name, amount=1)
- observe(name, value)
- timeit(name): context manager returning elapsed seconds

If `prometheus_client` is unavailable, falls back to no-op counters and logging.
"""
from contextlib import contextmanager
import time
import logging

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram

    _PROM_AVAILABLE = True
except Exception:
    _PROM_AVAILABLE = False

_metrics_store = {}


def _ensure_counter(name: str):
    if name in _metrics_store:
        return _metrics_store[name]
    if _PROM_AVAILABLE:
        c = Counter(name, f"Auto-generated counter {name}")
    else:
        c = None
    _metrics_store[name] = c
    return c


def _ensure_histogram(name: str):
    if name in _metrics_store:
        return _metrics_store[name]
    if _PROM_AVAILABLE:
        h = Histogram(name, f"Auto-generated histogram {name}")
    else:
        h = None
    _metrics_store[name] = h
    return h


def incr(name: str, amount: int = 1) -> None:
    c = _ensure_counter(name)
    if c is not None:
        try:
            c.inc(amount)
        except Exception as e:
            logger.debug("metrics incr failed: %s", e)
    else:
        logger.debug("metric %s += %d", name, amount)


def observe(name: str, value: float) -> None:
    h = _ensure_histogram(name)
    if h is not None:
        try:
            h.observe(value)
        except Exception as e:
            logger.debug("metrics observe failed: %s", e)
    else:
        logger.debug("metric %s observe %f", name, value)


@contextmanager
def timeit(name: str):
    start = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start
        observe(name, elapsed)
        logger.debug("metric %s elapsed %f", name, elapsed)
