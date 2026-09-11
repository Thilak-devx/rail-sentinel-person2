from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import httpx
import logging
import re

from app.services.segment_registry import segment_registry


logger = logging.getLogger(__name__)

# Sensitive query parameters that should never appear in logs
SENSITIVE_PARAMS = ("appid", "api_key", "apikey", "access_token", "token", "secret", "password")


def _redact_sensitive_params(url: str) -> str:
    """Redact sensitive query parameters from a URL."""
    for param in SENSITIVE_PARAMS:
        pattern = rf'({param}=)[^&\s]+'
        url = re.sub(pattern, r'\1[REDACTED]', url)
    return url


class _SensitiveParamFilter(logging.Filter):
    """Filter to redact sensitive query parameters from log messages.
    
    Works on both formatted messages and log record args to catch httpx/httpcore
    log messages before they are fully formatted.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Redact in the message string if present
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = _redact_sensitive_params(record.msg)
        
        # Redact in args if present (httpx logs often use args for formatting)
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    new_args.append(_redact_sensitive_params(arg))
                elif hasattr(arg, '__str__') and not isinstance(arg, (int, float, bool)):  # Handle httpx.URL and similar objects
                    # Convert to string, redact, and keep as string for formatting
                    new_args.append(_redact_sensitive_params(str(arg)))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)
        
        return True


# Apply filter to httpx and httpcore loggers
# This ensures sensitive params are redacted even at DEBUG level
_sensitive_filter = _SensitiveParamFilter()
logging.getLogger("httpx").addFilter(_sensitive_filter)
logging.getLogger("httpcore").addFilter(_sensitive_filter)

# Also set default level to WARNING to avoid noisy logs in production
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@dataclass
class WeatherObservation:
    segment_id: str
    precipitation_mm: float
    visibility_m: Optional[float]
    condition: str
    observed_at: datetime
    source: str
    raw_data: Optional[dict] = None


@dataclass
class ProviderStatus:
    last_fetch_at: Optional[datetime] = None
    last_http_status: Optional[int] = None
    last_source: Optional[str] = None
    last_error: Optional[str] = None


class WeatherProvider(ABC):
    @abstractmethod
    async def get_weather(self, segment_id: str) -> WeatherObservation:
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        pass
    
    @abstractmethod
    def get_provider_status(self) -> ProviderStatus:
        pass


class OpenWeatherProvider(WeatherProvider):
    def __init__(self, api_key: str, timeout: float = 10.0):
        if not api_key:
            raise ValueError("OpenWeather API key is required")
        self.api_key = api_key
        self.timeout = timeout
        self._base_url = "https://api.openweathermap.org/data/2.5/weather"
        self._status = ProviderStatus()
    
    def _get_coordinates(self, segment_id: str) -> Optional[tuple]:
        """Get coordinates for a segment from the registry."""
        return segment_registry.get_coordinates(segment_id)
    
    async def get_weather(self, segment_id: str) -> WeatherObservation:
        coords = self._get_coordinates(segment_id)
        if not coords:
            return WeatherObservation(
                segment_id=segment_id,
                precipitation_mm=0.0,
                visibility_m=None,
                condition="unknown",
                observed_at=datetime.utcnow(),
                source="openweathermap",
            )
        
        lat, lon = coords
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
        }
        
        logger.info("openweathermap request started segment_id=%s lat=%s lon=%s", segment_id, lat, lon)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self._base_url, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            logger.warning("openweathermap request timeout segment_id=%s", segment_id)
            self._status = ProviderStatus(
                last_fetch_at=datetime.utcnow(),
                last_http_status=408,
                last_source="openweathermap",
                last_error="timeout"
            )
            return WeatherObservation(
                segment_id=segment_id,
                precipitation_mm=0.0,
                visibility_m=None,
                condition="timeout",
                observed_at=datetime.utcnow(),
                source="openweathermap",
                raw_data={"error": "timeout"},
            )
        except httpx.HTTPStatusError as e:
            logger.warning("openweathermap request http_error segment_id=%s status=%s", segment_id, e.response.status_code)
            self._status = ProviderStatus(
                last_fetch_at=datetime.utcnow(),
                last_http_status=e.response.status_code,
                last_source="openweathermap",
                last_error=f"http_{e.response.status_code}"
            )
            return WeatherObservation(
                segment_id=segment_id,
                precipitation_mm=0.0,
                visibility_m=None,
                condition="http_error",
                observed_at=datetime.utcnow(),
                source="openweathermap",
                raw_data={"error": f"http_{e.response.status_code}"},
            )
        except Exception as e:
            logger.error("openweathermap request error segment_id=%s error=%s", segment_id, type(e).__name__)
            self._status = ProviderStatus(
                last_fetch_at=datetime.utcnow(),
                last_http_status=None,
                last_source="openweathermap",
                last_error=type(e).__name__
            )
            return WeatherObservation(
                segment_id=segment_id,
                precipitation_mm=0.0,
                visibility_m=None,
                condition="error",
                observed_at=datetime.utcnow(),
                source="openweathermap",
                raw_data={"error": type(e).__name__},
            )
        
        logger.info("openweathermap request success segment_id=%s status=%s", segment_id, response.status_code)
        self._status = ProviderStatus(
            last_fetch_at=datetime.utcnow(),
            last_http_status=response.status_code,
            last_source="openweathermap",
            last_error=None
        )
        return self._parse_response(segment_id, data)
    
    def _parse_response(self, segment_id: str, data: dict) -> WeatherObservation:
        # Extract precipitation (rain volume in last 1h or 3h)
        precipitation_mm = 0.0
        if "rain" in data:
            rain = data["rain"]
            if isinstance(rain, dict):
                precipitation_mm = rain.get("1h", rain.get("3h", 0.0))
        
        # Extract visibility (meters)
        visibility_m = data.get("visibility")
        
        # Extract weather condition
        condition = "clear"
        if "weather" in data and data["weather"]:
            main = data["weather"][0].get("main", "").lower()
            desc = data["weather"][0].get("description", "").lower()
            if main in ("rain", "drizzle", "thunderstorm"):
                condition = "rain"
                if precipitation_mm >= 10.0 or "heavy" in desc:
                    condition = "heavy_rain"
            elif main in ("mist", "fog", "haze"):
                condition = "fog"
            elif main == "snow":
                condition = "snow"
            elif main == "clear":
                condition = "clear"
            else:
                condition = main
        
        # Observation timestamp
        dt = data.get("dt")
        observed_at = datetime.utcfromtimestamp(dt) if dt else datetime.utcnow()
        
        return WeatherObservation(
            segment_id=segment_id,
            precipitation_mm=precipitation_mm,
            visibility_m=visibility_m,
            condition=condition,
            observed_at=observed_at,
            source="openweathermap",
            raw_data=data,
        )
    
    def get_provider_name(self) -> str:
        return "openweathermap"
    
    def get_provider_status(self) -> ProviderStatus:
        return self._status


class MockWeatherProvider(WeatherProvider):
    def __init__(self):
        self._demo_weather = {
            "SEG_01": WeatherObservation(
                segment_id="SEG_01",
                precipitation_mm=0.0,
                visibility_m=10000.0,
                condition="clear",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
            "SEG_02": WeatherObservation(
                segment_id="SEG_02",
                precipitation_mm=15.0,
                visibility_m=5000.0,
                condition="heavy_rain",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
            "SEG_03": WeatherObservation(
                segment_id="SEG_03",
                precipitation_mm=0.5,
                visibility_m=200.0,
                condition="fog",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
            "SEG_04": WeatherObservation(
                segment_id="SEG_04",
                precipitation_mm=8.0,
                visibility_m=3000.0,
                condition="moderate_rain",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
            # Additional segments for testing specific risk scenarios
            "SEG_LOW_RAIN": WeatherObservation(
                segment_id="SEG_LOW_RAIN",
                precipitation_mm=15.0,
                visibility_m=5000.0,
                condition="heavy_rain",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
            "SEG_LOW_FOG": WeatherObservation(
                segment_id="SEG_LOW_FOG",
                precipitation_mm=0.5,
                visibility_m=200.0,
                condition="fog",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
            "SEG_MODERATE_FLOOD": WeatherObservation(
                segment_id="SEG_MODERATE_FLOOD",
                precipitation_mm=0.0,
                visibility_m=10000.0,
                condition="clear",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
        }
    
    async def get_weather(self, segment_id: str) -> WeatherObservation:
        # First check demo data for backward compatibility
        if segment_id in self._demo_weather:
            return self._demo_weather[segment_id]
        
        # For unknown segments, return default with coordinates from registry if available
        coords = segment_registry.get_coordinates(segment_id)
        if coords:
            lat, lon = coords
            return WeatherObservation(
                segment_id=segment_id,
                precipitation_mm=0.0,
                visibility_m=10000.0,
                condition="clear",
                observed_at=datetime.utcnow(),
                source="mock",
            )
        
        return WeatherObservation(
            segment_id=segment_id,
            precipitation_mm=0.0,
            visibility_m=10000.0,
            condition="clear",
            observed_at=datetime.utcnow(),
            source="mock",
        )
    
    def get_provider_name(self) -> str:
        return "mock"
    
    def get_provider_status(self) -> ProviderStatus:
        return ProviderStatus()