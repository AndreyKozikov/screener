from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Any
from pathlib import Path

# Find .env file - only check backend/.env (single source of truth)
_env_file_path = None
_backend_env = Path(__file__).parent.parent / ".env"  # backend/.env

if _backend_env.exists():
    _env_file_path = str(_backend_env)

class Settings(BaseSettings):
    """Application settings"""
    
    # API settings
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "Bonds Screener API"
    
    # CORS - default values include localhost, can be extended via environment variable
    # To allow external access, set CORS_ORIGINS environment variable as comma-separated list
    # Example: CORS_ORIGINS=http://localhost:5173,http://localhost:3000,http://192.168.1.100:5173
    # Or use ["*"] to allow all origins (less secure, not recommended for production)
    # Special value "*" means allow all origins (for development/external IP access)
    CORS_ORIGINS: List[str] | str = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"]
    
    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v: Any) -> Any:
        """Parse CORS_ORIGINS from string (comma-separated) or list"""
        if isinstance(v, str):
            # Special case: "*" means allow all origins
            if v.strip() == "*":
                return ["*"]
            # Split by comma and strip whitespace
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v
    
    # Data paths
    DATA_DIR: str = "./data"
    
    # External data sources
    MOEX_BONDS_URL: str = "https://iss.moex.com/iss/engines/stock/markets/bonds/securities.json"
    
    # OpenAI API - loaded from .env or environment variables
    OPENAI_API_KEY: str = ""
    
    # OpenRouter API - loaded from .env or environment variables
    OPENROUTER_API_KEY: str = ""
    
    # OpenRouter optional headers for rankings (optional)
    OPENROUTER_HTTP_REFERER: str = ""  # Optional. Site URL for rankings on openrouter.ai
    OPENROUTER_X_TITLE: str = ""  # Optional. Site title for rankings on openrouter.ai
    
    model_config = SettingsConfigDict(
        env_file=_env_file_path,  # Use found .env file path or None
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore',
        # Ignore fields that are not in the .env file to avoid parsing errors
        env_ignore_empty=True,
    )

# Create settings instance
settings = Settings()
