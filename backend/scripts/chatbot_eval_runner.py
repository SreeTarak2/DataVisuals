#!/usr/bin/env python3
"""
Run repeatable chatbot evaluations against DataSage backend and export results
for prompt tuning.

Usage example:
  python scripts/chatbot_eval_runner.py \
    --base-url http://localhost:8000 \
    --email you@example.com \
    --password 'your-password' \
    --dataset-id <DATASET_ID> \
    --modes deep learning quick
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


def now_utc() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def slug_time() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def request_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    response = requests.request(method, url, headers=headers, json=payload, timeout=timeout)
    try:
        data = response.json() if response.text else {}
    except json.JSONDecodeError:
        data = {"raw_text": response.text}
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {url} failed ({response.status_code}): {data}")
    return data


def login(base_url: str, email: str, password: str) -> str:
    data = request_json(
        "POST",
        f"{base_url}/api/auth/login",
        payload={"email": email, "password": password},
        timeout=60,
    )
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"Login succeeded but no access_token in response: {data}")
    return token


def auth_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def get_datasets(base_url: str, token: str) -> List[Dict[str, Any]]:
    data = request_json("GET", f"{base_url}/api/datasets/", headers=auth_headers(token), timeout=60)
    return data.get("datasets", [])


def dataset_id_of(dataset: Dict[str, Any]) -> Optional[str]:
    return dataset.get("id") or dataset.get("_id")


def resolve_dataset(datasets: List[Dict[str, Any]], dataset_id: Optional[str]) -> Dict[str, Any]:
    if not datasets:
        raise RuntimeError("No datasets found for this user.")
    if dataset_id:
        for ds in datasets:
            if dataset_id_of(ds) == dataset_id:
                return ds
        raise RuntimeError(f"Dataset '{dataset_id}' not found. Available IDs: {[dataset_id_of(d) for d in datasets]}")
    return datasets[0]


def get_columns(base_url: str, token: str, dataset_id: str) -> List[Dict[str, Any]]:
    try:
        data = request_json(
            "GET",
            f"{base_url}/api/datasets/{dataset_id}/columns",
            headers=auth_headers(token),
            timeout=60,
        )
        return data.get("columns", [])
    except Exception:
        return []


def pick_columns(columns: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    def is_id_like(name: str) -> bool:
        low = name.lower()
        return bool(re.search(r"(^id$|_id$|^id_|_id_|uuid|identifier)", low))

    numeric = [c["name"] for c in columns if c.get("is_numeric") and not is_id_like(c["name"])]
    categorical = [c["name"] for c in columns if c.get("is_categorical") and not is_id_like(c["name"])]
    temporal = [c["name"] for c in columns if c.get("is_temporal")]
    return {
        "num1": numeric[0] if len(numeric) >= 1 else None,
        "num2": numeric[1] if len(numeric) >= 2 else None,
        "cat1": categorical[0] if len(categorical) >= 1 else None,
        "cat2": categorical[1] if len(categorical) >= 2 else None,
        "time1": temporal[0] if len(temporal) >= 1 else None,
    }


def fill(template: str, slots: Dict[str, Optional[str]]) -> str:
    out = template
    for key, value in slots.items():
        out = out.replace("{" + key + "}", value or f"<{key.upper()}_MISSING>")
    return out


def build_default_cases(slots: Dict[str, Optional[str]]) -> List[Dict[str, str]]:
    cases: List[Dict[str, str]] = [
        {
            "id": "summary_exec",
            "group": "single_1",
            "query": "Give me an executive summary with the top 3 business insights from this dataset.",
        },
        {
            "id": "outliers_rootcause",
            "group": "single_2",
            "query": fill(
                "Find outliers in `{num1}` and provide plausible root causes grounded in available columns.",
                slots,
            ),
        },
        {
            "id": "segment_lift",
            "group": "single_3",
            "query": fill(
                "Segment `{num1}` by `{cat1}` and highlight which segments overperform or underperform with evidence.",
                slots,
            ),
        },
        {
            "id": "multi_1_context",
            "group": "multi_turn",
            "query": "What are the 3 most important findings here? Keep it concise.",
        },
        {
            "id": "multi_2_followup",
            "group": "multi_turn",
            "query": fill(
                "Take finding #1 and break it down by `{cat1}`. Explain what could bias this conclusion.",
                slots,
            ),
        },
        {
            "id": "multi_3_action",
            "group": "multi_turn",
            "query": "Propose 3 concrete actions with expected impact and risk for each.",
        },
    ]

    if slots.get("time1"):
        cases.append(
            {
                "id": "trend_seasonality",
                "group": "single_4",
                "query": fill(
                    "Analyze trend and seasonality of `{num1}` over `{time1}`. Point out any structural breaks.",
                    slots,
                ),
            }
        )

    if slots.get("num2"):
        cases.append(
            {
                "id": "correlation_causality",
                "group": "single_5",
                "query": fill(
                    "Evaluate relationship between `{num1}` and `{num2}`. Distinguish correlation from causation and mention confounders.",
                    slots,
                ),
            }
        )

    return cases


def detect_flags(text: str) -> Dict[str, int]:
    low = text.lower()
    flags = {
        "generic_response": int(bool(re.search(r"\b(i can help|i'm here to help|how can i help)\b", low))),
        "hallucination_risk": int(bool(re.search(r"\bdefinitely|certainly|always\b", low) and "not enough" in low)),
        "missing_followups": int("---" not in text),
        "missing_numbers": int(not bool(re.search(r"\d", text))),
    }
    return flags


def run_cases(
    base_url: str,
    token: str,
    dataset_id: str,
    cases: List[Dict[str, str]],
    modes: List[str],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for mode in modes:
        group_to_conversation: Dict[str, Optional[str]] = {}
        for i, case in enumerate(cases, start=1):
            group = case["group"]
            conversation_id = group_to_conversation.get(group)
            payload = {"message": case["query"], "conversation_id": conversation_id}
            url = f"{base_url}/api/datasets/{dataset_id}/chat?mode={mode}"
            started = time.time()
            status = "ok"
            error_text = ""
            response_text = ""
            response_json: Dict[str, Any] = {}
            try:
                response_json = request_json(
                    "POST",
                    url,
                    headers=auth_headers(token),
                    payload=payload,
                    timeout=240,
                )
                conversation_id = response_json.get("conversation_id", conversation_id)
                group_to_conversation[group] = conversation_id
                response_text = (
                    response_json.get("response")
                    or response_json.get("response_text")
                    or ""
                )
            except Exception as exc:
                status = "error"
                error_text = str(exc)
            latency_ms = round((time.time() - started) * 1000, 2)
            flags = detect_flags(response_text) if response_text else {}
            out.append(
                {
                    "run_at_utc": now_utc(),
                    "mode": mode,
                    "case_index": i,
                    "case_id": case["id"],
                    "group": group,
                    "query": case["query"],
                    "status": status,
                    "latency_ms": latency_ms,
                    "conversation_id": conversation_id,
                    "has_chart": bool(response_json.get("chart_config")),
                    "response_text": response_text,
                    "response_word_count": len(response_text.split()) if response_text else 0,
                    "error": error_text,
                    "flags": flags,
                }
            )
    return out


def write_outputs(results: List[Dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "results.jsonl"
    csv_path = out_dir / "results.csv"
    score_path = out_dir / "scoring_template.csv"
    summary_path = out_dir / "summary.md"

    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")

    flat_fields = [
        "run_at_utc",
        "mode",
        "case_index",
        "case_id",
        "group",
        "status",
        "latency_ms",
        "has_chart",
        "response_word_count",
        "conversation_id",
        "query",
        "response_text",
        "error",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=flat_fields)
        writer.writeheader()
        for row in results:
            writer.writerow({k: row.get(k, "") for k in flat_fields})

    score_fields = [
        "case_id",
        "mode",
        "query",
        "response_text",
        "faithfulness_1_5",
        "analytical_depth_1_5",
        "specificity_1_5",
        "actionability_1_5",
        "format_quality_1_5",
        "prompt_fix_notes",
    ]
    with score_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=score_fields)
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    "case_id": row["case_id"],
                    "mode": row["mode"],
                    "query": row["query"],
                    "response_text": row["response_text"],
                    "faithfulness_1_5": "",
                    "analytical_depth_1_5": "",
                    "specificity_1_5": "",
                    "actionability_1_5": "",
                    "format_quality_1_5": "",
                    "prompt_fix_notes": "",
                }
            )

    total = len(results)
    errors = sum(1 for r in results if r["status"] != "ok")
    charts = sum(1 for r in results if r["has_chart"])
    avg_latency = round(sum(r["latency_ms"] for r in results) / total, 2) if total else 0
    with summary_path.open("w", encoding="utf-8") as f:
        f.write("# Chatbot Eval Summary\n\n")
        f.write(f"- Total test calls: {total}\n")
        f.write(f"- Failed calls: {errors}\n")
        f.write(f"- Responses with chart_config: {charts}\n")
        f.write(f"- Average latency (ms): {avg_latency}\n\n")
        f.write("## Next Step\n")
        f.write("Review `scoring_template.csv`, fill scores, and cluster `prompt_fix_notes` into recurring prompt issues.\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DataSage chatbot evaluation suite.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL.")
    parser.add_argument("--email", required=True, help="Login email.")
    parser.add_argument("--password", required=True, help="Login password.")
    parser.add_argument("--dataset-id", default=None, help="Dataset ID. If omitted, uses first dataset.")
    parser.add_argument("--modes", nargs="+", default=["deep"], help="Chat modes to test (deep/learning/quick/forecast).")
    parser.add_argument(
        "--queries-file",
        default=None,
        help="Optional JSON file with list of {'id','group','query'} items.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory. Default: backend/evals/<timestamp>",
    )
    return parser.parse_args()


def load_cases(args: argparse.Namespace, slots: Dict[str, Optional[str]]) -> List[Dict[str, str]]:
    if not args.queries_file:
        return build_default_cases(slots)
    path = Path(args.queries_file)
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise RuntimeError(f"--queries-file must be a JSON list, got: {type(raw)}")
    cases: List[Dict[str, str]] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"Invalid query item at index {idx}: {item}")
        query = fill(str(item.get("query", "")), slots)
        if not query.strip():
            raise RuntimeError(f"Empty query at index {idx}")
        cases.append(
            {
                "id": str(item.get("id", f"custom_{idx}")),
                "group": str(item.get("group", f"custom_group_{idx}")),
                "query": query,
            }
        )
    return cases


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    try:
        token = login(base_url, args.email, args.password)
        datasets = get_datasets(base_url, token)
        dataset = resolve_dataset(datasets, args.dataset_id)
        dataset_id = dataset_id_of(dataset)
        if not dataset_id:
            raise RuntimeError(f"Resolved dataset has no id/_id: {dataset}")
        columns = get_columns(base_url, token, dataset_id)
        slots = pick_columns(columns)
        cases = load_cases(args, slots)
        results = run_cases(base_url, token, dataset_id, cases, args.modes)
        out_dir = Path(args.out_dir) if args.out_dir else Path("evals") / slug_time()
        write_outputs(results, out_dir)
        print(f"Completed {len(results)} calls. Outputs written to: {out_dir}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
