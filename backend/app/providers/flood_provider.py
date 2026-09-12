from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ProviderStatus:
    last_fetch_at: Optional[datetime] = None
    last_http_status: Optional[int] = None
    last_source: Optional[str] = None
    last_error: Optional[str] = None


@dataclass
class FloodObservation:
    segment_id: str
    water_level_m: Optional[float]
    warning_level_m: Optional[float]
    danger_level_m: Optional[float]
    status: str
    observed_at: datetime
    source: str
    raw_data: Optional[dict] = None


class FloodProvider(ABC):
    @abstractmethod
    async def get_flood_status(self, segment_id: str) -> FloodObservation:
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        pass
    
    @abstractmethod
    def get_provider_status(self) -> "ProviderStatus":
        pass


class MockFloodProvider:
    """Mock flood provider for testing and development."""
    
    def __init__(self):
        self._demo_flood = {
            "SEG_01": FloodObservation(
                segment_id="SEG_01",
                water_level_m=5.0,
                warning_level_m=8.0,
                danger_level_m=10.0,
                status="normal",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
            "SEG_02": FloodObservation(
                segment_id="SEG_02",
                water_level_m=9.0,
                warning_level_m=8.0,
                danger_level_m=10.0,
                status="warning",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
            "SEG_03": FloodObservation(
                segment_id="SEG_03",
                water_level_m=10.5,
                warning_level_m=8.0,
                danger_level_m=10.0,
                status="danger",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
            "SEG_04": FloodObservation(
                segment_id="SEG_04",
                water_level_m=7.5,
                warning_level_m=8.0,
                danger_level_m=10.0,
                status="normal",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
            # Additional segments for testing specific risk scenarios
            "SEG_LOW_RAIN": FloodObservation(
                segment_id="SEG_LOW_RAIN",
                water_level_m=5.0,
                warning_level_m=8.0,
                danger_level_m=10.0,
                status="normal",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
            "SEG_LOW_FOG": FloodObservation(
                segment_id="SEG_LOW_FOG",
                water_level_m=5.0,
                warning_level_m=8.0,
                danger_level_m=10.0,
                status="normal",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
            "SEG_MODERATE_FLOOD": FloodObservation(
                segment_id="SEG_MODERATE_FLOOD",
                water_level_m=9.0,
                warning_level_m=8.0,
                danger_level_m=10.0,
                status="warning",
                observed_at=datetime(2026, 9, 6, 18, 30, 0),
                source="mock",
            ),
        }
    
    async def get_flood_status(self, segment_id: str) -> "FloodObservation":
        return self._demo_flood.get(
            segment_id,
            FloodObservation(
                segment_id=segment_id,
                water_level_m=None,
                warning_level_m=None,
                danger_level_m=None,
                status="unknown",
                observed_at=datetime.utcnow(),
                source="mock",
            )
        )
    
    def get_provider_name(self) -> str:
        return "mock"
    
    def get_provider_status(self) -> "ProviderStatus":
        from app.providers.flood_provider import ProviderStatus
        return ProviderStatus()


def create_flood_provider():
    """Factory function to create the appropriate FloodProvider based on configuration."""
    from app.core.config import settings
    
    if settings.flood_provider == "cwc":
        from app.providers.cwc_provider import CWCProvider
        return CWCProvider(freshness_threshold_seconds=settings.cwc_max_age_seconds)
    else:
        return MockFloodProvider()


# Lazy import for CWCProvider (avoids circular import at module level)
def __getattr__(name: str):
    if name == "CWCProvider":
        from app.providers.cwc_provider import CWCProvider
        return CWCProvider
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "ProviderStatus",
    "FloodObservation",
    "FloodProvider",
    "MockFloodProvider",
    "CWCProvider",
    "create_flood_provider",
]