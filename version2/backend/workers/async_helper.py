import asyncio
from typing import Any, Coroutine
import logging

logger = logging.getLogger(__name__)

_worker_loop = None


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run async coroutine in a worker context.
    
    Handles event loop setup for Celery workers which run in separate processes.
    Gracefully handles event loop conflicts.
    """
    global _worker_loop

    try:
        # Check if there's already a running loop
        try:
            current_loop = asyncio.get_running_loop()
            # If we get here, there's a running loop, which shouldn't happen in a worker
            logger.warning("Detected running event loop in worker context, creating new loop")
            # Create a new loop for this task
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            return new_loop.run_until_complete(coro)
        except RuntimeError:
            # No running loop, proceed normally
            pass

        if _worker_loop is None or _worker_loop.is_closed():
            _worker_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_worker_loop)

        return _worker_loop.run_until_complete(coro)
    except Exception as e:
        logger.error(f"Error running async coroutine: {e}")
        raise


__all__ = ["run_async"]
