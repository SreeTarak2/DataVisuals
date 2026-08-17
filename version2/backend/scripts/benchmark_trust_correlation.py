"""
Trust Correlation Benchmark
===========================

Generates synthetic ``interaction_signals`` data, runs the
``TrustCorrelationService.correlate()`` method, and reports timing breakdowns.

Data volume benchmarked:
- 1,000 trust adjustment signals across 10+ metric names
- 5,000 engagement signals (queries, follow-ups, corrections, delight)
  randomly distributed within the trust adjustment time windows

Steps:
1. Insert synthetic signals into MongoDB (``benchmark_signals`` collection)
2. Run ``TrustCorrelationService.correlate()`` with the test user
3. Measure and report timing at each stage
4. Clean up all test data

Usage:
    cd version2/backend && python scripts/benchmark_trust_correlation.py
"""

import asyncio
import logging
import random
import sys
import time
from datetime import datetime, timedelta, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("benchmark")

# Test identifiers — deleted at cleanup
TEST_USER_ID = "__benchmark_test_user__"
TEST_WORKSPACE_ID = "__benchmark_test_workspace__"

# Data volume
NUM_TRUST_SIGNALS = 1000
NUM_ENGAGEMENT_SIGNALS = 5000

# Metric names to distribute trust adjustments across
METRIC_NAMES = [
    "revenue", "mrr", "arr", "churn", "retention",
    "conversion_rate", "arpu", "ltv", "cac", "gross_margin",
    "net_profit", "operating_expenses", "customer_count", "avg_order_value",
]

# Engagement signal types to generate
ENGAGEMENT_TYPES = ["query", "follow_up", "correction", "delight"]

# Time window: all signals generated within the last N hours
_TIME_SPAN_HOURS = 72
_LOOKAHEAD_MINUTES = 5


def _generate_trust_signals(count: int) -> list[dict]:
    """Generate ``count`` trust adjustment signals across multiple metrics."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    signals = []
    base_time = now - timedelta(hours=_TIME_SPAN_HOURS)

    for i in range(count):
        ts = base_time + timedelta(
            hours=random.uniform(0, _TIME_SPAN_HOURS),
        )
        metric_name = random.choice(METRIC_NAMES)
        signals.append({
            "signal_type": "trust_adjustment",
            "user_id": TEST_USER_ID,
            "workspace_id": TEST_WORKSPACE_ID,
            "dataset_id": f"benchmark_ds_{random.randint(1, 5)}",
            "target_id": f"trust:{metric_name}:benchmark",
            "target_metadata": {
                "metric_name": metric_name,
                "definition": f"{metric_name} is the recognized {metric_name} amount",
                "formula": f"SUM({metric_name}_amount)" if random.random() > 0.5 else None,
                "confidence": round(random.uniform(0.6, 0.99), 3),
                "was_augmented": True,
            },
            "weight": 2.5,
            "timestamp": ts,
            "source": "trust_verifier",
        })

    random.shuffle(signals)
    logger.info("  Generated %d trust adjustment signals", len(signals))
    return signals


def _generate_engagement_signals(
    trust_signals: list[dict],
    count: int,
) -> list[dict]:
    """
    Generate ``count`` engagement signals placed near trust adjustment times.

    ~70% of engagement signals are placed within the lookahead window of a trust
    adjustment (simulating user engagement after a correction). The remaining
    30% are placed at random unrelated times (simulating normal activity).
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    signals = []
    base_time = now - timedelta(hours=_TIME_SPAN_HOURS)
    lookahead = timedelta(minutes=_LOOKAHEAD_MINUTES)

    # Pick ~70% of trust timestamps to cluster engagement around
    trust_timestamps = [s["timestamp"] for s in trust_signals]
    cluster_times = random.sample(
        trust_timestamps,
        min(len(trust_timestamps), int(count * 0.7)),
    )

    for i in range(count):
        if i < len(cluster_times) and cluster_times:
            # Place within lookahead window of a trust adjustment
            adj_ts = random.choice(cluster_times)
            offset = timedelta(seconds=random.uniform(1, _LOOKAHEAD_MINUTES * 60))
            ts = adj_ts + offset
        else:
            # Random time within the span
            ts = base_time + timedelta(hours=random.uniform(0, _TIME_SPAN_HOURS))

        signal_type = random.choice(ENGAGEMENT_TYPES)
        signals.append({
            "signal_type": signal_type,
            "user_id": TEST_USER_ID,
            "workspace_id": TEST_WORKSPACE_ID,
            "dataset_id": f"benchmark_ds_{random.randint(1, 5)}",
            "target_id": f"{signal_type}:benchmark:{i}",
            "target_metadata": {
                "topic": random.choice([
                    "trend", "comparison", "composition", "diagnosis", "general",
                ]),
                "query_preview": f"benchmark query {i}"[:200],
            },
            "weight": 1.0,
            "timestamp": ts,
            "source": "benchmark",
        })

    random.shuffle(signals)
    logger.info("  Generated %d engagement signals", len(signals))
    return signals


async def _insert_signals(db, collection_name: str, signals: list[dict]) -> float:
    """Insert signals in batches, return elapsed seconds."""
    batch_size = 500
    total = len(signals)
    inserted = 0
    start = time.perf_counter()

    for i in range(0, total, batch_size):
        batch = signals[i:i + batch_size]
        collection = db[collection_name]
        await collection.insert_many(batch, ordered=False)
        inserted += len(batch)
        if inserted % 1000 == 0 or inserted == total:
            pct = inserted / total * 100
            logger.info("    Inserted %d/%d (%.0f%%)", inserted, total, pct)

    elapsed = time.perf_counter() - start
    return elapsed


async def _cleanup(db, collection_name: str) -> float:
    """Delete all benchmark signals, return elapsed seconds."""
    start = time.perf_counter()
    result = await db[collection_name].delete_many({
        "user_id": TEST_USER_ID,
    })
    elapsed = time.perf_counter() - start
    logger.info("  Deleted %d benchmark signals in %.2fs", result.deleted_count, elapsed)
    return elapsed


async def main():
    logger.info("=" * 60)
    logger.info("TRUST CORRELATION BENCHMARK")
    logger.info("=" * 60)
    logger.info("")

    # ── 1. Connect to MongoDB ──────────────────────────────────────────
    logger.info("[1/5] Connecting to MongoDB...")
    from db.database import connect_to_mongo, get_database
    from motor.motor_asyncio import AsyncIOMotorClient
    from core.config import settings

    await connect_to_mongo()
    db = get_database()
    collection_name = "interaction_signals"

    logger.info("  Connected to %s/%s", settings.MONGODB_URL[:40], settings.DATABASE_NAME)

    # ── 2. Generate synthetic data ─────────────────────────────────────
    logger.info("")
    logger.info("[2/5] Generating %d trust + %d engagement signals...",
                NUM_TRUST_SIGNALS, NUM_ENGAGEMENT_SIGNALS)

    gen_start = time.perf_counter()
    trust_signals = _generate_trust_signals(NUM_TRUST_SIGNALS)
    engagement_signals = _generate_engagement_signals(trust_signals, NUM_ENGAGEMENT_SIGNALS)
    all_signals = trust_signals + engagement_signals
    gen_elapsed = time.perf_counter() - gen_start
    logger.info("  Generated %d total signals in %.2fs", len(all_signals), gen_elapsed)

    # ── 3. Insert into MongoDB ─────────────────────────────────────────
    logger.info("")
    logger.info("[3/5] Inserting %d signals into %s...", len(all_signals), collection_name)

    insert_elapsed = await _insert_signals(db, collection_name, all_signals)
    logger.info("  Inserted %d signals in %.2fs (%.0f signals/s)",
                len(all_signals), insert_elapsed, len(all_signals) / insert_elapsed)

    # ── 4. Run correlation (the actual benchmark) ──────────────────────
    logger.info("")
    logger.info("[4/5] Running TrustCorrelationService.correlate()...")

    from services.learning.trust_correlation import trust_correlation_service

    # Warm up: run once to ensure indexes and connections are primed
    logger.info("  Warming up...")
    await trust_correlation_service.correlate(
        workspace_id=TEST_WORKSPACE_ID,
        user_id=TEST_USER_ID,
    )

    # Run 5 iterations and report the average
    NUM_RUNS = 5
    timings = []

    for run in range(NUM_RUNS):
        run_start = time.perf_counter()
        report = await trust_correlation_service.correlate(
            workspace_id=TEST_WORKSPACE_ID,
            user_id=TEST_USER_ID,
        )
        run_elapsed = time.perf_counter() - run_start
        timings.append(run_elapsed)
        logger.info("  Run %d/%d: %.4fs — %d metrics, %d total adjustments",
                    run + 1, NUM_RUNS, run_elapsed,
                    report.unique_metrics, report.total_trust_adjustments)

    # ── 5. Clean up ────────────────────────────────────────────────────
    logger.info("")
    logger.info("[5/5] Cleaning up benchmark data...")
    cleanup_elapsed = await _cleanup(db, collection_name)

    # ── Report ─────────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("BENCHMARK RESULTS")
    logger.info("=" * 60)
    logger.info("")

    avg_time = sum(timings) / len(timings)
    min_time = min(timings)
    max_time = max(timings)

    logger.info("Data volume:")
    logger.info("  Trust adjustments:  %d", NUM_TRUST_SIGNALS)
    logger.info("  Engagement signals: %d", NUM_ENGAGEMENT_SIGNALS)
    logger.info("  Distinct metrics:   %d", report.unique_metrics)
    logger.info("")
    logger.info("Timing (%d runs, after warmup):" % NUM_RUNS)
    logger.info("  Average: %.4fs (%.1fms)" % (avg_time, avg_time * 1000))
    logger.info("  Min:     %.4fs (%.1fms)" % (min_time, min_time * 1000))
    logger.info("  Max:     %.4fs (%.1fms)" % (max_time, max_time * 1000))
    logger.info("  Stddev:  %.4fs" % (
        (sum((t - avg_time) ** 2 for t in timings) / len(timings)) ** 0.5
    ))
    logger.info("")
    logger.info("Stage breakdown:")
    logger.info("  Data generation: %.2fs", gen_elapsed)
    logger.info("  DB insertion:    %.2fs (%.0f signals/s)",
                insert_elapsed, len(all_signals) / insert_elapsed)
    logger.info("  Correlation:     avg %.2fs (%d runs)", avg_time, NUM_RUNS)
    logger.info("  Cleanup:         %.2fs", cleanup_elapsed)
    logger.info("")
    logger.info("Report summary:")
    logger.info("  Overall engagement rate: %.2f", report.overall_engagement_rate)
    logger.info("  Overall satisfaction:    %.2f", report.overall_satisfaction)
    logger.info("  Top metric by triggers:  %s (%d)",
                report.top_metrics_by_trigger[0].metric_name,
                report.top_metrics_by_trigger[0].trigger_count
                if report.top_metrics_by_trigger else "N/A",)
    logger.info("=" * 60)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
