# RailSentinel SIH26028

## Person 1 -- Data & Prediction Engine

**Responsibility:** ETA forecasting system using railway schedule data, delay labels,
time-aware feature engineering, tree-based regression models, and uncertainty
estimation. **Does not implement** disaster-management, incident detection,
safety/risk analysis, or dashboard functionality.

---

## Project Structure

The project follows a clean separation of concerns:

```text
sih train/
├── app/                          # FastAPI application
│   ├── __init__.py
│   ├── main.py                   # App entry point
│   ├── api/                      # API routes
│   │   ├── __init__.py
│   │   └── routes.py             # POST /predict-eta
│   ├── schemas/                  # Pydantic models
│   │   ├── __init__.py
│   │   └── eta.py                # Request/response schemas
│   ├── config.py                 # Environment configuration
│   └── services/                 # Business logic
│       ├── __init__.py
│       └── prediction_service.py
├── src/                          # Source modules
│   ├── __init__.py
│   ├── data/                     # Data ingestion/cleaning
│   │   ├── __init__.py
│   │   ├── ingestion.py          # (future)
│   │   ├── cleaning.py           # (future)
│   │   └── validation.py         # Column validation
│   ├── features/                 # Feature engineering
│   │   ├── __init__.py
│   │   └── engineering.py        # Haversine, delays, time features, weather
│   ├── models/                   # Model interfaces
│   │   ├── __init__.py
│   │   ├── train.py              # XGBoost, RF, quantile wrappers
│   │   ├── predict.py            # Prediction orchestration
│   │   └── quantile.py           # (integrated in train.py)
│   └── evaluation/               # Evaluation utilities
│       ├── __init__.py
│       └── metrics.py            # MAE, naive baseline, chronological split
├── scripts/                      # Operational scripts
│   ├── __init__.py
│   ├── collect_delay_data.py     # runningstatus.in scraper foundation
│   ├── prepare_dataset.py        # (future)
│   ├── train_model.py            # (future)
│   └── evaluate_model.py         # (future)
├── data/                         # Data directories
│   ├── raw/                      # Raw downloaded data
│   ├── processed/                # Cleaned/engineered features
│   └── external/                 # External data (e.g. weather)
├── models/                       # Trained model artifacts
├── tests/                        # Unit tests
│   ├── __init__.py
│   ├── test_features.py          # Haversine, MAE, split, schema tests
│   ├── test_metrics.py           # (combined into test_features.py)
│   └── test_api.py               # API route and schema tests
├── .env.example                  # Configuration placeholders
├── requirements.txt              # Python dependencies
├── main.py                       # Script entry point (uvicorn launcher)
├── .gitignore
└── README.md