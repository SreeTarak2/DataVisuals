"""
Agent 6 — Critic / QA
Two-stage validation:
  1. Deterministic Python pass — removes charts with non-existent columns (fast, free, catches 80%)
  2. LLM semantic pass — checks type mismatches, contradictions, missing charts

Uses mistral_small_32 — reliable structured JSON output.
"""

import logging
from agents.eda.context import AgentContext
from llm import llm_router

logger = logging.getLogger(__name__)

PROMPT = """You are a QA reviewer for data analysis. Check the analysis output for semantic errors.

DATASET: {name} — {rows:,} rows, {cols} columns
ALL COLUMNS ({col_count} total): {all_columns}

CHARTS TO VALIDATE (columns already verified to exist):
{charts}

KEY RELATIONSHIPS CLAIMED:
{relationships}

UNIVARIATE FLAGS:
{uni_flags}

Check for SEMANTIC issues only (column existence is already verified):
1. Chart type mismatch (e.g. scatter on a categorical-only pair, pie on high-cardinality column)
2. Relationships that contradict each other
3. Too few charts for dataset complexity (< 2 charts for a complex dataset)
4. Aggregation mismatch (e.g. "sum" on a ratio/percentage column)

Respond with ONLY valid JSON:
{{
  "passed": true | false,
  "issues": ["specific issue description, empty list if none"],
  "fixed_charts": [],
  "confidence_score": 0.0-1.0
}}

If issues found and you can fix them, populate fixed_charts with corrected versions.
If no issues, return passed=true, issues=[], fixed_charts=[], confidence_score=0.95"""


def _hard_validate_charts(
    charts: list, ctx: AgentContext
) -> tuple[list, list]:
    """
    Deterministic pre-LLM validation.
    Removes any chart referencing a column that does not exist in the dataset.
    Returns (valid_charts, hard_issues).
    """
    valid_cols = ctx.valid_column_names()
    valid = []
    issues = []

    for ch in charts:
        bad = [
            ch.get(k)
            for k in ("x", "y", "color")
            if ch.get(k) and ch.get(k) not in valid_cols
        ]
        if bad:
            issues.append(
                f"Chart '{ch.get('title', '?')}' references unknown column(s): {bad} — removed"
            )
            logger.warning(f"[Critic] Hard-removed chart with unknown columns: {bad}")
        else:
            valid.append(ch)

    return valid, issues


async def run(ctx: AgentContext) -> AgentContext:
    # ── Stage 1: Deterministic validation ────────────────────────────────────
    ctx.chart_configs, hard_issues = _hard_validate_charts(ctx.chart_configs, ctx)
    if hard_issues:
        ctx.errors.extend(hard_issues)
        logger.info(f"[Critic] Hard validation removed {len(hard_issues)} invalid chart(s)")

    all_columns = [c["name"] for c in ctx.column_metadata]

    # Build chart lines for LLM (only valid charts remain)
    chart_lines = [
        f"  {i}. {ch.get('chart_type')} — x={ch.get('x')}, y={ch.get('y')}, "
        f"agg={ch.get('aggregation')}, title='{ch.get('title')}'"
        for i, ch in enumerate(ctx.chart_configs, 1)
    ]

    rel_lines = [
        f"  • {r.get('columns')} — {r.get('relationship', '')}"
        for r in ctx.bivariate_report.get("key_relationships", [])[:4]
    ]

    uni_flags = ctx.univariate_report.get("key_findings", [])
    uni_lines = [f"  {f['column']}: {f['finding']}" for f in uni_flags[:5]]

    # Pass all column names to LLM — truncate with a note so wide datasets aren't silently lost
    col_display = ", ".join(all_columns[:60])
    if len(all_columns) > 60:
        col_display += f" ... (+{len(all_columns) - 60} more)"

    # ── Stage 2: LLM semantic validation ─────────────────────────────────────
    prompt = PROMPT.format(
        name=ctx.dataset_name,
        rows=ctx.row_count,
        cols=ctx.column_count,
        col_count=len(all_columns),
        all_columns=col_display,
        charts="\n".join(chart_lines) or "  None generated",
        relationships="\n".join(rel_lines) or "  None",
        uni_flags="\n".join(uni_lines) or "  None",
    )

    try:
        result = await llm_router.call(
            prompt=prompt,
            model_role="validation",
            expect_json=True,
            temperature=0.1,
            max_tokens=1024,
        )

        if isinstance(result, dict):
            ctx.validation_result = result

            # Only replace charts if: LLM found issues AND provided actual fixes
            fixed = result.get("fixed_charts") or []
            issues_found = not result.get("passed", True)
            if issues_found and fixed:
                # Re-run hard validation on LLM-fixed charts too
                fixed_clean, _ = _hard_validate_charts(fixed, ctx)
                if fixed_clean:
                    ctx.chart_configs = fixed_clean
                    logger.info(f"[Critic] Replaced charts with {len(fixed_clean)} LLM-fixed version(s)")
        else:
            ctx.validation_result = {"passed": True, "issues": [], "confidence_score": 0.8}

    except Exception as e:
        logger.warning(f"[Critic] LLM failed: {e}")
        ctx.validation_result = {
            "passed": len(hard_issues) == 0,
            "issues": hard_issues,
            "confidence_score": 0.7,
        }

    # Merge hard issues into validation result for frontend visibility
    existing_issues = ctx.validation_result.get("issues", [])
    all_issues = hard_issues + [i for i in existing_issues if i not in hard_issues]
    ctx.validation_result["issues"] = all_issues
    if hard_issues:
        ctx.validation_result["passed"] = False

    passed = ctx.validation_result.get("passed", True)
    score = ctx.validation_result.get("confidence_score", 0.8)
    logger.info(
        f"[Critic] passed={passed} confidence={score} "
        f"hard_issues={len(hard_issues)} semantic_issues={len(existing_issues)}"
    )
    return ctx
