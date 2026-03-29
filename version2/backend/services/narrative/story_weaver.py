"""
Narrative Story Weaver Service
==============================
Transforms analytical findings into coherent, engaging narrative stories.

This service implements a 3-stage pipeline:
1. Stage 1: DeepSeek V3.2 - Raw computation & pattern extraction
2. Stage 2: DeepSeek V3.2 - Insight prioritization & curation
3. Stage 3: Qwen 2.5 72B - Plain English narration (enterprise-grade)

The dual-model approach ensures:
- DeepSeek handles complex analysis (computation, statistics)
- Qwen handles plain English output (no jargon, business-friendly)

Author: DataSage Team
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from uuid import uuid4

from services.llm_router import llm_router
from core.narrative_prompts import (
    get_story_weaver_prompt,
    get_story_theme_detection_prompt,
    FALLBACK_STORY_TEMPLATES,
    get_stage1_computation_prompt,
    get_stage2_prioritization_prompt,
    get_stage3_narration_prompt,
    validate_narration_quality,
)

logger = logging.getLogger(__name__)


class StoryWeaver:
    """
    Transforms analytical findings into narrative stories.

    The story weaver takes raw analytical outputs (correlations, anomalies,
    trends, etc.) and transforms them into a coherent, engaging narrative
    that reads like an article rather than a report.
    """

    def __init__(self, llm_router_instance=None):
        self.llm = llm_router_instance or llm_router

    async def weave_story(
        self,
        dataset_id: str,
        dataset_name: str,
        domain: str,
        correlations: Optional[List[Dict[str, Any]]] = None,
        anomalies: Optional[List[Dict[str, Any]]] = None,
        trends: Optional[List[Dict[str, Any]]] = None,
        segments: Optional[List[Dict[str, Any]]] = None,
        key_findings: Optional[List[Dict[str, Any]]] = None,
        distributions: Optional[List[Dict[str, Any]]] = None,
        driver_analysis: Optional[List[Dict[str, Any]]] = None,
        data_quality: Optional[Dict[str, Any]] = None,
        recommendations: Optional[List[Dict[str, Any]]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Main entry point - generates a complete narrative story.

        Args:
            dataset_id: Unique identifier for the dataset
            dataset_name: Human-readable name of the dataset
            domain: Business domain (sales, marketing, etc.)
            correlations: List of correlation findings
            anomalies: List of anomaly/outlier findings
            trends: List of trend findings
            segments: List of segment findings
            key_findings: List of key findings from QUIS
            distributions: List of distribution findings
            driver_analysis: List of driver analysis findings
            data_quality: Data quality metrics
            recommendations: List of recommendations
            use_cache: Whether to use cached stories

        Returns:
            Dict containing the complete story structure
        """
        correlations = correlations or []
        anomalies = anomalies or []
        trends = trends or []
        segments = segments or []
        key_findings = key_findings or []
        distributions = distributions or []
        driver_analysis = driver_analysis or []
        recommendations = recommendations or []
        data_quality = data_quality or {}

        story_id = str(uuid4())

        logger.info(f"Starting story weaving for dataset: {dataset_name}")

        try:
            # Step 1: Analyze data characteristics to determine theme
            theme_info = await self._detect_story_theme(
                correlations, anomalies, trends, data_quality
            )
            logger.info(f"Detected story theme: {theme_info.get('theme')}")

            # Step 2: Check for quality issues that should lead the story
            quality_story = self._check_quality_priority(data_quality)
            if quality_story:
                quality_score = (
                    data_quality.get("health_score", 100) if data_quality else 100
                )
                logger.warning(
                    f"Using quality fallback for story (dataset={dataset_name}): "
                    f"quality_score={quality_score}"
                )
                return self._build_response(
                    story_id=story_id,
                    story_data=quality_story,
                    dataset_name=dataset_name,
                    theme_info=theme_info,
                    generation_method="quality_fallback",
                )

            # Step 3: Check if we have enough findings
            total_findings = (
                len(correlations) + len(anomalies) + len(trends) + len(key_findings)
            )
            if total_findings == 0:
                logger.warning(
                    f"No findings for story (dataset={dataset_name}): "
                    f"correlations={len(correlations)}, anomalies={len(anomalies)}, "
                    f"trends={len(trends)}, key_findings={len(key_findings)}. "
                    f"Using 'no_findings' fallback template."
                )
                return self._build_response(
                    story_id=story_id,
                    story_data=FALLBACK_STORY_TEMPLATES["no_findings"],
                    dataset_name=dataset_name,
                    theme_info={"theme": "exploration", "tone": "neutral"},
                    generation_method="empty_fallback",
                )

            # Step 4: Build fact sheet for LLM
            fact_sheet = self._build_story_fact_sheet(
                correlations,
                anomalies,
                trends,
                segments,
                key_findings,
                distributions,
                driver_analysis,
                data_quality,
                recommendations,
            )

            # Step 5: Generate story with LLM
            story_data = await self._generate_story_with_llm(
                fact_sheet=fact_sheet,
                dataset_name=dataset_name,
                domain=domain,
                theme=theme_info.get("theme"),
                story_angle=theme_info.get("story_angle"),
            )

            if story_data:
                return self._build_response(
                    story_id=story_id,
                    story_data=story_data,
                    dataset_name=dataset_name,
                    theme_info=theme_info,
                    generation_method="llm_generated",
                )

            # Fallback if LLM fails
            logger.warning("LLM story generation failed, using template fallback")
            return self._generate_template_fallback(
                correlations,
                anomalies,
                trends,
                key_findings,
                data_quality,
                recommendations,
                story_id,
                dataset_name,
                theme_info,
            )

        except Exception as e:
            logger.error(f"Story weaving failed: {e}", exc_info=True)
            return self._generate_error_story(story_id, dataset_name, str(e))

    async def _detect_story_theme(
        self,
        correlations: List[Dict],
        anomalies: List[Dict],
        trends: List[Dict],
        data_quality: Dict,
    ) -> Dict[str, Any]:
        """
        Detect the most appropriate story theme based on data characteristics.
        """
        # Quick heuristic-based detection (avoid LLM call for simple cases)
        strong_correlations = len(
            [c for c in correlations if c.get("abs_value", 0) > 0.6]
        )
        high_anomalies = len([a for a in anomalies if a.get("severity") == "high"])
        sig_trends = len([t for t in trends if t.get("is_significant")])
        quality_score = data_quality.get("health_score", 100) if data_quality else 100

        # Determine theme based on characteristics
        if quality_score < 50:
            return {
                "theme": "warning",
                "tone": "concerned",
                "story_angle": "Data quality issues need attention before insights can be trusted",
            }

        if high_anomalies > 2:
            return {
                "theme": "risk",
                "tone": "concerned",
                "story_angle": "Multiple anomalies detected that require investigation",
            }

        if sig_trends > 2:
            increasing_trends = len(
                [t for t in trends if t.get("direction") == "increasing"]
            )
            if increasing_trends > sig_trends / 2:
                return {
                    "theme": "growth",
                    "tone": "optimistic",
                    "story_angle": "Clear growth patterns emerging that present opportunities",
                }
            else:
                return {
                    "theme": "decline",
                    "tone": "concerned",
                    "story_angle": "Declining trends that need immediate attention",
                }

        if strong_correlations > 2:
            return {
                "theme": "opportunity",
                "tone": "neutral",
                "story_angle": "Strong relationships discovered that explain the patterns",
            }

        if len(correlations) > 0 or len(trends) > 0:
            return {
                "theme": "exploration",
                "tone": "neutral",
                "story_angle": "Patterns and relationships worth exploring",
            }

        return {
            "theme": "exploration",
            "tone": "neutral",
            "story_angle": "An initial look at what your data reveals",
        }

    def _check_quality_priority(self, data_quality: Dict) -> Optional[Dict]:
        """
        Check if data quality is poor enough to lead the story.
        """
        if not data_quality:
            return None

        quality_score = data_quality.get("health_score", 100)

        if quality_score < 50:
            template = FALLBACK_STORY_TEMPLATES.get("quality_issues", {})
            # Customize with actual quality metrics
            if "opening" in template:
                template = template.copy()
                template["opening"] = template["opening"].copy()
                template["opening"]["takeaway"] = template["opening"][
                    "takeaway"
                ].format(
                    score=quality_score,
                    missing=data_quality.get("completeness", 0),
                    dup=data_quality.get("uniqueness", 0),
                )
            return template

        return None

    def _build_story_fact_sheet(
        self,
        correlations: List[Dict],
        anomalies: List[Dict],
        trends: List[Dict],
        segments: List[Dict],
        key_findings: List[Dict],
        distributions: List[Dict],
        driver_analysis: List[Dict],
        data_quality: Dict,
        recommendations: List[Dict],
    ) -> str:
        """
        Build a structured fact sheet from analytical findings.
        This is fed to the LLM for story generation.
        """
        lines = []

        # Data Quality Overview
        if data_quality:
            lines.append("=== DATA QUALITY ===")
            lines.append(f"Health Score: {data_quality.get('health_score', 'N/A')}%")
            lines.append(f"Completeness: {data_quality.get('completeness', 'N/A')}%")
            lines.append(f"Uniqueness: {data_quality.get('uniqueness', 'N/A')}%")
            lines.append(f"Total Rows: {data_quality.get('total_rows', 'N/A')}")
            lines.append(f"Total Columns: {data_quality.get('total_columns', 'N/A')}")
            lines.append("")

        # Key Findings (QUIS)
        if key_findings:
            lines.append(f"=== KEY FINDINGS ({len(key_findings)} found) ===")
            for i, finding in enumerate(key_findings[:10]):
                lines.append(f"\nFinding {i + 1}:")
                lines.append(f"  Title: {finding.get('title', 'N/A')}")
                lines.append(
                    f"  Description: {finding.get('plain_english', finding.get('description', 'N/A'))}"
                )
                if finding.get("severity"):
                    lines.append(f"  Severity: {finding.get('severity')}")
                if finding.get("impact"):
                    lines.append(f"  Impact: {finding.get('impact')}")
            lines.append("")

        # Trends
        if trends:
            lines.append(f"=== TRENDS ({len(trends)} detected) ===")
            for trend in trends[:8]:
                direction = trend.get("direction", "unknown")
                column = trend.get("column", "unknown")
                strength = trend.get("strength", "N/A")
                significance = (
                    "significant" if trend.get("is_significant") else "not significant"
                )
                lines.append(
                    f"- **{column}** is **{direction}** (tau={strength}, {significance})"
                )
            lines.append("")

        # Correlations
        if correlations:
            lines.append(f"=== CORRELATIONS ({len(correlations)} found) ===")
            for corr in correlations[:10]:
                col1 = corr.get("column1", "unknown")
                col2 = corr.get("column2", "unknown")
                value = corr.get("value", corr.get("correlation", 0))
                strength = (
                    "strong"
                    if abs(value) > 0.6
                    else "moderate"
                    if abs(value) > 0.4
                    else "weak"
                )
                direction = "positive" if value > 0 else "negative"
                lines.append(
                    f"- **{col1}** and **{col2}**: {strength} {direction} relationship (r={value:.3f})"
                )
            lines.append("")

        # Anomalies
        if anomalies:
            lines.append(f"=== ANOMALIES ({len(anomalies)} detected) ===")
            for anomaly in anomalies[:8]:
                column = anomaly.get("column", "unknown")
                count = anomaly.get("count", anomaly.get("outlier_count", 0))
                pct = anomaly.get("percentage", 0)
                severity = anomaly.get("severity", "medium")
                lines.append(
                    f"- **{column}**: {count} unusual values ({pct:.1f}%, severity={severity})"
                )
            lines.append("")

        # Segments
        if segments:
            lines.append(f"=== SEGMENTS ({len(segments)} found) ===")
            for segment in segments[:5]:
                name = segment.get("segment_name", segment.get("name", "unknown"))
                deviation = segment.get("deviation", 0)
                lines.append(f"- **{name}**: {deviation:.1f}% deviation from mean")
            lines.append("")

        # Distributions
        if distributions:
            lines.append(f"=== DISTRIBUTIONS ({len(distributions)} found) ===")
            for dist in distributions[:5]:
                column = dist.get("column", "unknown")
                skewness = dist.get("skewness")
                kurtosis = dist.get("kurtosis", 0)
                if skewness is not None and abs(skewness) > 1:
                    shape = (
                        "highly skewed" if abs(skewness) > 2 else "moderately skewed"
                    )
                    direction = "right" if skewness > 0 else "left"
                    lines.append(
                        f"- **{column}**: {shape} ({direction}-tailed, skewness={skewness:.2f})"
                    )
                else:
                    lines.append(f"- **{column}**: approximately normal distribution")
            lines.append("")

        # Recommendations
        if recommendations:
            lines.append(f"=== RECOMMENDATIONS ({len(recommendations)} found) ===")
            for i, rec in enumerate(recommendations[:5]):
                lines.append(f"\n{i + 1}. {rec.get('title', rec.get('text', 'N/A'))}")
                if rec.get("description"):
                    lines.append(f"   {rec.get('description')}")
                if rec.get("urgency_score"):
                    lines.append(f"   Urgency: {rec.get('urgency_score')}/100")
            lines.append("")

        return "\n".join(lines)

    async def _generate_story_with_llm(
        self,
        fact_sheet: str,
        dataset_name: str,
        domain: str,
        theme: Optional[str] = None,
        story_angle: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate story using 3-stage dual-model pipeline.

        Stage 1: DeepSeek V3.2 - Raw computation & analysis (deterministic)
        Stage 2: DeepSeek V3.2 - Prioritization & curation (deterministic)
        Stage 3: Qwen 2.5 72B - Plain English narration (creative)

        Returns None if generation fails at any stage.
        """
        try:
            # ── STAGE 1: Raw Computation ──────────────────────────────
            # DeepSeek V3.2 handles the heavy math
            logger.info("Stage 1: Running computation analysis with DeepSeek V3.2")
            stage1_prompt = get_stage1_computation_prompt(
                raw_data=fact_sheet,
                domain=domain,
                dataset_name=dataset_name,
            )

            stage1_response = await self.llm.call(
                prompt=stage1_prompt,
                model_role="complex_analysis",  # Uses DeepSeek V3.2
                expect_json=True,
                temperature=0.1,  # Deterministic for computation
                max_tokens=3000,
            )

            if not stage1_response:
                logger.warning(
                    "Stage 1 computation failed, falling back to single-stage generation"
                )
                return await self._generate_single_stage(
                    fact_sheet=fact_sheet,
                    dataset_name=dataset_name,
                    domain=domain,
                    story_angle=story_angle,
                )

            # Parse stage 1 output
            stage1_data = (
                stage1_response
                if isinstance(stage1_response, dict)
                else self._extract_json_from_response(str(stage1_response))
            )
            if not stage1_data:
                logger.warning(
                    "Stage 1 JSON parse failed, falling back to single-stage"
                )
                return await self._generate_single_stage(
                    fact_sheet=fact_sheet,
                    dataset_name=dataset_name,
                    domain=domain,
                    story_angle=story_angle,
                )

            # ── STAGE 2: Prioritization ─────────────────────────────
            # DeepSeek V3.2 decides what matters most
            logger.info("Stage 2: Running insight prioritization with DeepSeek V3.2")
            stage2_prompt = get_stage2_prioritization_prompt(
                stage1_output=str(stage1_data),
                domain=domain,
            )

            stage2_response = await self.llm.call(
                prompt=stage2_prompt,
                model_role="complex_analysis",  # Uses DeepSeek V3.2
                expect_json=True,
                temperature=0.1,  # Deterministic for prioritization
                max_tokens=2000,
            )

            if not stage2_response:
                logger.warning(
                    "Stage 2 prioritization failed, using stage 1 data directly"
                )
                stage2_data = stage1_data
            else:
                stage2_data = (
                    stage2_response
                    if isinstance(stage2_response, dict)
                    else self._extract_json_from_response(str(stage2_response))
                )
                if not stage2_data:
                    stage2_data = stage1_data

            # ── STAGE 3: Plain English Narration ────────────────────
            # Qwen 2.5 72B writes the final narrative
            logger.info("Stage 3: Generating plain English narration with Qwen 2.5 72B")
            stage3_prompt = get_stage3_narration_prompt(
                stage2_output=str(stage2_data),
                dataset_name=dataset_name,
                domain=domain,
            )

            stage3_response = await self.llm.call(
                prompt=stage3_prompt,
                model_role="narrative_story",  # Uses Qwen 2.5 72B
                expect_json=True,
                temperature=0.3,  # Creative but professional
                max_tokens=3000,
            )

            if not stage3_response:
                logger.warning("Stage 3 narration failed, falling back to single-stage")
                return await self._generate_single_stage(
                    fact_sheet=fact_sheet,
                    dataset_name=dataset_name,
                    domain=domain,
                    story_angle=story_angle,
                )

            # Parse stage 3 output
            story_data = (
                stage3_response
                if isinstance(stage3_response, dict)
                else self._extract_json_from_response(str(stage3_response))
            )

            if not story_data:
                logger.warning(
                    "Stage 3 JSON parse failed, falling back to single-stage"
                )
                return await self._generate_single_stage(
                    fact_sheet=fact_sheet,
                    dataset_name=dataset_name,
                    domain=domain,
                    story_angle=story_angle,
                )

            # Validate quality
            validation = validate_narration_quality(story_data, domain)
            if not validation["passed"]:
                logger.warning(
                    f"Narration quality check failed: {validation['issues']}"
                )
                # If jargon was found, attempt cleanup
                if validation.get("jargon_found"):
                    logger.info(
                        f"Attempting jargon cleanup for: {validation['jargon_found']}"
                    )
                    story_data = self._cleanup_jargon(
                        story_data, validation["jargon_found"], domain
                    )
                    # Revalidate after cleanup
                    validation = validate_narration_quality(story_data, domain)
                    if validation["passed"]:
                        logger.info(
                            "✓ Jargon cleanup successful — quality check passed"
                        )

            # Extract and transform report from new format to frontend-compatible format
            if "report" in story_data:
                transformed = self._transform_to_frontend_format(story_data["report"])
                return transformed
            elif "story" in story_data:
                # "story" key has the same structure as "report" — transform it
                return self._transform_to_frontend_format(story_data["story"])
            else:
                # Wrap raw output in expected format
                return story_data

        except Exception as e:
            logger.error(f"3-stage pipeline error: {e}", exc_info=True)
            # Fallback to single-stage generation
            return await self._generate_single_stage(
                fact_sheet=fact_sheet,
                dataset_name=dataset_name,
                domain=domain,
                story_angle=story_angle,
            )

    async def _generate_single_stage(
        self,
        fact_sheet: str,
        dataset_name: str,
        domain: str,
        story_angle: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fallback single-stage story generation (legacy behavior).
        Uses narrative_story role which now routes to Qwen 2.5 72B.
        """
        try:
            prompt = get_story_weaver_prompt(
                fact_sheet=fact_sheet,
                dataset_name=dataset_name,
                domain=domain,
                story_theme=story_angle,
            )

            response = await self.llm.call(
                prompt=prompt,
                model_role="narrative_story",  # Now uses Qwen 2.5 72B
                expect_json=False,
                temperature=0.7,
                max_tokens=4000,
            )

            if not response:
                return None

            # Parse JSON response
            story_data = self._extract_json_from_response(response)

            if story_data and "story" in story_data:
                return story_data["story"]
            elif story_data and "report" in story_data:
                return story_data["report"]

            return None

        except Exception as e:
            logger.error(f"Single-stage story generation error: {e}")
            return None

    def _extract_json_from_response(self, response: str) -> Optional[Dict]:
        """
        Extract and parse JSON from LLM response.
        Handles various formats and partial responses.
        """
        if not response:
            return None

        # Try direct JSON parse first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in markdown code blocks
        try:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
            if match:
                return json.loads(match.group(1))
        except:
            pass

        # Try to find raw JSON object
        try:
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                return json.loads(match.group(0))
        except:
            pass

        return None

    def _cleanup_jargon(
        self, story_data: Dict[str, Any], jargon_found: List[str], domain: str
    ) -> Dict[str, Any]:
        """
        Recursively clean jargon from the story data by string replacement.
        Maps technical terms to plain English equivalents.
        """
        jargon_replacements = {
            "correlation": "connection",
            "correlated": "connected",
            "correlates": "connects",
            "p-value": "real pattern",
            "p value": "real pattern",
            "r-value": "strength score",
            "r value": "strength score",
            "r-squared": "fit score",
            "r squared": "fit score",
            "r²": "fit score",
            "regression": "trend",
            "regressed": "trended",
            "standard deviation": "variability",
            "std dev": "variability",
            "std.": "variability",
            "variance": "spread",
            "coefficient": "strength",
            "coefficients": "strengths",
            "percentile": "rank out of 100",
            "quartile": "quarter",
            "iqr": "middle spread",
            "interquartile": "middle spread",
            "null hypothesis": "baseline assumption",
            "alternative hypothesis": "alternative pattern",
            "significance": "importance",
            "significant": "important",
            "statistically significant": "real pattern",
            "statistical significance": "real pattern",
            "confidence interval": "likely range",
            "ci": "range",
            "t-test": "comparison",
            "t test": "comparison",
            "z-score": "distance score",
            "z score": "distance score",
            "normal distribution": "typical spread",
            "gaussian": "typical spread",
            "bell curve": "typical spread",
            "skewness": "lopsidedness",
            "skewed": "tilted",
            "kurtosis": "tail behavior",
            "median": "middle value",
            "mean": "average",
            "mode": "most common value",
            "modality": "frequency pattern",
            "outlier": "unusual value",
            "outliers": "unusual values",
            "heteroscedasticity": "inconsistent spread",
            "multicollinearity": "overlapping factors",
            "autoregression": "self-pattern",
            "stationarity": "consistency over time",
            "covariance": "joint variation",
            "covariate": "related factor",
            "eigenvalue": "importance score",
        }

        def clean_text(text: str) -> str:
            if not isinstance(text, str):
                return text
            result = text
            for jargon, replacement in jargon_replacements.items():
                # Case-insensitive replacement
                result = re.sub(
                    rf"\b{re.escape(jargon)}\b",
                    replacement,
                    result,
                    flags=re.IGNORECASE,
                )
            return result

        def clean_dict(obj: Dict) -> Dict:
            cleaned = {}
            for key, value in obj.items():
                if isinstance(value, str):
                    cleaned[key] = clean_text(value)
                elif isinstance(value, dict):
                    cleaned[key] = clean_dict(value)
                elif isinstance(value, list):
                    cleaned[key] = [
                        clean_dict(item)
                        if isinstance(item, dict)
                        else clean_text(item)
                        if isinstance(item, str)
                        else item
                        for item in value
                    ]
                else:
                    cleaned[key] = value
            return cleaned

        return clean_dict(story_data)

    def _generate_template_fallback(
        self,
        correlations: List[Dict],
        anomalies: List[Dict],
        trends: List[Dict],
        key_findings: List[Dict],
        data_quality: Dict,
        recommendations: List[Dict],
        story_id: str,
        dataset_name: str,
        theme_info: Dict,
    ) -> Dict[str, Any]:
        """
        Generate a story from templates when LLM is unavailable.
        Uses heuristics to select and order findings.
        """
        findings = []

        # Add significant trends
        for trend in trends[:3]:
            if trend.get("is_significant"):
                findings.append(
                    {
                        "id": f"finding_{len(findings) + 1}",
                        "type": "trend",
                        "title": f"{trend.get('column', 'Metric')} is {trend.get('direction', 'changing')}",
                        "narrative": self._generate_trend_narrative(trend),
                        "evidence": {
                            "key_metric": f"τ = {trend.get('strength', 0):.3f}",
                            "confidence": "high"
                            if trend.get("p_value", 1) < 0.05
                            else "medium",
                        },
                        "connects_to": None,
                        "importance": 7,
                    }
                )

        # Add strong correlations
        for corr in correlations[:3]:
            if abs(corr.get("value", corr.get("correlation", 0))) > 0.5:
                findings.append(
                    {
                        "id": f"finding_{len(findings) + 1}",
                        "type": "connection",
                        "title": f"Relationship between {corr.get('column1')} and {corr.get('column2')}",
                        "narrative": self._generate_correlation_narrative(corr),
                        "evidence": {
                            "key_metric": f"r = {corr.get('value', corr.get('correlation', 0)):.3f}",
                            "confidence": "high"
                            if abs(corr.get("value", 0)) > 0.6
                            else "medium",
                        },
                        "connects_to": None,
                        "importance": 6,
                    }
                )

        # Add anomalies as complications
        complications = []
        for anomaly in anomalies[:3]:
            if anomaly.get("severity") in ["high", "medium"]:
                complications.append(
                    {
                        "id": f"risk_{len(complications) + 1}",
                        "type": "anomaly",
                        "title": f"Unusual values in {anomaly.get('column', 'data')}",
                        "narrative": self._generate_anomaly_narrative(anomaly),
                        "urgency": anomaly.get("severity", "medium"),
                        "evidence": {
                            "metric": f"{anomaly.get('count', 0)} values ({anomaly.get('percentage', 0):.1f}%)",
                            "risk_description": "Values deviate significantly from normal range",
                        },
                        "mitigation": "Investigate the source of these unusual values",
                    }
                )

        # Build story
        story_data = {
            "title": self._generate_title(findings, complications, theme_info),
            "subtitle": f"An analysis of {dataset_name}",
            "opening": {
                "hook": self._generate_hook(findings, complications, data_quality),
                "takeaway": self._generate_takeaway(findings, complications),
                "why_matters": self._generate_why_matters(findings),
            },
            "findings": findings,
            "complications": complications,
            "resolution": self._generate_resolution(
                recommendations, findings, complications
            ),
        }

        return self._build_response(
            story_id=story_id,
            story_data=story_data,
            dataset_name=dataset_name,
            theme_info=theme_info,
            generation_method="template_fallback",
        )

    def _generate_trend_narrative(self, trend: Dict) -> str:
        """Generate a narrative description for a trend."""
        column = trend.get("column", "this metric")
        direction = trend.get("direction", "changing")

        narratives = {
            "increasing": f"**{column}** shows a clear upward trend. This pattern has been consistent over the observed time period.",
            "decreasing": f"**{column}** is trending downward. This decline warrants attention and investigation.",
            "stable": f"**{column}** has remained relatively stable, suggesting consistent performance in this area.",
        }

        return narratives.get(
            direction,
            f"**{column}** shows a notable pattern that deserves examination.",
        )

    def _generate_correlation_narrative(self, corr: Dict) -> str:
        """Generate a narrative description for a correlation."""
        col1 = corr.get("column1", "X")
        col2 = corr.get("column2", "Y")
        value = corr.get("value", corr.get("correlation", 0))
        strength = "strong" if abs(value) > 0.6 else "moderate"
        direction = "positive" if value > 0 else "inverse"

        return f"A {strength} {direction} relationship exists between **{col1}** and **{col2}**. When one increases, the other tends to {'increase' if value > 0 else 'decrease'} as well."

    def _generate_anomaly_narrative(self, anomaly: Dict) -> str:
        """Generate a narrative description for an anomaly."""
        column = anomaly.get("column", "data")
        count = anomaly.get("count", 0)
        pct = anomaly.get("percentage", 0)

        return f"**{column}** contains {count} unusual values ({pct:.1f}% of data). These outliers may indicate data quality issues or genuine anomalies worth investigating."

    def _generate_title(
        self, findings: List, complications: List, theme_info: Dict
    ) -> str:
        """Generate a compelling story title."""
        theme = theme_info.get("theme", "exploration")

        if complications and len(complications) > 0:
            return "Data Reveals Areas Requiring Attention"

        if theme == "growth":
            return "Positive Trends Present Opportunities"

        if theme == "decline":
            return "Declining Patterns Need Investigation"

        if findings:
            return "Key Patterns Discovered in Your Data"

        return "Initial Analysis of Your Data"

    def _generate_hook(
        self, findings: List, complications: List, data_quality: Dict
    ) -> str:
        """Generate the opening hook."""
        if complications:
            return "Your data contains patterns that warrant closer examination."

        if findings:
            return "Analysis of your data reveals several noteworthy patterns and relationships."

        return "Your data is ready for exploration and discovery."

    def _generate_takeaway(self, findings: List, complications: List) -> str:
        """Generate the key takeaway."""
        if complications:
            return f"Found {len(complications)} areas of concern that may require attention. These include unusual patterns that deviate from expected behavior."

        if findings:
            return f"Identified {len(findings)} significant patterns in your data. These findings provide insight into the relationships and trends within your dataset."

        return "Initial analysis shows your data contains patterns worth exploring further."

    def _generate_why_matters(self, findings: List) -> str:
        """Generate why this matters."""
        if findings:
            return "Understanding these patterns can inform better decision-making and help identify opportunities or areas for improvement."

        return (
            "Recognizing these patterns is the first step toward data-driven insights."
        )

    def _generate_resolution(
        self, recommendations: List, findings: List, complications: List
    ) -> Dict:
        """Generate the resolution/action section."""
        primary_action = None

        if recommendations:
            rec = recommendations[0]
            primary_action = {
                "title": rec.get("title", rec.get("text", "Review the findings")),
                "rationale": rec.get(
                    "description", "This action addresses the key findings identified."
                ),
                "impact": "Addresses primary insights",
                "effort": "medium",
            }
        elif complications:
            primary_action = {
                "title": "Investigate the identified anomalies",
                "rationale": "Understanding these unusual patterns can prevent potential issues.",
                "impact": "Identify root causes",
                "effort": "medium",
            }
        elif findings:
            primary_action = {
                "title": "Dive deeper into the key findings",
                "rationale": "Further investigation can reveal additional insights.",
                "impact": "Discover opportunities",
                "effort": "low",
            }
        else:
            primary_action = {
                "title": "Ask specific questions about your data",
                "rationale": "Targeted questions yield the most valuable insights.",
                "impact": "Focused analysis",
                "effort": "low",
            }

        secondary = []
        for rec in recommendations[1:3]:
            secondary.append(
                {
                    "title": rec.get("title", rec.get("text", "Additional action")),
                    "description": rec.get("description", "Supporting action item"),
                }
            )

        return {
            "story_conclusion": "This analysis provides a foundation for understanding your data. Further exploration can reveal additional insights.",
            "primary_action": primary_action,
            "secondary_actions": secondary,
            "monitoring": {
                "key_metrics": [f.get("title", "Metric") for f in findings[:3]],
                "check_frequency": "weekly",
                "success_indicator": "Improved understanding and decision-making",
            },
        }

    def _build_response(
        self,
        story_id: str,
        story_data: Dict,
        dataset_name: str,
        theme_info: Dict,
        generation_method: str,
    ) -> Dict[str, Any]:
        """Build the complete response structure."""
        # Calculate reading time based on content
        findings_count = len(story_data.get("findings", []))
        reading_time = max(2, min(10, 2 + findings_count // 2))

        return {
            "story": {
                "id": story_id,
                "title": story_data.get("title", "Your Data Story"),
                "subtitle": story_data.get("subtitle", f"Analysis of {dataset_name}"),
                "opening": story_data.get(
                    "opening",
                    {
                        "hook": "Here's what your data reveals.",
                        "takeaway": "Key patterns and insights have been identified.",
                        "why_matters": "Understanding these patterns informs better decisions.",
                    },
                ),
                "findings": story_data.get("findings", []),
                "complications": story_data.get("complications", []),
                "resolution": story_data.get(
                    "resolution",
                    {
                        "story_conclusion": "Further exploration can reveal additional insights.",
                        "primary_action": {
                            "title": "Explore the findings",
                            "rationale": "Understanding these patterns is the first step.",
                            "impact": "Data-driven insights",
                            "effort": "low",
                        },
                        "secondary_actions": [],
                        "monitoring": {
                            "key_metrics": [],
                            "check_frequency": "weekly",
                            "success_indicator": "Improved understanding",
                        },
                    },
                ),
                "metadata": {
                    "theme": theme_info.get("theme", "exploration"),
                    "tone": theme_info.get("tone", "neutral"),
                    "confidence_score": 0.7,
                    "reading_time_minutes": reading_time,
                    "generation_method": generation_method,
                    "dataset": dataset_name,
                },
            },
            "story_id": story_id,
            "is_story": True,
            "generation_method": generation_method,
        }

    def _generate_error_story(
        self, story_id: str, dataset_name: str, error: str
    ) -> Dict[str, Any]:
        """Generate a story when everything fails."""
        return {
            "story": {
                "id": story_id,
                "title": "Analysis in Progress",
                "subtitle": f"Analysis of {dataset_name}",
                "opening": {
                    "hook": "We're preparing your data story.",
                    "takeaway": "The analysis is being completed. Please check back shortly.",
                    "why_matters": "Your insights are being generated.",
                },
                "findings": [],
                "complications": [],
                "resolution": {
                    "story_conclusion": "Your detailed story will be available shortly.",
                    "primary_action": {
                        "title": "Refresh to see results",
                        "rationale": "The analysis is still processing.",
                        "impact": "Complete insights",
                        "effort": "low",
                    },
                    "secondary_actions": [],
                    "monitoring": {
                        "key_metrics": [],
                        "check_frequency": "5 minutes",
                        "success_indicator": "Complete story available",
                    },
                },
                "metadata": {
                    "theme": "exploration",
                    "tone": "neutral",
                    "confidence_score": 0.0,
                    "reading_time_minutes": 1,
                    "generation_method": "error",
                    "dataset": dataset_name,
                    "error": error,
                },
            },
            "story_id": story_id,
            "is_story": True,
            "generation_method": "error",
        }

    def _transform_to_frontend_format(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform new 3-stage pipeline output to frontend-compatible format.

        New format (from Qwen 2.5 72B):
        {
            "report": {
                "headline": { title, subtitle, verdict },
                "opening_story": "...",
                "findings": [{ id, headline, story, the_number, what_it_means, connects_to_next }],
                "warnings": [{ id, headline, story, urgency_label, what_to_do }],
                "what_this_means": "...",
                "action_plan": { primary_action, supporting_actions },
                "what_to_watch": [{ metric, right_now, watch_for, how_often }],
                "closing": "...",
                "metadata": { overall_health, story_theme, tone, top_priority, reading_time_minutes }
            }
        }

        Frontend format (expected by StoryReader):
        {
            "title": "...",
            "subtitle": "...",
            "opening": { hook, takeaway, why_matters },
            "findings": [{ id, type, title, narrative, evidence, connects_to, importance }],
            "complications": [{ id, type, urgency, narrative, evidence, mitigation }],
            "resolution": {
                "story_conclusion": "...",
                "primary_action": { title, rationale, impact, effort },
                "secondary_actions": [{ title, description }],
                "monitoring": { key_metrics, check_frequency, success_indicator }
            },
            "metadata": { theme, tone, confidence_score, reading_time_minutes }
        }
        """
        try:
            headline = report.get("headline", {})
            action_plan = report.get("action_plan", {})
            primary_action = action_plan.get("primary_action", {})
            metadata = report.get("metadata", {})
            what_to_watch = report.get("what_to_watch", []) or []

            return {
                "title": headline.get("title", ""),
                "subtitle": headline.get("subtitle", ""),
                "opening": {
                    "hook": report.get("opening_story", ""),
                    "takeaway": report.get("what_this_means", ""),
                    "why_matters": headline.get("verdict", ""),
                },
                "findings": self._transform_findings(report.get("findings", [])),
                "complications": self._transform_warnings(report.get("warnings", [])),
                "resolution": {
                    "story_conclusion": report.get("closing", ""),
                    "primary_action": {
                        "title": primary_action.get("what", ""),
                        "rationale": primary_action.get("why", ""),
                        "impact": primary_action.get("expected_result", ""),
                        "effort": primary_action.get("effort", "medium"),
                    },
                    "secondary_actions": [
                        {
                            "title": action.get("what", ""),
                            "description": f"{action.get('why', '')} ({action.get('when', '')})",
                        }
                        for action in action_plan.get("supporting_actions", [])
                    ],
                    "monitoring": {
                        "key_metrics": [
                            watch.get("metric", "") for watch in what_to_watch
                        ],
                        "check_frequency": what_to_watch[0].get("how_often", "weekly")
                        if what_to_watch
                        else "weekly",
                        "success_indicator": what_to_watch[0].get("watch_for", "")
                        if what_to_watch
                        else "",
                    },
                },
                "metadata": {
                    "theme": metadata.get("story_theme", "mixed"),
                    "tone": metadata.get("tone", "neutral"),
                    "confidence_score": 0.85,
                    "reading_time_minutes": metadata.get("reading_time_minutes", 3),
                    "generation_method": "3_stage_pipeline",
                    "overall_health": metadata.get("overall_health", "Stable"),
                    "top_priority": metadata.get("top_priority", ""),
                },
            }
        except Exception as e:
            logger.error(f"Format transformation error: {e}")
            return report

    def _transform_findings(self, findings: List[Dict]) -> List[Dict]:
        """Transform new finding format to frontend format."""
        transformed = []
        for idx, finding in enumerate(findings):
            headline = finding.get("headline", "").strip()
            story = finding.get("story", "").strip()

            # Fallback: if headline or story is empty, generate from other fields
            if not headline:
                headline = finding.get("what_it_means", f"Finding {idx + 1}").strip()
            if not story:
                story = finding.get(
                    "connects_to_next", f"Key insight identified in your data"
                ).strip()

            # Only add to transformed if we have at least some content
            if headline or story:
                transformed.append(
                    {
                        "id": finding.get("id", f"finding_{idx + 1}"),
                        "type": "discovery",
                        "title": headline or f"Finding {idx + 1}",
                        "narrative": story
                        or "This finding reveals important patterns in your data.",
                        "evidence": {
                            "key_metric": finding.get("the_number", ""),
                            "supporting_details": [],
                            "confidence": "high",
                        },
                        "connects_to": finding.get("connects_to_next"),
                        "importance": 10 - idx,
                    }
                )
        return transformed

    def _transform_warnings(self, warnings: List[Dict]) -> List[Dict]:
        """Transform new warning format to frontend complications format."""
        transformed = []
        for idx, warning in enumerate(warnings):
            headline = warning.get("headline", "").strip()
            story = warning.get("story", "").strip()

            # Fallback: if content is empty, generate from other fields
            if not headline:
                headline = warning.get("urgency_label", f"Risk {idx + 1}").strip()
            if not story:
                story = warning.get(
                    "what_to_do", "Action needed to mitigate this risk"
                ).strip()

            urgency = warning.get("urgency_label", "")
            urgency_type = "high"
            if "today" in urgency.lower():
                urgency_type = "critical"
            elif "week" in urgency.lower():
                urgency_type = "high"
            else:
                urgency_type = "medium"

            transformed.append(
                {
                    "id": warning.get("id", f"warning_{idx + 1}"),
                    "type": "warning",
                    "title": headline or f"Risk {idx + 1}",
                    "urgency": urgency_type,
                    "narrative": story or "This risk requires attention.",
                    "evidence": {
                        "metric": headline or f"Risk {idx + 1}",
                        "threshold": "",
                        "risk_description": urgency or "Keep watching",
                    },
                    "mitigation": warning.get("what_to_do", ""),
                }
            )
        return transformed


# Singleton instance
story_weaver = StoryWeaver()
