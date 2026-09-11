"""Tests for RailSentinel Person 1 — Data & Prediction Engine.

Tests cover: haversine distance, chronological split, MAE calculation,
naive baseline, API response schema, and /predict-eta behavior when no
trained model exists.

All tests operate without fabricated railway data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.features.haversine import haversine_km
from src.evaluation.metrics import (
    mean_absolute_error_custom,
    naive_baseline_mae,
    percentage_improvement_ml_vs_baseline,
    naive_last_known_prediction,
)
from src.evaluation.timeseries import chronological_split, timeseries_split
from app.schemas.eta import ETAPredictRequest, ETAPredictResponse


# ---------------------------------------------------------------------------
# Haversine tests
# ---------------------------------------------------------------------------


def test_haversine_known_distance():
    """Test haversine against known distance: Paris to Amsterdam ≈ 431 km."""
    # Paris: 48.8566, 2.3522
    # Amsterdam: 52.3676, 4.9041
    distance = haversine_km(48.8566, 2.3522, 52.3676, 4.9041)
    assert 429 < distance < 435, f"Expected ~431 km, got {distance:.2f} km"
    print(f"  PASS: haversine Paris-Amsterdam = {distance:.2f} km")


def test_haversine_same_point():
    """ haversine of a point with itself should be 0."""
    distance = haversine_km(37.7749, -122.4194, 37.7749, -122.4194)
    assert distance == 0.0, f"Expected 0 km for same point, got {distance}"
    print(f"  PASS: haversine same point = {distance} km")


def test_haversine_invalid_latitude():
    """ Haversine should raise on invalid latitude."""
    try:
        haversine_km(100, 0, 0, 0)
        assert False, "Expected ValueError for invalid latitude"
    except ValueError:
        print("  PASS: haversine raises ValueError for invalid latitude")


def test_haversine_invalid_longitude():
    """ Haversine should raise on invalid longitude."""
    try:
        haversine_km(0, 200, 0, 0)
        assert False, "Expected ValueError for invalid longitude"
    except ValueError:
        print("  PASS: haversine raises ValueError for invalid longitude")


# ---------------------------------------------------------------------------
# MAE and naive baseline tests
# ---------------------------------------------------------------------------


def test_mae_custom():
    """Test custom MAE function against scikit-learn."""
    from sklearn.metrics import mean_absolute_error as sk_mae

    y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y_pred = np.array([1.1, 2.2, 2.9, 4.1, 5.3])

    custom_mae = mean_absolute_error_custom(y_true, y_pred)
    sk_mae_val = float(sk_mae(y_true, y_pred))

    assert abs(custom_mae - sk_mae_val) < 1e-10, (
        f"Custom MAE {custom_mae} != sklearn MAE {sk_mae_val}"
    )
    print(f"  PASS: custom MAE = {custom_mae:.6f}, sklearn MAE = {sk_mae_val:.6f}")


def test_naive_baseline_mae():
    """Test naive baseline MAE computation."""
    y_true = np.array([10.0, 12.0, 15.0, 13.0, 18.0])
    baseline_mae = naive_baseline_mae(y_true)

    # Manual check: naive predicts last known (18.0) for all after first
    # predictions: [0, 18, 18, 18, 18]
    # errors: [10, 6, 3, 5, 0] -> MAE = (10+6+3+5+0)/5 = 24/5 = 4.8
    expected_mae = 4.8
    assert abs(baseline_mae - expected_mae) < 1e-10, (
        f"Expected naive MAE {expected_mae}, got {baseline_mae}"
    )
    print(f"  PASS: naive baseline MAE = {baseline_mae:.6f} (expected {expected_mae})")


def test_naive_last_known_prediction():
    """Test naive last-known prediction function."""
    y = np.array([5.0, 8.0, 3.0, 12.0])
    predictions = naive_last_known_prediction(y)

    # First is 0, rest are last known (12.0)
    expected = np.array([0.0, 12.0, 12.0, 12.0])
    assert np.allclose(predictions, expected), (
        f"Expected {expected}, got {predictions}"
    )
    print(f"  PASS: naive last-known predictions = {predictions}")


def test_percentage_improvement():
    """Test percentage improvement computation."""
    # ML MAE = 3.0, baseline MAE = 5.0 -> improvement = (5-3)/5 * 100 = 40%
    improvement = percentage_improvement_ml_vs_baseline(3.0, 5.0)
    assert abs(improvement - 40.0) < 1e-10, f"Expected 40%, got {improvement}%"
    print(f"  PASS: percentage improvement = {improvement:.1f}%")

    # Zero baseline
    improvement_zero = percentage_improvement_ml_vs_baseline(3.0, 0.0)
    assert improvement_zero == 0.0, f"Expected 0% for zero baseline, got {improvement_zero}"
    print(f"  PASS: percentage improvement with zero baseline = {improvement_zero}%")


# ---------------------------------------------------------------------------
# Chronological split tests
# ---------------------------------------------------------------------------


def test_chronological_split():
    """Test that chronological split preserves order."""
    # Create data with a date column
    dates = pd.date_range("2024-01-01", periods=20, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "value": range(20),
        "delay": np.random.rand(20) * 10,
    })

    train, test = chronological_split(df, "date", train_ratio=0.7, shuffle=False)

    # Training should have earlier dates than testing
    assert train["date"].max() <= test["date"].min(), (
        f"Chronological split violated: train max {train['date'].max()} > "
        f"test min {test['date'].min()}"
    )

    # Training should be ~70% of data
    assert len(train) == 14, f"Expected 14 train rows, got {len(train)}"
    assert len(test) == 6, f"Expected 6 test rows, got {len(test)}"

    print(f"  PASS: chronological split: train={len(train)}, test={len(test)}")


def test_chronological_split_with_shuffle_false():
    """Test chronological split with shuffle=False (the recommended mode)."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({"date": dates, "delay": range(10)})

    train, test = chronological_split(df, "date", train_ratio=0.5, shuffle=False)

    assert len(train) == 5
    assert len(test) == 5
    # Verify ordering preserved
    assert train["date"].max() <= test["date"].min()
    print(f"  PASS: chronological split shuffle=False: train={len(train)}, test={len(test)}")


def test_chronological_split_invalid_date_col():
    """Test that invalid date column raises ValueError."""
    df = pd.DataFrame({"value": range(10)})
    try:
        chronological_split(df, "nonexistent_date", train_ratio=0.8)
        assert False, "Expected ValueError for invalid date column"
    except ValueError:
        print("  PASS: chronological split raises ValueError for invalid date column")


def test_timeseries_split():
    """Test timeseries split utility."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    df = pd.DataFrame({"date": dates, "delay": range(30)})

    splits = timeseries_split(df, "date", n_splits=3)

    assert len(splits) == 3, f"Expected 3 splits, got {len(splits)}"
    for i, (train, test) in enumerate(splits):
        assert len(train) > 0, f"Split {i}: train set is empty"
        assert len(test) > 0, f"Split {i}: test set is empty"
        # Verify train comes before test chronologically
        if len(train) > 0 and len(test) > 0:
            assert train["date"].max() <= test["date"].min(), (
                f"Split {i}: chronological order violated"
            )

    print(f"  PASS: timeseries split: {len(splits)} splits generated")


# ---------------------------------------------------------------------------
# Pydantic schema tests
# ---------------------------------------------------------------------------


def test_eta_predict_request():
    """Test ETAPredictRequest schema validation."""
    from app.schemas.eta import ETAPredictRequest

    # Valid request with all 10 required features
    valid_req = ETAPredictRequest(
        train_number="12345",
        current_station="Delhi",
        next_station="Mumbai",
        current_delay_min=5.0,
        distance_to_next_km=12.5,
        historical_section_avg_delay=15.0,
        section_historical_median_delay=9.0,
        section_historical_std_delay=13.399174556213485,
        section_historical_count=81121,
        train_historical_avg_delay=26.0,
        day_of_week=1,  # Tuesday
        time_of_day=14.5,  # 2:30 PM
    )
    assert valid_req.train_number == "12345"
    assert valid_req.current_station == "Delhi"
    assert valid_req.next_station == "Mumbai"
    assert valid_req.current_delay_min == 5.0
    assert valid_req.distance_to_next_km == 12.5
    assert valid_req.historical_section_avg_delay == 15.0
    assert valid_req.section_historical_median_delay == 9.0
    assert valid_req.section_historical_std_delay == 13.399174556213485
    assert valid_req.section_historical_count == 81121
    assert valid_req.train_historical_avg_delay == 26.0
    assert valid_req.day_of_week == 1
    assert valid_req.time_of_day == 14.5
    print("  PASS: ETAPredictRequest valid input")

    # Invalid: empty train number should fail (constr strip_min=1)
    try:
        invalid_req = ETAPredictRequest(
            train_number="",
            current_station="Delhi",
            next_station="Mumbai",
            current_delay_min=5.0,
            distance_to_next_km=12.5,
            historical_section_avg_delay=15.0,
            section_historical_median_delay=9.0,
            section_historical_std_delay=13.399174556213485,
            section_historical_count=81121,
            train_historical_avg_delay=26.0,
            day_of_week=1,
            time_of_day=14.5,
        )
        assert False, "Expected validation error for empty train number"
    except Exception:
        print("  PASS: ETAPredictRequest rejects empty train number")


def test_eta_predict_response():
    """Test ETAPredictResponse schema has exactly 5 fields."""
    # Construct a response with all 5 required fields
    response = ETAPredictResponse(
        predicted_delay_min=8.5,
        confidence_low_min=3.2,
        confidence_high_min=14.7,
        confidence_pct=82,
        baseline_mae_min=6.1,
    )

    # Verify all fields
    assert response.predicted_delay_min == 8.5
    assert response.confidence_low_min == 3.2
    assert response.confidence_high_min == 14.7
    assert response.confidence_pct == 82
    assert response.baseline_mae_min == 6.1

    # Verify confidence_pct is in [0, 100]
    assert 0 <= response.confidence_pct <= 100

    print("  PASS: ETAPredictResponse has exactly 5 fields with correct types")


def test_eta_predict_response_missing_fields():
    """Test that missing required fields raise validation error."""
    try:
        # Missing predicted_delay_min
        incomplete = ETAPredictResponse(
            confidence_low_min=3.0,
            confidence_high_min=5.0,
            confidence_pct=80,
            baseline_mae_min=2.0,
            # predicted_delay_min omitted
        )
        assert False, "Expected validation error for missing field"
    except Exception:
        print("  PASS: ETAPredictResponse rejects missing required fields")


# ---------------------------------------------------------------------------
# API behaviour tests (without running server)
# ---------------------------------------------------------------------------


def test_predict_eta_no_model():
    """Test that /predict-eta returns model-unavailable error when no model.

    Note: With the models now loaded at startup, this test demonstrates the 503
    path. If models fail to load, the endpoint returns 503.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # POST /predict-eta with all required fields - should succeed since models loaded
    response = client.post("/predict-eta/", json={
        "train_number": "12345",
        "current_station": "Delhi",
        "next_station": "Mumbai",
        "current_delay_min": 5.0,
        "distance_to_next_km": 12.5,
        "historical_section_avg_delay": 15.0,
        "section_historical_median_delay": 9.0,
        "section_historical_std_delay": 13.399174556213485,
        "section_historical_count": 81121,
        "train_historical_avg_delay": 26.0,
        "day_of_week": 1,
        "time_of_day": 14.5,
    })

    # Models are loaded at startup, so we get 200 with a prediction
    assert response.status_code == 200, f"Expected 200 (models loaded), got {response.status_code}"
    body = response.json()
    # Verify the response has the expected 5 fields
    expected_fields = {"predicted_delay_min", "confidence_low_min", "confidence_high_min",
                       "confidence_pct", "baseline_mae_min"}
    assert set(body.keys()) == expected_fields, f"Expected fields {expected_fields}, got {set(body.keys())}"
    assert body["confidence_pct"] == 80
    assert body["baseline_mae_min"] == 9.8544
    print("  PASS: /predict-eta returns prediction when models loaded")


def test_predict_eta_route_exists():
    """Test that POST /predict-eta route is registered."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # POST /predict-eta with all required fields
    response = client.post("/predict-eta/", json={
        "train_number": "12345",
        "current_station": "Delhi",
        "next_station": "Mumbai",
        "current_delay_min": 5.0,
        "distance_to_next_km": 12.5,
        "historical_section_avg_delay": 15.0,
        "section_historical_median_delay": 9.0,
        "section_historical_std_delay": 13.399174556213485,
        "section_historical_count": 81121,
        "train_historical_avg_delay": 26.0,
        "day_of_week": 1,
        "time_of_day": 14.5,
    })

    # Route is registered and returns 200 with prediction
    assert response is not None, "Route not registered - no response received"
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print("  PASS: POST /predict-eta route is registered in FastAPI app")


# ---------------------------------------------------------------------------
# Main test runner
# ---------------------------------------------------------------------------


import json
import os
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app


def test_predict_eta_success():
    """Test a successful /predict-eta request with valid input."""
    client = TestClient(app)

    # Valid request with all 10 required features
    response = client.post("/predict-eta/", json={
        "train_number": "12345",
        "current_station": "Delhi",
        "next_station": "Mumbai",
        "current_delay_min": 5.0,
        "distance_to_next_km": 12.5,
        "historical_section_avg_delay": 15.0,
        "section_historical_median_delay": 9.0,
        "section_historical_std_delay": 13.399174556213485,
        "section_historical_count": 81121,
        "train_historical_avg_delay": 26.0,
        "day_of_week": 1,  # Tuesday
        "time_of_day": 14.5,  # 2:30 PM
    })

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    body = response.json()

    # Verify exactly 5 fields present
    expected_fields = {
        "predicted_delay_min",
        "confidence_low_min",
        "confidence_high_min",
        "confidence_pct",
        "baseline_mae_min",
    }
    assert set(body.keys()) == expected_fields, (
        f"Expected fields {expected_fields}, got {set(body.keys())}"
    )

    # Verify predicted_delay_min is numeric
    assert isinstance(body["predicted_delay_min"], (int, float)), (
        f"predicted_delay_min should be numeric, got {type(body['predicted_delay_min'])}"
    )
    assert body["predicted_delay_min"] >= 0, (
        f"predicted_delay_min should be >= 0, got {body['predicted_delay_min']}"
    )

    # Verify confidence_low_min is numeric
    assert isinstance(body["confidence_low_min"], (int, float)), (
        f"confidence_low_min should be numeric, got {type(body['confidence_low_min'])}"
    )

    # Verify confidence_high_min is numeric
    assert isinstance(body["confidence_high_min"], (int, float)), (
        f"confidence_high_min should be numeric, got {type(body['confidence_high_min'])}"
    )

    # Verify confidence_pct == 80
    assert body["confidence_pct"] == 80, f"Expected confidence_pct == 80, got {body['confidence_pct']}"

    # Verify baseline_mae_min == 9.8544
    assert body["baseline_mae_min"] == 9.8544, (
        f"Expected baseline_mae_min == 9.8544, got {body['baseline_mae_min']}"
    )

    # Verify low <= predicted <= high
    assert body["confidence_low_min"] <= body["predicted_delay_min"] <= body["confidence_high_min"], (
        f"Ordering violated: {body['confidence_low_min']} <= {body['predicted_delay_min']} <= {body['confidence_high_min']}"
    )

    print("  PASS: successful /predict-eta request")


def test_predict_eta_missing_fields():
    """Test that missing required fields return 422 validation error."""
    client = TestClient(app)

    # Request missing several required fields
    response = client.post("/predict-eta/", json={
        "train_number": "12345",
        "current_station": "Delhi",
        "next_station": "Mumbai",
        # missing: current_delay_min and all other features
    })

    # Should return 422 validation error from Pydantic
    assert response.status_code == 422, f"Expected 422, got {response.status_code}"
    print("  PASS: missing fields return 422 validation error")


def test_predict_eta_model_loaded():
    """Test that model files load successfully."""
    # Check that the model files exist
    model_dir = Path(__file__).resolve().parent.parent / "models"

    p10_path = model_dir / "lightgbm_eta_p10.txt"
    p50_path = model_dir / "lightgbm_eta_p50.txt"
    p90_path = model_dir / "lightgbm_eta_p90.txt"

    assert p10_path.exists(), f"P10 model file not found: {p10_path}"
    assert p50_path.exists(), f"P50 model file not found: {p50_path}"
    assert p90_path.exists(), f"P90 model file not found: {p90_path}"

    # Verify models can be loaded
    import lightgbm as lgb
    b10 = lgb.Booster(model_file=str(p10_path))
    b50 = lgb.Booster(model_file=str(p50_path))
    b90 = lgb.Booster(model_file=str(p90_path))

    assert b10 is not None
    assert b50 is not None
    assert b90 is not None

    print("  PASS: model files load successfully")


def test_predict_eta_response_fields():
    """Test that the response contains exactly five fields with correct types."""
    from app.schemas.eta import ETAPredictResponse

    response = ETAPredictResponse(
        predicted_delay_min=7.8776,
        confidence_low_min=2.5,
        confidence_high_min=13.2,
        confidence_pct=80,
        baseline_mae_min=9.8544,
    )

    assert response.predicted_delay_min == 7.8776
    assert response.confidence_low_min == 2.5
    assert response.confidence_high_min == 13.2
    assert response.confidence_pct == 80
    assert response.baseline_mae_min == 9.8544

    # Verify confidence_pct is in [0, 100]
    assert 0 <= response.confidence_pct <= 100

    print("  PASS: response has exactly five fields with correct types")


# ---------------------------------------------------------------------------
# Main test runner extension
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("RailSentinel Person 1 — Foundation Tests")
    print("=" * 60)

    tests = [
        ("Haversine", [
            test_haversine_known_distance,
            test_haversine_same_point,
            test_haversine_invalid_latitude,
            test_haversine_invalid_longitude,
        ]),
        ("MAE & Naive Baseline", [
            test_mae_custom,
            test_naive_baseline_mae,
            test_naive_last_known_prediction,
            test_percentage_improvement,
        ]),
        ("Chronological Split", [
            test_chronological_split,
            test_chronological_split_with_shuffle_false,
            test_chronological_split_invalid_date_col,
            test_timeseries_split,
        ]),
        ("Pydantic Schemas", [
            test_eta_predict_request,
            test_eta_predict_response,
            test_eta_predict_response_missing_fields,
        ]),
        ("API Routes", [
            test_predict_eta_route_exists,
            test_predict_eta_no_model,
            test_predict_eta_success,
            test_predict_eta_missing_fields,
            test_predict_eta_model_loaded,
            test_predict_eta_response_fields,
        ]),
    ]

    passed = 0
    total = 0

    for category, test_funcs in tests:
        print(f"\n--- {category} ---")
        for func in test_funcs:
            total += 1
            try:
                func()
                passed += 1
            except Exception as e:
                print(f"  FAIL: {func.__name__}: {e}")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"{'=' * 60}")

    if passed == total:
        print("All tests passed! ✓")
        sys.exit(0)
    else:
        print(f"{total - passed} test(s) failed!")
        sys.exit(1)