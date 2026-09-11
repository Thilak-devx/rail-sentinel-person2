"""ETA Prediction Engine — wraps the XGBoost v2 model.

Loaded once at import; safe to call from the broadcast loop every second.
Falls back gracefully (returns None) when xgboost or the model file are
unavailable so the rest of the backend keeps running.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "xgboost_eta_v2.json"

_model = None
_load_attempted = False

# Feature names the XGBoost v2 model was trained with
_FEATURE_NAMES = [
    "current_arrival_delay_min",
    "distance_to_next_km",
    "historical_section_avg_delay_filled",
    "section_historical_median_delay_filled",
    "section_historical_std_delay_filled",
    "section_historical_count",
    "current_delay_minus_section_avg_filled",
    "train_historical_avg_delay_filled",
    "day_of_week",
    "time_of_day",
]

# Fallback constants derived from training data
_HIST_AVG = 15.0
_HIST_MED = 9.0
_HIST_STD = 13.4
_HIST_CNT = 50.0


def _load() -> None:
    global _model, _load_attempted
    if _load_attempted:
        return
    _load_attempted = True
    try:
        import xgboost as xgb
        m = xgb.Booster()
        m.load_model(str(_MODEL_PATH))
        _model = m
        logger.info("XGBoost ETA model loaded from %s", _MODEL_PATH)
    except Exception as exc:
        logger.warning("ETA model unavailable: %s", exc)


_load()


def predict_for_train(train: dict) -> dict | None:
    """Return ETA prediction dict for a live train, or None if unavailable."""
    if _model is None:
        return None

    try:
        import xgboost as xgb
        import numpy as np

        current_delay = float(train.get("delayMinutes", 0))
        dist_from_origin = float(train.get("distanceFromOriginKm", 0))
        total_dist = float(train.get("totalDistanceKm", 1000))
        remaining = max(0.0, total_dist - dist_from_origin)
        distance_to_next = min(remaining, 30.0) if remaining > 0 else 30.0

        now = datetime.now()
        day_of_week = float(now.weekday())
        time_of_day = now.hour + now.minute / 60.0

        train_hist_avg = max(_HIST_AVG, current_delay)

        features = {
            "current_arrival_delay_min": current_delay,
            "distance_to_next_km": distance_to_next,
            "historical_section_avg_delay_filled": _HIST_AVG,
            "section_historical_median_delay_filled": _HIST_MED,
            "section_historical_std_delay_filled": _HIST_STD,
            "section_historical_count": _HIST_CNT,
            "current_delay_minus_section_avg_filled": current_delay - _HIST_AVG,
            "train_historical_avg_delay_filled": train_hist_avg,
            "day_of_week": day_of_week,
            "time_of_day": time_of_day,
        }

        row = np.array([[features[f] for f in _FEATURE_NAMES]])
        dmat = xgb.DMatrix(row, feature_names=_FEATURE_NAMES)
        p50 = float(_model.predict(dmat)[0])
        p50 = max(0.0, p50)

        # ±30% confidence interval (XGBoost v2 is a point-estimate model)
        spread = max(5.0, p50 * 0.30)
        low = max(0.0, round(p50 - spread, 1))
        high = round(p50 + spread, 1)

        return {
            "predicted_delay_min": round(p50, 1),
            "confidence_low_min": low,
            "confidence_high_min": high,
            "confidence_pct": 60,
        }
    except Exception as exc:
        logger.error("ETA prediction error: %s", exc)
        return None
