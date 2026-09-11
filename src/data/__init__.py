"""Data module for RailSentinel Person 1 — Data & Prediction Engine.

Provides interfaces for loading, validating, and cleaning railway schedule data
and delay observations.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Column mapping configuration — eventually driven by the real Kaggle dataset
# ---------------------------------------------------------------------------

# Placeholder mapping: eventual column names from the Kaggle dataset
# will be mapped to internal canonical names via this dictionary.
# This keeps the rest of the pipeline agnostic to Kaggle-specific names.
COLUMN_MAPPING: Dict[str, str] = {
    # Example format (will be updated after dataset inspection):
    # "train_no": "train_number",
    # "station_name": "station",
    # "sch_time": "scheduled_time",
    # "act_time": "actual_time",
    # "delay": "delay_minutes",
}


def load_raw_schedule(data_dir: Optional[Path] = None) -> pd.DataFrame:
    """Load raw railway schedule data from the data directory.

    Parameters
    ----------
    data_dir : Path, optional
        Base data directory. Defaults to project-relative ``data/raw``.

    Returns
    -------
    pd.DataFrame
        Raw schedule data, or empty DataFrame if no files found.
    """
    from app.config import get_settings

    if data_dir is None:
        settings = get_settings()
        data_dir = Path(settings["raw_data_dir"])

    if not data_dir.is_dir():
        logger.warning("Raw data directory not found: %s", data_dir)
        return pd.DataFrame()

    # Load all CSV files found in the raw data directory
    frames: List[pd.DataFrame] = []
    for csv_file in sorted(data_dir.glob("*.csv")):
        try:
            df = pd.read_csv(csv_file, dtype=str)
            frames.append(df)
            logger.info("Loaded raw schedule from %s", csv_file.name)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to load %s: %s", csv_file.name, exc)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def validate_schedule_df(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Validate that a schedule DataFrame contains required columns.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to validate.
    returns
    -------
    Tuple[bool, List[str]]
        ``(is_valid, missing_columns)``.  If ``is_valid`` is ``True``,
        ``missing_columns`` is empty.
    """
    required_columns = {"train_number", "station", "scheduled_time", "actual_time"}
    missing = required_columns - set(df.columns)
    is_valid = len(missing) == 0
    return is_valid, list(missing)


def clean_schedule_df(df: pd.DataFrame) -> pd.DataFrame:
    """Clean raw schedule DataFrame.

    Performs basic cleaning: trims whitespace, converts time columns to
    standardized string format, computes raw delay where possible.

    Parameters
    ----------
    df : pd.DataFrame
        Raw schedule DataFrame.

    Returns
    -------
    pd.DataFrame
        Cleaned DataFrame with standardized columns.
    """
    if df.empty:
        return df

    # Trim whitespace from string columns
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()

    # Ensure key columns exist
    key_cols = {"train_number", "station", "scheduled_time", "actual_time"}
    missing = key_cols - set(df.columns)
    for col in missing:
        # Initialise missing key columns as empty strings
        df[col] = ""

    # Standardise time column format - keep as string for now, ISO preferred
    for time_col in ["scheduled_time", "actual_time"]:
        if time_col in df.columns:
            # Ensure they are strings
            df[time_col] = df[time_col].astype(str)

    # Compute raw delay in minutes if both times are present
    if "scheduled_time" in df.columns and "actual_time" in df.columns:
        df["delay_minutes"] = df.apply(
            lambda row: _compute_delay_minutes(row["scheduled_time"], row["actual_time"]),
            axis=1,
        )

    logger.info("Cleaned schedule DataFrame: %d rows", len(df))
    return df


def _compute_delay_minutes(scheduled: str, actual: str) -> float:
    """Compute delay in minutes from scheduled and actual time strings.

    This is a best-effort helper. Exact parsing depends on the data format
    and will be refined after the real Kaggle dataset is inspected.

    Parameters
    ----------
    scheduled : str
        Scheduled time.
    actual : str
        Actual time.

    Returns
    -------
    float
        Delay in minutes (positive = delayed, negative = early). Returns 0.0
        if times cannot be parsed.
    """
    # Placeholder: return 0.0 until proper time-format parsing is defined
    # after the real dataset is available.
    try:
        # Very naive attempt - will be replaced
        return 0.0
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Delay observation loading
# ---------------------------------------------------------------------------

def load_delay_observations(data_dir: Optional[Path] = None) -> pd.DataFrame:
    """Load delay observations from the data directory.

    Eventually this will read from runningstatus.in scraped data or the
    Kaggle dataset. For now returns an empty DataFrame with the expected
    column schema.

    Parameters
    ----------
    data_dir : Path, optional
        Base data directory.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: train_number, station, scheduled_time,
        actual_time, delay_minutes, observation_timestamp.
    """
    from app.config import get_settings

    if data_dir is None:
        settings = get_settings()
        data_dir = Path(settings["external_data_dir"])

    # Placeholder: return empty DataFrame with expected columns
    columns = ["train_number", "station", "scheduled_time", "actual_time", "delay_minutes", "observation_timestamp"]
    df = pd.DataFrame(columns=columns)
    logger.info("Returning empty delay observations DataFrame (no data source configured yet)")
    return df


def combine_route_and_delay(
    route_df: pd.DataFrame,
    delay_df: pd.DataFrame,
    on: str = "train_number",
    station_col: str = "station",
) -> pd.DataFrame:
    """Combine route schedule data with delay observations.

    Performs a left join of delay observations onto the route schedule,
    preserving all route entries and adding delay information where available.

    Parameters
    ----------
    route_df : pd.DataFrame
        Route schedule DataFrame (from load_raw_schedule).
    delay_df : pd.DataFrame
        Delay observations DataFrame (from load_delay_observations).
    on : str, optional
        Column to join on (default: ``train_number``).
    station_col : str, optional
        Column name for station in both DataFrames (default: ``station``).

    Returns
    -------
    pd.DataFrame
        Combined DataFrame with route + delay columns.
    """
    if route_df.empty:
        logger.warning("Route DataFrame is empty; returning delay DataFrame as-is")
        return delay_df

    if delay_df.empty:
        logger.warning("Delay DataFrame is empty; returning route DataFrame as-is")
        return route_df

    # Ensure station column exists in both
    if station_col not in route_df.columns:
        route_df[station_col] = ""
    if station_col not in delay_df.columns:
        delay_df[station_col] = ""

    # Left join: all rows from route, matching delay where available
    combined = route_df.merge(
        delay_df,
        how="left",
        left_on=[on, station_col],
        right_on=[on, station_col],
        suffixes=("", "_obs"),
    )

    logger.info("Combined route and delay: %d rows", len(combined))
    return combined