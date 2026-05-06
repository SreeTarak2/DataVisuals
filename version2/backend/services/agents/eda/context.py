"""
AgentContext — the shared blackboard that flows through all 6 EDA agents.

All pre-computed data from the Celery pipeline is loaded once at the start.
Each agent reads what it needs and writes its output back here.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentContext:
    # ── Inputs ──────────────────────────────────────────────
    dataset_id: str
    user_id: str
    user_question: str          # already sanitized (max 500 chars, stripped)

    # ── Pre-computed by Celery pipeline (loaded from MongoDB) ──
    dataset_name: str = ""
    domain: str = "general"
    row_count: int = 0
    column_count: int = 0
    column_metadata: List[Dict] = field(default_factory=list)
    data_quality: Dict = field(default_factory=dict)
    statistical_findings: Dict = field(default_factory=dict)  # correlations normalized to {column_a, column_b, correlation}
    deep_analysis: Dict = field(default_factory=dict)          # enhanced_analysis + quis_insights
    chart_recommendations: List[Dict] = field(default_factory=list)
    sample_data: List[Dict] = field(default_factory=list)
    domain_intelligence: Dict = field(default_factory=dict)

    # ── Agent outputs (filled as pipeline runs) ─────────────
    planner_output: Dict = field(default_factory=dict)      # Agent 1: intent, key_columns, plan
    data_passport: Dict = field(default_factory=dict)       # Agent 2: structured data summary
    univariate_report: Dict = field(default_factory=dict)   # Agent 3: per-column insights
    bivariate_report: Dict = field(default_factory=dict)    # Agent 4: relationships & patterns
    chart_configs: List[Dict] = field(default_factory=list) # Agent 5: Plotly-ready configs
    validation_result: Dict = field(default_factory=dict)   # Agent 6: QA pass/fail + fixes

    # ── Pipeline metadata ────────────────────────────────────
    errors: List[str] = field(default_factory=list)
    partial_failure: bool = False          # True if any agent failed/timed-out
    timings: Dict[str, float] = field(default_factory=dict)  # agent_name → seconds

    # ── Helpers ──────────────────────────────────────────────

    def schema_summary(self, priority_cols: Optional[List[str]] = None) -> str:
        """
        Compact schema string for LLM prompts.
        priority_cols (from planner's key_columns) are always included first.
        Remaining columns fill up to the cap of 40.
        """
        cap = 40
        all_cols = {c["name"]: c for c in self.column_metadata}

        ordered: List[Dict] = []
        if priority_cols:
            for name in priority_cols:
                if name in all_cols:
                    ordered.append(all_cols[name])

        for col in self.column_metadata:
            if len(ordered) >= cap:
                break
            if col not in ordered:
                ordered.append(col)

        if len(self.column_metadata) > cap:
            truncated = len(self.column_metadata) - len(ordered)
            suffix = f"\n  ... (+{truncated} more columns not shown)"
        else:
            suffix = ""

        lines = []
        for col in ordered:
            dtype = col.get("type", "unknown")
            nulls = col.get("null_percentage", 0)
            uniq = col.get("unique_count", "?")
            extra = ""
            if "numeric_summary" in col:
                ns = col["numeric_summary"]
                extra = f" | min={ns.get('min')}, max={ns.get('max')}, mean={ns.get('mean')}"
            lines.append(f"  {col['name']} ({dtype}) — {nulls:.1f}% null, {uniq} unique{extra}")
        return "\n".join(lines) + suffix

    def top_correlations(self, n: int = 5) -> List[Dict]:
        """Returns correlations — guaranteed schema: {column_a, column_b, correlation}."""
        return (self.statistical_findings.get("correlations") or [])[:n]

    def top_quis_insights(self, n: int = 5) -> List[Dict]:
        quis = self.deep_analysis.get("quis_insights", {})
        return (quis.get("top_insights") or quis.get("insights") or [])[:n]

    def column_by_name(self, name: str) -> Optional[Dict]:
        """O(1) lookup by column name (builds cache on first call)."""
        if not hasattr(self, "_col_index"):
            object.__setattr__(self, "_col_index", {c["name"]: c for c in self.column_metadata})
        return self._col_index.get(name)

    def valid_column_names(self) -> set:
        """Set of all known column names — used for deterministic validation."""
        return {c["name"] for c in self.column_metadata}
