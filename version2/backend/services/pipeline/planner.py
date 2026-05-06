"""
Stage 2 — Planner (LLM)

Takes the DatasetProfile + classifier candidate specs and asks a fast LLM to:
  - Confirm which primitives are worth computing for this specific data
  - Optionally suggest a better column binding from the columns in the profile

The LLM cannot invent column names or kpi_ids. Every output is validated
against the profile before it is accepted. On any failure the full candidate
list is returned unchanged (fail-open: better too many specs than none).
"""

import json
import logging
from typing import Optional

from db.schemas_pipeline import DatasetProfile, PrimitiveSpec

logger = logging.getLogger(__name__)


# ── Prompt construction ──────────────────────────────────────────────────────

_SYSTEM = (
    "You are a KPI planning agent. Review candidate metric primitives for a dataset "
    "and decide which ones are worth computing. "
    "You do not invent metrics and you do not invent column names. "
    "You only confirm or reject candidates from the list provided, and optionally "
    "suggest a better column binding using columns already listed in the profile.\n\n"
    "Rejection rules (cite evidence from the profile):\n"
    "- entity_concentration: reject if entity column has fewer than 10 unique values.\n"
    "- period_delta: reject if fewer than 2 distinct time periods are likely.\n"
    "- cohort_behavior: reject if entity column has fewer than 20 unique values.\n"
    "- anomaly_detection: reject if date_range_days < 90.\n"
    "- segment_mix: reject if the dimension column has only 1 unique value.\n"
    "Confirm everything else unless you have a specific data-evidence reason to reject.\n\n"
    "Output strict JSON only — no prose outside the JSON object."
)


def _profile_summary(profile: DatasetProfile) -> str:
    return json.dumps({
        "row_count": profile.row_count,
        "grain": profile.grain,
        "date_range_days": profile.date_range_days,
        "domain": profile.domain_signal,
        "columns": [
            {
                "name": c.name,
                "role": c.semantic.value,
                "cardinality": c.cardinality,
                "null_rate": c.null_rate,
            }
            for c in profile.columns
        ],
        "structures": {
            "entity_cols": profile.structures.entity_cols,
            "time_cols": profile.structures.time_cols,
            "measure_cols": profile.structures.measure_cols,
            "dimension_cols": profile.structures.dimension_cols,
        },
    }, indent=2)


def _specs_summary(specs: list[PrimitiveSpec]) -> str:
    return json.dumps([
        {
            "kpi_id": s.kpi_id,
            "primitive": s.primitive.value,
            "entity_col": s.entity_col,
            "measure_col": s.measure_col,
            "dimension_col": s.dimension_col,
            "time_col": s.time_col,
            "grain": s.grain.value if s.grain else None,
            "top_n": s.top_n if s.entity_col else None,
        }
        for s in specs
    ], indent=2)


def _build_prompt(profile: DatasetProfile, specs: list[PrimitiveSpec]) -> str:
    return (
        f"DATASET PROFILE:\n{_profile_summary(profile)}\n\n"
        f"CANDIDATE PRIMITIVES (confirm or reject each one):\n{_specs_summary(specs)}\n\n"
        "Respond with JSON matching this schema exactly:\n"
        "{\n"
        '  "confirmed_specs": [\n'
        "    {\n"
        '      "kpi_id": "<exact kpi_id from the candidate list>",\n'
        '      "confirmed": true | false,\n'
        '      "reason": "<one sentence citing specific column data>",\n'
        '      "column_overrides": {\n'
        '        "measure_col": "<col name — only if a better column exists in the profile>",\n'
        '        "entity_col":  "<col name — only if a better column exists in the profile>",\n'
        '        "dimension_col": "<col name — only if a better column exists in the profile>"\n'
        "      }\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Include every candidate kpi_id in the output. "
        "confirmed=false means skip that computation entirely."
    )


# ── Validation helpers ───────────────────────────────────────────────────────

def _col_exists(name: Optional[str], profile: DatasetProfile) -> bool:
    if not name:
        return True
    return any(c.name == name for c in profile.columns)


def _apply_overrides(
    spec: PrimitiveSpec,
    overrides: dict,
    profile: DatasetProfile,
) -> PrimitiveSpec:
    updates: dict = {}
    for field in ("entity_col", "measure_col", "dimension_col"):
        val = overrides.get(field)
        if val and isinstance(val, str) and _col_exists(val, profile):
            updates[field] = val
    return spec.model_copy(update=updates) if updates else spec


# ── Public API ───────────────────────────────────────────────────────────────

async def plan(
    profile: DatasetProfile,
    candidate_specs: list[PrimitiveSpec],
) -> list[PrimitiveSpec]:
    """
    LLM confirms which candidate specs to compute and optionally refines column
    bindings. Falls back to the full candidate list on any LLM or parse failure.
    """
    if not candidate_specs:
        return []

    from services.llm_router import llm_router

    prompt = _build_prompt(profile, candidate_specs)

    try:
        response = await llm_router.call(
            prompt=prompt,
            model_role="pipeline_planner",
            expect_json=True,
            temperature=0.1,
            max_tokens=2048,
            context=_SYSTEM,
        )
    except Exception as exc:
        logger.warning("Planner LLM call failed (%s) — using all candidates.", exc)
        return candidate_specs

    # Parse and validate LLM output
    confirmed_ids: dict[str, dict] = {}
    try:
        for item in response.get("confirmed_specs", []):
            kpi_id = item.get("kpi_id")
            if not kpi_id or not isinstance(kpi_id, str):
                continue
            if item.get("confirmed", True):
                confirmed_ids[kpi_id] = item.get("column_overrides") or {}
    except Exception as exc:
        logger.warning("Planner response parse failed (%s) — using all candidates.", exc)
        return candidate_specs

    # Safety net: if LLM confirmed nothing at all, keep everything
    if not confirmed_ids:
        logger.warning("Planner confirmed zero specs — falling back to all candidates.")
        return candidate_specs

    spec_by_id = {s.kpi_id: s for s in candidate_specs}
    result: list[PrimitiveSpec] = []

    for kpi_id, overrides in confirmed_ids.items():
        spec = spec_by_id.get(kpi_id)
        if spec is None:
            # LLM referenced a kpi_id that wasn't in the input — ignore
            logger.debug("Planner returned unknown kpi_id '%s' — skipped.", kpi_id)
            continue
        if overrides:
            spec = _apply_overrides(spec, overrides, profile)
        result.append(spec)

    logger.info("Planner: %d/%d candidates confirmed.", len(result), len(candidate_specs))
    return result
