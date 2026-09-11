"""Feature engineering module for RailSentinel Person 1.

Provides clearly separated functions for the features specified in the
requirements:
- current delay at last station
- distance to next station
- real station latitude/longitude with haversine distance
- historical average delay for the section
- day of week
- time-of-day bucket
- weather flag
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import numpy as np

from src.features.haversine import haversine_km


# ---------------------------------------------------------------------------
# Current delay
# ---------------------------------------------------------------------------

def extract_current_delay(df: pd.DataFrame, delay_col: str = "delay_minutes") -> pd.Series:
    """Extract the current delay at the last known station.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing delay observations, must have a ``delay_col``
        column with numeric delay values.
    delay_col : str, optional
        Name of the column containing delay in minutes. Default: ``"delay_minutes"``.

    Returns
    -------
    pd.Series
        Series of current delays indexed by observation order.
    """
    if delay_col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[delay_col], errors="coerce")


# ---------------------------------------------------------------------------
# Distance to next station (haversine)
# ---------------------------------------------------------------------------

def compute_next_station_distance_km(
    df: pd.DataFrame,
    lat_col: str = "station_lat",
    lon_col: str = "station_lon",
    next_lat_col: str = "next_station_lat",
    next_lon_col: str = "next_station_lon",
) -> pd.Series:
    """Compute haversine distance from each station to the next station.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with station and next-station coordinates.
    lat_col : str, optional
        Column name for current station latitude.
    lon_col : str, optional
        Column name for current station longitude.
    next_lat_col : str, optional
        Column name for next station latitude.
    next_lon_col : str, optional
        Column name for next station longitude.

    Returns
    -------
    pd.Series
        Distance in kilometres to the next station.
    """
    lats = df[lat_col].astype(float).values
    lons = df[lon_col].astype(float).values
    next_lats = df[next_lat_col].astype(float).values
    next_lons = df[next_lon_col].astype(float).values

    return pd.Series(
        haversine_km(lats, lons, next_lats, next_lons),
        index=df.index,
    )


# ---------------------------------------------------------------------------
# Historical average delay for the section
# ---------------------------------------------------------------------------

def compute_historical_section_average_delay(
    df: pd.DataFrame,
    section_id_col: str = "section_id",
    delay_col: str = "delay_minutes",
) -> pd.Series:
    """Compute historical average delay for each section.

    A "section" is identified by ``section_id`` (e.g. pair of consecutive
    stations). The function returns the mean delay observed for that section
    across all historical records.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with section identifiers and delay values.
    section_id_col : str, optional
        Column naming the section (e.g. ``"section_id"`).
    delay_col : str, optional
        Column containing delay in minutes.

    Returns
    -------
    pd.Series
        Historical average delay per section, indexed by section_id.
    """
    if section_id_col not in df.columns or delay_col not in df.columns:
        return pd.Series(dtype=float, index=df.index)

    # Group by section and compute mean delay
    section_means = df.groupby(section_id_col)[delay_col].mean()

    # Map back to each row
    return df[section_id_col].map(section_means)


# ---------------------------------------------------------------------------
# Day of week
# ---------------------------------------------------------------------------

def extract_day_of_week(df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.Series:
    """Extract day-of-week (0=Monday, 6=Sunday) from a timestamp column.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing a timestamp column.
    timestamp_col : str, optional
        Column name containing datetime or timestamp strings.

    Returns
    -------
    pd.Series
        Integer day-of-week values (0=Monday, 6=Sunday).
    """
    if timestamp_col not in df.columns:
        return pd.Series(dtype=int, index=df.index)

    # Try parsing the timestamp
    series = pd.to_datetime(df[timestamp_col], errors="coerce", utc=False)
    return series.dt.dayofweek


# ---------------------------------------------------------------------------
# Time-of-day bucket
# ---------------------------------------------------------------------------

def extract_time_of_day_bucket(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    bucket_count: int = 4,
) -> pd.Series:
    """Extract time-of-day bucket from a timestamp column.

    Divides the 24-hour day into ``bucket_count`` equal intervals and
    returns the bucket index (0 to bucket_count-1).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing a timestamp column.
    timestamp_col : str, optional
        Column name containing datetime or timestamp strings.
    bucket_count : int, optional
        Number of time buckets. Default: 4 (0=0-6, 1=6-12, 2=12-18, 3=18-24).

    Returns
    -------
    pd.Series
        Bucket index for each row.
    """
    if timestamp_col not in df.columns:
        return pd.Series(dtype=int, index=df.index)

    series = pd.to_datetime(df[timestamp_col], errors="coerce", utc=False)
    hour = series.dt.hour

    # Divide 24 hours into bucket_count equal intervals
    interval = 24 / bucket_count
    buckets = (hour / interval).astype(int)

    # Cap at bucket_count - 1 for the last hour (23)
    buckets = buckets.clip(upper=bucket_count - 1)

    return buckets


# ---------------------------------------------------------------------------
# Weather flag
# ---------------------------------------------------------------------------

def compute_weather_flag(
    df: pd.DataFrame,
    weather_col: str = "weather_condition",
    bad_conditions: Optional[list[str]] = None,
) -> pd.Series:
    """Compute a binary weather flag indicating adverse conditions.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame potentially containing weather information.
    weather_col : str, optional
        Column name with weather condition descriptions.
    bad_conditions : list[str], optional
        List of weather conditions considered adverse.
        Defaults to common rain/fog/snow values.

    Returns
    -------
    pd.Series
        Binary (0/1) series where 1 indicates adverse weather.
    """
    if bad_conditions is None:
        bad_conditions = ["rain", "drizzle", "fog", "smoke", "snow", "storm"]

    if weather_col not in df.columns:
        return pd.Series(dtype=int, index=df.index)

    weather_lower = df[weather_col].astype(str).str.lower()
    flag = weather_lower.apply(lambda x: 1 if any(cond in x for cond in bad_conditions) else 0)

    return pd.Series(flag, index=df.index, dtype=int)


# ---------------------------------------------------------------------------
# Feature assembly
# ---------------------------------------------------------------------------

def assemble_features(
    df: pd.DataFrame,
    **kwargs: Any,
) -> pd.DataFrame:
    """Assemble all engineered features into a single DataFrame.

    This is a convenience function that calls each feature function and
    concatenates the results into a DataFrame ready for model input.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with required columns.
    **kwargs : dict
        Additional keyword arguments passed to individual feature functions.

    Returns
    -------
    pd.DataFrame
        DataFrame with engineered features added.
    """
    features: Dict[str, pd.Series] = {}

    # Current delay
    if "delay_minutes" in df.columns:
        features["current_delay"] = extract_current_delay(df, "delay_minutes")
    else:
        features["current_delay"] = pd.Series(dtype=float, index=df.index)

    # Haversine distance to next station (requires lat/lon columns)
    if {"station_lat", "station_lon", "next_station_lat", "next_station_lon"}.issubset(df.columns):
        features["distance_to_next_km"] = compute_next_station_distance_km(df)
    else:
        features["distance_to_next_km"] = pd.Series(dtype=float, index=df.index)

    # Historical section average delay
    # section_id would need to be computed or present in the DataFrame
    features["historical_section_avg_delay"] = compute_historical_section_average_delay(df)

    # Day of week
    features["day_of_week"] = extract_day_of_week(df)

    # Time-of-day bucket
    features["time_of_day_bucket"] = extract_time_of_day_bucket(df)

    # Weather flag
    features["weather_flag"] = compute_weather_flag(df)

    # Convert all series to DataFrame and join
    features_df = pd.DataFrame(features, index=df.index)

    return features_df