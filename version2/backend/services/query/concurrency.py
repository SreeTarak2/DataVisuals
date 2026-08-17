"""
QueryConcurrencyController
=========================
Manages the number of concurrently executing DuckDB queries.

Uses an asyncio.Semaphore to limit DuckDB workers and a FIFO queue
for queries that arrive at capacity.  Designed to prevent resource
exhaustion from concurrent SQL execution.

Architecture::

    POST /execute  ──▶  acquire(semaphore)?  ──yes──▶  run_in_executor()
                           │ no
                           ▼
                    wait_queue.put(query_id)
                    (status = "queued")

    Slot released  ──▶  dequeue next query  ──▶  run_in_executor()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Coroutine

from core.config import settings

logger = logging.getLogger(__name__)


class QueryConcurrencyController:
    """Limit concurrent DuckDB executions with a FIFO wait queue.

    Parameters
    ----------
    max_workers:
        Maximum number of queries executing simultaneously.
    max_queue:
        Maximum number of queries allowed in the wait queue.
        Beyond this, new submissions are rejected with 429.
    """

    def __init__(
        self,
        max_workers: int | None = None,
        max_queue: int | None = None,
    ):
        self._max_workers = max_workers or settings.QUERY_MAX_WORKERS
        self._max_queue = max_queue or settings.QUERY_MAX_QUEUE
        self._semaphore = asyncio.Semaphore(self._max_workers)
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=self._max_queue)
        self._dequeue_event: asyncio.Event = asyncio.Event()
        self._dequeue_task: asyncio.Task | None = None
        self._pending: dict[str, Callable[[], Coroutine]] = {}  # query_id → runner

    # ── Public API ──────────────────────────────────────────────────────────

    async def try_acquire(self, query_id: str) -> bool | None:
        """Attempt to acquire an execution slot.

        Returns
        -------
        True
            Slot acquired — caller should start execution immediately.
        False
            Slot not available, but query was placed in the wait queue.
            Caller should set status to ``"queued"``.
        None
            Queue is full — caller should reject with 429.
        """
        if not self._semaphore.locked():
            await self._semaphore.acquire()
            return True

        try:
            self._queue.put_nowait(query_id)
            logger.info(
                "[Concurrency] %s queued (queue depth: %d/%d)",
                query_id[:12],
                self._queue.qsize(),
                self._max_queue,
            )
            return False  # queued
        except asyncio.QueueFull:
            logger.warning(
                "[Concurrency] Queue full; rejecting %s", query_id[:12]
            )
            return None  # reject

    def register_runner(self, query_id: str, coro: Callable[[], Coroutine]) -> None:
        """Register a coroutine to be called when a slot opens for *query_id*."""
        self._pending[query_id] = coro
        self._ensure_dequeue_loop()

    def release(self) -> None:
        """Release an execution slot and signal the dequeue loop."""
        self._semaphore.release()
        self._dequeue_event.set()

    async def count_waiting(self) -> int:
        """Return the number of queries currently in the wait queue."""
        return self._queue.qsize()

    # ── Internal ────────────────────────────────────────────────────────────

    def _ensure_dequeue_loop(self) -> None:
        if self._dequeue_task is None or self._dequeue_task.done():
            self._dequeue_task = asyncio.create_task(self._dequeue_loop())

    async def _dequeue_loop(self) -> None:
        """Background loop: wait for slot releases and dequeue next query."""
        while True:
            await self._dequeue_event.wait()
            self._dequeue_event.clear()

            # Dequeue as many as have slots available
            while not self._semaphore.locked() and not self._queue.empty():
                query_id = self._queue.get_nowait()
                runner = self._pending.pop(query_id, None)
                if runner:
                    await self._semaphore.acquire()
                    logger.info(
                        "[Concurrency] Dequeuing %s (queue depth: %d)",
                        query_id[:12],
                        self._queue.qsize(),
                    )
                    asyncio.create_task(runner())
                else:
                    # Runner disappeared (e.g. cancelled before slot opened)
                    logger.warning(
                        "[Concurrency] No runner found for dequeued %s",
                        query_id[:12],
                    )

    def cleanup(self, query_id: str) -> None:
        """Remove a cancelled/expired query from pending tracking."""
        self._pending.pop(query_id, None)


# Module-level singleton
concurrency_controller = QueryConcurrencyController()
