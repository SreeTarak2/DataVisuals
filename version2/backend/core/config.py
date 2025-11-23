import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # MongoDB Configuration
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "datasage_ai")
    
    # JWT Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "50"))
    
    # Ollama / local model configuration (optional, disabled by default)
    LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://localhost:11434")
    QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "http://localhost:11434")
    model_name = os.getenv("LLM_PRIMARY_MODEL", "llama3.1")

    MODELS = {
        "chat_engine": {
            "primary": {"model": model_name, "base_url": LLAMA_BASE_URL}
        },
        "layout_designer": {
            "primary": {"model": model_name, "base_url": LLAMA_BASE_URL}
        },
        "summary_engine": {
            "primary": {"model": model_name, "base_url": LLAMA_BASE_URL}
        },
        "chart_recommender": {
            "primary": {"model": model_name, "base_url": LLAMA_BASE_URL}
        },
        "chart_engine": {
            "primary": {"model": model_name, "base_url": LLAMA_BASE_URL}
        },
        "insight_engine": {
            "primary": {"model": model_name, "base_url": LLAMA_BASE_URL}
        },
        "visualization_engine": {
            "primary": {"model": "qwen3:0.6b", "base_url": QWEN_BASE_URL}
        },
    }
    
    MODEL_HEALTH_CHECK_TIMEOUT = 180
    MODEL_FALLBACK_ENABLED = False  # Fallback mechanism removed

    # OpenRouter configuration
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "alibaba/tongyi-deepresearch-30b-a3b:free")

    # Vector Database Configuration
    VECTOR_DB_PATH: str = os.getenv("VECTOR_DB_PATH", "./faiss_db")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
    ENABLE_VECTOR_SEARCH: bool = os.getenv("ENABLE_VECTOR_SEARCH", "true").lower() == "true"

    # CORS Configuration
    # In development, allow all localhost origins
    DEV_ORIGINS = [
        "http://127.0.0.1:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174",
        "http://localhost:3000", "http://localhost:5173", "http://localhost:5174",
    ]
    
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", ",".join(DEV_ORIGINS)).split(",")
    
    # File Upload Configuration
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "52428800"))  # 50MB
    ALLOWED_FILE_TYPES: List[str] = os.getenv("ALLOWED_FILE_TYPES", "csv,xlsx,xls").split(",")

settings = Settings()



