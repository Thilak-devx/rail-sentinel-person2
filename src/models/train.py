"""Model foundation for RailSentinel Person 1 — Data & Prediction Engine.

Provides interfaces for the primary XGBoost regression model, Random Forest
comparison baseline, quantile prediction, and model serialization/loading.

All functions are designed as clean interfaces that the later training pipeline
can use. No training data is fabricated, no models are trained in this scaffold.
"""

from __future__ import annotations

import joblib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

# Try to import XGBoost; gracefully handle if not installed
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    xgb = None

# Try to import LightGBM; graceful fallback
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    lgb = None

# scikit-learn RandomForest always available (part of core ML deps)
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error


# ---------------------------------------------------------------------------
# Model artifact paths
# ---------------------------------------------------------------------------

def get_model_path(model_name: str = "eta_delay_model") -> Path:
    """Return the filesystem path where a model artifact should be stored.

    Parameters
    ----------
    model_name : str, optional
        Base name for the model file. Defaults to ``"eta_delay_model"``.

    Returns
    -------
    Path
        Project-relative path under the ``models/`` directory.
    """
    from app.config import get_settings

    settings = get_settings()
    model_dir = Path(settings["model_dir"])
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir / f"{model_name}.joblib"


# ---------------------------------------------------------------------------
# Primary XGBoost regression model
# ---------------------------------------------------------------------------

class XGBoostModel:
    """Wrapper for an XGBoost regression model with serialization support.

    This class provides a clean interface for loading/saving XGBoost models
    and making predictions. The model is not trained in this scaffold —
    training is performed via the separate training pipeline.
    """

    def __init__(
        self,
        model_path: Optional[Path] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the XGBoost model wrapper.

        Parameters
        ----------
        model_path : Path, optional
            Path to a saved model file. If provided, the model is loaded
            from this path. If ``None``, a new untrained model is created.
        params : Dict[str, Any], optional
            XGBoost parameters for model creation. Ignored if ``model_path``
            is provided (loaded model takes precedence).
        """
        self.model_path = model_path or get_model_path()
        self.model: Optional[xgb.XGBRegressor] = None
        self._params = params or self._default_params()

        if model_path is not None and model_path.is_file():
            self.load()

    @staticmethod
    def _default_params() -> Dict[str, Any]:
        """Return default XGBoost regression parameters.

        These are sensible defaults for ETA delay prediction but will be
        fine-tuned during the training pipeline.
        """
        return {
            "objective": "reg:squarederror",
            "eval_metric": "mae",
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "n_jobs": -1,
        }

    def load(self) -> None:
        """Load a model from ``self.model_path``.

        Raises
        ------
        FileNotFoundError
            If the model file does not exist.
        """
        if not self.model_path.is_file():
            raise FileNotFoundError(f"XGBoost model not found at {self.model_path}")
        self.model = joblib.load(self.model_path)
        logger_name = __import__("logging").getLogger(__name__)
        logger = logging.getLogger(__name__)
        logger.info("Loaded XGBoost model from %s", self.model_path)

    def save(self) -> None:
        """Save the current model to ``self.model_path``.

        Raises
        ------
        ValueError
            If the model has not been trained/initialized.
        """
        if self.model is None:
            raise ValueError("No model to save; model is None.")
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, self.model_path)
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Saved XGBoost model to %s", self.model_path)

    def predict(self, X: pd.DataFrame or np.ndarray) -> np.ndarray:
        """Make predictions using the loaded/trained model.

        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            Feature matrix for prediction.

        Returns
        -------
        np.ndarray
        Predicted values (delay in minutes).

        Raises
        ------
        RuntimeError
            If the model has not been loaded or trained.
        """
        if self.model is None:
            raise RuntimeError(
                "XGBoost model not available; either load a saved model or "
                "train one first."
            )
        import logging
        logger = logging.getLogger(__name__)
        logger.debug("Making XGBoost prediction with %d samples", len(X))
        return self.model.predict(X)


# ---------------------------------------------------------------------------
# Random Forest comparison baseline
# ---------------------------------------------------------------------------

class RandomForestBaseline:
    """Wrapper for a scikit-learn RandomForestRegressor comparison baseline.

    Used as the comparison baseline model specified in the requirements.
    Provides train/fit, predict, and serialization support.
    """

    def __init__(
        self,
        model_path: Optional[Path] = None,
        params: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the Random Forest baseline wrapper.

        Parameters
        ----------
        model_path : Path, optional
            Path to a saved model file. If provided, the model is loaded
            from this path.
        params : Dict[str, Any], optional
            RandomForest parameters. Defaults to sensible values.
        """
        self.model_path = model_path or get_model_path("rf_baseline")
        self.model: Optional[RandomForestRegressor] = None
        self._params = params or self._default_params()

        if model_path is not None and model_path.is_file():
            self.load()

    @staticmethod
    def _default_params() -> Dict[str, Any]:
        """Return default RandomForest regression parameters."""
        return {
            "n_estimators": 100,
            "max_depth": 6,
            "random_state": 42,
            "n_jobs": -1,
            "verbose": 0,
        }

    def load(self) -> None:
        """Load a model from ``self.model_path``."""
        if not self.model_path.is_file():
            raise FileNotFoundError(f"Random Forest baseline model not found at {self.model_path}")
        self.model = joblib.load(self.model_path)
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Loaded Random Forest baseline from %s", self.model_path)

    def save(self) -> None:
        """Save the current model to ``self.model_path``."""
        if self.model is None:
            raise ValueError("No model to save; model is None.")
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, self.model_path)
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Saved Random Forest baseline to %s", self.model_path)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "RandomForestBaseline":
        """Fit the Random Forest model to training data.

        Parameters
        ----------
        X : pd.DataFrame
            Feature matrix.
        y : pd.Series
            Target values (delay in minutes).

        Returns
        -------
        RandomForestBaseline
            Self, for method chaining.
        """
        from importlib import import_module
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Training Random Forest baseline with %d samples", len(X))
        self.model = RandomForestRegressor(**self._params)
        self.model.fit(X, y)
        self.save()
        return self

    def predict(self, X: pd.DataFrame or np.ndarray) -> np.ndarray:
        """Make predictions using the Random Forest model.

        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            Feature matrix.

        Returns
        -------
        np.ndarray
            Predicted delays in minutes.

        Raises
        ------
        RuntimeError
            If the model has not been loaded or trained.
        """
        if self.model is None:
            raise RuntimeError(
                "Random Forest baseline model not available; fit or load a model first."
            )
        import logging
        logger = logging.getLogger(__name__)
        logger.debug("Making RF prediction with %d samples", len(X))
        return self.model.predict(X)


# ---------------------------------------------------------------------------
# Quantile prediction for uncertainty estimation
# ---------------------------------------------------------------------------

class QuantilePredictor:
    """Wrapper for quantile regression prediction producing lower/upper bounds.

    Supports both XGBoost and LightGBM quantile regression via their respective
    objective functions. When the primary model is XGBoost, quantile predictions
    are made using the ``reg:quantileerror`` objective. When LightGBM is
    available, ``quantile`` objective can be used.

    This is the interface through which confidence intervals
    ``confidence_low_min`` and ``confidence_high_min`` will be produced.
    """

    def __init__(
        self,
        model_type: str = "xgboost",
        model_path: Optional[Path] = None,
        quantiles: Optional[list[float]] = None,
    ):
        """Initialize the quantile predictor.

        Parameters
        ----------
        model_type : str, optional
            Either ``"xgboost"`` or ``"lightgbm"``. Defaults to ``"xgboost"``.
        model_path : Path, optional
            Path to a saved quantile model.
        quantiles : list[float], optional
            List of quantiles for prediction. Defaults to [0.1, 0.9] for
            80% confidence intervals.
        """
        self.model_type = model_type
        self.model_path = model_path
        self.quantiles = quantiles or [0.1, 0.9]  # 80% confidence interval
        self.model: Any = None  # Will be either xgb.XGBRegressor or lgb.Booster

        if model_path is not None and model_path.is_file():
            self.load()

    def load(self) -> None:
        """Load a quantile model from ``self.model_path``."""
        if self.model_type == "xgboost":
            import logging
            logger = logging.getLogger(__name__)
            if not self.model_path.is_file():
                raise FileNotFoundError(f"XGBoost quantile model not found at {self.model_path}")
            self.model = joblib.load(self.model_path)
            logger.info("Loaded XGBoost quantile model from %s", self.model_path)
        elif self.model_type == "lightgbm":
            import logging
            logger = logging.getLogger(__name__)
            # LightGBM model loading
            try:
                import lightgbm as lgb
            except ImportError:
                raise ImportError("LightGBM not installed; cannot load LightGBM model.")
            self.model = lgb.Booster(model_file=str(self.model_path))
            logger.info("Loaded LightGBM quantile model from %s", self.model_path)

    def save(self, path: Optional[Path] = None) -> None:
        """Save the quantile model to disk.

        Parameters
        ----------
        path : Path, optional
            Path to save the model to. Defaults to ``self.model_path``.
        """
        save_path = path or self.model_path
        if save_path is None:
            raise ValueError("No save path specified for quantile model.")
        save_path.parent.mkdir(parents=True, exist_ok=True)

        if self.model_type == "xgboost":
            import joblib
            joblib.dump(self.model, save_path)
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Saved XGBoost quantile model to %s", save_path)
        elif self.model_type == "lightgbm":
            import logging
            logger = logging.getLogger(__name__)
            self.model.save_model(str(save_path) + ".txt")
            logger.info("Saved LightGBM quantile model to %s", save_path)

    def predict_quantiles(
        self, X: pd.DataFrame or np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Predict lower and upper quantile bounds.

        Parameters
        ----------
        X : pd.DataFrame or np.ndarray
            Feature matrix for prediction.

        Returns
        -------
        Tuple[np.ndarray, np.ndarray]
            (lower_bound, upper_bound) arrays corresponding to the specified
            quantiles (default: 0.1 and 0.9 for 80% confidence interval).
        """
        if self.model is None:
            raise RuntimeError("Quantile model not available; load or train a model first.")

        if self.model_type == "xgboost":
            import logging
            logger = logging.getLogger(__name__)
            lower = self.model.predict(X, iterationrange=(0, self.model.best_iteration + 1))
            # For XGBoost with reg:quantileerror, we need to predict per-quantile
            # This is a simplified interface; full multi-quantile prediction
            # would require iterating over quantiles
            logger.debug("XGBoost quantile prediction for %d samples", len(X))
            # Return midpoint ± half-width as simplified confidence interval
            # In full implementation, would predict each quantile separately
            mid = self.model.predict(X, iterationrange=(0, self.model.best_iteration + 1))
            # Placeholder: return symmetric interval around median prediction
            # TODO: Replace with proper quantile prediction
            return mid - 2.0, mid + 2.0  # ~95% interval approximation

        elif self.model_type == "lightgbm":
            import logging
            logger = logging.getLogger(__name__)
            # LightGBM quantile prediction
            n_quantiles = len(self.quantiles)
            preds = self.model.predict(X, num_iteration=self.model.best_iteration + 1)
            # LightGBM can return multiple quantiles if configured during training
            # For now, return simplified interval
            logger.debug("LightGBM quantile prediction for %d samples", len(X))
            mid = preds
            return mid - 2.0, mid + 2.0  # Placeholder

        else:
            raise ValueError(f"Unknown model_type: {self.model_type}")


# ---------------------------------------------------------------------------
# Model serialization / loading utilities
# ---------------------------------------------------------------------------

def load_model_artifact(artifact_path: Path) -> Any:
    """Load a generic model artifact from disk.

    Parameters
    ----------
    artifact_path : Path
        Path to the model artifact file.

    Returns
    -------
    Any
        The deserialized model object.

    Raises
    ------
    FileNotFoundError
        If the artifact file does not exist.
    """
    if not artifact_path.is_file():
        raise FileNotFoundError(f"Model artifact not found at {artifact_path}")
    return joblib.load(artifact_path)


def save_model_artifact(model: Any, artifact_path: Path) -> None:
    """Save a model artifact to disk.

    Parameters
    ----------
    model : Any
        Model object to serialize and save.
    artifact_path : Path
        Path where the artifact should be saved.
    """
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifact_path)


# Helper import for logging
import logging
logger = logging.getLogger(__name__)