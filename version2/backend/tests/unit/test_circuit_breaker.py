import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import time
import pytest
from unittest.mock import patch, MagicMock


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        from services.retries.async_utils import CircuitBreaker

        cb = CircuitBreaker(fail_threshold=3, reset_timeout=60)
        assert cb.state_name == "closed"
        assert cb.is_allowed() is True
        assert cb.is_open() is False

    def test_transitions_to_open_after_threshold_failures(self):
        from services.retries.async_utils import CircuitBreaker

        cb = CircuitBreaker(fail_threshold=3, reset_timeout=60)
        for _ in range(3):
            cb.record_failure()
        assert cb.state_name == "open"
        assert cb.is_allowed() is False
        assert cb.is_open() is True

    def test_open_transitions_to_half_open_after_reset_timeout(self):
        from services.retries.async_utils import CircuitBreaker

        cb = CircuitBreaker(fail_threshold=2, reset_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state_name == "open"
        time.sleep(0.15)
        assert cb.is_allowed() is True
        assert cb.state_name == "half_open"

    def test_half_open_success_transitions_to_closed(self):
        from services.retries.async_utils import CircuitBreaker

        cb = CircuitBreaker(fail_threshold=2, reset_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.is_allowed()
        assert cb.state_name == "half_open"
        cb.record_success()
        assert cb.state_name == "closed"

    def test_half_open_failure_transitions_to_open(self):
        from services.retries.async_utils import CircuitBreaker

        cb = CircuitBreaker(fail_threshold=2, reset_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.is_allowed()
        cb.record_failure()
        assert cb.state_name == "open"

    def test_is_open_backward_compatible(self):
        from services.retries.async_utils import CircuitBreaker

        cb = CircuitBreaker(fail_threshold=1, reset_timeout=60)
        assert cb.is_open() is False
        cb.record_failure()
        assert cb.is_open() is True

    def test_error_rate_window_prunes_old_failures(self):
        from services.retries.async_utils import CircuitBreaker

        cb = CircuitBreaker(fail_threshold=3, reset_timeout=60, error_rate_window=0.05)
        cb.record_failure()
        time.sleep(0.1)
        cb.record_failure()
        assert len(cb.failure_timestamps) == 1  # old one pruned, new one added

    def test_record_success_increments_counter(self):
        from services.retries.async_utils import CircuitBreaker

        cb = CircuitBreaker()
        cb.record_success()
        assert cb.total_successes == 1

    def test_record_failure_increments_counter(self):
        from services.retries.async_utils import CircuitBreaker

        cb = CircuitBreaker()
        cb.record_failure()
        assert cb.total_failures == 1


class TestBreakerRegistry:
    def test_register_and_get(self):
        from services.retries.async_utils import BreakerRegistry, CircuitBreaker

        BreakerRegistry.reset()
        cb = CircuitBreaker(fail_threshold=3, reset_timeout=30)
        BreakerRegistry.register("test:service", cb)
        retrieved = BreakerRegistry.get("test:service")
        assert retrieved is cb
        assert retrieved._name == "test:service"

    def test_get_nonexistent_returns_none(self):
        from services.retries.async_utils import BreakerRegistry

        BreakerRegistry.reset()
        assert BreakerRegistry.get("nonexistent") is None

    def test_available_returns_names(self):
        from services.retries.async_utils import BreakerRegistry, CircuitBreaker

        BreakerRegistry.reset()
        BreakerRegistry.register("a", CircuitBreaker())
        BreakerRegistry.register("b", CircuitBreaker())
        av = BreakerRegistry.available()
        assert "a" in av
        assert "b" in av

    def test_status_returns_state_map(self):
        from services.retries.async_utils import BreakerRegistry, CircuitBreaker

        BreakerRegistry.reset()
        BreakerRegistry.register("x", CircuitBreaker())
        st = BreakerRegistry.status()
        assert st["x"] == "closed"

    def test_reset_clears_all(self):
        from services.retries.async_utils import BreakerRegistry, CircuitBreaker

        BreakerRegistry.reset()
        BreakerRegistry.register("x", CircuitBreaker())
        BreakerRegistry.reset()
        assert BreakerRegistry.available() == []


class TestRetryAsync:
    @pytest.mark.asyncio
    async def test_retry_async_succeeds_eventually(self):
        from services.retries.async_utils import retry_async

        call_count = 0

        async def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "success"

        result = await retry_async(flaky_fn, attempts=3)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_raises_after_exhaustion(self):
        from services.retries.async_utils import retry_async

        async def always_fails():
            raise ValueError("always")

        with pytest.raises(ValueError, match="always"):
            await retry_async(always_fails, attempts=2)
