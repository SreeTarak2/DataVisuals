"""
semantic — Governed Metric Definition & Resolution Layer
=========================================================

Transforms DataSage's feedback infrastructure into a governed execution engine.

Architecture:
  MetricDefinitionStore    — Unified repository of metric definitions from ALL sources
  MetricResolutionService  — NLQ → metric resolution middleware
  QueryIntent              — Structured intent schema (LLM as translator)
  MetricSQLCompiler        — Deterministic SQL compiler from structured intent
  IntentExtractor          — LLM-based NLQ → structured intent extraction
  SemanticQueryService     — Production-grade orchestrator (single execution path)

Flow (production-grade):
  NLQ → IntentExtractor.extract() → structured QueryIntent
    → validate_intent() against schema + definitions
    → MetricResolutionService.resolve() + MetricDefinitionStore.get_definitions()
    → MetricSQLCompiler.compile() → deterministic SQL
    → execute_sql() → interpret_results()
"""

from .metric_definition_store import (
    MetricDefinition,
    MetricDefinitionSource,
    MetricDefinitionStore,
    metric_definition_store,
)
from .metric_resolution_service import (
    ResolvedMetric,
    MetricResolutionResult,
    MetricResolutionService,
    metric_resolution_service,
)
from .query_intent import (
    QueryIntent,
    MetricIntent,
    DimensionIntent,
    FilterIntent,
    FilterOperator,
    OrderIntent,
    OrderDirection,
    TimeGrain,
    IntentValidationResult,
    validate_intent,
)
from .sql_compiler import MetricSQLCompiler, CompilationError, metric_sql_compiler
from .intent_extractor import IntentExtractor, intent_extractor
from .semantic_query_service import SemanticQueryService, SemanticQueryResult, semantic_query_service
from .validators import (
    IntentValidator,
    SQLValidator,
    ValidationOrchestrator,
    ValidationGateResult,
    EndToEndValidationResult,
    intent_validator,
    sql_validator,
    validation_orchestrator,
)

from .checkpoint_gate import (
    CheckpointGate,
    CheckpointDecision,
    PendingQuery,
    checkpoint_gate,
)

__all__ = [
    "MetricDefinition",
    "MetricDefinitionSource",
    "MetricDefinitionStore",
    "metric_definition_store",
    "ResolvedMetric",
    "MetricResolutionResult",
    "MetricResolutionService",
    "metric_resolution_service",
    "QueryIntent",
    "MetricIntent",
    "DimensionIntent",
    "FilterIntent",
    "FilterOperator",
    "OrderIntent",
    "OrderDirection",
    "TimeGrain",
    "IntentValidationResult",
    "validate_intent",
    "MetricSQLCompiler",
    "CompilationError",
    "metric_sql_compiler",
    "IntentExtractor",
    "intent_extractor",
    "SemanticQueryService",
    "SemanticQueryResult",
    "semantic_query_service",
    "CheckpointGate",
    "CheckpointDecision",
    "PendingQuery",
    "checkpoint_gate",
]
