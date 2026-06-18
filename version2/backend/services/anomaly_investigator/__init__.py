"""
anomaly_investigator — Autonomous root cause investigation for detected anomalies.

Architecture:
    ├── AnomalyDetector (reuses advanced_stats.AnomalyDetector)
    ├── RootCauseAnalyzer → correlates anomalies across dimensions
    ├── ImpactAssessor → quantifies business impact
    ├── RecommendationEngine → suggests corrective actions
    └── Synthesizer → combines everything into a structured report

Triggered automatically when AnomalyFeed or chart pipeline detects an anomaly.
"""

from .investigator import AnomalyInvestigatorAgent

__all__ = ["AnomalyInvestigatorAgent"]
