"""Chronological split and time-series utilities for RailSentinel.

Person 1 -- Data & Prediction Engine.
Provides train/test splitting functions that preserve temporal ordering,
avoiding data leakage from random shuffling of time-series data.
"""

from __future__ import annotations

from typing import List, Tuple

import pandas as pd


def chronological_split(
    df: pd.DataFrame,
    date_col: str,
    train_ratio: float = 0.8,
    shuffle: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Split a DataFrame into train and test sets preserving temporal order.

    Earlier dates go to training; later dates go to testing.
    Set shuffle=False (recommended for time series) to avoid data leakage.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing the date column.
    date_col : str
        Column name containing datetime values used for ordering.
    train_ratio : float, optional
        Fraction of data to use for training (default: 0.8 = 80%).
    shuffle : bool, optional
        If True, data is shuffled before splitting. Set to False for
        pure chronological splitting (recommended for time series).

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame]
        (train_df, test_df) with temporal ordering preserved.
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
        df_shuffled = df_sorted.sample(frac=1, random_state=42).reset_index(drop=True)
        train_df = df_shuffled.iloc[:train_size]
        test_df = df_shuffled.iloc[train_size:]
    else:
        train_df = df_sorted.iloc[:train_size].reset_index(drop=True)
        test_df = df_sorted.iloc[train_size:].reset_index(drop=True)

    return train_df, test_df


def timeseries_split(
    df: pd.DataFrame,
    date_col: str,
    n_splits: int = 5,
    test_size: int = None,
) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
    """Generate train/test splits for time series data.

    This produces exactly n_splits splits with chronological ordering.
    Each split has train data preceding test data chronologically.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing the date column.
    date_col : str
        Column name containing datetime values used for ordering.
    n_splits : int, optional
        Number of splits (folds) to generate. Default: 5.
    test_size : int, optional
        Fixed size of the test set for each split. If None, test set
        grows progressively.

    Returns
    -------
    List[Tuple[pd.DataFrame, pd.DataFrame]]
        List of (train_df, test_df) tuples with temporal ordering preserved.
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

    splits: List[Tuple[pd.DataFrame, pd.DataFrame]] = []

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