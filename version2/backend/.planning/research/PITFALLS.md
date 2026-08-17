# Enterprise Readiness Pitfalls

**Domain:** AI-Powered Data Analysis Platform
**Audited:** 2026-07-04

## Critical Pitfalls

### Pitfall 1: Production Secrets in Version Control

**What goes wrong:** The `.env` file (committed to git) contains real MongoDB Atlas credentials (username+password+hostname), real OpenRouter API keys, real HuggingFace API keys, and real Google OAuth client credentials. Anyone with repo access — including CI systems, collaborators, or attackers who find a cloned copy — has full database access and paid API quotas.

**Why it happens:** `.env` was not added to `.gitignore`. The file naturally lives at the project root and was committed during setup.

**Consequences:** Database compromise (data exfiltration, deletion, ransom), API key abuse (thousands of dollars in LLM charges), OAuth credential abuse (account takeover).

**Prevention:**
1. Immediately add `.env` to `.gitignore`
2. Remove `.env` from git history (`git rm --cached .env` + BFG Repo-Cleaner or `git filter-branch`)
3. Rotate ALL exposed credentials (MongoDB password, OpenRouter key, HuggingFace key, Google OAuth secret)
4. Use `.env.example` with placeholder values as the committed template
5. Consider a secrets manager (Vault, AWS Secrets Manager) for production

**Detection:** Run `git log --all --full-history -- .env` to confirm it was committed. Check CI logs for exposed env vars.

### Pitfall 2: Observability Is Optional (Silent Degradation)

**What goes wrong:** Prometheus metrics (`services/observability/metrics.py`) and OpenTelemetry tracing (`agents/telemetry/__init__.py`) both fall back to no-op implementations when their respective packages are not installed. No warning is emitted at startup. A production deployment could run for weeks with zero metrics and zero traces without anyone noticing.

**Why it happens:** The try/except pattern for optional dependencies swallows failures silently. `_PROM_AVAILABLE = False` is not logged at WARNING level.

**Consequences:** Operations teams have zero visibility into system health. Performance regressions, error spikes, and latency increases go undetected until users report issues.

**Prevention:**
1. Log a WARNING (not INFO) when observability packages are unavailable
2. Add a startup check that verifies metrics/tracing are configured in production mode
3. Register Prometheus `/metrics` endpoints as a required route in production

**Detection:** Check startup logs — "OpenTelemetry not available" and "Prometheus unavailable" are logged at INFO level only.

### Pitfall 3: Concurrency Limits Are Advisory, Not Enforced

**What goes wrong:** `agent_concurrency_limiter.try_acquire()` returns `False` when the slot limit is reached, but the agent code in `base_agent.py` (lines 124-135) logs a warning and **runs the agent anyway**. The concurrency slot is never acquired, meaning N+1 agents run concurrently. Under high load, this cascades into resource exhaustion.

**Why it happens:** `try_acquire` is used instead of `acquire` (blocking), and the "run anyway" path is the current behavior.

**Consequences:** Database connection pool exhaustion, LLM provider rate limiting (429 errors), memory pressure from concurrent agent execution, unpredictable latency.

**Prevention:**
1. Replace `try_acquire` with `acquire` (blocking with timeout) or reject with 429
2. Add a queue/buffer with bounded size for pending requests
3. Make all concurrency limits env-configurable
4. Remove the "run anyway with warning" code path entirely

**Detection:** Look for `Concurrency limit.*reached` warnings in logs. If they appear, the system is silently overloading itself.

### Pitfall 4: No Total Agent Execution Timeout

**What goes wrong:** Individual LLM calls have timeouts (`AGENT_LLM_TIMEOUT=120s`) but the entire agent `run()` or `run_streaming()` method has no envelope timeout. An agent executing dozens of tool call iterations could run for many minutes, holding concurrency slots, database connections, and memory.

**Why it happens:** Only the individual LLM call (`asyncio.wait_for` around `llm_router.call`) has a timeout. The `_run_loop` and `_synthesize` methods have no timeout wrapping.

**Consequences:** Runaway agents that consume resources indefinitely. Concurrency slots are held hostage, preventing other users' requests from executing. Memory grows unbounded.

**Prevention:**
1. Wrap the entire `run()` body in `asyncio.wait_for(..., timeout=settings.AGENT_RUN_TIMEOUT)`
2. Add env var `AGENT_RUN_TIMEOUT` with a reasonable default (e.g., 300s)
3. Ensure partial results are saved when timeout fires

**Detection:** Check for agents running longer than expected. Monitor agent execution duration via a new metric.

### Pitfall 5: Graceful Shutdown Does Not Drain In-Flight Work

**What goes wrong:** The `shutdown_event` handler (main.py lines 269-276) closes HTTP client and MongoDB connection but does not wait for active agent executions to complete. When the process receives SIGTERM (Kubernetes pod termination, deployment roll), in-flight agents are abruptly killed mid-execution, potentially corrupting shared state and leaving dangling DB writes.

**Why it happens:** No coordination mechanism (asyncio.Event) exists between the shutdown handler and active agent runs.

**Consequences:** Partial writes to MongoDB (orphaned records), leaked connections, inconsistent state, user-facing errors during deployments.

**Prevention:**
1. Add `app.state.shutdown_event = asyncio.Event()` 
2. Pass this event to agent `run()` so they can abort when shutdown is signaled
3. In shutdown_event, set the event and wait for active agents (with a hard timeout)
4. Register SIGTERM/SIGINT handlers explicitly in uvicorn config

**Detection:** Review shutdown logs for abrupt connection closures. Check for orphaned records after deployments.

## Moderate Pitfalls

### Pitfall 6: No Audit Logging for Agent Executions

**What goes wrong:** Chat interactions are logged to the audit service (`services/audit/service.py`) but agent runs — including which tools were called, decisions made, duration, and success/failure — are not. Operations teams cannot trace why specific analysis decisions were made or attribute LLM costs to specific agent runs.

**Prevention:** Add a single `audit_service.log_agent_run()` call in `base_agent.py`'s `run()` method (before the return statement), capturing user_id, agent_type, query, tools_used, iterations, duration, and token budget consumed.

### Pitfall 7: API Inconsistency

**What goes wrong:** Routes are a mix of patterns: `/api/auth`, `/api/chat`, `/api/v1/charts/overlay`, `/api/analysis`, `/api/ai`. There's no consistent URL versioning. The FastAPI app reports `version="4.0.0"` but no route is namespaced to this version. Adding a breaking change means either duplicating routes or breaking existing clients.

**Prevention:** Decide on a versioning strategy (URL prefix `/api/v1/` or header-based) and apply consistently. Add deprecation headers (`Sunset` header) to old routes.

### Pitfall 8: Hardcoded Limits in Module Code

**What goes wrong:** In `agents/resilience/concurrency.py`, `DEFAULT_MAX_CONCURRENCY = 3` and `AGENT_MAX_CONCURRENCY` dict are hardcoded. In `agents/multi/pipeline.py`, `AGENT_TIMEOUTS` dict is hardcoded. Operators cannot tune these without code changes.

**Prevention:** Move all limits to `core/config.py` Settings class with env var backing. Pass settings into modules via dependency injection or a shared settings object.

### Pitfall 9: Health Endpoint Is Superficial

**What goes wrong:** `GET /health` always returns `{"status": "healthy"}` without verifying MongoDB connectivity, LLM provider availability, or circuit breaker health. A completely shattered system would still report healthy. `GET /health/agents` checks circuit breaker state but not agent registration or model availability.

**Prevention:** Add actual dependency checks: MongoDB ping, LLM provider health check, vector DB availability. Return `503` with details when dependencies are down.

## Minor Pitfalls

### Pitfall 10: DB_ENCRYPTION_KEY Falls Back to SECRET_KEY

Violates the cryptographic principle of separate keys. Though documented with a warning, the fallback exists and could be silently active in production.

### Pitfall 11: CSRF Protection Gated by Env Var Defaulting to False

`CSRF_ENABLED=false` is the default in config.py (line 413). Production operators who miss this env var will deploy without CSRF protection.

### Pitfall 12: CSP Includes unsafe-eval

Documented as a Plotly dependency, but a CSP violation reporting endpoint is optional (`CSP_REPORT_URI` env var). Without the report endpoint, CSP violations go undetected.

### Pitfall 13: Agent run() Raises Exception on Unexpected Failure

If `_run_loop()` raises an exception that isn't caught internally (e.g., a RuntimeError or asyncio.CancelledError), the `run()` method in `base_agent.py` has no outer `try/except` — the exception propagates to the caller unhandled, and concurrency releases in the `finally` block are the only recovery.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Agent run audit | Audit service already exists for chat; easy to extend | Add agent_run event type + log call in base_agent.run() |
| Queue/buffer design | Over-engineering with Redis when in-memory suffices | Start with bounded asyncio.Queue, add Redis if multi-process needed |
| API versioning | Picking a strategy that requires all-client migration | Start with `/api/v1/` prefix on new routes, dual-support old routes with deprecation |
| Secrets management | Committing new .env files | Add pre-commit hook: `git diff --cached --name-only | grep .env` → reject |

## Sources

- Direct code analysis of 12+ source files across the backend
- `.env` file contents audited for secret exposure
- `base_agent.py` (694 lines) — full runtime behavior analysis
- `pipeline.py` (146 lines) — agent orchestration error handling
- `concurrency.py` (94 lines) — semaphore-based limiter patterns
- `main.py` (396 lines) — middleware stack, startup/shutdown lifecycle
- `services/audit/service.py` (562 lines) — existing audit infrastructure
- `services/observability/metrics.py` (78 lines) — Prometheus integration
- `agents/telemetry/__init__.py` (107 lines) — OTel configuration
