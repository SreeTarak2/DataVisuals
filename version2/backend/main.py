import logging
import math
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from core.config import settings
from core.rate_limiter import limiter, rate_limit_exceeded_handler
from db.database import connect_to_mongo, close_mongo_connection
from services.ai.ai_service import ai_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


class CustomJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        sanitized = _sanitize_for_json(content)
        return super().render(sanitized)


app = FastAPI(
    title="DataSage AI API v4.0",
    description="A professionally refactored, modular, AI-powered data visualization and analysis platform.",
    version="4.0.0",
    default_response_class=CustomJSONResponse,
)

app.state.limiter = limiter


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
        "message": "DataSage AI API is running.",
    }


from api.auth import auth_router
from api.datasets import datasets_router
from api.chat import chat_router
from api.dashboard import dashboard_router
from api.charts import charts_router
from api.analysis import analysis_router
from api.insights import insights_router
from api.reports import reports_router
from api.agentic import agentic_router
from api.bookmarks import bookmarks_router
from api.privacy import privacy_router
from api.kpi import router as kpi_router
from api import models

app.include_router(auth_router, prefix="/api/auth", tags=["1. Authentication"])
app.include_router(datasets_router, prefix="/api/datasets", tags=["2. Datasets"])
app.include_router(chat_router, prefix="/api/chat", tags=["3. AI Chat & Conversations"])

app.include_router(
    chat_router, prefix="/api", tags=["3. AI Chat & Conversations (Dataset Chat)"]
)
app.include_router(
    dashboard_router, prefix="/api/dashboard", tags=["4. Dashboards & Analytics"]
)
app.include_router(
    charts_router, prefix="/api/charts", tags=["4.5 Charts & Visualizations (New)"]
)
app.include_router(
    analysis_router, prefix="/api/ai", tags=["5. Advanced AI & Analysis"]
)
app.include_router(insights_router, prefix="/api/insights", tags=["6. Insights"])

app.include_router(reports_router, prefix="/api", tags=["6.5 Reports"])

app.include_router(
    analysis_router, prefix="/api/analysis", tags=["5. Advanced AI & Analysis (Legacy)"]
)
app.include_router(models.router, tags=["6. Model Management"])

app.include_router(agentic_router, prefix="/api", tags=["7. Agentic AI"])

app.include_router(
    bookmarks_router, prefix="/api/bookmarks", tags=["7.5 Saved Bookmarks"]
)

app.include_router(
    privacy_router, prefix="/api/privacy", tags=["8. Privacy & Data Protection"]
)

app.include_router(
    kpi_router, prefix="/api/kpi", tags=["9. Financial KPIs & Metrics"]
)

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
