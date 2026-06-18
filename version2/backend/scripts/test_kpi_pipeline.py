"""Standalone KPI Pipeline Test Runner.

Runs the REAL production IntelligentKPIGenerator pipeline end-to-end
with actual LLM calls via OpenRouter. No FastAPI server, no MongoDB, no cache.

Usage (from version2/backend/):
  python scripts/test_kpi_pipeline.py --csv data.csv
  python scripts/test_kpi_pipeline.py --csv data.csv --verbose
  python scripts/test_kpi_pipeline.py --csv data.csv --output kpis.json
  python scripts/test_kpi_pipeline.py --generate-sample
  python scripts/test_kpi_pipeline.py --generate-sample --verbose
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# Ensure the backend root is on sys.path so that "from core.config" etc. work
_backend_root = str(Path(__file__).resolve().parent.parent)
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

import polars as pl
from core.config import settings
from services.ai.intelligent_kpi_generator import IntelligentKPIGenerator

_original_call = None
_logged_prompts: List[Dict[str, Any]] = []


async def _logged_llm_call(
    prompt: str,
    model_role: Optional[str] = None,
    expect_json: bool = False,
    temperature: float = 0.1,
    max_tokens: int = 800,
    **kwargs: Any,
) -> Any:
    call_num = len(_logged_prompts) + 1
    entry = {
        "call_num": call_num,
        "model_role": model_role,
        "timestamp": datetime.now().isoformat(),
        "prompt": prompt,
        "response": None,
        "duration_ms": None,
    }

    print(f"\n{'╔' + '═' * 62 + '╗'}")
    print(f"║  LLM CALL #{call_num}  model_role={model_role}")
    print(f"{'╚' + '═' * 62 + '╝'}")
    print(f"\nPROMPT:\n{'─' * 62}")
    print(prompt[:4000])
    if len(prompt) > 4000:
        print(f"\n... (truncated, full length={len(prompt)} chars)")
    print(f"{'─' * 62}")

    start = time.time()
    response = await _original_call(
        prompt=prompt,
        model_role=model_role,
        expect_json=expect_json,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    duration = time.time() - start

    entry["response"] = response
    entry["duration_ms"] = round(duration * 1000)
    _logged_prompts.append(entry)

    print(f"\nRESPONSE ({duration:.1f}s):\n{'─' * 62}")
    try:
        print(json.dumps(response, indent=2, default=str)[:3000])
    except Exception:
        print(str(response)[:3000])
    print(f"{'═' * 62}\n")

    return response


def enable_verbose_logging() -> None:
    global _original_call
    from services.llm_router import llm_router

    _original_call = llm_router.call
    llm_router.call = _logged_llm_call


SAMPLE_SAAS = """date,revenue,cost,users,new_users,churned_users,mrr
2024-01-01,120000,45000,1500,120,45,125000
2024-02-01,135000,48000,1620,135,40,140000
2024-03-01,128000,47000,1580,110,50,132000
2024-04-01,142000,49000,1720,145,35,148000
2024-05-01,158000,52000,1850,160,30,162000
2024-06-01,165000,54000,1950,175,28,170000
2024-07-01,172000,55000,2050,180,32,178000
2024-08-01,180000,57000,2120,190,35,186000
2024-09-01,175000,56000,2080,170,40,181000
2024-10-01,190000,58000,2200,200,30,196000
2024-11-01,210000,62000,2400,220,28,215000
2024-12-01,225000,65000,2600,250,25,230000
"""

SAMPLE_ECOMMERCE = """date,revenue,orders,visitors,aov,cogs
2024-01-01,45000,320,12000,140.62,27000
2024-02-01,52000,380,13500,136.84,31200
2024-03-01,48000,350,12800,137.14,28800
2024-04-01,55000,400,14000,137.50,33000
2024-05-01,58000,420,14500,138.10,34800
2024-06-01,62000,450,15000,137.78,37200
2024-07-01,60000,430,14800,139.53,36000
2024-08-01,65000,470,15500,138.30,39000
2024-09-01,63000,455,15200,138.46,37800
2024-10-01,68000,490,16000,138.78,40800
2024-11-01,72000,520,17000,138.46,43200
2024-12-01,78000,560,18000,139.29,46800
"""

SAMPLE_AUTOMOTIVE = """price,year,mileage,fuel_type,engine_size,transmission
25000,2021,15000,Petrol,2.0,Automatic
18500,2019,42000,Diesel,1.6,Manual
32000,2022,8000,Petrol,2.5,Automatic
15000,2018,65000,Petrol,1.8,Manual
22000,2020,28000,Diesel,2.0,Automatic
28000,2023,5000,Electric,0.0,Automatic
16500,2017,55000,Petrol,1.6,Manual
35000,2022,12000,Petrol,3.0,Automatic
19500,2019,38000,Diesel,2.0,Manual
30000,2021,18000,Petrol,2.5,Automatic
"""


def generate_sample_data(target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    samples = {
        "saas_revenue.csv": SAMPLE_SAAS,
        "ecommerce_orders.csv": SAMPLE_ECOMMERCE,
        "vehicle_listings.csv": SAMPLE_AUTOMOTIVE,
    }
    for name, content in samples.items():
        path = target_dir / name
        path.write_text(content)
        print(f"  Created: {path}")
    print(f"\nSample files in: {target_dir}")


def print_kpi_summary(kpis: List[Dict[str, Any]]) -> None:
    kpi_count = len([k for k in kpis if k.get("type") == "kpi"])
    insight_count = len([k for k in kpis if k.get("type") == "insight"])
    print(f"\n{'=' * 62}")
    print(f"  Total items: {len(kpis)}  |  KPIs: {kpi_count}  |  Insights: {insight_count}")
    print(f"{'=' * 62}")
    for i, kpi in enumerate(kpis):
        if kpi.get("type") != "kpi":
            continue
        title = kpi.get("title", "?")
        val = kpi.get("value", "?")
        fmt = kpi.get("format", "number")
        delta = kpi.get("delta_percent")
        imp = kpi.get("importance", "?")
        domain = kpi.get("archetype", kpi.get("business_category", "?"))
        delta_str = f"  Δ={delta:+.1f}%" if delta is not None else ""
        print(f"  [{imp:<6}] {title:<30} {_fmt_preview(val, fmt):>12}{delta_str}  ({domain})")


def _fmt_preview(val: Any, fmt: str) -> str:
    if val is None:
        return "N/A"
    try:
        v = float(val)
    except (TypeError, ValueError):
        return str(val)[:15]
    if fmt == "currency":
        if abs(v) >= 1_000_000:
            return f"${v / 1_000_000:.2f}M"
        if abs(v) >= 1_000:
            return f"${v / 1_000:.1f}K"
        return f"${v:.0f}"
    if fmt == "percentage":
        return f"{v:.1f}%"
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:.1f}K"
    return f"{v:.1f}"


async def run_pipeline(
    csv_path: str,
    max_kpis: int = 6,
    verbose: bool = False,
    domain: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if verbose:
        enable_verbose_logging()

    print(f"\nLoading: {csv_path}")
    df = pl.read_csv(csv_path)
    print(f"  Rows: {len(df):,}  Columns: {len(df.columns)}  Names: {list(df.columns)}")
    print(f"  Dtypes: {dict(df.schema)}")

    generator = IntelligentKPIGenerator()

    print(f"\nRunning KPI pipeline (max_kpis={max_kpis})...")
    if domain:
        print(f"  Using explicit domain: {domain}")
    start = time.time()
    kpis = await generator.generate_intelligent_kpis(
        df,
        domain=domain,
        max_kpis=max_kpis,
    )
    duration = time.time() - start

    print(f"\nPipeline finished in {duration:.1f}s")
    print_kpi_summary(kpis)

    if verbose and _logged_prompts:
        total_llm_ms = sum(e["duration_ms"] for e in _logged_prompts if e["duration_ms"])
        print(f"\nLLM Call Summary:")
        for entry in _logged_prompts:
            ms = entry["duration_ms"]
            print(
                f"  #{entry['call_num']}: {entry['model_role']:<25} ({ms}ms)"
                if ms
                else f"  #{entry['call_num']}: {entry['model_role']:<25}"
            )
        print(f"  Total LLM time: {total_llm_ms / 1000:.1f}s")

    return kpis


def main() -> None:
    parser = argparse.ArgumentParser(
        description="KPI Pipeline Test Runner — exercises the REAL production KPI generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --generate-sample\n"
            "  %(prog)s --csv sample_data/saas_revenue.csv --verbose\n"
            "  %(prog)s --csv my_data.csv --output kpis.json --verbose\n"
            "  %(prog)s --csv sample_data/vehicle_listings.csv --domain automotive-metrics\n"
        ),
    )
    parser.add_argument("--csv", help="Path to input CSV file")
    parser.add_argument("--output", "-o", help="Save KPI JSON output to file")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print every LLM prompt and response"
    )
    parser.add_argument(
        "--max-kpis", type=int, default=6, help="Maximum KPIs to generate (default: 6)"
    )
    parser.add_argument(
        "--domain", help="Override domain detection (e.g. saas-metrics, ecommerce-metrics)"
    )
    parser.add_argument(
        "--generate-sample", action="store_true", help="Generate sample CSV datasets and exit"
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    script_dir = Path(__file__).parent
    sample_dir = script_dir / "sample_data"

    if args.generate_sample:
        print("Generating sample datasets...")
        generate_sample_data(sample_dir)
        return

    if not args.csv:
        default_csv = sample_dir / "saas_revenue.csv"
        if default_csv.exists():
            args.csv = str(default_csv)
            print(f"No --csv given, using sample: {args.csv}")
        else:
            parser.error("--csv is required. Run --generate-sample first to create sample data.")

    kpis = asyncio.run(
        run_pipeline(
            csv_path=args.csv,
            max_kpis=args.max_kpis,
            verbose=args.verbose,
            domain=args.domain,
        )
    )

    indent = 2 if args.pretty else None
    output = json.dumps(kpis, indent=indent, default=str, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output)
        print(f"\nWritten {len(kpis)} KPIs to {args.output}")

    print(f"\n{'─' * 62}")
    print("JSON output:")
    print(output[:5000])
    if len(output) > 5000:
        print(f"... (truncated, {len(output)} chars total)")


if __name__ == "__main__":
    main()
