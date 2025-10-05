from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # MongoDB Configuration
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "datasage"
    
    # OpenAI Configuration
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    
    # Local LLM Configuration
    use_local_llm: bool = True
    local_llm_url: str = "https://04da7c76bcab.ngrok-free.app/"
    local_llm_model: str = "llama3:instruct"
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    
    # File Upload Configuration
    max_file_size: int = 104857600  # 100MB
    upload_dir: str = "./uploads"
    
    # Authentication Configuration
    secret_key: str = "this is the random key for the jwt token"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Create settings instance
settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.upload_dir, exist_ok=True)
