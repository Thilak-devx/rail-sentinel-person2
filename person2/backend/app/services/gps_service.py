from collections import deque
from datetime import datetime, timezone
from typing import Optional
import math

from app.models.schemas import PositionCreate, PositionResponse
from app.core.config import settings
from app.services.map_matching import map_matcher


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


class GPSService:
    def __init__(self, max_history: int = None):
        self.max_history = max_history or settings.position_history_size
        self._positions: dict[str, deque[PositionResponse]] = {}
        self._latest: dict[str, PositionResponse] = {}

    def add_position(self, position: PositionCreate) -> PositionResponse:
        coach_id = position.coach_id

        if coach_id not in self._positions:
            self._positions[coach_id] = deque(maxlen=self.max_history)

        calculated_speed = None
        if coach_id in self._latest:
            prev = self._latest[coach_id]
            dt = (position.timestamp - prev.timestamp).total_seconds()
            if dt > 0:
                distance = haversine_distance(
                    prev.lat, prev.long, position.lat, position.long
                )
                calculated_speed = (distance / dt) * 3.6

        match_result = map_matcher.match_position(position.lat, position.long)

        response = PositionResponse(
            coach_id=coach_id,
            lat=position.lat,
            long=position.long,
            speed=position.speed,
            calculated_speed=round(calculated_speed, 2) if calculated_speed else None,
            timestamp=position.timestamp,
            matched_lat=match_result.matched_lat,
            matched_long=match_result.matched_long,
            match_distance_meters=match_result.distance_meters,
            route_segment_id=match_result.segment_id,
            matched=match_result.matched,
        )

        self._positions[coach_id].append(response)
        self._latest[coach_id] = response

        return response

    def get_latest_positions(self) -> list[PositionResponse]:
        return list(self._latest.values())

    def get_coach_history(self, coach_id: str) -> list[PositionResponse]:
        return list(self._positions.get(coach_id.upper(), []))

    def get_latest_for_coach(self, coach_id: str) -> Optional[PositionResponse]:
        return self._latest.get(coach_id.upper())


gps_service = GPSService()