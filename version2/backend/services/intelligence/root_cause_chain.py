"""
intelligence/root_cause_chain.py — Root Cause Chain Engine (P0)

Takes a metric that changed (e.g., Revenue ↓ 12%) and decomposes it into:
  Level 1: Which segments contributed most to the change?
  Level 2: For the top contributor, what drove its change?
  Level n: Recursive drill-down until variance is explained.

Output: RootCauseChain — a tree of metric → segment → sub-segment contributions.

All deterministic. No LLM calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────────────

# Minimum number of rows required for reliable decomposition
_MIN_ROWS = 20
# Minimum percentage change before decomposition triggers
_MIN_CHANGE_PCT = 2.0
# Top N contributors to include in each level
_MAX_CONTRIBUTORS = 3
# Contribution threshold to flag as a primary driver
_PRIMARY_DRIVER_THRESHOLD = 30.0
# Maximum recursion depth for drill-down chains
_MAX_DEPTH = 3


# ── Data Structures ───────────────────────────────────────────────────────────


@dataclass
class RootCauseLink:
    """A single link in the root cause chain.

    Each link represents one level of decomposition:
      Level 0: The metric itself (e.g., "Revenue ↓ 12%")
      Level 1: Segment contributions (e.g., "Region B contributed -8pp")
      Level 2: Sub-segment drill-down (e.g., "Within Region B, Product X contributed -5pp")
    """

    metric_name: str                               # "Revenue", "Total Orders"
    metric_column: str                             # Actual column name
    total_value: Optional[float] = None             # Current period value
    previous_value: Optional[float] = None          # Previous period value
    delta_pct: Optional[float] = None               # Percent change
    delta_abs: Optional[float] = None               # Absolute change
    polarity: str = "higher_is_better"             # Direction signal

    # Contributors at this level
    contributors: List[Dict[str, Any]] = field(default_factory=list)
    # Drill-down chain (next level of detail for top contributor)
    drill_down: Optional["RootCauseLink"] = None

    # Narrative
    headline: str = ""                              # "Revenue dropped 12%, driven by Region B"
    detail: str = ""                                # Multi-sentence explanation

    @property
    def is_driving(self) -> bool:
        """True if this link's top contributor is a primary driver (>threshold)."""
        if not self.contributors:
            return False
        return abs(self.contributors[0].get("contribution_pct", 0)) >= _PRIMARY_DRIVER_THRESHOLD


@dataclass
class RootCauseChain:
    """Complete root cause chain for one KPI metric.

    chain.links[0] = Metric level (e.g., Revenue ↓ 12%)
    chain.links[1] = Segment level (e.g., Region B: -8pp contribution)
    chain.links[2] = Sub-segment level (e.g., Region B > Product X: -5pp)
    """

    metric_name: str
    metric_column: str
    links: List[RootCauseLink] = field(default_factory=list)
    depth: int = 0
    has_root_cause: bool = False                    # True if at least 2 levels deep
    summary: str = ""                                # One-line takeaway

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for KPI card attachment."""
        return {
            "metric_name": self.metric_name,
            "metric_column": self.metric_column,
            "depth": self.depth,
            "has_root_cause": self.has_root_cause,
            "summary": self.summary,
            "links": [
                {
                    "metric_name": l.metric_name,
                    "delta_pct": l.delta_pct,
                    "delta_abs": l.delta_abs,
                    "headline": l.headline,
                    "contributors": l.contributors,
                    "drill_down": l.drill_down.metric_name if l.drill_down else None,
                    "is_driving": l.is_driving,
                }
                for l in self.links
            ],
        }


# ── Core Computation ─────────────────────────────────────────────────────────


def _safe_agg(df: pl.DataFrame, col: str, agg: str = "sum") -> Optional[float]:
    """Safely aggregate a column."""
    try:
        if col not in df.columns or df.height == 0:
            return None
        clean = df[col].drop_nulls()
        if len(clean) == 0:
            return None
        if agg == "sum":
            return float(clean.sum())
        elif agg == "mean":
            return float(clean.mean())
        elif agg == "median":
            return float(clean.median())
        elif agg == "count":
            return float(len(clean))
        else:
            return float(clean.sum())
    except Exception:
        return None


def _find_dimensions(df: pl.DataFrame) -> List[str]:
    """Find usable dimension columns for decomposition.

    A usable dimension is:
      - Categorical/text with 2-12 unique values
      - NOT an ID column (no _id, _key, _uuid, guid, hash suffix)
    """
    dims = []
    for col in df.columns:
        dtype = df[col].dtype
        if str(dtype) in ("Utf8", "String", "Categorical"):
            uniq = df[col].n_unique()
            if 2 <= uniq <= 12:
                # Filter out ID-like columns
                if not any(s in col.lower() for s in ("_id", "_key", "_uuid", "guid", "hash")):
                    dims.append(col)
        elif str(dtype) in ("Int8", "Int16", "Int32", "Int64"):
            uniq = df[col].n_unique()
            if 2 <= uniq <= 10:
                dims.append(col)
    return dims[:5]  # Max 5 dimensions


def compute_contributions(
    df: pl.DataFrame,
    metric_col: str,
    dimension_col: str,
    time_col: Optional[str] = None,
    aggregation: str = "sum",
) -> List[Dict[str, Any]]:
    """Decompose a metric's change by segment contributions.

    For each segment in the dimension, compute how much it contributed
    to the total change. Returns segments ranked by absolute contribution.

    Args:
        df: Full DataFrame
        metric_col: The metric to decompose (e.g., "revenue")
        dimension_col: The dimension to split by (e.g., "region")
        time_col: Optional time column for time-aware splitting
        aggregation: Aggregation to use

    Returns:
        List of dicts: {segment, change, contribution_pct, direction}
    """
    try:
        if metric_col not in df.columns or dimension_col not in df.columns:
            return []

        clean = df.drop_nulls(subset=[metric_col, dimension_col])
        if clean.height < _MIN_ROWS:
            return []

        # Time-aware split
        if time_col and time_col in df.columns:
            try:
                sorted_df = clean.sort(time_col)
                mid = sorted_df.height // 2
                first_half = sorted_df[:mid]
                second_half = sorted_df[mid:]
            except Exception:
                return []
        else:
            mid = clean.height // 2
            first_half = clean[:mid]
            second_half = clean[mid:]

        if first_half.height < _MIN_ROWS // 2 or second_half.height < _MIN_ROWS // 2:
            return []

        total_p1 = _safe_agg(first_half, metric_col, aggregation)
        total_p2 = _safe_agg(second_half, metric_col, aggregation)

        if total_p1 is None or total_p2 is None or total_p1 == 0:
            return []

        total_change = total_p2 - total_p1
        total_change_pct = (total_change / abs(total_p1)) * 100

        if abs(total_change_pct) < _MIN_CHANGE_PCT:
            return []

        # Per-segment aggregates
        seg_p1 = (
            first_half.group_by(dimension_col)
            .agg(pl.col(metric_col).sum().alias("_p1"))
        )
        seg_p2 = (
            second_half.group_by(dimension_col)
            .agg(pl.col(metric_col).sum().alias("_p2"))
        )
        merged = seg_p1.join(seg_p2, on=dimension_col, how="inner")

        contributions = []
        for row in merged.iter_rows(named=True):
            s1 = float(row["_p1"])
            s2 = float(row["_p2"])
            change = s2 - s1
            if abs(change) < 1e-6:
                continue
            contribution_pct = (change / abs(total_change)) * 100 if total_change != 0 else 0
            seg_pct = (s2 / abs(total_p2)) * 100 if total_p2 != 0 else 0
            contributions.append({
                "segment": str(row[dimension_col]),
                "segment_value_before": round(s1, 2),
                "segment_value_after": round(s2, 2),
                "change": round(change, 2),
                "contribution_pct": round(contribution_pct, 1),
                "segment_share_pct": round(seg_pct, 1),
                "direction": "up" if change > 0 else ("down" if change < 0 else "flat"),
            })

        contributions.sort(key=lambda c: abs(c["contribution_pct"]), reverse=True)
        return contributions

    except Exception as e:
        logger.debug(f"[RootCause] Contribution computation failed: {e}")
        return []


def compute_chain(
    df: pl.DataFrame,
    metric_col: str,
    metric_name: str,
    value: Optional[float] = None,
    previous_value: Optional[float] = None,
    aggregation: str = "sum",
    polarity: str = "higher_is_better",
    time_col: Optional[str] = None,
    max_depth: int = _MAX_DEPTH,
    _current_depth: int = 0,
) -> RootCauseChain:
    """Compute the full root cause chain for a metric.

    Builds a tree: metric → segment contributors → drill-down into top contributor.

    Args:
        df: DataFrame
        metric_col: Column name to analyze
        metric_name: Human-readable name
        value: Current period value (computed if None)
        previous_value: Previous period value (computed if None)
        aggregation: Aggregation method
        polarity: higher_is_better or lower_is_better
        time_col: Optional time column
        max_depth: Maximum recursion depth
        _current_depth: Internal recursion counter

    Returns:
        RootCauseChain with all levels of decomposition
    """
    try:
        if metric_col not in df.columns:
            return RootCauseChain(metric_name=metric_name, metric_column=metric_col)

        if value is None or previous_value is None:
            # Compute from time split
            if time_col and time_col in df.columns:
                try:
                    sorted_df = df.sort(time_col)
                    mid = sorted_df.height // 2
                    value = _safe_agg(sorted_df[mid:], metric_col, aggregation) or 0
                    previous_value = _safe_agg(sorted_df[:mid], metric_col, aggregation) or 0
                except Exception:
                    value = _safe_agg(df, metric_col, aggregation) or 0
                    previous_value = 0
            else:
                mid = df.height // 2
                value = _safe_agg(df[mid:], metric_col, aggregation) or 0
                previous_value = _safe_agg(df[:mid], metric_col, aggregation) or 0

        delta_abs = (value - previous_value) if previous_value else 0.0
        delta_pct = ((delta_abs / abs(previous_value)) * 100) if previous_value and previous_value != 0 else 0.0

        if abs(delta_pct) < _MIN_CHANGE_PCT and _current_depth == 0:
            return RootCauseChain(
                metric_name=metric_name,
                metric_column=metric_col,
                links=[RootCauseLink(
                    metric_name=metric_name,
                    metric_column=metric_col,
                    total_value=value,
                    previous_value=previous_value,
                    delta_pct=round(delta_pct, 1),
                    delta_abs=round(delta_abs, 2),
                    polarity=polarity,
                    headline=f"{metric_name} is stable ({delta_pct:+.1f}%)",
                    detail=f"No significant change detected ({abs(delta_pct):.1f}% change).",
                )],
                has_root_cause=False,
            )

        # Build the chain
        chain = RootCauseChain(
            metric_name=metric_name,
            metric_column=metric_col,
        )

        # Level 0: Metric level
        dir_word = "grew" if delta_pct > 0 else "declined"
        headline = f"{metric_name} {dir_word} {abs(delta_pct):.1f}%"
        if abs(delta_pct) > 20:
            headline = f"{metric_name} {dir_word} sharply {abs(delta_pct):.1f}%"
        elif abs(delta_pct) < 5:
            headline = f"{metric_name} {dir_word} slightly {abs(delta_pct):.1f}%"

        metric_link = RootCauseLink(
            metric_name=metric_name,
            metric_column=metric_col,
            total_value=value,
            previous_value=previous_value,
            delta_pct=round(delta_pct, 1),
            delta_abs=round(delta_abs, 2),
            polarity=polarity,
            headline=headline,
            detail="",
        )
        chain.links.append(metric_link)

        # Level 1+: Segment contributions
        dimensions = _find_dimensions(df)
        all_contributors: List[Dict[str, Any]] = []

        for dim in dimensions:
            contribs = compute_contributions(
                df, metric_col, dim, time_col, aggregation
            )
            if contribs:
                # Take the top contributor from each dimension
                all_contributors.append({
                    "dimension": dim,
                    "top_contributor": contribs[0],
                    "all_contributors": contribs,
                })

        if not all_contributors:
            chain.has_root_cause = False
            chain.links[0].detail = f"{metric_name} changed {abs(delta_pct):.1f}%, but no dimension with 2+ segments was found to decompose the change."
            return chain

        # Rank dimensions by top contributor's absolute contribution
        all_contributors.sort(
            key=lambda c: abs(c["top_contributor"]["contribution_pct"]),
            reverse=True,
        )

        # Build contributor list for the metric link
        top_contributors = []
        for ac in all_contributors[:_MAX_CONTRIBUTORS]:
            tc = ac["top_contributor"]
            top_contributors.append({
                "dimension": ac["dimension"],
                "segment": tc["segment"],
                "contribution_pct": tc["contribution_pct"],
                "change": tc["change"],
                "direction": tc["direction"],
            })
        chain.links[0].contributors = top_contributors

        # Build narrative
        if top_contributors:
            tc = top_contributors[0]
            dir_desc = "growth" if tc["contribution_pct"] > 0 else "decline"
            parts = [f"{abs(tc['contribution_pct']):.0f}% of the {dir_desc} came from {tc['segment']} ({tc['dimension']})"]
            if len(top_contributors) > 1:
                tc2 = top_contributors[1]
                parts.append(f"followed by {tc2['segment']} ({abs(tc2['contribution_pct']):.0f}% contribution)")
            chain.links[0].detail = "; ".join(parts) + "."
            chain.links[0].headline = f"{headline} — driven by {tc['segment']}"

        chain.has_root_cause = len(top_contributors) > 0

        # Level 2+: Drill down into top contributor
        if top_contributors and _current_depth < max_depth:
            tc = top_contributors[0]
            seg_value = tc["segment"]
            dim_col = tc["dimension"]
            # Filter df to this segment, then recurse
            try:
                filtered = df.filter(pl.col(dim_col) == seg_value)
                if filtered.height >= _MIN_ROWS:
                    sub_chain = compute_chain(
                        df=filtered,
                        metric_col=metric_col,
                        metric_name=f"{metric_name} ({seg_value})",
                        aggregation=aggregation,
                        polarity=polarity,
                        time_col=time_col,
                        max_depth=max_depth,
                        _current_depth=_current_depth + 1,
                    )
                    if sub_chain.links and len(sub_chain.links) > 1:
                        drill_down_link = sub_chain.links[1]
                        chain.links[0].drill_down = drill_down_link
                        chain.links.extend(sub_chain.links[1:])
                        chain.has_root_cause = True
            except Exception as e:
                logger.debug(f"[RootCause] Drill-down failed: {e}")

        chain.depth = len(chain.links)

        # Build summary
        if chain.has_root_cause and chain.links:
            l0 = chain.links[0]
            parts = [l0.headline]
            if l0.contributors:
                top = l0.contributors[0]
                parts.append(f"Primary driver: {top['segment']} (contributed {abs(top['contribution_pct']):.0f}%)")
                if len(l0.contributors) > 1:
                    top2 = l0.contributors[1]
                    parts.append(f"Secondary: {top2['segment']} ({abs(top2['contribution_pct']):.0f}%)")
            chain.summary = " — ".join(parts)

        return chain

    except Exception as e:
        logger.warning(f"[RootCause] Chain computation failed for '{metric_col}': {e}")
        return RootCauseChain(metric_name=metric_name, metric_column=metric_col)


# ── Batch API ────────────────────────────────────────────────────────────────


def compute_chains_for_kpis(
    df: pl.DataFrame,
    kpis: List[Dict[str, Any]],
    time_col: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Compute root cause chains for a list of KPI cards.

    Adds 'root_cause_chain' field to each KPI dict that has a delta.

    Args:
        df: DataFrame
        kpis: List of KPI card dicts (from IntelligentKPIGenerator)
        time_col: Optional time column

    Returns:
        Updated KPI cards with root_cause_chain field
    """
    for kpi in kpis:
        col = kpi.get("column")
        delta = kpi.get("delta_percent")
        if not col or col not in df.columns:
            continue
        if delta is None or abs(delta) < _MIN_CHANGE_PCT:
            continue

        try:
            chain = compute_chain(
                df=df,
                metric_col=col,
                metric_name=kpi.get("title", col),
                value=kpi.get("value"),
                previous_value=kpi.get("comparison_value"),
                aggregation=kpi.get("aggregation", "sum"),
                polarity=kpi.get("polarity", "higher_is_better"),
                time_col=time_col,
            )
            if chain.has_root_cause:
                kpi["root_cause_chain"] = chain.to_dict()
        except Exception as e:
            logger.debug(f"[RootCause] Chain failed for '{col}': {e}")
            continue

    return kpis
