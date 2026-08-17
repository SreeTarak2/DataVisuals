"""
api/assumptions/routes.py — Ontology assumptions API (Act-then-Validate)

The human's three touchpoints, all on FINISHED work (never authoring):
  1. Review queue   — GET  /datasets/{id}/assumptions?state=provisional
  2. Validate       — POST /datasets/{id}/assumptions/{aid}/validate  (or /reject)
  3. Fix            — PUT  /datasets/{id}/assumptions/{aid}  (user redefines)

Plus:
  - POST /datasets/{id}/assumptions/regenerate — re-run deterministic pass,
    LLM proposal pass, and drift re-verification in one shot.
  - GET  /datasets/{id}/hierarchies  — effective hierarchies (validated +
    provisional, rejected excluded) with state/confidence/evidence for the
    drill-down UI.
  - POST /datasets/{id}/drill-down   — execute a drill-down one level deeper
    along a hierarchy, with filters applied (consumes the ontology).

Every endpoint is tenant-scoped (workspace_id from the current user).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import polars as pl
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from services.auth_service import get_current_user
from core.rate_limiter import limiter, RateLimits

logger = logging.getLogger(__name__)

router = APIRouter()


class FixBody(BaseModel):
    definition: dict[str, Any]
    description: Optional[str] = None


class DrillDownBody(BaseModel):
    hierarchy: dict[str, Any]                  # {columns: [...], hierarchy_type: ...}
    current_level: Optional[str] = None
    filters: Optional[list[dict[str, Any]]] = None
    measures: Optional[list[str]] = None
    assumption_id: Optional[str] = None
    max_rows: int = 500


async def _load_full_df(dataset_id: str, user_id: str) -> pl.DataFrame:
    """Load the dataset frame — parquet preferred (full fidelity)."""
    from db.database import get_database
    from services.datasets.enhanced_dataset_service import enhanced_dataset_service

    db = get_database()
    doc = await db.uploads.find_one(
        {"_id": dataset_id, "user_id": user_id}, {"parquet_path": 1}
    )
    parquet_path = doc.get("parquet_path") if doc else None
    if parquet_path:
        try:
            return pl.read_parquet(parquet_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[Assumptions] parquet read failed, falling back: {exc}")
    df = await enhanced_dataset_service.load_dataset_data(
        dataset_id, user_id, max_rows=1_000_000
    )
    if df is None:
        raise HTTPException(status_code=404, detail="Dataset not found or empty")
    return df


def _workspace_id(current_user: dict) -> str:
    wid = current_user.get("workspace_id") or current_user.get("id")
    if not wid:
        raise HTTPException(status_code=400, detail="No workspace context")
    return str(wid)


# ─────────────────────────────────────────────────────────────────────────────
# Review queue + state transitions
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/datasets/{dataset_id}/assumptions")
@limiter.limit(RateLimits.DATASET_GET)
async def list_assumptions(
    request: Request,
    dataset_id: str,
    state: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """List assumptions (workspace-scoped), optionally filtered by state/type."""
    from services.semantic.assumption_store import assumption_store

    wid = _workspace_id(current_user)
    assumptions = await assumption_store.list(dataset_id, wid, state=state, type=type)
    counts = await assumption_store.counts(dataset_id, wid)
    return {
        "dataset_id": dataset_id,
        "counts": counts,
        "assumptions": [a.to_dict() for a in assumptions],
    }


@router.post("/datasets/{dataset_id}/assumptions/{assumption_id}/validate")
@limiter.limit(RateLimits.DATASET_GET)
async def validate_assumption(
    request: Request,
    dataset_id: str,
    assumption_id: str,
    current_user: dict = Depends(get_current_user),
):
    """One-click human sign-off → validated (writes to the belief store too)."""
    from services.semantic.assumption_store import assumption_store, VALIDATED

    wid = _workspace_id(current_user)
    updated = await assumption_store.set_state(
        dataset_id, wid, assumption_id, VALIDATED, user_id=current_user["id"]
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Assumption not found")

    # Mirror the validated ontology into the belief store so future prompts
    # (chat, QUIS, journey) inherit the confirmed semantics.
    try:
        from agents.belief.belief_store import get_belief_store

        belief_store = get_belief_store()
        await belief_store.add_belief(
            user_id=current_user["id"],
            dataset_id=dataset_id,
            belief_text=(
                f"Ontology (validated): {updated.type} "
                f"{updated.definition} — confidence {updated.confidence}"
            ),
            source="ontology_validation",
        )
    except Exception as exc:  # noqa: BLE001 — belief mirror is best-effort
        logger.debug(f"[Assumptions] belief mirror skipped: {exc}")

    return {"success": True, "assumption": updated.to_dict()}


@router.post("/datasets/{dataset_id}/assumptions/{assumption_id}/reject")
@limiter.limit(RateLimits.DATASET_GET)
async def reject_assumption(
    request: Request,
    dataset_id: str,
    assumption_id: str,
    current_user: dict = Depends(get_current_user),
):
    """One-click human rejection → remembered so the inference never repeats."""
    from services.semantic.assumption_store import assumption_store, REJECTED

    wid = _workspace_id(current_user)
    updated = await assumption_store.set_state(
        dataset_id, wid, assumption_id, REJECTED, user_id=current_user["id"]
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Assumption not found")
    return {"success": True, "assumption": updated.to_dict()}


@router.put("/datasets/{dataset_id}/assumptions/{assumption_id}")
@limiter.limit(RateLimits.DATASET_GET)
async def fix_assumption(
    request: Request,
    dataset_id: str,
    assumption_id: str,
    body: FixBody,
    current_user: dict = Depends(get_current_user),
):
    """User redefines the assumption → becomes user_defined + validated."""
    from services.semantic.assumption_store import assumption_store

    wid = _workspace_id(current_user)
    updated = await assumption_store.update_definition(
        dataset_id,
        wid,
        assumption_id,
        body.definition,
        description=body.description or "",
        user_id=current_user["id"],
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Assumption not found")
    return {"success": True, "assumption": updated.to_dict()}


# ─────────────────────────────────────────────────────────────────────────────
# Regenerate — deterministic pass + LLM pass + drift re-verification
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/datasets/{dataset_id}/assumptions/regenerate")
@limiter.limit(RateLimits.AI_DASHBOARD)
async def regenerate_assumptions(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Re-run the full inference stack against the current data.

    1. Re-profile from parquet (fresh facts).
    2. Deterministic pass → validated assumptions (upserted).
    3. Drift re-check on every existing validated assumption; broken ones
       revert to provisional with a drift flag.
    4. LLM proposal pass on uncovered dimensions → verified → persisted.
    """
    from services.profiling.engine import profiling_engine
    from services.intelligence.engine import intelligence_engine
    from services.intelligence.hierarchy_inference_v2 import (
        run_deterministic_pass,
        run_llm_pass,
        verify_assumption,
    )
    from services.semantic.assumption_store import (
        TYPE_HIERARCHY,
        VALIDATED,
        assumption_store,
    )

    wid = _workspace_id(current_user)
    df = await _load_full_df(dataset_id, current_user["id"])

    profiling = profiling_engine.run(df, file_type="parquet")
    intelligence_engine.run(profiling, df=df)  # side-effect free re-verify

    # ── 1. Deterministic pass (auto-validated) ──
    det = run_deterministic_pass(
        profiling, df, dataset_id, wid, user_id=current_user["id"]
    )
    for a in det:
        await assumption_store.upsert(a)

    # ── 2. Drift re-check on existing validated assumptions ──
    existing = await assumption_store.list(dataset_id, wid)
    drift_count = 0
    for a in existing:
        if a.type != TYPE_HIERARCHY or a.state != VALIDATED:
            continue
        ok, conf, evidence = verify_assumption(profiling, df, a)
        if not ok:
            a.confidence = conf
            a.evidence = {**a.evidence, **evidence}
            await assumption_store.apply_drift(a)
            drift_count += 1

    # ── 3. LLM proposal pass (uncovered dimensions only) ──
    covered: set[str] = set()
    for a in existing + det:
        for col in (a.definition.get("columns") or []):
            covered.add(col)
    llm_assumptions = await run_llm_pass(
        profiling,
        df,
        dataset_id,
        wid,
        user_id=current_user["id"],
        covered_columns=covered,
    )
    for a in llm_assumptions:
        await assumption_store.upsert(a)

    counts = await assumption_store.counts(dataset_id, wid)
    return {
        "success": True,
        "deterministic": len(det),
        "llm_proposals": len(llm_assumptions),
        "drift_reverted": drift_count,
        "counts": counts,
        "assumptions": [a.to_dict() for a in await assumption_store.list(dataset_id, wid)],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Consumption — hierarchies + drill-down
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/datasets/{dataset_id}/hierarchies")
@limiter.limit(RateLimits.DATASET_GET)
async def get_hierarchies(
    request: Request,
    dataset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Effective hierarchies for drill-down: validated first, then provisional.

    Fulfills the frontend drilldownAPI.getHierarchies contract. Provisional
    hierarchies carry their evidence + state so the UI can flag them.
    """
    from services.intelligence.hierarchy_inference_v2 import effective_hierarchies
    from services.semantic.assumption_store import assumption_store

    wid = _workspace_id(current_user)
    assumptions = await assumption_store.list(dataset_id, wid)
    hierarchies = effective_hierarchies(assumptions)

    # Fallback: legacy deterministic hierarchies from dataset_intelligence
    # (pre-assumption datasets) so the endpoint never returns empty.
    if not hierarchies:
        from db.database import get_database
        from db.tenant_guard import tenant_scope_query

        db = get_database()
        query = tenant_scope_query("dataset_intelligence", {"dataset_id": dataset_id}, wid)
        doc = await db.dataset_intelligence.find_one(query, {"intelligence.hierarchies": 1})
        if doc:
            for h in (doc.get("intelligence", {}).get("hierarchies") or []):
                hierarchies.append(
                    {
                        "columns": h.get("columns", []),
                        "hierarchy_type": h.get("hierarchy_type", "suggested"),
                        "confidence": 1.0,
                        "state": "validated",
                        "source": "legacy_deterministic",
                        "evidence": {},
                        "description": h.get("description", ""),
                    }
                )

    counts = await assumption_store.counts(dataset_id, wid)
    return {
        "dataset_id": dataset_id,
        "hierarchies": hierarchies,
        "counts": counts,
    }


@router.post("/datasets/{dataset_id}/drill-down")
@limiter.limit(RateLimits.DATASET_GET)
async def drill_down(
    request: Request,
    dataset_id: str,
    body: DrillDownBody,
    current_user: dict = Depends(get_current_user),
):
    """Execute a drill-down one level deeper along a hierarchy.

    Body:
      hierarchy:      {columns: [region, country, city], ...}
      current_level:  column currently on the axis (None = root → first level)
      filters:        [{field, value}, ...]  (cross-filter context)
      measures:       numeric columns to aggregate (default: all numeric)
      assumption_id:  optional — to surface the ontology state of the path

    Returns the next level's aggregated rows + the assumption state so the
    UI can flag provisional drill paths.
    """
    from core.chart_filter import apply_df_filters
    from services.semantic.assumption_store import assumption_store

    wid = _workspace_id(current_user)
    columns = body.hierarchy.get("columns") or []
    if len(columns) < 2:
        raise HTTPException(status_code=400, detail="Hierarchy needs at least 2 columns")

    df = await _load_full_df(dataset_id, current_user["id"])
    if body.filters:
        df = apply_df_filters(df, body.filters)
    if df.is_empty():
        return {
            "next_level": None,
            "columns": [],
            "data": [],
            "empty_filtered": True,
            "assumption": None,
        }

    # Locate the next level in the hierarchy chain.
    current = body.current_level
    next_level: Optional[str] = None
    if not current or current == "root":
        next_level = columns[0]
    else:
        try:
            idx = columns.index(current)
            if idx + 1 < len(columns):
                next_level = columns[idx + 1]
        except ValueError:
            next_level = columns[0]

    if next_level is None:
        # Leaf level — return detail rows instead of another aggregation.
        sample = df.head(body.max_rows)
        return {
            "next_level": None,
            "is_leaf": True,
            "columns": list(sample.columns),
            "data": sample.to_dicts(),
            "row_count": len(sample),
            "assumption": None,
        }

    # Aggregate measures over the next level.
    if body.measures:
        measures = [m for m in body.measures if m in df.columns]
    else:
        measures = [
            c for c in df.columns
            if df.schema[c] in (pl.Int8, pl.Int16, pl.Int32, pl.Int64,
                                pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64,
                                pl.Float32, pl.Float64)
            and c != next_level
        ]
    measures = measures[:8]

    aggs = [pl.col(m).sum().alias(m) for m in measures]
    if not aggs:
        aggs = [pl.len().alias("count")]
    try:
        grouped = (
            df.group_by(next_level)
            .agg(*aggs)
            .sort(next_level)
            .head(body.max_rows)
        )
        data = grouped.to_dicts()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Drill-down failed: {exc}")

    # Surface the ontology state of the drill path (provisional → flag).
    assumption = None
    if body.assumption_id:
        stored = await assumption_store.get(dataset_id, wid, body.assumption_id)
        if stored:
            assumption = {
                "assumption_id": stored.assumption_id,
                "state": stored.state,
                "confidence": stored.confidence,
                "columns": stored.definition.get("columns", []),
            }

    return {
        "next_level": next_level,
        "columns": [next_level] + measures,
        "data": data,
        "hierarchy_columns": columns,
        "assumption": assumption,
        "provisional": assumption is not None and assumption["state"] == "provisional",
    }
