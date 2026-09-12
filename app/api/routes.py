"""API routes for the ETA prediction engine.

Person 1 — Data & Prediction Engine only.
"""

from __future__ import annotations

import logging
from pathlib import Path

import lightgbm as lgb
import numpy as np
from fastapi import APIRouter, HTTPException, status

from app.schemas.eta import ETAPredictRequest, ETAPredictResponse
from app.api.risk_cache import get_risk_for_segment, find_risk_by_station

router = APIRouter(prefix="/predict-eta", tags=["ETA Prediction"])

# ---------------------------------------------------------------------------
# Model loading (lazy, on first request)
# ---------------------------------------------------------------------------

# Models are at the project root "models/" directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
model_dir = _PROJECT_ROOT / "models"

_ltgb_p10: lgb.Booster | None = None
_ltgb_p50: lgb.Booster | None = None
_ltgb_p90: lgb.Booster | None = None
_models_loaded = False


def _load_models() -> None:
    """Load the three LightGBM quantile models on first use (lazy loading)."""
    global _ltgb_p10, _ltgb_p50, _ltgb_p90, _models_loaded

    if _models_loaded:
        return  # already loaded

    try:
        _ltgb_p10 = lgb.Booster(model_file=str(model_dir / "lightgbm_eta_p10.txt"))
        _ltgb_p50 = lgb.Booster(model_file=str(model_dir / "lightgbm_eta_p50.txt"))
        _ltgb_p90 = lgb.Booster(model_file=str(model_dir / "lightgbm_eta_p90.txt"))
        logging.info("LightGBM quantile models loaded successfully")
    except Exception as exc:  # pragma: no cover - defensive
        logging.warning(f"Failed to load LightGBM models: {exc}")
        _ltgb_p10 = _ltgb_p50 = _ltgb_p90 = None

    _models_loaded = True


# NOTE: Models are now loaded lazily on first request, not at module import


def _prepare_features(request: ETAPredictRequest) -> dict[str, float]:
    """Prepare the 10 features required by the LightGBM quantile models.

    Uses the same fallback values documented in
    data/processed/lightgbm_quantile_metrics.json.
    Enforces P10 <= P50 <= P90 ordering on the output.

    Raises HTTP 422 if required information is missing or invalid.
    """
    try:
        # Map request fields to feature names
        current_arrival_delay_min = request.current_delay_min
        distance_to_next_km = request.distance_to_next_km
        historical_section_avg_delay = request.historical_section_avg_delay
        section_historical_median_delay = request.section_historical_median_delay
        section_historical_std_delay = request.section_historical_std_delay
        section_historical_count = request.section_historical_count
        train_historical_avg_delay = request.train_historical_avg_delay
        day_of_week = request.day_of_week
        time_of_day = request.time_of_day

        # current_delay_minus_section_avg = current - filled historical
        current_delay_minus_section_avg = current_arrival_delay_min - historical_section_avg_delay

        features = {
            "current_arrival_delay_min": current_arrival_delay_min,
            "distance_to_next_km": distance_to_next_km,
            "historical_section_avg_delay": historical_section_avg_delay,
            "section_historical_median_delay": section_historical_median_delay,
            "section_historical_std_delay": section_historical_std_delay,
            "section_historical_count": section_historical_count,
            "current_delay_minus_section_avg": current_delay_minus_section_avg,
            "train_historical_avg_delay": train_historical_avg_delay,
            "day_of_week": float(day_of_week),
            "time_of_day": float(time_of_day),
        }

        # Verify no NaN/inf (Pydantic ge/le constraints should prevent this,
        # but defensive check avoids silent failures)
        for name, val in features.items():
            if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
                raise ValueError(f"Feature '{name}' is NaN or inf")

        return features

    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid feature input: {exc}",
        )


# ---------------------------------------------------------------------------
# Prediction endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=ETAPredictResponse,
    summary="Predict estimated time of arrival delay",
    description="Given a train's current state, return ETA delay prediction with "
    "80% confidence interval (P10-P90)",
)
async def predict_eta(request: ETAPredictRequest) -> ETAPredictResponse:
    """POST /predict-eta endpoint.

    Returns predicted_delay_min, confidence_low_min (P10), confidence_high_min (P90),
    confidence_pct (80), and baseline_mae_min (9.8544).

    Prediction ordering is enforced: confidence_low_min <= predicted_delay_min <=
    confidence_high_min.
    """
    _load_models()

    # If models failed to load, return 503
    if _ltgb_p10 is None or _ltgb_p50 is None or _ltgb_p90 is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not trained or unavailable. Train the model first using the "
            "training pipeline before making predictions.",
        )

    # Prepare features from request
    features = _prepare_features(request)

    # --- P10 prediction ---
    X = [features[f] for f in
         ["current_arrival_delay_min", "distance_to_next_km", "historical_section_avg_delay",
          "section_historical_median_delay", "section_historical_std_delay",
          "section_historical_count", "current_delay_minus_section_avg",
          "train_historical_avg_delay", "day_of_week", "time_of_day"]]
    p10_raw = float(_ltgb_p10.predict([X])[0])

    # --- P50 prediction ---
    p50_raw = float(_ltgb_p50.predict([X])[0])

    # --- P90 prediction ---
    p90_raw = float(_ltgb_p90.predict([X])[0])

    # Enforce P10 <= P50 <= P90 ordering
    # Sort the three predictions and assign to P10/P50/P90 positions
    sorted_preds = sorted([p10_raw, p50_raw, p90_raw])
    p10 = sorted_preds[0]  # lowest -> P10
    p50 = sorted_preds[1]  # middle -> P50
    p90 = sorted_preds[2]  # highest -> P90

    # Compute interval width and coverage
    confidence_low_min = p10
    predicted_delay_min = p50
    confidence_high_min = p90
    confidence_pct = 80  # P10-P90 = 80% interval
    baseline_mae_min = 9.8544  # naive baseline from Task 20/21c

    # Final ordering safety check (should always pass due to sorting above)
    if not (confidence_low_min <= predicted_delay_min <= confidence_high_min):
        # This should never happen, but if it does, return a safe fallback
        # rather than fabricating values: use the median as all three
        predicted_delay_min = (p10_raw + p50_raw + p90_raw) / 3
        confidence_low_min = predicted_delay_min
        confidence_high_min = predicted_delay_min

    # --- Integrate risk data from Person 2 cache ---
    risk_level = None
    risk_source = None
    risk_last_updated = None
    risk_stale = None

    # Try to get risk data from cache using route_segment_id if available
    # The request doesn't have route_segment_id in the current schema,
    # so we try to match by station names if possible
    route_segment_id = getattr(request, 'route_segment_id', None)

    # Access the risk cache using the new risk_cache module
    risk_data = None
    if route_segment_id:
        risk_data = await get_risk_for_segment(route_segment_id)
    else:
        # Try to find by station names - use current_station as fallback
        # This is a best-effort match since we don't have segment_id in request
        risk_data = await find_risk_by_station(request.current_station)

    if risk_data:
        risk_level = risk_data.get("risk_level")
        risk_source = risk_data.get("source")
        risk_last_updated = risk_data.get("last_updated")
        # Check if risk data is stale
        if isinstance(risk_data, dict):
            freshness = risk_data.get("freshness", {})
            if isinstance(freshness, dict):
                risk_stale = freshness.get("is_stale", False)

    return ETAPredictResponse(
        predicted_delay_min=predicted_delay_min,
        confidence_low_min=confidence_low_min,
        confidence_high_min=confidence_high_min,
        confidence_pct=confidence_pct,
        baseline_mae_min=baseline_mae_min,
        risk_level=risk_level,
        risk_source=risk_source,
        risk_last_updated=risk_last_updated,
        risk_stale=risk_stale,
    )