# Production Readiness -- Technology Gaps

**Project:** DataSage Backend
**Audited:** 2026-07-04

## Current Stack vs Enterprise Requirements

| Concern | Current | What's Missing | Recommended Addition |
|---------|---------|---------------|-------------------|
| Logging | `logging.basicConfig` with text format | JSON-structured logs for log aggregators | `python-json-logger` or `structlog` with JSON renderer |
| Metrics | `prometheus_client` counters/histograms (no-op if unavailable) | Registered `/metrics` endpoint, agent-specific metrics | `prometheus_client` + FastAPI middleware for request metrics |
| Tracing | OpenTelemetry SDK (no-op if unavailable) | Required export endpoint, metrics bridge | OTel SDK with configured OTLP exporter |
| Secrets | `.env` file committed to git | Secrets manager, gitignored .env, pre-commit guard | `python-dotenv` + `git-crypt` or HashiCorp Vault |
| Rate limiting | `slowapi` with per-user key | Rate limits on ALL agent endpoints | Already have `RateLimits` class -- just apply decorators |
| Queue/backpressure | None beyond asyncio semaphore | Bounded queue for pending agent requests | `asyncio.Queue` (single-process) or Redis-backed queue |
| Structured error reporting | `logger.error(f"...")` format strings | Structured error objects with correlation IDs | `CustomJSONResponse` already exists -- extend for errors |
| API versioning | None (mixed route prefixes) | Consistent versioning strategy | URL prefix `/api/v1/` |

## Recommended Additions for Enterprise

### Logging
```bash
pip install python-json-logger
```

```python
# In main.py
from pythonjsonlogger import jsonlogger
handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(correlation_id)s %(message)s"
)
handler.setFormatter(formatter)
logging.getLogger().addHandler(handler)
# Remove the existing basicConfig or adjust it
```

### Metrics Endpoint
```bash
pip install prometheus-client
```

```python
# In main.py
from prometheus_fastapi_instrumentator import Instrumentator
# or manually:
from prometheus_client import make_asgi_app
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

### Configuration Additions (core/config.py)
```python
# Missing settings that should exist
AGENT_RUN_TIMEOUT: int = int(os.getenv("AGENT_RUN_TIMEOUT", "300"))
AGENT_CONCURRENCY_CHAT: int = int(os.getenv("AGENT_CONCURRENCY_CHAT", "3"))
AGENT_CONCURRENCY_ANALYST: int = int(os.getenv("AGENT_CONCURRENCY_ANALYST", "3"))
AGENT_CONCURRENCY_KPI: int = int(os.getenv("AGENT_CONCURRENCY_KPI", "3"))
AGENT_CONCURRENCY_PROFILE: int = int(os.getenv("AGENT_CONCURRENCY_PROFILE", "5"))
AGENT_CONCURRENCY_CHART: int = int(os.getenv("AGENT_CONCURRENCY_CHART", "3"))
METRICS_ENABLED: bool = os.getenv("METRICS_ENABLED", "true").lower() == "true"
AUDIT_AGENT_RUNS: bool = os.getenv("AUDIT_AGENT_RUNS", "true").lower() == "true"
```

## Sources

- Direct analysis of main.py logging configuration (lines 18-27)
- Direct analysis of config.py (442 lines) -- complete settings inventory
- Direct analysis of .env.example (112 lines) -- documented env vars
- `prometheus_fastapi_instrumentator` is community standard for FastAPI+Prometheus integration
