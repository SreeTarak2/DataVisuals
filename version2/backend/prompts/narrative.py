"""
narrative — 3-Stage Enterprise Narrative Pipeline
====================================================

Extracted from core/narrative_prompts.py.

Pipeline:
  Stage 1: Raw computation & pattern extraction
  Stage 2: Insight prioritization
  Stage 3: Enterprise plain-English narration
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

JARGON_BAN: Dict[str, List[str]] = {
    "finance": [
        "correlation", "correlated", "correlates",
        "p-value", "p value", "p < 0.05",
        "r-value", "r value", "r-squared", "r squared", "r²",
        "regression", "regressed",
        "standard deviation", "std dev", "std.",
        "variance", "coefficient", "coefficients",
        "percentile", "quartile", "IQR", "interquartile",
        "null hypothesis", "alternative hypothesis",
        "significance", "significant",
        "statistically significant", "statistical significance",
        "confidence interval", "CI",
        "t-test", "t test", "z-score", "z score",
        "normal distribution", "gaussian", "bell curve",
        "skewness", "skewed", "kurtosis",
        "median", "mean", "mode", "modality",
        "outlier", "outliers",
        "heteroscedasticity", "multicollinearity",
        "autoregression", "stationarity",
        "covariance", "covariate", "eigenvalue",
    ],
    "scientific": [
        "p-value", "p < 0.05", "p value",
        "null hypothesis", "alternative hypothesis",
        "statistical significance", "confidence interval",
        "standard error", "effect size", "Cohen's d",
        "ANOVA", "chi-square", "chi square", "χ²",
        "F-statistic", "f-statistic", "t-statistic", "t statistic",
        "degrees of freedom", "power analysis",
        "beta error", "alpha level", "Bonferroni",
        "post-hoc", "post hoc",
        "multivariate", "univariate", "heterogeneity",
        "confounding variable", "covariate",
        "longitudinal", "cross-sectional", "cohort",
        "endogenous", "exogenous",
    ],
}

PLAIN_ENGLISH_GLOSSARY = {
    "strong positive correlation (r=0.85)": "when one goes up, the other almost always goes up too",
    "weak correlation": "these two things don't have a clear relationship",
    "statistically significant (p<0.05)": "this pattern is real, not random chance",
    "outlier detected": "one result is very different from everything else",
    "high variance": "results are all over the place",
    "low variance": "results are very consistent and predictable",
    "left-skewed distribution": "most results are on the higher end, with a few unusually low ones",
    "right-skewed distribution": "most results are on the lower end, with a few unusually high ones",
    "normal distribution": "results follow the typical bell-curve pattern",
    "standard deviation of 2.3": "results typically vary by about 2.3 from the average",
    "confidence interval": "the range we'd expect the true number to fall within",
    "regression analysis shows": "when we look at what drives this number",
    "multivariate analysis": "when we look at everything at once",
    "anomaly": "something unusual",
    "null value": "missing information",
    "data quality issue": "some of the data has problems",
    "median": "the middle value",
    "quartile": "group of 25%",
    "percentile": "ranked position out of 100",
}


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — RAW COMPUTATION PROMPT
# ─────────────────────────────────────────────────────────────────────────────


def get_stage1_computation_prompt(
    raw_data: str,
    domain: str,
    dataset_name: str,
    business_context: Optional[str] = None,
) -> str:
    """Stage 1: DeepSeek V3.2 — heavy lifting computation, pattern detection."""
    return f"""You are a senior data analyst performing deep quantitative analysis.
Your job is ONLY computation and pattern extraction — not storytelling.

DATASET: {dataset_name}
DOMAIN: {domain}
{f"BUSINESS CONTEXT: {business_context}" if business_context else ""}

== RAW DATA / QUERY RESULTS ==
{raw_data}
== END DATA ==

Perform exhaustive analysis and return ONLY valid JSON.

{{
  "dataset_summary": {{
    "total_records": <integer>,
    "time_period": "<date range or 'N/A'>",
    "key_dimensions": ["<column or dimension names>"],
    "data_completeness": "<percentage of non-null values>"
  }},
  "primary_findings": [
    {{
      "id": "finding_1",
      "type": "trend | pattern | anomaly | comparison | relationship",
      "metric_name": "<exact metric>",
      "raw_value": "<exact number or percentage>",
      "baseline_value": "<what this is compared against>",
      "delta": "<change in absolute and percentage terms>",
      "direction": "up | down | stable | volatile",
      "magnitude": "critical | high | medium | low",
      "technical_detail": "<full technical explanation with numbers>",
      "time_context": "<when did this happen or what time range>"
    }}
  ],
  "anomalies": [...],
  "trends": [...],
  "top_performers": [...],
  "bottom_performers": [...],
  "key_drivers": [...],
  "risks_and_warnings": [...],
  "data_quality_flags": [...],
  "headline_number": {{
    "metric": "<the single most important number>",
    "value": "<its value>",
    "context": "<one sentence of context>"
  }}
}}

Rules:
- Include ONLY what the data actually shows. Never invent.
- Every finding must cite a specific number from the data.
- If a section has no findings, return [].
- Return ONLY valid JSON. No markdown, no explanation.
"""


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — INSIGHT PRIORITIZATION PROMPT
# ─────────────────────────────────────────────────────────────────────────────


def get_stage2_prioritization_prompt(
    stage1_output: str,
    domain: str,
    business_context: Optional[str] = None,
) -> str:
    """Stage 2: DeepSeek V3.2 — rank and prioritize findings."""
    return f"""You are a senior data analyst with 15 years of experience.
You've just completed a technical analysis. Now you must decide:
"If I had 5 minutes with the CEO, what would I tell them?"

DOMAIN: {domain}
{f"BUSINESS CONTEXT: {business_context}" if business_context else ""}

== TECHNICAL ANALYSIS OUTPUT ==
{stage1_output}
== END ANALYSIS ==

Your task: From all findings above, select and prioritize ONLY what truly matters.
A real analyst doesn't dump everything — they curate ruthlessly.

Return ONLY valid JSON:

{{
  "story_angle": "<one sentence: what is THE story in this data?>",
  "story_theme": "growth | decline | risk | opportunity | mixed | warning",
  "overall_health": {{
    "status": "strong | stable | concerning | critical",
    "one_line_verdict": "<honest one-line verdict>"
  }},
  "top_3_things_that_matter": [
    {{
      "rank": 1,
      "finding_ref": "<id from stage 1>",
      "why_it_matters": "<business impact in plain terms>",
      "the_number": "<the specific value>",
      "compared_to": "<what it's being measured against>",
      "plain_english_label": "<a label a non-analyst would understand>"
    }}
  ],
  "the_good_news": [...],
  "the_bad_news": [...],
  "the_surprising_finding": {{
    "exists": true | false,
    "finding": "...",
    "why_surprising": "..."
  }},
  "root_cause": {{
    "exists": true | false,
    "main_driver": "...",
    "evidence": "...",
    "confidence": "high | medium | low"
  }},
  "recommended_actions": [
    {{
      "priority": 1,
      "action": "<specific, concrete action>",
      "expected_outcome": "...",
      "timeframe": "...",
      "effort": "quick win | medium effort | major initiative"
    }}
  ],
  "what_to_watch": [...],
  "narrative_facts": ["fact 1 with number", "fact 2 with number", "..."]
}}

Rules:
- Be ruthlessly honest. If things are bad, say so clearly.
- top_3_things_that_matter ranked by BUSINESS IMPACT.
- recommended_actions must be SPECIFIC.
- Return ONLY valid JSON. No markdown.
"""


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — ENTERPRISE NARRATION PROMPT
# ─────────────────────────────────────────────────────────────────────────────


def get_stage3_narration_prompt(
    stage2_output: str,
    dataset_name: str,
    domain: str,
    business_context: Optional[str] = None,
) -> str:
    """Stage 3: Qwen 2.5 72B — enterprise-grade plain English narrative."""
    return f"""You are a world-class business storyteller. Your job: take raw data findings and transform them into a narrative that any smart business owner can read in 5 minutes and immediately act on.

DATASET: {dataset_name}
DOMAIN: {domain}
{f"BUSINESS CONTEXT: {business_context}" if business_context else ""}

== PRIORITIZED FINDINGS (from senior analyst) ==
{stage2_output}
== END FINDINGS ==

Apply BLUF (Bottom Line Up Front): The most important insight goes FIRST.
Use SCR (Situation → Complication → Resolution) framework.
Every finding must follow: Observation → Business Impact → Recommended Action.

Return ONLY valid JSON:
{{
  "report": {{
    "headline": {{
      "title": "<8-12 words. Newspaper headline with a number.>",
      "subtitle": "<one sentence adding context>",
      "verdict": "<the single most important thing happening right now>"
    }},
    "opening_story": "<2-3 sentences. BLUF. Include numbers.>",
    "findings": [
      {{
        "id": "finding_1",
        "finding_type": "trend | pattern | anomaly | connection | discovery",
        "importance": <integer 1-10>,
        "headline": "<5-8 words with a number>",
        "story": "<3-5 sentences. Situation → Complication → Resolution.>",
        "the_number": "<the single most important metric>",
        "what_it_means": "<business consequence>",
        "connects_to_next": "<bridge to next finding>"
      }}
    ],
    "warnings": [...],
    "what_this_means": "<2-3 sentences big picture>",
    "action_plan": {{
      "primary_action": {{ "what": "...", "why": "...", "expected_result": "...", "when": "...", "effort": "..." }},
      "supporting_actions": [...]
    }},
    "what_to_watch": [...],
    "closing": "<2 sentences forward-looking>",
    "metadata": {{
      "overall_health": "Strong | Stable | Needs attention | Critical",
      "story_theme": "growth | decline | opportunity | risk | mixed",
      "tone": "positive | cautious | urgent | neutral",
      "top_priority": "<the single most important thing>"
    }}
  }}
}}

JARGON BAN: Never use any of these: {", ".join(JARGON_BAN.get(domain.lower(), JARGON_BAN["finance"]))}
Replace with plain English equivalents. Always bold key numbers with **.

Return ONLY valid JSON. No markdown, no explanation outside the JSON.
"""


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK TEMPLATES (for when no findings exist)
# ─────────────────────────────────────────────────────────────────────────────

FALLBACK_STORY_TEMPLATES = {
    "no_findings": {
        "story": {
            "headline": {
                "title": "Your Data Holds Stories We Can Help You Find",
                "subtitle": "Initial scan complete. The strongest insights come from asking the right questions.",
                "verdict": "We found initial patterns, but need more context for deeper insights.",
            },
            "opening_story": (
                "Your data is connected and we've done an initial scan. "
                "We found some basic patterns, but the most valuable insights come from "
                "asking specific questions about what matters to your business."
            ),
            "findings": [],
            "warnings": [],
            "what_this_means": (
                "Every dataset has stories to tell. "
                "Try asking a specific question like 'What drives my sales?' or 'Why do customers churn?' "
                "to unlock meaningful insights tailored to your needs."
            ),
            "action_plan": {
                "primary_action": {
                    "what": "Ask a specific question about your data",
                    "why": "Focused questions produce the clearest, most actionable insights.",
                    "expected_result": "A clear, plain-English answer backed by your actual data",
                    "when": "Right now",
                    "effort": "Quick win (minutes)",
                },
                "supporting_actions": [],
            },
            "what_to_watch": [],
            "closing": "Your data is ready. Ask a question to discover what it knows.",
            "metadata": {
                "overall_health": "Stable",
                "story_theme": "opportunity",
                "tone": "neutral",
                "top_priority": "Ask a specific question to unlock meaningful insights",
                "reading_time_minutes": 1,
            },
        }
    },
    "insufficient_data": {
        "story": {
            "headline": {
                "title": "Your Data Is Ready — Let's Ask It a Question",
                "subtitle": "Initial scan complete. The real insights come from specific questions.",
                "verdict": "We have your data loaded and ready to analyze.",
            },
            "opening_story": (
                "Your data is connected and we've done an initial scan. "
                "At this stage, the data looks clean and usable. "
                "The best insights will come when you ask a specific question."
            ),
            "findings": [],
            "warnings": [],
            "what_this_means": (
                "Every business dataset tells a story. "
                "We just need to know which chapter you want to read first."
            ),
            "action_plan": {
                "primary_action": {
                    "what": "Ask your first question about the data",
                    "why": "Focused questions produce the clearest insights.",
                    "expected_result": "A clear, plain-English answer backed by your actual data",
                    "when": "Right now",
                    "effort": "Quick win (hours)",
                },
                "supporting_actions": [],
            },
            "what_to_watch": [],
            "closing": "Your data is ready. The insights are waiting.",
            "metadata": {
                "overall_health": "Stable",
                "story_theme": "opportunity",
                "tone": "neutral",
                "top_priority": "Ask a specific question to unlock meaningful insights",
                "reading_time_minutes": 1,
            },
        }
    },
    "data_quality_too_low": {
        "story": {
            "headline": {
                "title": "Data Quality Issues Found — Action Needed",
                "subtitle": "Several problems in the data need to be fixed before we can give you reliable insights.",
                "verdict": "The data has quality issues that could lead to wrong conclusions.",
            },
            "opening_story": (
                "Before we can give you insights you can trust, there are some data problems "
                "that need to be addressed. This isn't unusual — most business data has gaps. "
                "The good news is these are fixable."
            ),
            "findings": [],
            "warnings": [
                {
                    "id": "warning_data_quality",
                    "headline": "Data quality problems could lead to wrong conclusions",
                    "story": (
                        "Some fields are missing data, and some values look incorrect. "
                        "If we run analysis on data with these problems, the results could be misleading."
                    ),
                    "urgency_label": "Act this week",
                    "what_to_do": "Review and fill in the flagged fields in your data source before re-running analysis",
                }
            ],
            "what_this_means": "Clean data leads to reliable insights. Messy data leads to wrong decisions.",
            "action_plan": {
                "primary_action": {
                    "what": "Fix the identified data quality issues in your source system",
                    "why": "Decisions based on bad data are worse than no data at all.",
                    "expected_result": "Clean, reliable data ready for meaningful analysis",
                    "when": "This week",
                    "effort": "This week",
                },
                "supporting_actions": [],
            },
            "what_to_watch": [],
            "closing": "Once the data is clean, we'll be able to give you the full picture.",
            "metadata": {
                "overall_health": "Needs attention",
                "story_theme": "risk",
                "tone": "cautious",
                "top_priority": "Fix data quality issues before running analysis",
                "reading_time_minutes": 1,
            },
        }
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# LEGACY PROMPTS
# ─────────────────────────────────────────────────────────────────────────────


def get_story_weaver_prompt(
    fact_sheet: str,
    dataset_name: str,
    domain: str,
    story_theme: Optional[str] = None,
) -> str:
    """Legacy single-stage story generation prompt."""
    return f"""You are a master storyteller specializing in data journalism.

DATASET: "{dataset_name}"
DOMAIN: {domain}
{f"SUGGESTED THEME: {story_theme}" if story_theme else ""}

== ANALYTICAL FACT SHEET ==
{fact_sheet}
== END FACT SHEET ==

Write a JSON response with story structure including title, subtitle, opening, findings, complications, and resolution.
Return ONLY valid JSON.
"""


def get_story_theme_detection_prompt(
    current_finding: Dict[str, Any],
    next_finding: Dict[str, Any],
) -> str:
    """Generate transition between two story findings."""
    return f"""Generate a 1-2 sentence transition.

CURRENT: {current_finding.get("title", "N/A")} — {str(current_finding.get("narrative", ""))[:200]}
NEXT: {next_finding.get("title", "N/A")} — {str(next_finding.get("narrative", ""))[:200]}

Return: {{"transition": "your transition text here"}}
"""


def get_story_resolution_prompt(
    story_findings: List[Dict],
    complications: List[Dict],
    primary_metrics: Dict,
) -> str:
    """Generate resolution/conclusion of a story."""
    findings_text = "\n".join([f"- {f.get('title', 'N/A')}: {str(f.get('narrative', ''))[:100]}..." for f in story_findings[:5]])
    complications_text = "\n".join([f"- {c.get('title', 'N/A')}" for c in complications]) if complications else "- No major risks identified"
    metrics_text = "\n".join([f"- {k}: {v}" for k, v in primary_metrics.items()])

    return f"""Write the resolution section:

FINDINGS:
{findings_text}

COMPLICATIONS:
{complications_text}

METRICS:
{metrics_text}

Return ONLY valid JSON with story_conclusion, primary_action, secondary_actions, and monitoring.
"""


# ─────────────────────────────────────────────────────────────────────────────
# QUALITY VALIDATION
# ─────────────────────────────────────────────────────────────────────────────


def validate_narration_quality(narration_output: dict, domain: str) -> dict:
    """Validate Stage 3 output for quality before sending to UI."""
    issues = []
    report_text = str(narration_output)
    banned_words = JARGON_BAN.get(domain.lower(), JARGON_BAN["finance"])

    found_jargon = [word for word in banned_words if word.lower() in report_text.lower()]
    if found_jargon:
        issues.append(f"Banned jargon found: {', '.join(found_jargon)}")

    report = narration_output.get("story", narration_output.get("report", {}))
    action_plan = report.get("action_plan", {})
    primary_action = action_plan.get("primary_action", {})
    if not primary_action.get("what"):
        issues.append("Missing primary action")

    opening = report.get("opening_story", "")
    if len(opening) < 50:
        issues.append("Opening story too short")

    findings = report.get("findings", [])
    if len(findings) == 0:
        issues.append("No findings")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "jargon_found": found_jargon,
    }


__all__ = [
    "FALLBACK_STORY_TEMPLATES",
    "JARGON_BAN",
    "PLAIN_ENGLISH_GLOSSARY",
    "get_stage1_computation_prompt",
    "get_stage2_prioritization_prompt",
    "get_stage3_narration_prompt",
    "get_story_weaver_prompt",
    "get_story_theme_detection_prompt",
    "get_story_resolution_prompt",
    "validate_narration_quality",
]
