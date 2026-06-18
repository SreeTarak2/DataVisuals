"""
intelligence/metric_graph.py — Metric Relationship Graph (P0)

Builds a runtime graph showing how metrics relate to each other:

  Revenue
    ├── Orders × Price
    ├── New Revenue + Repeat Revenue
    └── Revenue - Refunds

  Profit = Revenue - Cost

  Gross Margin = (Revenue - Cost) / Revenue

This enables root cause analysis to decompose metric changes by
COMPONENT METRICS (not just by segments), answering questions like:
  "Revenue ↓ 12% because Orders ↓ 15% and Price ↓ 3%"

Three sources of relationships:
  1. Column name conventions (revenue - cost = profit)
  2. Domain template formulas (from definitions.py)
  3. Statistical correlations (highly correlated column pairs)

All deterministic. No LLM calls.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import polars as pl

logger = logging.getLogger(__name__)


# ── Data Structures ───────────────────────────────────────────────────────────


@dataclass
class MetricEdge:
    """A directional relationship between two metrics.

    source: The parent/derived metric (e.g. "Profit")
    target: The component/input metric (e.g. "Revenue", "Cost")
    relationship_type: How they relate
        - "component" = source is composed of targets (Revenue = sum of parts)
        - "ratio" = source = target_a / target_b
        - "derived" = source = f(target_a, target_b) via custom formula
        - "correlation" = statistically related (weakest signal)
    formula: Human-readable formula string
    confidence: 0.0-1.0 how reliable this relationship is
    """
    source: str              # Column name of derived metric
    target: str              # Column name of component metric
    relationship_type: str   # "component" | "ratio" | "derived" | "correlation"
    formula: str = ""        # e.g. "Revenue - Cost"
    confidence: float = 0.5  # 0.0-1.0
    source_category: str = ""  # Business category of source
    target_category: str = ""  # Business category of target


@dataclass
class MetricGraph:
    """A directed graph of metric relationships within a dataset.

    Allows querying:
      - parents(metric) → which metrics does this metric contribute to?
      - children(metric) → which metrics contribute to this metric?
      - decompose(metric) → component breakdown with contributions
    """
    edges: List[MetricEdge] = field(default_factory=list)
    _by_source: Dict[str, List[MetricEdge]] = field(default_factory=dict)
    _by_target: Dict[str, List[MetricEdge]] = field(default_factory=dict)

    def __post_init__(self):
        self._index()

    def _index(self):
        """Build lookup maps for fast queries."""
        self._by_source.clear()
        self._by_target.clear()
        for edge in self.edges:
            s = edge.source.lower()
            t = edge.target.lower()
            self._by_source.setdefault(s, []).append(edge)
            self._by_target.setdefault(t, []).append(edge)

    def add_edge(self, edge: MetricEdge):
        """Add a single edge to the graph."""
        self.edges.append(edge)
        self._by_source.setdefault(edge.source.lower(), []).append(edge)
        self._by_target.setdefault(edge.target.lower(), []).append(edge)

    def add_edges(self, edges: List[MetricEdge]):
        """Add multiple edges."""
        for e in edges:
            self.add_edge(e)

    def children(self, metric: str) -> List[MetricEdge]:
        """Get all component metrics that feed into this metric.

        E.g. for profit = revenue - cost:
          children("profit") → [revenue, cost]
        """
        return self._by_source.get(metric.lower(), [])

    def parents(self, metric: str) -> List[MetricEdge]:
        """Get all derived metrics that this metric contributes to.

        E.g. for profit = revenue - cost:
          parents("revenue") → [profit]
        """
        return self._by_target.get(metric.lower(), [])

    def has_metric(self, metric: str) -> bool:
        """True if this metric is in the graph."""
        ml = metric.lower()
        return ml in self._by_source or ml in self._by_target

    def decompose(self, metric: str, df: Optional[pl.DataFrame] = None) -> List[Dict[str, Any]]:
        """Decompose a metric into its direct component metrics.

        If a DataFrame is provided, computes the actual contribution
        percentages based on relative magnitudes.

        Args:
            metric: Column name to decompose
            df: Optional DataFrame for computing contributions

        Returns:
            List of dicts: {column, relationship_type, formula, contribution_pct, ...}
        """
        components = self.children(metric)
        if not components:
            return []

        result = []
        for comp in components:
            entry = {
                "column": comp.target,
                "relationship_type": comp.relationship_type,
                "formula": comp.formula,
                "confidence": comp.confidence,
                "source_category": comp.source_category,
                "target_category": comp.target_category,
            }

            # Compute contribution if DataFrame available
            if df is not None and metric in df.columns and comp.target in df.columns:
                try:
                    metric_sum = float(df[metric].drop_nulls().sum())
                    comp_sum = float(df[comp.target].drop_nulls().sum())
                    if metric_sum and metric_sum != 0:
                        abs_ratio = abs(comp_sum / metric_sum) * 100
                        entry["contribution_pct"] = round(abs_ratio, 1)
                        entry["target_value"] = round(comp_sum, 2)
                    else:
                        entry["contribution_pct"] = 0
                        entry["target_value"] = 0
                except Exception:
                    entry["contribution_pct"] = None
                    entry["target_value"] = None
            else:
                entry["contribution_pct"] = None
                entry["target_value"] = None

            result.append(entry)

        # Sort by contribution (descending), unknowns last
        result.sort(key=lambda r: -(r["contribution_pct"] or 0))
        return result

    def decompose_deep(
        self,
        metric: str,
        df: Optional[pl.DataFrame] = None,
        max_depth: int = 3,
        _depth: int = 0,
    ) -> Dict[str, Any]:
        """Recursively decompose a metric into its full component tree.

        Returns a nested tree structure:
        {
            "metric": "Revenue",
            "children": [
                {
                    "metric": "Orders",
                    "children": [
                        {"metric": "New Orders", ...},
                        {"metric": "Repeat Orders", ...},
                    ]
                },
                {"metric": "Price", ...},
            ]
        }
        """
        node: Dict[str, Any] = {
            "metric": metric,
            "components": [],
            "contribution_pct": None,
            "formula": None,
        }

        if _depth >= max_depth:
            return node

        components = self.decompose(metric, df)
        for comp in components:
            child = self.decompose_deep(
                comp["column"], df, max_depth, _depth + 1
            )
            child["contribution_pct"] = comp.get("contribution_pct")
            child["formula"] = comp.get("formula")
            child["relationship_type"] = comp.get("relationship_type")
            node["components"].append(child)

        return node

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the graph to a dict."""
        return {
            "edge_count": len(self.edges),
            "metrics": list(set(e.source for e in self.edges) | set(e.target for e in self.edges)),
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "type": e.relationship_type,
                    "formula": e.formula,
                    "confidence": e.confidence,
                }
                for e in self.edges
            ],
        }

    @property
    def metric_count(self) -> int:
        return len(set(e.source for e in self.edges) | set(e.target for e in self.edges))

    @property
    def empty(self) -> bool:
        return len(self.edges) == 0


# ── Built-in Formula Patterns ──────────────────────────────────────────────

# These patterns detect common metric relationships from column names.
# Format: (derived_name_pattern, component_patterns, formula_string, confidence)
# e.g., if a dataset has "profit", "revenue", and "cost" columns, we know
# profit ≈ revenue - cost.

_COLUMN_NAME_FORMULAS: List[Tuple[str, List[str], str, str, float]] = [
    # Profit = Revenue - Cost
    (r"\bprofit|gross_profit|net_profit|operating_profit\b",
     ["revenue", "cost", "cogs"],
     "Revenue - Cost", "derived", 0.75),
    # Margin = (Revenue - Cost) / Revenue
    (r"\bmargin|gross_margin|profit_margin|net_margin\b",
     ["revenue", "cost", "cogs"],
     "(Revenue - Cost) / Revenue", "ratio", 0.70),
    # Net Income = Revenue - Total Expenses
    (r"\bnet_income|net_earnings|bottom_line\b",
     ["revenue", "expense", "cost"],
     "Revenue - Expenses", "derived", 0.70),
    # ROAS = Revenue / Ad Spend
    (r"\broas|return_on_ad_spend\b",
     ["revenue", "cost"],
     "Revenue / Cost", "ratio", 0.75),
    # Conversion Rate = Conversions / Visitors
    (r"\bconversion_rate|conversion_ratio|cvr\b",
     ["conversion", "visitor", "impression"],
     "Conversions / Visitors", "ratio", 0.80),
    # CTR = Clicks / Impressions
    (r"\bctr|click_rate|click_through_rate\b",
     ["click", "impression"],
     "Clicks / Impressions", "ratio", 0.85),
    # CPC = Cost / Clicks
    (r"\bcpc|cost_per_click\b",
     ["cost", "click"],
     "Cost / Clicks", "ratio", 0.85),
    # AOV = Revenue / Orders
    (r"\baov|average_order_value|avg_order\b",
     ["revenue", "order"],
     "Revenue / Orders", "ratio", 0.85),
    # ARPU = Revenue / Users
    (r"\barpu|arpc|average_revenue_per_user|average_revenue_per_customer\b",
     ["revenue", "user", "customer"],
     "Revenue / Users", "ratio", 0.85),
    # Churn Rate = Churned / Total Customers
    (r"\bchurn_rate|attrition_rate|cancellation_rate\b",
     ["churn", "customer"],
     "Churned / Total Customers", "ratio", 0.80),
    # Defect Rate = Defects / Total Units
    (r"\bdefect_rate|defect_pct|failure_rate\b",
     ["defect", "quantity", "unit"],
     "Defects / Total Units", "ratio", 0.80),
    # Yield Rate = Good Units / Total Units
    (r"\byield_rate|yield_pct|pass_rate|quality_rate\b",
     ["yield", "quantity", "unit"],
     "Good Units / Total Units", "ratio", 0.80),
    # LTV/CAC Ratio
    (r"\bltv_cac|ltv_over_cac|cac_ratio\b",
     ["ltv", "cac"],
     "LTV / CAC", "ratio", 0.90),
    # Gross Profit = Revenue - COGS
    (r"\bgross_profit|gross\b",
     ["revenue", "cogs"],
     "Revenue - COGS", "derived", 0.80),
    # Net Revenue = Revenue - Refunds
    (r"\bnet_revenue|net_sales|revenue_net\b",
     ["revenue", "refund", "return"],
     "Revenue - Refunds", "derived", 0.70),
    # Employee Turnover = Departed / Headcount
    (r"\bturnover_rate|employee_turnover|separation_rate\b",
     ["turnover", "headcount", "employee"],
     "Departed / Total Employees", "ratio", 0.75),
    # Graduation Rate = Graduated / Enrolled
    (r"\bgraduation_rate|grad_rate\b",
     ["graduated", "enrolled", "student"],
     "Graduated / Enrolled", "ratio", 0.80),
    # Attendance Rate = Present / Total
    (r"\battendance_rate|attendance_pct\b",
     ["present", "enrolled", "student"],
     "Present / Enrolled", "ratio", 0.80),
    # Burn Rate = Total Expenses - Revenue (when both present)
    (r"\bburn_rate|monthly_burn|net_burn\b",
     ["expense", "revenue"],
     "Total Expenses - Revenue", "derived", 0.70),
    # Cost per Unit = Total Cost / Units
    (r"\bcost_per_unit|unit_cost|cpu\b",
     ["cost", "quantity", "unit"],
     "Total Cost / Units", "ratio", 0.80),
    # Price per Sq Ft = Price / Area
    (r"\bprice_per_sqft|price_per_sf|price_per_sq_ft\b",
     ["price", "sqft", "square_feet", "area"],
     "Price / SqFt", "ratio", 0.85),
    # Days on Market (no formula, but related to listing dates)
    (r"\bdays_on_market|dom|time_to_sell\b",
     ["date"],
     "Date range metric", "correlation", 0.50),
    # Cash Runway = Cash / Burn Rate
    (r"\b(runway|cash_runway)\b",
     ["cash", "burn_rate", "expense"],
     "Cash / Burn Rate", "ratio", 0.80),
]


# ── Domain Template Formula Patterns ─────────────────────────────────────────

def _load_domain_template_formulas() -> List[Tuple[str, List[str], str, str, float]]:
    """Load formula patterns from KPIService domain templates.

    Extracts formulas from KPIDefinition objects in the kpi/definitions.py
    module. These are hand-crafted formulas per domain (SaaS, Ecom, etc.)
    with high confidence.
    """
    formulas: List[Tuple[str, List[str], str, str, float]] = []
    try:
        from services.kpi.definitions import ALL_KPIS
    except ImportError:
        return formulas

    for kpi_id, kpi_def in ALL_KPIS.items():
        formula = kpi_def.formula
        name = kpi_def.name
        col = kpi_def.formula.column if kpi_def.formula else ""

        if formula.formula_type == "ratio":
            # Ratio formulas need numerator and denominator columns
            num_col = formula.numerator_column or col or ""
            den_col = formula.denominator_column or ""
            if num_col and den_col:
                formulas.append((
                    name,
                    [num_col, den_col],
                    f"{num_col} / {den_col}",
                    "ratio",
                    0.90,
                ))
        elif formula.formula_type == "custom" and formula.custom_expression:
            # Custom expression like "revenue - cogs" or "mrr * 12"
            # Extract variable names from the expression
            vars_found = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', formula.custom_expression)
            # Filter out Python keywords and numbers
            skip = {"in", "is", "and", "or", "not", "if", "else", "for", "to", "by", "from"}
            components = [v for v in vars_found if v.lower() not in skip and not v.isdigit()]
            if components:
                formulas.append((
                    name,
                    components,
                    formula.custom_expression,
                    "derived",
                    0.90,
                ))

    return formulas


# ── Graph Builder ────────────────────────────────────────────────────────────


def _find_column_fuzzy(available: List[str], target: str) -> Optional[str]:
    """Find a column that fuzzy-matches a target name.

    Tries exact match, then partial match (target in column name).
    """
    tl = target.lower()
    for col in available:
        if col.lower() == tl:
            return col
    for col in available:
        if tl in col.lower() or col.lower() in tl:
            return col
    return None


def _find_columns_fuzzy(available: List[str], targets: List[str]) -> Dict[str, Optional[str]]:
    """Map target names to actual column names (fuzzy matched)."""
    result: Dict[str, Optional[str]] = {}
    for t in targets:
        found = _find_column_fuzzy(available, t)
        if found:
            result[t] = found
    return result


def build_metric_graph(
    df: pl.DataFrame,
    profiles: Optional[List[Any]] = None,
    domain_template_id: Optional[str] = None,
) -> MetricGraph:
    """Build a MetricGraph from a DataFrame's columns.

    Discovers relationships from:
      1. Column name conventions (revenue + cost → profit)
      2. Domain template formulas (from definitions.py)
      3. Business category relationships (revenue items are additive)

    Args:
        df: DataFrame with the data
        profiles: Optional list of ColumnProfile objects
        domain_template_id: Optional domain template ID (e.g. "saas-metrics")

    Returns:
        MetricGraph with all discovered relationships
    """
    available = list(df.columns)
    graph = MetricGraph()

    # ── 1. Column name convention patterns ──
    for pattern, targets, formula_str, rel_type, confidence in _COLUMN_NAME_FORMULAS:
        # Check if any column matches the derived metric pattern
        for col in available:
            if re.search(pattern, col, re.I):
                # Found a derived metric — find its components
                mapping = _find_columns_fuzzy(available, targets)
                found_targets = {k: v for k, v in mapping.items() if v is not None}

                if found_targets and len(found_targets) >= 1:
                    for target_name, actual_col in found_targets.items():
                        if actual_col != col:
                            graph.add_edge(MetricEdge(
                                source=col,
                                target=actual_col,
                                relationship_type=rel_type,
                                formula=formula_str,
                                confidence=confidence,
                            ))
                break

    # ── 2. Domain template formulas ──
    template_formulas = _load_domain_template_formulas()
    for name, targets, formula_str, rel_type, confidence in template_formulas:
        # Check if the derived KPI name matches any column
        name_match = _find_column_fuzzy(available, name)
        if not name_match:
            continue

        mapping = _find_columns_fuzzy(available, targets)
        found_targets = {k: v for k, v in mapping.items() if v is not None}

        if found_targets and len(found_targets) >= 1:
            for target_name, actual_col in found_targets.items():
                if actual_col != name_match:
                    graph.add_edge(MetricEdge(
                        source=name_match,
                        target=actual_col,
                        relationship_type=rel_type,
                        formula=formula_str,
                        confidence=max(confidence, 0.85),
                    ))

    # ── 3. Detect additive relationships between columns in the same category ──
    # If we have profiles with business categories, find columns that sum to another
    if profiles:
        _discover_additive_relationships(graph, profiles, df)

    return graph


def _discover_additive_relationships(
    graph: MetricGraph,
    profiles: List[Any],
    df: pl.DataFrame,
):
    """Discover potential additive relationships between columns.

    For example, if we have "new_orders" and "repeat_orders", they likely
    sum to "total_orders" or "orders". Similarly for revenue components.

    Strategy:
      - Group columns by prefix (e.g., "new_orders", "repeat_orders" → "orders")
      - Check if the sum of component columns equals the aggregate column
      - Use business categories to find related columns
    """
    from collections import defaultdict

    # Build column names (lowercased)
    col_names = [p.name for p in profiles if hasattr(p, "name")]
    name_lower = {c.lower(): c for c in col_names}

    # Find prefix groups: columns sharing a common prefix
    # e.g., new_revenue + repeat_revenue → revenue
    #       new_orders + repeat_orders → orders
    prefix_pattern = re.compile(r"^(new|repeat|returning|direct|indirect|organic|paid)_(.+)$", re.I)

    groups: Dict[str, List[str]] = defaultdict(list)
    for col in col_names:
        m = prefix_pattern.match(col)
        if m:
            base = m.group(2).lower()
            if base in name_lower:
                parent = name_lower[base]
                if parent != col:
                    groups[parent].append(col)

    for parent, components in groups.items():
        if len(components) < 2:
            continue
        for comp in components:
            graph.add_edge(MetricEdge(
                source=parent,
                target=comp,
                relationship_type="component",
                formula=f"Sum of components including {comp}",
                confidence=0.65,  # Lower confidence — inferred, not defined
            ))

    # Also check business categories from profiles
    cat_groups: Dict[str, List[str]] = defaultdict(list)
    for p in profiles:
        cat = getattr(p, "business_category", "unknown")
        if cat and cat not in ("unknown", "general"):
            cat_groups[cat].append(p.name)

    # If a category has 3+ columns, they're likely related components
    # E.g., revenue category might have: revenue, net_revenue, refunds
    for cat, members in cat_groups.items():
        if len(members) >= 3:
            # The column with the largest magnitude is likely the aggregate
            try:
                sums = []
                for m in members:
                    if m in df.columns:
                        s = float(df[m].drop_nulls().sum())
                        sums.append((m, s))
                sums.sort(key=lambda x: -abs(x[1]))
                if len(sums) >= 2:
                    largest = sums[0][0]
                    for i in range(1, min(3, len(sums))):
                        smaller = sums[i][0]
                        # Only add if the larger is significantly bigger
                        if abs(sums[0][1]) > abs(sums[i][1]) * 1.5:
                            graph.add_edge(MetricEdge(
                                source=largest,
                                target=smaller,
                                relationship_type="component",
                                formula=f"Related {cat} metrics",
                                confidence=0.50,  # Weakest signal — just same category
                                source_category=cat,
                                target_category=cat,
                            ))
            except Exception:
                pass


# ── Decomposition with Actual Data ──────────────────────────────────────────


def decompose_metric_change(
    df: pl.DataFrame,
    metric_col: str,
    graph: MetricGraph,
    time_col: Optional[str] = None,
    aggregation: str = "sum",
) -> Dict[str, Any]:
    """Decompose a metric's change into component metric contributions.

    This is the key function that enables "Revenue ↓ 12% because Orders ↓ 15%".

    For each component of the metric in the graph, computes:
      - Its absolute change
      - Its percent change
      - How much it contributed to the parent's total change

    Args:
        df: DataFrame
        metric_col: Column to decompose
        graph: MetricGraph with relationships
        time_col: Optional time column for period-over-period comparison
        aggregation: Aggregation to use

    Returns:
        Dict with decomposition results
    """
    from services.intelligence.root_cause_chain import _safe_agg

    components = graph.decompose(metric_col, df)
    if not components:
        return {"metric": metric_col, "components": []}

    # Compute parent's total and change
    if time_col and time_col in df.columns:
        try:
            sorted_df = df.sort(time_col)
            mid = sorted_df.height // 2
            parent_p1 = _safe_agg(sorted_df[:mid], metric_col, aggregation) or 0
            parent_p2 = _safe_agg(sorted_df[mid:], metric_col, aggregation) or 0
        except Exception:
            mid = df.height // 2
            parent_p1 = _safe_agg(df[:mid], metric_col, aggregation) or 0
            parent_p2 = _safe_agg(df[mid:], metric_col, aggregation) or 0
    else:
        mid = df.height // 2
        parent_p1 = _safe_agg(df[:mid], metric_col, aggregation) or 0
        parent_p2 = _safe_agg(df[mid:], metric_col, aggregation) or 0

    parent_change = parent_p2 - parent_p1
    parent_change_pct = ((parent_change / abs(parent_p1)) * 100) if parent_p1 != 0 else 0

    # Compute each component's contribution
    detailed: List[Dict[str, Any]] = []
    for comp in components:
        col = comp["column"]
        if col not in df.columns:
            continue

        if time_col and time_col in df.columns:
            try:
                sorted_df = df.sort(time_col)
                mid = sorted_df.height // 2
                c_p1 = _safe_agg(sorted_df[:mid], col, aggregation) or 0
                c_p2 = _safe_agg(sorted_df[mid:], col, aggregation) or 0
            except Exception:
                mid = df.height // 2
                c_p1 = _safe_agg(df[:mid], col, aggregation) or 0
                c_p2 = _safe_agg(df[mid:], col, aggregation) or 0
        else:
            mid = df.height // 2
            c_p1 = _safe_agg(df[:mid], col, aggregation) or 0
            c_p2 = _safe_agg(df[mid:], col, aggregation) or 0

        c_change = c_p2 - c_p1
        c_change_pct = ((c_change / abs(c_p1)) * 100) if c_p1 != 0 else 0

        # Contribution to parent change (percentage points)
        contrib_to_parent = (c_change / abs(parent_p1)) * 100 if parent_p1 != 0 else 0

        detailed.append({
            "column": col,
            "value_before": round(c_p1, 2),
            "value_after": round(c_p2, 2),
            "change": round(c_change, 2),
            "change_pct": round(c_change_pct, 1),
            "contribution_pp": round(contrib_to_parent, 2),
            "contribution_pct_of_change": round(abs(contrib_to_parent / parent_change_pct) * 100, 1) if parent_change_pct != 0 else 0,
            "formula": comp.get("formula", ""),
            "relationship_type": comp.get("relationship_type", ""),
        })

    detailed.sort(key=lambda d: -abs(d["contribution_pp"]))

    return {
        "metric": metric_col,
        "value_before": round(parent_p1, 2),
        "value_after": round(parent_p2, 2),
        "change": round(parent_change, 2),
        "change_pct": round(parent_change_pct, 1),
        "components": detailed,
        "component_count": len(detailed),
        "has_decomposition": len(detailed) > 0,
    }


# ── Batch API for KPI Cards ────────────────────────────────────────────────


def attach_metric_decompositions(
    kpis: List[Dict[str, Any]],
    graph: MetricGraph,
    df: pl.DataFrame,
    time_col: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Attach metric decomposition to KPI cards that have graph relationships.

    Adds 'metric_decomposition' field to KPI dicts — a component-level
    breakdown of what drives the metric, beyond just segment root cause.

    Args:
        kpis: List of KPI card dicts
        graph: MetricGraph
        df: DataFrame
        time_col: Optional time column

    Returns:
        Updated KPI cards with metric_decomposition field
    """
    for kpi in kpis:
        col = kpi.get("column")
        if not col or col not in df.columns:
            continue
        if not graph.has_metric(col):
            continue

        try:
            decomp = decompose_metric_change(
                df, col, graph, time_col,
                aggregation=kpi.get("aggregation", "sum"),
            )
            if decomp["has_decomposition"]:
                kpi["metric_decomposition"] = decomp
        except Exception as e:
            logger.debug(f"[MetricGraph] Decomposition failed for '{col}': {e}")
            continue

    return kpis
