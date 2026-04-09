import math
from typing import Any


def sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize objects, converting NaN/Inf to None."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


def ensure_json_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable objects to serializable equivalents."""
    if obj is None:
        return None
    elif isinstance(obj, dict):
        return {k: ensure_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [ensure_json_serializable(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    else:
        return str(obj)
