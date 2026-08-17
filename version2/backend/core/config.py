import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


class Settings:
    USE_OPENROUTER: bool = os.getenv("USE_OPENROUTER", "true").lower() == "true"
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions"
    )

    # MongoDB Configuration
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "signal_ai")

    # JWT Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    # Short-lived access token (JWT). Long-lived sessions use refresh-token
    # rotation: every /auth/refresh mints a new access token + rotates the
    # refresh token, so revocation takes effect within one access-token lifetime.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "50"))
    # Long-lived refresh token (opaque, stored hashed) — lifetime in days.
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    # HttpOnly cookie name for the refresh token (path-scoped to /api/auth)
    REFRESH_COOKIE_NAME: str = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")
    # Path scope for the refresh cookie — only sent to auth endpoints
    REFRESH_COOKIE_PATH: str = os.getenv("REFRESH_COOKIE_PATH", "/api/auth")

    # Database credential encryption key (MUST be separate from SECRET_KEY)
    # Used to encrypt/decrypt stored database connection passwords via Fernet.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    DB_ENCRYPTION_KEY: str = os.getenv("DB_ENCRYPTION_KEY", "")

    LLM_MAX_CONCURRENT_CALLS: int = int(os.getenv("LLM_MAX_CONCURRENT_CALLS", "5"))
    LLM_REQUEST_STAGGER_SECONDS: float = float(os.getenv("LLM_REQUEST_STAGGER_SECONDS", "1.5"))

    # -------------------------------------------------------------------------
    # LLM Call Timeouts
    # -------------------------------------------------------------------------
    CHAT_LLM_TIMEOUT: int = int(os.getenv("CHAT_LLM_TIMEOUT", "120"))
    AGENT_LLM_TIMEOUT: int = int(os.getenv("AGENT_LLM_TIMEOUT", "120"))
    CHAT_STREAM_TIMEOUT: int = int(os.getenv("CHAT_STREAM_TIMEOUT", "300"))
    UNDERSTAND_QUERY_TIMEOUT: int = int(os.getenv("UNDERSTAND_QUERY_TIMEOUT", "30"))

    # -------------------------------------------------------------------------
    # Agent Run Configuration
    # -------------------------------------------------------------------------
    # Max wall-clock seconds for a single agent run (0 = no limit)
    AGENT_RUN_TIMEOUT: int = int(os.getenv("AGENT_RUN_TIMEOUT", "300"))
    # Max concurrent runs per agent type (0 = unlimited)
    AGENT_CONCURRENCY_MAX: int = int(os.getenv("AGENT_CONCURRENCY_MAX", "3"))

    # -------------------------------------------------------------------------
    # OpenRouter Models — Updated March 2026
    # Strategy: Free for chat (openrouter/free), paid Gemini 2.5 Flash Lite for
    # reliability, DeepSeek V3.2 for complex reasoning tasks.
    # -------------------------------------------------------------------------
    OPENROUTER_MODELS: dict[str, dict[str, Any]] = {
        # PAID — Gemini 2.5 Flash Lite ($0.10/$0.40 per M)
        # Cheapest proprietary model. 1M context. Ultra-fast.
        "gemini_flash_lite": {
            "model": "google/gemini-2.5-flash-lite:exacto",
            "name": "Gemini 2.5 Flash Lite",
            "strengths": [
                "instruction_following",
                "structured_output",
                "speed",
                "markdown_formatting",
                "long_context",
            ],
            "best_for": [
                "chat_engine",
                "chat_streaming",
                "conversational",
                "simple_query",
                "rewrite_engine",
            ],
            "context_window": 1048576,
            "cost": "$0.10/$0.40",
            "reasoning_config": {"effort": "medium", "exclude": True},
        },
        # PAID — Mistral Small 3.2 24B ($0.06/$0.18 per M)
        # Cheapest accurate paid model. Reliable for structured JSON, charts.
        "mistral_small_32": {
            "model": "mistralai/mistral-small-3.2-24b-instruct:exacto",
            "name": "Mistral Small 3.2 24B",
            "strengths": [
                "instruction_following",
                "sql",
                "structured_output",
                "function_calling",
            ],
            "best_for": [
                "chart_explanation",
                "validation",
                "draft_generation",
                "simple_query",
            ],
            "context_window": 131000,
            "cost": "$0.06/$0.18",
            "reasoning_config": {"effort": "low", "exclude": True},
        },
        # PAID — DeepSeek V3.2 ($0.25/$0.40 per M)
        # Best for: complex SQL generation, reasoning-heavy tasks.
        # #4 on OpenRouter rankings. Excellent for data analysis.
        # Medium reasoning preserves accuracy while cutting latency 5x.
        "deepseek_v32": {
            "model": "deepseek/deepseek-v3.2:exacto",
            "name": "DeepSeek V3.2",
            "strengths": ["deep_reasoning", "coding", "agentic", "tool_use", "math"],
            "best_for": [
                "sql_generator",
                "complex_analysis",
                "kpi_suggestion",
                "insight_generation",
                "chart_recommendation",
                "system_design",
            ],
            "context_window": 164000,
            "cost": "$0.25/$0.40",
            "reasoning_config": {"effort": "medium", "exclude": True},
        },
        # PAID — DeepSeek V4 Flash ($0.14/$0.28 per M)
        # Best for: JSON constraint following, structured outputs.
        # Significantly better at following strict JSON schemas than V3.2.
        # Fast enough for structured tasks — low reasoning, exclude from streaming.
        "deepseek_v4_flash": {
            "model": "deepseek/deepseek-v4-flash:exacto",
            "name": "DeepSeek V4 Flash",
            "strengths": ["json_following", "structured_output", "coding", "reasoning"],
            "best_for": [
                "chart_recommendation",
                "layout_designer",
                "dashboard_design",
            ],
            "context_window": 164000,
            "cost": "$0.14/$0.28",
            "reasoning_config": {"effort": "low", "exclude": True},
        },
        # PAID — DeepSeek R1T2 Chimera ($0.25/$0.85 per M)
        # Second-gen mixture-of-experts from DeepSeek R1 + V3.
        # Strong reasoning, 20% faster than original R1, good for complex analysis.
        "tngtech_deepseek_r1t2_chimera": {
            "model": "tngtech/deepseek-r1t2-chimera",
            "name": "DeepSeek R1T2 Chimera",
            "strengths": [
                "deep_reasoning",
                "reasoning",
                "complex_analysis",
                "long_context",
            ],
            "best_for": [
                "complex_analysis",
                "narrative_insights",
                "insight_generation",
            ],
            "context_window": 163840,
            "cost": "$0.25/$0.85",
            "reasoning_config": {"effort": "medium", "exclude": True},
        },
        # PAID — MiniMax M2.5 ($0.30/$1.10 per M)
        # #2 on OpenRouter rankings. SOTA coding/agentic, planning.
        # No reasoning needed for structured planning tasks.
        "minimax_m25": {
            "model": "minimax/minimax-m2.5",
            "name": "MiniMax M2.5",
            "strengths": [
                "coding",
                "agentic",
                "excel",
                "data_analysis",
                "office_productivity",
            ],
            "best_for": [
                "layout_designer",
                "dashboard_design",
                "pipeline_planner",
            ],
            "context_window": 196000,
            "cost": "$0.30/$1.10",
            "reasoning_config": {"effort": "low", "exclude": True},
        },
        # PAID — Qwen 2.5 72B Instruct ($0.12/$0.39 per M)
        # Best for: Plain English narration, enterprise reporting, clear explanations.
        # Excellent at transforming technical findings into business-friendly language.
        "qwen_2.5_72b": {
            "model": "qwen/qwen-2.5-72b-instruct:exacto",
            "name": "Qwen 2.5 72B Instruct",
            "strengths": [
                "plain_english",
                "instruction_following",
                "narrative",
                "clarity",
                "enterprise_reporting",
            ],
            "best_for": [
                "narrative_story",
                "plain_english_explanation",
                "enterprise_reporting",
            ],
            "context_window": 131000,
            "cost": "$0.12/$0.39",
            "reasoning_config": {"effort": "low", "exclude": True},
        },
        # PAID — Mistral Nemo 12B ($0.08/$0.08 per M)
        # Cheapest Mistral model. Fast, excellent instruction following, 128K context.
        # Perfect for lightweight tasks like conversation naming.
        "mistral_nemo": {
            "model": "mistralai/mistral-nemo:exacto",
            "name": "Mistral Nemo 12B",
            "strengths": [
                "instruction_following",
                "structured_output",
                "speed",
                "cost_efficiency",
            ],
            "best_for": [
                "conversation_naming",
                "simple_query",
                "classification",
            ],
            "context_window": 128000,
            "cost": "$0.08/$0.08",
            "reasoning_config": {"effort": "low", "exclude": True},
        },
        # FREE — Gemini Flash (context understanding, fast intent detection)
        # Best for: fast query understanding, intent detection, lightweight enrichment
        "gemini_flash_lite_intent": {
            "model": "google/gemini-2.5-flash-lite:exacto",
            "name": "Gemini Flash Intent",
            "strengths": [
                "fast",
                "context_understanding",
                "structured_output",
                "function_calling",
            ],
            "best_for": [
                "intent_engine",
                "query_understanding",
                "fast_classification",
            ],
            "context_window": 1000000,
            "cost": "$0.10/$0.40",
        },
    }

    OPENROUTER_ROLE_MAPPING: dict[str, str] = {
        # Chat & Conversational — Gemini 2.5 Flash Lite (paid), OpenRouter Free (fallback)
        "chat_engine": "gemini_flash_lite",
        "chat_streaming": "qwen_2.5_72b",
        "conversational": "gemini_flash_lite",
        # KPI suggestion — DeepSeek V4 Flash (structured output, fast)
        "kpi_suggestion": "deepseek_v4_flash",
        # Complex analysis — DeepSeek V3.2 (paid, medium reasoning)
        "insight_generation": "deepseek_v32",
        "narrative_insights": "deepseek_v32",
        # Narrative storytelling — Qwen 2.5 72B (plain English)
        "narrative_story": "qwen_2.5_72b",
        "sql_generator": "deepseek_v32",
        # Chart recommendation — DeepSeek V4 Flash (better JSON following, faster)
        "chart_recommendation": "deepseek_v4_flash",
        "complex_analysis": "deepseek_v32",
        # System design & planning — MiniMax M2.5 (#2 on OpenRouter for coding/agentic)
        "system_design": "minimax_m25",
        "pipeline_planner": "minimax_m25",
        # Requirements synthesis — Mistral Small (fast, cheap information gathering)
        "requirements_synthesis": "mistral_small_32",
        "layout_designer": "deepseek_v4_flash",
        "dashboard_design": "deepseek_v4_flash",
        # Chart explanation — Qwen (best for plain English, human-centric)
        "chart_explanation": "qwen_2.5_72b",
        # Simple/cheap tasks — Mistral (paid)
        "visualization_engine": "mistral_small_32",
        "draft_generation": "mistral_small_32",
        "simple_query": "mistral_small_32",
        "rewrite_engine": "mistral_small_32",
        "intent_engine": "gemini_flash_lite_intent",
        "query_understanding": "gemini_flash_lite_intent",
        # Domain enrichment — Mistral Small 3.2 (reliable structured output)
        "enrichment_engine": "mistral_small_32",
        "validation": "mistral_small_32",
        "chart_image_analysis": "mistral_small_32",
        "visual_extraction": "mistral_small_32",
        "layout_from_image": "mistral_small_32",
        # Column cleaning suggestions — Mistral Small 3.2 (cheap, good JSON)
        "column_cleaning_suggestion": "mistral_small_32",
        # LLM-powered column suggestion from user intent — DeepSeek V4 Flash (better JSON)
        "column_suggestion": "deepseek_v4_flash",
        # Conversation naming — Mistral Nemo (fast, cheap, generates concise titles)
        "conversation_naming": "mistral_nemo",
        # Default — free
        "default": "openrouter_free",
    }

    FALLBACKS: dict[str, list[str]] = {
        # Chat — Gemini primary (paid), DeepSeek fallback
        "chat_engine": [
            "gemini_flash_lite",
            "openrouter_free",
            "deepseek_v32",
        ],
        "chat_streaming": [
            "gemini_flash_lite",
            "openrouter_free",
            "mistral_small_32",
            "deepseek_v32",
        ],
        "conversational": [
            "gemini_flash_lite",
            "openrouter_free",
            "deepseek_v32",
        ],
        # Complex analysis — DeepSeek primary, Chimera reasoning backup, Mistral cheap fallback
        "kpi_suggestion": [
            "deepseek_v4_flash",
            "deepseek_v32",
            "mistral_small_32",
        ],
        "insight_generation": [
            "deepseek_v32",
            "tngtech_deepseek_r1t2_chimera",
            "mistral_small_32",
        ],
        "narrative_insights": [
            "deepseek_v32",
            "tngtech_deepseek_r1t2_chimera",
            "mistral_small_32",
        ],
        # Narrative storytelling — Qwen primary, DeepSeek fallback
        "narrative_story": ["qwen_2.5_72b", "deepseek_v32", "mistral_small_32"],
        "sql_generator": ["deepseek_v32", "mistral_small_32"],
        "chart_recommendation": ["deepseek_v4_flash", "deepseek_v32", "mistral_small_32"],
        "complex_analysis": [
            "deepseek_v32",
            "tngtech_deepseek_r1t2_chimera",
            "mistral_small_32",
        ],
        "system_design": ["minimax_m25", "deepseek_v32"],
        "pipeline_planner": ["minimax_m25", "deepseek_v32"],
        "layout_designer": ["deepseek_v4_flash", "deepseek_v32", "minimax_m25"],
        "dashboard_design": ["deepseek_v4_flash", "deepseek_v32", "minimax_m25"],
        "requirements_synthesis": ["mistral_small_32", "deepseek_v32"],
        # Chart explanation — Qwen primary, V4 Flash backup
        "chart_explanation": ["qwen_2.5_72b", "deepseek_v4_flash"],
        "visualization_engine": ["mistral_small_32"],
        "draft_generation": ["mistral_small_32"],
        "simple_query": ["mistral_small_32"],
        "rewrite_engine": ["mistral_small_32"],
        "intent_engine": [
            "gemini_flash_lite_intent",
            "mistral_small_32",
        ],
        "query_understanding": [
            "gemini_flash_lite_intent",
            "mistral_small_32",
        ],
        "enrichment_engine": ["mistral_small_32", "deepseek_v32"],
        "validation": ["mistral_small_32"],
        "chart_image_analysis": ["mistral_small_32", "deepseek_v32"],
        "visual_extraction": ["mistral_small_32", "deepseek_v32"],
        "layout_from_image": ["mistral_small_32", "deepseek_v32"],
        # Column cleaning suggestions - Mistral Small primary, V4 Flash fallback
        "column_cleaning_suggestion": [
            "mistral_small_32",
            "deepseek_v4_flash",
            "deepseek_v32",
        ],
        # Column suggestion from intent - DeepSeek V4 Flash primary, Mistral fallback
        "column_suggestion": [
            "deepseek_v4_flash",
            "mistral_small_32",
            "deepseek_v32",
        ],
        # Conversation naming
        "conversation_naming": ["mistral_nemo", "mistral_small_32"],
        # Default
        "default": [
            "deepseek_v32",
            "mistral_small_32",
        ],
    }

    # -------------------------------------------------------------------------
    # LLM Cost Controls — Budgets & Abuse Prevention
    # -------------------------------------------------------------------------
    # Per-user daily budget in cents (default: $5.00)
    LLM_DAILY_BUDGET_CENTS: int = int(os.getenv("LLM_DAILY_BUDGET_CENTS", "500"))
    # Global daily budget in cents (default: $100.00)
    LLM_GLOBAL_DAILY_BUDGET_CENTS: int = int(os.getenv("LLM_GLOBAL_DAILY_BUDGET_CENTS", "10000"))
    # Master toggle for cost tracking
    LLM_COST_TRACKING_ENABLED: bool = (
        os.getenv("LLM_COST_TRACKING_ENABLED", "true").lower() == "true"
    )

    # ── Column Cleaning (Stage 1.6) Configuration ────────────────────
    # Confidence thresholds for AI cleaning suggestions
    COLUMN_CLEANING_CONFIDENCE_AUTO: float = float(
        os.getenv("COLUMN_CLEANING_CONFIDENCE_AUTO", "0.85")
    )
    COLUMN_CLEANING_CONFIDENCE_SUGGEST: float = float(
        os.getenv("COLUMN_CLEANING_CONFIDENCE_SUGGEST", "0.50")
    )
    # Max AI candidates per batch to control cost
    COLUMN_CLEANING_MAX_CANDIDATES: int = int(
        os.getenv("COLUMN_CLEANING_MAX_CANDIDATES", "50")
    )

    # -------------------------------------------------------------------------
    # Health / Timeouts
    # -------------------------------------------------------------------------
    MODEL_HEALTH_CHECK_TIMEOUT: int = int(os.getenv("MODEL_HEALTH_CHECK_TIMEOUT", "180"))
    MODEL_FALLBACK_ENABLED: bool = os.getenv("MODEL_FALLBACK_ENABLED", "true").lower() == "true"

    # Hard timeout (seconds) for the entire Tier 1 dataset processing pipeline.
    # A pathological CSV will tie up the worker forever without this guard.
    # On timeout, the dataset is marked as "failed" with a clear message.
    # Default: 120 seconds. Tune per-environment via env var.
    #
    # The effective timeout for a given file is
    #   max(PIPELINE_TIMEOUT, min(file_size_mb * PIPELINE_TIMEOUT_PER_MB,
    #                             PIPELINE_TIMEOUT_MAX))
    # so small files keep the fast fail-fast timeout while large files
    # (e.g. 300MB+) get proportional headroom instead of being killed
    # mid-pipeline. See services/pipeline/process.py.
    PIPELINE_TIMEOUT: int = int(os.getenv("PIPELINE_TIMEOUT", "120"))
    # Extra budget: seconds granted per MB of source file.
    PIPELINE_TIMEOUT_PER_MB: int = int(os.getenv("PIPELINE_TIMEOUT_PER_MB", "2"))
    # Ceiling for the scaled timeout (seconds) — a runaway file still dies.
    PIPELINE_TIMEOUT_MAX: int = int(os.getenv("PIPELINE_TIMEOUT_MAX", "1800"))

    # On startup, re-queue datasets whose background pipeline was killed by a
    # server restart/reload (they sit stuck mid-stage with no task running).
    # Set to false in multi-worker deployments that manage their own queue.
    PIPELINE_RECOVER_STUCK_ON_STARTUP: bool = (
        os.getenv("PIPELINE_RECOVER_STUCK_ON_STARTUP", "true").lower() == "true"
    )

    # Maximum allowed file size (in MB) for pipeline processing.
    # Files larger than this are rejected at pipeline entry with a clear
    # error before any memory is allocated.  This prevents OOM from
    # pathological CSVs that balloon in memory when parsed by Polars.
    # Note: MAX_FILE_SIZE governs raw upload acceptance; this is the
    # absolute server-side memory-safety ceiling. The *effective* limit
    # for a user is min(tier limit, this ceiling) — see
    # ``services/datasets/size_limits.py``.
    # Default: 1024 MB. Tune per-environment via env var.
    PIPELINE_MAX_FILE_SIZE_MB: int = int(os.getenv("PIPELINE_MAX_FILE_SIZE_MB", "1024"))

    # -------------------------------------------------------------------------
    # Pricing-tier file size limits (MB)
    # -------------------------------------------------------------------------
    # Product limits per billing tier (Free / Pro / Enterprise). The user's
    # tier is read from their user document (subscription / plan / tier
    # fields, defaulting to "free"). The effective limit for any user is
    # min(tier limit, PIPELINE_MAX_FILE_SIZE_MB) so the pipeline memory
    # ceiling always wins. Tune per-environment via env vars.
    TIER_FILE_SIZE_LIMITS_MB: dict[str, int] = {
        "free": int(os.getenv("TIER_LIMIT_FREE_MB", "200")),
        "pro": int(os.getenv("TIER_LIMIT_PRO_MB", "500")),
        "enterprise": int(os.getenv("TIER_LIMIT_ENTERPRISE_MB", "1024")),
    }

    # -------------------------------------------------------------------------
    # Vector Database Configuration
    # -------------------------------------------------------------------------
    VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", "./faiss_db")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
    ENABLE_VECTOR_SEARCH: bool = os.getenv("ENABLE_VECTOR_SEARCH", "true").lower() == "true"
    # Max per-dataset chunk FAISS indices to keep in memory (LRU eviction)
    CHUNK_INDEX_CACHE_MAX: int = int(os.getenv("CHUNK_INDEX_CACHE_MAX", "100"))

    # -------------------------------------------------------------------------
    # -------------------------------------------------------------------------
    # Cookie Configuration (HttpOnly JWT cookie, Phase 1)
    # -------------------------------------------------------------------------
    COOKIE_DOMAIN: str = os.getenv("COOKIE_DOMAIN", "")

    # Secure flag: auto-disabled for localhost so dev works without HTTPS
    @property
    def COOKIE_SECURE(self) -> bool:
        is_local = any(
            "localhost" in origin or "127.0.0.1" in origin for origin in self.ALLOWED_ORIGINS
        )
        return not is_local

    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax")
    # Cookie path — restrict to API prefix. Root is safe for most SPAs.
    COOKIE_PATH: str = os.getenv("COOKIE_PATH", "/")
    # Master toggle for CSRF protection. Default OFF until Phase 2 frontend is deployed
    # (which adds X-CSRF-Protection: 1 header to all state-changing requests).
    CSRF_ENABLED: bool = os.getenv("CSRF_ENABLED", "false").lower() == "true"

    # -------------------------------------------------------------------------
    # CORS Configuration
    # -------------------------------------------------------------------------
    ALLOWED_ORIGINS: list[str] = os.getenv("ALLOWED_ORIGINS", "").split(",")

    # -------------------------------------------------------------------------
    # File Upload Configuration
    # -------------------------------------------------------------------------
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "524288000"))
    ALLOWED_FILE_TYPES: list[str] = os.getenv("ALLOWED_FILE_TYPES", "csv,xlsx,xls").split(",")

    # -------------------------------------------------------------------------
    # Google OAuth Configuration
    # -------------------------------------------------------------------------
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv(
        "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback"
    )
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # -------------------------------------------------------------------------
    # BYOK Configuration — Bring Your Own Key
    # -------------------------------------------------------------------------
    # Master toggle for BYOK (user-provided API keys)
    BYOK_ENABLED: bool = os.getenv("BYOK_ENABLED", "false").lower() == "true"

    # Curated model lists per provider (used to filter API-discovered models)
    BYOK_PROVIDER_MODELS: dict[str, list[str]] = {
        "openai": ["gpt-4o", "gpt-4o-mini", "o3-mini", "o4-mini"],
        "anthropic": ["claude-sonnet-4", "claude-haiku-3.5", "claude-opus-5", "claude-fable-5"],
        "deepseek": ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash", "deepseek-v4-pro"],
        "google": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
    }

    # -------------------------------------------------------------------------
    # S3 / Object Storage Configuration
    # -------------------------------------------------------------------------
    SUPABASE_S3_URL: str = os.getenv("SUPABASE_S3_URL", "")
    SUPABASE_BUCKET_NAME: str = os.getenv("SUPABASE_BUCKET_NAME", "datasage-datasets")
    SUPABASE_S3_ACCESS_KEY: str = os.getenv("SUPABASE_S3_ACCESS_KEY", "")
    SUPABASE_S3_SECRET_KEY: str = os.getenv("SUPABASE_S3_SECRET_KEY", "")
    SUPABASE_S3_REGION: str = os.getenv("SUPABASE_S3_REGION", "auto")
    # When true, agents read parquet from S3 lazily instead of local disk eagerly
    S3_ENABLED: bool = os.getenv("S3_ENABLED", "false").lower() == "true"
    # Max rows for agent context sampling (prevents full-dataset loads)
    AGENT_MAX_CONTEXT_ROWS: int = int(os.getenv("AGENT_MAX_CONTEXT_ROWS", "200"))
    # Max columns for agent context (prevents wide-table loads)
    AGENT_MAX_CONTEXT_COLS: int = int(os.getenv("AGENT_MAX_CONTEXT_COLS", "30"))

    # -------------------------------------------------------------------------
    # Colab Model Configuration — Cloud GPU for local inference
    # -------------------------------------------------------------------------
    # URL of a Colab-hosted Ollama instance exposed via ngrok (or similar tunnel).
    # When set, SQL generation is routed through this model instead of OpenRouter,
    # making it free and faster. Falls back to OpenRouter if the tunnel is down.
    COLAB_OLLAMA_URL: str = os.getenv("COLAB_OLLAMA_URL", "")
    # Model name inside the Colab Ollama instance
    COLAB_SQL_MODEL: str = os.getenv("COLAB_SQL_MODEL", "a-kore/Arctic-Text2SQL-R1-7B")

    # -------------------------------------------------------------------------
    # Approximate Query Processing (AQP) Configuration
    # -------------------------------------------------------------------------
    # When True, users can toggle "approximate mode" for faster results on
    # billion-row datasets using DuckDB's native APPROX_COUNT_DISTINCT, etc.
    AQP_ENABLED: bool = os.getenv("AQP_ENABLED", "true").lower() == "true"
    # Default mode: "exact" | "approximate"
    AQP_DEFAULT_MODE: str = os.getenv("AQP_DEFAULT_MODE", "exact")

    # -------------------------------------------------------------------------
    # Async Query Execution Configuration
    # -------------------------------------------------------------------------
    # Max wall-clock seconds for a single DuckDB query (asyncio.wait_for timeout)
    QUERY_TIMEOUT: int = int(os.getenv("QUERY_TIMEOUT", "120"))
    # Max concurrent DuckDB connections (thread pool workers)
    QUERY_MAX_WORKERS: int = int(os.getenv("QUERY_MAX_WORKERS", "4"))
    # Max queued queries waiting for a slot
    QUERY_MAX_QUEUE: int = int(os.getenv("QUERY_MAX_QUEUE", "20"))
    # Per-connection DuckDB memory limit
    QUERY_MEMORY_LIMIT: str = os.getenv("QUERY_MEMORY_LIMIT", "2GB")
    # Hours before query results are auto-deleted by MongoDB TTL index
    QUERY_RESULT_TTL_HOURS: int = int(os.getenv("QUERY_RESULT_TTL_HOURS", "24"))
    # Max rows before query execution warns the user (default: 10,000)
    # If a COUNT(*) estimate exceeds this threshold, the query is not executed
    # and a warning is returned instead. Set to 0 to disable the pre-check.
    MAX_ROWS_WARNING_THRESHOLD: int = int(os.getenv("MAX_ROWS_WARNING_THRESHOLD", "10000"))
    # DiskCache directory for SQL query result caching (persists across restarts)
    QUERY_CACHE_DIR: str = os.getenv("QUERY_CACHE_DIR", "./data/query_cache")
    # Seconds before a cached query result expires (default: 5 minutes)
    # Set to 0 to disable caching
    QUERY_CACHE_TTL: int = int(os.getenv("QUERY_CACHE_TTL", "300"))

    # -------------------------------------------------------------------------
    # DuckDB Connection Configuration (for direct file reads / in-memory queries)
    # -------------------------------------------------------------------------
    # Per-connection memory limit. DuckDB spills to disk when this is exceeded.
    # For production, set this to a fraction of total RAM divided by expected
    # concurrent queries (e.g., 32GB RAM / 8 concurrent = 4GB per connection).
    DUCKDB_MEMORY_LIMIT: str = os.getenv("DUCKDB_MEMORY_LIMIT", "2GB")
    # Threads per DuckDB connection. Limits CPU contention between concurrent
    # queries. Set to 2-4 for a web app backend to prevent thread starvation.
    DUCKDB_THREADS: int = int(os.getenv("DUCKDB_THREADS", "4"))
    # Temp directory for DuckDB disk spillover (when queries exceed memory_limit).
    # Use a fast SSD-backed path. DuckDB creates the directory if it doesn't exist.
    DUCKDB_TEMP_DIRECTORY: str = os.getenv("DUCKDB_TEMP_DIRECTORY", "/tmp/duckdb_temp")

    # Role-to-model mapping for BYOK auto-pick (per provider)
    # Maps each task role to the best model from a user's available set.
    BYOK_ROLE_MODEL_MAPPING: dict[str, dict[str, list[str]]] = {
        # Priority-ordered: system tries first match from user's selected models
        "chat": {
            "priority": [
                "gpt-4o-mini",
                "claude-haiku-3.5",
                "gemini-2.5-flash-lite",
                "deepseek-chat",
            ],
            "fallback": ["gpt-4o", "claude-sonnet-4", "gemini-2.5-flash", "deepseek-v4-flash"],
        },
        "analysis": {
            "priority": ["o3-mini", "deepseek-reasoner", "claude-sonnet-4", "gemini-2.5-pro"],
            "fallback": ["gpt-4o", "deepseek-v4-pro", "claude-opus-5", "gemini-2.5-flash"],
        },
        "narrative": {
            "priority": ["gpt-4o", "claude-sonnet-4", "gemini-2.5-flash", "deepseek-v4-flash"],
            "fallback": [
                "gpt-4o-mini",
                "claude-haiku-3.5",
                "gemini-2.5-flash-lite",
                "deepseek-chat",
            ],
        },
        "structured": {
            "priority": [
                "gpt-4o-mini",
                "deepseek-v4-flash",
                "claude-haiku-3.5",
                "gemini-2.5-flash-lite",
            ],
            "fallback": ["gpt-4o", "deepseek-chat", "claude-sonnet-4", "gemini-2.5-flash"],
        },
        "simple": {
            "priority": [
                "gpt-4o-mini",
                "claude-haiku-3.5",
                "gemini-2.5-flash-lite",
                "deepseek-chat",
            ],
            "fallback": ["gpt-4o", "claude-sonnet-4", "gemini-2.5-flash", "deepseek-v4-flash"],
        },
    }


settings = Settings()

if settings.USE_OPENROUTER and not settings.OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY must be set in .env for OpenRouter usage")
if not settings.SECRET_KEY:
    raise ValueError("SECRET_KEY must be set in .env (use secrets.token_hex(32) to generate)")
