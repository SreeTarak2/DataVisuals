#!/usr/bin/env python3
"""
Benchmark: Vectorized Subspace Search vs Old Nested-Loop Approach
==================================================================
Compares the performance of the OLD BeamSearchExplorer (nested Python loops
with filter() + pearsonr()) against the NEW VectorizedSubspaceEngine
(Polars group_by + pl.corr).

Synthetic dataset: 20 numeric columns, 15 categorical columns, 10,000 rows.
This is the scale where the old approach starts to hurt (~50K+ filter operations).

Usage:
    python benchmark/benchmark_subspace_vectorization.py
"""

import sys
import time
import logging
import statistics
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import polars as pl
from scipy import stats

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

sys.path.insert(0, '.')

# ── Import the NEW vectorized engine ──────────────────────────────────────
from services.analysis.enhanced_quis import (
    VectorizedSubspaceEngine,
    EnhancedQUIS,
    QUISInsight,
    InsightGenerator,
    AnalyticalQuestion,
)


# ══════════════════════════════════════════════════════════════════════════
# SYNTHETIC DATASET GENERATOR
# ══════════════════════════════════════════════════════════════════════════

def generate_synthetic_dataset(
    n_rows: int = 10_000,
    n_numeric: int = 20,
    n_categorical: int = 15,
    seed: int = 42,
) -> pl.DataFrame:
    """
    Generate a realistic synthetic dataset with known correlation structure.
    
    Creates:
    - n_numeric numeric columns with varying correlations
    - n_categorical categorical columns with varying cardinality (3-12 unique values)
    - Some numeric columns are correlated globally; some only within specific subspaces
    """
    rng = np.random.RandomState(seed)
    
    data = {}
    
    # Base random data
    base = rng.randn(n_rows)
    
    # ── Numeric columns ──
    for i in range(n_numeric):
        # Mix of independent and correlated columns
        noise = rng.randn(n_rows) * 0.3
        if i < 5:
            # Strongly correlated with base (r ≈ 0.95)
            data[f"metric_{i}"] = base * 0.8 + noise * 0.2
        elif i < 10:
            # Moderately correlated (r ≈ 0.6)
            data[f"metric_{i}"] = base * 0.5 + noise * 0.5
        else:
            # Weakly correlated (r ≈ 0.2)
            data[f"metric_{i}"] = base * 0.2 + noise * 0.8
    
    # ── Embed a strong subspace pattern ──
    # metric_0 and metric_1 are strongly correlated (r ≈ 0.95) globally,
    # but within region="A" the correlation flips to negative (Simpson's Paradox)
    mask_a = np.zeros(n_rows, dtype=bool)
    mask_a[:n_rows // 5] = True  # First 20% are region A
    data["metric_0"] = np.where(
        mask_a,
        -data["metric_1"] * 0.7 + rng.randn(n_rows) * 0.3,  # Negative in subspace
        data["metric_0"]
    )
    
    # ── Categorical columns ──
    categories_pool = {
        "region": ["North", "South", "East", "West", "Central"],
        "department": ["Sales", "Engineering", "Marketing", "Finance", "HR", "Operations"],
        "product_tier": ["Basic", "Premium", "Enterprise"],
        "customer_segment": ["SMB", "Mid-Market", "Enterprise", "Strategic"],
        "channel": ["Direct", "Partner", "Online", "Retail"],
        "priority": ["High", "Medium", "Low"],
        "status": ["Active", "Inactive", "Pending"],
        "industry": ["Tech", "Finance", "Healthcare", "Retail", "Manufacturing", "Energy"],
        "quarter": ["Q1", "Q2", "Q3", "Q4"],
        "cohort": [f"Cohort_{i}" for i in range(8)],
        "source": ["Email", "Web", "Referral", "Social", "Phone"],
        "plan_type": ["Monthly", "Annual", "Bi-Annual"],
        "team_size": ["Small", "Medium", "Large"],
        "engagement": ["Low", "Medium", "High", "Very High"],
        "lifecycle_stage": ["Lead", "Prospect", "Customer", "Churned"],
    }
    
    for col_name, values in categories_pool.items():
        data[col_name] = rng.choice(values, size=n_rows)
    
    # ── Make region correlate with the subspace pattern ──
    # Region A has the Simpson's Paradox for metric_0 vs metric_1
    data["region"] = ["A" if i < n_rows // 5 else rng.choice(
        ["B", "C", "D", "E"]  # Other regions don't show the flip
    ) for i in range(n_rows)]
    
    df = pl.DataFrame(data)
    return df


# ══════════════════════════════════════════════════════════════════════════
# RECONSTRUCT OLD NESTED-LOOP BEAM SEARCH
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class SubspaceCandidate:
    filters: Dict[str, Any]
    score: float = 0.0
    n_samples: int = 0
    depth: int = 0

    def __lt__(self, other):
        return self.score > other.score


def old_nested_loop_beam_search(
    df: pl.DataFrame,
    col1: str,
    col2: str,
    categorical_cols: List[str],
    base_correlation: float,
    base_n: int,
    beam_width: int = 10,
    max_depth: int = 2,
) -> List[Dict[str, Any]]:
    """
    Exact reconstruction of the OLD BeamSearchExplorer.explore_correlation_subspaces.
    
    Uses nested Python loops with DataFrame.filter() + to_numpy() + pearsonr().
    This is what the original code did before VectorizedSubspaceEngine.
    """
    insights = []
    import heapq
    
    # Fisher z-test (copy of QUISStatistics.fisher_z_test)
    def fisher_z_test(r1, n1, r2, n2):
        def r_to_z(r):
            r = np.clip(r, -0.9999, 0.9999)
            return 0.5 * np.log((1 + r) / (1 - r))
        z1 = r_to_z(r1)
        z2 = r_to_z(r2)
        se = np.sqrt(1/(n1 - 3) + 1/(n2 - 3))
        z_stat = (z1 - z2) / se if se > 0 else 0
        p_value = 2 * (1 - stats.norm.cdf(abs(z_stat)))
        return round(z_stat, 4), round(p_value, 6)
    
    # Cohen's q
    def cohens_q(r1, r2):
        def r_to_z(r):
            r = np.clip(r, -0.9999, 0.9999)
            return 0.5 * np.log((1 + r) / (1 - r))
        q = abs(r_to_z(r1) - r_to_z(r2))
        if q < 0.1:
            interp = "negligible"
        elif q < 0.3:
            interp = "small"
        elif q < 0.5:
            interp = "medium"
        else:
            interp = "large"
        return round(q, 4), interp
    
    # Simpson detection
    def detect_simpson(subspace_corr, base_correlation, fisher_p_value, n_subspace):
        signs_flipped = np.sign(subspace_corr) != np.sign(base_correlation)
        if not signs_flipped:
            return False
        return fisher_p_value < 0.05 and n_subspace >= 30
    
    def describe_insight(col1, col2, filters, base_corr, subspace_corr, is_simpson):
        filter_desc = " AND ".join([f"{k}={v}" for k, v in filters.items()])
        if is_simpson:
            return (f"⚠️ SIMPSON'S PARADOX: Correlation between {col1} and {col2} "
                    f"reverses from {base_corr:.2f} to {subspace_corr:.2f} when {filter_desc}")
        else:
            direction = "stronger" if abs(subspace_corr) > abs(base_corr) else "weaker"
            return (f"Correlation between {col1} and {col2} is {direction} "
                    f"({base_corr:.2f} → {subspace_corr:.2f}) when {filter_desc}")
    
    # Initialize beam
    beam = [(0.0, 0, SubspaceCandidate(filters={}, score=0.0, n_samples=len(df), depth=0))]
    heapq.heapify(beam)
    visited = set()
    
    for depth in range(1, max_depth + 1):
        next_beam = []
        candidates_expanded = 0
        
        while beam and candidates_expanded < beam_width * 2:
            neg_score, _, candidate = heapq.heappop(beam)
            filter_key = tuple(sorted(candidate.filters.items()))
            if filter_key in visited:
                continue
            visited.add(filter_key)
            candidates_expanded += 1
            
            filtered_df = df
            for col, val in candidate.filters.items():
                filtered_df = filtered_df.filter(pl.col(col) == val)
            
            if len(filtered_df) < 20:
                continue
            
            for cat_col in categorical_cols:
                if cat_col in candidate.filters:
                    continue
                
                unique_vals = filtered_df[cat_col].drop_nulls().unique().to_list()
                if len(unique_vals) > 10:
                    continue
                
                for val in unique_vals[:5]:
                    subspace_df = filtered_df.filter(pl.col(cat_col) == val)
                    n_subspace = len(subspace_df)
                    
                    if n_subspace < 15:
                        continue
                    
                    try:
                        x = subspace_df[col1].to_numpy()
                        y = subspace_df[col2].to_numpy()
                        mask = ~(np.isnan(x) | np.isnan(y))
                        x_clean, y_clean = x[mask], y[mask]
                        
                        if len(x_clean) < 10:
                            continue
                        
                        subspace_corr, _ = stats.pearsonr(x_clean, y_clean)
                        improvement = abs(subspace_corr) - abs(base_correlation)
                        
                        if improvement > 0.1:
                            new_filters = {**candidate.filters, cat_col: val}
                            new_candidate = SubspaceCandidate(
                                filters=new_filters,
                                score=improvement,
                                n_samples=n_subspace,
                                depth=depth
                            )
                            heapq.heappush(next_beam, (-improvement, id(new_candidate), new_candidate))
                            
                            z_stat, p_value = fisher_z_test(
                                subspace_corr, n_subspace, base_correlation, base_n
                            )
                            effect_size, effect_interp = cohens_q(subspace_corr, base_correlation)
                            is_simpson = detect_simpson(
                                subspace_corr, base_correlation, p_value, n_subspace
                            )
                            
                            insights.append({
                                "insight_type": "subspace_correlation",
                                "description": describe_insight(
                                    col1, col2, new_filters, base_correlation, subspace_corr, is_simpson
                                ),
                                "columns": [col1, col2],
                                "subspace": new_filters,
                                "statistic": round(subspace_corr, 4),
                                "p_value": p_value,
                                "effect_size": effect_size,
                                "effect_interpretation": effect_interp,
                                "sample_size": n_subspace,
                                "is_simpson_paradox": is_simpson,
                                "novelty_score": improvement
                            })
                    except Exception:
                        continue
        
        next_beam = heapq.nlargest(beam_width, next_beam, key=lambda x: x[0])
        beam = next_beam
        if not beam:
            break
    
    return insights


# ══════════════════════════════════════════════════════════════════════════
# BENCHMARK SUITE
# ══════════════════════════════════════════════════════════════════════════

def run_benchmark():
    print("=" * 72)
    print("  QUIS Subspace Search: Vectorization Benchmark")
    print("=" * 72)
    print()
    
    # ── Generate dataset ──
    print("Generating synthetic dataset...")
    df = generate_synthetic_dataset(n_rows=10_000, n_numeric=20, n_categorical=15)
    print(f"  Dataset: {df.shape[0]:,} rows × {df.shape[1]} columns")
    print(f"  Numeric columns: {len(df.select(pl.NUMERIC_DTYPES).columns)}")
    print(f"  Categorical columns: {len(df.select([pl.Utf8, pl.Categorical]).columns)}")
    print()
    
    # ── Select test columns ──
    numeric_cols = df.select(pl.NUMERIC_DTYPES).columns
    categorical_cols = df.select([pl.Utf8, pl.Categorical]).columns
    
    # Pick a known interesting pair (metric_0 and metric_1 have the Simpson's pattern)
    test_pairs = [
        ("metric_0", "metric_1"),   # Has built-in Simpson's Paradox
        ("metric_2", "metric_3"),   # Normal correlated pair
        ("metric_0", "metric_5"),   # Cross-correlation
        ("metric_4", "metric_7"),   # Moderate correlation
        ("metric_1", "metric_9"),   # Weak global, possible subspace
    ]
    
    # ── Compute global correlations ──
    print("Computing global base correlations...")
    base_corrs = {}
    for col1, col2 in test_pairs:
        if col1 in df.columns and col2 in df.columns:
            x = df[col1].to_numpy()
            y = df[col2].to_numpy()
            mask = ~(np.isnan(x) | np.isnan(y))
            r, _ = stats.pearsonr(x[mask], y[mask])
            base_corrs[(col1, col2)] = {"r": r, "n": int(mask.sum())}
            print(f"  {col1} × {col2}: global r = {r:.4f} (n={mask.sum():,})")
    print()
    
    # ── Benchmark parameters ──
    N_WARMUP = 1
    N_RUNS = 5
    
    # ── Test scenarios ──
    scenarios = [
        ("All 15 categorical columns, depth=1", len(categorical_cols), 1),
        ("All 15 categorical columns, depth=2", len(categorical_cols), 2),
        ("First 5 categorical columns (old default), depth=1", 5, 1),
        ("First 5 categorical columns (old default), depth=2", 5, 2),
    ]
    
    results = []
    
    for scenario_name, n_cats, max_depth in scenarios:
        cat_cols = categorical_cols[:n_cats]
        print(f"\n{'─' * 72}")
        print(f"  Scenario: {scenario_name}")
        print(f"  Categorical columns: {n_cats}, Depth: {max_depth}")
        print(f"{'─' * 72}")
        
        for col1, col2 in test_pairs:
            if (col1, col2) not in base_corrs:
                continue
                
            base_info = base_corrs[(col1, col2)]
            
            # ── Old approach timing ──
            old_times = []
            for run in range(N_WARMUP + N_RUNS):
                start = time.perf_counter()
                old_insights = old_nested_loop_beam_search(
                    df, col1, col2, cat_cols,
                    base_info["r"], base_info["n"],
                    beam_width=10, max_depth=max_depth
                )
                elapsed = time.perf_counter() - start
                if run >= N_WARMUP:
                    old_times.append(elapsed)
            
            # ── New approach timing ──
            engine = VectorizedSubspaceEngine(beam_width=10, max_depth=max_depth)
            new_times = []
            for run in range(N_WARMUP + N_RUNS):
                start = time.perf_counter()
                new_insights = engine.explore_correlation_subspaces(
                    df, col1, col2, cat_cols,
                    base_info["r"], base_info["n"]
                )
                elapsed = time.perf_counter() - start
                if run >= N_WARMUP:
                    new_times.append(elapsed)
            
            old_mean = statistics.mean(old_times)
            new_mean = statistics.mean(new_times)
            old_total_filters = estimate_filter_count(df, cat_cols, max_depth)
            
            speedup = old_mean / new_mean if new_mean > 0 else float('inf')
            
            results.append({
                "scenario": scenario_name,
                "pair": f"{col1} × {col2}",
                "n_cats": n_cats,
                "depth": max_depth,
                "old_mean_ms": old_mean * 1000,
                "new_mean_ms": new_mean * 1000,
                "speedup": speedup,
                "old_insights": len(old_insights),
                "new_insights": len(new_insights),
            })
            
            print(f"\n  {col1} × {col2} (global r={base_info['r']:.3f}):")
            print(f"    OLD: {old_mean*1000:>8.1f} ms  ({len(old_insights)} insights)")
            print(f"    NEW: {new_mean*1000:>8.1f} ms  ({len(new_insights)} insights)")
            print(f"    {'🚀' if speedup > 5 else '✓'} Speedup: {speedup:.1f}×")
    
    # ── Summary Table ──
    print(f"\n\n{'=' * 72}")
    print("  BENCHMARK SUMMARY")
    print(f"{'=' * 72}")
    print()
    print(f"{'Scenario':<45} {'Pair':<20} {'Old (ms)':<10} {'New (ms)':<10} {'Speedup':<10} {'Insights':<10}")
    print(f"{'-' * 105}")
    
    for r in results:
        print(
            f"{r['scenario'][:43]:<45} "
            f"{r['pair']:<20} "
            f"{r['old_mean_ms']:<10.1f} "
            f"{r['new_mean_ms']:<10.1f} "
            f"{r['speedup']:<10.1f}× "
            f"{r['new_insights']}/{r['old_insights']}"
        )
    
    # ── Aggregated Stats ──
    print(f"\n{'─' * 72}")
    print("  AGGREGATED STATISTICS")
    print(f"{'─' * 72}")
    
    for scenario_name in set(r['scenario'] for r in results):
        scenario_results = [r for r in results if r['scenario'] == scenario_name]
        avg_old = statistics.mean(r['old_mean_ms'] for r in scenario_results)
        avg_new = statistics.mean(r['new_mean_ms'] for r in scenario_results)
        avg_speedup = statistics.mean(r['speedup'] for r in scenario_results)
        min_speedup = min(r['speedup'] for r in scenario_results)
        max_speedup = max(r['speedup'] for r in scenario_results)
        total_old_insights = sum(r['old_insights'] for r in scenario_results)
        total_new_insights = sum(r['new_insights'] for r in scenario_results)
        
        print(f"\n  {scenario_name}")
        print(f"    Avg old: {avg_old:.1f} ms  |  Avg new: {avg_new:.1f} ms")
        print(f"    Avg speedup: {avg_speedup:.1f}×  (range: {min_speedup:.1f}× – {max_speedup:.1f}×)")
        print(f"    Total insights found: old={total_old_insights}, new={total_new_insights}")
    
    print(f"\n{'=' * 72}")
    print("  BENCHMARK COMPLETE")
    print(f"{'=' * 72}")
    
    return results


def estimate_filter_count(df: pl.DataFrame, cat_cols: List[str], depth: int) -> int:
    """Estimate how many DataFrame filter operations the old approach performs."""
    total = 0
    for col in cat_cols:
        n_vals = min(df[col].n_unique(), 5)  # Old code capped at 5
        total += n_vals
    if depth >= 2 and len(cat_cols) >= 2:
        for i, c1 in enumerate(cat_cols):
            n1 = min(df[c1].n_unique(), 5)
            for c2 in cat_cols[i+1:]:
                n2 = min(df[c2].n_unique(), 5)
                total += n1 * n2
    return total


if __name__ == "__main__":
    results = run_benchmark()
    
    # Save results to JSON
    import json
    output_path = "benchmark/vectorization_benchmark_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")
