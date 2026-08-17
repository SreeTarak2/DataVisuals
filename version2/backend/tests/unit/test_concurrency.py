import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest


@pytest.mark.asyncio
async def test_try_acquire_returns_true_first():
    from agents.resilience.concurrency import AgentConcurrencyLimiter

    limiter = AgentConcurrencyLimiter()
    assert await limiter.try_acquire("TestAgent") is True


@pytest.mark.asyncio
async def test_try_acquire_exhausts_at_limit():
    from agents.resilience.concurrency import AgentConcurrencyLimiter

    limiter = AgentConcurrencyLimiter()
    assert await limiter.try_acquire("TestAgent") is True
    assert await limiter.try_acquire("TestAgent") is True
    assert await limiter.try_acquire("TestAgent") is True
    assert await limiter.try_acquire("TestAgent") is False


@pytest.mark.asyncio
async def test_release_restores_slot():
    from agents.resilience.concurrency import AgentConcurrencyLimiter

    limiter = AgentConcurrencyLimiter()
    await limiter.try_acquire("TestAgent")
    await limiter.try_acquire("TestAgent")
    await limiter.try_acquire("TestAgent")
    assert await limiter.try_acquire("TestAgent") is False

    limiter.release("TestAgent")
    assert await limiter.try_acquire("TestAgent") is True


@pytest.mark.asyncio
async def test_different_agent_types_independent():
    from agents.resilience.concurrency import AgentConcurrencyLimiter

    limiter = AgentConcurrencyLimiter()
    for _ in range(3):
        assert await limiter.try_acquire("AgentA") is True
    assert await limiter.try_acquire("AgentA") is False
    assert await limiter.try_acquire("AgentB") is True


@pytest.mark.asyncio
async def test_release_twice_does_not_crash():
    from agents.resilience.concurrency import AgentConcurrencyLimiter

    limiter = AgentConcurrencyLimiter()
    await limiter.try_acquire("TestAgent")
    limiter.release("TestAgent")
    limiter.release("TestAgent")


@pytest.mark.asyncio
async def test_release_unacquired_does_not_crash():
    from agents.resilience.concurrency import AgentConcurrencyLimiter

    limiter = AgentConcurrencyLimiter()
    limiter.release("NeverAcquired")


@pytest.mark.asyncio
async def test_acquire_context_manager():
    from agents.resilience.concurrency import AgentConcurrencyLimiter

    limiter = AgentConcurrencyLimiter()
    ctx = await limiter.acquire("CtxAgent")
    async with ctx:
        assert limiter._semaphores["CtxAgent"]._value == 2
    assert limiter._semaphores["CtxAgent"]._value == 3


@pytest.mark.asyncio
async def test_custom_max_concurrency():
    from agents.resilience.concurrency import AgentConcurrencyLimiter

    limiter = AgentConcurrencyLimiter()
    for _ in range(5):
        assert await limiter.try_acquire("ProfileAgent") is True
    assert await limiter.try_acquire("ProfileAgent") is False


@pytest.mark.asyncio
async def test_release_restores_full_slots():
    from agents.resilience.concurrency import AgentConcurrencyLimiter

    limiter = AgentConcurrencyLimiter()
    await limiter.try_acquire("TestAgent")
    await limiter.try_acquire("TestAgent")
    limiter.release("TestAgent")
    limiter.release("TestAgent")
    assert await limiter.try_acquire("TestAgent") is True
    assert await limiter.try_acquire("TestAgent") is True
    assert await limiter.try_acquire("TestAgent") is True
    assert await limiter.try_acquire("TestAgent") is False
