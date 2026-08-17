"""
Chat Pipeline — Unified Replacement for ai_service and copilot_service
======================================================================

Replaces:
  - services/ai/ai_service.py      (~2700 lines, monolithic)
  - services/ai/copilot_service.py (~200 lines, adapter)
  - services/copilot/orchestrator.py (partial — mode routing)

Provides a single, clean pipeline for:
  - Chat processing (non-streaming + streaming)
  - Off-topic guardrails at the edge (before any LLM call)
  - RAG context retrieval
  - Privacy controls
  - Memory injection
  - Strong synthesis with quality gate
  - Conversation persistence
  - Background tasks (reflection, belief update, memory)

Usage:
    from services.chat import ChatPipeline

    pipeline = ChatPipeline()
    result = await pipeline.process(query, dataset_id, user_id)
    async for chunk in pipeline.process_streaming(query, dataset_id, user_id):
        ...

    # Or use the singleton instance directly
    from services.chat import chat_pipeline
    result = await chat_pipeline.process(query, dataset_id, user_id)
"""

from services.chat.pipeline import ChatPipeline, chat_pipeline

__all__ = ["ChatPipeline", "chat_pipeline"]
