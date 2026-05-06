"""
Compatibility wrapper for chart recommender.

Canonical module location:
    services.charts.chart_recommender

This file is kept to avoid breaking older imports while the codebase
transitions to chart-domain ownership.
"""

from services.charts.chart_recommender import ChartRecommender, chart_recommender

__all__ = ["ChartRecommender", "chart_recommender"]
