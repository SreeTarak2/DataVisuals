"""Small utilities for agents (observation summarization, snippets).

Placed here so ChatAgent remains minimal while infra helpers are available
to other agents or tests.
"""
from typing import List, Dict


def build_observation_summary(observations: List[Dict], max_items: int = 5) -> str:
    """Return a compact, human-readable summary of recent observations.

    Each observation is expected to contain `tool` and `reasoning_summary`.
    """
    if not observations:
        return "No observations yet."

    items = observations[-max_items:]
    lines = []
    for o in items:
        tool = o.get("tool", "unknown")
        rs = o.get("reasoning_summary") or ""
        # Keep each line short
        snippet = rs.replace("\n", " ")
        if len(snippet) > 300:
            snippet = snippet[:297] + "..."
        lines.append(f"{tool}: {snippet}")

    return "\n".join(lines)


def build_synthesis_snippets(observations: List[Dict], max_chars: int = 300) -> List[str]:
    """Produce compact snippet strings suitable for inclusion in narrative prompts."""
    snippets = []
    for o in observations:
        tool = o.get("tool", "unknown")
        rs = o.get("reasoning_summary") or ""
        res = o.get("result") or {}
        brief_res = str(res)[: max_chars]
        snippets.append(f"[{tool}] {rs} -- {brief_res}")
    return snippets
