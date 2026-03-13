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
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "datasage_ai")

    # JWT Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "50"))


    LLM_MAX_CONCURRENT_CALLS: int = int(os.getenv("LLM_MAX_CONCURRENT_CALLS", "5"))
    LLM_REQUEST_STAGGER_SECONDS: float = float(os.getenv("LLM_REQUEST_STAGGER_SECONDS", "0.5"))

    # -------------------------------------------------------------------------
    # OpenRouter Models — Updated March 2026
    # Strategy: Gemini primary, Mistral fallback, Qwen3 VL for vision
    # -------------------------------------------------------------------------
    OPENROUTER_MODELS: Dict[str, Dict[str, Any]] = {

        # ═══════════════════════════════════════════════════════════════════
        # PRIMARY — Gemini 2.5 Flash Lite ($0.075/$0.30 per M)
        # Best response formatting + speed. Natively writes structured
        # markdown, tables, bold numbers. 1M context. Use for ALL
        # user-facing and reasoning tasks.
        # ═══════════════════════════════════════════════════════════════════

        "gemini_flash_lite": {
            "model": "google/gemini-2.5-flash-lite",
            "name": "Gemini 2.5 Flash Lite",
            "strengths": ["instruction_following", "structured_output", "reasoning", "speed", "markdown_formatting"],
            "best_for": ["chat_engine", "chat_streaming", "conversational", "sql_generator", "kpi_suggestion", "insight_generation", "chart_recommendation", "complex_analysis"],
            "context_window": 1000000,
            "cost": "$0.075/$0.30",
        },

        # ═══════════════════════════════════════════════════════════════════
        # FALLBACK — Mistral Small 3.2 24B ($0.06/$0.18 per M)
        # Cheapest accurate model. Reliable for structured JSON, charts,
        # validation. Falls back here if Gemini has issues.
        # ═══════════════════════════════════════════════════════════════════

        "mistral_small_32": {
            "model": "mistralai/mistral-small-3.2-24b-instruct",
            "name": "Mistral Small 3.2 24B",
            "strengths": ["instruction_following", "sql", "structured_output", "function_calling", "vision"],
            "best_for": ["chart_explanation", "validation", "simple_query", "rewrite_engine", "draft_generation"],
            "context_window": 131000,
            "cost": "$0.06/$0.18",
        },

        # ═══════════════════════════════════════════════════════════════════
        # VISION — Qwen3 VL 8B (free on OpenRouter)
        # Dedicated vision model for chart/image analysis tasks.
        # Keeps vision costs at $0.
        # ═══════════════════════════════════════════════════════════════════

        "deepseek_v32": {
            "model": "deepseek/deepseek-v3.2",
            "name": "DeepSeek V3.2",
            "strengths": ["deep_reasoning", "coding", "agentic", "tool_use", "math"],
            "best_for": ["sql_generator", "complex_analysis", "kpi_suggestion", "insight_generation", "system_design"],
            "context_window": 164000,
            "cost": "$0.25/$0.40",
        },

        # ═══════════════════════════════════════════════════════════════════
        # TIER 3: FRONTIER — MiniMax M2.5 ($0.30/$1.10 per M)
        # #1 on OpenRouter rankings. SOTA coding/agentic. Excel/data expert.
        # Use only for complex design/layout tasks.
        # Estimated cost: ~5K tokens per call = ~$0.007
        # ═══════════════════════════════════════════════════════════════════

        "minimax_m25": {
            "model": "minimax/minimax-m2.5",
            "name": "MiniMax M2.5",
            "strengths": ["coding", "agentic", "excel", "data_analysis", "office_productivity"],
            "best_for": ["layout_designer", "dashboard_design", "chat_engine", "pipeline_planner"],
            "context_window": 196000,
            "cost": "$0.30/$1.10",
        },

        # ═══════════════════════════════════════════════════════════════════
        # FREE MODELS (commented out — uncomment to switch back)
        # ═══════════════════════════════════════════════════════════════════

        # "deepseek_r1": {
        #     "model": "deepseek/deepseek-r1-0528:free",
        #     "name": "DeepSeek R1 0528",
        #     "strengths": ["deep_reasoning", "math", "chain_of_thought", "coding"],
        #     "best_for": ["complex_analysis", "kpi_suggestion", "insight_generation", "sql_generator"],
        #     "context_window": 164000,
        #     "cost": "free",
        # },
        # "qwen3_235b": {
        #     "model": "qwen/qwen3-235b-a22b-thinking-2507:free",
        #     "name": "Qwen3 235B A22B Thinking",
        #     "strengths": ["reasoning", "math", "science", "tool_use", "agentic"],
        #     "best_for": ["refinement", "requirements_synthesis", "pipeline_planner", "validation"],
        #     "context_window": 131000,
        #     "cost": "free",
        # },
        # "gpt_oss_120b": {
        #     "model": "openai/gpt-oss-120b:free",
        #     "name": "OpenAI GPT-OSS 120B",
        #     "strengths": ["function_calling", "structured_output", "tool_use", "reasoning"],
        #     "best_for": ["kpi_suggestion", "insight_generation", "refinement", "json_generation"],
        #     "context_window": 131000,
        #     "cost": "free",
        # },
        # "arcee_trinity_large": {
        #     "model": "arcee-ai/trinity-large-preview:free",
        #     "name": "Arcee Trinity Large Preview",
        #     "strengths": ["agentic", "long_context", "creative", "tool_use", "orchestration"],
        #     "best_for": ["layout_designer", "dashboard_design", "system_design", "chat_engine"],
        #     "context_window": 131000,
        #     "cost": "free",
        # },
        # "stepfun_35_flash": {
        #     "model": "stepfun/step-3.5-flash:free",
        #     "name": "StepFun Step 3.5 Flash",
        #     "strengths": ["speed", "efficiency", "long_context", "reasoning"],
        #     "best_for": ["draft_generation", "simple_query", "rewrite_engine", "chat_streaming"],
        #     "context_window": 256000,
        #     "cost": "free",
        # },
        # "nvidia_nemotron_vl": {
        #     "model": "nvidia/nemotron-nano-12b-v2-vl:free",
        #     "name": "NVIDIA Nemotron Nano 12B VL",
        #     "strengths": ["vision", "ocr", "chart_analysis", "document_intelligence"],
        #     "best_for": ["chart_image_analysis", "visual_extraction", "layout_from_image"],
        #     "context_window": 128000,
        #     "cost": "free",
        # },
        # "mistral_24b": {
        #     "model": "mistralai/mistral-small-3.1-24b-instruct:free",
        #     "name": "Mistral Small 3.1 24B",
        #     "strengths": ["instruction_following", "sql", "reasoning", "efficiency"],
        #     "best_for": ["sql_generator", "chart_recommendation", "chart_explanation", "validation"],
        #     "context_window": 128000,
        #     "cost": "free",
        # },
        # "glm_45_air": {
        #     "model": "z-ai/glm-4.5-air:free",
        #     "name": "Z.ai GLM 4.5 Air",
        #     "strengths": ["agentic", "tool_use", "dual_mode", "efficiency"],
        #     "best_for": ["conversational", "simple_query", "rewrite_engine"],
        #     "context_window": 131000,
        #     "cost": "free",
        # },
        # "nvidia_nemotron_nano": {
        #     "model": "nvidia/nemotron-3-nano-30b-a3b:free",
        #     "name": "NVIDIA Nemotron 3 Nano 30B",
        #     "strengths": ["agentic", "efficiency", "specialized_tasks"],
        #     "best_for": ["draft_generation", "pipeline_planner", "simple_query"],
        #     "context_window": 256000,
        #     "cost": "free",
        # },
        # "arcee_trinity_mini": {
        #     "model": "arcee-ai/trinity-mini:free",
        #     "name": "Arcee Trinity Mini",
        #     "strengths": ["speed", "function_calling", "long_context", "efficiency"],
        #     "best_for": ["rewrite_engine", "simple_query", "draft_generation"],
        #     "context_window": 131000,
        #     "cost": "free",
        # },
        # "openrouter_auto": {
        #     "model": "openrouter/auto",
        #     "name": "OpenRouter Auto",
        #     "strengths": ["adaptive", "fallback", "broad_coverage"],
        #     "best_for": ["default"],
        #     "context_window": 200000,
        #     "cost": "free",
        # },
    }

    OPENROUTER_ROLE_MAPPING: Dict[str, str] = {
    # ─── Chat & Conversational (Gemini only, as you requested) ──────────
    "chat_engine":               "gemini_flash_lite",
    "chat_streaming":            "gemini_flash_lite",
    "conversational":            "gemini_flash_lite",

    # ─── HIGH‑PRECISION TASKS → DeepSeek V3.2 (power model) ────────────
    "kpi_suggestion":            "deepseek_v32",
    "insight_generation":        "deepseek_v32",
    "narrative_insights":        "deepseek_v32",
    "sql_generator":             "deepseek_v32",
    "chart_recommendation":      "deepseek_v32",
    "complex_analysis":          "deepseek_v32",
    "system_design":             "deepseek_v32",
    "pipeline_planner":          "deepseek_v32",
    "requirements_synthesis":    "deepseek_v32",
    "layout_designer":           "deepseek_v32",      # complex layout logic
    "dashboard_design":          "deepseek_v32",

    # ─── Medium / Cheap Tasks (Mistral is fine) ─────────────────────────
    "chart_explanation":         "mistral_small_32",  # simple explanation
    "visualization_engine":      "mistral_small_32",  # formatting, not heavy reasoning
    "draft_generation":          "mistral_small_32",
    "simple_query":              "mistral_small_32",
    "rewrite_engine":            "mistral_small_32",
    "validation":                "mistral_small_32",

    # ─── Vision Tasks (dedicated VL model) ──────────────────────────────
    "chart_image_analysis":      "qwen2_5_vl_72b",
    "visual_extraction":         "qwen2_5_vl_72b",
    "layout_from_image":         "qwen2_5_vl_72b",

    # ─── Default Fallback ───────────────────────────────────────────────
    "default":                   "mistral_small_32",    
    }
    
    # -------------------------------------------------------------------------
    # Fallback Chains
    # Primary fails → try next in chain
    # -------------------------------------------------------------------------
    FALLBACKS: Dict[str, List[str]] = {
        # Chat roles → Gemini only
        "chat_engine":          ["gemini_flash_lite", "deepseek_v32", "openrouter_auto"],
        "chat_streaming":       ["gemini_flash_lite", "deepseek_v32", "openrouter_auto"],
        "conversational":       ["gemini_flash_lite", "deepseek_v32", "openrouter_auto"],

        # High‑precision tasks → DeepSeek primary, Gemini secondary, Mistral last
        "kpi_suggestion":       ["deepseek_v32", "gemini_flash_lite", "mistral_small_32"],
        "insight_generation":   ["deepseek_v32", "gemini_flash_lite", "mistral_small_32"],
        "sql_generator":        ["deepseek_v32", "gemini_flash_lite", "mistral_small_32"],
        "chart_recommendation": ["deepseek_v32", "gemini_flash_lite", "mistral_small_32"],
        "complex_analysis":     ["deepseek_v32", "gemini_flash_lite", "mistral_small_32"],
        "system_design":        ["deepseek_v32", "gemini_flash_lite", "mistral_small_32"],
        "pipeline_planner":     ["deepseek_v32", "gemini_flash_lite", "mistral_small_32"],
        "layout_designer":      ["deepseek_v32", "gemini_flash_lite", "mistral_small_32"],
        "dashboard_design":     ["deepseek_v32", "gemini_flash_lite", "mistral_small_32"],

        # Medium tasks → Mistral primary, Gemini fallback
        "chart_explanation":    ["mistral_small_32", "gemini_flash_lite"],
        "draft_generation":     ["mistral_small_32", "gemini_flash_lite"],
        "simple_query":         ["mistral_small_32", "gemini_flash_lite"],
        "rewrite_engine":       ["mistral_small_32", "gemini_flash_lite"],
        "validation":           ["mistral_small_32", "gemini_flash_lite"],

        # Vision → Qwen primary, Gemini fallback (if Gemini gains vision)
        "chart_image_analysis": ["qwen2_5_vl_72b", "gemini_flash_lite", "mistral_small_32"],
        "visual_extraction":    ["qwen2_5_vl_72b", "gemini_flash_lite", "mistral_small_32"],
        "layout_from_image":    ["qwen2_5_vl_72b", "gemini_flash_lite", "mistral_small_32"],

        # Default
        "default":              ["mistral_small_32", "gemini_flash_lite", "openrouter_auto"],
    }
    # -------------------------------------------------------------------------
    # Health / Timeouts
    # -------------------------------------------------------------------------
    MODEL_HEALTH_CHECK_TIMEOUT: int = int(os.getenv("MODEL_HEALTH_CHECK_TIMEOUT", "180"))
    MODEL_FALLBACK_ENABLED: bool = os.getenv("MODEL_FALLBACK_ENABLED", "true").lower() == "true"

    # -------------------------------------------------------------------------
    # Vector Database Configuration
    # -------------------------------------------------------------------------
    VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", "./faiss_db")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
    ENABLE_VECTOR_SEARCH: bool = os.getenv("ENABLE_VECTOR_SEARCH", "true").lower() == "true"

    # -------------------------------------------------------------------------
    # CORS Configuration
    # -------------------------------------------------------------------------
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "").split(",")

    # -------------------------------------------------------------------------
    # File Upload Configuration
    # -------------------------------------------------------------------------
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "524288000"))  # 500 MB
    ALLOWED_FILE_TYPES: List[str] = os.getenv("ALLOWED_FILE_TYPES", "csv,xlsx,xls").split(",")


# Instantiate settings and run validation
settings = Settings()

# Runtime validation (since __post_init__ doesn't run on regular classes)
if settings.USE_OPENROUTER and not settings.OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY must be set in .env for OpenRouter usage")
if not settings.SECRET_KEY:
    raise ValueError("SECRET_KEY must be set in .env (use secrets.token_hex(32) to generate)")