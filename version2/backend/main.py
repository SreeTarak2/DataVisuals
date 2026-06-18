import logging
import math
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings
from core.rate_limiter import limiter
from db.database import close_mongo_connection, connect_to_mongo

logging.basicConfig(level=logging.INFO)
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
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https: wss:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response


app = FastAPI(
    title="Signal API v4.0",
    description="A professionally refactored, modular, AI-powered data visualization and analysis platform.",
    version="4.0.0",
    default_response_class=CustomJSONResponse,
)

app.state.limiter = limiter

# ── Middleware Stack (order matters: security before CORS is fine here) ──
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

    try:
        from agents.multi.registry import MultiAgentToolRegistry

        MultiAgentToolRegistry.initialize_defaults()
        logger.info("ToolRegistry initialized")
    except Exception as e:
        logger.warning(f"ToolRegistry initialization failed (non-critical): {e}")

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
    from services.llm import llm_router

    if llm_router.http and not llm_router.http.is_closed:
        await llm_router.http.aclose()
    await close_mongo_connection()


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "version": app.version,
        "message": "Signal API is running.",
    }


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
from api.notifications import notification_router
from api.chat import chat_router
from api.dashboard import dashboard_router
from api.databases import databases_router
from api.datasets import datasets_router
from api.datasets import layout_snapshots_router
from api.insights import insights_router
from api.privacy import privacy_router
from api.reports import reports_router

app.include_router(auth_router, prefix="/api/auth", tags=["1. Authentication"])
app.include_router(datasets_router, prefix="/api/datasets", tags=["2. Datasets"])
app.include_router(databases_router, prefix="/api/databases", tags=["2.5 Database Connections"])
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

app.include_router(notification_router, prefix="/api", tags=["7.11 Proactive Notifications"])

app.include_router(layout_snapshots_router, tags=["4. Dashboards & Analytics (Layout Snapshots)"])

app.include_router(privacy_router, prefix="/api/privacy", tags=["8. Privacy & Data Protection"])

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
