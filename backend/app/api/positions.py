from fastapi import APIRouter, HTTPException, status

from app.models.schemas import PositionCreate, PositionResponse, HealthResponse
from app.services.gps_service import gps_service

router = APIRouter(prefix="/api/v1", tags=["positions"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        service="RailSentinel Position Service"
    )


@router.post("/position", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
async def receive_position(position: PositionCreate):
    try:
        result = gps_service.add_position(position)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process position: {str(e)}"
        )


@router.get("/live-positions", response_model=list[PositionResponse])
async def get_live_positions():
    return gps_service.get_latest_positions()