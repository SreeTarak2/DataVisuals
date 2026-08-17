"""
Scheduled Belief Decay Task
============================
Background worker that periodically applies temporal confidence decay
to all ChromaDB beliefs, regardless of whether the user has queried
them recently.

Without this task, beliefs about topics the user never revisits stay
at their initial confidence forever — a stale "Revenue is $120K" belief
from 2024 still sits at 0.95 if nobody asks about it.

The decay formula (same as BeliefStore._apply_decay):
    c(t) = c0 * e^(-λt)
    where λ = 0.01 (1% per day), floor at 0.3

Schedule: runs every DECAY_INTERVAL_HOURS (default 6). Each run is
marker-gated in MongoDB so that in multi-replica deployments only
ONE worker executes the decay pass.
"""

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────
DECAY_INTERVAL_HOURS = 6  # Run every 6 hours
DECAY_INTERVAL_SECONDS = DECAY_INTERVAL_HOURS * 3600

# Marker collection for coordination across replicas
_MARKER_COLLECTION = "maintenance_markers"
_MARKER_ID = "belief_decay_last_run"
_DECAY_MIN_INTERVAL = 3600  # Minimum 1 hour between runs (safety guard)


async def _acquire_decay_lock() -> bool:
    """Atomically claim the decay run slot via MongoDB upsert.

    Only one worker across all replicas succeeds — the rest skip.
    Returns True if this worker should run the decay pass.
    """
    try:
        from db.database import get_database
        db = get_database()
        collection = db[_MARKER_COLLECTION]

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        result = await collection.find_one_and_update(
            {"_id": _MARKER_ID},
            {
                "$set": {
                    "last_run": now,
                    "worker": asyncio.current_task().get_name(),
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
            return_document=False,  # Return the document BEFORE update
        )

        if result is None:
            # First run ever — this worker gets it
            return True

        last_run = result.get("last_run")
        if last_run is None:
            return True

        # Type-safe: last_run could be datetime or ISO string
        if isinstance(last_run, datetime):
            elapsed = (datetime.now(timezone.utc).replace(tzinfo=None) - last_run).total_seconds()
        elif isinstance(last_run, str):
            elapsed = (
                datetime.now(timezone.utc).replace(tzinfo=None)
                - datetime.fromisoformat(last_run.replace("Z", "+00:00")).replace(tzinfo=None)
            ).total_seconds()
        else:
            elapsed = _DECAY_MIN_INTERVAL + 1  # Force run if format is unexpected

        return elapsed >= _DECAY_MIN_INTERVAL

    except Exception as e:
        logger.warning(f"[BeliefDecay] Failed to acquire lock (non-critical): {e}")
        return False


async def decay_all_beliefs() -> int:
    """Iterate all ChromaDB collections and apply temporal decay.

    Returns the total number of beliefs whose confidence was updated.
    Runs inside a single worker across all replicas (marker-gated).
    """
    try:
        from agents.belief.belief_store import get_belief_store

        store = get_belief_store()
    except Exception as e:
        logger.error(f"[BeliefDecay] Failed to get BeliefStore: {e}")
        return 0

    return await store.decay_all_collections()


async def belief_decay_loop():
    """Background loop that runs the decay pass on schedule.

    Launched as a fire-and-forget task during startup. Each iteration:
    1. Sleeps for DECAY_INTERVAL_SECONDS
    2. Acquires the MongoDB marker lock (only one replica proceeds)
    3. Runs decay_all_beliefs()
    4. Logs results

    The loop never raises — all errors are caught and logged.
    """
    logger.info(
        f"[BeliefDecay] Background task started — running every "
        f"{DECAY_INTERVAL_HOURS}h (lock: MongoDB marker)"
    )

    while True:
        try:
            await asyncio.sleep(DECAY_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("[BeliefDecay] Background task cancelled — shutting down")
            return

        try:
            if not await _acquire_decay_lock():
                logger.debug("[BeliefDecay] Another worker handled this interval — skipping")
                continue

            updated = await decay_all_beliefs()
            if updated > 0:
                logger.info(
                    f"[BeliefDecay] Decayed confidence for {updated} beliefs "
                    f"across all users"
                )
            else:
                logger.debug("[BeliefDecay] No beliefs needed decay — all within threshold")

        except asyncio.CancelledError:
            logger.info("[BeliefDecay] Background task cancelled during run — shutting down")
            return
        except Exception as e:
            logger.error(f"[BeliefDecay] Run failed (non-critical): {e}")


async def start_belief_decay_task():
    """Start the background decay loop as a daemon task.

    Call this during application startup. The task is automatically
    cancelled when the event loop shuts down.
    """
    task = asyncio.create_task(belief_decay_loop())
    task.set_name("belief_decay_task")
    logger.info("[BeliefDecay] Background task scheduled")
    return task
