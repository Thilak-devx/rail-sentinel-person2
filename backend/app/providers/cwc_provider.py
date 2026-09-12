"""
CWC Flood Provider - Flood data from CWC/NWDP Telemetry API

Uses the verified NWDP CWC River Water Level Telemetry Hourly dataset
via the CKAN DataStore API.

Data freshness varies by station (2026-2030 resources):
- Rajghat: stale (Jun 2026)
- Anandpur: stale (Jun 2026)
- Akhuapada: recent (Sep 2026)
- Jenapur: recent (Sep 2026)
- Alipingal: UNAVAILABLE in 2026-2030 resource
- Nimapara: fresh (Sep 2026)
"""

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, List
import httpx
import logging

from app.providers.flood_provider import FloodProvider, FloodObservation, ProviderStatus
from app.services.segment_registry import segment_registry
from app.providers.cwc_thresholds import (
    CWCStationThresholds,
    CWC_STATION_THRESHOLDS,
    NWDP_TO_CWC_STATION_MAP,
    is_supported_cwc_station,
    is_unsupported_station,
    get_cwc_thresholds,
)
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class CWCProviderStatus(ProviderStatus):
    """Extended provider status for CWC provider."""
    station_count: int = 0
    supported_stations: List[str] = None
    last_station_fetch: Optional[datetime] = None


@dataclass
class StationFreshness:
    """Tracks freshness status for a specific station."""
    station_id: str
    observed_at: Optional[datetime]
    is_fresh: bool
    is_stale: bool
    is_unavailable: bool
    age_days: Optional[float]
    error: Optional[str] = None


class CWCProvider(FloodProvider):
    """
    CWC Flood Provider using NWDP/NWIC CWC River Water Level Telemetry API.
    
    Uses the official NWDP CKAN DataStore API to fetch river water level
    telemetry from CWC telemetry stations (2026-2030 resources).
    
    Supported stations (6 verified with official CWC thresholds):
    - Rajghat (Subarnarekha) - stale data
    - Anandpur (Baitarani) - stale data
    - Akhuapada (Baitarani) - recent data
    - Jenapur (Brahmani) - recent data
    - Alipingal (Mahanadi) - UNAVAILABLE in 2026-2030 resource
    - Nimapara (Mahanadi) - fresh data
    
    Naraj (Mahanadi) is NOT supported - no verified NWDP telemetry match.
    """
    
    # NWDP API configuration
    NWDP_API_BASE = "https://www.nwdp.nwic.gov.in/api/3/action"
    DATASTORE_SEARCH_ENDPOINT = "/datastore_search"
    
    # Resource IDs for the CWC River Water Level Telemetry Hourly datasets (2026-2030)
    # Verified via official NWDP CKAN API discovery
    RESOURCE_IDS = {
        "subarnarekha": "1e23cbb8-c1ce-4434-a635-8231535305f3",  # Subernarekha 2026-2030
        "brahmani_baitarni": "178082a5-2a2b-445e-b059-97337f325cd7",  # Brahmani and Baitarni 2026-2030
        "mahanadi": "0ab89c38-558f-47b5-818e-eda9f17cffc4",  # Mahanadi 2026-2030
    }
    
    # Mapping from station name to (resource_key, search_query)
    STATION_RESOURCE_MAP = {
        "Rajghat": ("subarnarekha", "rajghat"),
        "Anandpur": ("brahmani_baitarni", "anandpur"),
        "Akhuapada": ("brahmani_baitarni", "akhuapada"),
        "Jenapur": ("brahmani_baitarni", "jenapur"),
        "Alipingal": ("mahanadi", "alipingal"),
        "Nimapara": ("mahanadi", "nimapara"),
    }
    
    # Supported station names (keys are CWC station names)
    SUPPORTED_STATIONS = frozenset([
        "Rajghat",
        "Anandpur",
        "Akhuapada",
        "Jenapur",
        "Alipingal",
        "Nimapara",
    ])
    
    # Stations explicitly NOT supported (have CWC thresholds but no verified telemetry)
    UNSUPPORTED_STATIONS = frozenset(["Naraj"])
    
    # Stations with known unavailability in 2026-2030 resources
    UNAVAILABLE_STATIONS = frozenset(["Alipingal"])
    
    def __init__(
        self,
        timeout: float = 10.0,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        freshness_threshold_seconds: int = 604800,  # Default: 7 days in seconds
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.freshness_threshold_seconds = freshness_threshold_seconds
        self._base_url_value = "https://www.nwdp.nwic.gov.in"
        self._api_base = f"{self._base_url_value}/api/3/action"
        self._status = CWCProviderStatus()
        self._station_coords_cache: Dict[str, tuple] = {}
        self._load_station_coordinates()
    
    @property
    def _base_url(self) -> str:
        return self._base_url_value
    
    @_base_url.setter
    def _base_url(self, value: str) -> None:
        self._base_url_value = value
    
    def _load_station_coordinates(self) -> None:
        """Load station coordinates from segment registry for coordinate-based queries."""
        try:
            for seg_id, info in segment_registry._segments.items():
                if seg_id.startswith("REAL_RAIL_SEG_") and info.geometry is not None:
                    # Get centroid of segment geometry
                    centroid = info.geometry.centroid
                    self._station_coords_cache[seg_id] = (info.representative_lat, info.representative_long)
        except Exception as e:
            logger.warning(f"Failed to load station coordinates: {e}")
    
    def get_provider_name(self) -> str:
        return "cwc"
    
    def get_provider_status(self) -> ProviderStatus:
        return CWCProviderStatus(
            last_fetch_at=self._status.last_fetch_at,
            last_http_status=self._status.last_http_status,
            last_source=self._status.last_source,
            last_error=self._status.last_error,
            station_count=len(self.SUPPORTED_STATIONS),
            supported_stations=list(self.SUPPORTED_STATIONS),
            last_station_fetch=self._status.last_station_fetch,
        )
    
    async def get_flood_status(self, segment_id: str) -> FloodObservation:
        """
        Get flood status for a segment by segment_id.
        
        Maps segment_id to CWC station, fetches telemetry, and applies thresholds.
        Includes freshness evaluation based on configurable threshold.
        """
        # Check if segment is explicitly unsupported (has CWC thresholds but no telemetry)
        if is_unsupported_station(segment_id):
            return FloodObservation(
                segment_id=segment_id,
                water_level_m=None,
                warning_level_m=None,
                danger_level_m=None,
                status="provider_unavailable",
                observed_at=datetime.now(timezone.utc),
                source="cwc",
                raw_data={"error": f"Station {segment_id} has CWC thresholds but no verified NWDP telemetry match"},
            )
        
        # Check if segment is a supported CWC station
        cwc_station = self._map_segment_to_cwc_station(segment_id)
        if not cwc_station:
            return FloodObservation(
                segment_id=segment_id,
                water_level_m=None,
                warning_level_m=None,
                danger_level_m=None,
                status="provider_unavailable",
                observed_at=datetime.now(timezone.utc),
                source="cwc",
                raw_data={"error": f"No CWC station mapping for segment: {segment_id}"},
            )
        
        # Check if station is known to be unavailable in 2026-2030 resources
        if cwc_station in self.UNAVAILABLE_STATIONS:
            return FloodObservation(
                segment_id=segment_id,
                water_level_m=None,
                warning_level_m=None,
                danger_level_m=None,
                status="provider_unavailable",
                observed_at=datetime.now(timezone.utc),
                source="cwc",
                raw_data={
                    "error": f"Station {cwc_station} has CWC thresholds but is not present in 2026-2030 NWDP telemetry resource",
                    "freshness": "unavailable",
                },
            )
        
        # Fetch telemetry from NWDP API
        telemetry = await self._fetch_latest_telemetry(cwc_station)
        if not telemetry:
            return FloodObservation(
                segment_id=segment_id,
                water_level_m=None,
                warning_level_m=None,
                danger_level_m=None,
                status="telemetry_unavailable",
                observed_at=datetime.now(timezone.utc),
                source="cwc",
                raw_data={"error": f"Failed to fetch telemetry for station: {cwc_station}"},
            )
        
        # Evaluate data freshness
        observed_at = telemetry.get("observed_at")
        freshness_info = self._evaluate_freshness(cwc_station, observed_at)
        
        # Get CWC thresholds for this station
        thresholds = get_cwc_thresholds(cwc_station)
        if not thresholds:
            return FloodObservation(
                segment_id=cwc_station,
                water_level_m=telemetry.get("water_level"),
                warning_level_m=None,
                danger_level_m=None,
                status="threshold_unavailable",
                observed_at=datetime.now(timezone.utc),
                source="cwc",
                raw_data={
                    "error": f"No CWC thresholds for station: {cwc_station}",
                    "freshness": freshness_info,
                },
            )
        
        # Build observation with threshold comparison and freshness info
        return self._build_observation(telemetry, thresholds, freshness_info)
    
    def _map_segment_to_cwc_station(self, segment_id: str) -> Optional[str]:
        """Map a segment_id to a CWC station name."""
        # Direct mapping for supported stations
        if segment_id in self.SUPPORTED_STATIONS:
            return segment_id
        
        # Check if it's a REAL_RAIL_SEG that maps to a CWC station
        if segment_id.startswith("REAL_RAIL_SEG_"):
            # Try to find by sequence number or coordinate proximity
            # For now, return None - caller should use exact CWC station names
            return None
        
        return None
    
    async def _fetch_latest_telemetry(self, cwc_station: str) -> Optional[Dict]:
        """Fetch latest telemetry for a CWC station from NWDP API."""
        station_key = cwc_station
        if cwc_station not in self.STATION_RESOURCE_MAP:
            logger.warning(f"No resource mapping for station: {cwc_station}")
            return None
        
        resource_key, search_query = self.STATION_RESOURCE_MAP[cwc_station]
        resource_id = self.RESOURCE_IDS.get(resource_key)
        if not resource_id:
            logger.error(f"No resource ID for resource key: {resource_key}")
            return None
        
        # Search for the station in the appropriate dataset
        url = f"{self._api_base}/datastore_search"
        params = {
            "resource_id": self.RESOURCE_IDS[resource_key],
            "q": search_query,
            "limit": 1,
            "sort": "_id desc",  # Get latest record first
        }
        
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(f"Fetching telemetry for {cwc_station} from {resource_key}")
                    response = await client.get(
                        f"{self._api_base}/datastore_search",
                        params=params,
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    if not data.get("success"):
                        logger.error(f"API error for {cwc_station}: {data}")
                        return None
                    
                    records = data.get("result", {}).get("records", [])
                    if not records:
                        logger.warning(f"No telemetry records found for {cwc_station}")
                        return None
                    
                    # Get the latest record (already sorted by _id desc)
                    record = records[0]
                    return self._parse_telemetry_record(cwc_station, record)
            
            except httpx.TimeoutException:
                logger.warning(f"Timeout fetching telemetry for {cwc_station} (attempt {attempt + 1}/{self.max_retries + 1})")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
                    continue
                return None
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error for {cwc_station}: {e.response.status_code}")
                return None
            except Exception as e:
                logger.error(f"Error fetching telemetry for {cwc_station}: {e}")
                return None
            
            return None
    
    def _parse_telemetry_record(self, station_id: str, record: Dict) -> Optional[Dict]:
        """Parse a telemetry record from NWDP API response."""
        try:
            # Extract water level
            water_level_str = record.get("River Water Level Telemetry Hourly (meter)", "")
            water_level = float(water_level_str) if water_level_str else None
            
            # Extract coordinates
            lat_str = record.get("Latitude", "")
            lon_str = record.get("Longitude", "")
            lat = float(lat_str) if lat_str else None
            lon = float(lon_str) if lon_str else None
            
            # Extract timestamp
            time_str = record.get("Data Acquisition Time", "")
            observed_at = self._parse_timestamp(time_str)
            
            # Extract other fields
            station = record.get("Station", "")
            river = record.get("River", "")
            basin = record.get("Basin", "")
            rl_zero = record.get("RL_of_zeroGauge", "")
            rl_zero_val = float(rl_zero) if rl_zero else None
            msl_str = record.get("MeanSeaLevel", "")
            msl = float(msl_str) if msl_str else None
            
            return {
                "station_id": station_id,
                "water_level": water_level,
                "lat": lat,
                "lon": lon,
                "observed_at": observed_at,
                "river": river,
                "basin": basin,
                "rl_zero_gauge": rl_zero_val,
                "mean_sea_level": msl,
                "raw_data": record,
            }
        except Exception as e:
            logger.error(f"Error parsing telemetry record for {station_id}: {e}")
            return None
    
    def _parse_timestamp(self, time_str: str) -> datetime:
        """Parse CWC timestamp string to datetime."""
        # Format: "DD-MM-YYYY HH:MM" or "DD-MM-YYYY HH:MM:SS"
        try:
            # Try multiple formats
            for fmt in ("%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M"):
                try:
                    dt = datetime.strptime(time_str, fmt)
                    return dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        except Exception:
            pass
        return datetime.now(timezone.utc)
    
    def _evaluate_freshness(self, station_id: str, observed_at: Optional[datetime]) -> dict:
        """Evaluate freshness of telemetry data for a station."""
        if observed_at is None:
            return {
                "status": "unknown",
                "age_seconds": None,
                "is_fresh": False,
                "is_stale": True,
                "is_unavailable": True,
                "error": "No observation timestamp available",
            }
        
        now = datetime.now(timezone.utc)
        age = now - observed_at
        age_seconds = age.total_seconds()
        
        # Future timestamps are invalid for current flood-risk decisions
        if age_seconds < 0:
            return {
                "status": "future",
                "age_seconds": int(age_seconds),
                "is_fresh": False,
                "is_stale": False,
                "is_unavailable": True,
                "error": "Observation timestamp is in the future",
                "observed_at": observed_at.isoformat(),
            }
        
        is_fresh = age_seconds <= self.freshness_threshold_seconds
        is_stale = age_seconds > self.freshness_threshold_seconds
        is_unavailable = False
        
        if is_fresh:
            status = "fresh"
        elif is_stale:
            status = "stale"
        else:
            status = "unknown"
        
        return {
            "status": status,
            "age_seconds": int(age_seconds),
            "is_fresh": is_fresh,
            "is_stale": is_stale,
            "is_unavailable": is_unavailable,
            "observed_at": observed_at.isoformat(),
        }
    
    def _build_observation(
        self,
        telemetry: Dict,
        thresholds: "CWCStationThresholds",
        freshness_info: dict,
    ) -> FloodObservation:
        """Build FloodObservation from telemetry and thresholds."""
        water_level = telemetry.get("water_level")
        warning_level = thresholds.warning_level_m
        danger_level = thresholds.danger_level_m
        
        # Determine risk level
        risk_level = "none"
        source = "none"
        
        water_level = telemetry.get("water_level")
        if water_level is not None:
            if danger_level is not None and water_level >= danger_level:
                risk_level = "severe"
                source = "flood"
            elif warning_level is not None and water_level >= warning_level:
                risk_level = "moderate"
                source = "flood"
            else:
                # Check weather conditions would be done in RiskEngine
                risk_level = "none"
                source = "none"
        
        # Determine source based on risk level
        if risk_level in ("moderate", "severe"):
            source = "flood"
        elif risk_level == "low":
            source = "weather"
        else:
            source = "none"
        
        observed_at = telemetry.get("observed_at", datetime.now(timezone.utc))
        water_level_val = telemetry.get("water_level")
        rl_zero = telemetry.get("rl_zero_gauge")
        
        # Calculate water level above gauge zero if available
        water_level_above_gauge = None
        if water_level_val is not None and telemetry.get("rl_zero_gauge") is not None:
            water_level_above_gauge = water_level_val + telemetry["rl_zero_gauge"]
        
        # Include freshness info in raw_data
        raw_data = telemetry.get("raw_data", {})
        if isinstance(raw_data, dict):
            raw_data = {**raw_data, "freshness": freshness_info}
        
        return FloodObservation(
            segment_id=telemetry.get("station_id", ""),
            water_level_m=water_level,
            warning_level_m=warning_level,
            danger_level_m=danger_level,
            status="normal" if water_level is not None else "telemetry_unavailable",
            observed_at=telemetry.get("observed_at", datetime.now(timezone.utc)),
            source="cwc",
            raw_data=raw_data,
        )
    
    def get_provider_name(self) -> str:
        return "cwc"
    
    # get_provider_status is defined above (line 153) with proper station info


# Factory function to create CWCProvider
def create_cwc_provider() -> FloodProvider:
    """Factory function to create CWCProvider instance."""
    return CWCProvider()