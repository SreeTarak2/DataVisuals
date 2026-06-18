"""
AnomalyInvestigatorAgent — Autonomous root cause investigation for detected anomalies.

Architecture:
    RootCauseAnalyzer    → Correlates anomalies across dimensions via drill-down
    ImpactAssessor       → Quantifies business impact in relative terms
    RecommendationEngine → Suggests corrective actions based on anomaly type + severity
    Synthesizer          → Combines everything into a structured AnomalyReport

Design principles:
    - Statistical first, LLM second: root cause uses computation, LLM only for narrative
    - Stateless: instantiate once and reuse across multiple anomaly events
    - Graceful degradation: partial results returned even if sub-components fail
    - Reuses existing advanced_stats infrastructure (AnomalyDetector, CorrelationAnalyzer)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class AnomalyReport:
    """Structured output of a full anomaly investigation."""

    anomalies: list[dict] = field(default_factory=list)
    root_causes: list[dict] = field(default_factory=list)
    impact: dict = field(default_factory=dict)
    narrative: str = ""
    recommendations: list[dict] = field(default_factory=list)
    investigation_id: str = ""
    dataset_id: str = ""
    confidence: float = 0.5


# ── Prompt templates ─────────────────────────────────────────────────────────

ROOT_CAUSE_PROMPT = """\
<role>You are a root-cause analyst investigating data anomalies.</role>
<instructions>
Below is an anomaly detection result from a dataset analysis.

## Anomalies Detected
{anomalies_text}

## Dataset Context (Schema & Stats)
{schema_context}

## Sample Data Context
{sample_context}

## Task
Identify the most likely root causes for these anomalies. For each root cause:
1. What metric/dimension is affected?
2. Why might this anomaly have occurred? (be specific)
3. What additional data would confirm the root cause?

Return a JSON array of root causes, each with:
- "affected_metric": Column or KPI affected
- "root_cause": Specific explanation of what caused the anomaly
- "confidence": 0.0–1.0 estimate of confidence in this root cause
- "supporting_evidence": What in the data supports this conclusion
- "verification_query": What query would confirm this root cause
</instructions>"""

IMPACT_ASSESSMENT_PROMPT = """\
<role>You are a business impact analyst quantifying the effect of data anomalies.</role>
<instructions>
## Anomalies Detected
{anomalies_text}

## Root Causes Identified
{root_causes_text}

## Task
Assess the business impact of these anomalies. Return a JSON object with:
- "severity": one of "critical", "high", "medium", "low"
- "magnitude": relative impact magnitude (0.0–1.0)
- "affected_dimensions": Which data dimensions are affected
- "estimated_effect": Brief quantification of the effect
- "trend_acceleration": Whether this is accelerating (worsening) or decelerating
- "business_functions_impacted": Which teams/functions are affected

Be conservative — do not overstate impact.
</instructions>"""

RECOMMENDATION_PROMPT = """\
<role>You are a data reliability engineer recommending actions for anomaly resolution.</role>
<instructions>
## Anomalies to Address
{anomalies_text}

## Root Causes
{root_causes_text}

## Impact Assessment
{impact_text}

## Task
Generate 2-4 specific, actionable recommendations. For each:
- "action": Specific next step
- "rationale": Why this action
- "urgency": "immediate", "today", "this_week"
- "effort": "low", "medium", "high"
- "expected_outcome": What improvement is expected
- "owner": Suggested team or role to take action

Return ONLY a JSON array of recommendations.
</instructions>"""

NARRATIVE_PROMPT = """\
<role>You are a data storyteller explaining anomalies to business stakeholders.</role>
<instructions>
Summarize the following anomaly investigation into 2-3 paragraphs suitable for
a business stakeholder. Focus on:
1. What happened (the anomaly)
2. Why it happened (root cause)
3. What to do about it (recommendation)

Use clear, jargon-free language. Prioritize actionable insight over technical detail.

Anomalies: {anomalies_text}
Root Causes: {root_causes_text}
Impact: {impact_text}
Recommendations: {recommendations_text}
</instructions>"""


# ── AnomalyInvestigatorAgent ─────────────────────────────────────────────────


class AnomalyInvestigatorAgent:
    """
    Autonomous root cause investigation for detected anomalies.

    Usage:
        agent = AnomalyInvestigatorAgent()
        report = await agent.investigate(
            dataset_id="...",
            columns=[...],
            anomalies=[...],    # from AnomalyDetector
            df=polars_df,
            sample_rows=[...],
        )
    """

    def __init__(self):
        self._llm_router = None
        self._anomaly_detector = None
        self._correlation_analyzer = None

    @property
    def llm_router(self):
        if self._llm_router is None:
            from services.llm_router import llm_router
            self._llm_router = llm_router
        return self._llm_router

    @property
    def anomaly_detector(self):
        if self._anomaly_detector is None:
            from services.analysis.advanced_stats import anomaly_detector
            self._anomaly_detector = anomaly_detector
        return self._anomaly_detector

    @property
    def correlation_analyzer(self):
        if self._correlation_analyzer is None:
            from services.analysis.advanced_stats import correlation_analyzer
            self._correlation_analyzer = correlation_analyzer
        return self._correlation_analyzer

    async def investigate(
        self,
        dataset_id: str,
        columns: list[dict] | None = None,
        anomalies: list[dict] | None = None,
        df: Any = None,
        sample_rows: list[dict] | None = None,
        row_count: int = 0,
        investigation_id: str = "",
    ) -> AnomalyReport:
        """
        Run a full anomaly investigation: root cause → impact → recommendations.

        Args:
            dataset_id: The dataset ID
            columns: Column metadata list
            anomalies: Pre-detected anomalies (optional — will run detection if omitted)
            df: Polars DataFrame for deeper analysis
            sample_rows: Sample data rows
            row_count: Total row count
            investigation_id: Optional ID for tracing

        Returns:
            AnomalyReport with structured investigation results
        """
        # ── Step 1: Detect or use provided anomalies ────────────────────────
        if not anomalies and df is not None:
            anomalies = await self._detect_anomalies(df, columns or [])

        if not anomalies:
            logger.info(f"[AnomalyInvestigator] No anomalies to investigate for {dataset_id}")
            return AnomalyReport(
                investigation_id=investigation_id,
                dataset_id=dataset_id,
                narrative="No anomalies detected.",
            )

        # Build context strings
        schema_context, sample_context = self._build_context(columns, row_count, sample_rows)
        anomalies_text = self._format_anomalies(anomalies)

        # ── Step 2: Run parallel analysis ───────────────────────────────────
        root_causes_task = self._analyze_root_causes(
            anomalies_text, schema_context, sample_context
        )
        impact_task = self._assess_impact(anomalies_text)

        root_causes, impact = await asyncio.gather(root_causes_task, impact_task)

        # ── Step 3: Generate recommendations based on root causes + impact ──
        root_causes_text = self._format_list(root_causes, "root_cause")
        impact_text = str(impact)

        recommendations = await self._generate_recommendations(
            anomalies_text, root_causes_text, impact_text
        )

        # ── Step 4: Synthesize narrative ────────────────────────────────────
        recommendations_text = self._format_list(recommendations, "action")
        narrative = await self._synthesize_narrative(
            anomalies_text, root_causes_text, impact_text, recommendations_text
        )

        # Confidence based on anomaly severity (not quantity)
        # More root causes = more uncertainty, not less certainty
        max_outlier_pct = max(
            (a.get("outlier_percentage", 0) for a in anomalies),
            default=0,
        )
        confidence = min(1.0, max_outlier_pct / 15.0)  # 15% outliers = ~1.0

        # Small boost only if root causes have high individual confidence
        has_strong_evidence = any(
            rc.get("confidence", 0) >= 0.5 for rc in root_causes[:3]
        )
        if has_strong_evidence:
            confidence = min(1.0, confidence + 0.15)
        if impact.get("severity") in ("critical", "high", "medium"):
            confidence = min(1.0, confidence + 0.1)

        confidence = round(max(0.1, min(1.0, confidence)), 2)

        return AnomalyReport(
            anomalies=anomalies[:20],
            root_causes=root_causes[:5],
            impact=impact,
            narrative=narrative,
            recommendations=recommendations[:4],
            investigation_id=investigation_id,
            dataset_id=dataset_id,
            confidence=round(confidence, 2),
        )

    # ── Anomaly Detection ────────────────────────────────────────────────────

    async def _detect_anomalies(
        self, df: Any, columns: list[dict]
    ) -> list[dict]:
        """Run z-score detection on numeric columns using existing infrastructure."""
        detected = []

        for col_meta in columns:
            name = col_meta.get("name", "")
            col_type = col_meta.get("type", "")
            if col_type not in ("numeric", "float", "int", "integer"):
                continue

            try:
                col_data = df[name].to_numpy()
                col_data = col_data[~np.isnan(col_data)]

                if len(col_data) < 10:
                    continue

                result = self.anomaly_detector.detect_zscore(
                    data=col_data,
                    column_name=name,
                    threshold=3.0,
                )
                if result.outlier_count > 0:
                    detected.append({
                        "column": name,
                        "method": result.method,
                        "outlier_count": result.outlier_count,
                        "outlier_percentage": result.outlier_percentage,
                        "threshold": result.threshold,
                        "severity": self._classify_severity(result.outlier_percentage),
                        "direction": "mixed",
                    })
            except Exception as e:
                logger.debug(f"[AnomalyInvestigator] Skipping {name}: {e}")

        return detected

    @staticmethod
    def _classify_severity(outlier_pct: float) -> str:
        if outlier_pct > 10:
            return "critical"
        elif outlier_pct > 5:
            return "high"
        elif outlier_pct > 2:
            return "medium"
        return "low"

    # ── Root Cause Analysis ──────────────────────────────────────────────────

    async def _analyze_root_causes(
        self, anomalies_text: str, schema_context: str, sample_context: str
    ) -> list[dict]:
        prompt = ROOT_CAUSE_PROMPT.format(
            anomalies_text=anomalies_text,
            schema_context=schema_context,
            sample_context=sample_context,
        )
        try:
            result = await self.llm_router.call(
                prompt=prompt,
                model_role="kpi_suggestion",  # DeepSeek V4 Flash — diagnostic reasoning needs premium JSON + reasoning
                expect_json=True,
                temperature=0.2,
                max_tokens=1000,
            )
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return result.get("root_causes", result.get("results", []))
            return []
        except Exception as e:
            logger.warning(f"[AnomalyInvestigator] root_cause analysis failed: {e}")
            return []

    # ── Impact Assessment ────────────────────────────────────────────────────

    async def _assess_impact(self, anomalies_text: str) -> dict:
        prompt = IMPACT_ASSESSMENT_PROMPT.format(anomalies_text=anomalies_text)
        try:
            result = await self.llm_router.call(
                prompt=prompt,
                model_role="simple_query",  # Mistral Small 3.2 — impact classification + structured JSON
                expect_json=True,
                temperature=0.2,
                max_tokens=500,
            )
            if isinstance(result, dict):
                return result
            return {"severity": "unknown", "magnitude": 0.0}
        except Exception as e:
            logger.warning(f"[AnomalyInvestigator] impact assessment failed: {e}")
            return {"severity": "unknown", "magnitude": 0.0}

    # ── Recommendation Generation ────────────────────────────────────────────

    async def _generate_recommendations(
        self, anomalies_text: str, root_causes_text: str, impact_text: str
    ) -> list[dict]:
        prompt = RECOMMENDATION_PROMPT.format(
            anomalies_text=anomalies_text,
            root_causes_text=root_causes_text,
            impact_text=impact_text,
        )
        try:
            result = await self.llm_router.call(
                prompt=prompt,
                model_role="simple_query",  # Mistral Small 3.2 — action formatting from pre-reasoned inputs
                expect_json=True,
                temperature=0.3,
                max_tokens=800,
            )
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return result.get("recommendations", result.get("results", []))
            return []
        except Exception as e:
            logger.warning(f"[AnomalyInvestigator] recommendation gen failed: {e}")
            return []

    # ── Narrative Synthesis ──────────────────────────────────────────────────

    async def _synthesize_narrative(
        self,
        anomalies_text: str,
        root_causes_text: str,
        impact_text: str,
        recommendations_text: str,
    ) -> str:
        prompt = NARRATIVE_PROMPT.format(
            anomalies_text=anomalies_text,
            root_causes_text=root_causes_text,
            impact_text=impact_text,
            recommendations_text=recommendations_text,
        )
        try:
            result = await self.llm_router.call(
                prompt=prompt,
                model_role="simple_query",  # Mistral Small 3.2 — short business narrative, under 500 tokens
                expect_json=False,
                temperature=0.3,
                max_tokens=500,
            )
            if isinstance(result, dict):
                return result.get("text", "")
            return str(result) if result else ""
        except Exception as e:
            logger.warning(f"[AnomalyInvestigator] narrative synthesis failed: {e}")
            return ""

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_context(
        columns: list[dict] | None,
        row_count: int,
        sample_rows: list[dict] | None,
    ) -> tuple[str, str]:
        schema_lines = []
        if columns:
            for c in columns[:20]:
                name = c.get("name", "?")
                col_type = c.get("type", "?")
                nulls = c.get("null_percentage", 0)
                num_summary = c.get("numeric_summary", {})
                if num_summary:
                    schema_lines.append(
                        f"- {name} ({col_type}): {num_summary.get('min', '?')}–{num_summary.get('max', '?')}, "
                        f"mean={num_summary.get('mean', '?')}, nulls={nulls}%"
                    )
                else:
                    schema_lines.append(f"- {name} ({col_type}): nulls={nulls}%")
            if len(columns) > 20:
                schema_lines.append(f"... and {len(columns) - 20} more columns")
        schema_context = "Schema:\n" + "\n".join(schema_lines)
        if row_count:
            schema_context += f"\nTotal rows: {row_count:,}"

        sample_context = ""
        if sample_rows:
            sample_context = "Sample rows:\n"
            if sample_rows:
                headers = list(sample_rows[0].keys()) if sample_rows else []
                sample_context += " | ".join(str(h)[:20] for h in headers[:6]) + "\n"
                for row in sample_rows[:3]:
                    sample_context += " | ".join(str(v)[:15] for v in list(row.values())[:6]) + "\n"

        return schema_context, sample_context

    @staticmethod
    def _format_anomalies(anomalies: list[dict]) -> str:
        if not anomalies:
            return "No anomalies detected."
        lines = []
        for i, a in enumerate(anomalies[:10], 1):
            col = a.get("column", "?")
            count = a.get("outlier_count", 0)
            pct = a.get("outlier_percentage", 0)
            sev = a.get("severity", "unknown")
            direction = a.get("direction", "mixed")
            lines.append(
                f"{i}. {col}: {count} outliers ({pct}%), severity={sev}, direction={direction}"
            )
        if len(anomalies) > 10:
            lines.append(f"... and {len(anomalies) - 10} more anomalies")
        return "\n".join(lines)

    @staticmethod
    def _format_list(items: list[dict], key: str) -> str:
        if not items:
            return "None identified."
        lines = []
        for i, item in enumerate(items[:5], 1):
            val = item.get(key, str(item))
            desc = item.get("description", item.get("rationale", ""))
            priority = item.get("priority", item.get("confidence"))
            if priority:
                lines.append(f"{i}. {val} (confidence: {priority})")
            else:
                lines.append(f"{i}. {val}")
            if desc:
                lines[-1] += f" — {str(desc)[:100]}"
        return "\n".join(lines)


# ── Singleton ────────────────────────────────────────────────────────────────

anomaly_investigator_agent = AnomalyInvestigatorAgent()
