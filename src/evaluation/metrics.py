"""Evaluation module for RailSentinel Person 1 — Data & Prediction Engine.

Provides MAE calculation, naive baseline prediction, chronological dataset
splitting, and percentage improvement over baseline.

All functions operate on supplied arrays/data — no fabricated metrics.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# MAE (Mean Absolute Error)
# ---------------------------------------------------------------------------

def mean_absolute_error_custom(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Compute mean absolute error between true and predicted values.

    Parameters
    ----------
    y_true : np.ndarray
        Ground truth values (delay in minutes).
    y_pred : np.ndarray
        Predicted values (delay in minutes).

    Returns
    -------
    float
        MAE in minutes.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if y_true.size == 0:
        return 0.0
    return float(np.mean(np.abs(y_true - y_pred)))


# ---------------------------------------------------------------------------
# Naive baseline prediction and MAE
# ---------------------------------------------------------------------------

def naive_last_known_prediction(y: np.ndarray) -> np.ndarray:
    """Produce naive baseline predictions using the last-known delay.

    The strategy: for all time steps after the first, predict the same value
    as the last observed delay. This is the simplest possible baseline for
    delay prediction.

    Parameters
    ----------
    y : np.ndarray
        Array of actual delays (shape: n_samples,).

    Returns
    -------
    np.ndarray
        Array of naive predictions (same value repeated for all but first entry).
    """
    y = np.asarray(y, dtype=float)
    if y.size <= 1:
        return y.copy()
    # First prediction is 0 (no prior delay known), rest are last known value
    predictions = np.empty_like(y, dtype=float)
    predictions[0] = 0.0
    if y.size > 1:
        predictions[1:] = y[-1]  # Always predict the last observed delay
    return predictions


def naive_baseline_mae(y_true: np.ndarray) -> float:
    """Compute the naive baseline MAE using the last-known-delay strategy.

    Parameters
    ----------
    y_true : np.ndarray
        Array of actual delay values.

    Returns
    -------
    float
        MAE of the naive last-known-delay baseline, in minutes.
    """
    y = np.asarray(y_true, dtype=float)
    if y.size == 0:
        return 0.0
    y_pred = naive_last_known_prediction(y)
    return mean_absolute_error_custom(y, y_pred)


# ---------------------------------------------------------------------------
# Percentage improvement over baseline
# ---------------------------------------------------------------------------

def percentage_improvement_ml_vs_baseline(ml_mae: float, baseline_mae: float) -> float:
    """Compute percentage improvement of ML model over naive baseline.

    Parameters
    ----------
    ml_mae : float
        MAE of the machine learning model.
    baseline_mae : float
        MAE of the naive baseline.

    Returns
    -------
    float
        Percentage improvement. Positive means the ML model is better.
        Formula: ((baseline_mae - ml_mae) / baseline_mae) * 100.
        Returns 0.0 if baseline_mae is 0 (division-safe).
    """
    baseline = float(baseline_mae)
    ml = float(ml_mae)
    if baseline == 0:
        return 0.0
    return float((baseline - ml) / baseline * 100.0)


# ---------------------------------------------------------------------------
# Chronological train/test split utility
# ---------------------------------------------------------------------------

def chronological_split(
    df: pd.DataFrame,
    date_col: str,
    train_ratio: float = 0.8,
    shuffle: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split a DataFrame into train and test sets preserving temporal order.

    The split is performed chronologically: earlier dates go to training,
    later dates go to testing. This respects the time-series nature of the
    data and avoids data leakage from random shuffling.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing the date column.
    date_col : str
        Column name containing datetime values used for ordering.
    train_ratio : float, optional
        Fraction of data to use for training (default: 0.8 = 80%).
    shuffle : bool, optional
        If ``True``, data is shuffled before splitting. Set to ``False``
        for pure chronological splitting (recommended for time series).

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame]
        (train_df, test_df) with temporal ordering preserved.

    Raises
    ------
    ValueError
        If ``date_col`` is not present in ``df``, or if ``train_ratio``
        is not in (0, 1).
    """
    if date_col not in df.columns:
        raise ValueError(f"Date column '{date_col}' not found in DataFrame")

    if not 0 < train_ratio < 1:
        raise ValueError(f"train_ratio must be in (0, 1); got {train_ratio}")

    # Make a copy to avoid modifying the original
    df_sorted = df.copy()

    # Ensure the date column is datetime
    df_sorted[date_col] = pd.to_datetime(df_sorted[date_col], errors="coerce")

    # Sort by date chronologically
    df_sorted = df_sorted.sort_values(by=date_col)

    # Determine split index
    n = len(df_sorted)
    train_size = int(n * train_ratio)

    if shuffle:
        # NOTE: For time-series, shuffle=True is generally NOT recommended.
        # This branch is provided for completeness but the recommended
        # usage is shuffle=False.
        df_shuffled = df_sorted.sample(frac=1, random_state=42).reset_index(drop=True)
        train_df = df_shuffled.iloc[:train_size]
        test_df = df_shuffled.iloc[train_size:]
    else:
        train_df = df_sorted.iloc[:train_size].reset_index(drop=True)
        test_df = df_sorted.iloc[train_size:].reset_index(drop=True)

    return train_df, test_df


# ---------------------------------------------------------------------------
# Time series split (TimeSeriesSplit-inspired utility)
# ---------------------------------------------------------------------------

def timeseries_split(
    df: pd.DataFrame,
    date_col: str,
    n_splits: int = 5,
    test_size: Optional[int] = None,
) -> list[Tuple[pd.DataFrame, pd.DataFrame]]:
    """Generate train/test splits for time series data.

    This is a simplified version of scikit-learn's TimeSeriesSplit that
    produces exactly ``n_splits`` splits with chronological ordering.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing the date column.
    date_col : str
        Column name containing datetime values used for ordering.
    n_splits : int, optional
        Number of splits (folds) to generate. Default: 5.
    test_size : int, optional
        Fixed size of the test set for each split. If ``None``, the test
        set grows progressively.

    Returns
    -------
    list[Tuple[pd.DataFrame, pd.DataFrame]]
        List of (train_df, test_df) tuples, each with temporal ordering
        preserved (train comes before test chronologically).
    """
    if date_col not in df.columns:
        raise ValueError(f"Date column '{date_col}' not found in DataFrame")

    n = len(df)
    if n_splits >= n:
        n_splits = max(1, n // 2)

    # Sort by date
    df_sorted = df.copy()
    df_sorted[date_col] = pd.to_datetime(df_sorted[date_col], errors="coerce")
    df_sorted = df_sorted.sort_values(by=date_col).reset_index(drop=True)

    splits: list[Tuple[pd.DataFrame, pd.DataFrame]] = []

    # Calculate split points
    if test_size is None:
        # Progressive test set: each split takes the next portion
        step = n // (n_splits + 1)
        if step < 1:
            step = 1
        test_start = step
    else:
        # Fixed test size
        step = test_size

    for i in range(n_splits):
        if test_size is None:
            # Progressive: train ends at test_start + i * step, test ends at next test_start
            train_end = test_start + i * step
            if i < n_splits - 1:
                test_end = test_start + (i + 1) * step
            else:
                test_end = n
            train_df = df_sorted.iloc[:train_end].reset_index(drop=True)
            test_df = df_sorted.iloc[train_end:test_end].reset_index(drop=True)
        else:
            # Fixed test size
            if i == 0:
                train_end = n - test_size
            else:
                train_end = (n - test_size) - (i - 1) * step  # Adjust for progressive
                if train_end < 1:
                    break
            train_df = df_sorted.iloc[:train_end].reset_index(drop=True)
            test_df = df_sorted.iloc[train_end:train_end + test_size].reset_index(drop=True)

        splits.append((train_df, test_df))

    # Ensure we have at least one split
    if not splits and n > 0:
        split_point = n // 2
        splits = [(df_sorted.iloc[:split_point].reset_index(drop=True),
                   df_sorted.iloc[split_point:].reset_index(drop=True))]

    return splits