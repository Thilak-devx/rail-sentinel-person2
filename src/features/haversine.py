"""Haversine distance implementation for railway station geolocation.

Person 1 -- Data & Prediction Engine.
Provides a real mathematical implementation of the haversine formula
for computing great-circle distances between two points on Earth.
"""

from __future__ import annotations

import math
from typing import Tuple


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the great-circle distance in kilometres between two points
    on the Earth given their longitudes and latitudes in decimal degrees.

    Parameters
    ----------
    lat1 : float
        Latitude of point 1 in decimal degrees.
    lon1 : float
        Longitude of point 1 in decimal degrees.
    lat2 : float
        Latitude of point 2 in decimal degrees.
    lon2 : float
        Longitude of point 2 in decimal degrees.

    Returns
    -------
    float
        Distance between the two points in kilometres.

    References
    ----------
    - https://en.wikipedia.org/wiki/Haversine_formula
    """
    # Validate input ranges
    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
        raise ValueError(f"Latitude values must be in [-90, 90]; got lat1={lat1}, lat2={lat2}")
    if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        raise ValueError(f"Longitude values must be in [-180, 180]; got lon1={lon1}, lon2={lon2}")

    # Convert decimal degrees to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    # Haversine formula
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    # Earth radius in kilometres (mean radius = 6371 km)
    earth_radius_km = 6371.0

    return earth_radius_km * c


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the great-circle distance in miles between two points
    on the Earth given their longitudes and latitudes in decimal degrees.

    Parameters
    ----------
    lat1, lon1, lat2, lon2 : float
        Decimal degree coordinates.

    Returns
    -------
    float
        Distance in miles.
    """
    km = haversine_km(lat1, lon1, lat2, lon2)
    return km * 0.621371


def batch_haversine_km(
    lats1: list[float], lons1: list[float], lats2: list[float], lons2: list[float]
) -> list[float]:
    """Compute haversine distances for multiple point pairs.

    Parameters
    ----------
    lats1, lons1 : list[float]
        Coordinates of the first set of points.
    lats2, lons2 : list[float]
        Coordinates of the second set of points.

    Returns
    -------
    list[float]
        Distances in kilometres for each pair.
    """
    return [
        haversine_km(lat1, lon1, lat2, lon2)
        for lat1, lon1, lat2, lon2 in zip(lats1, lons1, lats2, lons2)
    ]