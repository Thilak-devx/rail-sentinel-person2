from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional
from enum import Enum


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    SEVERE = "severe"


class PositionCreate(BaseModel):
    coach_id: str = Field(..., min_length=1, max_length=10)
    lat: float = Field(..., ge=-90, le=90)
    long: float = Field(..., ge=-180, le=180)
    speed: Optional[float] = Field(None, ge=0)
    timestamp: datetime

    @field_validator("coach_id")
    @classmethod
    def validate_coach_id(cls, v: str) -> str:
        return v.strip().upper()


class PositionResponse(BaseModel):
    coach_id: str
    lat: float
    long: float
    speed: Optional[float] = None
    calculated_speed: Optional[float] = None
    timestamp: datetime
    matched_lat: Optional[float] = None
    matched_long: Optional[float] = None
    match_distance_meters: Optional[float] = None
    route_segment_id: Optional[str] = None
    matched: Optional[bool] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str = "1.0.0"


class RiskScoreResponse(BaseModel):
    segment_id: str
    risk_level: RiskLevel
    source: str
    last_updated: datetime