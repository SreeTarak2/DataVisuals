import io
import re
import logging
from collections import Counter
from typing import Any, Optional

import polars as pl

logger = logging.getLogger(__name__)

_NULL_SENTINELS = frozenset(
    {
        "",
        "-",
        "--",
        "---",
        "N/A",
        "n/a",
        "NA",
        "na",
        "null",
        "NULL",
        "None",
        "none",
        "NaN",
        "nan",
        "True",
        "False",
        "TRUE",
        "FALSE",
        "#N/A",
        "#VALUE!",
        "#REF!",
        "#DIV/0!",
        "inf",
        "-inf",
        "Inf",
        "-Inf",
    }
)


# ── Encoding Detection ────────────────────────────────────────────────────────


def detect_encoding(file_path: str) -> tuple[str, float]:
    """Detect file encoding by reading the first 100KB and using charset-normalizer.

    Returns:
        (encoding_name, confidence) tuple. Falls back to ("utf-8", 0.0) on failure.
    """
    try:
        from charset_normalizer import from_bytes

        with open(file_path, "rb") as f:
            raw_data = f.read(100 * 1024)  # First 100KB

        result = from_bytes(raw_data)
        best = result.best()
        if best and best.encoding:
            logger.info(f"  Detected encoding: {best.encoding} (confidence={best.confidence:.2f})")
            return best.encoding, best.confidence
    except ImportError:
        logger.debug("  charset-normalizer not installed; falling back to utf-8")
    except Exception as e:
        logger.debug(f"  Encoding detection failed ({e}); falling back to utf-8")

    return "utf-8", 0.0


# ── Delimiter Detection ───────────────────────────────────────────────────────


def detect_delimiter(file_path: str, encoding: str = "utf-8") -> str:
    """Detect CSV delimiter by counting occurrences outside quoted regions.

    Examines first 20 lines and picks the most consistently occurring candidate.
    Falls back to ',' if no clear winner.

    Returns:
        The detected delimiter character.
    """
    candidates = [",", ";", "\t", "|"]

    try:
        with open(file_path, "rb") as f:
            raw = f.read(50 * 1024)  # First 50KB

        try:
            text = raw.decode(encoding)
        except Exception:
            text = raw.decode("utf-8", errors="replace")

        lines = [line for line in text.split("\n")[:20] if line.strip()]
        if not lines:
            return ","
    except Exception:
        return ","

    scores: dict[str, int] = {}
    for delim in candidates:
        counts = []
        for line in lines:
            in_quote = False
            count = 0
            for char in line:
                if char == '"':
                    in_quote = not in_quote
                elif char == delim and not in_quote:
                    count += 1
            if count > 0:
                counts.append(count)

        if not counts:
            continue
        counter = Counter(counts)
        most_common_count, most_common_freq = counter.most_common(1)[0]
        consistency = most_common_freq / len(counts)
        if consistency >= 0.80 and most_common_count >= 2:
            scores[delim] = most_common_count

    if scores:
        best = max(scores, key=scores.get)
        return best

    logger.debug("  No delimiter detected with high confidence; defaulting to ','")
    return ","


# ── Numeric Parsing ───────────────────────────────────────────────────────────


def try_parse_numeric(val: str) -> float | None:
    if not isinstance(val, str):
        return None
    v = val.strip()
    if v in _NULL_SENTINELS:
        return None
    paren = re.match(r"^\(([\d,. ]+)\)$", v)
    if paren:
        v = "-" + paren.group(1)
    v = re.sub(r"[£$€¥₹₩₪₨฿]", "", v)
    v = re.sub(r"\s*[A-Z]{2,4}$", "", v)
    v = v.replace("%", "")
    v = re.sub(r"(?<=\d) (?=\d)", "", v)
    v = v.strip()
    if not v:
        return None
    if re.match(r"^\d{1,3}(\.\d{3})*,\d{1,2}$", v):
        v = v.replace(".", "").replace(",", ".")
    elif re.match(r"^\d+,\d{1,2}$", v):
        v = v.replace(",", ".")
    elif re.match(r"^-?[\d,]+$", v) and "," in v:
        v = v.replace(",", "")
    try:
        return float(v)
    except ValueError:
        return None


# ── Main Loader ───────────────────────────────────────────────────────────────


def load_dataset(file_path: str):
    """Load a dataset file and return (DataFrame, load_metadata).

    ``load_metadata`` contains detected encoding, delimiter, and other
    file-level parameters for audit logging.
    """
    file_extension = file_path.split(".")[-1].lower()
    logger.info(f"Loading {file_extension.upper()} file: {file_path}")

    load_metadata: dict = {
        "detected_encoding": "utf-8",
        "detected_encoding_confidence": 0.0,
        "detected_delimiter": ",",
        "file_type": file_extension,
    }

    if file_extension == "csv":
        encoding, enc_confidence = detect_encoding(file_path)
        load_metadata["detected_encoding"] = encoding
        load_metadata["detected_encoding_confidence"] = round(enc_confidence, 2)

        delimiter = detect_delimiter(file_path, encoding)
        load_metadata["detected_delimiter"] = delimiter

        # If encoding is not utf-8-compatible, decode in Python first
        if encoding.lower() not in ("utf-8", "utf8", "ascii", "us-ascii"):
            with open(file_path, "rb") as f:
                raw = f.read()
            text = raw.decode(encoding, errors="replace")
            buffer = io.StringIO(text)
            df = pl.read_csv(
                buffer,
                infer_schema_length=10000,
                ignore_errors=True,
                separator=delimiter,
            )
            logger.info(
                f"  Decoded CSV from {encoding} to UTF-8 in memory "
                f"(confidence={enc_confidence:.2f})"
            )
        else:
            try:
                df = pl.read_csv(
                    file_path,
                    infer_schema_length=10000,
                    ignore_errors=True,
                    separator=delimiter,
                )
            except Exception:
                logger.warning("Direct CSV read failed, retrying with encoding fallback")
                with open(file_path, "rb") as f:
                    raw = f.read()
                text = raw.decode(encoding, errors="replace")
                buffer = io.StringIO(text)
                df = pl.read_csv(
                    buffer,
                    infer_schema_length=10000,
                    ignore_errors=True,
                    separator=delimiter,
                )

    elif file_extension in ["xlsx", "xls"]:
        df = pl.read_excel(file_path)
    elif file_extension == "json":
        df = pl.read_json(file_path)
    elif file_extension == "parquet":
        df = pl.read_parquet(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")

    return df, load_metadata


def coerce_numeric_columns(
    df: pl.DataFrame,
    sample_size: int = 200,
    threshold: float = 0.80,
    min_sample: int = 5,
    track_failures: bool = True,
) -> tuple[pl.DataFrame, list[str], dict[str, dict[str, Any]]]:
    """Attempt to coerce string columns that look numeric to Float64.

    For each candidate column, a sample of non-null values is parsed via
    ``try_parse_numeric``.  If >= *threshold* parse successfully, the full
    column is coerced with an expression pipeline that handles currency
    symbols, parenthetical negatives, thousand separators, etc.

    Returns:
        (df, coerced_column_names, coercion_audit)

        *coercion_audit* is ``{col_name: {"sample_failures": [...], ...}}``
        and is empty when *track_failures* is False or no columns coerce.
    """
    coercion_audit: dict[str, dict[str, Any]] = {}
    coerce_cols: list[str] = []

    # ── First pass: detect candidate columns + collect failure samples ──
    for col in df.columns:
        if df[col].dtype not in (pl.Utf8, pl.String):
            continue
        sample = df[col].drop_nulls().head(sample_size).to_list()
        if len(sample) < min_sample:
            continue
        parsed = [try_parse_numeric(v) for v in sample]
        numeric_count = sum(1 for v in parsed if v is not None)

        if numeric_count / len(sample) >= threshold:
            coerce_cols.append(col)

            if track_failures:
                # Record unique failure values from the sample (preserve order)
                failures = list(dict.fromkeys(v for v, p in zip(sample, parsed) if p is None))
                failure_count = len(failures)
                coercion_audit[col] = {
                    "sample_failures": failures[:10],
                    "sample_failure_count": failure_count,
                    "sample_total": len(sample),
                    "sample_failure_rate": round(failure_count / len(sample), 4),
                }

    if not coerce_cols:
        return df, coerce_cols, coercion_audit

    # ── Snapshot null counts before coercion (for delta computation) ────
    pre_null_counts: dict[str, int] = {}
    if track_failures:
        pre_null_counts = {col: df[col].null_count() for col in coerce_cols}

    # ── Apply coercion expressions ──────────────────────────────────────
    coerce_exprs = []
    for col in coerce_cols:
        expr = (
            pl.col(col)
            .str.strip_chars()
            .str.replace_all(r"^\((.+)\)$", r"-$1")
            .str.replace_all(r"[£$€¥₹₩₪₨฿]", "")
            .str.replace_all(r"\s+[A-Z]{2,4}$", "")
            .str.replace_all(r"%$", "")
            .str.replace_all(r"(\d) (\d)", r"$1$2")
            .str.replace_all(r"\.(\d{3})", "█TEMP█$1")
            .str.replace_all(r",", ".")
            .str.replace_all(r"█TEMP█", ",")
            .str.replace_all(r",(\d{3})([^0-9]|$)", r"$1$2")
            .str.strip_chars()
            .cast(pl.Float64, strict=False)
            .alias(col)
        )
        coerce_exprs.append(expr)

    df = df.with_columns(coerce_exprs)

    # ── Post-coercion audit: compute failure delta per column ───────────
    if track_failures and coerce_cols:
        failure_cols = []
        for col in coerce_cols:
            null_before = pre_null_counts[col]
            null_after = df[col].null_count()
            parse_failures = null_after - null_before
            if parse_failures > 0:
                coercion_audit[col]["full_column_parse_failures"] = int(parse_failures)
                failure_cols.append(col)

        if failure_cols:
            logger.info(
                "  Numeric coercion: %d cols promoted — %d had parse failures "
                "(%d nulls before → %d after)",
                len(coerce_cols),
                len(failure_cols),
                sum(pre_null_counts.values()),
                sum(df[c].null_count() for c in coerce_cols),
            )
        else:
            logger.info(
                "✓ Numeric coercion: %d columns — all values parsed successfully",
                len(coerce_cols),
            )
    else:
        logger.info(
            "✓ Numeric coercion: %d columns promoted String→Float64: %s",
            len(coerce_cols),
            coerce_cols,
        )

    return df, coerce_cols, coercion_audit


__all__ = ["load_dataset", "coerce_numeric_columns", "detect_encoding", "detect_delimiter"]
