# backend/main.py

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Application Modules ---
# Import the new API routers
from api import auth, datasets, chat, dashboard, analysis

# Import core components and services needed for lifecycle events
from core.config import settings
from db.database import connect_to_mongo, close_mongo_connection
from services.ai.ai_service import ai_service

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="DataSage AI API v4.0",
    description="A professionally refactored, modular, AI-powered data visualization and analysis platform.",
    version="4.0.0"
)

# --- Middleware Configuration ---
# Handles Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- Application Lifecycle Events ---
# Defines what happens when the application starts and shuts down

@app.on_event("startup")
async def startup_event():
    """Connects to the database when the application starts."""
    logger.info("Starting up the application...")
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleans up resources when the application shuts down."""
    logger.info("Shutting down the application...")
    # Properly close the httpx client in the LLM router
    from services.llm_router import llm_router
    if llm_router.http and not llm_router.http.is_closed:
        await llm_router.http.aclose()
    # Close the database connection
    await close_mongo_connection()

# --- Core API Routers ---
# Includes the modular endpoint groups into the main application

# Health check for basic service availability
@app.get("/health", tags=["System"])
async def health_check():
    """Provides a simple health check endpoint."""
    return {
        "status": "healthy",
        "version": app.version,
        "message": "DataSage AI API is running."
    }

# Include all the modular routers with their respective prefixes and tags
# This keeps the main file clean and organizes the API documentation
app.include_router(auth.router, prefix="/api/auth", tags=["1. Authentication"])
app.include_router(datasets.router, prefix="/api/datasets", tags=["2. Datasets"])
app.include_router(chat.router, prefix="/api/chat", tags=["3. AI Chat & Conversations"])
# Mount chat router again under /api to support /api/datasets/{id}/chat endpoint
app.include_router(chat.router, prefix="/api", tags=["3. AI Chat & Conversations (Dataset Chat)"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["4. Dashboards & Analytics"])
app.include_router(analysis.router, prefix="/api/ai", tags=["5. Advanced AI & Analysis"])
# Legacy route for frontend compatibility
app.include_router(analysis.router, prefix="/api/analysis", tags=["5. Advanced AI & Analysis (Legacy)"])


# --- Main Execution Block ---
# Allows running the application directly for development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)