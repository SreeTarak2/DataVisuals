"""
builder — PromptBuilder Orchestrator
======================================

Composes prompts from identity + capability modules + dynamic context.

Usage:
    from prompts.builder import PromptBuilder

    prompt = (
        PromptBuilder()
        .with_identity()
        .with_capability("chat", archetype="analyst")
        .with_context(dataset=schema_str, query=user_query)
        .build()
    )
"""

from __future__ import annotations

import importlib
from typing import Any, Optional


class PromptBuilder:
    """
    Compose prompts from identity + capability modules + dynamic context.

    Each .with_*() method adds a section. Sections are joined with blank lines.
    Empty sections are skipped. Order is preserved.
    """

    def __init__(self):
        self._parts: list[str] = []

    def with_identity(self) -> "PromptBuilder":
        """Add platform identity, tone, and safety rules."""
        from prompts._identity import IDENTITY, SAFETY_RULES, TONE_RULES

        self._parts.extend([IDENTITY, SAFETY_RULES, TONE_RULES])
        return self

    def with_capability(self, name: str, **kwargs: Any) -> "PromptBuilder":
        """
        Add a capability-specific prompt section.

        Args:
            name: One of 'chat', 'sql', 'chart', 'kpi', 'dashboard', etc.
            **kwargs: Passed to the capability's build() function.

        The capability module must export a ``build(**kwargs) -> str`` function.
        """
        module = importlib.import_module(f"prompts.{name}")
        build_fn = getattr(module, "build", None)
        if build_fn:
            prompt = build_fn(**kwargs)
            if prompt:
                self._parts.append(prompt)
        return self

    def with_context(
        self,
        *,
        dataset: Optional[str] = None,
        history: Optional[str] = None,
        query: Optional[str] = None,
        **extra: str,
    ) -> "PromptBuilder":
        """Add dynamic context sections (dataset, history, query, etc.)."""
        ctx_parts: list[str] = []
        if dataset:
            ctx_parts.append(f"## Dataset\n{dataset}")
        if history:
            ctx_parts.append(f"## Conversation History\n{history}")
        if query:
            ctx_parts.append(f"## User Question\n{query}")
        for key, value in extra.items():
            if value:
                label = key.replace("_", " ").title()
                ctx_parts.append(f"## {label}\n{value}")
        if ctx_parts:
            self._parts.append("\n\n".join(ctx_parts))
        return self

    def add_section(self, title: str, content: str) -> "PromptBuilder":
        """Add an arbitrary named section."""
        if content:
            self._parts.append(f"## {title}\n{content}")
        return self

    def build(self) -> str:
        """Join all non-empty sections with blank lines."""
        return "\n\n".join(p for p in self._parts if p and p.strip())

    def reset(self) -> "PromptBuilder":
        """Clear all parts for reuse."""
        self._parts = []
        return self


__all__ = ["PromptBuilder"]
