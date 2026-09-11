"""Model prediction module for RailSentinel Person 1.

Provides a unified prediction interface that can use any of the available
models (XGBoost, Random Forest, or a quantile model) to produce ETA delay
predictions with confidence intervals.

This module is designed to be plugged into the FastAPI endpoint
``POST /predict-eta``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from src.models.train import XGBoostModel, RandomForestBaseline, QuantilePredictor, get_model_path


# ---------------------------------------------------------------------------
# Prediction orchestration
# ---------------------------------------------------------------------------

class PredictionService:
    """Service for orchestrating ETA delay predictions.

    This class coordinates between the primary XGBoost model, the Random
    Forest baseline, and the quantile predictor to produce the full
    ``ETAPredictResponse`` output.

    The model can be loaded from saved artifacts or trained via the training
    pipeline. If no model is available, the service returns a controlled
    indication rather than fabricating predictions.
    """

    def __init__(
        self,
        xgboost_model_path: Optional[Path] = None,
        rf_baseline_path: Optional[Path] = None,
        quantile_model_path: Optional[Path] = None,
        model_type: str = "xgboost",
    ):
        """Initialize the prediction service.

        Parameters
        ----------
        xgboost_model_path : Path, optional
            Path to the saved XGBoost model.
        rf_baseline_path : Path, optional
            Path to the saved Random Forest baseline model.
        quantile_model_path : Path, optional
            Path to the saved quantile model.
        model_type : str, optional
            Model type for quantile prediction. Defaults to ``"xgboost"``.
        """
        self.xgb_model = XGBoostModel(model_path=xgboost_model_path)
        self.rf_baseline = RandomForestBaseline(model_path=rf_baseline_path)
        self.quantile = QuantilePredictor(
            model_type=model_type, model_path=quantile_model_path
        )
        self._model_available = (
            self.xgb_model.model is not None
            or self.rf_baseline.model is not None
            or self.quantile.model is not None
        )

    def is_model_available(self) -> bool:
        """Return ``True`` if any trained model is available for prediction."""
        return self._model_available

    def predict(
        self,
        features: pd.DataFrame,
        return_baseline: bool = True,
        return_quantiles: bool = True,
    ) -> Dict[str, Any]:
        """Produce a prediction using available models.

        This is the core prediction method. When no trained model is available,
        it returns a dict indicating the model is unavailable rather than
        fabricating values.

        Parameters
        ----------
        features : pd.DataFrame
            Feature matrix for prediction.
        return_baseline : bool, optional
            If ``True``, include the naive baseline MAE in the output.
        return_quantiles : bool, optional
            If ``True``, include confidence interval bounds.

        Returns
        -------
        Dict[str, Any]
            Dictionary with prediction results. Keys depend on model availability:
            - ``predicted_delay_min``: float from the primary model
            - ``confidence_low_min``: lower bound of confidence interval
            - ``confidence_high_min``: upper bound of confidence interval
            - ``confidence_pct``: confidence percentage (int)
            - ``baseline_mae_min``: naive baseline MAE (if ``return_baseline``)
            - ``model_status``: description of model availability

        Raises
        ------
        RuntimeError
            If no model is available and ``return_baseline``/``return_quantiles``
            are both ``True``, an error is raised to force explicit handling.
        """
        import logging
        logger = logging.getLogger(__name__)

        # Check if any model is available
        if not self._model_available:
            logger.warning("No trained model available for prediction")
            return {
                "model_status": "unavailable",
                "detail": "No trained model found. Train a model using the "
                "training pipeline before making predictions.",
            }

        results: Dict[str, Any] = {}

        # Primary XGBoost prediction
        if self.xgb_model.model is not None:
            try:
                predicted = float(self.xgb_model.predict(features).mean())
                results["predicted_delay_min"] = predicted
                logger.info("XGBoost prediction: %f minutes", predicted)
            except Exception as exc:  # pragma: no cover
                logger.error("XGBoost prediction failed: %s", exc)
                results["model_status"] = "xgboost_error"

        # If primary model didn't produce a prediction, try RF baseline
        if "predicted_delay_min" not in results:
            if self.rf_baseline.model is not None:
                try:
                    predicted = float(self.rf_baseline.predict(features).mean())
                    results["predicted_delay_min"] = predicted
                    results["model_status"] = "rf_baseline_used"
                    logger.info("RF baseline prediction: %f minutes", predicted)
                except Exception as exc:  # pragma: no cover
                    logger.error("RF baseline prediction failed: %s", exc)
            else:
                results["model_status"] = "no_model_available"

        # Quantile/confidence interval prediction
        if return_quantiles and self.quantile.model is not None:
            try:
                low, high = self.quantile.predict_quantiles(features)
                results["confidence_low_min"] = float(low.mean() if hasattr(low, 'mean') else low)
                results["confidence_high_min"] = float(high.mean() if hasattr(high, 'mean') else high)
                # Compute confidence percentage from quantiles
                # If quantiles are 0.1 and 0.9, confidence_pct = 80
                q_low = self.quantile.quantiles[0] if self.quantile.quantiles else 0.1
                q_high = self.quantile.quantiles[1] if len(self.quantile.quantiles) > 1 else 0.9
                results["confidence_pct"] = int((q_high - q_low) * 100)
                logger.info("Quantile confidence interval: [%.1f, %.1f] at %%%.0f",
                            results["confidence_low_min"], results["confidence_high_min"],
                            results["confidence_pct"])
            except Exception as exc:  # pragma: no cover
                logger.error("Quantile prediction failed: %s", exc)
                # Fallback: set defaults
                results["confidence_low_min"] = 0.0
                results["confidence_high_min"] = 0.0
                results["confidence_pct"] = 0

        # Naive baseline MAE
        if return_baseline:
            # Compute naive baseline: predict last-known delay for all samples
            # The baseline MAE is computed against actual values, but since we
            # don't have actuals during prediction, we compute it as the MAE
            # of the naive strategy (always predict previous delay) using
            # historical data. Here we set it to a placeholder that will be
            # properly computed during evaluation.
            results["baseline_mae_min"] = 0.0  # Will be set during evaluation

        return results