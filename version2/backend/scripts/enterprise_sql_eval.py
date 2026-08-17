#!/usr/bin/env python3
"""
Enterprise-Grade SQL Generation Evaluation Suite
=================================================

Tests the sql_analyst copilot mode across multiple dimensions:
  - Basic SQL queries (SELECT, WHERE, GROUP BY, ORDER BY, LIMIT)
  - Advanced SQL (CTEs, window functions, subqueries, JOINs)
  - SQL debugging (fix broken queries with error context)
  - SQL explanation (explain what a given query does)
  - Edge cases (empty results, ambiguous columns, complex aggregations)
  - Multi-turn conversations (follow-up refinement)
  - Schema awareness (correct column/table references)

Outputs a detailed HTML report with scores, latencies, and per-test analysis.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests


# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class EvalCase:
    id: str
    category: str          # basic | advanced | debugging | explanation | edge_case | multi_turn
    query: str
    description: str       # What this test verifies
    required_elements: List[str] = field(default_factory=list)  # SQL keywords/phrases that MUST appear
    forbidden_elements: List[str] = field(default_factory=list) # SQL patterns that should NOT appear
    expected_tables: List[str] = field(default_factory=list)    # Table names that should be referenced
    min_sql_blocks: int = 1                                     # Minimum ```sql blocks expected
    is_multi_turn: bool = False                                 # Whether this continues a conversation


@dataclass
class EvalResult:
    case_id: str
    category: str
    query: str
    status: str            # ok | error | timeout
    latency_ms: float
    response_text: str
    sql_extracted: Optional[str]
    sql_block_count: int
    elements_found: List[str]
    elements_missing: List[str]
    forbidden_found: List[str]
    has_explanation: bool
    has_sql_block: bool
    error_detail: str = ""
    conversation_id: Optional[str] = None
    response_word_count: int = 0


# ─── Test Cases ──────────────────────────────────────────────────────────────

def build_test_cases(dataset_id: str) -> Tuple[List[EvalCase], List[EvalCase]]:
    """
    Build test cases for two datasets.
    Returns (shopping_cases, education_cases)
    """

    shopping_cases = [
        # ── BASIC SQL ──
        EvalCase(
            id="basic_select_all",
            category="basic",
            query="Write a query to show me all columns and the first 10 rows from this dataset",
            description="Basic SELECT * with LIMIT",
            required_elements=["SELECT", "LIMIT"],
            min_sql_blocks=1,
        ),
        EvalCase(
            id="basic_where_filter",
            category="basic",
            query="Find all records where the purchase amount is greater than 200",
            description="SELECT with WHERE filter on numeric column",
            required_elements=["SELECT", "WHERE", ">", "FROM"],
            min_sql_blocks=1,
        ),
        EvalCase(
            id="basic_group_by",
            category="basic",
            query="Count the number of purchases grouped by category, sorted by count descending",
            description="GROUP BY with COUNT and ORDER BY",
            required_elements=["GROUP BY", "COUNT", "ORDER BY"],
            min_sql_blocks=1,
        ),
        EvalCase(
            id="basic_aggregation",
            category="basic",
            query="What's the average, minimum, and maximum purchase amount per category?",
            description="Multiple aggregations with GROUP BY",
            required_elements=["AVG", "MIN", "MAX", "GROUP BY"],
            min_sql_blocks=1,
        ),
        EvalCase(
            id="basic_having",
            category="basic",
            query="Show me categories that have more than 100 purchases, ordered by count",
            description="GROUP BY with HAVING clause",
            required_elements=["GROUP BY", "HAVING", "COUNT"],
            min_sql_blocks=1,
        ),

        # ── ADVANCED SQL ──
        EvalCase(
            id="advanced_window_rank",
            category="advanced",
            query="Rank all purchases by amount within each category, showing position and total count",
            description="Window function with RANK() or ROW_NUMBER() and PARTITION BY",
            required_elements=["RANK|ROW_NUMBER|DENSE_RANK", "PARTITION BY", "OVER"],
            min_sql_blocks=1,
        ),
        EvalCase(
            id="advanced_cte",
            category="advanced",
            query="Using a CTE (WITH clause), find the top 5% highest-value purchases and their categories",
            description="CTE with percentile or subquery filtering",
            required_elements=["WITH", "AS"],
            min_sql_blocks=1,
        ),
        EvalCase(
            id="advanced_window_lag",
            category="advanced",
            query="For each purchase, show the previous purchase amount by the same customer using a window function",
            description="LAG window function for sequential analysis",
            required_elements=["LAG|LEAD", "OVER", "ORDER BY"],
            min_sql_blocks=1,
        ),

        # ── SQL DEBUGGING ──
        EvalCase(
            id="debugging_syntax",
            category="debugging",
            query='Fix this broken SQL: SELECT category SUM(amount) FROM data WERE amount > 100 GROUPY category',
            description="Fix syntax errors (WERE→WHERE, missing comma, GROUPY→GROUP BY)",
            required_elements=["SELECT", "SUM", "FROM", "WHERE", "GROUP BY"],
            forbidden_elements=["WERE", "GROUPY"],
            min_sql_blocks=1,
        ),
        EvalCase(
            id="debugging_logic",
            category="debugging",
            query="""Fix this SQL - it's supposed to find categories above-average purchase amount but it's wrong:
SELECT category, AVG(amount) FROM data GROUP BY category HAVING amount > 500""",
            description="Fix logical error (HAVING should use aggregate, not raw column)",
            required_elements=["HAVING", "AVG", "GROUP BY"],
            forbidden_elements=["HAVING amount"],
            min_sql_blocks=1,
        ),

        # ── SQL EXPLANATION ──
        EvalCase(
            id="explanation_simple",
            category="explanation",
            query="Explain this SQL query: SELECT category, COUNT(*) as cnt FROM data GROUP BY category ORDER BY cnt DESC LIMIT 5",
            description="Explain a simple GROUP BY query - no SQL generation needed",
            required_elements=["count", "group", "category"],
            min_sql_blocks=0,
        ),
        EvalCase(
            id="explanation_complex",
            category="explanation",
            query="""Explain what this query does step by step:
WITH avg_per_category AS (
  SELECT category, AVG(amount) as avg_amount FROM data GROUP BY category
)
SELECT d.category, d.amount, a.avg_amount,
  ROUND((d.amount - a.avg_amount) / a.avg_amount * 100, 2) as pct_diff
FROM data d
JOIN avg_per_category a ON d.category = a.category
WHERE d.amount > a.avg_amount * 1.5""",
            description="Explain a query with CTE, JOIN, and window function",
            required_elements=["cte", "join", "average", "percent", "difference"],
            min_sql_blocks=0,
        ),

        # ── EDGE CASES ──
        EvalCase(
            id="edge_case_null",
            category="edge_case",
            query="Write a query to find records where any column has NULL or missing values",
            description="NULL handling with IS NULL check across columns",
            required_elements=["IS NULL", "SELECT"],
            min_sql_blocks=1,
        ),
        EvalCase(
            id="edge_case_complex_filter",
            category="edge_case",
            query="Find all records from the last 30 days where amount is both above average AND below 2 standard deviations from the mean",
            description="Complex statistical filter with subquery",
            required_elements=["AVG", "STDDEV|STD", "WHERE", "SELECT"],
            min_sql_blocks=1,
        ),

        # ── MULTI-TURN ──
        EvalCase(
            id="multiturn_1",
            category="multi_turn",
            query="Show me the top 5 categories by total purchase amount",
            description="Initial query for multi-turn conversation",
            required_elements=["SUM", "GROUP BY", "ORDER BY", "LIMIT"],
            min_sql_blocks=1,
            is_multi_turn=False,
        ),
        EvalCase(
            id="multiturn_2",
            category="multi_turn",
            query="Now add a column showing the percentage of total each category represents",
            description="Follow-up refinement - add percentage calculation",
            required_elements=["SUM", "OVER|total|percent", "GROUP BY"],
            min_sql_blocks=1,
            is_multi_turn=True,
        ),
        EvalCase(
            id="multiturn_3",
            category="multi_turn",
            query="Filter to only categories with at least 50 purchases, then sort by percentage descending",
            description="Second follow-up - add HAVING filter and re-sort",
            required_elements=["HAVING", "ORDER BY", "COUNT"],
            min_sql_blocks=1,
            is_multi_turn=True,
        ),
    ]

    education_cases = [
        EvalCase(
            id="edu_basic_select",
            category="basic",
            query="Show me all columns and the first 20 rows of the education dataset",
            description="Basic SELECT with LIMIT on education data",
            required_elements=["SELECT", "LIMIT"],
            min_sql_blocks=1,
        ),
        EvalCase(
            id="edu_group_comparison",
            category="basic",
            query="Compare average graduation rates across different countries or regions",
            description="GROUP BY on categorical column with AVG",
            required_elements=["AVG", "GROUP BY", "ORDER BY"],
            min_sql_blocks=1,
        ),
        EvalCase(
            id="edu_advanced_ranking",
            category="advanced",
            query="Rank countries by their education spending as a percentage of GDP, and show which quartile each falls into",
            description="Window function for ranking with NTILE or quartile logic",
            required_elements=["NTILE|RANK|quartile", "OVER", "ORDER BY"],
            min_sql_blocks=1,
        ),
        EvalCase(
            id="edu_debug",
            category="debugging",
            query="Fix this SQL: SELECT coutry, AVG(enrollment) as avg_enroll FROM edu_data GROU BY country WHERE enrollment > 0",
            description="Fix syntax: coutry→country, GROU→GROUP BY, wrong clause order",
            required_elements=["SELECT", "AVG", "FROM", "WHERE", "GROUP BY", "count"],
            forbidden_elements=["coutry", "GROU"],
            min_sql_blocks=1,
        ),
        EvalCase(
            id="edu_edge_correlation",
            category="edge_case",
            query="Write a query to find if there's a correlation between education spending and graduation rates, comparing countries above and below the median spending",
            description="Complex query splitting data by median with subquery",
            required_elements=["AVG|MEDIAN", "CASE|WHEN", "GROUP BY"],
            min_sql_blocks=1,
        ),
    ]

    return shopping_cases, education_cases


# ─── Evaluation Functions ────────────────────────────────────────────────────

def extract_sql(text: str) -> Tuple[Optional[str], int]:
    """Extract SQL from markdown. Returns (first_sql, count_of_blocks)."""
    blocks = re.findall(r'```sql\s*\n?([\s\S]*?)```', text, re.IGNORECASE)
    if blocks:
        return blocks[0].strip(), len(blocks)
    return None, 0


def check_elements(text: str, sql: Optional[str], elements: List[str]) -> Tuple[List[str], List[str]]:
    """Check which elements are found/missing in the SQL. Supports | for OR matching."""
    haystack = (sql or "") + " " + text
    found = []
    missing = []
    for elem in elements:
        parts = elem.split("|")
        if any(p.strip().upper() in haystack.upper() for p in parts):
            found.append(elem)
        else:
            missing.append(elem)
    return found, missing


def check_forbidden(text: str, sql: Optional[str], forbidden: List[str]) -> List[str]:
    """Check which forbidden elements appear in the text/SQL."""
    haystack = (sql or "") + " " + text
    found = []
    for elem in forbidden:
        if elem.strip().upper() in haystack.upper():
            found.append(elem)
    return found


def has_explanation(text: str, sql: Optional[str]) -> bool:
    """Check if response contains explanatory text beyond just the SQL block."""
    if not sql:
        return bool(len(text.strip()) > 50)
    text_without_sql = re.sub(r'```sql\s*\n?[\s\S]*?```', '', text)
    return bool(len(text_without_sql.strip()) > 50)


def score_sql_quality(sql: Optional[str]) -> Dict[str, Any]:
    """Score SQL on various quality dimensions."""
    if not sql:
        return {"score": 0, "has_semicolon": False, "has_comment": False,
                "is_formatted": False, "has_identifiers": False}

    sql_upper = sql.upper()
    return {
        "score": 1,
        "has_semicolon": sql.strip().endswith(";"),
        "has_comment": "--" in sql or "/*" in sql,
        "is_formatted": bool(re.search(r'\n\s{2,}', sql)),  # Indented
        "has_identifiers": bool(re.search(r'"[^"]+"|`[^`]+`|\[[^\]]+\]', sql)),  # Quoted identifiers
    }


# ─── API Functions ──────────────────────────────────────────────────────────

def login(base_url: str, email: str, password: str) -> str:
    r = requests.post(f"{base_url}/api/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    data = r.json()
    token = data.get("access_token") or data.get("token", "")
    if not token:
        raise RuntimeError(f"No token in login response: {data}")
    return token


def run_sql_chat(base_url: str, headers: dict, dataset_id: str, query: str,
                 mode: str = "sql_analyst", conversation_id: str = None) -> Dict[str, Any]:
    """Run a single chat request and return parsed result."""
    url = f"{base_url}/api/datasets/{dataset_id}/chat?mode={mode}"
    payload = {"message": query}
    if conversation_id:
        payload["conversation_id"] = conversation_id

    start = time.time()
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=180)
        elapsed = time.time() - start
        r.raise_for_status()
        data = r.json()

        resp_text = (data.get("response") or data.get("response_text") or "")
        sql, sql_count = extract_sql(resp_text)
        new_conv_id = data.get("conversation_id", conversation_id)

        return {
            "status": "ok",
            "latency_ms": round(elapsed * 1000, 2),
            "response_text": resp_text,
            "sql_extracted": sql,
            "sql_block_count": sql_count,
            "conversation_id": new_conv_id,
            "error_detail": "",
        }
    except requests.Timeout:
        return {
            "status": "timeout",
            "latency_ms": 180000,
            "response_text": "",
            "sql_extracted": None,
            "sql_block_count": 0,
            "conversation_id": conversation_id,
            "error_detail": "Request timed out after 180s",
        }
    except Exception as e:
        return {
            "status": "error",
            "latency_ms": round((time.time() - start) * 1000, 2),
            "response_text": "",
            "sql_extracted": None,
            "sql_block_count": 0,
            "conversation_id": conversation_id,
            "error_detail": str(e),
        }


# ─── HTML Report Generator ─────────────────────────────────────────────────

def generate_html_report(
    results_by_dataset: Dict[str, List[EvalResult]],
    stats: Dict[str, Any],
    latency_stats: Dict[str, Any],
) -> str:
    """Generate a comprehensive HTML report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Score categories
    score_colors = {
        "basic": "#3b82f6",
        "advanced": "#8b5cf6",
        "debugging": "#f59e0b",
        "explanation": "#10b981",
        "edge_case": "#ef4444",
        "multi_turn": "#06b6d4",
    }

    rows_html = ""
    cat_scores: Dict[str, List[float]] = {}
    total_score = 0
    total_count = 0

    for dataset_name, results in results_by_dataset.items():
        for r in results:
            if r.status != "ok":
                score = 0
            else:
                elements_score = max(0, 1 - len(r.elements_missing) * 0.15)
                forbidden_penalty = len(r.forbidden_found) * 0.25
                sql_quality = 0.5 if r.has_sql_block else 0
                exp_quality = 0.3 if r.has_explanation else 0
                score = min(1, max(0, elements_score - forbidden_penalty + sql_quality * 0.3 + exp_quality * 0.2))

            cat_scores.setdefault(r.category, []).append(score)
            total_score += score
            total_count += 1

            if r.status == "ok":
                status_badge = '<span class="badge badge-ok">OK</span>'
            elif r.status == "timeout":
                status_badge = '<span class="badge badge-warn">TIMEOUT</span>'
            else:
                status_badge = f'<span class="badge badge-error">ERROR</span>'

            score_pct = round(score * 100)
            latency_str = f"{r.latency_ms:.0f}ms" if r.latency_ms > 0 else "N/A"

            sql_preview = ""
            if r.sql_extracted:
                escaped_sql = r.sql_extracted[:300].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                sql_preview = f'<pre class="sql-preview"><code>{escaped_sql}{"..." if len(r.sql_extracted) > 300 else ""}</code></pre>'

            missing_str = ", ".join(r.elements_missing) if r.elements_missing else "—"
            forbidden_str = ", ".join(r.forbidden_found) if r.forbidden_found else "—"

            cat_color = score_colors.get(r.category, "#6b7280")

            rows_html += f"""
            <tr>
                <td><span class="cat-tag" style="background:{cat_color}20;color:{cat_color}">{r.category}</span></td>
                <td><strong>{r.case_id}</strong></td>
                <td class="query-cell" title="{r.query.replace('"', '&quot;')}">{r.query[:60]}...</td>
                <td>{status_badge}</td>
                <td class="num">{latency_str}</td>
                <td>{score_pct}%</td>
                <td>{'✅' if r.has_sql_block else '❌'}</td>
                <td>{'✅' if r.has_explanation else '❌'}</td>
                <td>{missing_str}</td>
                <td>{forbidden_str}</td>
            </tr>
            <tr class="detail-row">
                <td colspan="10">
                    <div class="detail-content">
                        {sql_preview}
                        <div class="error-detail">{r.error_detail}</div>
                    </div>
                </td>
            </tr>
            """

    # Category breakdown
    cat_rows = ""
    for cat in ["basic", "advanced", "debugging", "explanation", "edge_case", "multi_turn"]:
        scores = cat_scores.get(cat, [])
        if scores:
            avg = round(sum(scores) / len(scores) * 100)
            count = len(scores)
            cat_color = score_colors.get(cat, "#6b7280")
            cat_rows += f"""
            <tr>
                <td><span class="cat-tag" style="background:{cat_color}20;color:{cat_color}">{cat}</span></td>
                <td class="num">{count}</td>
                <td>
                    <div class="score-bar-track">
                        <div class="score-bar-fill" style="width:{avg}%;background:{cat_color}"></div>
                    </div>
                </td>
                <td class="num">{avg}%</td>
            </tr>
            """

    overall_pct = round(total_score / max(total_count, 1) * 100)
    avg_latency = latency_stats.get("avg_ms", 0)
    p50_latency = latency_stats.get("p50_ms", 0)
    p95_latency = latency_stats.get("p95_ms", 0)
    total_calls = stats.get("total_calls", 0)
    ok_calls = stats.get("ok_calls", 0)
    error_calls = stats.get("error_calls", 0)
    timeout_calls = stats.get("timeout_calls", 0)
    sql_extracted_count = stats.get("sql_extracted", 0)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Enterprise SQL Generation Eval Report</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0a0a0f; color:#e2e8f0; padding:24px; }}
h1 {{ font-size:24px; font-weight:700; color:#f1f5f9; margin-bottom:4px; }}
.subtitle {{ color:#94a3b8; font-size:14px; margin-bottom:24px; }}
.card {{ background:#13131a; border:1px solid #1e1e2a; border-radius:12px; padding:20px; margin-bottom:20px; }}
.card h2 {{ font-size:16px; font-weight:600; color:#e2e8f0; margin-bottom:12px; }}
.metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; }}
.metric {{ text-align:center; padding:16px; background:#1a1a24; border-radius:8px; }}
.metric .value {{ font-size:28px; font-weight:700; }}
.metric .label {{ font-size:11px; color:#94a3b8; text-transform:uppercase; letter-spacing:0.5px; margin-top:4px; }}
.val-green {{ color:#22c55e; }}
.val-red {{ color:#ef4444; }}
.val-yellow {{ color:#eab308; }}
.val-blue {{ color:#3b82f6; }}
.val-purple {{ color:#8b5cf6; }}
.val-cyan {{ color:#06b6d4; }}

table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ text-align:left; padding:10px 8px; border-bottom:1px solid #1e1e2a; color:#94a3b8; font-weight:500; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; }}
td {{ padding:10px 8px; border-bottom:1px solid #1a1a24; vertical-align:top; }}
tr:hover td {{ background:#1a1a24; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
.query-cell {{ max-width:250px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}

.badge {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }}
.badge-ok {{ background:#22c55e20; color:#22c55e; }}
.badge-warn {{ background:#eab30820; color:#eab308; }}
.badge-error {{ background:#ef444420; color:#ef4444; }}

.cat-tag {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:500; }}

.score-bar-track {{ height:8px; background:#1a1a24; border-radius:4px; overflow:hidden; }}
.score-bar-fill {{ height:100%; border-radius:4px; transition:width 0.5s; }}

.detail-row {{ display:none; }}
tr:hover + .detail-row {{ display:table-row; }}
.detail-content {{ padding:12px; background:#0f0f18; border-radius:8px; font-size:12px; color:#94a3b8; }}
.sql-preview {{ background:#0a0a0f; padding:12px; border-radius:6px; overflow-x:auto; margin-bottom:8px; }}
.sql-preview code {{ font-family:'SF Mono','Fira Code',monospace; font-size:12px; color:#e2e8f0; white-space:pre-wrap; }}
.error-detail {{ color:#ef4444; font-family:monospace; font-size:12px; }}

.summary-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
@media (max-width:768px) {{ .summary-grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<h1>🔬 Enterprise SQL Generation Evaluation</h1>
<p class="subtitle">Generated: {now} | Arctic-Text2SQL-R1-7B via Colab Ollama</p>

<div class="summary-grid">
<div class="card">
    <h2>📊 Overall Results</h2>
    <div class="metrics">
        <div class="metric"><div class="value val-blue">{total_calls}</div><div class="label">Total Calls</div></div>
        <div class="metric"><div class="value val-green">{ok_calls}</div><div class="label">Succeeded</div></div>
        <div class="metric"><div class="value val-red">{error_calls}</div><div class="label">Errors</div></div>
        <div class="metric"><div class="value val-yellow">{timeout_calls}</div><div class="label">Timeouts</div></div>
        <div class="metric"><div class="value {'val-green' if overall_pct >= 70 else 'val-yellow' if overall_pct >= 40 else 'val-red'}">{overall_pct}%</div><div class="label">Overall Score</div></div>
        <div class="metric"><div class="value val-purple">{sql_extracted_count}</div><div class="label">SQL Extracted</div></div>
    </div>
</div>

<div class="card">
    <h2>⏱ Latency</h2>
    <div class="metrics">
        <div class="metric"><div class="value val-cyan">{avg_latency:.0f}ms</div><div class="label">Average</div></div>
        <div class="metric"><div class="value val-green">{p50_latency:.0f}ms</div><div class="label">Median (P50)</div></div>
        <div class="metric"><div class="value val-yellow">{p95_latency:.0f}ms</div><div class="label">P95</div></div>
    </div>
</div>
</div>

<div class="card">
    <h2>📈 Category Breakdown</h2>
    <table>
        <thead><tr><th>Category</th><th class="num">Tests</th><th>Score</th><th class="num">Avg</th></tr></thead>
        <tbody>{cat_rows}</tbody>
    </table>
</div>

<div class="card">
    <h2>🔍 Detailed Test Results</h2>
    <table>
        <thead>
            <tr>
                <th>Category</th><th>Test ID</th><th>Query</th><th>Status</th>
                <th class="num">Latency</th><th class="num">Score</th><th>SQL?</th><th>Expl?</th>
                <th>Missing</th><th>Forbidden</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
</div>

<div class="card">
    <h2>📋 Key Findings</h2>
    <ul style="list-style:none;padding:0;">
        <li style="padding:8px 0;border-bottom:1px solid #1a1a24;">
            <strong style="color:#22c55e;">✅ SQL Extraction Rate:</strong> {sql_extracted_count}/{total_calls} ({round(sql_extracted_count/max(total_calls,1)*100)}%) of responses contained valid ```sql blocks
        </li>
        <li style="padding:8px 0;border-bottom:1px solid #1a1a24;">
            <strong style="color:#3b82f6;">⚡ Average Latency:</strong> {avg_latency:.0f}ms (P50: {p50_latency:.0f}ms, P95: {p95_latency:.0f}ms)
        </li>
        <li style="padding:8px 0;border-bottom:1px solid #1a1a24;">
            <strong style="color:#eab308;">⚠ Error Rate:</strong> {error_calls + timeout_calls}/{total_calls} ({round((error_calls+timeout_calls)/max(total_calls,1)*100)}%) failed or timed out
        </li>
        <li style="padding:8px 0;">
            <strong style="color:#8b5cf6;">📋 Overall Quality Score:</strong> {overall_pct}% across all test dimensions
        </li>
    </ul>
</div>
</body>
</html>"""
    return html


# ─── Main ───────────────────────────────────────────────────────────────────

def compute_percentiles(values: List[float], percentiles: List[int]) -> Dict[str, float]:
    if not values:
        return {f"p{p}_ms": 0 for p in percentiles}
    sorted_vals = sorted(values)
    result = {}
    for p in percentiles:
        idx = max(0, min(len(sorted_vals) - 1, int(len(sorted_vals) * p / 100)))
        result[f"p{p}_ms"] = sorted_vals[idx]
    return result


def main():
    parser = argparse.ArgumentParser(description="Enterprise SQL Generation Eval")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", default="eval@test.com")
    parser.add_argument("--password", default="Eval123!")
    parser.add_argument("--shopping-dataset", default="73660f57-4bda-4958-b12b-6ffe0bab46f3")
    parser.add_argument("--education-dataset", default="ccacee66-078a-4845-9ab3-ed8f5516aa8c")
    parser.add_argument("--mode", default="sql_analyst")
    parser.add_argument("--output", default="/tmp/enterprise_sql_eval_report.html")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    # ── Login ──
    print(f"🔐 Logging in as {args.email}...")
    token = login(base_url, args.email, args.password)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print(f"   ✅ Logged in successfully")

    # ── Build test cases ──
    shopping_cases, education_cases = build_test_cases(args.shopping_dataset)

    print(f"\n📋 Test Plan:")
    print(f"   Shopping dataset ({args.shopping_dataset[:8]}...): {len(shopping_cases)} cases")
    print(f"   Education dataset ({args.education_dataset[:8]}...): {len(education_cases)} cases")
    print(f"   Total: {len(shopping_cases) + len(education_cases)} cases across 6 categories")
    print(f"   Mode: {args.mode}")

    # ── Run shopping dataset tests ──
    print(f"\n🚀 Running shopping dataset tests...")
    shopping_results = []
    for i, case in enumerate(shopping_cases):
        sys.stdout.write(f"   [{i+1}/{len(shopping_cases)}] {case.id}... ")
        sys.stdout.flush()

        conv_id = None
        if case.is_multi_turn:
            # Find conversation ID from previous multi-turn result
            for prev in reversed(shopping_results):
                if prev.case_id.startswith("multiturn") and prev.conversation_id:
                    conv_id = prev.conversation_id
                    break

        result = run_sql_chat(base_url, headers, args.shopping_dataset, case.query, args.mode, conv_id)

        sql, sql_count = extract_sql(result["response_text"])
        elements_found, elements_missing = check_elements(
            result["response_text"], sql, case.required_elements
        )
        forbidden_found = check_forbidden(result["response_text"], sql, case.forbidden_elements)
        has_exp = has_explanation(result["response_text"], sql)

        eval_result = EvalResult(
            case_id=case.id,
            category=case.category,
            query=case.query,
            status=result["status"],
            latency_ms=result["latency_ms"],
            response_text=result["response_text"][:1000],
            sql_extracted=sql[:500] if sql else None,
            sql_block_count=sql_count,
            elements_found=elements_found,
            elements_missing=elements_missing,
            forbidden_found=forbidden_found,
            has_explanation=has_exp,
            has_sql_block=sql is not None and sql_count >= case.min_sql_blocks,
            error_detail=result["error_detail"],
            conversation_id=result["conversation_id"],
            response_word_count=len(result["response_text"].split()),
        )
        shopping_results.append(eval_result)

        status = "✅" if result["status"] == "ok" else "❌"
        print(f"{status} ({result['latency_ms']:.0f}ms, sql={sql is not None})")

    # ── Run education dataset tests ──
    print(f"\n🚀 Running education dataset tests...")
    education_results = []
    for i, case in enumerate(education_cases):
        sys.stdout.write(f"   [{i+1}/{len(education_cases)}] {case.id}... ")
        sys.stdout.flush()

        result = run_sql_chat(base_url, headers, args.education_dataset, case.query, args.mode)

        sql, sql_count = extract_sql(result["response_text"])
        elements_found, elements_missing = check_elements(
            result["response_text"], sql, case.required_elements
        )
        forbidden_found = check_forbidden(result["response_text"], sql, case.forbidden_elements)
        has_exp = has_explanation(result["response_text"], sql)

        eval_result = EvalResult(
            case_id=case.id,
            category=case.category,
            query=case.query,
            status=result["status"],
            latency_ms=result["latency_ms"],
            response_text=result["response_text"][:1000],
            sql_extracted=sql[:500] if sql else None,
            sql_block_count=sql_count,
            elements_found=elements_found,
            elements_missing=elements_missing,
            forbidden_found=forbidden_found,
            has_explanation=has_exp,
            has_sql_block=sql is not None and sql_count >= case.min_sql_blocks,
            error_detail=result["error_detail"],
            conversation_id=result["conversation_id"],
            response_word_count=len(result["response_text"].split()),
        )
        education_results.append(eval_result)

        status = "✅" if result["status"] == "ok" else "❌"
        print(f"{status} ({result['latency_ms']:.0f}ms, sql={sql is not None})")

    # ── Aggregate stats ──
    all_results = shopping_results + education_results
    all_latencies = [r.latency_ms for r in all_results if r.status == "ok"]
    percentiles = compute_percentiles(all_latencies, [50, 75, 90, 95, 99])

    stats = {
        "total_calls": len(all_results),
        "ok_calls": sum(1 for r in all_results if r.status == "ok"),
        "error_calls": sum(1 for r in all_results if r.status == "error"),
        "timeout_calls": sum(1 for r in all_results if r.status == "timeout"),
        "sql_extracted": sum(1 for r in all_results if r.sql_extracted),
        "sql_with_explanation": sum(1 for r in all_results if r.has_explanation),
    }

    latency_stats = {
        "avg_ms": sum(all_latencies) / max(len(all_latencies), 1),
        "min_ms": min(all_latencies) if all_latencies else 0,
        "max_ms": max(all_latencies) if all_latencies else 0,
        **percentiles,
    }

    # ── Print summary ──
    print(f"\n{'='*60}")
    print(f"📊 EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Total calls:    {stats['total_calls']}")
    print(f"  Succeeded:      {stats['ok_calls']}")
    print(f"  Errors:         {stats['error_calls']}")
    print(f"  Timeouts:       {stats['timeout_calls']}")
    print(f"  SQL extracted:  {stats['sql_extracted']}")
    print(f"  Avg latency:    {latency_stats['avg_ms']:.0f}ms")
    print(f"  P50 latency:    {latency_stats['p50_ms']:.0f}ms")
    print(f"  P95 latency:    {latency_stats['p95_ms']:.0f}ms")
    print(f"\n📁 Results saved to: {args.output}")

    # ── Generate HTML report ──
    results_by_dataset = {
        "Customer Shopping Behavior": shopping_results,
        "Global Education Data": education_results,
    }
    html = generate_html_report(results_by_dataset, stats, latency_stats)
    Path(args.output).write_text(html, encoding="utf-8")

    # ── Save raw results as JSONL ──
    jsonl_path = Path(args.output).with_suffix(".jsonl")
    with jsonl_path.open("w") as f:
        for r in all_results:
            f.write(json.dumps(asdict(r)) + "\n")

    print(f"📁 Raw results: {jsonl_path}")
    print(f"📊 Open the HTML report in your browser to see detailed results.")
    print(f"\n{'='*60}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
