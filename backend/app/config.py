from pydantic_settings import BaseSettings
from typing import List
import os
from pathlib import Path

class Settings(BaseSettings):
    """Application settings"""
    
    # API settings
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "Bonds Screener API"
    
    # CORS - default values only, don't load from .env
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # Data paths
    DATA_DIR: str = "./data"
    
    # External data sources
    MOEX_BONDS_URL: str = "https://iss.moex.com/iss/engines/stock/markets/bonds/securities.json"
    
    # OpenAI API - will be loaded manually from .env
    OPENAI_API_KEY: str = ""
    
    class Config:
        # Don't load from .env automatically to avoid parsing errors
        env_file = None
        case_sensitive = True
        extra = "ignore"

# Create settings instance
settings = Settings()

# Manually load OPENAI_API_KEY from .env file
_env_file = Path(__file__).parent.parent / ".env"  # backend/.env
if not _env_file.exists():
    _env_file = Path(__file__).parent.parent.parent / ".env"  # project root/.env

if _env_file.exists():
    with open(_env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                if key == "OPENAI_API_KEY":
                    settings.OPENAI_API_KEY = value
                    break

# Also check environment variable as fallback
if not settings.OPENAI_API_KEY:
    settings.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip().strip("'").strip('"')
