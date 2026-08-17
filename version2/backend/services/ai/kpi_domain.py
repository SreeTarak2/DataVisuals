"""
KPI Domain Detection
====================
LLM-first hybrid domain classification with pattern-matching fallback.
Extracted from intelligent_kpi_generator.py.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import polars as pl

from .kpi_types import ColumnProfile

logger = logging.getLogger(__name__)


def _compute_domain_scores(
    profiles: List[ColumnProfile],
) -> tuple[dict[str, float], Optional[str], float]:
    from services.kpi.patterns import COLUMN_PATTERNS
    from services.kpi.templates import ALL_TEMPLATES

    column_names = [p.name for p in profiles]
    detected_types: set = set()

    for col_name in column_names:
        col_lower = col_name.lower().replace("_", " ").replace("-", " ")
        for col_type, patterns in COLUMN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, col_lower, re.IGNORECASE):
                    detected_types.add(col_type)
                    break

    scores: dict[str, float] = {}
    for template_id, template in ALL_TEMPLATES.items():
        required_found = sum(1 for r in template.required_columns if r in detected_types)
        optional_found = sum(1 for o in template.optional_columns if o in detected_types)

        if required_found == len(template.required_columns):
            scores[template_id] = 50.0 + 10.0 * required_found + 5.0 * optional_found
        elif required_found > 0:
            scores[template_id] = 15.0 * required_found + 3.0 * optional_found

    if scores:
        best = max(scores, key=scores.get)
        return scores, best, scores[best]
    return {}, None, 0.0


def dtype_abbrev(dtype_str: str) -> str:
    if "Int" in dtype_str or "UInt" in dtype_str or "Float" in dtype_str:
        return "numeric"
    if "Date" in dtype_str or "Datetime" in dtype_str or "Duration" in dtype_str:
        return "datetime"
    if "Utf8" in dtype_str or "String" in dtype_str or "Categorical" in dtype_str:
        return "text"
    if "Bool" in dtype_str:
        return "boolean"
    return dtype_str[:12]


async def _llm_classify_domain(
    profiles: List[ColumnProfile],
    df: pl.DataFrame,
    business_rules: Optional[List[str]] = None,
) -> tuple[Optional[str], Optional[dict[str, str]]]:
    from services.kpi.templates import ALL_TEMPLATES

    # ── Build business rules block ──
    rules_block = ""
    if business_rules:
        rules_block = "\nBUSINESS CONTEXT (user-defined rules — follow these):\n"
        for i, rule in enumerate(business_rules[:5], 1):
            rules_block += f"  {i}. {rule}\n"
        rules_block += "\nThese business rules MUST influence domain selection and column mapping.\n"

    # ── Build rich column info with data stats ──
    col_lines = []
    for p in profiles:
        if p.name.startswith("_"):
            continue
        role = p.role.value
        null_pct = p.null_pct

        samples = []
        dist_str = ""
        if p.name in df.columns:
            raw = df[p.name].drop_nulls().head(3).to_list()
            samples = [str(v)[:60] for v in raw if v is not None]

            if role == "dimension" and p.n_unique <= 15 and p.n_unique > 0 and df[p.name].dtype in (pl.Utf8, pl.Categorical):
                try:
                    vc = df[p.name].drop_nulls().value_counts(name="_count", normalize=False)
                    if "_count" in vc.columns and len(vc) > 0:
                        total = vc["_count"].sum()
                        pairs = []
                        for row in vc.sort("_count", descending=True).head(8).iter_rows():
                            val, cnt = row
                            pct = int(round(cnt / total * 100)) if total > 0 else 0
                            pairs.append(f"{val}({pct}%)")
                        if pairs:
                            dist_str = f"  distribution: {', '.join(pairs)}"
                except Exception:
                    pass

        sample_str = f"  samples: {', '.join(samples)}" if samples else "  (all null)"

        if role in ("measure", "rate", "count") and p.col_min is not None:
            stats_line = (
                f"  range: [{p.col_min:.2f}, {p.col_max:.2f}]  "
                f"mean: {p.col_mean:.2f}  med: {p.col_median:.2f}  "
                f"cardinality: {p.n_unique}/{p.n_rows}  nulls: {null_pct:.0f}%"
            )
        else:
            stats_line = (
                f"  cardinality: {p.n_unique}/{p.n_rows}  nulls: {null_pct:.0f}%"
            )

        col_lines.append(f"- {p.name} [{dtype_abbrev(str(df[p.name].dtype))}]")
        col_lines.append(f"  role: {role}")
        col_lines.append(stats_line)
        col_lines.append(sample_str)
        if dist_str:
            col_lines.append(dist_str)

    columns_str = "\n".join(col_lines)

    prompt = f"""You are a data domain classifier. Your job is to analyze a dataset's columns and describe what domain it belongs to.

HOW TO REASON:
1. Sample values and VALUE RANGES are your strongest signal — trust them over column names.
   - A "value" column with samples [32000, 28500, 48000] and range [5000, 180000] is NOT the same as "value" with samples [0.023, -0.015, 0.009]
   - A "score" column that ranges [0, 100] with samples [85, 72, 91] is an exam/test score, not a medical score
2. For categorical columns, the VALUE DISTRIBUTION tells you more than the category names.
   - fuelType: Petrol(65%), Diesel(25%) is clearly different from fuelType: E10(40%), E85(30%), Diesel(30%)
3. Column NAMES are your weakest signal — disambiguate using the actual data values.
4. Describe what the data IS — what business process it captures, what entities it records.
5. BUSINESS CONTEXT overrides column names. If a user says "Revenue is our north star metric" or "Active users matter more than registered users", respect that in domain selection.
6. If you cannot determine the domain with high confidence, set domain_id to "unknown" and explain what single piece of information would resolve the ambiguity.
7. If the data matches a well-known pattern, include a domain_id (e.g. "automotive-metrics", "ecommerce-metrics", "healthcare-metrics"). Otherwise set domain_id to "unknown".

Output a JSON object with these fields:
- domain: a SHORT description of what this data is (3-8 words, never a full sentence). This is the primary output.
- domain_id: optional standard identifier if one clearly matches (use "unknown" if none fits)
- confidence: 0.0-1.0 score
- reasoning: 1-2 sentences explaining the key signals that determined the classification
- column_mapping: dictionary mapping template column types to actual column names (empty object if uncertain)

DATASET COLUMNS:
{columns_str}

{rules_block}OUTPUT (valid JSON only):
{{
  "domain": "vehicle listings with pricing and specs",
  "domain_id": "automotive-metrics",
  "confidence": 0.92,
  "reasoning": "Price range $5K-$185K with mileage, engine_size, transmission, and fuel type distribution (Petrol 65%, Diesel 25%) — standard vehicle listing columns.",
  "column_mapping": {{
    "mileage": "mileage",
    "price": "price"
  }}
}}

Return ONLY valid JSON. No markdown fences. No text before or after."""

    try:
        from llm.router import llm_router

        response = await llm_router.call(
            prompt=prompt,
            model_role="intent_engine",
            expect_json=True,
            temperature=0.1,
            is_conversational=False,
            max_tokens=800,
        )

        if isinstance(response, dict) and "domain_id" in response:
            domain_id = response.get("domain_id", "")
            confidence = response.get("confidence", 0.0)
            column_mapping = response.get("column_mapping", {}) or {}
            domain_desc = response.get("domain", "")

            if domain_id in ALL_TEMPLATES and confidence >= 0.5:
                col_names_lower = {c.lower(): c for c in df.columns}
                valid_mapping = {}
                for k, v in column_mapping.items():
                    if v in df.columns:
                        valid_mapping[k] = v
                    elif v.lower() in col_names_lower:
                        valid_mapping[k] = col_names_lower[v.lower()]
                logger.info(
                    f"[KPI] LLM classified domain: {domain_id} "
                    f"(desc='{domain_desc}', confidence={confidence}, "
                    f"reasoning={response.get('reasoning', 'N/A')[:80]}, "
                    f"mapped={len(valid_mapping)} columns)"
                )
                return domain_id, valid_mapping

            logger.info(
                f"[KPI] LLM returned: desc='{domain_desc}' (domain_id='{domain_id}', "
                f"confidence={confidence}) — no template match, using fallback"
            )
            return None, None

        logger.warning("[KPI] LLM domain classification returned invalid or unparseable response")
        return None, None

    except Exception as e:
        logger.warning(f"[KPI] LLM domain classification failed: {e}")
        return None, None


async def _detect_domain_hybrid(
    profiles: List[ColumnProfile],
    df: pl.DataFrame,
    business_rules: Optional[List[str]] = None,
) -> tuple[Optional[str], Optional[dict[str, str]]]:
    llm_domain, llm_mapping = await _llm_classify_domain(profiles, df, business_rules=business_rules)

    if llm_domain:
        logger.info(f"[KPI] LLM selected domain: {llm_domain}")
        return llm_domain, llm_mapping

    _, best_template, best_score = _compute_domain_scores(profiles)
    if best_template and best_score >= 30:
        logger.info(
            f"[KPI] LLM failed, pattern fallback: {best_template} "
            f"(score={best_score})"
        )
        return best_template, None

    logger.warning("[KPI] Domain detection failed completely — no template matched")
    return None, None
