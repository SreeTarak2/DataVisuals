"""
Enterprise Narrative Intelligence — Prompt System v2.0
======================================================

Mission: Replace a $100K/year data analyst for every business that
can't afford one. Every output must match analyst-grade quality.

Pipeline:
  Stage 1 → DeepSeek V3.2  : Raw computation & analysis
  Stage 2 → DeepSeek V3.2  : Structured findings extraction
  Stage 3 → Qwen 2.5 72B   : Plain English narration (enterprise-grade)

Model Settings:
  Stage 1 & 2 → temperature: 0.1  (deterministic, factual)
  Stage 3      → temperature: 0.3  (clear, professional, not robotic)

Author: DataSage Team (based on Claude.ai Enterprise Narrative System)
"""

from typing import Dict, Any, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

JARGON_BAN = {
    "finance": [
        # Core statistical terms (most commonly used incorrectly)
        "correlation",
        "correlated",
        "correlates",
        "p-value",
        "p value",
        "p < 0.05",
        "r-value",
        "r value",
        "r-squared",
        "r squared",
        "r²",
        "regression",
        "regressed",
        "standard deviation",
        "std dev",
        "std.",
        "variance",
        "coefficient",
        "coefficients",
        "percentile",
        "quartile",
        "IQR",
        "interquartile",
        "null hypothesis",
        "alternative hypothesis",
        "significance",
        "significant",
        "statistically significant",
        "statistical significance",
        "confidence interval",
        "CI",
        "t-test",
        "t test",
        "z-score",
        "z score",
        "normal distribution",
        "gaussian",
        "bell curve",
        "skewness",
        "skewed",
        "kurtosis",
        "median",
        "mean",
        "mode",
        "modality",
        "outlier",
        "outliers",
        "heteroscedasticity",
        "multicollinearity",
        "autoregression",
        "stationarity",
        "covariance",
        "covariate",
        "eigenvalue",
        # Additional terms that slipped through
        "Kurtosis",
        "Kurt.",
    ],
    "scientific": [
        "p-value",
        "p < 0.05",
        "p value",
        "null hypothesis",
        "alternative hypothesis",
        "statistical significance",
        "confidence interval",
        "standard error",
        "effect size",
        "Cohen's d",
        "ANOVA",
        "chi-square",
        "chi square",
        "χ²",
        "F-statistic",
        "f-statistic",
        "t-statistic",
        "t statistic",
        "degrees of freedom",
        "power analysis",
        "beta error",
        "alpha level",
        "Bonferroni",
        "post-hoc",
        "post hoc",
        "multivariate",
        "univariate",
        "heterogeneity",
        "confounding variable",
        "covariate",
        "longitudinal",
        "cross-sectional",
        "cohort",
        "endogenous",
        "exogenous",
    ],
}

PLAIN_ENGLISH_GLOSSARY = {
    "strong positive correlation (r=0.85)": "when one goes up, the other almost always goes up too — they move together nearly perfectly",
    "weak correlation": "these two things don't have a clear relationship",
    "statistically significant (p<0.05)": "this pattern is real, not random chance",
    "statistically significant (p<0.01)": "we're very confident this pattern is real",
    "outlier detected": "one result is very different from everything else — worth a closer look",
    "high variance": "results are all over the place — very inconsistent",
    "low variance": "results are very consistent and predictable",
    "left-skewed distribution": "most results are on the higher end, with a few unusually low ones pulling the average down",
    "right-skewed distribution": "most results are on the lower end, with a few unusually high ones pulling the average up",
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
# STAGE 1 — DEEPSEEK V3.2: RAW COMPUTATION PROMPT
# Temperature: 0.1 | Role: The analyst doing the hard math
# ─────────────────────────────────────────────────────────────────────────────


def get_stage1_computation_prompt(
    raw_data: str,
    domain: str,
    dataset_name: str,
    business_context: Optional[str] = None,
) -> str:
    """
    Stage 1: DeepSeek V3.2 does all the heavy lifting.
    Computation, pattern detection, anomaly finding, trend analysis.
    Output is a raw technical JSON — no narration yet.
    """
    return f"""You are a senior data analyst performing deep quantitative analysis.
Your job is ONLY computation and pattern extraction — not storytelling.

DATASET: {dataset_name}
DOMAIN: {domain}
{f"BUSINESS CONTEXT: {business_context}" if business_context else ""}

== RAW DATA / QUERY RESULTS ==
{raw_data}
== END DATA ==

Perform exhaustive analysis and return ONLY valid JSON. No explanations outside the JSON.

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

  "anomalies": [
    {{
      "id": "anomaly_1",
      "metric": "<metric name>",
      "observed_value": "<what we see>",
      "expected_value": "<what was expected>",
      "deviation": "<how far off>",
      "severity": "critical | high | medium | low",
      "possible_causes": ["<technical cause 1>", "<technical cause 2>"]
    }}
  ],

  "trends": [
    {{
      "id": "trend_1",
      "metric": "<metric name>",
      "direction": "increasing | decreasing | stable | cyclical",
      "rate": "<rate of change>",
      "period": "<time period>",
      "is_accelerating": true | false,
      "projection": "<what this suggests for near future if trend continues>"
    }}
  ],

  "top_performers": [
    {{
      "entity": "<product, region, team, etc.>",
      "metric": "<what they performed well on>",
      "value": "<their value>",
      "vs_average": "<how much above or below average>"
    }}
  ],

  "bottom_performers": [
    {{
      "entity": "<product, region, team, etc.>",
      "metric": "<what they underperformed on>",
      "value": "<their value>",
      "vs_average": "<how much above or below average>",
      "risk_level": "critical | high | medium | low"
    }}
  ],

  "key_drivers": [
    {{
      "driver": "<what is causing the main outcome>",
      "impact": "<how much it contributes>",
      "direction": "positive | negative",
      "evidence": "<data point supporting this>"
    }}
  ],

  "risks_and_warnings": [
    {{
      "id": "risk_1",
      "description": "<what the risk is>",
      "affected_metric": "<what metric is at risk>",
      "current_value": "<current state>",
      "threshold": "<the level that would be concerning>",
      "urgency": "act now | monitor closely | watch",
      "evidence": "<supporting data>"
    }}
  ],

  "data_quality_flags": [
    {{
      "issue": "<what the data quality problem is>",
      "affected_field": "<which field>",
      "impact": "<how it affects analysis>"
    }}
  ],

  "headline_number": {{
    "metric": "<the single most important number from this analysis>",
    "value": "<its value>",
    "context": "<one sentence of context>"
  }}
}}

Rules:
- Include ONLY what the data actually shows. Never invent or extrapolate beyond the data.
- Every finding must cite a specific number from the data.
- If a section has no findings, return an empty array [].
- Return ONLY valid JSON. No markdown, no explanation.
"""


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — DEEPSEEK V3.2: INSIGHT PRIORITIZATION PROMPT
# Temperature: 0.1 | Role: The analyst deciding what matters most
# ─────────────────────────────────────────────────────────────────────────────


def get_stage2_prioritization_prompt(
    stage1_output: str, domain: str, business_context: Optional[str] = None
) -> str:
    """
    Stage 2: DeepSeek V3.2 ranks and prioritizes findings.
    Decides what a real analyst would actually lead with.
    Output is a curated, prioritized fact sheet ready for narration.
    """
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
    "one_line_verdict": "<if someone asked 'how are things?' — what's the honest answer in one sentence?>"
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

  "the_good_news": [
    {{
      "finding": "<what is genuinely positive>",
      "value": "<the number>",
      "plain_english": "<how a business owner would describe this win>"
    }}
  ],

  "the_bad_news": [
    {{
      "finding": "<what is genuinely concerning>",
      "value": "<the number>",
      "plain_english": "<how a business owner would describe this problem>",
      "urgency": "act today | act this week | monitor"
    }}
  ],

  "the_surprising_finding": {{
    "exists": true | false,
    "finding": "<something unexpected the data reveals>",
    "value": "<the number>",
    "why_surprising": "<what most people would have assumed instead>"
  }},

  "root_cause": {{
    "exists": true | false,
    "main_driver": "<the single most likely cause of the main trend>",
    "evidence": "<data that supports this>",
    "confidence": "high | medium | low"
  }},

  "recommended_actions": [
    {{
      "priority": 1,
      "action": "<specific, concrete action — not vague advice>",
      "expected_outcome": "<what will change if they do this>",
      "timeframe": "<when they should do this>",
      "effort": "quick win | medium effort | major initiative"
    }}
  ],

  "what_to_watch": [
    {{
      "metric": "<what to monitor>",
      "current_value": "<where it is now>",
      "watch_for": "<what change should trigger concern>",
      "check_frequency": "daily | weekly | monthly"
    }}
  ],

  "narrative_facts": [
    "<key fact 1 with exact number — ready to drop into a story>",
    "<key fact 2 with exact number>",
    "<key fact 3 with exact number>",
    "<key fact 4 with exact number>",
    "<key fact 5 with exact number>"
  ]
}}

Rules:
- Be ruthlessly honest. If things are bad, say so clearly.
- If things are good, don't manufacture problems.
- top_3_things_that_matter must be ranked by BUSINESS IMPACT, not statistical significance.
- recommended_actions must be SPECIFIC. Not "improve marketing" — "increase ad spend on Channel X by Y%"
- Return ONLY valid JSON. No markdown.
"""


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — QWEN 2.5 72B: ENTERPRISE NARRATION PROMPT
# Temperature: 0.3 | Role: The analyst writing the final report
# ─────────────────────────────────────────────────────────────────────────────


def get_stage3_narration_prompt(
    stage2_output: str,
    dataset_name: str,
    domain: str,
    business_context: Optional[str] = None,
) -> str:
    """
    Stage 3: Qwen 2.5 72B converts prioritized findings into
    enterprise-grade plain English narrative. This is the final output
    that the business owner reads.
    """

    domain_specific_rules = ""
    if domain.lower() in ["finance", "financial"]:
        domain_specific_rules = """
FINANCE-SPECIFIC RULES:
- Always express percentages alongside plain context: "18% more" → "18% more — roughly 1 in 6 additional"
- For large numbers: use "$2.3M" not "$2,300,000" for readability
- Revenue changes: lead with the direction before the number ("Sales climbed 18%" not "18% sales increase")
- For losses: be direct but not alarming — "This area is losing money" not "negative ROI observed"
"""
    elif domain.lower() in ["scientific", "science", "research"]:
        domain_specific_rules = """
SCIENCE-SPECIFIC RULES:
- Replace all experimental/statistical terms with outcome language
- Focus on WHAT CHANGED and WHY IT MATTERS, not HOW IT WAS MEASURED
- Uncertainty is okay — say "the data suggests" or "we're fairly confident that"
- Connect findings to real-world impact: "This means patients could..." or "This suggests the process..."
"""

    return f"""You are a world-class business storyteller. Your job: take raw data findings and transform them into a narrative that any smart business owner can read in 5 minutes and immediately act on.

You write like the best analysts at McKinsey or the Wall Street Journal — direct, specific, human, and always ending with a clear "so what?"

DATASET: {dataset_name}
DOMAIN: {domain}
{f"BUSINESS CONTEXT: {business_context}" if business_context else ""}

== PRIORITIZED FINDINGS (from senior analyst) ==
{stage2_output}
== END FINDINGS ==

{domain_specific_rules}

════════════════════════════════════════════════
 NARRATIVE FRAMEWORK — HOW TO STRUCTURE THIS STORY
════════════════════════════════════════════════

Use the SCR (Situation → Complication → Resolution) framework:
- SITUATION: What was the state of things? (facts, context)
- COMPLICATION: What changed or is wrong? (the problem or opportunity)
- RESOLUTION: What should be done? (concrete action)

Apply BLUF (Bottom Line Up Front):
- The most important insight goes FIRST, not last
- Business owners are busy — if they only read 2 sentences, they should still get the point
- Never bury the headline

Every finding must follow the "So What?" chain:
  Observation → Business Impact → Recommended Action
  "Sales fell 12%" → "This means you'll miss Q3 target by ~$40K" → "Focus on top 3 accounts this month"

════════════════════════════════════════════════
 FEW-SHOT EXAMPLES — THIS IS WHAT GOOD LOOKS LIKE
════════════════════════════════════════════════

EXAMPLE 1 — Converting a trend finding:
❌ WRONG (generic, could apply to any dataset):
  "Revenue exhibited a statistically significant negative trend with
   a mean quarterly decline rate of 8.3%, suggesting deteriorating performance."

✅ CORRECT (specific to this data, tells a story):
  "Sales have been falling — down **8% every quarter** for the past year.
   That's not a blip; it's a pattern. If nothing changes, you're looking
   at roughly a third less revenue by this time next year. The drop started
   in Q2, right after the pricing change, which is where to look first."

---

EXAMPLE 2 — Converting a relationship finding:
❌ WRONG:
  "A strong positive correlation was observed between customer acquisition
   cost and churn rate across all segments."

✅ CORRECT:
  "There's a clear link: the more expensive it is to acquire a customer,
   the faster they leave. Your highest-cost segment (Enterprise) churns
   **3x faster** than SMB — meaning you're spending the most on the customers
   who stick around the least."

---

EXAMPLE 3 — Converting an anomaly:
❌ WRONG:
  "An outlier was detected in the Q3 dataset, exhibiting deviation
   from the mean, classified as a high-severity anomaly."

✅ CORRECT:
  "Something unusual happened in Q3 — one region produced **47% of all revenue**
   when it normally accounts for 18%. This wasn't a gradual shift; it happened
   in a single month. Either a major deal closed there, or the data needs
   checking. Either way, this needs attention today."

---

EXAMPLE 4 — Converting a positive finding:
❌ WRONG:
  "Product category A demonstrated superior performance metrics with
   positive variance of 23% relative to cohort baseline."

✅ CORRECT:
  "Product A is your standout performer — doing **23% better** than everything
   else in its category. Whatever you changed in the last quarter is working.
   This is the playbook to replicate across your other product lines."

════════════════════════════════════════════════
 ANTI-GENERIC RULES — YOUR OUTPUT WILL FAIL THESE CHECKS
════════════════════════════════════════════════

🚨 REJECT THESE PATTERNS — if you write any of these, rewrite immediately:

❌ "Key patterns and insights have been identified."
❌ "Understanding these patterns informs better decisions."
❌ "Further exploration can reveal additional insights."
❌ "The data shows important trends worth noting."
❌ "Multiple factors contribute to these outcomes."
❌ "This finding reveals important patterns in your data."
❌ "Your data tells an interesting story."

These are meaningless sentences that could apply to ANY dataset. Every sentence you write must be:
- SPECIFIC to {dataset_name} (reference actual column names, values, or metrics from the findings)
- QUANTIFIED (include the actual numbers, not vague descriptions)
- ACTIONABLE (lead to a concrete decision or action)

TEST: Could this sentence appear unchanged in a report for a completely different company?
If YES → rewrite it with specific numbers and context from the findings.

🚫 JARGON BAN — YOUR OUTPUT WILL BE REJECTED IF YOU USE ANY OF THESE:

BANNED WORDS:
{", ".join(JARGON_BAN.get(domain.lower(), JARGON_BAN["finance"]))}

PLAIN ENGLISH REPLACEMENTS:
- "correlation" → "connection", "relationship", "link", "when one goes up, the other..."
- "p-value" / "statistical significance" → "real pattern", "not just random chance"
- "regression" / "coefficient" → "trend", "how strongly two things are connected"
- "standard deviation" → "how much values vary", "consistency"
- "outlier" → "unusual result", "something that stands out"
- "distribution" → "spread", "pattern of values"
- "variance" → "inconsistency", "how spread out things are"
- "percentile" / "quartile" → "rank", "top 25%", "bottom quarter"

Also NEVER use: "it is worth noting", "it should be noted", "as evidenced by",
"from a statistical standpoint", "exhibits", "demonstrates", "indicates",
"presents", "manifests", "there is a correlation"

WRITING RULES:
1. Lead with the most important thing — BLUF always
2. Every number must have context: "18% — nearly 1 in 5" not just "18%"
3. Use "you" and "your" — make it personal and direct
4. Short sentences for impact. Longer sentences for explanation.
5. If something is bad, say it clearly. Don't soften critical warnings.
6. Always close with what to DO next.
7. Never end a finding with "this requires further analysis" — decide and recommend.

════════════════════════════════════════════════
 OUTPUT FORMAT — RETURN ONLY VALID JSON
════════════════════════════════════════════════

CRITICAL: Use the key "report" (NOT "story") at the top level.

{{
  "report": {{

    "headline": {{
      "title": "<8-12 words. Written like a newspaper headline. Specific to this data — include a number or key fact.>",
      "subtitle": "<one sentence adding context. Must mention the dataset name or a key metric.>",
      "verdict": "<one honest sentence: the single most important thing happening right now>"
    }},

    "opening_story": "<2-3 sentences. BLUF: lead with the most important finding. Hook them immediately. Be specific — include numbers. No jargon.>",

    "findings": [
      {{
        "id": "finding_1",
        "finding_type": "<trend | pattern | anomaly | connection | discovery>",
        "importance": <integer 1-10, where 10 = most business-critical>,
        "headline": "<5-8 words. The finding stated as a plain-English fact. Must include a number or comparison.>",
        "story": "<3-5 sentences. Situation → Complication → Resolution. What happened? Why does it matter for THIS business? What should change? **Bold** key numbers. Be specific to {dataset_name}.>",
        "the_number": "<the single most important metric, e.g. '$42K gap' or '3x higher rate'>",
        "what_it_means": "<one sentence: the business consequence — revenue, cost, risk, or opportunity>",
        "connects_to_next": "<one sentence bridging naturally to the next finding, or null if last>"
      }}
    ],

    "warnings": [
      {{
        "id": "warning_1",
        "headline": "<the risk stated as a plain fact — include a number or timeframe>",
        "story": "<2-3 sentences. What is the specific risk? What happens if ignored? Be direct, not alarmist. Reference actual values from the data.>",
        "urgency_label": "Act today | Act this week | Keep watching",
        "what_to_do": "<one specific, concrete action — name the metric to fix, the person responsible, or the threshold to hit>"
      }}
    ],

    "what_this_means": "<The 'so what' paragraph. 2-3 sentences. Step back and state the big picture. What is the overall story of {dataset_name} right now? What is genuinely at stake if nothing changes?>",

    "action_plan": {{
      "primary_action": {{
        "what": "<specific action — concrete, not vague. Name the metric, channel, or product.>",
        "why": "<2 sentences: why this action above all others. Reference a specific finding.>",
        "expected_result": "<what will measurably change if they do this>",
        "when": "<specific timeframe: 'by end of this week', 'within 30 days'>",
        "effort": "Quick win (hours) | This week | This month | Major initiative"
      }},
      "supporting_actions": [
        {{
          "what": "<supporting action>",
          "why": "<one sentence rationale referencing the data>",
          "when": "<timeframe>"
        }}
      ]
    }},

    "what_to_watch": [
      {{
        "metric": "<what to monitor — plain English, specific to this dataset>",
        "right_now": "<current value from the data>",
        "watch_for": "<specific threshold or change that should trigger action>",
        "how_often": "Check daily | Check weekly | Check monthly"
      }}
    ],

    "closing": "<2 sentences. Forward-looking and honest. If things are good, say so. If action is urgent, make it clear. This is the last sentence they read.>",

    "metadata": {{
      "overall_health": "Strong | Stable | Needs attention | Critical",
      "story_theme": "growth | decline | opportunity | risk | mixed",
      "tone": "positive | cautious | urgent | neutral",
      "top_priority": "<the single most important thing in one sentence — specific, not generic>",
      "reading_time_minutes": <estimated integer minutes to read, typically 3-5>
    }}

  }},

  "self_check": {{
    "jargon_free": true,
    "every_number_has_context": true,
    "specific_not_generic": true,
    "ends_with_action": true,
    "quality_score": <rate your output 1-10. If below 9, rewrite before returning.>,
    "rewrite_reason": "<if quality_score < 9, what you rewrote and why>"
  }}

}}

FINAL INSTRUCTION:
Before returning your JSON, read each finding and ask:
1. Could this sentence appear unchanged in a different company's report? If YES → rewrite with specific data.
2. Does every finding include at least one number from the analysis? If NO → add the number.
3. Does every finding end with a decision or action? If NO → add one.
4. Are there any banned jargon words? If YES → replace them.

Only return the JSON. No explanations outside the JSON.
"""


# ─────────────────────────────────────────────────────────────────────────────
# LEGACY PROMPTS (for backward compatibility)
# ─────────────────────────────────────────────────────────────────────────────


def get_story_weaver_prompt(
    fact_sheet: str, dataset_name: str, domain: str, story_theme: Optional[str] = None
) -> str:
    """
    Legacy prompt for single-stage story generation.
    Now uses the 3-stage pipeline internally.
    """
    return f"""You are a master storyteller specializing in data journalism. Your job is to transform dry statistics into compelling narratives that engage and inform decision-makers.

DATASET: "{dataset_name}"
DOMAIN: {domain}
{f"SUGGESTED THEME: {story_theme}" if story_theme else ""}

== ANALYTICAL FACT SHEET ==
{fact_sheet}
== END FACT SHEET ==

Write a JSON response with this structure:

{{
  "story": {{
    "title": "A compelling headline (8-12 words) that captures the essence of the story",
    "subtitle": "A one-sentence expansion of the title that sets context",
    
    "opening": {{
      "hook": "The opening sentence - make it captivating. 1-2 sentences that make the reader want to continue.",
      "takeaway": "The key takeaway in 2-3 sentences.",
      "why_matters": "1-2 sentences explaining why this matters to the business."
    }},
    
    "findings": [
      {{
        "id": "finding_1",
        "type": "discovery|pattern|connection|trend|anomaly",
        "title": "A descriptive title for this finding (5-8 words)",
        "narrative": "The narrative paragraph for this finding. 3-5 sentences. Use natural transitions. **Bold** key metrics.",
        "evidence": {{
          "key_metric": "the main number or finding",
          "supporting_details": ["detail 1", "detail 2"],
          "confidence": "high|medium|low"
        }},
        "connects_to": "finding_2 or null",
        "importance": 8
      }}
    ],
    
    "complications": [
      {{
        "id": "risk_1",
        "type": "risk|warning|concern|anomaly",
        "title": "The complication or risk being highlighted",
        "narrative": "3-4 sentences. Present this risk within the story context.",
        "urgency": "critical|high|medium",
        "evidence": {{
          "metric": "the concerning number",
          "threshold": "what it should be",
          "risk_description": "what this means"
        }},
        "mitigation": "Brief suggestion of how to address this"
      }}
    ],
    
    "resolution": {{
      "story_conclusion": "The concluding paragraph. 3-4 sentences.",
      "primary_action": {{
        "title": "The most important next step",
        "rationale": "2-3 sentences explaining WHY.",
        "impact": "What improvement to expect",
        "effort": "low|medium|high"
      }},
      "secondary_actions": [
        {{
          "title": "Supporting action 1",
          "description": "1-2 sentences"
        }}
      ],
      "monitoring": {{
        "key_metrics": ["metric 1", "metric 2"],
        "check_frequency": "daily|weekly|monthly",
        "success_indicator": "What success looks like"
      }}
    }},
    
    "metadata": {{
      "theme": "growth|decline|risk|opportunity|exploration|warning",
      "tone": "optimistic|concerned|neutral|urgent",
      "confidence_score": 0.0-1.0,
      "reading_time_minutes": 3
    }}
  }}
}}

== RULES ==

1. NO CHAPTERS OR SECTIONS - narrative flows naturally
2. STORY FLOW - findings connect with natural transitions
3. EVIDENCE - every claim supported by fact sheet
4. JARGON-FREE - no statistical terms like p-value, IQR, correlation. Translate everything.
5. BOLD KEY NUMBERS - use **double asterisks**
6. QUALITY OVER QUANTITY - 3-7 findings based on what fact sheet provides
7. HONESTY - if data is good, say so. If bad, be direct.
8. JSON ONLY - return only valid JSON
9. WRITE FOR A BUSY EXECUTIVE - 3 minutes to read. Clear, direct, compelling.
"""


def get_story_theme_detection_prompt(
    current_finding: Dict[str, Any], next_finding: Dict[str, Any]
) -> str:
    """Generate a natural transition between two story findings."""
    return f"""You are a data storyteller writing smooth transitions between story points.

CURRENT FINDING:
- Title: {current_finding.get("title", "N/A")}
- Summary: {current_finding.get("narrative", "N/A")[:200]}...

NEXT FINDING:
- Title: {next_finding.get("title", "N/A")}
- Summary: {next_finding.get("narrative", "N/A")[:200]}...

Generate a 1-2 sentence transition that:
1. Acknowledges what we just learned
2. Sets up what comes next
3. Creates curiosity or tension
4. Flows naturally into the next finding

Return ONLY the transition text as a JSON object:
{{"transition": "your transition text here"}}
"""


def get_story_resolution_prompt(
    story_findings: List[Dict], complications: List[Dict], primary_metrics: Dict
) -> str:
    """Generate the resolution/conclusion of a story."""
    return f"""You are a strategic advisor writing action-oriented conclusions to data stories.

STORY FINDINGS:
{chr(10).join([f"- {f.get('title', 'N/A')}: {f.get('narrative', 'N/A')[:100]}..." for f in story_findings[:5]])}

COMPLICATIONS/RISKS:
{chr(10).join([f"- {c.get('title', 'N/A')}" for c in complications]) if complications else "- No major risks identified"}

KEY METRICS FROM DATA:
{chr(10).join([f"- {k}: {v}" for k, v in primary_metrics.items()])}

Write the resolution section of this story:
1. Summarize key takeaway in 2-3 sentences
2. Explain the one most important action to take
3. List 1-2 secondary actions
4. Define what metrics to monitor
5. End with forward-looking statement

Return ONLY valid JSON:
{{
  "story_conclusion": "...",
  "primary_action": {{"title": "...", "rationale": "...", "impact": "..."}},
  "secondary_actions": [{{"title": "...", "description": "..."}}],
  "monitoring": {{"key_metrics": [...], "check_frequency": "...", "success_indicator": "..."}}
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK TEMPLATES
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
# PIPELINE CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

PIPELINE_CONFIG = {
    "stage_1": {
        "model": "deepseek/deepseek-chat-v3-5",
        "temperature": 0.1,
        "max_tokens": 3000,
        "purpose": "Raw computation and pattern extraction",
    },
    "stage_2": {
        "model": "deepseek/deepseek-chat-v3-5",
        "temperature": 0.1,
        "max_tokens": 2000,
        "purpose": "Insight prioritization and analyst curation",
    },
    "stage_3": {
        "model": "qwen/qwen-2.5-72b-instruct",
        "temperature": 0.3,
        "max_tokens": 3000,
        "purpose": "Enterprise plain-English narration",
    },
    "theme_detection": {
        "model": "deepseek/deepseek-chat-v3-5",
        "temperature": 0.1,
        "max_tokens": 500,
        "purpose": "Quick theme detection pre-narration",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# QUALITY VALIDATION
# ─────────────────────────────────────────────────────────────────────────────


def validate_narration_quality(narration_output: dict, domain: str) -> dict:
    """
    Validates the Stage 3 output for quality before sending to UI.
    """
    issues = []
    report_text = str(narration_output)
    banned_words = JARGON_BAN.get(domain.lower(), JARGON_BAN["finance"])

    found_jargon = [
        word for word in banned_words if word.lower() in report_text.lower()
    ]
    if found_jargon:
        issues.append(f"Banned jargon found: {', '.join(found_jargon)}")

    self_check = narration_output.get("self_check", {})
    quality_score = self_check.get("quality_score", 0)
    if quality_score < 8:
        issues.append(f"Model self-rated quality too low: {quality_score}/10")

    report = narration_output.get("story", narration_output.get("report", {}))
    action_plan = report.get("action_plan", {})
    primary_action = action_plan.get("primary_action", {})
    if not primary_action.get("what"):
        issues.append("Missing primary action — report must end with clear next step")

    opening = report.get("opening_story", "")
    if len(opening) < 50:
        issues.append("Opening story too short — needs more substance")

    findings = report.get("findings", [])
    if len(findings) == 0:
        issues.append("No findings — report has no substance")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "quality_score": quality_score,
        "jargon_found": found_jargon,
    }
