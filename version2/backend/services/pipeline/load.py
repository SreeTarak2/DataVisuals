import re
import logging

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


def load_dataset(file_path: str) -> pl.DataFrame:
    file_extension = file_path.split(".")[-1].lower()
    logger.info(f"Loading {file_extension.upper()} file: {file_path}")

    if file_extension == "csv":
        df = pl.read_csv(file_path, infer_schema_length=10000, ignore_errors=True)
    elif file_extension in ["xlsx", "xls"]:
        df = pl.read_excel(file_path)
    elif file_extension == "json":
        df = pl.read_json(file_path)
    elif file_extension == "parquet":
        df = pl.read_parquet(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_extension}")

    return df


def coerce_numeric_columns(
    df: pl.DataFrame,
    sample_size: int = 200,
    threshold: float = 0.80,
    min_sample: int = 5,
) -> tuple[pl.DataFrame, list[str]]:
    coerce_cols: list[str] = []
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

    if coerce_cols:
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
        logger.info(
            f"✓ Numeric coercion: {len(coerce_cols)} columns promoted String→Float64: {coerce_cols}"
        )

    return df, coerce_cols


__all__ = ["load_dataset", "coerce_numeric_columns"]
