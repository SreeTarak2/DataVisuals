"""
Cache Services
==============
Centralized cache services for DataSage AI.

Modules:
- CacheService: General-purpose DataFrame caching (Redis + in-memory LRU)
- DashboardCacheService: Caches dashboard components (KPIs, charts, insights) in MongoDB
- ResponseCache: LLM response caching with semantic similarity matching
- SemanticCache: Query caching with sentence embeddings
- ChartConfigCache: Chart configurations per dataset
- DashboardLayoutCache: Dashboard layouts per user/dataset
"""

from .cache_service import cache_service, CacheService
from .dashboard_cache_service import dashboard_cache_service, DashboardCacheService
from .response_cache import (
    response_cache,
    fallback_generator,
    ResponseCache,
    FallbackResponseGenerator,
)
from .semantic_cache import (
    semantic_cache,
    chart_config_cache,
    dashboard_layout_cache,
    SemanticCache,
    ChartConfigCache,
    DashboardLayoutCache,
)

__all__ = [
    # CacheService
    "cache_service",
    "CacheService",
    # DashboardCacheService
    "dashboard_cache_service",
    "DashboardCacheService",
    # ResponseCache
    "response_cache",
    "fallback_generator",
    "ResponseCache",
    "FallbackResponseGenerator",
    # SemanticCache
    "semantic_cache",
    "chart_config_cache",
    "dashboard_layout_cache",
    "SemanticCache",
    "ChartConfigCache",
    "DashboardLayoutCache",
]
