"""
Chart Recommendation Service
=============================
Intelligently recommends visualizations based on:
- Column types (numeric, categorical, temporal)
- Cardinality (unique value counts)
- Domain context (automotive, healthcare, sales, etc.)
- Data relationships and patterns

Author: DataSage AI Team
Version: 1.0
"""

import logging
from typing import Dict, List, Any
import polars as pl

logger = logging.getLogger(__name__)


class ChartRecommender:
    """
    Recommends optimal visualizations for dataset columns.
    """
    
    # Chart type definitions with applicability rules
    CHART_TYPES = {
        "bar": {
            "best_for": "comparing categories",
            "requires": ["1+ categorical", "1 numeric"],
            "max_categories": 15,
            "use_cases": ["sales by region", "product performance", "department metrics"]
        },
        "line": {
            "best_for": "trends over time",
            "requires": ["1 time", "1+ numeric"],
            "use_cases": ["revenue over time", "monthly sales", "performance trends"]
        },
        "pie": {
            "best_for": "part-to-whole relationships",
            "requires": ["1 categorical", "1 numeric"],
            "max_categories": 7,
            "use_cases": ["market share", "category distribution", "budget breakdown"]
        },
        "scatter": {
            "best_for": "correlation between variables",
            "requires": ["2+ numeric"],
            "use_cases": ["price vs mileage", "age vs salary", "correlation analysis"]
        },
        "heatmap": {
            "best_for": "correlation matrix or intensity",
            "requires": ["multiple numeric"],
            "use_cases": ["correlation matrix", "density map", "pattern visualization"]
        },
        "histogram": {
            "best_for": "distribution of values",
            "requires": ["1 numeric"],
            "use_cases": ["age distribution", "price distribution", "frequency analysis"]
        },
        "box": {
            "best_for": "distribution and outliers",
            "requires": ["1 numeric", "optional categorical"],
            "use_cases": ["outlier detection", "quartile analysis", "distribution comparison"]
        },
        "area": {
            "best_for": "cumulative trends",
            "requires": ["1 time", "1+ numeric"],
            "use_cases": ["stacked revenue", "cumulative sales", "growth trends"]
        }
    }
    
    def recommend_charts(
        self, 
        df: pl.DataFrame, 
        column_metadata: List[Dict],
        domain: str,
        cardinality: Dict[str, Any],
        time_columns: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Recommend optimal chart types for the dataset.
        
        Args:
            df: Polars DataFrame
            column_metadata: Column metadata
            domain: Dataset domain (automotive, healthcare, sales, etc.)
            cardinality: Cardinality analysis from profiler
            time_columns: List of time/date columns
        
        Returns:
            List of chart recommendations with config and relevance scores
        """
        logger.info(f"Generating chart recommendations for {domain} domain...")
        
        # Extract column types
        numeric_cols = [col["name"] for col in column_metadata 
                       if any(t in col["type"].lower() for t in ["int", "float"])]
        categorical_cols = [col["name"] for col in column_metadata 
                           if any(t in col["type"].lower() for t in ["str", "utf8", "categorical"])]
        
        # Filter categorical columns by cardinality (exclude high-cardinality)
        low_card_categorical = [
            col for col in categorical_cols 
            if col in cardinality and cardinality[col]["cardinality_level"] in ["low", "medium"]
        ]
        
        recommendations = []
        
        # 1. Time series charts (if time columns exist)
        if time_columns and numeric_cols:
            recommendations.extend(self._recommend_time_series_charts(
                time_columns, numeric_cols, domain
            ))
        
        # 2. Categorical comparison charts
        if low_card_categorical and numeric_cols:
            recommendations.extend(self._recommend_categorical_charts(
                low_card_categorical, numeric_cols, cardinality, domain
            ))
        
        # 3. Correlation charts
        if len(numeric_cols) >= 2:
            recommendations.extend(self._recommend_correlation_charts(
                numeric_cols, domain
            ))
        
        # 4. Distribution charts
        if numeric_cols:
            recommendations.extend(self._recommend_distribution_charts(
                numeric_cols, domain
            ))
        
        # 5. Domain-specific recommendations
        recommendations.extend(self._recommend_domain_specific_charts(
            domain, numeric_cols, low_card_categorical, time_columns
        ))
        
        # Sort by relevance score and deduplicate
        recommendations = self._deduplicate_recommendations(recommendations)
        recommendations.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        logger.info(f"Generated {len(recommendations)} chart recommendations")
        return recommendations[:10]  # Top 10 recommendations
    
    def _recommend_time_series_charts(
        self, 
        time_columns: List[str], 
        numeric_cols: List[str], 
        domain: str
    ) -> List[Dict]:
        """Recommend time series visualizations."""
        recommendations = []
        
        # Use the first time column
        time_col = time_columns[0]
        
        # Line chart for each numeric column
        for num_col in numeric_cols[:3]:  # Top 3 metrics
            recommendations.append({
                "chart_type": "line",
                "title": f"{num_col} Over Time",
                "config": {
                    "x_axis": time_col,
                    "y_axis": num_col,
                    "aggregation": "sum" if "count" not in num_col.lower() else "count"
                },
                "relevance_score": 0.95,
                "reasoning": f"Time series visualization of {num_col} trends",
                "use_case": self.CHART_TYPES["line"]["best_for"]
            })
        
        # Area chart for cumulative trends (if domain is sales/finance)
        if domain in ["sales", "finance", "ecommerce"]:
            if numeric_cols:
                recommendations.append({
                    "chart_type": "area",
                    "title": f"Cumulative {numeric_cols[0]} Over Time",
                    "config": {
                        "x_axis": time_col,
                        "y_axis": numeric_cols[0],
                        "aggregation": "cumsum"
                    },
                    "relevance_score": 0.85,
                    "reasoning": f"Cumulative trend analysis for {domain}",
                    "use_case": self.CHART_TYPES["area"]["best_for"]
                })
        
        return recommendations
    
    def _recommend_categorical_charts(
        self, 
        categorical_cols: List[str], 
        numeric_cols: List[str],
        cardinality: Dict,
        domain: str
    ) -> List[Dict]:
        """Recommend categorical comparison charts."""
        recommendations = []
        
        # Bar charts for low-cardinality categories
        for cat_col in categorical_cols[:3]:
            if cat_col not in cardinality:
                continue
            
            unique_count = cardinality[cat_col]["unique_count"]
            
            if unique_count <= 15:  # Good for bar chart
                for num_col in numeric_cols[:2]:
                    recommendations.append({
                        "chart_type": "bar",
                        "title": f"{num_col} by {cat_col}",
                        "config": {
                            "x_axis": cat_col,
                            "y_axis": num_col,
                            "aggregation": "sum"
                        },
                        "relevance_score": 0.90,
                        "reasoning": f"Compare {num_col} across {cat_col} categories",
                        "use_case": self.CHART_TYPES["bar"]["best_for"]
                    })
        
        # Pie chart for low-cardinality (2-7 categories)
        for cat_col in categorical_cols[:2]:
            if cat_col not in cardinality:
                continue
            
            unique_count = cardinality[cat_col]["unique_count"]
            
            if 2 <= unique_count <= 7:  # Good for pie chart
                if numeric_cols:
                    recommendations.append({
                        "chart_type": "pie",
                        "title": f"{numeric_cols[0]} Distribution by {cat_col}",
                        "config": {
                            "category": cat_col,
                            "value": numeric_cols[0],
                            "aggregation": "sum"
                        },
                        "relevance_score": 0.75,
                        "reasoning": f"Part-to-whole distribution of {cat_col}",
                        "use_case": self.CHART_TYPES["pie"]["best_for"]
                    })
        
        return recommendations
    
    def _recommend_correlation_charts(
        self, 
        numeric_cols: List[str], 
        domain: str
    ) -> List[Dict]:
        """Recommend correlation visualizations."""
        recommendations = []
        
        # Scatter plots for pairs of numeric columns
        if len(numeric_cols) >= 2:
            # Create scatter for most interesting pairs
            pairs = [
                (numeric_cols[0], numeric_cols[1]),
                (numeric_cols[0], numeric_cols[2]) if len(numeric_cols) > 2 else None
            ]
            
            for pair in pairs:
                if pair:
                    recommendations.append({
                        "chart_type": "scatter",
                        "title": f"{pair[1]} vs {pair[0]}",
                        "config": {
                            "x_axis": pair[0],
                            "y_axis": pair[1]
                        },
                        "relevance_score": 0.80,
                        "reasoning": f"Correlation analysis between {pair[0]} and {pair[1]}",
                        "use_case": self.CHART_TYPES["scatter"]["best_for"]
                    })
        
        # Heatmap for correlation matrix (if 3+ numeric columns)
        if len(numeric_cols) >= 3:
            recommendations.append({
                "chart_type": "heatmap",
                "title": "Correlation Matrix",
                "config": {
                    "columns": numeric_cols[:8],  # Max 8 columns for readability
                    "aggregation": "correlation"
                },
                "relevance_score": 0.85,
                "reasoning": "Comprehensive correlation analysis of numeric variables",
                "use_case": self.CHART_TYPES["heatmap"]["best_for"]
            })
        
        return recommendations
    
    def _recommend_distribution_charts(
        self, 
        numeric_cols: List[str], 
        domain: str
    ) -> List[Dict]:
        """Recommend distribution visualizations."""
        recommendations = []
        
        # Histogram for key metrics
        for num_col in numeric_cols[:2]:
            recommendations.append({
                "chart_type": "histogram",
                "title": f"{num_col} Distribution",
                "config": {
                    "column": num_col,
                    "bins": 20
                },
                "relevance_score": 0.70,
                "reasoning": f"Frequency distribution of {num_col}",
                "use_case": self.CHART_TYPES["histogram"]["best_for"]
            })
        
        # Box plot for outlier detection
        if numeric_cols:
            recommendations.append({
                "chart_type": "box",
                "title": f"{numeric_cols[0]} Outlier Analysis",
                "config": {
                    "column": numeric_cols[0]
                },
                "relevance_score": 0.65,
                "reasoning": f"Outlier detection and quartile analysis for {numeric_cols[0]}",
                "use_case": self.CHART_TYPES["box"]["best_for"]
            })
        
        return recommendations
    
    def _recommend_domain_specific_charts(
        self, 
        domain: str, 
        numeric_cols: List[str],
        categorical_cols: List[str],
        time_columns: List[str]
    ) -> List[Dict]:
        """Recommend charts specific to the domain."""
        recommendations = []
        
        if domain == "automotive":
            # Price vs Mileage scatter
            if "price" in [c.lower() for c in numeric_cols] and "mileage" in [c.lower() for c in numeric_cols]:
                price_col = next(c for c in numeric_cols if "price" in c.lower())
                mileage_col = next(c for c in numeric_cols if "mileage" in c.lower())
                recommendations.append({
                    "chart_type": "scatter",
                    "title": "Price vs Mileage Analysis",
                    "config": {"x_axis": mileage_col, "y_axis": price_col},
                    "relevance_score": 0.95,
                    "reasoning": "Key automotive insight: price depreciation by mileage",
                    "use_case": "Automotive pricing analysis"
                })
        
        elif domain == "sales":
            # Sales funnel (if funnel stages exist)
            funnel_keywords = ["lead", "qualified", "proposal", "closed", "won"]
            funnel_cols = [c for c in categorical_cols if any(kw in c.lower() for kw in funnel_keywords)]
            if funnel_cols and numeric_cols:
                recommendations.append({
                    "chart_type": "bar",
                    "title": "Sales Funnel Analysis",
                    "config": {"x_axis": funnel_cols[0], "y_axis": numeric_cols[0]},
                    "relevance_score": 0.90,
                    "reasoning": "Sales funnel conversion analysis",
                    "use_case": "Sales performance tracking"
                })
        
        elif domain == "healthcare":
            # Age distribution
            age_cols = [c for c in numeric_cols if "age" in c.lower()]
            if age_cols:
                recommendations.append({
                    "chart_type": "histogram",
                    "title": "Patient Age Distribution",
                    "config": {"column": age_cols[0], "bins": 15},
                    "relevance_score": 0.88,
                    "reasoning": "Healthcare demographic analysis",
                    "use_case": "Patient population insights"
                })
        
        return recommendations
    
    def _deduplicate_recommendations(self, recommendations: List[Dict]) -> List[Dict]:
        """Remove duplicate recommendations based on chart_type + config."""
        seen = set()
        unique_recs = []
        
        for rec in recommendations:
            # Create signature from chart type and main config keys
            signature = (
                rec["chart_type"],
                tuple(sorted(rec["config"].items()))
            )
            
            if signature not in seen:
                seen.add(signature)
                unique_recs.append(rec)
        
        return unique_recs


# Singleton instance
chart_recommender = ChartRecommender()
