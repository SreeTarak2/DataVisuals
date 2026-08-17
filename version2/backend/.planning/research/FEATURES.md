# Enterprise Production Readiness -- Missing Features

**Domain:** AI-Powered Data Analysis Platform
**Audited:** 2026-07-04
**Focus:** Features an enterprise deployment requires that are absent or incomplete

## Table Stakes (Missing)

Enterprise features that operations teams and security auditors expect. Absence = deployment gate.

| Feature | Status | What's Needed | Complexity |
|---------|--------|---------------|------------|
| Structured JSON logging | MISSING | Structured log output (JSON) consumable by ELK/Datadog/Splunk instead of plaintext `%(asctime)s [%(levelname)s]` format | Low |
| Prometheus `/metrics` endpoint | MISSING | Register prometheus_client metrics endpoint in FastAPI so Prometheus can scrape | Low |
| Liveness / Readiness probes | INCOMPLETE | `/health` returns 200 without verifying MongoDB, LLM providers, vector DB; no `/readyz` or `/livez` | Low |
| Graceful shutdown with work draining | MISSING | SIGTERM handler that waits for in-flight agent runs to complete or abort cleanly | Medium |
| Rate limiting on ALL agent endpoints | PARTIAL | All agent routes need per-user rate limits (not just chat and auth) | Low |
| Per-user cost attribution | MISSING | Track LLM spend per user per agent run, expose via dashboard | Medium |
| Secrets management (not in git) | MISSING | Remove `.env` from git, use vault/secrets manager, add pre-commit guard | Low |
| API versioning | MISSING | Consistent URL prefix (`/api/v1/`) or header-based versioning | Medium |
| Agent-run audit logging | MISSING | Log every agent execution to audit collection (who ran what, how long, cost) | Low |
| Configuration-driven tuning | PARTIAL | Many limits (concurrency, timeouts) are hardcoded in Python modules, not env vars | Low |

## Differentiators (Would Add Value)

Features that would distinguish the platform in enterprise deployments.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Agent execution checkpointing | Mid-crash recovery: resume agent from last completed tool call | High | Requires state serialization to DB |
| LLM provider failover with cost awareness | Route to cheaper model when primary is degraded | Medium | Fallback chain exists in config.py but isn't cost-aware |
| Tenant-scoped concurrency limits | Prevent noisy-neighbor: one user's agents don't starve another | Medium | Requires workspace-aware limiter |
| Request prioritization | Premium users' agents bypass queue | Medium | Priority queue in front of executor |
| Auto-scaling agent workers | Scale agent pods based on queue depth | High | Requires Kubernetes HPA + metrics |
| Agent execution timeline visualization | Trace every tool call, LLM call, decision in a waterfall view | High | Requires exporting OTel traces to Jaeger |

## Anti-Features

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Global rate limit (shared across all users) | One abusive user degrades everyone | Use per-user rate limits (already implemented via `get_rate_limit_key`) |
| File-based secrets | Credential sprawl, hard to rotate | Environment variables -> secrets manager |
| Blocking concurrency acquire (wait forever) | Deadlock risk | Use `asyncio.wait_for(limiter.acquire(), timeout=)` with rejection on timeout |
| Custom logging framework | Maintenance burden, learning curve | Use structlog or standard library with JSON formatter |

## Feature Dependencies

```
Concurrency enforcement --> Rate limiting (both need shared state)
Prometheus metrics     --> Existing metrics module (just needs endpoint registration)
Agent audit logging    --> Existing audit service (just needs new event type)
Structured logging     --> No dependencies, can be done independently
Secrets management     --> Needs git history cleanup (retroactive)
Graceful shutdown      --> Needs asyncio coordination primitives
```

## MVP Recommendation

Immediate (must address before production deployment):

1. **Secrets management** -- Remove .env from git, rotate all credentials, add to .gitignore
2. **Prometheus /metrics endpoint** -- Register the existing prometheus_client metrics
3. **Agent execution timeout** -- Wrap agent run() in total timeout envelope
4. **Structured logging** -- Replace basicConfig with JSON log formatter
5. **Health endpoint with actual checks** -- Add MongoDB ping, LLM provider check

Defer:
- **API versioning**: Only needed when breaking changes are planned
- **Graceful shutdown with draining**: Needed for Kubernetes deployments, defer if single-instance
- **Agent checkpointing**: Worthwhile but high effort; circuit breakers mitigate some of the same risks
- **Tenant-scoped limits**: Defer until multi-tenant pressure observed

## Sources

- Direct code analysis of main.py, config.py, base_agent.py, pipeline.py, concurrency.py
- services/observability/metrics.py -- Prometheus integration exists but is unexposed
- services/audit/service.py -- Audit infrastructure exists but not connected to agent runs
- agents/telemetry/__init__.py -- OTel tracing exists but no metrics bridge
