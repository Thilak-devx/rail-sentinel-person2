"""Haversine distance and batch utility for railway station geolocation.

Person 1 -- Data & Prediction Engine.
Implements the haversine formula for computing great-circle distances
between two points on Earth given their longitudes and latitudes.
"""

from __future__ import annotations

from .haversine import haversine_km, haversine_mi, batch_haversine_km