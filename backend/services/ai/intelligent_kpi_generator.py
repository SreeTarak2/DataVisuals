# backend/services/ai/intelligent_kpi_generator.py

"""
Intelligent KPI Generator - v3 (Honest Edition)
================================================
Generates contextual, domain-aware KPIs using LLM + real data.

Key changes from v2:
- Enriched LLM prompt with domain, statistical findings, data profile
- NO fabricated comparison/target values — uses real data or omits
- Domain-aware fallback when LLM fails
"""

import logging
import math
from typing import Dict, List, Any, Optional
import polars as pl
import json

from services.llm_router import llm_router
from core.prompts import PromptFactory, PromptType, extract_and_validate, KPIGeneratorResponse

logger = logging.getLogger(__name__)


class IntelligentKPIGenerator:
    """
    Generates intelligent, context-aware KPIs using LLM with rich domain context.
    All comparison/context data is derived from real data — nothing fabricated.
    """

    def __init__(self):
        pass

    async def generate_intelligent_kpis(
        self,
        df: pl.DataFrame,
        domain: Optional[str] = None,
        max_kpis: int = 8,
        dataset_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate dynamic KPIs using LLM with enriched context.

        Args:
            df: Polars DataFrame
            domain: Detected domain (e.g., "ecommerce", "healthcare")
            max_kpis: Maximum number of KPIs to generate
            dataset_metadata: Full metadata dict from MongoDB (contains domain_intelligence,
                            data_profile, deep_analysis, statistical_findings, etc.)
        
        Returns:
            List of KPI configurations with real data
        """
        metadata = dataset_metadata or {}

        try:
            # Build enriched column metadata for the LLM
            column_metadata = []
            for col in df.columns:
                dtype = str(df[col].dtype)
                sample_value = df[col][0] if len(df) > 0 else ""
                col_info = {
                    "name": col,
                    "type": dtype,
                    "sample_value": sample_value,
                }
                column_metadata.append(col_info)

            dataset_overview = {
                "total_rows": len(df),
                "total_columns": len(df.columns),
            }

            # Build enriched prompt metadata
            prompt_metadata = {
                "column_metadata": column_metadata,
                "dataset_overview": dataset_overview,
            }

            # Inject domain intelligence if available
            domain_intel = metadata.get("domain_intelligence", {})
            if domain_intel:
                prompt_metadata["domain_context"] = {
                    "domain": domain_intel.get("domain", domain or "general"),
                    "confidence": domain_intel.get("confidence", 0),
                    "key_metrics": domain_intel.get("key_metrics", []),
                    "dimensions": domain_intel.get("dimensions", []),
                    "measures": domain_intel.get("measures", []),
                    "time_columns": domain_intel.get("time_columns", []),
                }
            elif domain:
                prompt_metadata["domain_context"] = {"domain": domain}

            # Inject data profile highlights if available
            data_profile = metadata.get("data_profile", {})
            if data_profile:
                prompt_metadata["data_profile"] = {
                    "id_columns": data_profile.get("id_columns", []),
                    "low_cardinality_dims": data_profile.get("low_cardinality_dims", []),
                    "high_cardinality_dims": data_profile.get("high_cardinality_dims", []),
                }

            # Inject deep analysis highlights if available
            deep_analysis = metadata.get("deep_analysis", {})
            enhanced = deep_analysis.get("enhanced_analysis", {})
            if enhanced:
                # Top 3 correlations for context
                top_corr = enhanced.get("correlations", [])[:3]
                if top_corr:
                    prompt_metadata["top_correlations"] = [
                        {
                            "columns": [c.get("column1", ""), c.get("column2", "")],
                            "r": round(c.get("correlation", 0), 3),
                            "strength": c.get("strength", ""),
                        }
                        for c in top_corr
                    ]

                # Distribution anomalies
                skewed = [
                    d.get("column", "")
                    for d in enhanced.get("distributions", [])
                    if abs(d.get("skewness", 0)) > 1.5
                ]
                if skewed:
                    prompt_metadata["skewed_columns"] = skewed[:5]

            # Build prompt via factory
            factory = PromptFactory(prompt_metadata)
            prompt = factory.get_prompt(PromptType.KPI_GENERATOR)

            # Call LLM
            response = await llm_router.call(
                task="kpi_suggestion",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            )

            # Validate and extract
            result = extract_and_validate(response, KPIGeneratorResponse)
            kpis = result.kpis[:max_kpis]

            # Validate columns exist before any Polars access
            kpis = self._validate_kpi_columns(df, kpis)

            # Compute actual values and real enrichment data
            for kpi in kpis:
                kpi["value"] = self._calculate_kpi_value(
                    df, kpi["column"], kpi["aggregation"],
                    secondary=kpi.get("secondary_column"),
                )
                self._enrich_with_real_data(kpi, df, metadata)

            logger.info(
                f"Generated {len(kpis)} KPIs for archetype '{result.archetype}' "
                f"(confidence: {result.confidence})"
            )
            return kpis

        except Exception as e:
            logger.error(f"Dynamic KPI generation failed: {e} — falling back to domain-aware generic")
            return self._generate_domain_aware_kpis(df, max_kpis, metadata)

    # =========================================================================
    # REAL DATA ENRICHMENT (replaces fake random-based methods)
    # =========================================================================

    def _validate_kpi_columns(
        self, df: pl.DataFrame, kpis: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate that LLM-suggested columns exist in the DataFrame.
        Skips KPIs with hallucinated columns, clears invalid secondary columns.
        """
        valid_columns = set(df.columns)
        valid_kpis = []

        for kpi in kpis:
            col = kpi.get("column", "")
            if col not in valid_columns:
                logger.warning(
                    f"LLM hallucinated column: '{col}' — skipping KPI '{kpi.get('title', '?')}'. "
                    f"Available: {sorted(valid_columns)[:10]}..."
                )
                continue
            sec = kpi.get("secondary_column")
            if sec and sec not in valid_columns:
                logger.warning(
                    f"Secondary column '{sec}' not found for KPI '{kpi.get('title', '?')}' — clearing"
                )
                kpi["secondary_column"] = None
            valid_kpis.append(kpi)

        if len(valid_kpis) < len(kpis):
            logger.info(
                f"Column validation: {len(valid_kpis)}/{len(kpis)} KPIs passed validation"
            )
        return valid_kpis

    def _enrich_with_real_data(
        self, kpi: Dict[str, Any], df: pl.DataFrame, metadata: Dict[str, Any]
    ) -> None:
        """
        Enrich a KPI with REAL data — no fabricated values.

        - Format: inferred from column name/value
        - Comparison: real first-half vs second-half of dataset (if meaningful)
        - Target: replaced with percentile context (p75/p90)
        - Sparkline: sampled from actual column values
        - Context: derived from real comparison or statistical position
        """
        value = kpi.get("value", 0)
        column = kpi.get("column", "")
        aggregation = kpi.get("aggregation", "sum")

        # Infer display format
        kpi["format"] = self._infer_format(column, value)

        # Real comparison: split dataset into halves and compare
        comparison = self._calculate_real_comparison(df, column, aggregation)
        if comparison is not None:
            kpi["comparison_value"] = comparison["previous"]
            kpi["comparison_label"] = comparison["label"]
            kpi["delta_percent"] = comparison["delta_percent"]
            kpi["delta_direction"] = comparison["delta_direction"]
            kpi["context"] = comparison["context"]
        else:
            kpi["comparison_value"] = None
            kpi["comparison_label"] = ""
            kpi["delta_percent"] = None
            kpi["delta_direction"] = None
            kpi["context"] = self._calculate_percentile_context(df, column, value, aggregation)

        # Percentile position instead of fabricated target
        kpi["target_value"] = None
        kpi["target_label"] = None

        # Real sparkline from actual data (prefers time-series binning)
        kpi["sparkline_data"] = self._generate_sparkline_data(df, column, aggregation)

    def _calculate_real_comparison(
        self, df: pl.DataFrame, column: str, aggregation: str
    ) -> Optional[Dict[str, Any]]:
        """
        Compare first half vs second half of dataset.
        Sorts by datetime column if available for meaningful temporal comparison.
        Returns None if comparison isn't meaningful.
        """
        try:
            if column not in df.columns:
                return None

            col_data = df[column].drop_nulls()
            if len(col_data) < 10:
                return None

            # Sort by datetime column if one exists (critical for temporal accuracy)
            date_col = None
            for col_name in df.columns:
                if df[col_name].dtype in (pl.Date, pl.Datetime):
                    date_col = col_name
                    break

            working_df = df.sort(date_col) if date_col else df

            # Split into two halves
            mid = len(working_df) // 2
            first_half = working_df[:mid]
            second_half = working_df[mid:]

            # Compute aggregation for each half
            val_first = self._compute_agg(first_half, column, aggregation)
            val_second = self._compute_agg(second_half, column, aggregation)

            if val_first is None or val_second is None or val_first == 0:
                return None

            delta_pct = round(((val_second - val_first) / abs(val_first)) * 100, 2)
            direction = "↑" if delta_pct >= 0 else "↓"
            is_meaningful = date_col is not None
            label = "vs first half (time-sorted)" if is_meaningful else "vs first half (row order)"

            return {
                "previous": round(val_first, 2),
                "label": label,
                "delta_percent": delta_pct,
                "delta_direction": "up" if delta_pct > 0 else "down" if delta_pct < 0 else "neutral",
                "is_meaningful": is_meaningful,
                "context": f"{direction}{abs(delta_pct):.1f}% {label}",
            }
        except Exception as e:
            logger.debug(f"Real comparison failed for {column}: {e}")
            return None

    def _calculate_percentile_context(
        self, df: pl.DataFrame, column: str, value: Any, aggregation: str
    ) -> str:
        """
        Generate context based on percentile position instead of fabricated targets.
        """
        try:
            if column not in df.columns or not isinstance(value, (int, float)):
                return ""

            col_data = df[column].drop_nulls().cast(pl.Float64)
            if len(col_data) < 5:
                return ""

            median = float(col_data.median())
            p25 = float(col_data.quantile(0.25))
            p75 = float(col_data.quantile(0.75))

            if aggregation in ("mean", "avg"):
                if value > p75:
                    return f"Above 75th percentile (median: {median:,.2f})"
                elif value < p25:
                    return f"Below 25th percentile (median: {median:,.2f})"
                else:
                    return f"Near median ({median:,.2f})"
            elif aggregation == "sum":
                null_pct = (df[column].null_count() / len(df)) * 100
                if null_pct > 10:
                    return f"{null_pct:.0f}% values missing"
                return f"Across {len(col_data):,} records"
            elif aggregation in ("count", "count_unique", "nunique"):
                return f"Out of {len(df):,} total records"
            else:
                return ""
        except Exception:
            return ""

    def _compute_agg(self, df: pl.DataFrame, column: str, aggregation: str) -> Optional[float]:
        """Compute a single aggregation safely."""
        try:
            if column not in df.columns:
                return None
            col = df[column].drop_nulls()
            if len(col) == 0:
                return None

            if aggregation == "sum":
                return float(col.sum())
            elif aggregation in ("mean", "avg"):
                return float(col.mean())
            elif aggregation == "max":
                return float(col.max())
            elif aggregation == "min":
                return float(col.min())
            elif aggregation == "count":
                return float(col.count())
            elif aggregation in ("count_unique", "nunique"):
                return float(col.n_unique())
            else:
                return float(col.sum())
        except Exception:
            return None

    # =========================================================================
    # SPARKLINE (kept — was already using real data)
    # =========================================================================

    def _generate_sparkline_data(
        self,
        df: pl.DataFrame,
        column: str,
        aggregation: str,
        max_points: int = 12,
    ) -> Any:
        """
        Generate sparkline trend data.
        Prefers time-series binning when a datetime column exists.
        Falls back to row sampling otherwise.
        Returns dict with 'data' and 'type' for frontend to label correctly.
        """
        try:
            if column not in df.columns:
                return []

            # Try time-series binning first (more meaningful sparklines)
            date_col = None
            for col_name in df.columns:
                if df[col_name].dtype in (pl.Date, pl.Datetime):
                    date_col = col_name
                    break

            if date_col:
                try:
                    binned = (
                        df.sort(date_col)
                          .with_columns(pl.col(date_col).cast(pl.Date).alias("_spark_date"))
                          .group_by_dynamic("_spark_date", every="1mo")
                          .agg(pl.col(column).mean().alias("_spark_val"))
                          .sort("_spark_date")
                          .tail(max_points)
                    )
                    values = binned["_spark_val"].drop_nulls().to_list()
                    if len(values) >= 3:
                        return {
                            "data": [round(v, 2) for v in values],
                            "type": "time_series"
                        }
                except Exception:
                    pass  # fall through to row sampling

            # Fallback: row sampling (existing logic)
            values = df[column].to_list()
            numeric_values = [
                v for v in values
                if isinstance(v, (int, float)) and v is not None
                and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))
            ]

            if len(numeric_values) < 3:
                return []

            step = max(1, len(numeric_values) // max_points)
            sampled = [numeric_values[i] for i in range(0, len(numeric_values), step)][:max_points]

            return {
                "data": [round(v, 2) if isinstance(v, float) else v for v in sampled],
                "type": "distribution"
            }

        except Exception as e:
            logger.debug(f"Error generating sparkline for {column}: {e}")
            return []

    # =========================================================================
    # FORMAT INFERENCE (kept — was already working correctly)
    # =========================================================================

    def _infer_format(self, column: str, value: Any) -> str:
        """Infer the appropriate display format for a KPI."""
        col_lower = (column or "").lower()

        if any(term in col_lower for term in [
            "price", "revenue", "sales", "cost", "amount", "total",
            "profit", "income", "expense", "budget", "salary", "fee",
        ]):
            return "currency"

        if any(term in col_lower for term in [
            "rate", "ratio", "percent", "pct", "growth", "change", "margin",
        ]):
            return "percentage"

        if any(term in col_lower for term in [
            "count", "quantity", "qty", "units", "number", "num",
        ]):
            return "integer"

        if isinstance(value, float) and 0 <= value <= 1:
            return "percentage"

        if isinstance(value, int):
            return "integer"

        return "number"

    # =========================================================================
    # KPI VALUE CALCULATION (kept — was already using real data)
    # =========================================================================

    def _calculate_kpi_value(
        self,
        df: pl.DataFrame,
        column: str,
        aggregation: str,
        secondary: Optional[str] = None,
    ) -> Any:
        """Calculate KPI value from real data."""
        try:
            if aggregation == "sum":
                return int(df[column].sum())
            elif aggregation == "mean":
                return round(float(df[column].mean()), 2)
            elif aggregation == "max":
                return float(df[column].max())
            elif aggregation == "min":
                return float(df[column].min())
            elif aggregation == "count":
                return int(df[column].count())
            elif aggregation == "count_unique":
                return int(df[column].n_unique())
            elif aggregation == "last":
                return df[column].tail(1)[0]
            elif aggregation == "range":
                # Return structured data — frontend formats as "min – max"
                return {
                    "min": round(float(df[column].min()), 2),
                    "max": round(float(df[column].max()), 2)
                }
            elif aggregation == "pct_change":
                if not secondary:
                    logger.warning(
                        f"pct_change requires secondary_column, none provided for '{column}' — returning None"
                    )
                    return None
                sorted_df = df.sort(secondary)
                prices = sorted_df[column].to_list()
                changes = [
                    (prices[i] - prices[i - 1]) / prices[i - 1] * 100
                    for i in range(1, len(prices))
                    if prices[i - 1] != 0
                ]
                return round(sum(changes) / len(changes), 2) if changes else 0
            elif aggregation == "std":
                return round(float(df[column].std()), 2)
            elif aggregation in ("ratio", "percentage") and secondary:
                # Unified: always compute as percentage (value * 100)
                # Eliminates ambiguity — frontend always shows as X%
                denom = df[secondary].count()
                if denom > 0:
                    return round((df[column].sum() / denom) * 100, 1)
                return 0
            else:
                return df[column].sum()
        except Exception as e:
            logger.error(f"Error calculating KPI for {column} with {aggregation}: {e}")
            return 0

    # =========================================================================
    # DOMAIN-AWARE FALLBACK (replaces blind generic fallback)
    # =========================================================================

    def _generate_domain_aware_kpis(
        self,
        df: pl.DataFrame,
        max_kpis: int,
        metadata: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Domain-aware fallback when LLM fails.
        Uses domain detection results to pick meaningful KPIs.
        """
        kpis = []
        domain_intel = metadata.get("domain_intelligence", {})
        data_profile = metadata.get("data_profile", {})

        # Columns to skip (IDs, high-cardinality dims)
        skip_cols = set(data_profile.get("id_columns", []))
        skip_cols.update(data_profile.get("high_cardinality_dims", []))

        # Prefer domain-identified measures and key metrics
        preferred_cols = []
        for col in domain_intel.get("key_metrics", []):
            if col in df.columns and col not in skip_cols:
                preferred_cols.append(col)
        for col in domain_intel.get("measures", []):
            if col in df.columns and col not in skip_cols and col not in preferred_cols:
                preferred_cols.append(col)

        # Fall back to numeric columns if no domain info
        numeric_cols = [
            col for col in df.select(pl.col(pl.NUMERIC_DTYPES)).columns
            if col not in skip_cols
        ]
        if not preferred_cols:
            preferred_cols = numeric_cols

        # Generate KPIs from preferred columns
        for col in preferred_cols[:max_kpis]:
            try:
                # Pick the most meaningful aggregation for this column
                aggregation = self._pick_best_aggregation(df, col)
                value = self._calculate_kpi_value(df, col, aggregation)

                kpi = {
                    "title": self._humanize_column_name(col, aggregation),
                    "value": value,
                    "column": col,
                    "aggregation": aggregation,
                    "importance": "high" if col in domain_intel.get("key_metrics", []) else "medium",
                }
                self._enrich_with_real_data(kpi, df, metadata)
                kpis.append(kpi)
            except Exception:
                continue

        # Add a count-based KPI if we have room
        if len(kpis) < max_kpis:
            dims = domain_intel.get("dimensions", [])
            low_card = data_profile.get("low_cardinality_dims", [])
            cat_cols = dims or low_card

            for col in cat_cols:
                if col in df.columns and len(kpis) < max_kpis:
                    try:
                        unique_count = int(df[col].n_unique())
                        kpi = {
                            "title": f"Unique {self._humanize_column_name(col, 'count_unique')}",
                            "value": unique_count,
                            "column": col,
                            "aggregation": "count_unique",
                            "importance": "medium",
                        }
                        self._enrich_with_real_data(kpi, df, metadata)
                        kpis.append(kpi)
                    except Exception:
                        continue

        return kpis[:max_kpis]

    def _pick_best_aggregation(self, df: pl.DataFrame, column: str) -> str:
        """Pick the most meaningful aggregation for a column based on its data."""
        col_lower = column.lower()

        # Revenue/sales/cost → sum
        if any(term in col_lower for term in [
            "revenue", "sales", "cost", "total", "amount", "income", "profit",
            "expense", "budget", "fee", "salary",
        ]):
            return "sum"

        # Rate/ratio/percentage → mean
        if any(term in col_lower for term in [
            "rate", "ratio", "percent", "pct", "average", "avg", "score",
            "rating", "index", "margin",
        ]):
            return "mean"

        # Count-like → count_unique
        if any(term in col_lower for term in [
            "id", "name", "category", "type", "status",
        ]):
            return "count_unique"

        # Default: check value range — if all similar values, use mean; if varied, use sum
        try:
            col_data = df[column].drop_nulls()
            if len(col_data) > 0:
                cv = float(col_data.std()) / float(col_data.mean()) if float(col_data.mean()) != 0 else 0
                if cv < 0.3:
                    return "mean"  # Low variance → average is meaningful
                return "sum"
        except Exception:
            pass

        return "sum"

    def _humanize_column_name(self, column: str, aggregation: str) -> str:
        """Convert column_name to a human-readable KPI title."""
        name = column.replace("_", " ").replace("-", " ").strip().title()

        agg_prefix = {
            "sum": "Total",
            "mean": "Average",
            "avg": "Average",
            "max": "Highest",
            "min": "Lowest",
            "count": "Count of",
            "count_unique": "",
            "std": "Std Dev of",
        }

        prefix = agg_prefix.get(aggregation, "")
        if prefix:
            return f"{prefix} {name}"
        return name


# Singleton instance
intelligent_kpi_generator = IntelligentKPIGenerator()