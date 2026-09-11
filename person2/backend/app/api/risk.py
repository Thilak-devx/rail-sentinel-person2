from fastapi import APIRouter, HTTPException, status, Query

from app.models.schemas import RiskScoreResponse, RiskLevel
from app.services.risk_service import risk_service
from app.services.segment_registry import segment_registry

router = APIRouter(prefix="/api/v1", tags=["risk"])


@router.get("/risk-score", response_model=RiskScoreResponse)
async def get_risk_score(segment_id: str = Query(..., description="Route segment identifier")):
    # Check if segment is known in our registry
    if not segment_registry.has_segment(segment_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Segment not found"
        )
    
    assessment = await risk_service.get_risk_score(segment_id)
    
    return RiskScoreResponse(
        segment_id=assessment.segment_id,
        risk_level=assessment.risk_level,
        source=assessment.source,
        last_updated=assessment.last_updated,
    )


@router.get("/risk-scores-all")
async def get_all_risk_scores():
    """Return risk scores for every known segment — used by main backend polling."""
    segments = segment_registry.list_segments()
    results = {}
    for seg_id in segments:
        try:
            assessment = await risk_service.get_risk_score(seg_id)
            results[seg_id] = {
                "risk_level": assessment.risk_level,
                "source": assessment.source,
                "last_updated": assessment.last_updated.isoformat(),
            }
        except Exception:
            pass
    return results


@router.get("/provider-status")
async def get_provider_status():
    return risk_service.get_provider_status()