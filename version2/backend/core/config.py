import os
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # OpenRouter Configuration (Primary/Only Backend)
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
    
    # OpenRouter Models (Free Tier - Productive for Analytics)
    OPENROUTER_MODELS: Dict[str, Dict[str, Any]] = {
        "hermes_405b": {
            "model": "nousresearch/hermes-3-llama-3.1-405b:free",
            "name": "Nous Hermes 3 405B",
            "strengths": ["structured_output", "function_calling", "reasoning", "json_generation"],
            "best_for": ["chart_explanation", "kpi_suggestion", "insight_refinement"],
            "context_window": 128000,
            "cost": "free"
        },
        "qwen_235b": {
            "model": "qwen/qwen3-235b-a22b:free",
            "name": "Qwen3-235B (A22B)",
            "strengths": ["reasoning", "thinking_mode", "long_context", "tool_calling"],
            "best_for": ["chart_recommendation", "kpi_generation", "complex_reasoning"],
            "context_window": 32768,
            "cost": "free"
        },
        "qwen_4b": {
            "model": "qwen/qwen3-4b:free",
            "name": "Qwen3-4B",
            "strengths": ["efficiency", "dual_mode", "quick_responses"],
            "best_for": ["draft_generation", "simple_chat", "quick_analysis"],
            "context_window": 32768,
            "cost": "free"
        },
        "mistral_24b": {
            "model": "mistralai/mistral-small-3.1-24b-instruct:free",
            "name": "Mistral Small 3.1 24B",
            "strengths": ["reasoning", "math", "vision", "long_context"],
            "best_for": ["generalist_tasks", "multi_modal", "math_reasoning"],
            "context_window": 128000,
            "cost": "free"
        },
        "llama_70b": {
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "name": "Meta Llama 3.3 70B",
            "strengths": ["dialogue", "instruction_following", "multilingual"],
            "best_for": ["chat_engine", "instruction_tasks", "refinement"],
            "context_window": 128000,
            "cost": "free"
        },
        "nemotron_vl": {
            "model": "nvidia/nemotron-nano-12b-v2-vl:free",
            "name": "NVIDIA Nemotron Nano 12B VL",
            "strengths": ["vision", "chart_analysis", "multi_image", "ocr"],
            "best_for": ["chart_image_analysis", "visual_reasoning", "data_extraction"],
            "context_window": 8192,
            "cost": "free"
        }
    }
    
    # Role Mapping (Distributed to Avoid Rate Limits - Max 2-3 Tasks Per Model)
    OPENROUTER_ROLE_MAPPING: Dict[str, str] = {
        # Charts & Visualization
        "chart_recommendation": "mistral_24b",
        "chart_explanation": "mistral_24b",
        # KPIs & Insights
        "kpi_suggestion": "hermes_405b",
        "insight_generation": "hermes_405b",
        # Chat & Conversational
        "chat_engine": "llama_70b",
        "conversational": "llama_70b",
        "chat_streaming": "llama_70b",
        # Design & Layout
        "layout_designer": "qwen_235b",
        "dashboard_design": "qwen_235b",
        # Quick Tasks
        "draft_generation": "qwen_4b",
        "simple_query": "qwen_4b",
        "rewrite_engine": "qwen_4b",
        # Refinement & Validation
        "refinement": "hermes_405b",
        "validation": "mistral_24b",
        "visualization_engine": "qwen_235b",
        # Vision Tasks
        "chart_image_analysis": "nemotron_vl",
        "visual_extraction": "nemotron_vl",
        # Default
        "default": "mistral_24b"
    }
    
    # Fallback Chain (Simple List Per Role - Cycle if Primary Fails)
    FALLBACKS: Dict[str, List[str]] = {
        "chat_engine": ["llama_70b", "qwen_235b", "mistral_24b"],
        "kpi_suggestion": ["hermes_405b", "qwen_235b", "llama_70b"],
        "layout_designer": ["qwen_235b", "hermes_405b", "mistral_24b"],
        # ... (add for other roles as needed, or default to ["qwen_4b", "mistral_24b"])
        "default": ["qwen_4b", "mistral_24b", "llama_70b"]
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