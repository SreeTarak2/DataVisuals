#!/usr/bin/env python3
"""
Prompt Tuner: Automated Evaluation and Prompt Fix Plan Generator

This script analyzes evaluation runs for DataSage, auto-scores responses across key quality dimensions, detects common failure patterns, and generates a prioritized fix plan for prompt engineering. It supports merging manual scores and outputs detailed reports to guide iterative prompt improvement.

Key Features:
- Scores responses on faithfulness, depth, specificity, actionability, and format quality.
- Detects and catalogs common response issues using regex and heuristics.
- Produces a markdown fix plan ranked by severity and frequency of issues.
- Supports merging manual scoring for deeper analysis.
- CLI interface for integration into evaluation workflows.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple




@dataclass
class Score:

    faithfulness: float = 0.0
    depth: float = 0.0
    specificity: float = 0.0
    actionability: float = 0.0
    format_quality: float = 0.0

    @property
    def total(self) -> float:
        return round(
            (self.faithfulness + self.depth + self.specificity + self.actionability + self.format_quality) / 5,
            2,
        )




PATTERN_CATALOGUE: List[Dict[str, Any]] = [
    {
        "id": "filler_opening",
        "label": "Filler opening sentence",
        "description": "Response starts with useless preamble instead of the direct answer.",
        "regex": r"(?i)^(based on the (data|results|analysis|information)|according to (the )?(data|results)|the (data|results) show(s)?|looking at the (data|results))",
        "check": "response_start",
        "severity": "high",
        "prompt_fn": "get_result_interpretation_prompt",
        "suggested_rule": 'Add to HOW TO RESPOND: "Never start the response with \'Based on...\' or \'According to...\' — your first word must be a noun, number, or named entity."',
        "dimension": "specificity",
    },
    {
        "id": "generic_helper",
        "label": "Generic helper opener",
        "description": "Response opens with a service-desk greeting instead of an insight.",
        "regex": r"(?i)\b(i('d be happy to|'m here to| can certainly| will help)|of course|sure[,!]|happy to help)",
        "check": "response_start",
        "severity": "high",
        "prompt_fn": "CONVERSATIONAL_SYSTEM_PROMPT",
        "suggested_rule": 'Add rule: "Never open with affirmations (\'Sure\', \'Of course\', \'Happy to help\'). Start immediately with the insight."',
        "dimension": "specificity",
    },
    {
        "id": "missing_numbers",
        "label": "No numbers in analytical response",
        "description": "An analytical question got a response with zero numeric values.",
        "regex": r"\d",
        "check": "no_match",
        "severity": "critical",
        "prompt_fn": "get_result_interpretation_prompt",
        "suggested_rule": 'Strengthen rule: "If the query results contain numbers, your response MUST cite at least one specific number in the first sentence."',
        "dimension": "faithfulness",
    },
    {
        "id": "missing_bold",
        "label": "Numbers not bolded",
        "description": "Numbers present but not wrapped in **bold** markdown.",
        "check": "number_without_bold",
        "severity": "medium",
        "prompt_fn": "get_result_interpretation_prompt",
        "suggested_rule": 'Reinforce: "Wrap EVERY number and metric in **bold**. No exceptions."',
        "dimension": "format_quality",
    },
    {
        "id": "no_followup",
        "label": "Missing follow-up suggestion",
        "description": "Response does not end with a `---` separator and a next-step suggestion.",
        "regex": r"---",
        "check": "no_match",
        "severity": "medium",
        "prompt_fn": "get_result_interpretation_prompt",
        "suggested_rule": 'Make the separator mandatory: "Always end with a `---` line followed by exactly one specific follow-up question."',
        "dimension": "actionability",
    },
    {
        "id": "vague_patterns",
        "label": "Vague qualitative language",
        "description": 'Uses words like "significantly", "generally", "tends to" without backing numbers.',
        "regex": r"(?i)\b(significantly|generally|tend(s)? to|some|many|often|usually|might be|could be|may be|seem(s)? to)\b",
        "check": "match_without_number_context",
        "severity": "medium",
        "prompt_fn": "get_result_interpretation_prompt",
        "suggested_rule": 'Add: "Every qualitative claim (\'significant\', \'high\', \'low\') MUST be followed immediately by the supporting number in parentheses."',
        "dimension": "specificity",
    },
    {
        "id": "sql_error_leaked",
        "label": "SQL error leaked into response",
        "description": "Backend error text (syntax error, column not found, etc.) appears in response.",
        "regex": r"(?i)(syntax error|column.{1,30}not (found|exist)|table.{1,20}not (found|exist)|duckdb|polars|traceback|exception|error at or near)",
        "check": "match",
        "severity": "critical",
        "prompt_fn": "get_result_interpretation_prompt + query_executor.py error handler",
        "suggested_rule": 'Add fallback rule: "If ACTUAL QUERY RESULTS contains an error message, respond: \'I could not retrieve data for this question — the query failed with: [reason]. Please try rephrasing.\'"',
        "dimension": "faithfulness",
    },
    {
        "id": "hallucination_marker",
        "label": "Overconfident / hallucination risk",
        "description": 'Uses "definitely", "certainly", "always" when data is limited or results are empty.',
        "regex": r"(?i)\b(definitely|certainly|absolutely|without (a )?doubt|always|never fail)\b",
        "check": "match",
        "severity": "medium",
        "prompt_fn": "CONVERSATIONAL_SYSTEM_PROMPT",
        "suggested_rule": 'Add: "Never use absolute terms (\'definitely\', \'certainly\', \'always\') — qualify claims with the actual sample size or confidence level."',
        "dimension": "faithfulness",
    },
    {
        "id": "short_response",
        "label": "Suspiciously short analytical response",
        "description": "Response is under 40 words for a complex analytical query.",
        "check": "word_count_lt_40",
        "severity": "high",
        "prompt_fn": "get_result_interpretation_prompt",
        "suggested_rule": 'Enforce minimum depth: "For analytical questions, provide at least 3 sentences. Never truncate mid-analysis."',
        "dimension": "depth",
    },
    {
        "id": "chart_missing",
        "label": "Chart not generated for visual query",
        "description": "User asked to visualise / plot / chart but no chart_config was returned.",
        "check": "chart_keyword_no_chart",
        "severity": "high",
        "prompt_fn": "chart generation logic / AI service chart decision",
        "suggested_rule": 'Ensure: Any query containing "plot", "chart", "visualise", "graph", "show me a bar/line/pie" triggers chart_config generation.',
        "dimension": "actionability",
    },
    {
        "id": "question_not_answered",
        "label": "Response does not address the question",
        "description": 'Response says "I cannot answer" or deflects when data is available.',
        "regex": r"(?i)\b(cannot (answer|determine|calculate|compute|tell)|don'?t have (enough|sufficient|access)|unable to (answer|provide|determine)|not (possible|able) to (answer|determine))\b",
        "check": "match",
        "severity": "critical",
        "prompt_fn": "get_result_interpretation_prompt",
        "suggested_rule": 'Add: "You have already executed the SQL — the results are provided above. NEVER say you cannot compute or determine the answer. If results are empty, explain why they are empty."',
        "dimension": "faithfulness",
    },
    {
        "id": "no_chart_config_any",
        "label": "Zero charts across entire eval run",
        "description": "Not a single response produced a chart_config.",
        "check": "run_level_no_charts",
        "severity": "medium",
        "prompt_fn": "AI service / chart decision heuristic",
        "suggested_rule": 'Check chart_decision logic in ai_service.py — ensure numeric + categorical column combinations auto-trigger chart suggestions.',
        "dimension": "format_quality",
    },
]





CHART_KEYWORDS = re.compile(r"(?i)\b(plot|chart|bar|line|pie|scatter|histogram|heatmap|visuali[sz]e?|graph|trend over|show me a)\b")


def _starts_with(text: str, pattern: str) -> bool:
    return bool(re.match(pattern, text.strip()))


def _has_number_without_bold(text: str) -> bool:
    # Returns True if a bare number is present in the narrative part of the response, not wrapped in bold markdown.

    clean = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    clean = re.sub(r"`[^`]+`", "", clean)
    clean = re.sub(r"<details[^>]*>.*?</details>", "", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"^\|.*\|$", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"\*\*Query Results:\*\*.*", "", clean, flags=re.DOTALL)


    # Detect broken nested bold: any `****` sequence in narrative text (indicates two adjacent closing spans).
    broken_bold = bool(re.search(r'\*{4}', clean))
    if broken_bold:
        return True


    clean = re.sub(r"\*\*[^*]+\*\*", "", clean)
    return bool(re.search(r"\b\d+[\d,.]*\b", clean))


def check_pattern(pattern: Dict[str, Any], row: Dict[str, Any]) -> bool:
    text = row.get("response_text", "") or ""
    check = pattern["check"]

    if check == "response_start":
        return _starts_with(text, pattern["regex"])

    if check == "match":
        return bool(re.search(pattern["regex"], text))

    if check == "no_match":
        return not bool(re.search(pattern["regex"], text))

    if check == "number_without_bold":
        return _has_number_without_bold(text)

    if check == "match_without_number_context":
        matches = list(re.finditer(pattern["regex"], text))
        if not matches:
            return False
        for m in matches:
            window = text[max(0, m.start() - 40): m.end() + 40]
            if re.search(r"\d", window):
                return False
        return True

    if check == "word_count_lt_40":
        return len(text.split()) < 40 and len(text.strip()) > 0

    if check == "chart_keyword_no_chart":
        query = row.get("query", "")
        has_chart = row.get("has_chart", False)
        return bool(CHART_KEYWORDS.search(query)) and not has_chart

    if check == "run_level_no_charts":
        # Handled at run level, not per-row
        return False

    return False




def auto_score(row: Dict[str, Any]) -> Tuple[Score, List[str]]:
    text = row.get("response_text", "") or ""
    query = row.get("query", "") or ""
    flags: List[str] = []

    faith = 5.0
    depth = 5.0
    spec = 5.0
    action = 5.0
    fmt = 5.0

    if row.get("status", "ok") != "ok":
        return Score(1, 1, 1, 1, 1), ["error_response"]


    # Key scoring logic: adjust scores and flags based on detected issues.
    if check_pattern({"check": "match", "regex": r"(?i)\b(cannot (answer|determine|compute)|unable to (answer|provide))\b"}, row):
        faith -= 3
        flags.append("deflects_question")
    if check_pattern({"check": "match", "regex": r"(?i)(syntax error|column.{1,30}not (found|exist)|traceback)"}, row):
        faith -= 2
        flags.append("sql_error_leaked")
    if check_pattern({"check": "match", "regex": r"(?i)\b(definitely|certainly|always)\b"}, row):
        faith -= 1
        flags.append("overconfident")

    if check_pattern({"check": "response_start", "regex": r"(?i)^(based on the|according to the|the (data|results) show)"}, row):
        spec -= 2
        flags.append("filler_opening")
    if check_pattern({"check": "response_start", "regex": r"(?i)\b(i('d be happy|'m here|'ll help)|of course|sure[,!]|happy to)"}, row):
        spec -= 2
        flags.append("generic_helper")
    if check_pattern({"check": "no_match", "regex": r"\d"}, row) and any(
        kw in query.lower() for kw in ("average", "total", "count", "how many", "percent", "rate", "top", "max", "min", "sum")
    ):
        spec -= 3
        flags.append("missing_numbers")

    if len(text.split()) < 40 and len(text.strip()) > 5:
        depth -= 2
        flags.append("short_response")

    if "---" not in text:
        action -= 1.5
        flags.append("no_followup")
    if check_pattern({"check": "chart_keyword_no_chart"}, row):
        action -= 1
        flags.append("chart_missing")

    if _has_number_without_bold(text):
        fmt -= 1
        flags.append("missing_bold")

    def clamp(v: float) -> float:
        return max(1.0, min(5.0, round(v, 1)))

    return Score(clamp(faith), clamp(depth), clamp(spec), clamp(action), clamp(fmt)), flags




def analyse_run(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    scored_rows: List[Dict[str, Any]] = []
    pattern_hits: Dict[str, List[str]] = defaultdict(list)  # pattern_id → [case_ids]
    dimension_totals: Dict[str, float] = defaultdict(float)
    total = len(results)

    has_any_chart = any(r.get("has_chart") for r in results)

    for row in results:
        score, flags = auto_score(row)
        case_id = row.get("case_id", "?")

        for flag in flags:
            pattern_hits[flag].append(case_id)

        for dim, val in [
            ("faithfulness", score.faithfulness),
            ("depth", score.depth),
            ("specificity", score.specificity),
            ("actionability", score.actionability),
            ("format_quality", score.format_quality),
        ]:
            dimension_totals[dim] += val

        # Check structured patterns (per-row)
        for pat in PATTERN_CATALOGUE:
            if pat["check"] == "run_level_no_charts":
                continue
            if check_pattern(pat, row) and pat["id"] not in flags:
                pattern_hits[pat["id"]].append(case_id)

        scored_rows.append(
            {
                **{k: row.get(k, "") for k in ("run_at_utc", "mode", "case_id", "group", "query", "status", "latency_ms", "has_chart", "response_word_count")},
                "faithfulness": score.faithfulness,
                "depth": score.depth,
                "specificity": score.specificity,
                "actionability": score.actionability,
                "format_quality": score.format_quality,
                "total_score": score.total,
                "flags": "|".join(flags),
                "response_text": row.get("response_text", ""),
                "error": row.get("error", ""),
            }
        )

    # Run-level: no charts at all
    if not has_any_chart:
        pattern_hits["no_chart_config_any"] = ["(all cases)"]

    avg: Dict[str, float] = {dim: round(v / total, 2) if total else 0 for dim, v in dimension_totals.items()}
    return {"scored_rows": scored_rows, "pattern_hits": dict(pattern_hits), "averages": avg, "total": total}




def build_fix_plan(analysis: Dict[str, Any], out_dir: Path) -> str:
    hits = analysis["pattern_hits"]
    avgs = analysis["averages"]
    total = analysis["total"]
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Build ordered catalogue keyed by id
    cat_by_id = {p["id"]: p for p in PATTERN_CATALOGUE}

    # Rank: severity weight × hit count
    severity_weight = {"critical": 3, "high": 2, "medium": 1}

    def rank_key(pid: str) -> int:
        pat = cat_by_id.get(pid, {})
        sev = severity_weight.get(pat.get("severity", "medium"), 1)
        return sev * len(hits.get(pid, []))

    ranked = sorted(hits.keys(), key=rank_key, reverse=True)

    lines: List[str] = [
        "# DataSage Prompt Fix Plan",
        f"\n_Auto-generated by `prompt_tuner.py` at {now}_\n",
        "---",
        "",
        "## Average Dimension Scores (1–5)",
        "",
        "| Dimension | Avg Score | Status |",
        "|---|---|---|",
    ]
    for dim, avg in sorted(avgs.items()):
        status = "✅" if avg >= 4.0 else ("⚠️" if avg >= 3.0 else "🔴")
        lines.append(f"| {dim.replace('_', ' ').title()} | **{avg}** | {status} |")

    lines += [
        "",
        "---",
        "",
        "## Prioritised Fix List",
        "",
        "> Ordered by: severity × hit count.  Fix critical items first.",
        "",
    ]

    for rank, pid in enumerate(ranked, start=1):
        affected_cases = hits[pid]
        count = len(affected_cases)
        pct = round(100 * count / total) if total else 0
        pat = cat_by_id.get(pid)

        if pat is None:
            # Flag only, no catalogue entry — generic entry
            lines += [
                f"### {rank}. `{pid}` — {count} case(s) ({pct}%)",
                "",
                f"- Affected: {', '.join(affected_cases[:8])}{'...' if count > 8 else ''}",
                f"- **Action**: Review responses flagged with `{pid}` and add a targeted rule to the relevant prompt.",
                "",
            ]
            continue

        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(pat["severity"], "⚪")
        lines += [
            f"### {rank}. {severity_emoji} {pat['label']} — {count} case(s) ({pct}%)",
            "",
            f"**Pattern ID**: `{pid}`  ",
            f"**Severity**: {pat['severity']}  ",
            f"**Prompt to fix**: `{pat['prompt_fn']}`  ",
            f"**Affected dimension**: {pat['dimension']}  ",
            "",
            f"**Problem**: {pat['description']}",
            "",
            f"**Affected cases**: {', '.join(affected_cases[:8])}{'...' if count > 8 else ''}",
            "",
            "**Suggested rule to add**:",
            f"> {pat['suggested_rule']}",
            "",
        ]

    if not ranked:
        lines += [
            "✅ No significant failure patterns detected in this eval run.",
            "",
            "Consider raising the bar — run more diverse/harder queries to stress-test.",
            "",
        ]

    # Lowest-scoring dimension recommendation
    if avgs:
        worst_dim = min(avgs, key=avgs.get)
        lines += [
            "---",
            "",
            "## Top Priority Dimension",
            "",
            f"The weakest dimension is **{worst_dim.replace('_', ' ').title()}** (avg **{avgs[worst_dim]}**/5).",
            "",
            "Focus prompt edits on this dimension first to get the biggest quality lift.",
            "",
        ]

    lines += [
        "---",
        "",
        "## How to Apply Fixes",
        "",
        "1. Open `version2/backend/core/prompt_templates.py`",
        "2. Locate the function listed under **Prompt to fix** above",
        "3. Add the suggested rule to the `## HOW TO RESPOND` section",
        "4. Re-run the eval: `python scripts/chatbot_eval_runner.py ...`",
        "5. Re-run tuner: `python scripts/prompt_tuner.py --eval-dir evals/<new_timestamp>`",
        "6. Compare average scores and repeat until all dimensions ≥ 4.0",
        "",
    ]

    return "\n".join(lines)




def load_results(eval_dir: Path) -> List[Dict[str, Any]]:
    jsonl = eval_dir / "results.jsonl"
    csv_path = eval_dir / "results.csv"
    if jsonl.exists():
        rows = []
        with jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    raise FileNotFoundError(f"No results.jsonl or results.csv found in {eval_dir}")


def merge_manual_scores(
    scored_rows: List[Dict[str, Any]], scored_csv: Optional[Path]
) -> List[Dict[str, Any]]:
    if not scored_csv or not scored_csv.exists():
        return scored_rows
    manual: Dict[Tuple[str, str], Dict[str, str]] = {}
    with scored_csv.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row.get("case_id", ""), row.get("mode", ""))
            manual[key] = row

    dim_map = {
        "faithfulness_1_5": "faithfulness",
        "analytical_depth_1_5": "depth",
        "specificity_1_5": "specificity",
        "actionability_1_5": "actionability",
        "format_quality_1_5": "format_quality",
    }
    for row in scored_rows:
        key = (row.get("case_id", ""), row.get("mode", ""))
        m = manual.get(key, {})
        for csv_col, dim in dim_map.items():
            val = m.get(csv_col, "").strip()
            if val and val.replace(".", "", 1).isdigit():
                row[f"manual_{dim}"] = float(val)
        notes = m.get("prompt_fix_notes", "").strip()
        if notes:
            row["manual_notes"] = notes
    return scored_rows


def write_auto_scores(scored_rows: List[Dict[str, Any]], out_dir: Path) -> None:
    path = out_dir / "auto_scores.csv"
    if not scored_rows:
        return
    fields = list(scored_rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(scored_rows)
    print(f"  Auto scores → {path}")


def write_fix_plan(plan_md: str, out_dir: Path) -> None:
    path = out_dir / "prompt_fix_plan.md"
    path.write_text(plan_md, encoding="utf-8")
    print(f"  Fix plan    → {path}")




def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Analyse a DataSage eval run and produce a prompt fix plan.")
    p.add_argument("--eval-dir", required=True, help="Path to eval output directory (must contain results.jsonl or results.csv).")
    p.add_argument("--scored-csv", default=None, help="Optional path to a manually-scored scoring_template.csv to merge into the report.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    eval_dir = Path(args.eval_dir)
    if not eval_dir.exists():
        print(f"ERROR: eval-dir not found: {eval_dir}", file=sys.stderr)
        return 1

    print(f"Loading results from {eval_dir} ...")
    try:
        results = load_results(eval_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"  {len(results)} result rows loaded.")
    analysis = analyse_run(results)

    scored_csv = Path(args.scored_csv) if args.scored_csv else None
    analysis["scored_rows"] = merge_manual_scores(analysis["scored_rows"], scored_csv)

    print("Writing outputs:")
    write_auto_scores(analysis["scored_rows"], eval_dir)

    fix_plan = build_fix_plan(analysis, eval_dir)
    write_fix_plan(fix_plan, eval_dir)

    # Print summary to console
    print("\n── Dimension Averages ──────────────────")
    for dim, avg in sorted(analysis["averages"].items()):
        bar = "█" * int(avg) + "░" * (5 - int(avg))
        print(f"  {dim:<20} {bar}  {avg}/5")

    print("\n── Top Failures ────────────────────────")
    hits = analysis["pattern_hits"]
    if hits:
        cat_by_id = {p["id"]: p for p in PATTERN_CATALOGUE}
        for pid, cases in sorted(hits.items(), key=lambda x: -len(x[1]))[:5]:
            label = cat_by_id.get(pid, {}).get("label", pid)
            print(f"  [{len(cases):>2}x] {label}")
    else:
        print("  No significant failures detected.")

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
