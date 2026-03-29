# backend/main.py

import logging
import math
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from core.config import settings
from api import (
    auth,
    datasets,
    chat,
    dashboard,
    analysis,
    models,
    charts,
    agentic,
    insights,
    reports,
    privacy,
    bookmarks,
)
from core.rate_limiter import limiter, rate_limit_exceeded_handler
from db.database import connect_to_mongo, close_mongo_connection
from services.ai.ai_service import ai_service

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Custom JSON Encoder for handling NaN/Inf values ---
def _sanitize_for_json(obj):
    """Recursively sanitize objects, converting NaN/Inf to None."""
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


# --- FastAPI App Initialization ---
app = FastAPI(
    title="DataSage AI API v4.0",
    description="A professionally refactored, modular, AI-powered data visualization and analysis platform.",
    version="4.0.0",
    default_response_class=CustomJSONResponse,
)

# --- Rate Limiter Configuration ---
# Attach limiter to app state for access in routes
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# --- Middleware Configuration ---
# Handles Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],    
)


@app.on_event("startup")
async def startup_event():
    """Connects to the database when the application starts."""
    logger.info("Starting up the application...")
    await connect_to_mongo()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleans up resources when the application shuts down."""
    logger.info("Shutting down the application...")
    from services.llm_router import llm_router

    if llm_router.http and not llm_router.http.is_closed:
        await llm_router.http.aclose()
    await close_mongo_connection()


# Health check for basic service availability
@app.get("/health", tags=["System"])
async def health_check():
    """Provides a simple health check endpoint."""
    return {
        "status": "healthy",
        "version": app.version,
        "message": "DataSage AI API is running.",
    }


app.include_router(auth.router, prefix="/api/auth", tags=["1. Authentication"])
app.include_router(datasets.router, prefix="/api/datasets", tags=["2. Datasets"])
app.include_router(chat.router, prefix="/api/chat", tags=["3. AI Chat & Conversations"])

app.include_router(
    chat.router, prefix="/api", tags=["3. AI Chat & Conversations (Dataset Chat)"]
)
app.include_router(
    dashboard.router, prefix="/api/dashboard", tags=["4. Dashboards & Analytics"]
)
app.include_router(
    charts.router, prefix="/api/charts", tags=["4.5 Charts & Visualizations (New)"]
)
app.include_router(
    analysis.router, prefix="/api/ai", tags=["5. Advanced AI & Analysis"]
)
app.include_router(insights.router, prefix="/api/insights", tags=["6. Insights"])

# Professional PDF Report Generation
app.include_router(reports.router, prefix="/api", tags=["6.5 Reports"])

app.include_router(
    analysis.router, prefix="/api/analysis", tags=["5. Advanced AI & Analysis (Legacy)"]
)
# Model management and testing
app.include_router(models.router, tags=["6. Model Management"])

# Agentic QUIS (LangGraph-based analysis with subjective novelty)
app.include_router(agentic.router, prefix="/api", tags=["7. Agentic AI"])

# Saved Analysis and Bookmarks
app.include_router(
    bookmarks.router, prefix="/api/bookmarks", tags=["7.5 Saved Bookmarks"]
)

# Privacy & Data Protection
app.include_router(
    privacy.router, prefix="/api/privacy", tags=["8. Privacy & Data Protection"]
)

# --- Static File Serving (chat image uploads) ---
_chat_images_dir = Path(__file__).resolve().parent / "uploads" / "chat_images"
_chat_images_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/static/chat-images",
    StaticFiles(directory=str(_chat_images_dir)),
    name="chat-images",
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
