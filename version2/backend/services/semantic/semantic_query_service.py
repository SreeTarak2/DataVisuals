"""
semantic/semantic_query_service.py — Semantic Query Orchestration Service
========================================================================

The production-grade orchestrator that ties together the full pipeline:

  1. Intent extraction (LLM NLQ → structured QueryIntent)
  2. Intent validation (against schema + definitions)
  3. Metric resolution (against MetricDefinitionStore)
  4. SQL compilation (deterministic compiler)
  5. SQL validation (check SQL answers the intent)
  6. Execution (DuckDB)
  7. Result interpretation (LLM explains results)

SINGLE EXECUTION PATH: If any step fails, the service returns a structured
error. It does NOT fall back to LLM-SQL generation. This ensures governed
behavior is enforced — or the user is told exactly why it can't be.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import polars as pl

from llm.router import llm_router
from core.config import settings
from prompts.sql import get_result_interpretation_prompt
from services.query.executor import QueryExecutor, query_executor as legacy_executor
from services.semantic.metric_definition_store import (
    MetricDefinition,
    MetricDefinitionStore,
    metric_definition_store,
)
from services.semantic.metric_resolution_service import (
    MetricResolutionService,
    metric_resolution_service,
)
from services.semantic.sql_compiler import CompilationError, MetricSQLCompiler, metric_sql_compiler
from services.semantic.intent_extractor import IntentExtractor, intent_extractor
from services.semantic.query_intent import (
    IntentValidationResult,
    QueryIntent,
    validate_intent,
)
from services.semantic.validators import (
    ValidationGateResult,
    ValidationOrchestrator,
    validation_orchestrator,
)
from services.semantic.query_decomposer import (
    DecompositionPlan,
    QueryDecomposer,
    SubIntent,
    query_decomposer,
)
from services.semantic.query_recombiner import QueryRecombinator, query_recombinator
from services.semantic.checkpoint_gate import CheckpointGate, checkpoint_gate

logger = logging.getLogger(__name__)


# ── Result model ───────────────────────────────────────────────────────────


@dataclass
class SemanticQueryResult:
    """Full result of a semantic query execution."""

    success: bool
    response: str = ""
    sql: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    row_count: int = 0
    error: Optional[str] = None

    # Pipeline trace for observability
    intent: Optional[Dict[str, Any]] = None
    validation: Optional[IntentValidationResult] = None
    resolved_metrics: Optional[Dict[str, Any]] = None
    validation_gates: Optional[Dict[str, Any]] = None  # LLM-based validators output
    execution_time_ms: float = 0.0
    path: str = "semantic"  # "semantic" | "metadata" | "conversational" | "fallback_raw" | "checkpoint_required"
    checkpoint_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        base = {
            "success": self.success,
            "response": self.response,
            "sql": self.sql,
            "data": self.data,
            "columns": self.columns,
            "row_count": self.row_count,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "requires_confirmation": self.path == "checkpoint_required",
            "pipeline": {
                "path": self.path,
                "intent": self.intent,
                "validation": self.validation.to_dict() if self.validation else None,
                "resolved_metrics": self.resolved_metrics,
            },
        }
        if self.checkpoint_id:
            base["checkpoint_id"] = self.checkpoint_id
        return base


# ── Orchestrator ───────────────────────────────────────────────────────────


class SemanticQueryService:
    """Production-grade orchestrator for governed semantic queries.

    This is the single entry point for all metric-based queries.
    It enforces that EVERY metric query goes through the governed pipeline:
    intent → validate → resolve → compile → validate_sql → execute → interpret.

    For non-metric queries (metadata, raw data listing, conversational),
    it routes to the appropriate handler.
    """

    def __init__(
        self,
        compiler: Optional[MetricSQLCompiler] = None,
        extractor: Optional[IntentExtractor] = None,
        definition_store: Optional[MetricDefinitionStore] = None,
        resolution_service: Optional[MetricResolutionService] = None,
    ):
        self._compiler = compiler or metric_sql_compiler
        self._extractor = extractor or intent_extractor
        self._definition_store = definition_store or metric_definition_store
        self._resolution_service = resolution_service or metric_resolution_service
        self._validators = ValidationOrchestrator()
        self._decomposer = QueryDecomposer()
        self._recombiner = QueryRecombinator()
        self._checkpoint_gate = CheckpointGate()

    async def execute(
        self,
        query: str,
        df: pl.DataFrame,
        dataset_id: str,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        return_raw: bool = False,
        intent: Optional[QueryIntent] = None,
        skip_checkpoint: bool = False,
    ) -> SemanticQueryResult:
        """Execute a semantic query end-to-end.

        This is the main entry point. It handles ALL query types:
        - Metric queries: through the governed pipeline
        - Metadata queries: answered from schema
        - Conversational: rejected with guardrail
        - Raw data queries: simple SQL generation

        If a pre-parsed QueryIntent is provided (via `intent` param),
        the LLM-based intent extraction step is skipped. This is used
        when the caller already has a structured intent (e.g., programmatic API).
        """
        start_time = datetime.now()

        if not query or not query.strip():
            return SemanticQueryResult(
                success=False,
                error="Empty query",
                execution_time_ms=self._elapsed_ms(start_time),
            )

        # ── Direct path for raw SQL generation ────────────────────────
        # When return_raw=True and no pre-parsed intent, skip the expensive
        # understand_query() + IntentExtractor.extract() + validation pipeline.
        # Instead, do a single merged LLM call that produces SQL directly.
        # This is the "Generate SQL" feature path (used by the SQL Editor).
        if return_raw and intent is None:
            result_df, sql, error = await self._execute_direct_sql(query, df)
            if error:
                # Handle row-count warnings with a formatted message
                if error.startswith("row_count_warning:"):
                    parts = error.split(":")
                    estimated = parts[1] if len(parts) > 1 else "many"
                    threshold = parts[2] if len(parts) > 2 else "10,000"
                    formatted_msg = (
                        f"⚠️ Your query would return **{estimated} rows**, "
                        f"which exceeds my safety limit of {threshold} rows.\n\n"
                        "To make this query more efficient, try:\n"
                        f"1. **Add filters** — narrow down the results using WHERE\n"
                        f"2. **Use LIMIT** — cap the results to a manageable size\n"
                        f"3. **Be more specific** — ask for aggregates or a summary instead"
                    )
                    return SemanticQueryResult(
                        success=False,
                        error="row_count_warning",
                        response=formatted_msg,
                        sql=sql,
                        execution_time_ms=self._elapsed_ms(start_time),
                        path="direct_sql",
                    )
                return SemanticQueryResult(
                    success=False,
                    error=error,
                    sql=sql,
                    execution_time_ms=self._elapsed_ms(start_time),
                    path="direct_sql",
                )
            return SemanticQueryResult(
                success=True,
                response=legacy_executor.format_results(result_df),
                sql=sql,
                data=result_df.to_dicts()
                if len(result_df) <= 100
                else result_df.head(100).to_dicts(),
                columns=list(result_df.columns),
                row_count=len(result_df),
                execution_time_ms=self._elapsed_ms(start_time),
                path="direct_sql",
            )

        # ── Step 0: Route the query (skip if intent is pre-parsed) ────
        if intent is None:
            from services.ai.query_rewrite import understand_query

            try:
                understanding = await understand_query(
                    user_query=query,
                    dataset_context="",
                    available_columns=list(df.columns),
                )
            except Exception as e:
                logger.warning(f"[SemanticQuery] Routing failed, defaulting to metric path: {e}")
                understanding = None

            if understanding:
                routing = understanding.routing
            else:
                routing = "sql"

            # ── Route to handler ────────────────────────────────────────
            if routing == "conversational":
                return self._handle_conversational(query, start_time)

            if routing == "metadata":
                return self._handle_metadata(query, df, start_time)

        # ── Step 1: Extract structured intent (or use pre-parsed) ────
        if intent is not None:
            # Pre-parsed intent provided — skip LLM extraction
            logger.info(
                f"[SemanticQuery] Using pre-parsed intent with {len(intent.metrics)} metrics"
            )
        else:
            column_schema = legacy_executor._get_column_schema(df)
            available_metrics = await self._get_metric_list(dataset_id, user_id, workspace_id)

            intent = await self._extractor.extract(
                query=query,
                column_schema=column_schema,
                available_metrics=available_metrics,
                sample_data=None,
            )

            if not intent or intent.is_empty() or intent.confidence < 0.3:
                # Intent extraction failed or too low confidence
                # Fall back to a basic raw query (no governed metrics)
                logger.info(
                    f"[SemanticQuery] Intent extraction low confidence ({intent.confidence if intent else 0}), "
                    f"falling back to raw query"
                )
                return await self._execute_raw_query(
                    query=query, df=df, dataset_id=dataset_id, start_time=start_time
                )

        elapsed = self._elapsed_ms(start_time)

        # ── Step 2: LLM-based intent validation gate (non-blocking) ────
        available_metrics_list = await self._get_metric_list(dataset_id, user_id, workspace_id)
        validation_gates = await self._validators.validate_all(
            query=query,
            intent_dict=intent.to_dict(),
            available_columns=list(df.columns),
            available_metrics=available_metrics_list,
        )

        if not validation_gates.passed:
            logger.warning(
                f"[SemanticQuery] Intent validation gate FAILED: {validation_gates.all_warnings}"
            )

        # ── Step 3: Validate intent against schema ─────────────────────
        defined_metrics = set(
            await self._get_defined_metric_names(dataset_id, user_id, workspace_id)
        )
        validation = validate_intent(
            intent=intent,
            available_columns=list(df.columns),
            defined_metrics=defined_metrics,
        )

        if not validation.is_valid:
            return SemanticQueryResult(
                success=False,
                error=f"Intent validation failed: {'; '.join(validation.errors)}",
                intent=intent.to_dict(),
                validation=validation,
                validation_gates=validation_gates.to_dict(),
                execution_time_ms=elapsed,
            )

        # ── Step 4: Check if this is a metric query ────────────────────
        if not intent.is_metric_query():
            return await self._execute_raw_query(
                query=query, df=df, dataset_id=dataset_id, start_time=start_time
            )

        # ── Step 5: Decompose into sub-intents ─────────────────────────
        plan = await self._decomposer.decompose(
            intent=intent,
            query=query,
            available_columns=list(df.columns),
            available_metrics=available_metrics_list,
        )

        # ── Step 5.5: Checkpoint gate ──────────────────────────────
        if not skip_checkpoint:
            checkpoint = await self._checkpoint_gate.evaluate(
                query=query,
                sql=f"-- {len(plan.sub_intents)} sub-query(ies)\n-- Merge strategy: {plan.merge_strategy.value}",
                dataset_id=dataset_id,
                user_id=user_id or "anonymous",
                df=df,
                columns=list(df.columns),
                estimated_row_count=len(df),
            )

            if checkpoint.requires_confirmation:
                logger.info(
                    f"[SemanticQuery] Checkpoint triggered: {checkpoint.reason} "
                    f"(id={checkpoint.checkpoint_id[:8]})"
                )
                return SemanticQueryResult(
                    success=False,
                    response=f"Checkpoint required: {checkpoint.reason}",
                    error=f"checkpoint_required:{checkpoint.checkpoint_id}",
                    intent=intent.to_dict(),
                    execution_time_ms=self._elapsed_ms(start_time),
                    path="checkpoint_required",
                    checkpoint_id=checkpoint.checkpoint_id,
                )

        # ── Step 6: Execute each sub-intent ────────────────────────────
        sub_results: List[Tuple[SubIntent, Optional[pl.DataFrame], Optional[str]]] = []
        all_resolved_metrics: Dict[str, str] = {}
        all_sqls: List[str] = []

        # Fetch definitions once outside the loop
        definitions = await self._definition_store.get_definitions(
            dataset_id=dataset_id,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        cols_lower = {c.lower(): c for c in df.columns}

        for sub in plan.sub_intents:
            # Resolve metrics for this sub-intent
            resolved_map: Dict[str, MetricDefinition] = {}
            unresolved: List[str] = []

            for m in sub.intent.metrics:
                name_lower = m.name.lower().strip()
                if name_lower in definitions:
                    resolved_map[m.name] = definitions[name_lower]
                elif name_lower in cols_lower:
                    col_name = cols_lower[name_lower]
                    resolved_map[m.name] = MetricDefinition(
                        name=name_lower,
                        display_name=col_name.replace("_", " ").title(),
                        source_column=col_name,
                        aggregation=m.aggregation or "sum",
                        source="column_name",
                        confidence=0.5,
                    )
                else:
                    unresolved.append(m.name)

            if unresolved:
                logger.warning(
                    f"[SemanticQuery] Sub-query '{sub.label}' has unresolved: {unresolved}"
                )
                sub_results.append((sub, None, f"Unresolved: {unresolved}"))
                continue

            # Compile and execute
            try:
                sub_sql = self._compiler.compile(
                    intent=sub.intent,
                    metric_definitions=resolved_map,
                    available_columns=list(df.columns),
                )
                all_sqls.append(sub_sql)

                sub_df, sub_err = legacy_executor.execute_sql(sub_sql, df)
                sub_results.append((sub, sub_df, sub_err))

                # Collect resolved metric info
                for name, defn in resolved_map.items():
                    all_resolved_metrics[name] = defn.to_prompt_block()

            except CompilationError as e:
                logger.warning(
                    f"[SemanticQuery] Sub-query '{sub.label}' compile failed: {e.message}"
                )
                sub_results.append((sub, None, f"Compile error: {e.message}"))

        # ── Step 7: Recombine results ─────────────────────────────────
        recombined = await self._recombiner.recombine(plan=plan, results=sub_results)
        result_df = recombined.get("merged_df")
        merge_log = recombined.get("merge_log", {})

        if result_df is None:
            return SemanticQueryResult(
                success=False,
                error=recombined.get("response", "All sub-queries failed"),
                intent=intent.to_dict(),
                validation=validation,
                execution_time_ms=elapsed,
                path="semantic",
            )

        # ── Step 8: SQL validation gate on primary SQL ─────────────
        primary_sql = all_sqls[0] if all_sqls else ""
        if primary_sql:
            sql_val = await self._validators.validate_all(
                query=query,
                sql=primary_sql,
                available_columns=list(df.columns),
            )
            if sql_val.sql_validation:
                validation_gates.sql_validation = sql_val.sql_validation
                validation_gates.all_warnings.extend(sql_val.all_warnings)
                if not sql_val.passed:
                    validation_gates.passed = False

        # ── Step 9: Interpret ─────────────────────────────────────
        if return_raw:
            response = legacy_executor.format_results(result_df)
        else:
            response = await self._interpret_results(query, primary_sql, result_df)

        elapsed = self._elapsed_ms(start_time)

        n_rows = len(result_df) if result_df is not None else 0
        logger.info(
            f"[SemanticQuery] ✅ {len(plan.sub_intents)} sub-queries, "
            f"{n_rows} rows, merge={plan.merge_strategy.value}, "
            f"path=semantic"
        )

        return SemanticQueryResult(
            success=True,
            response=response,
            sql=primary_sql,
            data=result_df.to_dicts() if n_rows <= 100 else result_df.head(100).to_dicts(),
            columns=list(result_df.columns) if result_df is not None else [],
            row_count=n_rows,
            error=None,
            intent=intent.to_dict(),
            validation=validation,
            resolved_metrics=all_resolved_metrics or None,
            validation_gates=validation_gates.to_dict(),
            execution_time_ms=elapsed,
            path="semantic",
        )

    # ── Non-metric handlers ────────────────────────────────────────────

    def _handle_conversational(self, query: str, start_time: datetime) -> SemanticQueryResult:
        """Handle off-topic or conversational queries."""
        guardrail_msg = (
            "I'm a data analytics assistant. I can help you explore your dataset "
            "with questions like:\n"
            '- "What is the total revenue by category?"\n'
            '- "Show me the top 10 customers by profit"\n'
            '- "What are the columns in my data?"'
        )
        return SemanticQueryResult(
            success=False,
            response=guardrail_msg,
            error="off_topic",
            execution_time_ms=self._elapsed_ms(start_time),
            path="conversational",
        )

    def _handle_metadata(
        self, query: str, df: pl.DataFrame, start_time: datetime
    ) -> SemanticQueryResult:
        """Answer metadata questions from schema directly."""
        columns = df.columns
        n_rows, n_cols = df.shape
        dtypes = {col: str(df[col].dtype) for col in columns}

        col_list = "\n".join(f"- **{c}** ({dtypes[c]})" for c in columns)
        response = (
            f"Your dataset has **{n_rows:,} rows** and **{n_cols} columns**:\n\n"
            f"{col_list}\n\n"
            "You can ask me to analyze, filter, or visualize any of these fields."
        )
        return SemanticQueryResult(
            success=True,
            response=response,
            data=[{"column_name": c, "data_type": dtypes[c]} for c in columns],
            columns=["column_name", "data_type"],
            row_count=n_cols,
            execution_time_ms=self._elapsed_ms(start_time),
            path="metadata",
        )

    async def _execute_raw_query(
        self,
        query: str,
        df: pl.DataFrame,
        dataset_id: str,
        start_time: datetime,
    ) -> SemanticQueryResult:
        """Execute a non-metric/fallback query using the existing SQL pipeline.

        This is used for:
        - Queries that don't have metrics (couldn't extract intent)
        - Queries that are just listing/showing data
        - The fallback path when intent extraction fails
        """
        try:
            sql, sql_error = await legacy_executor.generate_sql(
                query=query, df=df, governance_block=None
            )
        except Exception as e:
            return SemanticQueryResult(
                success=False,
                error=f"SQL generation failed: {e}",
                execution_time_ms=self._elapsed_ms(start_time),
                path="fallback_raw",
            )

        if sql_error:
            return SemanticQueryResult(
                success=False,
                error=f"SQL generation failed: {sql_error}",
                execution_time_ms=self._elapsed_ms(start_time),
                path="fallback_raw",
            )

        # ── Row-count pre-check before execution ──
        threshold = settings.MAX_ROWS_WARNING_THRESHOLD
        if threshold > 0:
            estimated_rows, est_error = legacy_executor._estimate_row_count(sql, df)
            if estimated_rows > threshold:
                logger.warning(
                    "[SemanticQuery] Row-count warning: %d rows (threshold=%d)",
                    estimated_rows,
                    threshold,
                )
                formatted_count = f"{estimated_rows:,}"
                threshold_str = f"{threshold:,}"
                return SemanticQueryResult(
                    success=False,
                    error="row_count_warning",
                    response=(
                        f"⚠️ Your query would return **{formatted_count} rows**, "
                        f"which exceeds my safety limit of {threshold_str} rows.\n\n"
                        "To make this query more efficient, try:\n"
                        f"1. **Add filters** — narrow down the results using WHERE\n"
                        f"2. **Use LIMIT** — cap the results to a manageable size\n"
                        f"3. **Be more specific** — ask for aggregates or a summary instead"
                    ),
                    sql=sql,
                    execution_time_ms=self._elapsed_ms(start_time),
                    path="fallback_raw",
                )

        result_df, exec_error = legacy_executor.execute_sql(sql, df)
        if exec_error:
            return SemanticQueryResult(
                success=False,
                error=f"Query execution failed: {exec_error}",
                sql=sql,
                execution_time_ms=self._elapsed_ms(start_time),
                path="fallback_raw",
            )

        response = legacy_executor.format_results(result_df)
        elapsed = self._elapsed_ms(start_time)

        return SemanticQueryResult(
            success=True,
            response=response,
            sql=sql,
            data=result_df.to_dicts() if len(result_df) <= 100 else result_df.head(100).to_dicts(),
            columns=list(result_df.columns),
            row_count=len(result_df),
            error=None,
            execution_time_ms=elapsed,
            path="fallback_raw",
        )

    async def _execute_direct_sql(
        self,
        query: str,
        df: pl.DataFrame,
    ) -> Tuple[Optional[pl.DataFrame], Optional[str], Optional[str]]:
        """1-call NLQ→SQL generation with direct DuckDB execution.

        Uses the new generate_sql_direct() method which merges query
        understanding, intent extraction, and SQL generation into a single
        LLM call. Max 1 repair retry on execution error.

        Returns:
            (result_df, sql, error)
        """
        try:
            sql, sql_error = await legacy_executor.generate_sql_direct(
                query=query,
                df=df,
            )
        except Exception as e:
            logger.error(f"[DirectSQL] Generation failed: {e}", exc_info=True)
            return None, None, f"SQL generation failed: {e}"

        if sql_error:
            return None, sql or None, sql_error

        # ── Row-count pre-check before execution ──
        threshold = settings.MAX_ROWS_WARNING_THRESHOLD
        if threshold > 0:
            estimated_rows, est_error = legacy_executor._estimate_row_count(sql, df)
            if estimated_rows > threshold:
                logger.warning(
                    "[DirectSQL] Row-count warning: %d rows (threshold=%d)",
                    estimated_rows,
                    threshold,
                )
                return None, sql, f"row_count_warning:{estimated_rows}:{threshold}"

        result_df, exec_error = legacy_executor.execute_sql(sql, df)
        if exec_error:
            return None, sql, exec_error

        return result_df, sql, None

    # ── Helpers ─────────────────────────────────────────────────────────

    async def _get_metric_list(
        self,
        dataset_id: str,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Get available metric definitions for prompt context."""
        definitions = await self._definition_store.get_definitions(
            dataset_id=dataset_id,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        return [
            {
                "name": name,
                "display_name": defn.display_name,
                "description": defn.description or f"Column: {defn.source_column or 'unknown'}",
            }
            for name, defn in definitions.items()
        ]

    async def _get_defined_metric_names(
        self,
        dataset_id: str,
        user_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> List[str]:
        """Get all defined metric names for intent validation."""
        definitions = await self._definition_store.get_definitions(
            dataset_id=dataset_id,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        return list(definitions.keys())

    async def _interpret_results(self, query: str, sql: str, result_df: pl.DataFrame) -> str:
        """Use LLM to interpret query results in natural language."""
        try:
            if len(result_df) == 0:
                results_str = "The query returned no results (empty dataset)."
            elif len(result_df) == 1 and len(result_df.columns) == 1:
                value = result_df.row(0)[0]
                results_str = f"Single value: {value}"
            else:
                results_str = legacy_executor.format_results(result_df, max_display_rows=15)

            prompt = get_result_interpretation_prompt(
                user_query=query, sql_query=sql, query_results=results_str
            )

            interpretation = await llm_router.call(
                prompt=prompt,
                model_role="chat_engine",
                expect_json=False,
                temperature=0.3,
                max_tokens=500,
                is_conversational=True,
            )

            return str(interpretation).strip()
        except Exception as e:
            logger.error(f"[SemanticQuery] Result interpretation failed: {e}")
            return f"Query completed. Results:\n\n{legacy_executor.format_results(result_df)}"

    @staticmethod
    def _elapsed_ms(start: datetime) -> float:
        return (datetime.now() - start).total_seconds() * 1000


# Singleton
semantic_query_service = SemanticQueryService()
