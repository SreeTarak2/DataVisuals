import logging
import math
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from core.auth import CSRFProtectionMiddleware
from core.config import settings
from core.rate_limiter import limiter
from db.database import close_mongo_connection, connect_to_mongo


class _CorrelationFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, "correlation_id"):
            record.correlation_id = ""
        return super().format(record)


_handler = logging.StreamHandler()
_handler.setFormatter(
    _CorrelationFormatter("%(asctime)s [%(levelname)s] %(name)s [%(correlation_id)s] %(message)s")
)
logging.basicConfig(level=logging.INFO, handlers=[_handler])
try:
    from agents.resilience.correlation import CorrelationFilter

    logging.getLogger().addFilter(CorrelationFilter())
except Exception:
    pass

logger = logging.getLogger(__name__)


def _sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


class CustomJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        sanitized = _sanitize_for_json(content)
        return super().render(sanitized)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to all responses.

    CSP: Restricts script/style sources to prevent XSS.
    HSTS: Enforces HTTPS connections in production.
    X-Frame-Options: Prevents clickjacking.
    X-Content-Type-Options: Prevents MIME type sniffing.
    Referrer-Policy: Controls referrer header leakage.
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), interest-cohort=()"
        )
        # HSTS only in production (non-localhost origins)
        is_local = any(
            "localhost" in origin or "127.0.0.1" in origin for origin in settings.ALLOWED_ORIGINS
        )
        if not is_local:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        # ------------------------------------------------------------------
        # Content-Security-Policy
        # ------------------------------------------------------------------
        # Rationale for allowances that look permissive:
        #
        # script-src 'unsafe-inline'
        #   Required by Vite dev-mode HMR which injects inline <script> tags.
        #   In production (Vite build), JS is bundled into external files
        #   and this directive is unused — but keeping it avoids a hard
        #   dependency on build-time nonce generation. Ref: strict-dynamic.
        #
        # script-src 'unsafe-eval'
        #   REQUIRED by Plotly.js which uses new Function() internally for
        #   expression evaluation in chart rendering. Cannot be removed
        #   while Plotly is in use. This is a known limitation documented
        #   in the Plotly security advisory.
        #
        # style-src 'unsafe-inline'
        #   Required by dynamically-injected CSS (e.g. CSS modules, some
        #   React component libraries, react-syntax-highlighter). React
        #   inline styles (style={{}}) are DOM properties and are NOT
        #   affected by this CSP directive.
        #
        # strict-dynamic
        #   Modern-browser fallback: once a trusted script loads, any
        #   scripts it creates dynamically are also trusted. This means
        #   inline event handlers won't fire unless created by a trusted
        #   script. In strict-dynamic mode, 'unsafe-inline' is ignored
        #   by supporting browsers, giving defense-in-depth.
        #
        # report-uri
        #   Sends violation reports to the backend's /csp-violation
        #   endpoint (in development, logged to server console).
        #   Set CSP_REPORT_URI env var to a real endpoint in production.
        # ------------------------------------------------------------------
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' 'strict-dynamic'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob: https:",
            "font-src 'self' data:",
            "connect-src 'self' https: wss:",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        report_uri = os.getenv("CSP_REPORT_URI", "")
        if report_uri:
            csp_directives.append(f"report-uri {report_uri}")
            csp_directives.append(f"report-to {report_uri}")

        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        return response


app = FastAPI(
    title="Signal API v4.0",
    description="A professionally refactored, modular, AI-powered data visualization and analysis platform.",
    version="4.0.0",
    default_response_class=CustomJSONResponse,
)

app.state.limiter = limiter

# ── Middleware Stack (order matters) ──
# CSRF must be outermost so it runs before all other middleware on state-changing requests.
app.add_middleware(CSRFProtectionMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    logger.info("Starting up the application...")
    await connect_to_mongo()

    # Initialize cost tracker with configured budgets
    try:
        from llm.cost_tracker import cost_tracker

        cost_tracker.configure(
            daily_budget_cents=settings.LLM_DAILY_BUDGET_CENTS,
            global_daily_budget_cents=settings.LLM_GLOBAL_DAILY_BUDGET_CENTS,
            enabled=settings.LLM_COST_TRACKING_ENABLED,
        )
        logger.info("✓ Cost tracker initialized")
    except Exception as e:
        logger.warning(f"Cost tracker initialization failed (non-critical): {e}")

    from services.feedback.context_store import context_store

    await context_store.init_indexes()
    logger.info("Context store initialized")

    # Recover datasets whose background pipeline died with a previous process
    # (server restart / dev reload while processing). Without this, a dataset
    # stuck mid-stage shows "Analyzing Dataset" forever and blocks re-uploads.
    try:
        if settings.PIPELINE_RECOVER_STUCK_ON_STARTUP:
            from services.pipeline.recovery import recover_stuck_datasets

            summary = await recover_stuck_datasets()
            logger.info(
                "✓ Pipeline recovery: %d re-queued, %d failed (missing file)",
                len(summary["requeued"]),
                len(summary["failed_missing_file"]),
            )
        else:
            logger.info("Pipeline recovery disabled (PIPELINE_RECOVER_STUCK_ON_STARTUP=false)")
    except Exception as e:
        logger.warning(f"Pipeline recovery failed (non-critical): {e}")

    # Initialize learning system indexes
    try:
        from services.learning.signal_collector import signal_collector

        await signal_collector.init_indexes()
        logger.info("Learning system indexes initialized")
    except Exception as e:
        logger.warning(f"Learning system index initialization failed (non-critical): {e}")

    # Initialize token budgeting system
    try:
        from prompts.measure_templates import init_token_budgets

        init_token_budgets()
        logger.info("Token budgets initialized")
    except Exception as e:
        logger.warning(f"Token budget initialization failed (non-critical): {e}")

    # Preload embedding model at startup to avoid cold-start delay (Issue #8)
    try:
        from agents.belief.belief_store import get_belief_store

        belief_store = get_belief_store()
        if belief_store and belief_store.embedding_model:
            logger.info(
                f"✓ Embedding model preloaded at startup: {belief_store.embedding_model_name}"
            )
        else:
            logger.warning("Embedding model preload skipped (not available or disabled)")
    except Exception as e:
        logger.warning(f"Embedding model preload failed (non-critical): {e}")

    # Start scheduled belief decay background task
    # Decays old ChromaDB beliefs every 6 hours so stale knowledge
    # doesn't permanently suppress novelty detection.
    # start_belief_decay_task() already creates an asyncio.Task internally
    # — don't wrap in another create_task() to avoid dead overhead.
    try:
        from services.maintenance.belief_decay_task import start_belief_decay_task

        _belief_decay_task = await start_belief_decay_task()  # fire-and-forget
        logger.info("✓ Scheduled belief decay task started (every 6h)")
    except Exception as e:
        logger.warning(f"Belief decay task initialization failed (non-critical): {e}")

    try:
        from agents.multi.registry import MultiAgentToolRegistry

        MultiAgentToolRegistry.initialize_defaults()
        logger.info("ToolRegistry initialized")
    except Exception as e:
        logger.warning(f"ToolRegistry initialization failed (non-critical): {e}")

    # OpenTelemetry initialization
    try:
        from agents.telemetry import init_telemetry

        init_telemetry()
        logger.info("OpenTelemetry tracer initialized")
    except Exception as e:
        logger.warning(f"OpenTelemetry init failed (non-critical): {e}")

    # Circuit breaker registration
    try:
        from services.retries.async_utils import BreakerRegistry, CircuitBreaker

        BreakerRegistry.register("tool:sql", CircuitBreaker(fail_threshold=3, reset_timeout=60))
        BreakerRegistry.register(
            "tool:profiler", CircuitBreaker(fail_threshold=5, reset_timeout=30)
        )
        BreakerRegistry.register("tool:rag", CircuitBreaker(fail_threshold=5, reset_timeout=30))
        BreakerRegistry.register("tool:memory", CircuitBreaker(fail_threshold=5, reset_timeout=30))
        BreakerRegistry.register(
            "tool:classifier", CircuitBreaker(fail_threshold=5, reset_timeout=30)
        )
        logger.info("BreakerRegistry: %d breakers registered", len(BreakerRegistry.available()))
    except Exception as e:
        logger.warning(f"BreakerRegistry init failed (non-critical): {e}")

    # Register agents with the AgentRegistry
    try:
        from agents import AgentRegistry
        from agents.chat.chat_agent import ChatAgent
        from agents.multi.analyst_agent import AnalystAgent
        from agents.multi.kpi_agent import KPICAgent
        from agents.multi.chart_agent import ChartAgent
        from agents.multi.profile_agent import ProfileAgent
        from agents.eda.orchestrator import run_eda_pipeline

        AgentRegistry.register("chat", ChatAgent)
        AgentRegistry.register("analyst", AnalystAgent)
        AgentRegistry.register("kpi", KPICAgent)
        AgentRegistry.register("chart", ChartAgent)
        AgentRegistry.register("profile", ProfileAgent)
        AgentRegistry.register_fn("eda", run_eda_pipeline)

        logger.info(
            "✓ AgentRegistry: %d agents registered",
            len(AgentRegistry.available()),
        )
    except Exception as e:
        logger.warning(f"AgentRegistry initialization failed (non-critical): {e}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down the application...")
    from llm import llm_router

    if llm_router.http and not llm_router.http.is_closed:
        await llm_router.http.aclose()
    await close_mongo_connection()


@app.get("/health", tags=["System"])
async def health_check():
    """
    Enterprise health check endpoint.

    Checks:
    - MongoDB connectivity (ping)
    - LLM router availability (Healthy/Bypassed/Degraded)
    - Colab/Arctic reachability (when configured)
    - Circuit breaker status
    - Overall status: healthy / degraded / unhealthy

    Returns diagnostic detail so operators can identify issues
    without digging through logs.
    """
    checks = {}
    all_healthy = True

    # ── MongoDB sanity check ──
    try:
        from db.database import db as db_instance

        if db_instance.client:
            await db_instance.client.admin.command("ping")
            checks["mongodb"] = {"status": "healthy", "database": db_instance.database.name}
        else:
            checks["mongodb"] = {"status": "degraded", "detail": "Not initialized yet"}
            all_healthy = False
    except Exception as e:
        checks["mongodb"] = {"status": "unhealthy", "detail": str(e)}
        all_healthy = False

    # ── LLM Router check ──
    try:
        from llm.router import llm_router

        if llm_router:
            checks["llm_router"] = {"status": "healthy"}
        else:
            checks["llm_router"] = {"status": "bypassed", "detail": "Not configured"}
    except Exception as e:
        checks["llm_router"] = {"status": "degraded", "detail": str(e)}
        all_healthy = False

    # ── Colab / Arctic check (only when configured) ──
    if settings.COLAB_OLLAMA_URL:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.COLAB_OLLAMA_URL}/api/tags")
                if resp.status_code == 200:
                    checks["colab_arctic"] = {
                        "status": "healthy",
                        "model": settings.COLAB_SQL_MODEL,
                        "url": settings.COLAB_OLLAMA_URL[:40],
                    }
                else:
                    checks["colab_arctic"] = {
                        "status": "degraded",
                        "detail": f"HTTP {resp.status_code}",
                    }
                    all_healthy = False
        except Exception as e:
            checks["colab_arctic"] = {"status": "unreachable", "detail": str(e)}
            all_healthy = False
    else:
        checks["colab_arctic"] = {"status": "not_configured"}

    # ── Circuit breakers ──
    try:
        from services.retries.async_utils import BreakerRegistry

        breakers = BreakerRegistry.status()
        open_breakers = [k for k, v in breakers.items() if v != "closed"]
        checks["circuit_breakers"] = {
            "status": "healthy" if not open_breakers else "degraded",
            "open": open_breakers,
            "all": breakers,
        }
        if open_breakers:
            all_healthy = False
    except Exception:
        checks["circuit_breakers"] = {"status": "not_initialized"}

    overall = "healthy" if all_healthy else "degraded"
    return {
        "status": overall,
        "version": app.version,
        "message": "Signal API is running.",
        "checks": checks,
    }


@app.get("/health/agents", tags=["System"])
async def health_agents():
    try:
        from agents import AgentRegistry
        from services.retries.async_utils import BreakerRegistry

        breakers = BreakerRegistry.status()
        agents = AgentRegistry.available()
        all_closed = all(s == "closed" for s in breakers.values())
        return {
            "status": "healthy" if all_closed else "degraded",
            "breakers": breakers,
            "agents": agents,
        }
    except Exception as e:
        logger.error("Health/agents check failed: %s", e)
        return {"status": "error", "detail": str(e)}


from api import models
from api.agentic import agentic_router
from api.ai import ai_router
from api.analysis import analysis_router
from api.auth import auth_router
from api.beliefs import belief_router
from api.bookmarks import bookmarks_router
from api.charts import charts_router
from api.anomalies import anomaly_router
from api.reflection import reflection_router
from api.feedback import feedback_router
from api.notifications import notification_router
from api.chat import chat_router
from api.dashboard import dashboard_router
from api.databases import databases_router
from api.datasets import datasets_router
from api.datasets import layout_snapshots_router
from api.insights import insights_router
from api.preferences import preferences_router
from api.api_keys.routes import router as api_keys_router
from api.privacy import privacy_router
from api.reports import reports_router
from api.workspace import workspace_router
from api.projects import projects_router
from api.semantic import semantic_router
from api.predictive_questions import predictive_questions_router
from api.assumptions import assumptions_router
from api.v2.query_routes import router as query_v2_router
from api.dlt.routes import router as dlt_router

app.include_router(auth_router, prefix="/api/auth", tags=["1. Authentication"])
app.include_router(datasets_router, prefix="/api/datasets", tags=["2. Datasets"])
app.include_router(databases_router, prefix="/api/databases", tags=["2.5 Database Connections"])
app.include_router(dlt_router, tags=["2.7 dlt Data Connectors"])
app.include_router(chat_router, prefix="/api/chat", tags=["3. AI Chat & Conversations"])

app.include_router(chat_router, prefix="/api", tags=["3. AI Chat & Conversations (Dataset Chat)"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["4. Dashboards & Analytics"])
app.include_router(charts_router, prefix="/api/charts", tags=["4.5 Charts & Visualizations (New)"])
app.include_router(analysis_router, prefix="/api/ai", tags=["5. Advanced AI & Analysis"])
app.include_router(ai_router, prefix="/api/ai", tags=["5.5 AI Dashboard Design"])
app.include_router(insights_router, prefix="/api/insights", tags=["6. Insights"])

app.include_router(reports_router, prefix="/api", tags=["6.5 Reports"])

app.include_router(
    analysis_router, prefix="/api/analysis", tags=["5. Advanced AI & Analysis (Legacy)"]
)
app.include_router(models.router, tags=["6. Model Management"])

app.include_router(agentic_router, prefix="/api", tags=["7. Agentic AI"])

app.include_router(bookmarks_router, prefix="/api/bookmarks", tags=["7.5 Saved Bookmarks"])

app.include_router(belief_router, prefix="/api/beliefs", tags=["7.6 Business Rules & Beliefs"])

app.include_router(anomaly_router, prefix="/api", tags=["7.9 Anomaly Investigation"])

app.include_router(reflection_router, prefix="/api", tags=["7.10 Insight Reflection & Quality"])

app.include_router(
    feedback_router, prefix="/api/feedback", tags=["7.11 Feedback & Correction Semantics"]
)

app.include_router(notification_router, prefix="/api", tags=["7.12 Proactive Notifications"])

app.include_router(layout_snapshots_router, tags=["4. Dashboards & Analytics (Layout Snapshots)"])

app.include_router(workspace_router, prefix="/api/workspaces", tags=["1.5 Workspaces & Tenancy"])

app.include_router(projects_router, prefix="/api/projects", tags=["1.6 Project Workspace (Analysis Containers)"])

app.include_router(preferences_router, prefix="/api/preferences", tags=["7.12 Learned Preferences"])

app.include_router(api_keys_router, tags=["8. BYOK API Keys"])

app.include_router(privacy_router, prefix="/api/privacy", tags=["8. Privacy & Data Protection"])

app.include_router(semantic_router, prefix="/api/v2", tags=["9. Semantic Layer (Governed Metrics)"])

# Predictive Questions — auto-generated business questions from dataset intelligence
app.include_router(predictive_questions_router, prefix="/api", tags=["9.5 Predictive Questions"])

# Ontology Assumptions — Act-then-Validate state machine (hierarchies/relationships)
app.include_router(assumptions_router, tags=["9.6 Ontology Assumptions"])

# Async Query Execution
app.include_router(
    query_v2_router, prefix="/api/v2", tags=["9.5 Async Query Execution (SQL Editor)"]
)

# Graph-RAG Integration (Phase 3)
from services.knowledge_graph import graph_rag_router

app.include_router(graph_rag_router)

# Entity Extraction API (Phase 4)
from services.knowledge_graph import entity_extraction_router

app.include_router(entity_extraction_router)


_chat_images_dir = Path(__file__).resolve().parent / "data" / "uploads" / "chat_images"
_chat_images_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/static/chat-images",
    StaticFiles(directory=str(_chat_images_dir)),
    name="chat-images",
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
