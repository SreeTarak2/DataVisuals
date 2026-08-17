# Architecture Gaps for Enterprise Readiness

**Domain:** AI-Powered Data Analysis Platform
**Audited:** 2026-07-04

## Current Architecture (Simplified)

```
Request
  |
  v
[FastAPI App] -- SecurityHeadersMiddleware
  |              CSRFProtectionMiddleware
  |              CORSMiddleware
  |
  v
[Router Layer] -- auth, chat, datasets, agentic, etc.
  |               get_current_user() on ~100 routes
  |               limiter.limit() on some routes
  |
  v
[Agent Layer] -- ChatAgent (run/run_streaming)
  |               AnalystAgent, KPICAgent, ChartAgent, ProfileAgent
  |               PipelineOrchestrator (sequential agent runner)
  |               EDA Pipeline (6-stage sequential)
  |
  v
[LLM Layer] -- llm_router.call() with asyncio.wait_for(timeout)
  |             retry_async(attempts=2)
  |             token budget check
  |
  v
[Data Layer] -- MongoDB, FAISS vector store, FalkorDB graph
```

## What's Missing for Enterprise

### Observability Flow (Missing Parts)

```
Current:
  Agent.run() -- OTel span --> BatchSpanProcessor --> OTLP endpoint (if configured)
  Metrics incr() -- in-memory Counter --> (no /metrics endpoint to scrape)

What's needed:
  All logs --> JSON formatter --> stdout --> log shipper (Filebeat/Fluentd) --> ELK
  /metrics endpoint --> Prometheus scrape --> Grafana dashboards
  OTel traces --> Jaeger/Zipkin for agent execution waterfall
  READY probe (/readyz) -- checks MongoDB, LLM, vector DB before returning 200
  LIVE probe (/livez) -- light check that process is responsive
```

### Request Lifecycle (Security Gaps)

```
Current:
  Request --> [Auth middleware on each route] --> [Rate limiter on SOME routes]
                                          |
                                          v
                                    [Agent runs even when concurrency full]
                                    [No total timeout on agent run]

What's needed:
  Request --> [Auth middleware on ALL routes] --> [Rate limiter on ALL agent routes]
                                                    |
                                                    v
                                              [Concurrency: acquire or 429]
                                                    |
                                                    v
                                              [Agent.run() with total timeout]
                                                    |
                                                    v
                                              [Audit log: user, agent, duration, tools, cost]
```

### Agent Execution Architecture

```
Current (base_agent.py run()):
  try:
      observations = await self._run_loop(context)    # no timeout envelope
  finally:
      return_run_budget()
      agent_concurrency_limiter.release()
  # if _run_loop raises, continues to undefined observations -> UnboundLocalError
  try:
      domain_output = await self._process_result(observations, context)
  except:
      ...
  try:
      final_answer = await self._synthesize(query, observations, context)
  except:
      ...
  return {...}

What's needed:
  async def run(self, ...):
      try:
          result = await asyncio.wait_for(self._run_with_timeout(...), 
                                          timeout=settings.AGENT_RUN_TIMEOUT)
      except asyncio.TimeoutError:
          logger.error("Agent run timed out")
          return partial_result_with_error
      except Exception:
          logger.error("Agent run failed", exc_info=True)
          return error_result
      finally:
          return_run_budget()
          agent_concurrency_limiter.release()
```

### Concurrency Architecture

```
Current:
  AgentConcurrencyLimiter
    - Per-agent-type asyncio.Semaphore
    - try_acquire(): returns False if full, agent runs anyway
    - acquire(): blocks forever (no timeout)
    - Limits hardcoded in Python dict
    - No queue, no rejection, no backpressure

What's needed:
  AgentConcurrencyLimiter
    - acquire(timeout=5): blocks up to N seconds, then raises
    - Enforce: reject or queue when full, never silently run without slot
    - Configurable per agent via env vars
    - Optional Redis-backed for multi-process deployments
    - BoundedQueue for pending requests with configurable max size
```

## Component Boundary Gaps

| Component | Current Responsibility | Missing for Enterprise |
|-----------|----------------------|----------------------|
| **main.py** | App creation, middleware registration, startup/shutdown hooks | SIGTERM handler, work draining, /metrics route, /readyz//livez |
| **core/config.py** | Env-based Settings class | Missing: AGENT_RUN_TIMEOUT, PER_AGENT_CONCURRENCY (env-backed), AUDIT_ENABLED, METRICS_ENABLED |
| **base_agent.py** | ReAct loop, tool calling, synthesis | Missing: total timeout envelope, audit logging hook, partial result on crash |
| **concurrency.py** | Per-agent semaphore | Missing: env-based limits, queue, timeout on acquire, active count tracking |
| **pipeline.py** | Agent orchestration with timeout | Missing: env-based AGENT_TIMEOUTS, pipeline-level timeout |
| **audit/service.py** | Chat interaction audit | Missing: agent run audit (new event type needed) |
| **observability/metrics.py** | Prometheus counters/histograms | Missing: registered /metrics endpoint, agent-specific metrics |
| **telemetry/__init__.py** | OTel tracer init | Missing: metrics bridge, required configuration check in production |

## Scalability Considerations

| Concern | Current State | Enterprise Target |
|---------|--------------|-------------------|
| Concurrent agent limit | Hardcoded at 3 per type | Configurable per type, per tenant, with queue |
| Max agent execution time | Unbounded (only LLM calls timed) | 300s total timeout with graceful abort |
| Concurrent requests | No backpressure mechanism | Queue + 429 when queue full |
| Database connections | Single MongoDB connection pool | Connection pooling with configurable max |
| LLM provider failover | Static fallback chain in config | Cost-aware + availability-aware routing |
| Log volume at scale | Plaintext to stdout | JSON to log shipper, log level per module |
| Metrics cardinality | No labels on prometheus metrics | Labels: agent_type, model_role, success/failure |

## Sources

- Direct analysis of main.py (396 lines)
- Direct analysis of base_agent.py (694 lines)
- Direct analysis of concurrency.py (94 lines)
- Direct analysis of pipeline.py (146 lines)
- Direct analysis of config.py (442 lines)
- Direct analysis of audit/service.py (562 lines)
- Direct analysis of observability/metrics.py (78 lines)
- Direct analysis of telemetry/__init__.py (107 lines)
