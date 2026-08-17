"""
chat — Chat Synthesis Prompt Builder
======================================

Builds strongly structured chat response prompts with:
  - BLUF (answer first)
  - Jargon ban with plain English replacements
  - Quality gate (no LLM call — rule-based)
  - Response normalizer (post-processing)

Consolidates patterns from:
  - services/chat/synthesis.py (original source)
  - agents/chat/chat_agent.py (had a duplicate)
  - ai_service.py: _normalize_response_style(), _humanize_chat_text()
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from prompts._identity import ARCHETYPE_INSTRUCTIONS

logger = logging.getLogger(__name__)


# =============================================================================
# JARGON REPLACEMENTS
# =============================================================================

_CHAT_JARGON_REPLACEMENTS: Dict[str, str] = {
    "correlation coefficient": "strength of link",
    "negative correlation": "inverse relationship",
    "positive correlation": "direct relationship",
    "correlation": "link between",
    "correlates": "is linked to",
    "operational driver": "key factor",
    "causal": "cause-and-effect",
    "skewed": "lopsided",
    "skew": "lopsided",
    "volatility": "ups and downs",
    "volatile": "unstable",
    "anomaly": "unusual value",
    "anomalies": "unusual values",
    "outlier": "extreme value",
    "outliers": "extreme values",
    "distribution": "spread",
    "median": "middle value",
    "standard deviation": "typical spread from the average",
    "variance": "spread",
    "deviation": "difference",
    "coefficient": "factor",
    "percentile": "percentage point",
    "quartile": "quarter",
    "r-squared": "how well the model fits",
    "r-value": "strength of link",
    "p-value": "statistical significance",
    "regression": "trend line",
    "statistically significant": "a meaningful pattern (not random chance)",
    "null hypothesis": "the assumption that nothing changed",
    "confidence interval": "range of likely values",
    "multicollinearity": "overlapping factors",
    "heteroscedasticity": "uneven spread of data",
    "autocorrelation": "pattern repeating over time",
}

_BANNED_JARGON: frozenset = frozenset({
    "correlation", "correlated", "correlates",
    "outlier", "outliers",
    "distribution",
    "variance",
    "standard deviation", "std dev", "std.",
    "percentile", "quartile", "interquartile", "iqr",
    "p-value", "p value", "p < 0.05",
    "statistically significant", "statistical significance",
    "coefficient", "coefficients",
    "regression", "regressed",
    "anomaly", "anomalies",
    "skewness", "skewed", "skew",
    "heteroscedasticity", "multicollinearity",
    "null hypothesis", "alternative hypothesis",
    "r-squared", "r squared", "r²", "r-value", "r value",
    "kurtosis",
})

_GENERIC_PATTERNS: List[str] = [
    "it is worth noting",
    "it should be noted",
    "as evidenced by",
    "from a statistical standpoint",
    "exhibits",
    "demonstrates",
    "indicates",
    "presents",
    "manifests",
    "there is a correlation",
    "the data reveals",
    "the data suggests",
    "interestingly",
    "importantly,",
    "upon reviewing",
    "after analyzing",
    "based on the data",
    "according to the analysis",
    "i have analyzed",
    "i found that",
    "let me explain",
]

_BLUF_VIOLATIONS: List[str] = [
    "based on the", "the analysis shows", "i found that", "i see that",
    "i have analyzed", "after analyzing", "upon reviewing",
    "according to", "let me explain", "the data reveals",
    "the data suggests", "looking at the",
]

_HEDGING_PATTERNS: List[str] = [
    "i think", "i believe",
    "probably", "perhaps", "maybe",
    "might be", "could be", "could indicate",
    "appears to", "seems to", "would seem",
    "it is possible that", "it may be that",
    "my analysis suggests", "what i'm seeing is",
]


# =============================================================================
# PROMPT BUILDER
# =============================================================================


def build_synthesis_prompt(
    query: str,
    snippets: List[str],
    archetype: str = "analyst",
    conversation_context: Optional[str] = None,
    comparison_resolution: Optional[Dict[str, Any]] = None,
) -> str:
    """Build strongly structured synthesis prompt with BLUF, jargon ban, and self-check.

    Args:
        query: The user's question
        snippets: Data findings from the agent
        archetype: User archetype (explorer | analyst | expert)
        conversation_context: Optional previous messages for context continuity
        comparison_resolution: Optional dict from the comparison resolver — when
            the user EXPLICITLY named a comparison ("vs last year"), the LLM must
            explain against THAT baseline, not substitute another.
    """
    snippets_text = "\n".join(snippets) if snippets else "No findings available."
    archetype_instruction = ARCHETYPE_INSTRUCTIONS.get(archetype, "")

    conversation_block = (
        f"\n## Conversation History (for context — don't repeat these)\n{conversation_context}\n"
        if conversation_context
        else ""
    )

    comparison_block = ""
    if comparison_resolution and comparison_resolution.get("source") == "explicit":
        label = comparison_resolution.get("label") or "the stated comparison"
        comparison_block = (
            "\n## Verified Comparison Baseline\n"
            f"The user's question explicitly asks to compare against: {label}.\n"
            "Ground your explanation in THIS baseline and state the delta against it "
            "explicitly (e.g. \"down 11% vs previous month\"). Do not substitute "
            "a different comparison period.\n"
        )

    return f"""You are a data analyst who explains numbers in clear, direct language.
Your audience is a business user who needs to understand what the data says and what to do about it.

## User's Question
{query}
{conversation_block}{comparison_block}
## Data Findings
{snippets_text}

## Response Rules — Follow Strictly

### 1. BLUF (Bottom Line Up Front) — Answer First
Your very first sentence must be the single most important finding with its number.
Never start with any of these:
- "Based on..."
- "The analysis shows..."
- "I found that..." or "I see that..."
- "According to..."
- "Looking at..."
- "After analyzing..."
- "Upon reviewing..."
- "The data reveals/suggests..."
- "Let me explain..."
Lead with the number and what it means. First 5 words must contain a number or the answer.

### 2. Structure (3 paragraphs max)
- Paragraph 1: The headline answer (BLUF) — 1-2 sentences with the key number
- Paragraph 2: Supporting detail — 1-2 sentences with specific numbers
- Paragraph 3: What to do next — 1 sentence

### 3. Language Rules — ZERO TOLERANCE
Never use these words. Replace them with plain English:
- correlation / correlated → "connection" or "linked"
- outlier / anomaly → "unusual value" or "unusual finding"
- distribution → "spread" or "range"
- variance / standard deviation → "typical range" or "how much values vary"
- percentile / quartile → "top/bottom X%" or "group"
- median → "middle value" or "typical"
- p-value / statistically significant → "a real pattern" or "not random"
- coefficient / regression → "factor" or "trend"
- skew / skewed → "uneven" or "lopsided"
- exhibit / demonstrate / indicate → use direct language instead

### 4. Numbers & Data Citation
- Bold key numbers with **double asterisks** — the first number in the response MUST be bolded
- Every number needs context: "**18%** — nearly 1 in 5" not just "18%"
- Include at least 2 specific numbers from the findings
- When making a claim, mention which column or field the data comes from:
  "Your **Northeast** region delivered **$2.1M** in revenue — **34%** of total"
  NOT: "A region delivered significant revenue"

### 5. Confidence & Honesty
- State findings as facts when the data supports them. NEVER hedge with:
  - "I think..." / "I believe..." / "It seems..."
  - "Probably" / "Perhaps" / "Maybe" / "Might be"
  - "Appears to" / "Could indicate" / "Seems to suggest"
- If the data is genuinely uncertain or sparse, say so directly:
  "The data on this point is limited, but within what we have..."
- If the data is conclusive, state it confidently: "Revenue grew **22%**" not "Revenue appears to have grown around 22%"

### 6. Self-Check — Verify Before Returning
- [ ] Does the first sentence answer the question directly with a number?
- [ ] Are the first 5 words free of generic openers?
- [ ] Is the FIRST number in the response bolded with **asterisks**?
- [ ] Are there at least 2 specific numbers in **bold**?
- [ ] Is every banned word replaced with plain English?
- [ ] Does it end with a clear next step or conclusion?
- [ ] Does it avoid ALL generic phrases like "the data reveals"?
- [ ] Are claims attributed to specific columns/fields?
- [ ] Are there NO hedging phrases ("I think", "probably", "seems")?

### 7. Scope Boundary — DO NOT Cross
- ONLY answer questions about the user's data (columns, metrics, trends, charts)
- If the question is about the real world, news, people, time, weather, or general knowledge → DO NOT answer
- Instead respond: "I can only answer questions about your data. Try asking about a specific metric or trend."
- Never make up data that isn't in the findings above

{archetype_instruction}

Write your response below:"""


# =============================================================================
# QUALITY GATE
# =============================================================================


def check_response_quality(response: str) -> Dict[str, Any]:
    """Run rule-based quality checks on generated response. No LLM call."""
    issues: List[str] = []
    response_lower = response.lower()

    # 1. Check for banned jargon
    found_jargon = [w for w in _BANNED_JARGON if w.lower() in response_lower]
    if found_jargon:
        issues.append(f"Banned jargon: {', '.join(sorted(set(found_jargon))[:4])}")

    # 2. Check for generic AI phrases
    found_generic = [p for p in _GENERIC_PATTERNS if p in response_lower]
    if found_generic:
        issues.append(f"Generic phrasing: {', '.join(sorted(set(found_generic))[:3])}")

    # 3. Check for numbers
    numbers = re.findall(r"\d+[,.]?\d*", response)
    if len(numbers) < 2:
        issues.append(f"Only {len(numbers)} number(s) found (need at least 2)")

    # 4. Check minimum length
    word_count = len(response.split())
    if word_count < 15:
        issues.append(f"Too short ({word_count} words, need at least 15)")

    # 5. Check for BLUF violation (expanded to first 100 chars)
    first_100 = response_lower[:100]
    for v in _BLUF_VIOLATIONS:
        if first_100.startswith(v):
            issues.append("BLUF violation: response starts with a generic opener")
            break

    # 6. Check for bolded numbers (at least 1 should be bolded)
    # Match any bolded segment containing a digit — handles **18%**, **$2.1M**, **34% of total**, etc.
    bolded_numbers = re.findall(r"\*\*[^*]*\d[^*]*\*\*", response)
    if len(bolded_numbers) < 1:
        issues.append("No bolded numbers found — key numbers must be in **double asterisks**")

    # 7. Check for hedging / weakening language
    found_hedging = [p for p in _HEDGING_PATTERNS if p in response_lower]
    if found_hedging:
        issues.append(f"Hedging language: {', '.join(sorted(set(found_hedging))[:3])}")

    # 8. Check that first token isn't a filler word
    first_word_raw = response_lower.split()[0] if response_lower.split() else ""
    first_word_stripped = first_word_raw.strip(",.:;!?-")
    FILLER_WORDS = {"well", "so", "okay", "first", "now", "regarding"}
    if first_word_stripped in FILLER_WORDS:
        issues.append(f"Response starts with filler word '{first_word_raw}' — lead with the answer")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "jargon_found": found_jargon,
        "number_count": len(numbers),
        "bolded_numbers": len(bolded_numbers),
        "hedging_found": found_hedging,
    }


# =============================================================================
# RESPONSE NORMALIZER
# =============================================================================


def normalize_response_style(text: str) -> str:
    """Apply lightweight style guardrails to narrative responses."""
    if not text:
        return text

    cleaned = text.strip()

    # Strip leading generic openers
    cleaned = re.sub(
        r"(?i)^\s*(based on the (?:data|results|analysis|information)"
        r"|according to (?:the )?(?:data|results)"
        r"|the (?:data|results) show(?:s)?"
        r"|looking at the (?:data|results))[\s,:-]*",
        "",
        cleaned,
    )
    cleaned = re.sub(r"(?i)^that\s+", "", cleaned)

    # Soften overconfident language
    rewrites = [
        (r"(?i)\bwithout (?:a )?doubt\b", "based on available data"),
        (r"(?i)\bdefinitely\b", "likely"),
        (r"(?i)\bcertainly\b", "likely"),
        (r"(?i)\babsolutely\b", "strongly"),
        (r"(?i)\balways\b", "consistently"),
        (r"(?i)\bnever fail\b", "rarely fail"),
        (r"(?i)\bcannot compute\b", "cannot reliably estimate"),
        (r"(?i)\bcannot determine\b", "cannot reliably infer"),
        (r"(?i)\bunable to (answer|provide|determine)\b", "not supported well enough to \1"),
    ]
    for pattern, replacement in rewrites:
        cleaned = re.sub(pattern, replacement, cleaned)

    # Replace --- divider with blank line
    cleaned = re.sub(r"\n\s*---\s*\n", "\n\n", cleaned)

    return cleaned


def humanize_text(text: str) -> str:
    """Strip technical jargon from chat responses for non-technical users."""
    if not text:
        return text
    result = text
    for jargon, plain in _CHAT_JARGON_REPLACEMENTS.items():
        result = re.sub(rf"\b{re.escape(jargon)}\b", plain, result, flags=re.IGNORECASE)
    return result


__all__ = [
    "ARCHETYPE_INSTRUCTIONS",
    "build_synthesis_prompt",
    "check_response_quality",
    "normalize_response_style",
    "humanize_text",
]
