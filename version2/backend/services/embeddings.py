"""
Shared Embedding Singleton
===========================

Prevents multiple services from each loading their own SentenceTransformer model.
Both ``ResponseCache`` and ``SemanticCache`` independently load
``BAAI/bge-small-en-v1.5`` (133 MB each). This module ensures the model is
loaded exactly once and shared across all consumers.

Usage:
    from services.embeddings import get_bge_small_embedding

    model = get_bge_small_embedding()
    embedding = model.encode(text, normalize_embeddings=True)
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_bge_small_model = None
_bge_small_lock = threading.Lock()


def get_bge_small_embedding(model_name: str = "BAAI/bge-small-en-v1.5"):
    """
    Get or create the shared bge-small SentenceTransformer model singleton.

    Args:
        model_name: HuggingFace model name (default: BAAI/bge-small-en-v1.5)

    Returns:
        SentenceTransformer model instance, or None if unavailable
    """
    global _bge_small_model
    if _bge_small_model is not None:
        return _bge_small_model

    with _bge_small_lock:
        if _bge_small_model is not None:
            return _bge_small_model

        try:
            from sentence_transformers import SentenceTransformer

            _bge_small_model = SentenceTransformer(model_name)
            logger.info(
                f"Shared embedding model loaded: {model_name}"
            )
        except ImportError:
            logger.warning(
                "sentence-transformers not available — shared embedding disabled"
            )
            _bge_small_model = None
        except Exception as e:
            logger.warning(
                f"Failed to load shared embedding model '{model_name}': {e}"
            )
            _bge_small_model = None

    return _bge_small_model
