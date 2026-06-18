from typing import Dict, List


def build_observation_summary(observations: List[Dict], max_items: int = 5) -> str:
    if not observations:
        return "No observations yet."

    lines: List[str] = []
    for obs in observations[-max_items:]:
        tool = str(obs.get("tool", "unknown"))
        success = bool(obs.get("success", False))
        status = "ok" if success else "fail"
        detail = (
            obs.get("reasoning_summary")
            if success
            else (obs.get("error") or obs.get("reasoning_summary") or "failed")
        )
        text = str(detail).replace("\n", " ").strip()
        line = f"- {tool}: {status} - {text}"
        if len(line) > 120:
            line = line[:117] + "..."
        lines.append(line)

    return "\n".join(lines)


def build_synthesis_snippets(observations: List[Dict], max_chars: int = 300) -> List[str]:
    snippets: List[str] = []
    for obs in observations:
        if not obs.get("success", False):
            continue
        tool = str(obs.get("tool", "unknown")).upper()
        summary = str(obs.get("reasoning_summary") or "").replace("\n", " ").strip()
        snippet = f"{tool}: {summary}" if summary else f"{tool}:"
        if len(snippet) > max_chars:
            snippet = snippet[: max_chars - 3] + "..."
        snippets.append(snippet)
    return snippets
