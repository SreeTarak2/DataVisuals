"""
Query Understanding & Rewrite Layer
------------------------------------
Evolved from: meaning-preserving rewriter (v1)
Now handles:  intent detection + query enrichment + clarification offer (v2)

Three failure modes this layer fixes:
  1. UNDERSPECIFIED — "show me something interesting" → enriched to specific ask
  2. MISSPECIFIED   — user asks for the wrong thing to answer their real question
  3. VOCABULARY GAP — "average price" when they need median (skewed column)

Pipeline:
  raw query
    → detect_query_intent()        [Fast model — cheap, fast, structured JSON]
    → enrich_query()              [extends REWRITE_SYSTEM_PROMPT logic]
    → QueryUnderstanding result    [carries enriched_query + what_i_understood]
    → caller decides: show clarification card or proceed silently

Internal use only — NEVER shown raw to end-users.
The what_i_understood field IS shown to users (plain English confirmation).

Backward compatibility:
  rewrite_query() still exists and works exactly as before.
  New entry point: understand_query() — use this for conversational + dashboard paths.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from services.llm_router import llm_router
from core.prompt_templates import REWRITE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class QueryUnderstanding:
    """
    Full output of the query understanding pipeline.
    Callers use enriched_query for downstream LLM calls.
    what_i_understood is shown in the UI clarification card.
    """

    original_query: str
    enriched_query: str
    what_i_understood: str
    failure_mode: Optional[str] = None
    needs_clarification: bool = False
    archetype: str = "analyst"
    decision_at_stake: str = ""
    was_enriched: bool = False


# =============================================================================
# VOCABULARY FINGERPRINTS  (rule-based pre-classifier — no LLM call needed)
# =============================================================================

_EXPERT_TERMS = {
    "correlation",
    "regression",
    "quartile",
    "percentile",
    "distribution",
    "p-value",
    "r-value",
    "coefficient",
    "variance",
    "std",
    "standard deviation",
    "cohort",
    "segmentation",
    "yoy",
    "mom",
    "cagr",
    "ltv",
    "churn",
    "multivariate",
    "hypothesis",
    "statistical",
    "significance",
    "outlier",
    "skew",
    "kurtosis",
    "median",
    "interquartile",
    "delta",
    "benchmark",
    "autocorrelation",
    "heteroscedasticity",
    "time series",
    "stationarity",
}

_ANALYST_TERMS = {
    "average",
    "trend",
    "breakdown",
    "compare",
    "group by",
    "filter",
    "top",
    "bottom",
    "highest",
    "lowest",
    "by region",
    "by category",
    "over time",
    "monthly",
    "weekly",
    "segment",
    "split",
    "ratio",
    "rank",
    "sort",
    "aggregate",
    "sum",
    "count",
    "total",
}

_CASUAL_SIGNALS = {
    "show me",
    "what is",
    "how many",
    "which",
    "hey",
    "yo",
    "quick",
    "just",
    "can you",
    "tell me",
    "give me",
    "i want",
    "what's",
    "whats",
    "wanna",
    "wana",
    "pls",
    "please",
    "thanks",
}

_VAGUE_PATTERNS = [
    r"^show me (something|anything)",
    r"^(what('s| is) (interesting|important|useful|cool))",
    r"^(analyse|analyze|analyse|look at) (my |the |this )?(data|dataset)?\.?$",
    r"^(give me|show me) (some |a few )?(insight|insights|finding|findings)\.?$",
    r"^(what (can|should) (i|we) (know|look at|check))\.?$",
    r"^(explore|summarize|summarise) (the |my |this )?(data|dataset)?\.?$",
    r"^(help|help me)\.?$",
    r"^(anything interesting)\.?$",
]
_COMPILED_VAGUE = [re.compile(p, re.IGNORECASE) for p in _VAGUE_PATTERNS]

_SKEW_PRONE_COLUMNS = {
    "price",
    "revenue",
    "salary",
    "income",
    "cost",
    "spend",
    "spending",
    "mileage",
    "age",
    "distance",
    "value",
    "profit",
    "loss",
    "tax",
    "quantity",
    "order_value",
    "transaction",
    "amount",
}


def _fast_archetype(query: str) -> str:
    """Rule-based archetype detection — runs in microseconds, no LLM call."""
    q = query.lower()
    words = q.split()
    word_count = len(words)

    expert_hits = sum(1 for t in _EXPERT_TERMS if t in q)
    analyst_hits = sum(1 for t in _ANALYST_TERMS if t in q)
    has_snake_case = bool(re.search(r"\b[a-z]+_[a-z]+\b", q))
    is_diagnostic = q.startswith(
        ("why", "does", "how does", "what drives", "which factors", "is there a", "do ")
    )

    if expert_hits >= 2 or (word_count > 15 and is_diagnostic):
        return "expert"
    if (
        analyst_hits >= 2
        or has_snake_case
        or (word_count > 10 and not any(q.startswith(s) for s in _CASUAL_SIGNALS))
    ):
        return "analyst"
    return "explorer"


def _is_vague(query: str) -> bool:
    """Check if query matches known underspecified patterns."""
    q = query.strip()
    if len(q.split()) <= 4:
        if not any(
            col_hint in q.lower() for col_hint in _ANALYST_TERMS | _EXPERT_TERMS
        ):
            return True
    return any(p.search(q) for p in _COMPILED_VAGUE)


def _has_vocabulary_gap(query: str, available_columns: Optional[list] = None) -> bool:
    """Detect if user said 'average' for a likely skew-prone column."""
    q = query.lower()
    if "average" not in q and "mean" not in q:
        return False

    cols_to_check = available_columns or list(_SKEW_PRONE_COLUMNS)
    return any(
        col.lower() in q for col in cols_to_check if col.lower() in _SKEW_PRONE_COLUMNS
    )


# =============================================================================
# PROMPT BUILDERS
# =============================================================================


def _build_intent_detection_prompt(
    query: str,
    dataset_context: str,
    available_columns: list,
    archetype: str,
) -> str:
    cols_preview = (
        ", ".join(available_columns[:25]) if available_columns else "not provided"
    )

    return f"""You are the Intent Engine for DataSage AI — a data analytics assistant.
A user has submitted a query. Your job: understand the REAL business question
behind their words, detect what is missing or wrong, and produce an enriched
version that will get them a genuinely useful answer.

USER QUERY: "{query}"
USER ARCHETYPE: {archetype}  (explorer=non-technical | analyst=comfortable with data | expert=statistical)
AVAILABLE COLUMNS: {cols_preview}
DATASET CONTEXT (summary):
{dataset_context[:600] if dataset_context else "Not provided"}

══════════════════════════════════════════════════════════
FAILURE MODE DETECTION — check all three
══════════════════════════════════════════════════════════

UNDERSPECIFIED: Query is too vague to produce a specific, useful answer.
  Examples: "show me something interesting", "analyse my data", "what's important"
  Fix: Replace with the single most commercially valuable question this dataset can answer.

MISSPECIFIED: What they asked won't actually answer their real question.
  Example: User wants to know which product to stock more of.
  They asked: "show me total sales by product" (correct data, wrong framing —
  they need sell-through rate or margin per unit, not raw sales volume).
  Fix: Reframe to answer their real question, not their literal words.

VOCABULARY_GAP: They used an imprecise term for a skew-prone column.
  Example: "average price" when the price column is right-skewed —
  mean will overstate the typical value; they almost certainly want median.
  Fix: Substitute the correct statistical term and explain in what_i_understood.

══════════════════════════════════════════════════════════
ENRICHMENT RULES — apply to enriched_query
══════════════════════════════════════════════════════════

A good analyst automatically adds context a non-technical user omits:
  ✓ Specify aggregation type (sum, median, count) — not just "show me X"
  ✓ Add sort order for rankings ("descending by revenue")
  ✓ Add a percentage/share alongside absolute values for context
  ✓ Specify top N for long lists ("top 10 products")
  ✓ Add comparison dimension if implied ("vs last period", "vs average")
  ✓ Fix mean→median for price, revenue, salary, mileage, tax columns

Explorer archetype: enrich heavily (they don't know what to ask for)
Analyst archetype:  enrich moderately (fill gaps, fix vocabulary)
Expert archetype:   enrich minimally (they usually specify well — trust their words)

══════════════════════════════════════════════════════════
what_i_understood WRITING RULES
══════════════════════════════════════════════════════════

This sentence is shown to the user as a confirmation card before answering.
  ✓ Plain English — no column names, no jargon
  ✓ States WHAT you will show AND WHY it answers their real question
  ✓ If you fixed a vocabulary gap: mention it naturally
  ✓ Maximum 2 sentences
  ✗ NEVER start with "I" or "DataSage"
  ✗ NEVER be robotic ("Processing your request to display...")

  GOOD: "Showing median price by fuel type — median is more reliable than average
         here because a few expensive outliers would skew the average upward."
  GOOD: "Ranking all products by revenue share (not just total sales) so you can
         see which ones actually drive the business vs which just have high volume."
  BAD:  "I will now show you the data you requested."

══════════════════════════════════════════════════════════
OUTPUT FORMAT — return ONLY valid JSON
══════════════════════════════════════════════════════════

{{
  "surface_request": "What they literally asked for in plain English",
  "real_question": "The actual business question behind their words",
  "decision_at_stake": "What decision a good answer would help them make",
  "failure_mode": "underspecified | misspecified | vocabulary_gap | none",
  "needs_clarification": true if failure_mode is not "none" and not "vocabulary_gap",
  "enriched_query": "Fully specified query. References exact column names if available.
                     Adds aggregation type, sort order, N limit, comparison context.
                     For Explorer: rewrite substantially. For Expert: minimal changes.",
  "what_i_understood": "1-2 plain English sentences shown to user. States what will
                        be shown and why it answers their real question.",
  "archetype_confirmed": "explorer | analyst | expert"
}}"""


def _build_enrichment_only_prompt(query: str, dataset_context: str) -> str:
    """Lightweight enrichment for well-specified queries."""
    return f"""{REWRITE_SYSTEM_PROMPT}

ENRICHMENT EXTENSION (apply after meaning-preserving rewrite):
Beyond clarity, a good analyst adds what the user implicitly needs:
  - If ranking: add "in descending order" and "top 10" if N not specified
  - If comparing groups: add "include percentage share alongside absolute value"
  - If asking about price/revenue/salary: use median not mean (skew-prone columns)
  - If time-related: specify the period explicitly if inferable from context
  - If asking about relationships: specify both columns explicitly

DATASET CONTEXT (for column name reference):
{dataset_context[:400] if dataset_context else "Not provided"}

User Query: {query}"""


# =============================================================================
# EXISTING _post_validate  (unchanged — backward compatible)
# =============================================================================


def _post_validate(original: str, rewritten: str) -> str:
    """Validate rewritten query. If empty, too short, or malformed, fall back to original."""
    if not rewritten or rewritten.strip() == "":
        logger.info("Rewrite validation: empty result, using original")
        return original

    rewritten_clean = rewritten.strip()
    original_clean = original.strip()

    if len(rewritten_clean.split()) <= max(3, len(original_clean.split()) // 4):
        logger.warning(
            f"Rewrite validation: too short "
            f"({len(rewritten_clean.split())} words vs {len(original_clean.split())}), "
            f"using original"
        )
        return original

    if rewritten_clean.lower() == original_clean.lower():
        logger.debug("Rewrite validation: identical to original, no improvement")
        return original

    answer_indicators = [
        "i'm here to help",
        "i am here to help",
        "i don't have",
        "i do not have",
        "i can help",
        "let me help",
        "sure!",
        "of course!",
        "absolutely!",
        "here's",
        "here is",
        "based on the",
        "looking at the",
        "it seems",
        "it appears",
        "you might want to",
        "you may want to",
        "to get started",
        "to begin",
        "unfortunately",
        "however,",
        "great question",
        "good question",
        "the answer is",
        "answer:",
        "i found that",
        "i can see that",
        "after analyzing",
        "upon review",
    ]
    rewritten_lower = rewritten_clean.lower()
    for indicator in answer_indicators:
        if rewritten_lower.startswith(indicator) or f"\n{indicator}" in rewritten_lower:
            logger.warning(
                f"Rewrite validation: detected answer pattern '{indicator}', using original"
            )
            return original

    if len(rewritten_clean.split()) > len(original_clean.split()) * 3:
        logger.warning(
            f"Rewrite validation: too long "
            f"({len(rewritten_clean.split())} vs {len(original_clean.split())}), "
            f"using original"
        )
        return original

    logger.info(
        f"Rewrite validation: SUCCESS - "
        f"'{original_clean[:30]}...' -> '{rewritten_clean[:30]}...'"
    )
    return rewritten_clean


# =============================================================================
# CORE PIPELINE FUNCTIONS
# =============================================================================


async def understand_query(
    user_query: str,
    dataset_context: str = "",
    available_columns: Optional[list] = None,
    force_full_intent: bool = False,
) -> QueryUnderstanding:
    """
    Full query understanding pipeline — NEW entry point.

    Use this instead of rewrite_query() for:
      - Conversational chat
      - Dashboard generation
      - Any path where query quality directly affects insight quality

    Args:
        user_query        : Raw user input
        dataset_context   : Formatted context string
        available_columns : List of actual column names
        force_full_intent : Always run full intent call (skip fast-path)

    Returns:
        QueryUnderstanding — use .enriched_query for downstream LLM calls,
                             .what_i_understood for UI clarification card,
                             .needs_clarification to decide whether to show card.
    """
    if not user_query or not user_query.strip():
        return QueryUnderstanding(
            original_query=user_query,
            enriched_query=user_query,
            what_i_understood="",
            needs_clarification=False,
        )

    query = user_query.strip()
    cols = available_columns or []

    archetype = _fast_archetype(query)
    is_vague = _is_vague(query)
    vocab_gap = _has_vocabulary_gap(query, cols)
    failure_mode = (
        "underspecified" if is_vague else "vocabulary_gap" if vocab_gap else None
    )

    use_fast_path = (
        not force_full_intent
        and not is_vague
        and not vocab_gap
        and archetype in ("analyst", "expert")
    )

    if use_fast_path:
        logger.debug(f"understand_query: fast path — archetype={archetype}")
        enriched = await _run_enrichment_only(query, dataset_context)
        return QueryUnderstanding(
            original_query=query,
            enriched_query=enriched,
            what_i_understood=_generate_simple_confirmation(query, enriched),
            failure_mode=None,
            needs_clarification=False,
            archetype=archetype,
            was_enriched=(enriched.lower() != query.lower()),
        )

    logger.debug(
        f"understand_query: full intent path — archetype={archetype}, "
        f"vague={is_vague}, vocab_gap={vocab_gap}"
    )

    intent_prompt = _build_intent_detection_prompt(
        query, dataset_context, cols, archetype
    )

    try:
        import json

        raw = await llm_router.call(
            prompt=intent_prompt,
            model_role="intent_engine",
            expect_json=True,
        )

        if isinstance(raw, str):
            raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            intent = json.loads(raw)
        elif isinstance(raw, dict):
            intent = raw
        else:
            raise ValueError(f"Unexpected intent response type: {type(raw)}")

    except Exception as e:
        logger.error(f"Intent detection failed: {e} — falling back to enrichment only")
        enriched = await _run_enrichment_only(query, dataset_context)
        return QueryUnderstanding(
            original_query=query,
            enriched_query=enriched,
            what_i_understood=_generate_simple_confirmation(query, enriched),
            failure_mode=failure_mode,
            needs_clarification=is_vague,
            archetype=archetype,
            was_enriched=(enriched.lower() != query.lower()),
        )

    enriched_query = intent.get("enriched_query", query)
    what_i_understood = intent.get("what_i_understood", "")
    detected_failure = intent.get("failure_mode", failure_mode or "none")
    needs_clarification = intent.get("needs_clarification", is_vague)
    archetype_confirmed = intent.get("archetype_confirmed", archetype)
    decision_at_stake = intent.get("decision_at_stake", "")

    enriched_query = _post_validate(query, enriched_query)

    if not what_i_understood.strip():
        what_i_understood = _generate_simple_confirmation(query, enriched_query)

    logger.info(
        f"understand_query: "
        f"archetype={archetype_confirmed}, "
        f"failure={detected_failure}, "
        f"clarification={needs_clarification}, "
        f"enriched='{enriched_query[:50]}...'"
    )

    return QueryUnderstanding(
        original_query=query,
        enriched_query=enriched_query,
        what_i_understood=what_i_understood,
        failure_mode=detected_failure if detected_failure != "none" else None,
        needs_clarification=bool(needs_clarification),
        archetype=archetype_confirmed,
        decision_at_stake=decision_at_stake,
        was_enriched=(enriched_query.lower() != query.lower()),
    )


async def _run_enrichment_only(query: str, dataset_context: str) -> str:
    """Lightweight enrichment for clear queries."""
    prompt = _build_enrichment_only_prompt(query, dataset_context)
    try:
        result = await llm_router.call(
            prompt=prompt,
            model_role="rewrite_engine",
            expect_json=False,
        )
        if isinstance(result, dict):
            result = (
                result.get("response")
                or result.get("text")
                or result.get("content", "")
            )
        return _post_validate(query, str(result).strip()) if result else query
    except Exception as e:
        logger.warning(f"Enrichment only failed: {e} — using original")
        return query


def _generate_simple_confirmation(original: str, enriched: str) -> str:
    """Fallback what_i_understood when LLM doesn't return one."""
    if enriched.lower() == original.lower():
        return f"Answering: {original}"
    return f"Here's what I'll look at: {enriched[:120]}{'...' if len(enriched) > 120 else ''}"


# =============================================================================
# BACKWARD-COMPATIBLE ENTRY POINT
# =============================================================================


async def rewrite_query(
    user_query: str,
    dataset_context: Optional[str] = None,
) -> str:
    """
    Backward-compatible rewrite entry point.
    Existing callers (RAG/FAISS, chart insight generation) continue to work.
    """
    if not user_query or not user_query.strip():
        return user_query

    logger.debug(f"rewrite_query (compat): '{user_query[:50]}...'")

    understanding = await understand_query(
        user_query=user_query,
        dataset_context=dataset_context or "",
        available_columns=None,
        force_full_intent=False,
    )
    return understanding.enriched_query


# =============================================================================
# ARCHETYPE INSTRUCTION BLOCKS
# =============================================================================

ARCHETYPE_INSTRUCTIONS = {
    "explorer": """
RESPONSE CALIBRATION — EXPLORER MODE:
This user is non-technical. Calibrate every element of your response:
- VOCABULARY: Zero jargon. Translate every column name to plain English on first use.
  NEVER use: correlation, distribution, quartile, median, skew, outlier, p-value.
  Translate → "relationship between X and Y", "spread of values", "typical value".
- LENGTH: Shorter is better. 80–150 words. One clear insight, not five.
- NUMBERS: Bold the 1–2 numbers that matter most. Don't list every statistic.
- CHART: Always recommend exactly one chart. Title describes the finding, not axes.
  "Your Best-Selling Region" not "Revenue by Region".
- FOLLOW-UPS: Sound like natural curiosity, not analytical tasks.
  BAD: "Analyse the correlation between price and mileage"
  GOOD: "Which cars hold their value best as they age?"
- TONE: Warm, direct, like a trusted colleague. Never condescending.
  Never use "simply" or "just". Never explain what a bar chart is.
""",
    "analyst": """
RESPONSE CALIBRATION — ANALYST MODE:
This user understands data but isn't a statistician. Calibrate:
- VOCABULARY: Data terms are fine. Translate statistical jargon once on first use.
  "Median (the middle value — more reliable than average when a few outliers exist)."
- LENGTH: Standard. 150–250 words. Main finding + 2 supporting details.
- NUMBERS: Key comparisons with top 3–5 values in a table if comparing groups.
- METHODOLOGY: One brief sentence on how you got the number is appreciated.
  "Aggregated by sum across all transactions in the date range."
- FOLLOW-UPS: Diagnostic and specific — reference actual column names.
  "Which product category drives the Q4 spike — is it consistent year-over-year?"
- TONE: Peer-to-peer. Confident. Skip hand-holding but don't assume PhD-level.
""",
    "expert": """
RESPONSE CALIBRATION — EXPERT MODE:
This user is technically sophisticated. Calibrate:
- VOCABULARY: Full statistical vocabulary expected. No need to translate median,
  quartile, correlation, skew — use them precisely.
- LENGTH: Match query complexity. Dense questions deserve dense answers. Don't pad.
- NUMBERS: All relevant statistics. Include min/max/std where illuminating.
  Don't just give mean — give distribution shape and N if relevant.
- METHODOLOGY: Be explicit. State aggregation method, filters applied,
  how nulls were handled, sample size.
- CAVEATS: Surface data quality issues proactively. Don't hide skew or sparsity.
- FOLLOW-UPS: Push analytical depth. Suggest next steps they haven't considered.
- TONE: Direct. Precise. Peer-level. Skip narrative flourishes and coaching.
""",
}


__all__ = [
    "understand_query",
    "rewrite_query",
    "QueryUnderstanding",
    "ARCHETYPE_INSTRUCTIONS",
]
