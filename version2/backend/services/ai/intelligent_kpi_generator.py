# backend/services/ai/intelligent_kpi_generator.py

"""
Intelligent KPI Generator
=========================
Generates context-aware, domain-specific KPIs based on actual dataset columns.

NO MORE HARDCODED "Total Revenue" FOR CRICKET DATA!
"""

import logging
from typing import Dict, List, Any, Optional
import polars as pl

from services.llm_router import llm_router

logger = logging.getLogger(__name__)


class IntelligentKPIGenerator:
    """
    Generates intelligent, context-aware KPIs by analyzing:
    1. Column names and types
    2. Domain context
    3. Data relationships
    4. Statistical properties
    """

    def __init__(self):
        self.domain_kpi_templates = {
            "cricket": {
                "patterns": ["batsman", "runs", "wicket", "bowl", "strike", "average", "innings"],
                "kpis": [
                    {"title": "Top Scorer", "column_pattern": ["runs", "total_runs"], "aggregation": "max"},
                    {"title": "Total Runs Scored", "column_pattern": ["runs", "total_runs"], "aggregation": "sum"},
                    {"title": "Average Runs", "column_pattern": ["average", "avg"], "aggregation": "mean"},
                    {"title": "Best Strike Rate", "column_pattern": ["strike", "strikerate"], "aggregation": "max"},
                    {"title": "Total Wickets", "column_pattern": ["out", "wicket"], "aggregation": "sum"},
                    {"title": "Total Batsmen", "column_pattern": ["batsman", "player"], "aggregation": "count_unique"}
                ]
            },
            "football": {
                "patterns": ["goal", "assist", "match", "team", "player", "score"],
                "kpis": [
                    {"title": "Total Goals", "column_pattern": ["goal"], "aggregation": "sum"},
                    {"title": "Top Scorer", "column_pattern": ["goal", "score"], "aggregation": "max"},
                    {"title": "Total Assists", "column_pattern": ["assist"], "aggregation": "sum"},
                    {"title": "Average Goals per Match", "column_pattern": ["goal"], "aggregation": "mean"}
                ]
            },
            "sales": {
                "patterns": ["revenue", "sales", "order", "customer", "product", "amount", "price"],
                "kpis": [
                    {"title": "Total Revenue", "column_pattern": ["revenue", "sales", "amount"], "aggregation": "sum"},
                    {"title": "Total Orders", "column_pattern": ["order"], "aggregation": "count"},
                    {"title": "Total Customers", "column_pattern": ["customer"], "aggregation": "count_unique"},
                    {"title": "Average Order Value", "column_pattern": ["amount", "price"], "aggregation": "mean"}
                ]
            },
            "ecommerce": {
                "patterns": ["product", "customer", "order", "cart", "purchase", "transaction"],
                "kpis": [
                    {"title": "Total Sales", "column_pattern": ["sales", "amount", "total"], "aggregation": "sum"},
                    {"title": "Total Customers", "column_pattern": ["customer", "user"], "aggregation": "count_unique"},
                    {"title": "Total Orders", "column_pattern": ["order"], "aggregation": "count"},
                    {"title": "Average Purchase", "column_pattern": ["amount", "price"], "aggregation": "mean"}
                ]
            },
            "finance": {
                "patterns": ["balance", "transaction", "account", "payment", "debit", "credit"],
                "kpis": [
                    {"title": "Total Balance", "column_pattern": ["balance", "amount"], "aggregation": "sum"},
                    {"title": "Total Transactions", "column_pattern": ["transaction"], "aggregation": "count"},
                    {"title": "Average Transaction", "column_pattern": ["amount"], "aggregation": "mean"},
                    {"title": "Total Accounts", "column_pattern": ["account"], "aggregation": "count_unique"}
                ]
            }
        }

    def detect_domain(self, columns: List[str]) -> Optional[str]:
        """
        Detect the domain based on column names.
        """
        columns_lower = [col.lower() for col in columns]
        
        domain_scores = {}
        for domain, config in self.domain_kpi_templates.items():
            score = 0
            for pattern in config["patterns"]:
                if any(pattern in col for col in columns_lower):
                    score += 1
            domain_scores[domain] = score
        
        # Get domain with highest score
        if domain_scores:
            best_domain = max(domain_scores, key=domain_scores.get)
            if domain_scores[best_domain] > 0:
                logger.info(f"Detected domain: {best_domain} (score: {domain_scores[best_domain]})")
                return best_domain
        
        logger.info("No specific domain detected, using generic approach")
        return None

    def match_column_to_kpi(self, kpi_config: Dict, columns: List[str]) -> Optional[str]:
        """
        Find the best matching column for a KPI based on patterns.
        """
        columns_lower = [col.lower() for col in columns]
        
        for pattern in kpi_config["column_pattern"]:
            for i, col_lower in enumerate(columns_lower):
                if pattern in col_lower:
                    return columns[i]  # Return original column name
        
        return None

    async def generate_intelligent_kpis(
        self,
        df: pl.DataFrame,
        domain: Optional[str] = None,
        max_kpis: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Generate intelligent KPIs based on the dataframe and domain.
        
        Returns:
            List of KPI configurations:
            [
                {
                    "title": "Top Scorer",
                    "value": 5426,
                    "column": "total_runs",
                    "aggregation": "max",
                    "subtitle": "Highest total runs"
                }
            ]
        """
        try:
            columns = df.columns
            
            # Auto-detect domain if not provided
            if not domain:
                domain = self.detect_domain(columns)
            
            kpis = []
            
            if domain and domain in self.domain_kpi_templates:
                # Use domain-specific KPI templates
                kpi_templates = self.domain_kpi_templates[domain]["kpis"]
                
                for kpi_config in kpi_templates[:max_kpis]:
                    # Find matching column
                    matched_column = self.match_column_to_kpi(kpi_config, columns)
                    
                    if matched_column:
                        # Calculate KPI value
                        value = self._calculate_kpi_value(df, matched_column, kpi_config["aggregation"])
                        
                        kpis.append({
                            "title": kpi_config["title"],
                            "value": value,
                            "column": matched_column,
                            "aggregation": kpi_config["aggregation"],
                            "subtitle": f"{kpi_config['aggregation']} of {matched_column}"
                        })
                
                # Fill remaining slots with generic KPIs if needed
                if len(kpis) < max_kpis:
                    kpis.extend(self._generate_generic_kpis(df, max_kpis - len(kpis), exclude_columns=[k["column"] for k in kpis]))
            
            else:
                # Fallback to generic KPIs
                kpis = self._generate_generic_kpis(df, max_kpis)
            
            logger.info(f"Generated {len(kpis)} intelligent KPIs")
            return kpis
        
        except Exception as e:
            logger.error(f"Error generating intelligent KPIs: {e}", exc_info=True)
            return self._generate_fallback_kpis(df, max_kpis)

    def _calculate_kpi_value(self, df: pl.DataFrame, column: str, aggregation: str) -> Any:
        """
        Calculate the KPI value based on aggregation type.
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
        Generate generic KPIs based on column types when domain is unknown.
        """
        kpis = []
        
        # Get numeric columns
        numeric_cols = [col for col in df.select(pl.col(pl.NUMERIC_DTYPES)).columns if col not in exclude_columns]
        
        # Get categorical columns
        categorical_cols = [col for col in df.select(pl.col(pl.Utf8, pl.Categorical)).columns if col not in exclude_columns]
        
        # Generate KPIs for numeric columns
        for col in numeric_cols[:max_kpis]:
            try:
                max_val = float(df[col].max())
                kpis.append({
                    "title": f"Top {col.replace('_', ' ').title()}",
                    "value": round(max_val, 2),
                    "column": col,
                    "aggregation": "max",
                    "subtitle": f"Highest {col}"
                })
                
                if len(kpis) >= max_kpis:
                    break
                
                total_val = float(df[col].sum())
                kpis.append({
                    "title": f"Total {col.replace('_', ' ').title()}",
                    "value": round(total_val, 2),
                    "column": col,
                    "aggregation": "sum",
                    "subtitle": f"Sum of {col}"
                })
                
                if len(kpis) >= max_kpis:
                    break
            except:
                continue
        
        # Add count of unique values for categorical columns if space remains
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
                    "subtitle": f"Distinct {col} count"
                })
            except:
                continue
        
        return kpis[:max_kpis]

    def _generate_fallback_kpis(self, df: pl.DataFrame, max_kpis: int) -> List[Dict[str, Any]]:
        """
        Fallback KPIs when everything else fails.
        """
        return [
            {
                "title": "Total Rows",
                "value": len(df),
                "column": None,
                "aggregation": "count",
                "subtitle": "Total records in dataset"
            },
            {
                "title": "Total Columns",
                "value": len(df.columns),
                "column": None,
                "aggregation": "count",
                "subtitle": "Number of columns"
            }
        ][:max_kpis]


# Singleton instance
intelligent_kpi_generator = IntelligentKPIGenerator()
