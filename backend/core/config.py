import os
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class Settings:
    USE_OPENROUTER: bool = os.getenv("USE_OPENROUTER", "true").lower() == "true"
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")

    # MongoDB Configuration
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "datasage_ai")

    # JWT Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "50"))

    # OPENROUTER_MODELS (Free-tier confirmed as of Jan 2026)
    OPENROUTER_MODELS: Dict[str, Dict[str, Any]] = {
        "hermes_405b": {
            "model": "nousresearch/hermes-3-llama-3.1-405b:free",
            "name": "Nous Hermes 3 405B",
            "strengths": ["structured_output", "function_calling", "reasoning", "json_generation"],
            "best_for": ["kpi_suggestion", "insight_generation", "refinement", "tool_use"],
            "context_window": 128000,
            "cost": "free"
        },
        "qwen_vl_8b": {
            "model": "qwen/qwen3-vl-8b-instruct",  # NOTE: Not free currently; remove :free or monitor
            "name": "Qwen3-VL 8B Instruct",
            "strengths": ["vision", "chart_analysis", "ocr", "visual_reasoning"],
            "best_for": ["chart_image_analysis", "visual_extraction", "layout_from_image"],
            "context_window": 32768,
            "cost": "paid"  # Update if it becomes free
        },
        "mistral_24b": {
            "model": "mistralai/mistral-small-3.1-24b-instruct:free",
            "name": "Mistral Small 3.1 24B",
            "strengths": ["reasoning", "math", "efficiency", "instruction_following"],
            "best_for": ["chat_engine", "conversational", "refinement", "generalist_tasks"],
            "context_window": 128000,
            "cost": "free"
        },
        "devstral_2": {
            "model": "mistralai/devstral-2512:free",  # Correct ID format
            "name": "Devstral 2 2512",
            "strengths": ["long_context", "planning", "codebase_understanding", "orchestration"],
            "best_for": ["layout_designer", "system_design", "requirements_synthesis", "pipeline_planner"],
            "context_window": 256000,
            "cost": "free"
        },
        "qwen_4b": {
            "model": "qwen/qwen3-4b:free",  # Confirm if still free; fallback if not
            "name": "Qwen3-4B",
            "strengths": ["efficiency", "dual_mode", "quick_responses"],
            "best_for": ["draft_generation", "simple_query", "rewrite_engine"],
            "context_window": 32768,
            "cost": "free"
        }
    }

    OPENROUTER_ROLE_MAPPING: Dict[str, str] = {
        # Charts & Visualization
        "chart_recommendation": "mistral_24b",
        "chart_explanation": "mistral_24b",
        # KPIs & Insights
        "kpi_suggestion": "hermes_405b",
        "insight_generation": "hermes_405b",
        # Chat & Conversational
        "chat_engine": "mistral_24b",
        "conversational": "mistral_24b",
        "chat_streaming": "mistral_24b",
        # Design & Layout
        "layout_designer": "devstral_2",  # Text-based planning
        "dashboard_design": "devstral_2",
        "layout_from_image": "qwen_vl_8b",  # Vision input
        # Quick Tasks
        "draft_generation": "qwen_4b",
        "simple_query": "qwen_4b",
        "rewrite_engine": "qwen_4b",
        # Refinement & Validation
        "refinement": "hermes_405b",
        "validation": "mistral_24b",
        "visualization_engine": "mistral_24b",
        # Vision Tasks
        "chart_image_analysis": "qwen_vl_8b",
        "visual_extraction": "qwen_vl_8b",
        # High-Level Planning
        "system_design": "devstral_2",
        "requirements_synthesis": "devstral_2",
        "pipeline_planner": "devstral_2",
        # Default Fallback
        "default": "mistral_24b"
    }

    FALLBACKS: Dict[str, List[str]] = {
        "chat_engine": ["mistral_24b", "hermes_405b", "qwen_4b"],
        "kpi_suggestion": ["hermes_405b", "mistral_24b", "devstral_2"],
        "layout_designer": ["devstral_2", "hermes_405b", "mistral_24b"],
        "chart_image_analysis": ["qwen_vl_8b", "mistral_24b"],  
        "layout_from_image": ["qwen_vl_8b", "devstral_2"],
        "default": ["qwen_4b", "mistral_24b", "hermes_405b"]
    }

    # Health/Timeouts
    MODEL_HEALTH_CHECK_TIMEOUT: int = int(os.getenv("MODEL_HEALTH_CHECK_TIMEOUT", "180"))
    MODEL_FALLBACK_ENABLED: bool = os.getenv("MODEL_FALLBACK_ENABLED", "true").lower() == "true"

    # Vector Database Configuration
    VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", "./faiss_db")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
    ENABLE_VECTOR_SEARCH: bool = os.getenv("ENABLE_VECTOR_SEARCH", "true").lower() == "true"

    # CORS Configuration
    DEV_ORIGINS = [
        "http://127.0.0.1:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174",
        "http://localhost:3000", "http://localhost:5173", "http://localhost:5174",
    ]
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", ",".join(DEV_ORIGINS)).split(",")

    # File Upload Configuration
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "52428800"))  # 50MB
    ALLOWED_FILE_TYPES: List[str] = os.getenv("ALLOWED_FILE_TYPES", "csv,xlsx,xls").split(",")

    def __post_init__(self):
        if self.USE_OPENROUTER and not self.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY must be set in .env for OpenRouter usage")
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set in .env (use secrets.token_hex(32) to generate)")

settings = Settings()