# backend/services/ai/intelligent_kpi_generator.py

"""
Intelligent KPI Generator
=========================
Fully dynamic KPI generation using LLM for any dataset.
No more static templates — detects domain + generates perfect KPIs automatically.
"""

import logging
from typing import Dict, List, Any, Optional
import polars as pl
import json

from services.llm_router import llm_router
from core.prompts import PromptFactory, PromptType, extract_and_validate, KPIGeneratorResponse

logger = logging.getLogger(__name__)


class IntelligentKPIGenerator:
    """
    Generates intelligent, context-aware KPIs using LLM for domain detection and KPI design.
    Falls back to generic if LLM fails.
    """

    def __init__(self):
        pass  # No static templates — fully dynamic

    async def generate_intelligent_kpis(
        self,
        df: pl.DataFrame,
        domain: Optional[str] = None,
        max_kpis: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Generate dynamic KPIs using unbreakable LLM prompt.
        
        Returns:
            List of KPI configurations:
            [
                {
                    "title": "Current Price",
                    "value": 687.39,
                    "column": "price",
                    "aggregation": "last",
                    "format": "currency",
                    "importance": "hero",
                    "context": "↓0.5% today"
                }
            ]
        """
        try:
            # Prep metadata for PromptFactory
            column_metadata = []
            for col in df.columns:
                dtype = str(df[col].dtype)
                sample_value = df[col][0] if len(df) > 0 else ""
                column_metadata.append({
                    "name": col,
                    "type": dtype,
                    "sample_value": sample_value
                })

            dataset_overview = {
                "total_rows": len(df),
                "total_columns": len(df.columns)
            }

            metadata = {
                "column_metadata": column_metadata,
                "dataset_overview": dataset_overview
            }

            # Build unbreakable prompt via factory
            factory = PromptFactory(metadata)
            prompt = factory.get_prompt(PromptType.KPI_GENERATOR)

            # Call LLM via router
            response = await llm_router.call(
                task="kpi_suggestion",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0 
            )

            # Validate and extract
            result = extract_and_validate(response, KPIGeneratorResponse)
            kpis = result.kpis[:max_kpis]

            # Compute actual values using existing calculator
            for kpi in kpis:
                kpi["value"] = self._calculate_kpi_value(
                    df, kpi["column"], kpi["aggregation"], 
                    secondary=kpi.get("secondary_column")
                )

            logger.info(f"Generated {len(kpis)} dynamic KPIs for archetype '{result.archetype}' (confidence: {result.confidence})")
            return kpis

        except Exception as e:
            logger.error(f"Dynamic KPI generation failed: {e} — falling back to generic")
            return self._generate_generic_kpis(df, max_kpis)

    def _calculate_kpi_value(
        self, 
        df: pl.DataFrame, 
        column: str, 
        aggregation: str, 
        secondary: Optional[str] = None
    ) -> Any:
        """
        Calculate KPI value. Supports ratio/percentage for secondary.
        """
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
                return f"{df[column].min()} – {df[column].max()}"
            elif aggregation == "pct_change" and secondary:  # e.g., price over date
                sorted_df = df.sort(secondary)
                prices = sorted_df[column].to_list()
                changes = [(prices[i] - prices[i-1]) / prices[i-1] * 100 for i in range(1, len(prices))]
                return round(sum(changes) / len(changes), 2)
            elif aggregation == "std":
                return round(float(df[column].std()), 2)
            elif aggregation == "ratio" and secondary:
                return round(df[column].sum() / df[secondary].count(), 2)
            elif aggregation == "percentage" and secondary:
                return round((df[column].sum() / df[secondary].count()) * 100, 1)
            else:
                return df[column].sum()
        except Exception as e:
            logger.error(f"Error calculating KPI for {column} with {aggregation}: {e}")
            return 0

    def _generate_generic_kpis(
        self,
        df: pl.DataFrame,
        max_kpis: int,
        exclude_columns: List[str] = []
    ) -> List[Dict[str, Any]]:
        """
        Fallback generic KPIs when dynamic LLM fails.
        """
        kpis = []

        # Numeric KPIs
        numeric_cols = [col for col in df.select(pl.col(pl.NUMERIC_DTYPES)).columns if col not in exclude_columns]
        for col in numeric_cols[:max_kpis // 2]:
            try:
                max_val = float(df[col].max())
                kpis.append({
                    "title": f"Max {col.replace('_', ' ').title()}",
                    "value": round(max_val, 2),
                    "column": col,
                    "aggregation": "max",
                    "format": "decimal",
                    "importance": "medium",
                    "context": ""
                })

                total_val = float(df[col].sum())
                kpis.append({
                    "title": f"Total {col.replace('_', ' ').title()}",
                    "value": round(total_val, 2),
                    "column": col,
                    "aggregation": "sum",
                    "format": "decimal",
                    "importance": "medium",
                    "context": ""
                })

                if len(kpis) >= max_kpis:
                    break
            except:
                continue

        # Categorical KPIs
        categorical_cols = [col for col in df.select(pl.col(pl.Utf8, pl.Categorical)).columns if col not in exclude_columns]
        for col in categorical_cols:
            if len(kpis) >= max_kpis:
                break
            try:
                unique_count = int(df[col].n_unique())
                kpis.append({
                    "title": f"Unique {col.replace('_', ' ').title()}",
                    "value": unique_count,
                    "column": col,
                    "aggregation": "count_unique",
                    "format": "integer",
                    "importance": "medium",
                    "context": ""
                })
            except:
                continue

        return kpis[:max_kpis]


# Singleton instance
intelligent_kpi_generator = IntelligentKPIGenerator()