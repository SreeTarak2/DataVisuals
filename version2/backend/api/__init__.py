from api.auth.routes import router as auth_router
from api.datasets.routes import router as datasets_router
from api.chat.routes import router as chat_router
from api.dashboard.routes import router as dashboard_router
from api.charts.routes import router as charts_router
from api.analysis.routes import router as analysis_router
from api.insights.routes import router as insights_router
from api.reports.routes import router as reports_router
from api.agentic.routes import router as agentic_router
from api.bookmarks.routes import router as bookmarks_router
from api.privacy.routes import router as privacy_router
from api import models

__all__ = [
    "auth_router",
    "datasets_router",
    "chat_router",
    "dashboard_router",
    "charts_router",
    "analysis_router",
    "insights_router",
    "reports_router",
    "agentic_router",
    "bookmarks_router",
    "privacy_router",
    "models",
]
