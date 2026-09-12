"""Configuration module for RailSentinel using environment variables.

Person 1 — Data & Prediction Engine.
Uses python-dotenv for local development and os.environ for production.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# Load .env file from project root if present
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.is_file():
    load_dotenv(_ENV_FILE)


def get_settings() -> dict:
    """Return configuration as a dictionary.

    Returns
    -------
    dict
        Configuration keyed by setting name.
    """
    return {
        "data_dir": os.getenv("DATA_DIR", "data"),
        "model_dir": os.getenv("MODEL_DIR", "models"),
        "raw_data_dir": os.path.join(
            _PROJECT_ROOT, os.getenv("DATA_DIR", "data"), "raw"
        ),
        "processed_data_dir": os.path.join(
            _PROJECT_ROOT, os.getenv("DATA_DIR", "data"), "processed"
        ),
        "external_data_dir": os.path.join(
            _PROJECT_ROOT, os.getenv("DATA_DIR", "data"), "external"
        ),
        "model_path": os.getenv(
            "MODEL_PATH",
            str(_PROJECT_ROOT / "models" / "eta_delay_model.joblib"),
        ),
        "openweather_api_key": os.getenv("OPENWEATHER_API_KEY", ""),
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "env": os.getenv("RAILSENTRY_ENV", "development"),
        "person2_base_url": os.getenv("PERSON2_BASE_URL", "http://127.0.0.1:8001"),
        "risk_poll_interval_seconds": int(os.getenv("RISK_POLL_INTERVAL_SECONDS", "10")),
        "port": int(os.getenv("PORT", "8000")),
    }