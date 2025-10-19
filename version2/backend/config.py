import os
from typing import List

class Settings:
    # MongoDB Configuration
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "datasage_ai")
    
    # JWT Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "50"))
    
    
    # # Ollama Configuration
    # OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "https://3aa913b93b79.ngrok-free.app/")
    # OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "mistral:7b")

    LLAMA_BASE_URL = "https://e25f9df7b292.ngrok-free.app/"
    MISTRAL_BASE_URL = "https://wilber-unremarried-reversibly.ngrok-free.dev/"

    MODELS = {
        "chat_engine": {"model": "llama3.1", "base_url":LLAMA_BASE_URL},
        "layout_designer": {"model": "llama3.1", "base_url":LLAMA_BASE_URL},
        "summary_engine": {"model": "llama3.1", "base_url":LLAMA_BASE_URL},
        "chart_recommender": {"model": "mistral:7b", "base_url": MISTRAL_BASE_URL},
        "story_engine": {"model": "mistral:7b", "base_url": MISTRAL_BASE_URL},
        "explainer_engine": {"model": "mistral:7b", "base_url": MISTRAL_BASE_URL},
        "business_engine": {"model": "mistral:7b", "base_url": MISTRAL_BASE_URL},
    }

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
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
    ALLOWED_FILE_TYPES: List[str] = os.getenv("ALLOWED_FILE_TYPES", "csv,xlsx,xls").split(",")

settings = Settings()



