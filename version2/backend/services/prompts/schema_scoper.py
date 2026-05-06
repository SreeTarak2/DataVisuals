"""
Schema context optimization - send only relevant columns to LLM.

This prevents prompt bloat when datasets have 40+ columns but the query
only touches 2-3 of them.
"""

import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def extract_column_names_from_schema(schema_text: str) -> List[str]:
    """
    Parse column names from schema string.
    Handles both simple CSV format and complex formatted schemas.
    """
    columns = []
    seen = set()

    for line in schema_text.splitlines():
        line = line.strip()
        if not line or line.startswith("--") or line.startswith("#"):
            continue

        # Extract first word as column name (stops at first space, comma, or special char)
        col_name = ""
        for char in line:
            if char in (" ", ",", ":", "|", "\t", "(", "["):
                break
            col_name += char

        if col_name and col_name not in seen and col_name[0].isalpha() or col_name[0] == "_":
            columns.append(col_name)
            seen.add(col_name)

    return columns


def extract_column_metadata(schema_text: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse schema to extract column name → type mapping.
    Handles formats like: "column_name: integer" or "column_name (type)"
    """
    metadata = {}

    for line in schema_text.splitlines():
        line = line.strip()
        if not line or line.startswith("--") or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) < 1:
            continue

        col_name = parts[0].rstrip(":")
        col_type = parts[1] if len(parts) > 1 else "unknown"

        if col_name and (col_name[0].isalpha() or col_name[0] == "_"):
            metadata[col_name] = {"type": col_type}

    return metadata


def scope_schema_to_query(
    schema_text: str, user_query: str, embedding_fn=None, top_k: int = 15
) -> str:
    """
    Scope schema to only include relevant columns for the user's query.

    If no embedding_fn provided, uses substring matching (naive).
    If embedding_fn provided, uses semantic relevance (preferred).

    Args:
        schema_text: The full schema
        user_query: The user's question
        embedding_fn: Optional function(text) -> embedding vector
        top_k: Max columns to include in scoped schema

    Returns:
        Scoped schema string with only top-k relevant columns
    """
    all_cols = extract_column_names_from_schema(schema_text)
    if len(all_cols) <= top_k:
        return schema_text  # Already small enough

    if embedding_fn is None:
        # Fallback: substring matching
        query_words = user_query.lower().split()
        scores = {}
        for col in all_cols:
            col_lower = col.lower()
            score = sum(
                query_words.count(word)
                for word in col_lower.split("_")
                if word in query_words
            )
            scores[col] = score

        # Sort by score descending, take top K
        relevant_cols = sorted(scores.keys(), key=lambda c: scores[c], reverse=True)[
            :top_k
        ]
        logger.info(
            f"[schema_scope] Naive matching selected {len(relevant_cols)}/{len(all_cols)} columns"
        )
    else:
        # Semantic matching
        try:
            query_embedding = embedding_fn(user_query)
            col_embeddings = {col: embedding_fn(col) for col in all_cols}

            # Simple cosine similarity
            from numpy import dot
            from numpy.linalg import norm

            def cosine_sim(a, b):
                return dot(a, b) / (norm(a) * norm(b) + 1e-9)

            scores = {col: cosine_sim(query_embedding, col_embeddings[col]) for col in all_cols}
            relevant_cols = sorted(scores.keys(), key=lambda c: scores[c], reverse=True)[
                :top_k
            ]
            logger.info(
                f"[schema_scope] Semantic matching selected {len(relevant_cols)}/{len(all_cols)} columns"
            )
        except Exception as e:
            logger.warning(f"[schema_scope] Semantic matching failed: {e}, falling back to all")
            relevant_cols = all_cols

    # Filter schema to only include relevant columns
    relevant_set = set(relevant_cols)
    scoped_lines = []

    for line in schema_text.splitlines():
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("--") or line_stripped.startswith("#"):
            scoped_lines.append(line)
            continue

        # Check if this line mentions any relevant column
        include = False
        for col in relevant_set:
            if line_stripped.startswith(col):
                include = True
                break

        if include:
            scoped_lines.append(line)

    return "\n".join(scoped_lines)


def estimate_schema_tokens(schema_text: str, max_cols: int = 20) -> int:
    """Quick estimate of schema size in tokens (for budget checks)."""
    lines = len(schema_text.splitlines())
    return min(lines * 5, max_cols * 10)  # Rough: ~5 tokens/line, capped
