from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    app_name: str = "RailSentinel Position Service"
    debug: bool = True
    cors_origins: List[str] = ["*"]
    position_history_size: int = 50
    map_matching_max_distance: float = 100.0
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Risk layer configuration
    weather_provider: str = "mock"
    flood_provider: str = "mock"
    risk_refresh_interval_seconds: int = 600
    # API keys for future real providers (not used by mock)
    openweather_api_key: Optional[str] = None
    cwc_api_key: Optional[str] = None
    # CWC freshness guard: max age in seconds for CWC observations to be considered fresh
    # Default: 7 days (604800 seconds) - configurable for demo
    cwc_max_age_seconds: int = 604800

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()