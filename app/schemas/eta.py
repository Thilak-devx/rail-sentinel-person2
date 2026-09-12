"""Pydantic schemas for /predict-eta endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ETAPredictRequest(BaseModel):
    """Input model representing a train's current state for ETA prediction.

    All 10 features required by the LightGBM quantile regression model must be
    supplied.  Missing or invalid values will cause a 422 validation error.
    """

    train_number: str = Field(
        ..., min_length=1, description="Train number identifier"
    )
    current_station: str = Field(
        ..., min_length=1, description="Current/last station name"
    )
    next_station: str = Field(
        ..., min_length=1, description="Next station name"
    )
    current_delay_min: float = Field(
        ..., ge=0, description="Current delay in minutes at last station"
    )
    distance_to_next_km: float = Field(
        ..., ge=0, description="Distance to next station in kilometres"
    )
    historical_section_avg_delay: float = Field(
        ..., ge=0, description="Historical average delay for the section in minutes"
    )
    section_historical_median_delay: float = Field(
        ..., ge=0, description="Historical median delay for the section in minutes"
    )
    section_historical_std_delay: float = Field(
        ..., ge=0, description="Historical standard deviation of section delays in minutes"
    )
    section_historical_count: int = Field(
        ..., ge=0, description="Number of historical observations used for section statistics"
    )
    train_historical_avg_delay: float = Field(
        ..., ge=0, description="Average delay across the entire train route in minutes"
    )
    day_of_week: int = Field(
        ..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)"
    )
    time_of_day: float = Field(
        ..., ge=0, le=24, description="Time of day in hours (0.0-24.0)"
    )


class ETAPredictResponse(BaseModel):
    """Response model for /predict-eta endpoint with exact five fields."""

    predicted_delay_min: float = Field(
        ..., ge=0, description="Predicted delay in minutes"
    )
    confidence_low_min: float = Field(
        ..., ge=0, description="Lower bound of confidence interval in minutes"
    )
    confidence_high_min: float = Field(
        ..., ge=0, description="Upper bound of confidence interval in minutes"
    )
    confidence_pct: int = Field(
        ..., ge=0, le=100, description="Confidence percentage"
    )
    baseline_mae_min: float = Field(
        ..., ge=0, description="Naive baseline MAE in minutes"
    )
    # Optional risk fields from Person 2 integration
    risk_level: Optional[str] = Field(
        None, description="Risk level: none, low, moderate, severe"
    )
    risk_source: Optional[str] = Field(
        None, description="Source of risk: flood, weather, none, unavailable"
    )
    risk_last_updated: Optional[str] = Field(
        None, description="ISO timestamp of when risk data was last updated"
    )
    risk_stale: Optional[bool] = Field(
        None, description="Whether the risk data is stale"
    )