"""
Dashboard Schemas (Core)
------------------------
This module defines ALL schemas related to dashboard generation:
- Component types
- Chart/KPI/Table/Text configuration
- DashboardBlueprint (single source of truth)
- SchemaRepairer for fixing LLM-produced invalid structures

Every dashboard-related service MUST use these models.
"""

from typing import List, Dict, Any, Optional, Union, Sequence, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

# -------------------------
# ENUMS
# -------------------------
class ComponentType(str, Enum):
    KPI = "kpi"
    CHART = "chart"
    TABLE = "table"
    TEXT = "text"


class ChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    HISTOGRAM = "histogram"
    BOX_PLOT = "box_plot"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    TREEMAP = "treemap"
    GROUPED_BAR = "grouped_bar"
    AREA = "area"


class AggregationType(str, Enum):
    SUM = "sum"
    MEAN = "mean"
    COUNT = "count"
    NUNIQUE = "nunique"
    FIRST = "first"
    NONE = "none"


class LayoutGrid(str, Enum):
    FOUR_COL = "repeat(4, 1fr)"
    THREE_COL = "repeat(3, 1fr)"
    TWO_COL = "repeat(2, 1fr)"
    ONE_COL = "1fr"


# -------------------------
# BASE COMPONENT
# -------------------------
class BaseComponentConfig(BaseModel):
    type: ComponentType
    title: str = Field(..., min_length=1, max_length=100)
    span: int = Field(1, ge=1, le=4)

    class Config:
        extra = "forbid"
        use_enum_values = True
        from_attributes = True  # Pydantic v2: renamed from orm_mode


# -------------------------
# KPI COMPONENT
# -------------------------
class KpiConfig(BaseComponentConfig):
    type: Literal[ComponentType.KPI] = ComponentType.KPI
    column: str
    aggregation: AggregationType = AggregationType.COUNT
    icon: Optional[str] = None
    color: Optional[str] = None


# -------------------------
# CHART COMPONENT
# -------------------------
class ChartConfig(BaseComponentConfig):
    type: Literal[ComponentType.CHART] = ComponentType.CHART
    chart_type: ChartType
    columns: List[str] = Field(..., min_length=1, max_length=4)
    aggregation: AggregationType = AggregationType.SUM
    group_by: Optional[List[str]] = None

    class Config:
        extra = "forbid"
        from_attributes = True

    @field_validator("columns", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if isinstance(v, str):
            return [c.strip() for c in v.split(",")]
        return v

    @model_validator(mode="after")
    def validate_chart(self):
        t = self.chart_type
        cols = self.columns

        if t == ChartType.PIE and len(cols) != 2:
            raise ValueError("Pie requires exactly two columns.")

        if t in [ChartType.BAR, ChartType.LINE] and len(cols) < 2:
            raise ValueError("Bar/Line require x and y columns.")

        return self


# -------------------------
# TABLE COMPONENT
# -------------------------
class TableConfig(BaseComponentConfig):
    type: Literal[ComponentType.TABLE] = ComponentType.TABLE
    columns: List[str] = Field(..., min_length=1, max_length=20)
    limit: int = Field(10, ge=1, le=500)


# -------------------------
# TEXT COMPONENT
# -------------------------
class TextConfig(BaseComponentConfig):
    type: Literal[ComponentType.TEXT] = ComponentType.TEXT
    content: str = Field(..., min_length=1, max_length=2000)


# -------------------------
# UNION
# -------------------------
ComponentConfig = Union[KpiConfig, ChartConfig, TableConfig, TextConfig]


# -------------------------
# DASHBOARD BLUEPRINT
# -------------------------
class DashboardBlueprint(BaseModel):
    layout_grid: LayoutGrid = LayoutGrid.FOUR_COL
    components: List[ComponentConfig] = Field(..., min_length=1, max_length=50)
    version: str = "1.0"
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "forbid"
        use_enum_values = True
        from_attributes = True

    @model_validator(mode="after")
    def validate_spans(self):
        layout = self.layout_grid
        comps = self.components

        grid_cols = {
            LayoutGrid.FOUR_COL: 4,
            LayoutGrid.THREE_COL: 3,
            LayoutGrid.TWO_COL: 2,
            LayoutGrid.ONE_COL: 1,
        }
        max_cols = grid_cols[layout]

        for comp in comps:
            if comp.span > max_cols:
                raise ValueError(
                    f"Component span {comp.span} exceeds grid width {max_cols}"
                )

        return self


# -------------------------
# SCHEMA REPAIRER
# -------------------------

class SchemaRepairer:
    """
    Pure dict -> dict SchemaRepairer.
    Input:
        - blueprint_dict: raw dict (from LLM)
        - schema_columns: Sequence of column names OR list of column dicts
    Output:
        - repaired dict (compatible with DashboardBlueprint.parse_obj)
    Guarantees:
        - returns a dict (never Pydantic models)
        - ensures layout_grid and components keys exist
        - normalizes chart_type strings
        - fuzzy-matches/repairs column names using provided schema_columns
        - guarantees at least one KPI and one chart component
    """

    @staticmethod
    def repair(blueprint_dict: Dict[str, Any], schema_columns: Sequence) -> Dict[str, Any]:
        # Defensive inputs
        if not isinstance(blueprint_dict, dict):
            blueprint_dict = {}

        # Normalize schema_columns into a list of names
        if not schema_columns:
            names: List[str] = []
        elif isinstance(schema_columns[0], dict):
            names = [c.get("name") for c in schema_columns if c.get("name")]
        else:
            names = [c for c in schema_columns]

        all_cols = [c for c in names if c]
        all_cols_lower = {c.lower(): c for c in all_cols}

        # layout_grid safe default
        layout = blueprint_dict.get("layout_grid")
        if not isinstance(layout, str) or "repeat" not in layout:
            layout = "repeat(4, 1fr)"

        repaired = {"layout_grid": layout, "components": []}

        raw_components = blueprint_dict.get("components") or []
        if not isinstance(raw_components, list):
            raw_components = []

        for comp in raw_components:
            if not isinstance(comp, dict):
                # skip malformed component
                logger.debug("Dropping non-dict component: %r", comp)
                continue

            ctype = (comp.get("type") or "").lower()

            if ctype == "kpi":
                fixed = SchemaRepairer._fix_kpi(comp, all_cols, all_cols_lower)
            elif ctype == "chart":
                fixed = SchemaRepairer._fix_chart(comp, all_cols, all_cols_lower)
            elif ctype == "table":
                fixed = SchemaRepairer._fix_table(comp, all_cols, all_cols_lower)
            else:
                # unknown, drop it
                logger.debug("Dropping unknown component type: %r", ctype)
                fixed = None

            if fixed:
                repaired["components"].append(fixed)

        # Ensure minimum components exist: >=1 KPI and >=1 chart
        SchemaRepairer._ensure_minimum_components(repaired, all_cols)

        return repaired

    # ---------- internal helpers ----------
    @staticmethod
    def _normalize_chart_type(raw: Optional[str]) -> str:
        if not raw:
            return "bar"
        rt = str(raw).lower()
        mapping = {
            "bar_chart": "bar", "bar": "bar",
            "line_chart": "line", "line": "line",
            "pie_chart": "pie", "pie": "pie",
            "histogram": "histogram", "hist": "histogram",
            "box_plot": "box_plot", "box": "box_plot",
            "scatter_plot": "scatter", "scatter": "scatter",
            "heatmap": "heatmap", "treemap": "treemap",
            "grouped_bar": "grouped_bar", "grouped_bar_chart": "grouped_bar",
            "area_chart": "area", "area": "area"
        }
        if rt in mapping:
            return mapping[rt]
        # fallback: substring matching
        clean = re.sub(r"[^a-z0-9_]", "_", rt)
        for k, v in mapping.items():
            if k in clean:
                return v
        return "bar"

    @staticmethod
    def _fuzzy_col(candidate: Any, all_cols: List[str], all_cols_lower: Dict[str, str]) -> Optional[str]:
        if not candidate or not isinstance(candidate, str):
            return None
        # direct
        if candidate in all_cols:
            return candidate
        lc = candidate.lower()
        if lc in all_cols_lower:
            return all_cols_lower[lc]
        # normalized compare (strip non-alnum)
        norm = re.sub(r"[^a-z0-9]", "", lc)
        for col in all_cols:
            if re.sub(r"[^a-z0-9]", "", col.lower()) == norm:
                return col
        # substring match
        for col in all_cols:
            if lc in col.lower() or col.lower() in lc:
                return col
        return None

    @staticmethod
    def _fix_kpi(comp: Dict[str, Any], all_cols: List[str], all_cols_lower: Dict[str, str]) -> Dict[str, Any]:
        cfg = comp.get("config") or {}
        title = comp.get("title") or cfg.get("title") or "KPI"
        span = int(comp.get("span", 1) or 1)
        # column may be in config or directly present
        col = cfg.get("column") or (cfg.get("columns") and (cfg.get("columns")[0] if isinstance(cfg.get("columns"), list) else cfg.get("columns"))) or "__all__"
        col_fixed = SchemaRepairer._fuzzy_col(col, all_cols, all_cols_lower) or "__all__"
        agg = (cfg.get("aggregation") or "count").lower()
        agg = agg if agg in {"sum", "mean", "count", "nunique", "first", "none"} else "count"
        return {
            "type": "kpi",
            "title": title,
            "span": span,
            "config": {"title": title, "column": col_fixed, "aggregation": agg}
        }

    @staticmethod
    def _fix_chart(comp: Dict[str, Any], all_cols: List[str], all_cols_lower: Dict[str, str]) -> Dict[str, Any]:
        cfg = comp.get("config") or {}
        title = comp.get("title") or cfg.get("title") or "Chart"
        span = int(comp.get("span", 2) or 2)
        raw_type = cfg.get("chart_type") or cfg.get("type") or "bar"
        chart_type = SchemaRepairer._normalize_chart_type(raw_type)
        raw_cols = cfg.get("columns") or cfg.get("cols") or []
        if isinstance(raw_cols, str):
            raw_cols = [raw_cols]
        fixed_cols = []
        for c in raw_cols:
            match = SchemaRepairer._fuzzy_col(c, all_cols, all_cols_lower)
            if match:
                fixed_cols.append(match)
        if not fixed_cols:
            if all_cols:
                fixed_cols = [all_cols[0]]
            else:
                fixed_cols = ["__all__"]
        agg = (cfg.get("aggregation") or "sum").lower()
        agg = agg if agg in {"sum", "mean", "count", "nunique", "first", "none"} else "sum"
        group = cfg.get("group_by") or []
        if isinstance(group, str):
            group = [group]
        fixed_group = [g for g in (SchemaRepairer._fuzzy_col(g, all_cols, all_cols_lower) for g in group) if g]
        return {
            "type": "chart",
            "title": title,
            "span": span,
            "config": {
                "title": title,
                "chart_type": chart_type,
                "columns": fixed_cols,
                "aggregation": agg,
                "group_by": fixed_group
            }
        }

    @staticmethod
    def _fix_table(comp: Dict[str, Any], all_cols: List[str], all_cols_lower: Dict[str, str]) -> Dict[str, Any]:
        cfg = comp.get("config") or {}
        title = comp.get("title") or cfg.get("title") or "Table"
        span = int(comp.get("span", 4) or 4)
        cols = cfg.get("columns") or []
        if isinstance(cols, str):
            cols = [cols]
        fixed = [SchemaRepairer._fuzzy_col(c, all_cols, all_cols_lower) for c in cols]
        fixed = [c for c in fixed if c]
        if not fixed:
            fixed = all_cols[:6]
        limit = int(cfg.get("limit", 200) or 200)
        limit = max(1, min(limit, 1000))
        return {"type": "table", "title": title, "span": span, "config": {"title": title, "columns": fixed, "limit": limit}}

    @staticmethod
    def _ensure_minimum_components(bp: Dict[str, Any], all_cols: List[str]):
        comps = bp.get("components", [])
        has_kpi = any(c.get("type") == "kpi" for c in comps)
        has_chart = any(c.get("type") == "chart" for c in comps)
        if not has_kpi:
            bp["components"].insert(0, {"type": "kpi", "title": "Total Records", "span": 1, "config": {"title": "Total Records", "column": "__all__", "aggregation": "count"}})
        if not has_chart:
            first = all_cols[0] if all_cols else "__all__"
            bp["components"].insert(1, {"type": "chart", "title": "Auto Chart", "span": 2, "config": {"title": "Auto Chart", "chart_type": "bar", "columns": [first], "aggregation": "sum", "group_by": []}})


__all__ = [
    "DashboardBlueprint",
    "ComponentConfig",
    "ChartConfig",
    "KpiConfig",
    "TableConfig",
    "TextConfig",
    "SchemaRepairer",
    "ComponentType",
    "ChartType",
    "AggregationType",
    "LayoutGrid",
]
