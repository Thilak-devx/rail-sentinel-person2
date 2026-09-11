"""
CWC Flood Threshold Metadata for Verified Stations

Official source: CWC Flood Forecasting Network/Appraisal Report 2024.
Source: CWC Flood Forecasting Network/Appraisal Report 2024.
Data last updated: 2024.

These thresholds are from official CWC Flood Forecasting Network/Appraisal Report 2024.
Do NOT fabricate or modify these values.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class CWCStationThresholds:
    """Threshold metadata for a CWC flood forecast station."""
    station_name: str
    river: str
    warning_level_m: float
    danger_level_m: float
    highest_flood_level_m: float
    unit: str
    source: str
    source_year: int


# Verified CWC Station Thresholds (CWC Flood Forecasting Network/Appraisal Report 2024)
# These are the ONLY stations with verified thresholds. Do NOT add stations without official verification.

CWC_STATION_THRESHOLDS: Dict[str, CWCStationThresholds] = {
    "Rajghat": CWCStationThresholds(
        station_name="Rajghat",
        river="Subarnarekha",
        warning_level_m=9.45,
        danger_level_m=10.36,
        highest_flood_level_m=12.69,
        unit="m",
        source="CWC Flood Forecasting Network/Appraisal Report 2024",
        source_year=2024,
    ),
    "Anandpur": CWCStationThresholds(
        station_name="Anandpur",
        river="Baitarani",
        warning_level_m=37.44,
        danger_level_m=38.36,
        highest_flood_level_m=41.35,
        unit="m",
        source="CWC Flood Forecasting Network/Appraisal Report 2024",
        source_year=2024,
    ),
    "Akhuapada": CWCStationThresholds(
        station_name="Akhuapada",
        river="Baitarani",
        warning_level_m=17.83,
        danger_level_m=18.33,
        highest_flood_level_m=21.95,
        unit="m",
        source="CWC Flood Forecasting Network/Appraisal Report 2024",
        source_year=2024,
    ),
    "Jenapur": CWCStationThresholds(
        station_name="Jenapur",
        river="Brahmani",
        warning_level_m=22.00,
        danger_level_m=23.00,
        highest_flood_level_m=24.78,
        unit="m",
        source="CWC Flood Forecasting Network/Appraisal Report 2024",
        source_year=2024,
    ),
    "Alipingal": CWCStationThresholds(
        station_name="Alipingal",
        river="Mahanadi",
        warning_level_m=10.85,
        danger_level_m=11.76,
        highest_flood_level_m=13.11,
        unit="m",
        source="CWC Flood Forecasting Network/Appraisal Report 2024",
        source_year=2024,
    ),
    "Nimapara": CWCStationThresholds(
        station_name="Nimapara",
        river="Mahanadi",
        warning_level_m=9.85,
        danger_level_m=10.76,
        highest_flood_level_m=11.60,
        unit="m",
        source="CWC Flood Forecasting Network/Appraisal Report 2024",
        source_year=2024,
    ),
}

# Station name mapping from NWDP telemetry station names to CWC threshold station names
# This maps NWDP telemetry station names to CWC threshold station names
NWDP_TO_CWC_STATION_MAP: Dict[str, str] = {
    "Rajghat_1": "Rajghat",
    "Anandpur": "Anandpur",
    "Akhuapada": "Akhuapada",
    "Jenapur": "Jenapur",
    "Alipingal": "Alipingal",
    "Nimapara": "Nimapara",
}

# Station name to CWC station identifier (for threshold lookup)
CWC_STATION_NAMES = frozenset(CWC_STATION_THRESHOLDS.keys())

# Naraj is explicitly UNSUPPORTED - has CWC thresholds but no verified NWDP telemetry
# DO NOT add to this list
UNSUPPORTED_STATIONS = frozenset(["Naraj"])

def get_cwc_thresholds(station_name: str) -> Optional[CWCStationThresholds]:
    """Get CWC thresholds for a station by name."""
    cwc_name = NWDP_TO_CWC_STATION_MAP.get(station_name, station_name)
    return CWC_STATION_THRESHOLDS.get(cwc_name)

def is_supported_cwc_station(station_name: str) -> bool:
    """Check if a station has verified CWC thresholds."""
    cwc_name = NWDP_TO_CWC_STATION_MAP.get(station_name, station_name)
    return cwc_name in CWC_STATION_THRESHOLDS

def is_unsupported_station(station_name: str) -> bool:
    """Check if a station is explicitly unsupported (e.g., Naraj)."""
    return station_name in UNSUPPORTED_STATIONS