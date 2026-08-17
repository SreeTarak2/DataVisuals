"""
Chat Pipeline — Context Loader
===============================

Gathers everything the agent needs before synthesis:
  - Dataset metadata from MongoDB
  - RAG context via FAISS vector search (with reranking)
  - Memory injection (beliefs + conversation history)
  - Privacy controls (column redaction, PII detection)
  - Context window optimization

Replaces:
  - ai_service: _get_rag_context(), _apply_privacy_controls(), ContextWindowManager
  - copilot_service: inline dataset loading
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from services.chat.models import ContextPackage, MemoryContext

logger = logging.getLogger(__name__)

# =============================================================================
# CONTEXT WINDOW MANAGER  (moved from ai_service.py)
# =============================================================================


class ContextWindowManager:
    """
    Smart context selection to reduce LLM costs and improve quality.

    Strategy:
    1. Always keep most recent N messages (immediate context)
    2. From older messages, prioritize:
       - Messages with charts (high value, visual context)
       - User questions (understanding the conversation flow)
       - Messages referenced in recent context
    3. Limit total context to prevent token bloat
    """

    def __init__(self, max_tokens: int = 4000, keep_recent: int = 5):
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent

    def optimize_history(
        self, messages: List[Dict], keep_recent: Optional[int] = None
    ) -> List[Dict]:
        if not messages:
            return []
        recent_count = keep_recent or self.keep_recent
        if len(messages) <= recent_count + 5:
            return messages

        recent = messages[-recent_count:]
        older = messages[:-recent_count]
        important = []
        max_older = 10

        for msg in reversed(older):
            score = self._score_message_importance(msg)
            if score > 0:
                important.insert(0, msg)
            if len(important) >= max_older:
                break

        optimized = important + recent
        logger.debug(
            f"ContextWindow: {len(messages)} msgs → {len(optimized)} "
            f"({len(important)} important + {len(recent)} recent)"
        )
        return optimized

    def _score_message_importance(self, message: Dict) -> int:
        score = 0
        if message.get("chart_config"):
            score += 3
        if message.get("role") == "user":
            score += 1
        content = message.get("content", "")
        if any(kw in content.lower() for kw in ["trend", "insight", "analysis", "found"]):
            score += 1
        if message.get("role") == "ai" and len(content) > 500:
            score += 1
        return score


context_manager = ContextWindowManager(max_tokens=4000, keep_recent=5)


# =============================================================================
# PRIVACY CONTROLS  (moved from ai_service.py)
# =============================================================================


async def apply_privacy_controls(
    metadata: Dict[str, Any],
    user_id: str,
    dataset_id: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Apply privacy controls to metadata before sending to LLM.

    Returns (modified_metadata, privacy_info).
    """
    privacy_info = {
        "columns_redacted": [],
        "columns_shared": [],
        "sample_rows_shared": True,
        "pii_detected": [],
        "auto_redacted": False,
    }

    try:
        from services.privacy.privacy_settings_service import privacy_settings_service
        from services.privacy.pii_detector import pii_detector
        from services.privacy.privacy_audit_service import privacy_audit_service

        effective_settings = await privacy_settings_service.get_effective_settings(
            user_id, dataset_id
        )
        private_columns = set(effective_settings.get("private_columns", []))
        share_column_names = effective_settings.get("share_column_names", True)
        share_sample_rows = effective_settings.get("share_sample_rows", True)
        pii_auto_redact = effective_settings.get("pii_auto_redact", True)

        metadata = dict(metadata)

        if not share_column_names:
            privacy_info["columns_shared"] = []
        else:
            privacy_info["columns_shared"] = [
                c.get("name")
                for c in metadata.get("column_metadata", [])
                if c.get("name") not in private_columns
            ]

        if private_columns and share_column_names:
            original_columns = metadata.get("column_metadata", [])
            metadata["column_metadata"] = [
                c for c in original_columns if c.get("name") not in private_columns
            ]
            privacy_info["columns_redacted"] = list(private_columns)

        if pii_auto_redact and effective_settings.get("pii_auto_detect", True):
            for col in metadata.get("column_metadata", []):
                col_name = col.get("name", "")
                if not col_name or col_name in private_columns:
                    continue
                try:
                    detection_result = pii_detector.scan_column_name(col_name)
                    if detection_result:
                        pii_type = (
                            detection_result.pii_type.value
                            if hasattr(detection_result, "pii_type")
                            else str(detection_result)
                        )
                        confidence = (
                            detection_result.confidence
                            if hasattr(detection_result, "confidence")
                            else 1.0
                        )
                        privacy_info["pii_detected"].append(
                            {"column": col_name, "pii_type": pii_type, "confidence": confidence}
                        )
                        private_columns.add(col_name)
                        metadata["column_metadata"] = [
                            c
                            for c in metadata.get("column_metadata", [])
                            if c.get("name") != col_name
                        ]
                        privacy_info["columns_redacted"].append(col_name)
                        privacy_info["auto_redacted"] = True
                except Exception as det_err:
                    logger.warning(f"PII detection failed for column {col_name}: {det_err}")

        metadata["_privacy_info"] = privacy_info
        if not share_sample_rows:
            metadata["sample_data"] = None
            privacy_info["sample_rows_shared"] = False

        if privacy_info["columns_redacted"] or privacy_info["pii_detected"]:
            logger.info(
                f"Privacy: redacted {len(privacy_info['columns_redacted'])} columns, "
                f"detected {len(privacy_info['pii_detected'])} PII columns"
            )
            asyncio.create_task(
                privacy_audit_service.log_pii_scan(
                    user_id=user_id,
                    dataset_id=dataset_id,
                    columns_found=[p["column"] for p in privacy_info["pii_detected"]],
                    pii_detected=privacy_info["pii_detected"],
                    confidence_scores={
                        p["column"]: p.get("confidence", 0.9) for p in privacy_info["pii_detected"]
                    },
                )
            )
    except Exception as e:
        logger.warning(f"Privacy controls failed (non-critical): {e}")

    return metadata, privacy_info


# =============================================================================
# RAG CONTEXT RETRIEVAL  (moved from ai_service.py)
# =============================================================================


async def get_rag_context(
    query: str,
    dataset_id: str,
    user_id: str,
    metadata: Dict[str, Any],
) -> str:
    """
    Get context for LLM using RAG vector retrieval.
    Falls back to full context string if vector search unavailable.
    Applies privacy controls before returning context.
    """
    try:
        privacy_metadata, _ = await apply_privacy_controls(metadata, user_id, dataset_id)

        from services.datasets.faiss_vector_service import faiss_vector_service
        from services.rag.reranker_service import reranker_service
        from services.datasets.dataset_loader import create_context_string

        if faiss_vector_service.enable_vector_search:
            # Lazily initialize cross-encoder reranker on first RAG call
            if not reranker_service.use_cross_encoder:
                asyncio.create_task(
                    _lazy_init_cross_encoder(reranker_service)
                )
            chunks = await faiss_vector_service.search_relevant_chunks(
                query=query,
                dataset_id=dataset_id,
                k=10,
                score_threshold=0.3,
            )
            if chunks:
                # Fuse dense (FAISS) + sparse (BM25) for better coverage
                try:
                    from services.rag.hybrid_search import hybrid_search_service

                    if hybrid_search_service.bm25_available:
                        chunks = hybrid_search_service.hybrid_search(
                            query=query,
                            dense_results=chunks,
                            dataset_id=dataset_id,
                            k=10,
                            fusion_method="rrf",
                        )
                except ImportError:
                    pass  # rank_bm25 not installed
                except Exception as e:
                    logger.debug(f"Hybrid search unavailable (non-critical): {e}")

                reranked = reranker_service.rerank(
                    query=query,
                    chunks=chunks,
                    top_k=5,
                    score_threshold=0.4,
                    use_diversity=True,
                )
                if reranked:
                    context = faiss_vector_service.assemble_context_from_chunks(
                        reranked, max_tokens=2000
                    )
                    logger.info(
                        f"RAG: {len(chunks)} chunks → reranked to {len(reranked)}"
                    )
                    return context

            logger.debug("RAG: No chunks after reranking, falling back to full context")
        return create_context_string(privacy_metadata)
    except Exception as e:
        logger.warning(f"RAG retrieval failed, using fallback: {e}")
        from services.datasets.dataset_loader import create_context_string
        return create_context_string(metadata) if metadata else ""


# =============================================================================
# RERANKER INITIALIZATION  (lazy — first RAG call pays the model load cost)
# =============================================================================


async def _lazy_init_cross_encoder(reranker_service) -> None:
    """
    Lazily initialize the cross-encoder reranker on first RAG call.
    Runs as fire-and-forget so it doesn't block the pipeline.
    If it fails (e.g., model download), the fallback diversity rerank still works.
    """
    try:
        reranker_service.enable_cross_encoder(model_name="BAAI/bge-reranker-v2-m3")
    except Exception as e:
        logger.warning(f"Cross-encoder initialization failed (non-critical): {e}")


# =============================================================================
# MEMORY CONTEXT  (unified retrieval — replaces 3 individual service calls)
# =============================================================================


async def load_memory_context(
    user_id: str,
    dataset_id: str,
    query: str,
    conversation_id: str,
) -> MemoryContext:
    """Unified memory retrieval — one call replaces 3 individual service calls."""
    try:
        from services.memory_injector import memory_injector

        mem_ctx = await memory_injector.get_context(
            user_id=user_id,
            dataset_id=dataset_id,
            query=query,
            conversation_id=conversation_id,
        )
        return MemoryContext(
            memories=mem_ctx.memories,
            belief_context=mem_ctx.belief_context,
            instructions_override=mem_ctx.instructions_override,
        )
    except Exception as e:
        logger.warning(f"Memory context load failed (non-critical): {e}")
        return MemoryContext()


# =============================================================================
# MAIN CONTEXT LOADER
# =============================================================================


async def load_context(
    query: str,
    dataset_id: str,
    user_id: str,
    conversation_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> ContextPackage:
    """
    Load all context needed for the chat pipeline.

    Loads in parallel where possible:
      - Dataset document from MongoDB (workspace-scoped)
      - Conversation history
      - Privacy-controlled metadata
      - RAG context via vector search
      - Memory injection (beliefs + instructions)

    Args:
        workspace_id: Optional tenant scope. When omitted, resolves the
            user's personal workspace (canonical post-backfill tag) so
            single-workspace callers keep working unchanged.
    """
    from services.conversations.conversation_service import load_or_create_conversation

    # ── Load dataset document (workspace-scoped read) ──
    dataset_doc = None
    try:
        from services.datasets.enhanced_dataset_service import enhanced_dataset_service

        dataset_doc = await enhanced_dataset_service.get_dataset_doc(
            dataset_id, user_id, workspace_id=workspace_id
        )
    except Exception as e:
        logger.warning(f"Failed to load dataset {dataset_id}: {e}")

    if not dataset_doc:
        raise ValueError(f"Dataset {dataset_id} not found or not accessible")

    metadata: Dict[str, Any] = dataset_doc.get("metadata", {})
    if not metadata:
        raise ValueError("Dataset is still being processed.")

    # ── Load conversation ──
    conv = await load_or_create_conversation(conversation_id, user_id, dataset_id)
    messages = conv.get("messages", [])
    conv_id_str = str(conv["_id"])

    # ── Get column names ──
    columns = []
    schema = metadata.get("schema", {})
    if schema:
        columns = list(schema.keys())

    # ── Load RAG + Memory in parallel ──
    rag_task = get_rag_context(query, dataset_id, user_id, metadata)
    memory_task = load_memory_context(user_id, dataset_id, query, conv_id_str)

    rag_context, memory_ctx = await asyncio.gather(rag_task, memory_task, return_exceptions=True)

    if isinstance(rag_context, Exception):
        logger.warning(f"RAG context retrieval failed: {rag_context}")
        from services.datasets.dataset_loader import create_context_string
        rag_context = create_context_string(metadata)

    if isinstance(memory_ctx, Exception):
        logger.warning(f"Memory context retrieval failed: {memory_ctx}")
        memory_ctx = MemoryContext()

    # Cleaning manifest (top-level on the uploads doc, nested in metadata on
    # older records) — used by the pipeline's cleaning guard (Principle #0).
    cleaning_manifest = (
        dataset_doc.get("cleaning_manifest")
        or metadata.get("cleaning_manifest")
        or []
    )

    return ContextPackage(
        dataset_metadata=metadata,
        dataset_context_str=rag_context,
        rag_context=rag_context,
        memory_context=memory_ctx,
        columns=columns,
        cleaning_manifest=cleaning_manifest,
        conversation_messages=messages,
        conversation_id=conv_id_str,
    )


__all__ = [
    "load_context",
    "apply_privacy_controls",
    "get_rag_context",
    "load_memory_context",
    "ContextWindowManager",
    "context_manager",
]
