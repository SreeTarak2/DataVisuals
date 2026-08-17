"""
semantic/query_recombiner.py — Query Result Recombinator (Phase 1 Agent Component)
====================================================================================

Takes results from multiple sub-query executions and merges them into a
single coherent result according to the DecompositionPlan's merge strategy.

Merge strategies:
  SIDE_BY_SIDE    — Create columns like revenue_2024, revenue_2023 from separate results
  APPEND          — Stack results on top of each other (UNION-style)
  COMPUTE_CHANGE  — Add a computed 'change' column from two result sets
  SEPARATE        — Present each result as a completely separate answer block
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Set

import polars as pl

from .query_decomposer import DecompositionPlan, MergeStrategy, SubIntent

logger = logging.getLogger(__name__)


# ── Recombinator ───────────────────────────────────────────────────────────


class QueryRecombinator:
    """Merges results from multiple sub-queries according to a decomposition plan.

    The recombiner:
    1. Takes a DecompositionPlan + list of (SubIntent, result_df) tuples
    2. Applies the merge strategy from the plan
    3. Returns a single merged DataFrame + a narrative description of how to merge
    """

    async def recombine(
        self,
        plan: DecompositionPlan,
        results: List[Tuple[SubIntent, Optional[pl.DataFrame], Optional[str]]],
    ) -> Dict[str, Any]:
        """Recombine results from multiple sub-queries.

        Args:
            plan: The decomposition plan from the decomposer
            results: List of (SubIntent, result_df, error) tuples

        Returns:
            Dict with:
            - merged_df: Combined DataFrame or None
            - response: Narrative description of the combined results
            - merge_log: How results were combined (for observability)
        """
        if not results:
            return {
                "merged_df": None,
                "response": "No results to combine.",
                "merge_log": {"strategy": "none", "steps": []},
            }

        # Filter to successful results only
        successful = [
            (s, df) for s, df, err in results
            if df is not None and err is None
        ]

        if not successful:
            errors = [err for _, _, err in results if err]
            return {
                "merged_df": None,
                "response": f"All sub-queries failed: {'; '.join(errors)}",
                "merge_log": {"strategy": "none", "errors": errors},
            }

        if len(successful) == 1:
            # Single result — no merging needed
            sub, df = successful[0]
            return {
                "merged_df": df,
                "response": "",
                "merge_log": {"strategy": "single", "label": sub.label},
            }

        # Apply merge strategy
        merge_strategy = plan.merge_strategy

        if merge_strategy == MergeStrategy.SIDE_BY_SIDE:
            return self._merge_side_by_side(plan, successful)
        elif merge_strategy == MergeStrategy.COMPUTE_CHANGE:
            return self._merge_compute_change(plan, successful)
        elif merge_strategy == MergeStrategy.APPEND:
            return self._merge_append(successful)
        else:
            return self._merge_separate(successful)

    def _merge_side_by_side(
        self,
        plan: DecompositionPlan,
        results: List[Tuple[SubIntent, pl.DataFrame]],
    ) -> Dict[str, Any]:
        """Merge results side-by-side: same dimensions, different metric columns."""
        merge_log = {"strategy": "side_by_side", "steps": []}

        if len(results) < 2:
            sub, df = results[0]
            return {"merged_df": df, "response": "", "merge_log": merge_log}

        # Determine the join column(s) — first dimension column that's common
        base_sub, base_df = results[0]
        join_cols = self._find_join_columns(base_df)

        if not join_cols:
            merge_log["steps"].append("No common join column found — stacking results")
            return self._merge_append(results)

        merge_log["steps"].append(f"Joining on: {join_cols}")

        # Rename metric columns in each result to include suffix
        renamed_dfs: List[pl.DataFrame] = []
        for i, (sub, df) in enumerate(results):
            label = sub.label or f"query_{i}"
            renamed = df

            # Rename non-join columns with the label as suffix
            for col in df.columns:
                if col not in join_cols:
                    # Strip backticks if present
                    clean_col = col.strip("`")
                    suffix = plan.column_suffixes.get(clean_col, {}).get(str(i), f"_{label}")
                    new_name = f"{clean_col}{suffix}"
                    renamed = renamed.rename({col: new_name})
                    merge_log["steps"].append(f"  {clean_col} → {new_name} (suffix: {suffix})")

            renamed_dfs.append(renamed)

        # Join on the common columns
        if len(renamed_dfs) >= 2:
            merged = renamed_dfs[0]
            for df in renamed_dfs[1:]:
                try:
                    merged = merged.join(df, on=join_cols, how="outer")
                except Exception as e:
                    logger.warning(f"[Recombinator] Join failed: {e} — falling back to append")
                    return self._merge_append(results)

            return {
                "merged_df": merged,
                "response": "",
                "merge_log": merge_log,
            }

        return {"merged_df": base_df, "response": "", "merge_log": merge_log}

    def _merge_compute_change(
        self,
        plan: DecompositionPlan,
        results: List[Tuple[SubIntent, pl.DataFrame]],
    ) -> Dict[str, Any]:
        """Compute change/delta between two result sets.

        Expects exactly 2 results: before and after.
        Adds columns: change_value, change_pct, change_direction.
        """
        merge_log = {"strategy": "compute_change", "steps": []}

        if len(results) < 2:
            sub, df = results[0]
            return {"merged_df": df, "response": "", "merge_log": merge_log}

        sub_a, df_a = results[0]
        sub_b, df_b = results[1]
        label_a = sub_a.label or "before"
        label_b = sub_b.label or "after"

        # First merge side-by-side
        temp_plan = DecompositionPlan(
            sub_intents=[sub_a, sub_b],
            merge_strategy=MergeStrategy.SIDE_BY_SIDE,
            column_suffixes=plan.column_suffixes,
        )
        side_by_side = self._merge_side_by_side(temp_plan, results)
        merged_df = side_by_side.get("merged_df")
        if merged_df is None:
            return {"merged_df": None, "response": "Could not merge for change computation",
                    "merge_log": merge_log}

        # Find paired metric columns and compute change
        metric_pairs = self._find_metric_pairs(merged_df.columns, label_a, label_b)
        merge_log["steps"].append(f"Computing change for: {list(metric_pairs.keys())}")

        for base_name, (col_a_name, col_b_name) in metric_pairs.items():
            try:
                change_col = f"{base_name}_change"
                change_pct_col = f"{base_name}_change_pct"

                merged_df = merged_df.with_columns(
                    [
                        (pl.col(col_b_name) - pl.col(col_a_name)).alias(change_col),
                        (
                            (pl.col(col_b_name) - pl.col(col_a_name))
                            / pl.col(col_a_name)
                            * 100
                        ).alias(change_pct_col),
                    ]
                )
                merge_log["steps"].append(
                    f"  {base_name}: {col_b_name} - {col_a_name} = {change_col}"
                )
            except Exception as e:
                logger.warning(f"[Recombinator] Change computation failed for {base_name}: {e}")

        return {"merged_df": merged_df, "response": "", "merge_log": merge_log}

    def _merge_append(
        self,
        results: List[Tuple[SubIntent, pl.DataFrame]],
    ) -> Dict[str, Any]:
        """Stack results vertically (UNION-style)."""
        merge_log = {"strategy": "append", "steps": []}

        if not results:
            return {"merged_df": None, "response": "", "merge_log": merge_log}

        if len(results) == 1:
            sub, df = results[0]
            return {"merged_df": df, "response": "", "merge_log": merge_log}

        # Find common columns across all results
        all_cols: Set[str] = set(results[0][1].columns)
        for _, df in results:
            all_cols &= set(df.columns)
        common_cols = list(all_cols)

        merge_log["steps"].append(f"Appending {len(results)} results, common columns: {common_cols}")

        if not common_cols:
            # No common columns — can't append, fall back to separate
            return self._merge_separate(results)

        # Stack, selecting only common columns
        stacked = pl.concat(
            [df.select(common_cols) for _, df in results],
            how="vertical",
        )

        return {"merged_df": stacked, "response": "", "merge_log": merge_log}

    def _merge_separate(
        self,
        results: List[Tuple[SubIntent, pl.DataFrame]],
    ) -> Dict[str, Any]:
        """Present results separately — no merging, return first as primary."""
        merge_log = {"strategy": "separate", "steps": [f"{len(results)} separate result sets"]}

        if not results:
            return {"merged_df": None, "response": "", "merge_log": merge_log}

        # Return the first result as primary, log that there are multiple
        sub, df = results[0]
        merge_log["steps"].append(f"Primary: {sub.label or 'query_0'}")
        for i in range(1, len(results)):
            merge_log["steps"].append(f"Additional: {results[i][0].label or f'query_{i}'}")

        return {"merged_df": df, "response": "", "merge_log": merge_log}

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _find_join_columns(df: pl.DataFrame) -> List[str]:
        """Find reasonable join columns (first dimension-like columns)."""
        candidates = []
        for col in df.columns:
            col_lower = col.lower()
            # Skip metric-like columns
            if any(kw in col_lower for kw in ["sum", "count", "avg", "mean", "total", "revenue",
                                                "profit", "cost", "price"]):
                continue
            candidates.append(col)
        return candidates[:3]  # Limit to 3 join columns

    @staticmethod
    def _find_metric_pairs(
        columns: List[str],
        label_a: str,
        label_b: str,
    ) -> Dict[str, Tuple[str, str]]:
        """Find paired metric columns for change computation.

        If label_a = "before" and label_b = "after":
        revenue_before, revenue_after → {"revenue": ("revenue_before", "revenue_after")}
        """
        pairs: Dict[str, Tuple[str, str]] = {}

        # Find columns ending with each label
        col_a = [c for c in columns if c.endswith(f"_{label_a}")]
        col_b = [c for c in columns if c.endswith(f"_{label_b}")]

        # Try to match them by base name
        for a in col_a:
            base = a[: -len(f"_{label_a}")]
            b = f"{base}_{label_b}"
            if b in col_b:
                pairs[base] = (a, b)

        return pairs


# Singleton
query_recombinator = QueryRecombinator()
