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

    # -------------------------------------------------------------------------
    # OpenRouter Models — Updated February 2026
    # All models tagged "free" are confirmed free-tier on OpenRouter.
    # Source: https://openrouter.ai/collections/free-models
    # -------------------------------------------------------------------------
    OPENROUTER_MODELS: Dict[str, Dict[str, Any]] = {

        # --- FRONTIER / REASONING ---

        "deepseek_r1": {
            # Best open-source reasoning model; on-par with OpenAI o1
            "model": "deepseek/deepseek-r1-0528:free",
            "name": "DeepSeek R1 0528",
            "strengths": ["deep_reasoning", "math", "chain_of_thought", "coding"],
            "best_for": ["complex_analysis", "kpi_suggestion", "insight_generation", "sql_generator"],
            "context_window": 164000,
            "cost": "free",
        },
        "qwen3_235b": {
            # 235B MoE reasoning monster — beats many closed models on benchmarks
            "model": "qwen/qwen3-235b-a22b-thinking-2507:free",
            "name": "Qwen3 235B A22B Thinking",
            "strengths": ["reasoning", "math", "science", "tool_use", "agentic"],
            "best_for": ["refinement", "requirements_synthesis", "pipeline_planner", "validation"],
            "context_window": 131000,
            "cost": "free",
        },
        "gpt_oss_120b": {
            # OpenAI's first open-weight model — strong tool use & structured output
            "model": "openai/gpt-oss-120b:free",
            "name": "OpenAI GPT-OSS 120B",
            "strengths": ["function_calling", "structured_output", "tool_use", "reasoning"],
            "best_for": ["kpi_suggestion", "insight_generation", "refinement", "json_generation"],
            "context_window": 131000,
            "cost": "free",
        },
        "arcee_trinity_large": {
            # 400B MoE — great for agents, creative tasks, long contexts
            "model": "arcee-ai/trinity-large-preview:free",
            "name": "Arcee Trinity Large Preview",
            "strengths": ["agentic", "long_context", "creative", "tool_use", "orchestration"],
            "best_for": ["layout_designer", "dashboard_design", "system_design", "chat_engine"],
            "context_window": 131000,
            "cost": "free",
        },
        "stepfun_35_flash": {
            # 196B MoE (11B active) — very fast, excellent for speed-sensitive tasks
            "model": "stepfun/step-3.5-flash:free",
            "name": "StepFun Step 3.5 Flash",
            "strengths": ["speed", "efficiency", "long_context", "reasoning"],
            "best_for": ["draft_generation", "simple_query", "rewrite_engine", "chat_streaming"],
            "context_window": 256000,
            "cost": "free",
        },

        # --- VISION / MULTIMODAL ---

        "nvidia_nemotron_vl": {
            # Best free vision model — OCR, charts, documents, video
            "model": "nvidia/nemotron-nano-12b-v2-vl:free",
            "name": "NVIDIA Nemotron Nano 12B VL",
            "strengths": ["vision", "ocr", "chart_analysis", "document_intelligence", "video_understanding"],
            "best_for": ["chart_image_analysis", "visual_extraction", "layout_from_image"],
            "context_window": 128000,
            "cost": "free",
        },

        # --- EFFICIENT / GENERAL PURPOSE ---

        "mistral_24b": {
            # Reliable, free, great at instructions and SQL
            "model": "mistralai/mistral-small-3.1-24b-instruct:free",
            "name": "Mistral Small 3.1 24B",
            "strengths": ["instruction_following", "sql", "reasoning", "efficiency"],
            "best_for": ["sql_generator", "chart_recommendation", "chart_explanation", "validation"],
            "context_window": 128000,
            "cost": "free",
        },
        "glm_45_air": {
            # Lightweight MoE with thinking + non-thinking modes; great for agents
            "model": "z-ai/glm-4.5-air:free",
            "name": "Z.ai GLM 4.5 Air",
            "strengths": ["agentic", "tool_use", "dual_mode", "efficiency"],
            "best_for": ["conversational", "simple_query", "rewrite_engine"],
            "context_window": 131000,
            "cost": "free",
        },
        "nvidia_nemotron_nano": {
            # Compact agentic MoE — ideal for specialized agent pipelines
            "model": "nvidia/nemotron-3-nano-30b-a3b:free",
            "name": "NVIDIA Nemotron 3 Nano 30B",
            "strengths": ["agentic", "efficiency", "specialized_tasks"],
            "best_for": ["draft_generation", "pipeline_planner", "simple_query"],
            "context_window": 256000,
            "cost": "free",
        },
        "arcee_trinity_mini": {
            # 26B MoE (3B active) — ultra-fast, long context, function calling
            "model": "arcee-ai/trinity-mini:free",
            "name": "Arcee Trinity Mini",
            "strengths": ["speed", "function_calling", "long_context", "efficiency"],
            "best_for": ["rewrite_engine", "simple_query", "draft_generation"],
            "context_window": 131000,
            "cost": "free",
        },

        # --- AUTO ROUTER (fallback / experimentation) ---
        "openrouter_auto": {
            # OpenRouter's smart router — picks best available free model automatically
            "model": "openrouter/auto",
            "name": "OpenRouter Auto",
            "strengths": ["adaptive", "fallback", "broad_coverage"],
            "best_for": ["default"],
            "context_window": 200000,
            "cost": "free",
        },
    }

    # -------------------------------------------------------------------------
    # Role → Model Mapping
    # -------------------------------------------------------------------------
    OPENROUTER_ROLE_MAPPING: Dict[str, str] = {
        # Charts & Visualization
        "chart_recommendation":     "mistral_24b",
        "chart_explanation":         "mistral_24b",
        "visualization_engine":      "mistral_24b",

        # KPIs & Insights
        "kpi_suggestion":            "gpt_oss_120b",
        "insight_generation":        "gpt_oss_120b",

        # SQL Generation
        "sql_generator":             "deepseek_r1",       # DeepSeek R1 is exceptional at SQL

        # Chat & Conversational
        "chat_engine":               "arcee_trinity_large",
        "conversational":            "glm_45_air",
        "chat_streaming":            "stepfun_35_flash",  # Fastest free model

        # Design & Layout
        "layout_designer":           "arcee_trinity_large",
        "dashboard_design":          "arcee_trinity_large",
        "layout_from_image":         "nvidia_nemotron_vl",  # Vision input

        # Quick Tasks
        "draft_generation":          "stepfun_35_flash",
        "simple_query":              "glm_45_air",
        "rewrite_engine":            "arcee_trinity_mini",

        # Refinement & Validation
        "refinement":                "qwen3_235b",
        "validation":                "mistral_24b",

        # Vision Tasks
        "chart_image_analysis":      "nvidia_nemotron_vl",
        "visual_extraction":         "nvidia_nemotron_vl",

        # High-Level Planning & Complex Reasoning
        "system_design":             "qwen3_235b",
        "requirements_synthesis":    "qwen3_235b",
        "pipeline_planner":          "arcee_trinity_large",
        "complex_analysis":          "deepseek_r1",

        # Default Fallback
        "default":                   "openrouter_auto",
    }

    # -------------------------------------------------------------------------
    # Fallback Chains (ordered by preference)
    # -------------------------------------------------------------------------
    FALLBACKS: Dict[str, List[str]] = {
        "chat_engine":          ["arcee_trinity_large", "glm_45_air", "stepfun_35_flash"],
        "kpi_suggestion":       ["gpt_oss_120b", "deepseek_r1", "qwen3_235b"],
        "sql_generator":        ["deepseek_r1", "mistral_24b", "gpt_oss_120b"],
        "layout_designer":      ["arcee_trinity_large", "qwen3_235b", "mistral_24b"],
        "chart_image_analysis": ["nvidia_nemotron_vl", "mistral_24b"],
        "layout_from_image":    ["nvidia_nemotron_vl", "arcee_trinity_large"],
        "complex_analysis":     ["deepseek_r1", "qwen3_235b", "gpt_oss_120b"],
        "simple_query":         ["glm_45_air", "arcee_trinity_mini", "stepfun_35_flash"],
        "default":              ["openrouter_auto", "stepfun_35_flash", "mistral_24b"],
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
    DEV_ORIGINS = [
        "http://127.0.0.1:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174",
        "http://localhost:3000",  "http://localhost:5173",  "http://localhost:5174",
    ]
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", ",".join(DEV_ORIGINS)).split(",")

    # -------------------------------------------------------------------------
    # File Upload Configuration
    # -------------------------------------------------------------------------
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "52428800"))  # 50 MB
    ALLOWED_FILE_TYPES: List[str] = os.getenv("ALLOWED_FILE_TYPES", "csv,xlsx,xls").split(",")

    def __post_init__(self):
        if self.USE_OPENROUTER and not self.OPENROUTER_API_KEY:
            raise ValueError(
                "OPENROUTER_API_KEY must be set in .env for OpenRouter usage"
            )
        if not self.SECRET_KEY:
            raise ValueError(
                "SECRET_KEY must be set in .env (use secrets.token_hex(32) to generate)"
            )


settings = Settings()