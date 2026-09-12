from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from app.core.config import settings
from app.providers.weather_provider import WeatherProvider, WeatherObservation, MockWeatherProvider, OpenWeatherProvider
from app.providers.flood_provider import FloodProvider, FloodObservation, create_flood_provider


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    SEVERE = "severe"


@dataclass
class RiskAssessment:
    segment_id: str
    risk_level: RiskLevel
    source: str
    last_updated: datetime
    flood_observation: Optional[FloodObservation] = None
    weather_observation: Optional[WeatherObservation] = None


class RiskEngine:
    def __init__(
        self,
        weather_provider: WeatherProvider,
        flood_provider: FloodProvider,
    ):
        self.weather_provider = weather_provider
        self.flood_provider = flood_provider
    
    async def assess_risk(self, segment_id: str) -> RiskAssessment:
        flood_obs = await self.flood_provider.get_flood_status(segment_id)
        weather_obs = await self.weather_provider.get_weather(segment_id)
        
        return self._assess_with_observations(segment_id, flood_obs, weather_obs)
    
    def assess_risk_with_observations(
        self, 
        segment_id: str, 
        flood: FloodObservation, 
        weather: WeatherObservation
    ) -> RiskAssessment:
        return self._assess_with_observations(segment_id, flood, weather)
    
    def _assess_with_observations(
        self, 
        segment_id: str, 
        flood: FloodObservation, 
        weather: WeatherObservation
    ) -> RiskAssessment:
        risk_level = self._calculate_risk(flood, weather)
        source = self._determine_source(flood, weather, risk_level)
        last_updated = max(flood.observed_at, weather.observed_at)
        
        return RiskAssessment(
            segment_id=segment_id,
            risk_level=risk_level,
            source=source,
            last_updated=last_updated,
            flood_observation=flood,
            weather_observation=weather,
        )
    
    def _calculate_risk(self, flood: FloodObservation, weather: WeatherObservation) -> RiskLevel:
        # Check if flood data is stale or unavailable - if so, don't use it for MODERATE/SEVERE
        flood_is_unusable = False
        if flood.raw_data and isinstance(flood.raw_data, dict):
            freshness = flood.raw_data.get("freshness", {})
            if isinstance(freshness, dict):
                if freshness.get("is_stale") or freshness.get("is_unavailable"):
                    flood_is_unusable = True
        
        # Rule 1: water level >= danger level → SEVERE (only if flood data is fresh/available)
        if (not flood_is_unusable and flood.water_level_m is not None and flood.danger_level_m is not None 
                and flood.water_level_m >= flood.danger_level_m):
            return RiskLevel.SEVERE
        
        # Rule 2: water level >= warning level → MODERATE (only if flood data is fresh/available)
        if (not flood_is_unusable and flood.water_level_m is not None and flood.warning_level_m is not None 
                and flood.water_level_m >= flood.warning_level_m):
            return RiskLevel.MODERATE
        
        # Rule 3: heavy rain OR fog → at least LOW
        if self._is_heavy_rain(weather) or self._is_fog(weather):
            return RiskLevel.LOW
        
        # Rule 4: otherwise → NONE
        return RiskLevel.NONE
    
    def _is_heavy_rain(self, weather: WeatherObservation) -> bool:
        return (
            weather.precipitation_mm >= 10.0 or
            weather.condition in ("heavy_rain", "storm", "extreme_rain")
        )
    
    def _is_fog(self, weather: WeatherObservation) -> bool:
        return (
            weather.visibility_m is not None and weather.visibility_m < 1000.0
        ) or weather.condition in ("fog", "dense_fog", "mist")
    
    def _determine_source(
        self, 
        flood: FloodObservation, 
        weather: WeatherObservation, 
        risk_level: RiskLevel
    ) -> str:
        if risk_level in (RiskLevel.SEVERE, RiskLevel.MODERATE):
            return "flood"
        elif risk_level == RiskLevel.LOW:
            if self._is_heavy_rain(weather) and self._is_fog(weather):
                return "weather"
            elif self._is_heavy_rain(weather):
                return "weather"
            elif self._is_fog(weather):
                return "weather"
        return "none"


class RiskService:
    def __init__(self, weather_provider: WeatherProvider, flood_provider: FloodProvider):
        self.engine = RiskEngine(weather_provider, flood_provider)
        self._cache: dict[str, RiskAssessment] = {}
        self._cache_time: dict[str, datetime] = {}
        self.refresh_interval = timedelta(seconds=settings.risk_refresh_interval_seconds)
    
    async def get_risk_score(self, segment_id: str) -> RiskAssessment:
        now = datetime.utcnow()
        
        if (segment_id in self._cache and segment_id in self._cache_time
                and now - self._cache_time[segment_id] < self.refresh_interval):
            return self._cache[segment_id]
        
        assessment = await self.engine.assess_risk(segment_id)
        self._cache[segment_id] = assessment
        self._cache_time[segment_id] = now
        return assessment
    
    def clear_cache(self) -> None:
        self._cache.clear()
        self._cache_time.clear()
    
    def get_provider_status(self) -> dict:
        weather_status = self.engine.weather_provider.get_provider_status()
        flood_status = self.engine.flood_provider.get_provider_status()
        
        return {
            "weather_provider": self.engine.weather_provider.get_provider_name(),
            "weather_api_configured": self.engine.weather_provider.get_provider_name() == "openweathermap",
            "last_weather_fetch_at": weather_status.last_fetch_at.isoformat() if weather_status.last_fetch_at else None,
            "last_weather_http_status": weather_status.last_http_status,
            "last_weather_source": weather_status.last_source,
            "cache_enabled": True,
            "cache_refresh_seconds": settings.risk_refresh_interval_seconds,
        }


def create_risk_service() -> RiskService:
    # Weather provider selection
    if settings.weather_provider == "openweathermap":
        api_key = settings.openweather_api_key
        if not api_key:
            raise ValueError("OPENWEATHER_API_KEY is required when WEATHER_PROVIDER=openweathermap")
        weather_provider = OpenWeatherProvider(api_key)
    else:
        weather_provider = MockWeatherProvider()
    
    # Flood provider selection
    flood_provider = create_flood_provider()
    
    return RiskService(weather_provider, flood_provider)


risk_service = create_risk_service()