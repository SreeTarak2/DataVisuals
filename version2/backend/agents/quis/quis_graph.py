# backend/services/agents/quis_graph.py

"""
LangGraph QUIS Orchestrator
===========================
Cyclic state graph implementing the agentic QUIS architecture.

Graph Topology:
    START -> planner -> analyst -> critic -> [conditional]
                                      |
                          +-----------+-----------+
                          |           |           |
                        REJECT      APPROVE     DONE
                          |           |           |
                          v           v           v
                       analyst    novelty    synthesizer -> END
                                    |
                          +---------+---------+
                          |                   |
                        BORING              NOVEL
                          |                   |
                          v                   v
                       planner           synthesizer

This replaces the linear `run_analysis()` in enhanced_quis.py with a
self-correcting loop that can retry on errors and filter boring insights.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Literal, Optional, List, Tuple
from datetime import datetime, timezone
import polars as pl

# LangGraph imports
try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logging.warning("LangGraph not installed. Run: pip install langgraph")

from .state import AgentState, create_initial_state

logger = logging.getLogger(__name__)

# ── Multiple-testing control helpers ────────────────────────────────────────
# The agentic graph tests many hypotheses across questions (correlation,
# comparison, trend, plus subspace expansions). Without global FDR control,
# the run surfaces false positives even when every individual p < 0.05.
# These helpers mirror the within-family Benjamini-Hochberg logic that the
# linear EnhancedQUIS path already applies.


def _insight_family(insight_type: str) -> str:
    """Map an insight_type to its statistical test family for within-family FDR.
    Mirrors the family bucketing in EnhancedQUIS.run_analysis so the agentic
    graph and the linear path apply the same multiple-testing control."""
    if insight_type in ("correlation", "subspace_correlation"):
        return "correlation"
    if insight_type == "group_comparison":
        return "comparison"
    if insight_type == "trend":
        return "trend"
    return "other"


def _safe_corr(d, c1: str, c2: str) -> Optional[float]:
    """Pearson r between two columns, or None on any failure (null/NaN/error)."""
    try:
        r = d.select(pl.corr(c1, c2)).item()
        if r is None:
            return None
        r = float(r)
        return None if r != r else r  # NaN check (NaN != NaN)
    except Exception:
        return None


def _check_insight_stability(df, insight) -> Optional[bool]:
    """
    Split-sample robustness check: recompute a finding on two independent halves
    and require the direction to agree. This is the "does it replicate?" gate that
    distinguishes real patterns from sampling noise (single-pass p < 0.05 is not
    enough when dozens of hypotheses are tested).

    Returns:
      True   finding replicates on both halves
      False  finding does NOT replicate (reject as noise)
      None   not checkable for this insight type (skip)

    Never raises — any failure degrades to None.
    """
    try:
        from scipy import stats as _stats
        import numpy as _np

        if isinstance(insight, dict):
            itype = insight.get("insight_type", "")
            cols = insight.get("columns", []) or []
        else:
            itype = getattr(insight, "insight_type", "")
            cols = getattr(insight, "columns", []) or []

        if itype == "correlation" and len(cols) >= 2:
            c1, c2 = cols[0], cols[1]
            if c1 not in df.columns or c2 not in df.columns:
                return None
            pair = df.select([c1, c2]).drop_nulls()
            n = len(pair)
            if n < 40:
                return None
            half = n // 2
            r1 = _safe_corr(pair.head(half), c1, c2)
            r2 = _safe_corr(pair.tail(n - half), c1, c2)
            if r1 is None or r2 is None:
                return None
            return bool((r1 > 0) == (r2 > 0) and abs(r1) > 0.05 and abs(r2) > 0.05)

        if itype == "trend" and cols:
            num = cols[0]
            if num not in df.columns:
                return None
            time_col = cols[1] if len(cols) > 1 and cols[1] in df.columns else None
            try:
                d = df.sort(time_col) if time_col else df
            except Exception:
                d = df
            data = d[num].drop_nulls().to_numpy()
            if len(data) < 40:
                return None
            half = len(data) // 2
            t1 = _stats.spearmanr(_np.arange(half), data[:half])
            t2 = _stats.spearmanr(_np.arange(len(data) - half), data[half:])
            # Direction agreement with a LOOSER per-half threshold (p < 0.1):
            # splitting halves the power, so requiring p < 0.05 in each half
            # rejects most real modest trends (over-strict). The gate's job is
            # replication (does the direction hold on independent halves), not
            # to re-prove full-sample significance.
            if t1.pvalue > 0.1 or t2.pvalue > 0.1:
                return False
            return bool((t1.statistic > 0) == (t2.statistic > 0))

        if itype == "group_comparison" and len(cols) >= 2:
            num, cat = cols[0], cols[1]
            if num not in df.columns or cat not in df.columns:
                return None
            sub = df.select([num, cat]).drop_nulls()
            n = len(sub)
            if n < 40:
                return None
            top = (
                sub.group_by(cat)
                .agg(pl.len().alias("_n"))
                .sort("_n", descending=True)
                .head(2)
            )
            gvals = top[cat].to_list()
            if len(gvals) < 2:
                return None

            def _mean_diff(d, ga, gb):
                ma = d.filter(pl.col(cat) == ga)[num].mean()
                mb = d.filter(pl.col(cat) == gb)[num].mean()
                if ma is None or mb is None:
                    return None
                return float(ma) - float(mb)

            half = n // 2
            diff1 = _mean_diff(sub.head(half), gvals[0], gvals[1])
            diff2 = _mean_diff(sub.tail(n - half), gvals[0], gvals[1])
            if diff1 is None or diff2 is None or diff1 == 0 or diff2 == 0:
                return None
            return bool((diff1 > 0) == (diff2 > 0))
    except Exception:
        pass
    return None


def _build_retry_question(
    question: Dict[str, Any], df, retry_index: int = 0
) -> Optional[Dict[str, Any]]:
    """
    Build a STRUCTURALLY different question for a deterministic retry.

    The InsightGenerator is fully deterministic and reads only the structured
    fields (question_type, target_columns, filter_column) — question *text* is
    inert. A retry must therefore change those fields; otherwise it
    reproduces the identical result (the research-verified same-input
    anti-pattern).

    Strategy (decompose / shift abstraction):
      1. correlation      → subspace   (same column pair, add a categorical filter)
      2. subspace         → different categorical filter
      3. comparison/trend → different numeric target column

    IMPORTANT: `retry_index` (error_count at entry) is used to ROTATE through
    the unused categoricals/numerics. Because this function is deterministic,
    calling it repeatedly with the same inputs reproduces the same output;
    rotating by attempt number guarantees each retry is a *different* question
    instead of re-running the identical modified one (stateful modification).

    Returns None when no meaningful modification exists — the caller should
    skip the question rather than re-run identical input.
    """
    try:
        from services.analysis.enhanced_quis import _is_id_column as _is_id

        q = dict(question)
        qtype = question.get("question_type")
        target = [c for c in (question.get("target_columns") or []) if c in df.columns]
        filter_col = question.get("filter_column")
        k = max(int(retry_index or 0), 0)

        numeric = [c for c in df.select(pl.col(pl.NUMERIC_DTYPES)).columns if not _is_id(c)]
        categorical = [
            c for c in df.select(pl.col([pl.Utf8, pl.Categorical])).columns if not _is_id(c)
        ]

        # 1) Decompose correlation/trend/comparison → subspace (different test family)
        if qtype in ("correlation", "trend", "comparison") and categorical:
            unused_cat = [c for c in categorical if c != filter_col]
            if unused_cat and len(target) >= 2:
                cat = unused_cat[k % len(unused_cat)]
                q["question_type"] = "subspace"
                q["filter_column"] = cat
                q["question"] = (
                    f"Does {target[0]} vs {target[1]} correlate differently "
                    f"across {cat}?"
                )
                return q

        # 2) Subspace → different categorical filter (rotate by attempt)
        if qtype == "subspace" and categorical:
            unused_cat = [c for c in categorical if c != filter_col]
            if unused_cat:
                cat = unused_cat[k % len(unused_cat)]
                q["filter_column"] = cat
                q["question"] = (
                    f"Is the relationship between {target[0] if target else '?'} and "
                    f"{target[1] if len(target) > 1 else '?'} different for "
                    f"{cat}?"
                )
                return q

        # 3) Comparison/trend → different numeric target column (rotate by attempt)
        if qtype in ("comparison", "trend") and target:
            unused_num = [c for c in numeric if c not in target]
            if unused_num:
                num = unused_num[k % len(unused_num)]
                q["target_columns"] = [num] + target[1:]
                q["question"] = (
                    f"Does {num} differ across {filter_col or 'groups'}?"
                )
                return q
    except Exception as e:
        logger.debug(f"[ANALYST] Retry question build failed: {e}")
    return None


# Checkpointer — use PostgresSaver in production, MemorySaver as fallback
import os as _os

_CHECKPOINT_DB_URI = _os.getenv("POSTGRES_CHECKPOINT_URL") or _os.getenv("DATABASE_URL")
_PERSISTENT_CHECKPOINT = bool(_CHECKPOINT_DB_URI) and _CHECKPOINT_DB_URI.startswith("postgres")

QUIS_MAX_ROWS = 100_000


async def _load_dataset_cached(
    dataset_id: str, user_id: str, tenant_id: Optional[str] = None
) -> Optional[pl.DataFrame]:
    """Load dataset from MongoDB with tenant-scoped caching.

    Uses CacheService (Redis + in-memory LRU) instead of the old in-memory
    FIFO dict to support multi-worker deployments.

    Returns sampled DataFrame if > 100K rows, with deterministic seed per user.
    """
    tid = tenant_id or user_id or "default"

    # Use CacheService for tenant-scoped caching (Redis + in-memory LRU fallback)
    from services.cache.cache_service import CacheService

    cache = CacheService()
    cache_key = f"quis:df:{tid}:{dataset_id}"
    cached = await cache.get_dataframe(cache_key)
    if cached is not None:
        logger.debug("[CACHE] Hit for tenant %s dataset %s", tid, dataset_id)
        return cached

    from services.datasets.enhanced_dataset_service import enhanced_dataset_service

    # Strictly workspace-scoped raw read (handles str/ObjectId _id + tenant pin).
    # When tenant_id is None, the helper resolves the user's personal workspace.
    dataset = await enhanced_dataset_service.get_dataset_doc(
        dataset_id, user_id, workspace_id=tenant_id
    )
    if not dataset:
        return None

    parquet_path = dataset.get("parquet_path")
    data_path = (
        parquet_path if parquet_path and Path(parquet_path).exists() else dataset.get("file_path")
    )
    if not data_path:
        return None

    try:
        df = pl.read_parquet(data_path)
    except Exception:
        try:
            df = pl.read_csv(data_path)
        except Exception as e:
            logger.error(f"Failed to load dataset {dataset_id}: {e}")
            return None

    row_count = len(df)
    if row_count > QUIS_MAX_ROWS:
        # Use user_id as seed so each user gets a different representative sample
        import hashlib

        seed = int(hashlib.sha256(tid.encode()).hexdigest()[:8], 16)
        df = df.sample(n=QUIS_MAX_ROWS, seed=seed)
        logger.info(f"[SAMPLE] Sampled {QUIS_MAX_ROWS:,} from {row_count:,} rows (seed={seed})")

    await cache.set_dataframe(cache_key, df)
    return df


# ============================================================
# NODE FUNCTIONS
# ============================================================


async def planner_node(state: AgentState) -> Dict[str, Any]:
    """
    QUGEN: Generate analytical questions from dataset schema.

    This node replaces QuestionGenerator.generate_questions_template()
    with state-aware question generation.
    """
    logger.info(f"[PLANNER] Starting question generation for dataset {state['dataset_id']}")

    # Import here to avoid circular dependencies
    from services.analysis.enhanced_quis import QuestionGenerator

    # Check if questions already generated
    if state["questions"] and state["current_question_idx"] < len(state["questions"]):
        # FIX §6: If we're skipping due to max retries, advance the question index
        # and reset the error counter to prevent the dead-loop documented in §2.2.
        if state.get("error_count", 0) >= state.get("max_retries", 3):
            skipped_idx = state["current_question_idx"]
            logger.info(
                f"[PLANNER] Skipping question {skipped_idx} after {state['error_count']} errors"
            )
            return {
                "current_question_idx": skipped_idx + 1,
                "error_count": 0,
            }

        logger.info(
            f"[PLANNER] Questions already generated, moving to next at idx {state['current_question_idx']}"
        )
        return {}  # No state update needed

    # Generate questions if not yet done
    if not state["questions"]:
        try:
            df = await _load_dataset_cached(
                state["dataset_id"],
                state["user_id"],
                tenant_id=state.get("tenant_id", state.get("user_id")),
            )
            if df is None:
                return {
                    "last_error": "Dataset not found or missing file path",
                    "final_response": "Error: Could not access dataset for analysis.",
                }

            # Generate questions
            generator = QuestionGenerator()
            questions = generator.generate_questions_template(df, max_questions=15)

            # Convert to state format
            question_states = [
                {
                    "question": q.question,
                    "question_type": q.question_type,
                    "target_columns": q.target_columns,
                    "filter_column": q.filter_column,
                    "priority": q.priority,
                }
                for q in questions
            ]

            logger.info(f"[PLANNER] Generated {len(question_states)} questions")

            return {
                "questions": question_states,
                "current_question_idx": 0,
                "iteration_count": state["iteration_count"] + 1,
            }

        except Exception as e:
            logger.error(f"[PLANNER] Error generating questions: {e}")
            return {
                "last_error": str(e),
                "iteration_count": state["iteration_count"] + 1,
            }

    return {"iteration_count": state["iteration_count"] + 1}


async def analyst_node(state: AgentState) -> Dict[str, Any]:
    """
    ISGEN: Execute statistical analysis for current question.

    FIX: Collects ALL insights from generate_insights instead of just insights[0].
    The old code discarded 5-15 insights on every question — a major data loss bug.

    Uses active_beliefs (user's true business rules, stored separately from
    seen_insights which are populated by the novelty filter).
    """
    logger.info(f"[ANALYST] Analyzing question {state['current_question_idx']}")

    from services.analysis.enhanced_quis import InsightGenerator, AnalyticalQuestion

    # Use active_beliefs — these are the user's actual business rules,
    # NOT the overwritten seen_insights from the novelty filter.
    # This separation fixes the belief_context corruption bug (§5.1).
    active_beliefs = state.get("active_beliefs", [])
    if active_beliefs:
        first_belief = (
            active_beliefs[0] if isinstance(active_beliefs, list) else str(active_beliefs)
        )
        logger.info(f"[ANALYST] Active business rules: {first_belief[:100]}...")

    # Safety check
    if state["current_question_idx"] >= len(state["questions"]):
        logger.info("[ANALYST] No more questions to analyze")
        return {}

    current_question = state["questions"][state["current_question_idx"]]

    try:
        df = await _load_dataset_cached(
            state["dataset_id"],
            state["user_id"],
            tenant_id=state.get("tenant_id", state.get("user_id")),
        )
        if df is None:
            return {
                "last_error": f"Dataset {state['dataset_id']} not found",
                "iteration_count": state["iteration_count"] + 1,
            }

        # ── FIX §2.1 (actual implementation): on retry, MODIFY the question ──
        # The InsightGenerator is deterministic and reads ONLY structured
        # fields (type/columns/filter) — question text is inert. So a retry
        # must structurally change the question (correlation → subspace,
        # swap columns/filters) or skip it entirely. Same-input retries
        # deterministically reproduce the same rejection (Huang et al. 2024
        # + follow-ups: only stateful modification helps).
        working_question = current_question
        retry_attempt = state.get("error_count", 0)
        if retry_attempt > 0:
            # Pass the attempt number so _build_retry_question ROTATES through
            # unused categoricals/numerics — deterministic builder, so the
            # rotation is what guarantees each retry is a different question
            # (retry #2 must not reproduce retry #1's identical modification).
            modified = _build_retry_question(current_question, df, retry_index=retry_attempt - 1)
            if modified is None:
                logger.info(
                    f"[ANALYST] No modified angle for question "
                    f"{state['current_question_idx']} — skipping"
                )
                return {
                    "current_insights": [],
                    "execution_result": "No significant insights found for this question.",
                    "error_count": 0,
                    "last_error": None,
                    "iteration_count": state["iteration_count"] + 1,
                }
            working_question = modified
            retry_hints = []
            if state.get("last_error"):
                retry_hints.append(f"Previous attempt failed: {state['last_error']}")
            critique = state.get("critique") or {}
            if critique.get("suggestions"):
                retry_hints.append("Critic feedback: " + "; ".join(critique["suggestions"][:3]))
            logger.info(
                f"[ANALYST] Retrying question {state['current_question_idx']} "
                f"with modified structure ({modified['question_type']})"
            )

        # Enrich question with active beliefs (user's business rules) if available
        enriched_question = working_question["question"]
        if active_beliefs:
            ctx_str = active_beliefs[0] if isinstance(active_beliefs, list) else str(active_beliefs)
            enriched_question = (
                f"{working_question['question']}\n\nActive business rules:\n{ctx_str}"
            )
        if state.get("error_count", 0) > 0 and retry_hints:
            enriched_question = (
                f"{enriched_question}\n\nContext from previous attempt:\n"
                + "\n".join(retry_hints)
            )

        # Convert to AnalyticalQuestion object (structured fields drive the
        # deterministic generator — the text is context for downstream use)
        question_obj = AnalyticalQuestion(
            question=enriched_question,
            question_type=working_question["question_type"],
            target_columns=working_question["target_columns"],
            filter_column=working_question.get("filter_column"),
            priority=working_question.get("priority", 1.0),
        )

        # Generate insights
        generator = InsightGenerator()
        insights = generator.generate_insights(df, [question_obj])

        logger.info(f"[ANALYST] Generated {len(insights)} raw insights")

        # Convert ALL insights to state format — NOT just insights[0]. Each
        # insight gets a stable run_id + test family (for the FDR gate) and a
        # split-sample stability verdict (for the critic's replicate gate).
        if insights:
            all_insights = []
            prev_pvalues = list(state.get("raw_insight_pvalues", []))
            for i, insight in enumerate(insights):
                # error_count in the run_id keeps retried generations unique in
                # the FDR pool (run_id would otherwise collide across retries).
                run_id = f"q{state['current_question_idx']}-r{state.get('error_count', 0)}-i{i}"
                family = _insight_family(insight.insight_type)
                stability_ok = (
                    _check_insight_stability(df, insight)
                    if insight.insight_type in ("correlation", "trend", "group_comparison")
                    else None
                )
                all_insights.append(
                    {
                        "insight_type": insight.insight_type,
                        "description": insight.description,
                        "columns": insight.columns,
                        "subspace": insight.subspace,
                        "statistic": insight.statistic,
                        "p_value": insight.p_value,
                        "effect_size": insight.effect_size,
                        "effect_interpretation": insight.effect_interpretation,
                        "sample_size": insight.sample_size,
                        "is_simpson_paradox": insight.is_simpson_paradox,
                        "novelty_score": insight.novelty_score,
                        "overall_score": insight.overall_score,
                        "confidence_interval": (
                            list(insight.confidence_interval)
                            if insight.confidence_interval
                            else None
                        ),
                        "run_id": run_id,
                        "family": family,
                        "stability_ok": stability_ok,
                    }
                )
                pv = insight.p_value
                if isinstance(pv, (int, float)) and 0 <= pv <= 1:
                    prev_pvalues.append(
                        {"run_id": run_id, "family": family, "p_value": float(pv)}
                    )

            import json as _json_ser

            return {
                "current_insights": all_insights,  # Store ALL insights
                "execution_result": _json_ser.dumps(all_insights[0], default=str),
                "error_count": 0,  # Reset on success
                "last_error": None,
                "raw_insight_pvalues": prev_pvalues,  # Accumulated for FDR gate
                "iteration_count": state["iteration_count"] + 1,
            }
        else:
            return {
                "current_insights": [],
                "execution_result": "No significant insights found for this question.",
                "iteration_count": state["iteration_count"] + 1,
            }

    except Exception as e:
        logger.error(f"[ANALYST] Error during analysis: {e}")
        return {
            "current_insights": [],
            "last_error": str(e),
            "error_count": state["error_count"] + 1,
            "iteration_count": state["iteration_count"] + 1,
        }


async def critic_node(state: AgentState) -> Dict[str, Any]:
    """
    Critic: Validate analyst output before passing to user.

    Checks:
    1. Statistical validity (p-value ranges, effect size sanity)
    2. Schema compliance (column names exist)
    3. Sample-size floor warning

    FIX §5.5: Populates rejected_insights when insights fail critique,
    so the field isn't perpetually empty.
    """
    logger.info("[CRITIC] Reviewing analyst output")

    execution_result = state.get("execution_result", "")
    current_insights = state.get("current_insights", [])

    # Check if there's an error to handle
    if state.get("last_error"):
        logger.info(f"[CRITIC] Found error: {state['last_error']}")
        return {
            "critique": {
                "score": 0.0,
                "passed": False,
                "feedback": f"Execution failed: {state['last_error']}",
                "issues": ["execution_error"],
                "suggestions": ["Fix the error and retry"],
            },
            "rejected_insights": state.get("rejected_insights", [])
            + [
                {
                    "reason": "execution_error",
                    "error": state["last_error"],
                    "question_idx": state["current_question_idx"],
                }
            ],
            "iteration_count": state["iteration_count"] + 1,
        }

    # Check if we got a valid result
    if (
        not execution_result
        or execution_result == "No significant insights found for this question."
    ):
        logger.info("[CRITIC] No significant insights, moving to next question")
        return {
            "critique": {
                "score": 0.5,
                "passed": True,  # Not an error, just no findings
                "feedback": "No significant insights for this question",
                "issues": [],
                "suggestions": [],
            },
            "iteration_count": state["iteration_count"] + 1,
        }

    # Validate ALL current_insights, not just the first one
    validated_insights = []
    rejected = list(state.get("rejected_insights", []))

    for insight_dict in current_insights:
        if not isinstance(insight_dict, dict):
            continue

        try:
            issues = []
            suggestions = []
            is_valid = True

            # --- CHECK 1: P-value range ---
            p_value = insight_dict.get("p_value", 1.0)
            if p_value < 0 or p_value > 1:
                issues.append("invalid_p_value")
                suggestions.append(f"P-value {p_value} is out of range [0, 1]")
                is_valid = False

            # --- CHECK 2: Effect size sanity ---
            effect_size = insight_dict.get("effect_size", 0)
            if effect_size and abs(effect_size) > 10:
                issues.append("suspicious_effect_size")
                suggestions.append(f"Effect size {effect_size} seems unreasonably large")
                is_valid = False

            # --- CHECK 3: Schema compliance ---
            insight_columns = insight_dict.get("columns", [])
            if insight_columns and state.get("data_schema"):
                try:
                    import json as _json

                    schema = _json.loads(state["data_schema"])
                    if isinstance(schema, dict):
                        valid_cols = set(schema.keys())
                    elif isinstance(schema, list):
                        valid_cols = {
                            entry.get("name", entry.get("column", ""))
                            for entry in schema
                            if isinstance(entry, dict)
                        }
                    else:
                        valid_cols = set()

                    if valid_cols:
                        bad_cols = [c for c in insight_columns if c not in valid_cols]
                        if bad_cols:
                            issues.append("schema_violation")
                            suggestions.append(f"Column(s) {bad_cols} not found in schema")
                            is_valid = False
                except Exception:
                    pass

            # --- CHECK 4: Sample-size floor (warning only) ---
            sample_size = insight_dict.get("sample_size", 0)
            if 0 < sample_size < 30:
                issues.append("low_sample_size")
                suggestions.append(f"Sample size {sample_size} < 30 — insufficient power")

            # --- CHECK 5: Confidence interval must exclude zero ---
            # Single-pass p < 0.05 is necessary but not sufficient — a wide CI
            # that straddles zero means the effect is not reliably distinguishable
            # from noise, even when the test happens to reject.
            ci = insight_dict.get("confidence_interval")
            if isinstance(ci, (list, tuple)) and len(ci) == 2:
                try:
                    low, high = float(ci[0]), float(ci[1])
                    if low <= 0 <= high:
                        issues.append("ci_includes_zero")
                        suggestions.append(
                            "Confidence interval includes zero — effect not reliably "
                            "distinguishable from noise"
                        )
                        is_valid = False
                except (TypeError, ValueError):
                    pass

            # --- CHECK 6: Split-sample stability (finding must replicate) ---
            # Computed in analyst_node: recompute the finding on two independent
            # halves and require direction agreement. Unstable findings are noise.
            stability_ok = insight_dict.get("stability_ok")
            if stability_ok is False:
                issues.append("unstable_finding")
                suggestions.append(
                    "Finding does not replicate on split samples — likely sampling noise"
                )
                is_valid = False

            if is_valid:
                validated_insights.append(insight_dict)
            else:
                rejected.append(
                    {
                        "reason": "; ".join(issues),
                        "insight": insight_dict.get("description", "")[:100],
                        "question_idx": state["current_question_idx"],
                    }
                )
        except Exception as e:
            rejected.append(
                {
                    "reason": f"validation_error: {str(e)}",
                    "question_idx": state["current_question_idx"],
                }
            )

    total = len(current_insights)
    passed_count = len(validated_insights)
    rejected_count = len(rejected) - len(state.get("rejected_insights", []))

    logger.info(
        f"[CRITIC] Validated {total} insights: {passed_count} passed, {rejected_count} rejected"
    )

    # Store validated insights back
    import json as _json_ser

    return {
        "current_insights": validated_insights,
        "execution_result": _json_ser.dumps(validated_insights[0], default=str)
        if validated_insights
        else execution_result,
        "critique": {
            "score": passed_count / max(total, 1),
            "passed": passed_count > 0,
            "feedback": f"{passed_count}/{total} insights passed validation",
            "issues": [] if passed_count > 0 else ["all_insights_rejected"],
            "suggestions": [],
        },
        "rejected_insights": rejected,
        "error_count": 0 if passed_count > 0 else state.get("error_count", 0) + 1,
        "iteration_count": state["iteration_count"] + 1,
    }


async def novelty_filter_node(state: AgentState) -> Dict[str, Any]:
    """
    Novelty Filter: Check if each insight is subjectively novel to this user.

    FIX §2: Per-insight novelty scoring — each insight gets its own hybrid score
    instead of the old behavior where the first insight's score was applied to all.
    The novelty filter now iterates over ALL current_insights and computes
    semantic surprisal + Bayesian surprise independently per insight.

    FIX §4: Alpha adaptation — when insights are rejected (boring), alpha is
    updated via EMA. If the Bayesian surprise was high but the semantic
    surprisal was low (user "already knew" the pattern), alpha rises to
    weight semantics more in the future.

    FIX §5.1: active_beliefs (user's business rules) are NEVER overwritten.
    seen_insights captures similar beliefs from the filter for transparency,
    but the original business rules stay in active_beliefs untouched.
    """
    logger.info("[NOVELTY] Checking insight novelty")

    from agents.belief.belief_store import get_belief_store, get_bayesian_tracker, BeliefStore
    import re
    import json as _json_parse

    belief_store = get_belief_store()
    bayesian_tracker = await get_bayesian_tracker()

    all_current = state.get("current_insights", [])

    # Fallback: if no current_insights but we have execution_result, parse it
    if not all_current:
        execution_result = state.get("execution_result", "")
        try:
            insight_dict = _json_parse.loads(execution_result)
            if isinstance(insight_dict, dict):
                all_current = [insight_dict]
        except (ValueError, TypeError):
            pass

    new_approved = list(state.get("approved_insights", []))
    new_boring = list(state.get("boring_insights", []))
    seen_insights = []
    current_alpha = state.get("alpha", 0.6)

    for insight in all_current:
        if not isinstance(insight, dict):
            continue

        insight_text = insight.get("description", "")
        if not insight_text:
            continue

        # 1. Calculate Semantic Surprisal (per-insight)
        semantic_surprisal, similar_beliefs = await belief_store.calculate_semantic_surprisal(
            user_id=state["user_id"], insight_text=insight_text
        )

        # FIX §3: Check insight against active_beliefs (MongoDB business rules).
        # If the insight shares significant keyword overlap with a known business
        # rule, apply a novelty penalty. This catches cases where the user said
        # "Revenue excludes refunds" but the QUIS pipeline finds "Revenue is $120K"
        # — the insight should be less novel because the user already articulated
        # specific knowledge about the revenue metric.
        active_beliefs_str = state.get("active_beliefs", [])
        if active_beliefs_str and isinstance(active_beliefs_str, list):
            active_beliefs_str = " ".join(active_beliefs_str)
        if isinstance(active_beliefs_str, str) and len(active_beliefs_str) > 20:
            # Extract key terms from both the insight and the business rules
            insight_terms = set(re.findall(r"[a-zA-Z_]+", insight_text.lower()))
            rule_terms = set(re.findall(r"[a-zA-Z_]+", active_beliefs_str.lower()))
            stopwords = {
                "the",
                "a",
                "an",
                "is",
                "are",
                "was",
                "were",
                "be",
                "been",
                "being",
                "have",
                "has",
                "had",
                "do",
                "does",
                "did",
                "will",
                "would",
                "could",
                "should",
                "may",
                "might",
                "shall",
                "can",
                "not",
                "no",
                "nor",
                "but",
                "or",
                "and",
                "if",
                "then",
                "else",
                "when",
                "where",
                "why",
                "how",
                "all",
                "each",
                "every",
                "both",
                "few",
                "more",
                "most",
                "other",
                "some",
                "such",
                "only",
                "own",
                "same",
                "so",
                "than",
                "too",
                "very",
                "just",
                "because",
                "as",
                "until",
                "while",
                "of",
                "at",
                "by",
                "for",
                "with",
                "about",
                "against",
                "between",
                "into",
                "through",
                "during",
                "before",
                "after",
                "above",
                "below",
                "to",
                "from",
                "up",
                "down",
                "in",
                "out",
                "on",
                "off",
                "over",
                "under",
                "again",
                "further",
                "once",
                "here",
                "there",
                "this",
                "that",
                "these",
                "those",
                "i",
                "me",
                "my",
                "myself",
                "we",
                "our",
                "ours",
                "ourselves",
                "you",
                "your",
                "yours",
                "yourself",
                "yourselves",
                "he",
                "him",
                "his",
                "himself",
                "she",
                "her",
                "hers",
                "herself",
                "it",
                "its",
                "itself",
                "they",
                "them",
                "their",
                "theirs",
                "themselves",
                "what",
                "which",
                "who",
                "whom",
                "data",
                "column",
                "row",
                "value",
                "values",
                "show",
                "shows",
                "shown",
                "using",
                "used",
                "use",
                "based",
                "per",
                "via",
                "also",
                "already",
                "always",
            }
            insight_keywords = insight_terms - stopwords
            rule_keywords = rule_terms - stopwords
            if insight_keywords and rule_keywords:
                overlap = len(insight_keywords & rule_keywords)
                jaccard = overlap / len(insight_keywords | rule_keywords)
                # If Jaccard > 0.15, the insight shares meaningful topic overlap
                # with a business rule — penalize semantic surprisal by 20%
                if jaccard > 0.15:
                    penalty = jaccard * 0.3  # Up to 30% reduction
                    old_surprisal = semantic_surprisal
                    semantic_surprisal = semantic_surprisal * (1 - penalty)
                    logger.debug(
                        f"[§3] Business rule overlap {jaccard:.2f}: "
                        f"semantic {old_surprisal:.2f} → {semantic_surprisal:.2f}"
                    )

        # Track seen insights from the first non-empty result (transparency context)
        if not seen_insights and similar_beliefs:
            seen_insights = [b["document"] for b in similar_beliefs[:3]]

        # 2. Calculate Bayesian Surprise (per-insight)
        bayesian_surprise = 0.5  # Default moderate surprise

        numbers = re.findall(r"[-+]?\d*\.?\d+", insight_text)
        if numbers:
            metric_value = insight.get("statistic") or insight.get("effect_size")
            if metric_value:
                columns = insight.get("columns", [])
                metric_name = "_".join(columns[:2]) if columns else "unknown_metric"
                bayesian_surprise = bayesian_tracker.update_prior(metric_name, float(metric_value))

        # 3. Compute Hybrid Score (Paper Eq. 6, §III.E)
        hybrid_score = current_alpha * semantic_surprisal + (1 - current_alpha) * bayesian_surprise
        is_novel = hybrid_score >= state["novelty_threshold"]

        logger.debug(
            f"[NOVELTY] Insight: {insight_text[:60]}... "
            f"Sem: {semantic_surprisal:.2f}, "
            f"Bay: {bayesian_surprise:.2f}, "
            f"Hyb: {hybrid_score:.2f}, "
            f"Novel: {is_novel}"
        )

        insight_copy = dict(insight)
        insight_copy["novelty_score"] = hybrid_score
        insight_copy["semantic_surprisal"] = semantic_surprisal
        insight_copy["bayesian_surprise"] = bayesian_surprise

        if is_novel:
            new_approved.append(insight_copy)
        else:
            insight_copy["similar_to"] = seen_insights[0] if seen_insights else None
            new_boring.append(insight_copy)

            # FIX §4: Adapt alpha when insight is rejected by the novelty filter.
            # If Bayesian surprise was high but semantics caught it (low semantic
            # surprisal means the user "already knew" this pattern), raise alpha
            # so semantics are weighted more heavily in future scoring.
            had_high_bayesian = bayesian_surprise > 0.5
            new_alpha = BeliefStore.update_alpha(
                current_alpha=current_alpha,
                was_rejected=True,
                had_high_bayesian=had_high_bayesian,
            )
            if new_alpha != current_alpha:
                logger.debug(
                    f"[NOVELTY] Alpha adapted: {current_alpha:.2f} → {new_alpha:.2f} "
                    f"(bayesian was {'high' if had_high_bayesian else 'low'})"
                )
                current_alpha = new_alpha

    total = len(all_current)
    newly_approved = len(new_approved) - len(state.get("approved_insights", []))
    newly_boring = len(new_boring) - len(state.get("boring_insights", []))
    logger.info(f"[NOVELTY] Scored {total} insights: {newly_approved} novel, {newly_boring} boring")

    # FIX §5: Persist Bayesian priors to MongoDB so they survive server restarts
    # across all replicas (replaces old JSON file approach).
    await bayesian_tracker.persist()

    # Use the last approved insight's scores for top-level fields
    # (these are consumed by downstream nodes for logging, not logic)
    last_approved = new_approved[-1] if new_approved else {}
    any_novel = newly_approved > 0

    return {
        "semantic_surprisal": last_approved.get("semantic_surprisal", 0.0),
        "bayesian_surprise": last_approved.get("bayesian_surprise", 0.0),
        "hybrid_novelty_score": last_approved.get("novelty_score", 0.0),
        "is_novel": any_novel,
        "seen_insights": seen_insights,
        "approved_insights": new_approved,
        "boring_insights": new_boring,
        "alpha": current_alpha,
        "current_question_idx": state["current_question_idx"] + 1,
        "error_count": 0,
        "iteration_count": state["iteration_count"] + 1,
    }


async def fdr_gate_node(state: AgentState) -> Dict[str, Any]:
    """
    FDR Gate: within-family Benjamini-Hochberg over EVERY hypothesis tested
    in the run.

    The agentic graph tests dozens of hypotheses across questions (correlation,
    comparison, trend + subspace expansions). Without global multiple-testing
    control, the run surfaces false positives even when every individual
    p < 0.05 — the classic "testing 100 things finds 5 that look significant
    by chance" failure. The linear EnhancedQUIS path already applies
    within-family FDR; this gate brings the agentic path to parity.

    Approved insights whose run_id does not survive FDR are dropped before
    synthesis. Insights without a run_id (legacy fallback dicts) pass through
    unchanged.
    """
    raw_pvalues = [
        e for e in state.get("raw_insight_pvalues", []) if e.get("p_value") is not None
    ]
    approved = list(state.get("approved_insights", []))
    if not raw_pvalues or not approved:
        return {
            "approved_insights": approved,
            "fdr_surviving_ids": [],
            "fdr_dropped_count": 0,
        }

    from services.analysis.enhanced_quis import QUISStatistics

    families: Dict[str, List[Dict[str, Any]]] = {}
    for entry in raw_pvalues:
        families.setdefault(entry.get("family", "other"), []).append(entry)

    surviving = set()
    for family, entries in families.items():
        entries_sorted = sorted(entries, key=lambda e: e["p_value"])
        pvals = [e["p_value"] for e in entries_sorted]
        mask = QUISStatistics.benjamini_hochberg(pvals, alpha=0.05)
        for entry, is_sig in zip(entries_sorted, mask):
            if is_sig:
                surviving.add(entry["run_id"])

    kept = []
    dropped = 0
    for insight in approved:
        rid = insight.get("run_id")
        if rid is None or rid in surviving:
            kept.append(insight)
        else:
            dropped += 1

    logger.info(
        f"[FDR] {len(surviving)}/{len(raw_pvalues)} hypotheses survive within-family BH; "
        f"{dropped} approved insight(s) dropped"
    )
    return {
        "approved_insights": kept,
        "fdr_surviving_ids": list(surviving),
        "fdr_dropped_count": dropped,
    }


async def synthesizer_node(state: AgentState) -> Dict[str, Any]:
    """
    Synthesizer: Compile approved insights into final response.

    Uses ALL current_insights from the novelty filter, not just the
    first insight per question. This fixes the data loss from the
    old insights[0] bug.
    """
    logger.info("[SYNTHESIZER] Generating final response")

    approved = state.get("approved_insights", [])

    if not approved:
        response = "Analysis complete. No significant novel insights were found for this dataset."
    else:
        lines = [f"## Analysis Results\n\nFound {len(approved)} significant insights:\n"]

        for i, insight in enumerate(approved, 1):
            desc = insight.get("description", "Unknown insight")
            p_val = insight.get("p_value", "N/A")
            effect = insight.get("effect_interpretation", "")
            novelty = insight.get("novelty_score", 0)
            effect_size = insight.get("effect_size", 0)
            sample_size = insight.get("sample_size", 0)
            simpson = insight.get("is_simpson_paradox", False)
            subspace = insight.get("subspace", None)

            lines.append(f"### {i}. {desc}")
            lines.append(f"- **Statistical Significance**: p = {p_val}")
            if effect:
                lines.append(f"- **Effect Size**: {effect} (size: {effect_size:.3f})")
            lines.append(f"- **Novelty Score**: {novelty:.2f}")
            if sample_size:
                lines.append(f"- **Sample Size**: {sample_size:,}")
            if simpson:
                lines.append("- ⚠️ **Simpson's Paradox Detected**")
            if subspace:
                lines.append(f"- **Subspace**: {subspace}")
            lines.append("")

        response = "\n".join(lines)

    boring_count = len(state.get("boring_insights", []))
    rejected_count = len(state.get("rejected_insights", []))
    logger.info(
        f"[SYNTHESIZER] Final: {len(approved)} approved, "
        f"{boring_count} filtered as boring, {rejected_count} rejected"
    )

    return {
        "final_response": response,
        "end_time": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "iteration_count": state["iteration_count"] + 1,
    }


# ============================================================
# ROUTING FUNCTIONS
# ============================================================


def route_after_critic(
    state: AgentState,
) -> Literal["analyst", "novelty_filter", "fdr_gate"]:
    """
    Conditional routing after Critic node.

    Routes:
    - REJECT (critique failed): Back to analyst for retry
    - APPROVE: To novelty filter
    - DONE (all questions answered): To FDR gate then synthesizer

    FIX §2.1 (actual): On REJECT, the analyst node modifies the question with
    the previous failure context (last_error + critic feedback) so the retry
    produces different output instead of re-running the identical question.

    FIX §2.2: When max retries exceeded, we route to fdr_gate if done,
    or back to planner for next question (NOT novelty_filter, which would crash
    trying to parse an empty execution_result).

    FIX §2.3: DONE and max_iterations routes are clearly separated.
    """
    critique = state.get("critique", {})
    error_count = state.get("error_count", 0)
    max_retries = state.get("max_retries", 3)
    current_idx = state.get("current_question_idx", 0)
    total_questions = len(state.get("questions", []))

    # Check if we've exceeded iteration limit
    if state.get("iteration_count", 0) >= state.get("max_iterations", 50):
        logger.warning("[ROUTER] Max iterations reached, forcing FDR gate + synthesis")
        return "fdr_gate"

    # Too many retries on this question - skip to next question
    # FIX §2.2: Route to planner (next question) instead of novelty_filter
    # which would crash on empty/invalid execution_result
    if error_count >= max_retries:
        logger.info(f"[ROUTER] Max retries ({max_retries}) exceeded, skipping question")
        if current_idx >= total_questions - 1:
            return "fdr_gate"
        # Increment current_question_idx in the state update that follows
        # The planner will handle starting the next question
        return "planner"  # Was: "novelty_filter" — this was the bug

    # Critique failed - retry with a modified question
    # FIX §2.1: analyst_node injects last_error + critic suggestions into the
    # question text on retry, so this is a stateful modification, not a
    # same-input loop.
    if not critique.get("passed", True):
        logger.info("[ROUTER] Critique failed, routing to analyst (question will be modified)")
        return "analyst"

    # All questions answered - run FDR gate then synthesize
    if current_idx >= total_questions - 1:
        logger.info("[ROUTER] All questions answered, routing to FDR gate")
        return "fdr_gate"

    # Normal flow - check novelty
    logger.info("[ROUTER] Critique passed, routing to novelty filter")
    return "novelty_filter"


def route_after_novelty(state: AgentState) -> Literal["planner", "viz_designer"]:
    """
    Conditional routing after Novelty Filter.

    FIX §2.4: Returns actual node name strings ("planner", "viz_designer")
    instead of a mislabeled mapping. Previously, the function returned
    "synthesizer" which was mapped to "viz_designer" in the graph builder —
    a load-bearing coincidence that would break on refactoring.

    Routes:
    - More questions to process: Back to planner
    - All questions done: Viz designer then synthesizer
    """
    current_idx = state.get("current_question_idx", 0)
    total_questions = len(state.get("questions", []))

    if current_idx >= total_questions:
        logger.info("[ROUTER] All questions processed, routing to viz_designer")
        return "viz_designer"  # Was: "synthesizer" — mislabeled

    logger.info(
        f"[ROUTER] More questions remaining ({current_idx}/{total_questions}), routing to planner"
    )
    return "planner"


# ============================================================
# VISUALIZATION NODE
# ============================================================


async def viz_designer_node(state: AgentState) -> Dict[str, Any]:
    """
    VIZ DESIGNER: Convert approved insights into Plotly visualization configs.

    FIX §7.1: Per-insight error isolation — a failure for one insight doesn't
    crash the entire node. The dataset load error is also isolated.

    FIX §7.2: Uses aggregation instead of raw data truncation:
    - Scatter: hex-bin or sampled 2K points
    - Bar: top-20 categories via aggregation
    - Line: sorted + downsampled via LTTB

    FIX §7.3: Complete chart type mapping including:
    - group_comparison → grouped_bar
    - subspace_correlation → faceted scatter
    - correlation → scatter
    - trend → line
    All entries in the map are actually produced by InsightGenerator.
    """
    logger.info("[VIZ] Generating visualizations for approved insights")

    import polars as pl

    viz_configs = []
    approved = state.get("approved_insights", [])

    if not approved:
        logger.info("[VIZ] No approved insights to visualize")
        return {"viz_configs": [], "iteration_count": state["iteration_count"] + 1}

    # FIX §7.3: Complete chart type mapping — every entry is actually produced
    chart_type_map = {
        "correlation": "scatter",
        "subspace_correlation": "scatter",  # Was missing — fell through to "bar"
        "group_comparison": "bar",  # Was missing — fell through to "bar"
        "comparison": "bar",
        "trend": "line",
        "distribution": "histogram",
        "anomaly": "box",
        "subspace": "bar",
        "composition": "pie",
        "ranking": "bar",
        "simpson_paradox": "scatter",  # Add for Simpson's paradox insights
    }

    # Try to load dataset with per-insight isolation
    # FIX §7.1: Data load error is isolated — if dataset can't be loaded,
    # we still return an empty viz_configs array without crashing the graph
    try:
        df = await _load_dataset_cached(
            state["dataset_id"],
            state["user_id"],
            tenant_id=state.get("tenant_id", state.get("user_id")),
        )
    except Exception as e:
        logger.warning(f"[VIZ] Failed to load dataset: {e}")
        return {"viz_configs": [], "iteration_count": state["iteration_count"] + 1}

    if df is None:
        logger.warning("[VIZ] Dataset not found, skipping visualization")
        return {"viz_configs": [], "iteration_count": state["iteration_count"] + 1}

    available_columns = list(df.columns)

    # FIX §7.1: Process each insight independently with error isolation
    for i, insight in enumerate(approved):
        try:
            insight_type = insight.get("insight_type", "correlation")
            columns = insight.get("columns", [])
            description = insight.get("description", f"Insight {i + 1}")
            subspace = insight.get("subspace")

            # Validate columns exist
            valid_columns = [c for c in columns if c in available_columns]
            if len(valid_columns) < 1:
                logger.warning(f"[VIZ] No valid columns for insight {i + 1}, skipping")
                continue

            # Apply subspace filter if present
            df_filtered = df
            subspace_label = ""
            if subspace:
                for col, val in subspace.items():
                    if col in df_filtered.columns:
                        df_filtered = df_filtered.filter(pl.col(col) == val)
                        subspace_label = f" (filtered: {col}={val})"

            # Don't try to visualize if filtered dataset is too small
            if len(df_filtered) < 5:
                logger.warning(
                    f"[VIZ] Filtered dataset too small ({len(df_filtered)}) for insight {i + 1}"
                )
                continue

            chart_type = chart_type_map.get(insight_type, "bar")

            # Generate Plotly trace based on chart type
            traces = []
            layout = {
                "title": f"{description[:60]}{'...' if len(description) > 60 else ''}{subspace_label}",
                "paper_bgcolor": "rgba(0,0,0,0)",
                "plot_bgcolor": "rgba(0,0,0,0)",
                "font": {"color": "#e2e8f0"},
                "height": 350,
                "margin": {"t": 50, "b": 50, "l": 60, "r": 20},
            }

            # FIX §7.2: Aggregate instead of truncate raw rows
            SAMPLE_SIZE = 2000  # Max points for scatter

            if chart_type == "scatter" and len(valid_columns) >= 2:
                x_col = valid_columns[0]
                y_col = valid_columns[1]

                # Get clean data
                clean_df = df_filtered.select([x_col, y_col]).drop_nulls()

                if len(clean_df) > SAMPLE_SIZE:
                    # Stratified sampling instead of taking first N rows
                    clean_df = clean_df.sample(n=SAMPLE_SIZE, seed=42)

                traces.append(
                    {
                        "type": "scatter",
                        "mode": "markers",
                        "x": clean_df[x_col].to_list(),
                        "y": clean_df[y_col].to_list(),
                        "marker": {"color": "#8b5cf6", "opacity": 0.7},
                    }
                )
                layout["xaxis"] = {"title": x_col}
                layout["yaxis"] = {"title": y_col}

            elif chart_type == "bar" and len(valid_columns) >= 1:
                # Aggregate by first categorical column (top 20)
                cat_col = valid_columns[0]
                if len(valid_columns) >= 2:
                    val_col = valid_columns[1]
                    agg_df = (
                        df_filtered.group_by(cat_col)
                        .agg(pl.col(val_col).mean().alias("value"))
                        .sort("value", descending=True)
                        .head(20)
                    )
                else:
                    agg_df = (
                        df_filtered.group_by(cat_col)
                        .agg(pl.count().alias("value"))
                        .sort("value", descending=True)
                        .head(20)
                    )

                traces.append(
                    {
                        "type": "bar",
                        "x": agg_df[cat_col].to_list(),
                        "y": agg_df["value"].to_list(),
                        "marker": {"color": "#06b6d4"},
                    }
                )
                layout["xaxis"] = {"title": cat_col}
                layout["yaxis"] = {
                    "title": valid_columns[1] if len(valid_columns) >= 2 else "Count"
                }

            elif chart_type == "line" and len(valid_columns) >= 2:
                # Sort by x column for line chart
                sorted_df = df_filtered.sort(valid_columns[0])

                # FIX §7.2: LTTB-like downsampling for line charts
                x_data = sorted_df[valid_columns[0]].to_list()
                y_data = sorted_df[valid_columns[1]].to_list()

                if len(x_data) > 200:
                    # Simple downsampling: take every nth point
                    step = len(x_data) // 200
                    x_data = x_data[::step]
                    y_data = y_data[::step]

                traces.append(
                    {
                        "type": "scatter",
                        "mode": "lines+markers",
                        "x": x_data[:500],
                        "y": y_data[:500],
                        "line": {"color": "#10b981"},
                    }
                )
                layout["xaxis"] = {"title": valid_columns[0]}
                layout["yaxis"] = {"title": valid_columns[1]}

            elif chart_type == "histogram" and len(valid_columns) >= 1:
                traces.append(
                    {
                        "type": "histogram",
                        "x": df_filtered[valid_columns[0]].drop_nulls().to_list(),
                        "marker": {"color": "#f59e0b"},
                        "nbinsx": 30,  # Fixed bin count for consistency
                    }
                )
                layout["xaxis"] = {"title": valid_columns[0]}
                layout["yaxis"] = {"title": "Frequency"}

            elif chart_type == "box" and len(valid_columns) >= 1:
                traces.append(
                    {
                        "type": "box",
                        "y": df_filtered[valid_columns[0]].drop_nulls().to_list(),
                        "name": valid_columns[0],
                        "marker": {"color": "#ef4444"},
                    }
                )
                layout["yaxis"] = {"title": valid_columns[0]}

            if traces:
                viz_configs.append(
                    {
                        "insight_id": f"insight_{i + 1}",
                        "insight_type": insight_type,
                        "description": description,
                        "data": traces,
                        "layout": layout,
                    }
                )
                logger.info(f"[VIZ] Generated {chart_type} chart for insight {i + 1}")

        except Exception as e:
            # FIX §7.1: Per-insight error isolation
            logger.warning(f"[VIZ] Failed to generate chart for insight {i + 1}: {e}")
            continue

    logger.info(f"[VIZ] Generated {len(viz_configs)} visualizations")
    return {"viz_configs": viz_configs, "iteration_count": state["iteration_count"] + 1}


# ============================================================
# GRAPH CONSTRUCTION
# ============================================================


def create_quis_graph():
    """
    Create the LangGraph state machine for agentic QUIS.

    Returns:
        Compiled StateGraph ready for execution
    """
    if not LANGGRAPH_AVAILABLE:
        raise ImportError(
            "LangGraph is required for agentic QUIS. Install with: pip install langgraph"
        )

    # Create graph builder
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("planner", planner_node)
    builder.add_node("analyst", analyst_node)
    builder.add_node("critic", critic_node)
    builder.add_node("novelty_filter", novelty_filter_node)
    builder.add_node("viz_designer", viz_designer_node)
    builder.add_node("fdr_gate", fdr_gate_node)
    builder.add_node("synthesizer", synthesizer_node)

    # Add edges
    builder.add_edge("planner", "analyst")
    builder.add_edge("analyst", "critic")

    # Conditional edges after critic
    builder.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "analyst": "analyst",
            "novelty_filter": "novelty_filter",
            "fdr_gate": "fdr_gate",
        },
    )

    # Conditional edges after novelty filter
    # FIX §2.4: Route returns actual node name strings, not mislabeled ones
    builder.add_conditional_edges(
        "novelty_filter",
        route_after_novelty,
        {
            "planner": "planner",
            "viz_designer": "viz_designer",  # Direct mapping — no load-bearing coincidence
        },
    )

    # Viz designer → FDR gate → synthesizer (FDR must run once, after ALL
    # questions have been processed and before final synthesis)
    builder.add_edge("viz_designer", "fdr_gate")
    builder.add_edge("fdr_gate", "synthesizer")

    # Synthesizer goes to END
    builder.add_edge("synthesizer", END)

    # Set entry point
    builder.set_entry_point("planner")

    # Compile checkpointer — PostgresSaver if available, MemorySaver fallback
    if _PERSISTENT_CHECKPOINT:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            checkpointer = PostgresSaver.from_conn_string(_CHECKPOINT_DB_URI)
            logger.info(
                "QUIS graph using PostgresSaver checkpoint (%s...)", _CHECKPOINT_DB_URI[:30]
            )
        except Exception:
            logger.warning("PostgresSaver unavailable, falling back to MemorySaver")
            checkpointer = MemorySaver()
    else:
        checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    logger.info("QUIS graph compiled successfully")
    return graph


# ============================================================
# MAIN ENTRY POINT
# ============================================================


async def run_agentic_quis(
    dataset_id: str,
    user_id: str,
    data_schema: str,
    sample_rows: str,
    row_count: int,
    column_count: int,
    novelty_threshold: float = 0.35,
    thread_id: str = None,
    belief_context: str = "",
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the agentic QUIS analysis pipeline.

    FIX: Uses active_beliefs (user's business rules) as an immutable input,
    separate from seen_insights which tracks what's visually similar.

    Args:
        dataset_id: ID of the dataset to analyze
        user_id: User ID for Belief Graph retrieval
        data_schema: JSON string of column schema
        sample_rows: Text preview of data
        row_count: Total rows
        column_count: Total columns
        novelty_threshold: Minimum novelty to present (default 0.35)
        thread_id: Optional thread ID for checkpointing
        belief_context: Active business rules string from BeliefService
        tenant_id: Optional tenant ID for multi-tenant cache scoping

    Returns:
        Dictionary containing:
        - final_response: Synthesized markdown response
        - approved_insights: List of novel insights
        - boring_insights: List of filtered insights
        - stats: Execution statistics
    """
    import uuid
    import asyncio

    QUIS_TIMEOUT_SECONDS = 120

    # Create graph
    graph = create_quis_graph()

    # Create initial state with belief context as active_beliefs
    # active_beliefs = user's true business rules (immutable input)
    # This is NEVER overwritten by seen_insights (output from novelty filter)
    belief_list = [belief_context] if belief_context else []

    initial_state = create_initial_state(
        dataset_id=dataset_id,
        user_id=user_id,
        data_schema=data_schema,
        sample_rows=sample_rows,
        row_count=row_count,
        column_count=column_count,
        novelty_threshold=novelty_threshold,
    )
    if belief_list:
        initial_state["active_beliefs"] = belief_list  # Was: "belief_context"

    if tenant_id:
        initial_state["tenant_id"] = tenant_id

    # Configuration with thread ID
    config = {"configurable": {"thread_id": thread_id or str(uuid.uuid4())}}

    # Run graph with timeout
    logger.info(f"Starting agentic QUIS for dataset {dataset_id}")

    try:
        final_state = await asyncio.wait_for(
            graph.ainvoke(initial_state, config), timeout=QUIS_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        logger.warning(f"QUIS analysis timed out after {QUIS_TIMEOUT_SECONDS}s")
        return {
            "final_response": "Analysis timed out. Please try with a smaller dataset.",
            "approved_insights": [],
            "boring_insights": [],
            "rejected_insights": [],
            "viz_configs": [],
            "stats": {"error": "timeout", "timeout_seconds": QUIS_TIMEOUT_SECONDS},
        }

    # Also catch asyncio.CancelledError (from timeout propagation)
    except asyncio.CancelledError:
        logger.warning(f"QUIS analysis cancelled after timeout")
        return {
            "final_response": "Analysis was cancelled.",
            "approved_insights": [],
            "boring_insights": [],
            "rejected_insights": [],
            "viz_configs": [],
            "stats": {"error": "cancelled"},
        }

    # Extract results from final state
    result_state = final_state if isinstance(final_state, dict) else {}

    return {
        "final_response": result_state.get("final_response", "Analysis complete."),
        "approved_insights": result_state.get("approved_insights", []),
        "boring_insights": result_state.get("boring_insights", []),
        "rejected_insights": result_state.get("rejected_insights", []),
        "viz_configs": result_state.get("viz_configs", []),
        "stats": {
            "total_questions": len(result_state.get("questions", [])),
            "novel_insights": len(result_state.get("approved_insights", [])),
            "filtered_insights": len(result_state.get("boring_insights", [])),
            "rejected_insights": len(result_state.get("rejected_insights", [])),
            "hypotheses_tested": len(result_state.get("raw_insight_pvalues", [])),
            "fdr_dropped": result_state.get("fdr_dropped_count", 0),
            "iterations": result_state.get("iteration_count", 0),
            "start_time": result_state.get("start_time"),
            "end_time": result_state.get("end_time"),
        },
    }


# ============================================================
# HIGH-LEVEL ANALYSIS ENTRY POINT (For Chat Integration)
# ============================================================


async def run_quis_analysis(
    dataset_id: str,
    user_id: str,
    query: str = None,
    novelty_threshold: float = 0.35,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    High-level entry point for QUIS analysis.

    Handles dataset loading from MongoDB and state initialization.
    FIX: Passes tenant_id for multi-tenant cache scoping and uses
    active_beliefs for business rules (separate from seen_insights).

    Args:
        dataset_id: MongoDB ObjectId of the dataset to analyze
        user_id: User ID for access control and Belief Graph
        query: Optional user query to guide analysis focus
        novelty_threshold: Minimum novelty score (0-1) to present insight
        tenant_id: Optional tenant ID for multi-tenant cache scoping

    Returns:
        Dict containing:
        - response: Synthesized markdown response with insights
        - charts: List of Plotly chart configurations
        - insights: List of approved insight objects
        - stats: Execution statistics

    Raises:
        HTTPException: If dataset not found or still processing
    """
    import polars as pl
    import json
    from fastapi import HTTPException
    from db.database import get_database
    from datetime import datetime

    start_time = datetime.now(timezone.utc).replace(tzinfo=None)

    # Get dataset from MongoDB — _id is stored as UUID string; ObjectId is legacy fallback.
    # Strictly workspace-scoped read (tenant_id → workspace, else personal).
    from services.datasets.enhanced_dataset_service import enhanced_dataset_service

    dataset = await enhanced_dataset_service.get_dataset_doc(
        dataset_id, user_id, workspace_id=tenant_id
    )

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = dataset.get("file_path")
    if not file_path:
        raise HTTPException(status_code=409, detail="Dataset is still processing")

    # Use parquet_path if available, fall back to file_path
    parquet_path = dataset.get("parquet_path")
    data_path = parquet_path if parquet_path and Path(parquet_path).exists() else file_path

    # Build lightweight schema summary using lazy loading
    try:
        lf = pl.scan_parquet(data_path)
        schema = {col: str(dtype) for col, dtype in lf.schema.items()}

        # Get sample rows (limit to 5 for context)
        sample_df = lf.limit(5).collect()
        sample_rows = sample_df.to_pandas().to_string()

        # Get row count from metadata or estimate
        metadata = dataset.get("metadata", {})
        row_count = metadata.get("dataset_overview", {}).get("total_rows", 0)
        if not row_count:
            row_count = lf.select(pl.count()).collect().item()

        column_count = len(schema)

    except Exception as e:
        logger.error(f"Failed to load dataset schema: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load dataset: {str(e)}")

    # Load active beliefs for business rule context → stored as active_beliefs
    # FIX §3: Unified belief context — merges MongoDB business rules (BeliefService)
    # with ChromaDB promoted beliefs (PassiveBeliefIngestion.get_novelty_context).
    # This ensures the analyst prompt sees BOTH explicit user corrections AND
    # implicitly learned beliefs, and the novelty filter checks against both.
    active_beliefs = ""

    # 1. Load MongoDB business rules (explicit user corrections)
    try:
        from services.memory.belief_service import BeliefService

        belief_service = BeliefService(db)
        active_beliefs = await belief_service.format_for_prompt(user_id, str(dataset_id))
        if active_beliefs:
            logger.info(f"[§3] Loaded MongoDB business rules: {len(active_beliefs)} chars")
    except Exception as e:
        logger.warning(f"[§3] Failed to load MongoDB beliefs (non-critical): {e}")

    # 2. Load ChromaDB promoted beliefs (implicitly learned from passive ingestion)
    try:
        from agents.belief.belief_store import get_belief_store, PassiveBeliefIngestion

        chroma_store = get_belief_store()
        chroma_beliefs = await PassiveBeliefIngestion.get_novelty_context(
            chroma_store, user_id, query or "", max_beliefs=5
        )
        if chroma_beliefs:
            chroma_section = "\n## Learned Knowledge — from your previous interactions:\n"
            for i, b in enumerate(chroma_beliefs, 1):
                chroma_section += f"{i}. {b}\n"
            if active_beliefs:
                active_beliefs += chroma_section
            else:
                active_beliefs = chroma_section
            logger.info(f"[§3] Merged {len(chroma_beliefs)} ChromaDB promoted beliefs")
    except Exception as e:
        logger.warning(f"[§3] Failed to load ChromaDB beliefs (non-critical): {e}")

    # Run the agentic QUIS pipeline
    logger.info(f"Starting QUIS analysis for dataset {dataset_id} (user: {user_id})")

    try:
        result = await run_agentic_quis(
            dataset_id=str(dataset_id),
            user_id=user_id,
            data_schema=json.dumps(schema),
            sample_rows=sample_rows,
            row_count=row_count,
            column_count=column_count,
            novelty_threshold=novelty_threshold,
            belief_context=active_beliefs,
            tenant_id=tenant_id,
        )
    except ImportError as e:
        logger.warning(f"LangGraph not available: {e}")
        return {
            "response": "Deep analysis requires LangGraph. Please install with: pip install langgraph",
            "charts": [],
            "insights": [],
            "stats": {"error": "langgraph_not_installed"},
            "analysis_type": "error",
        }
    except Exception as e:
        logger.error(f"QUIS analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    end_time = datetime.now(timezone.utc).replace(tzinfo=None)
    execution_time = (end_time - start_time).total_seconds()

    # Format response for chat integration
    return {
        "response": result.get("final_response", "Analysis complete."),
        "charts": result.get("viz_configs", []),
        "insights": result.get("approved_insights", []),
        "boring_filtered": len(result.get("boring_insights", [])),
        "rejected_count": len(result.get("rejected_insights", [])),
        "stats": {**result.get("stats", {}), "execution_time_seconds": execution_time},
        "analysis_type": "deep_quis",
    }
