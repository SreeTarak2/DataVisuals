import os
from typing import List, Dict, Any
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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "50")
    )

    # Database credential encryption key (MUST be separate from SECRET_KEY)
    # Used to encrypt/decrypt stored database connection passwords via Fernet.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    DB_ENCRYPTION_KEY: str = os.getenv("DB_ENCRYPTION_KEY", "")

    LLM_MAX_CONCURRENT_CALLS: int = int(os.getenv("LLM_MAX_CONCURRENT_CALLS", "5"))
    LLM_REQUEST_STAGGER_SECONDS: float = float(
        os.getenv("LLM_REQUEST_STAGGER_SECONDS", "1.5")
    )

    # -------------------------------------------------------------------------
    # LLM Call Timeouts
    # -------------------------------------------------------------------------
    CHAT_LLM_TIMEOUT: int = int(
        os.getenv("CHAT_LLM_TIMEOUT", "120")
    )
    CHAT_STREAM_TIMEOUT: int = int(
        os.getenv("CHAT_STREAM_TIMEOUT", "300")
    )
    UNDERSTAND_QUERY_TIMEOUT: int = int(
        os.getenv("UNDERSTAND_QUERY_TIMEOUT", "30")
    )

    # -------------------------------------------------------------------------
    # OpenRouter Models — Updated March 2026
    # Strategy: Free for chat (openrouter/free), paid Gemini 2.5 Flash Lite for
    # reliability, DeepSeek V3.2 for complex reasoning tasks.
    # -------------------------------------------------------------------------
    OPENROUTER_MODELS: Dict[str, Dict[str, Any]] = {
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

    OPENROUTER_ROLE_MAPPING: Dict[str, str] = {
        # Chat & Conversational — Gemini 2.5 Flash Lite (paid), OpenRouter Free (fallback)
        "chat_engine": "gemini_flash_lite",
        "chat_streaming": "gemini_flash_lite",
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
        # Conversation naming — Mistral Nemo (fast, cheap, generates concise titles)
        "conversation_naming": "mistral_nemo",
        # Default — free
        "default": "openrouter_free",
    }

    FALLBACKS: Dict[str, List[str]] = {
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
    LLM_DAILY_BUDGET_CENTS: int = int(
        os.getenv("LLM_DAILY_BUDGET_CENTS", "500")
    )
    # Global daily budget in cents (default: $100.00)
    LLM_GLOBAL_DAILY_BUDGET_CENTS: int = int(
        os.getenv("LLM_GLOBAL_DAILY_BUDGET_CENTS", "10000")
    )
    # Master toggle for cost tracking
    LLM_COST_TRACKING_ENABLED: bool = (
        os.getenv("LLM_COST_TRACKING_ENABLED", "true").lower() == "true"
    )

    # -------------------------------------------------------------------------
    # Health / Timeouts
    # -------------------------------------------------------------------------
    MODEL_HEALTH_CHECK_TIMEOUT: int = int(
        os.getenv("MODEL_HEALTH_CHECK_TIMEOUT", "180")
    )
    MODEL_FALLBACK_ENABLED: bool = (
        os.getenv("MODEL_FALLBACK_ENABLED", "true").lower() == "true"
    )

    # -------------------------------------------------------------------------
    # Vector Database Configuration
    # -------------------------------------------------------------------------
    VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", "./faiss_db")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
    ENABLE_VECTOR_SEARCH: bool = (
        os.getenv("ENABLE_VECTOR_SEARCH", "true").lower() == "true"
    )

    # -------------------------------------------------------------------------
    # CORS Configuration
    # -------------------------------------------------------------------------
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "").split(",")

    # -------------------------------------------------------------------------
    # File Upload Configuration
    # -------------------------------------------------------------------------
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "524288000"))
    ALLOWED_FILE_TYPES: List[str] = os.getenv(
        "ALLOWED_FILE_TYPES", "csv,xlsx,xls"
    ).split(",")

    # -------------------------------------------------------------------------
    # Google OAuth Configuration
    # -------------------------------------------------------------------------
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv(
        "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback"
    )
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")


settings = Settings()

if settings.USE_OPENROUTER and not settings.OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY must be set in .env for OpenRouter usage")
if not settings.SECRET_KEY:
    raise ValueError(
        "SECRET_KEY must be set in .env (use secrets.token_hex(32) to generate)"
    )
