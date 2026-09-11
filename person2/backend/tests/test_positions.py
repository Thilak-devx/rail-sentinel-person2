import pytest
import httpx
import logging
from httpx import AsyncClient, ASGITransport, Response, HTTPStatusError, TimeoutException
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from app.main import app
from app.services.map_matching import map_matcher, MapMatcher, DEMO_ROUTE_GEOJSON
from app.services.risk_service import risk_service, RiskEngine, RiskLevel
from app.services.segment_registry import segment_registry, SegmentRegistry
from app.providers.weather_provider import MockWeatherProvider, WeatherObservation, OpenWeatherProvider
from app.providers.flood_provider import MockFloodProvider, FloodObservation, CWCProvider


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealth:
    async def test_health_endpoint(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "RailSentinel Position Service"


class TestPositionSubmission:
    async def test_valid_position_submission(self, client):
        payload = {
            "coach_id": "S1",
            "lat": 20.2961,
            "long": 85.8245,
            "speed": 42.3,
            "timestamp": "2026-09-06T18:30:00Z"
        }
        response = await client.post("/api/v1/position", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["coach_id"] == "S1"
        assert data["lat"] == 20.2961
        assert data["long"] == 85.8245
        assert data["speed"] == 42.3
        assert "calculated_speed" in data

    async def test_invalid_latitude(self, client):
        payload = {
            "coach_id": "S1",
            "lat": 95.0,
            "long": 85.8245,
            "speed": 42.3,
            "timestamp": "2026-09-06T18:30:00Z"
        }
        response = await client.post("/api/v1/position", json=payload)
        assert response.status_code == 422

    async def test_invalid_longitude(self, client):
        payload = {
            "coach_id": "S1",
            "lat": 20.2961,
            "long": 200.0,
            "speed": 42.3,
            "timestamp": "2026-09-06T18:30:00Z"
        }
        response = await client.post("/api/v1/position", json=payload)
        assert response.status_code == 422

    async def test_missing_coach_id(self, client):
        payload = {
            "lat": 20.2961,
            "long": 85.8245,
            "speed": 42.3,
            "timestamp": "2026-09-06T18:30:00Z"
        }
        response = await client.post("/api/v1/position", json=payload)
        assert response.status_code == 422

    async def test_coach_id_normalization(self, client):
        payload = {
            "coach_id": "  s1  ",
            "lat": 20.2961,
            "long": 85.8245,
            "speed": 42.3,
            "timestamp": "2026-09-06T18:30:00Z"
        }
        response = await client.post("/api/v1/position", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["coach_id"] == "S1"


class TestLivePositions:
    async def test_live_positions_empty(self, client):
        response = await client.get("/api/v1/live-positions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_live_positions_multiple_coaches(self, client):
        positions = [
            {"coach_id": "S1", "lat": 20.2961, "long": 85.8245, "speed": 42.3, "timestamp": "2026-09-06T18:30:00Z"},
            {"coach_id": "S2", "lat": 20.2970, "long": 85.8250, "speed": 45.0, "timestamp": "2026-09-06T18:30:05Z"},
            {"coach_id": "B1", "lat": 20.2980, "long": 85.8260, "speed": 38.0, "timestamp": "2026-09-06T18:30:10Z"},
        ]
        for pos in positions:
            await client.post("/api/v1/position", json=pos)

        response = await client.get("/api/v1/live-positions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        coach_ids = {p["coach_id"] for p in data}
        assert coach_ids == {"S1", "S2", "B1"}


class TestSpeedCalculation:
    async def test_calculated_speed_from_consecutive_points(self, client):
        t1 = "2026-09-06T18:30:00Z"
        t2 = "2026-09-06T18:30:10Z"
        
        pos1 = {"coach_id": "S1", "lat": 20.2961, "long": 85.8245, "speed": 40.0, "timestamp": t1}
        pos2 = {"coach_id": "S1", "lat": 20.2971, "long": 85.8255, "speed": 45.0, "timestamp": t2}
        
        await client.post("/api/v1/position", json=pos1)
        response = await client.post("/api/v1/position", json=pos2)
        
        assert response.status_code == 201
        data = response.json()
        assert data["calculated_speed"] is not None
        assert data["calculated_speed"] > 0


class TestRiskEndpoints:
    async def test_unknown_segment(self, client):
        response = await client.get("/api/v1/risk-score?segment_id=UNKNOWN")
        assert response.status_code == 404


class TestAPIHealth:
    async def test_root_endpoint(self, client):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "RailSentinel" in data["message"]


class TestMapMatching:
    def test_point_on_route(self):
        # Use a coordinate from the real route (first coordinate)
        result = map_matcher.match_position(20.277631, 85.8504012)
        assert result.matched is True
        assert result.matched_lat is not None
        assert result.matched_long is not None
        assert result.distance_meters is not None
        assert result.distance_meters < 10
        assert result.segment_id is not None

    def test_point_near_route(self):
        # Use a coordinate slightly off the route but within 100m
        result = map_matcher.match_position(20.2777, 85.8505)
        assert result.matched is True
        assert result.distance_meters is not None
        assert result.distance_meters < 100

    def test_point_far_from_route(self):
        result = map_matcher.match_position(20.3500, 85.9000)
        assert result.matched is False
        assert result.reason == "outside_matching_threshold"
        assert result.distance_meters is not None
        assert result.distance_meters > 100

    def test_no_route_loaded(self):
        matcher = MapMatcher()
        result = matcher.match_position(20.2961, 85.8245)
        assert result.matched is False
        assert result.reason == "no_route_loaded"

    def test_coordinate_ordering(self):
        # Use a coordinate from the real route
        result = map_matcher.match_position(20.277631, 85.8504012)
        assert result.matched is True
        assert abs(result.matched_lat - 20.277631) < 0.001
        assert abs(result.matched_long - 85.8504012) < 0.001

    async def test_position_api_includes_match_fields(self, client):
        # Use a coordinate from the real route
        payload = {
            "coach_id": "S1",
            "lat": 20.277631,
            "long": 85.8504012,
            "speed": 42.3,
            "timestamp": "2026-09-06T18:30:00Z"
        }
        response = await client.post("/api/v1/position", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "matched" in data
        assert "matched_lat" in data
        assert "matched_long" in data
        assert "match_distance_meters" in data
        assert "route_segment_id" in data
        assert data["matched"] is True

    async def test_multiple_coaches_map_matching(self, client):
        # Use coordinates from the real route
        positions = [
            {"coach_id": "M1", "lat": 20.277631, "long": 85.8504012, "speed": 42.3, "timestamp": "2026-09-06T18:30:00Z"},
            {"coach_id": "M2", "lat": 20.2777, "long": 85.8505, "speed": 45.0, "timestamp": "2026-09-06T18:30:05Z"},
        ]
        for pos in positions:
            await client.post("/api/v1/position", json=pos)

        response = await client.get("/api/v1/live-positions")
        assert response.status_code == 200
        data = response.json()
        coach_ids = {p["coach_id"] for p in data}
        assert "M1" in coach_ids
        assert "M2" in coach_ids
        for pos in data:
            if pos["coach_id"] in {"M1", "M2"}:
                assert "matched" in pos
                assert pos["matched"] is True

    async def test_existing_speed_calculation_still_works(self, client):
        t1 = "2026-09-06T18:30:00Z"
        t2 = "2026-09-06T18:30:10Z"
        
        # Use coordinates from the real route
        pos1 = {"coach_id": "S1", "lat": 20.277631, "long": 85.8504012, "speed": 40.0, "timestamp": t1}
        pos2 = {"coach_id": "S1", "lat": 20.2777, "long": 85.8505, "speed": 45.0, "timestamp": t2}
        
        await client.post("/api/v1/position", json=pos1)
        response = await client.post("/api/v1/position", json=pos2)
        
        assert response.status_code == 201
        data = response.json()
        assert data["calculated_speed"] is not None
        assert data["calculated_speed"] > 0
        assert "matched" in data


class TestRiskEngine:
    def test_no_flood_no_bad_weather_none(self):
        flood = FloodObservation(
            segment_id="TEST_1",
            water_level_m=5.0,
            warning_level_m=8.0,
            danger_level_m=10.0,
            status="normal",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        weather = WeatherObservation(
            segment_id="TEST_1",
            precipitation_mm=0.0,
            visibility_m=10000.0,
            condition="clear",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        engine = RiskEngine(MockWeatherProvider(), MockFloodProvider())
        result = engine.assess_risk_with_observations("TEST_1", flood, weather)
        assert result.risk_level == RiskLevel.NONE
        assert result.source == "none"
    
    def test_heavy_rain_low(self):
        flood = FloodObservation(
            segment_id="TEST_2",
            water_level_m=5.0,
            warning_level_m=8.0,
            danger_level_m=10.0,
            status="normal",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        weather = WeatherObservation(
            segment_id="TEST_2",
            precipitation_mm=15.0,
            visibility_m=5000.0,
            condition="heavy_rain",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        engine = RiskEngine(MockWeatherProvider(), MockFloodProvider())
        result = engine.assess_risk_with_observations("TEST_2", flood, weather)
        assert result.risk_level == RiskLevel.LOW
        assert result.source == "weather"
    
    def test_fog_low(self):
        flood = FloodObservation(
            segment_id="TEST_3",
            water_level_m=5.0,
            warning_level_m=8.0,
            danger_level_m=10.0,
            status="normal",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        weather = WeatherObservation(
            segment_id="TEST_3",
            precipitation_mm=0.5,
            visibility_m=200.0,
            condition="fog",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        engine = RiskEngine(MockWeatherProvider(), MockFloodProvider())
        result = engine.assess_risk_with_observations("TEST_3", flood, weather)
        assert result.risk_level == RiskLevel.LOW
        assert result.source == "weather"
    
    def test_water_above_warning_moderate(self):
        flood = FloodObservation(
            segment_id="TEST_4",
            water_level_m=9.0,
            warning_level_m=8.0,
            danger_level_m=10.0,
            status="warning",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        weather = WeatherObservation(
            segment_id="TEST_4",
            precipitation_mm=0.0,
            visibility_m=10000.0,
            condition="clear",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        engine = RiskEngine(MockWeatherProvider(), MockFloodProvider())
        result = engine.assess_risk_with_observations("TEST_4", flood, weather)
        assert result.risk_level == RiskLevel.MODERATE
        assert result.source == "flood"
    
    def test_water_at_danger_severe(self):
        flood = FloodObservation(
            segment_id="TEST_5",
            water_level_m=10.5,
            warning_level_m=8.0,
            danger_level_m=10.0,
            status="danger",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        weather = WeatherObservation(
            segment_id="TEST_5",
            precipitation_mm=0.0,
            visibility_m=10000.0,
            condition="clear",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        engine = RiskEngine(MockWeatherProvider(), MockFloodProvider())
        result = engine.assess_risk_with_observations("TEST_5", flood, weather)
        assert result.risk_level == RiskLevel.SEVERE
        assert result.source == "flood"
    
    def test_flood_plus_heavy_rain_deterministic(self):
        flood = FloodObservation(
            segment_id="TEST_6",
            water_level_m=9.0,
            warning_level_m=8.0,
            danger_level_m=10.0,
            status="warning",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        weather = WeatherObservation(
            segment_id="TEST_6",
            precipitation_mm=20.0,
            visibility_m=5000.0,
            condition="heavy_rain",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        engine = RiskEngine(MockWeatherProvider(), MockFloodProvider())
        result = engine.assess_risk_with_observations("TEST_6", flood, weather)
        assert result.risk_level == RiskLevel.MODERATE
        assert result.source == "flood"
    
    def test_provider_failure_handling(self):
        flood = FloodObservation(
            segment_id="TEST_7",
            water_level_m=None,
            warning_level_m=None,
            danger_level_m=None,
            status="unknown",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        weather = WeatherObservation(
            segment_id="TEST_7",
            precipitation_mm=0.0,
            visibility_m=10000.0,
            condition="clear",
            observed_at=datetime(2026, 9, 6, 18, 30, 0),
            source="mock",
        )
        engine = RiskEngine(MockWeatherProvider(), MockFloodProvider())
        result = engine.assess_risk_with_observations("TEST_7", flood, weather)
        import asyncio
        result = asyncio.run(engine.assess_risk("TEST_7"))
        assert result.risk_level == RiskLevel.NONE


class TestRiskEndpoints:
    @pytest.fixture(autouse=True)
    async def clear_risk_cache(self):
        from app.services.risk_service import risk_service
        risk_service.clear_cache()
    
    @pytest.fixture(autouse=True)
    def use_mock_providers(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, 'weather_provider', 'mock')
        monkeypatch.setattr(settings, 'flood_provider', 'mock')
        # Need to recreate risk_service with mock providers
        from app.services.risk_service import create_risk_service, risk_service as rs
        rs.__init__(create_risk_service().engine.weather_provider, create_risk_service().engine.flood_provider)
    
    async def test_unknown_segment(self, client):
        response = await client.get("/api/v1/risk-score?segment_id=UNKNOWN")
        assert response.status_code == 404
    
    async def test_risk_score_none(self, client):
        response = await client.get("/api/v1/risk-score?segment_id=SEG_01")
        assert response.status_code == 200
        data = response.json()
        assert data["segment_id"] == "SEG_01"
        assert data["risk_level"] == "none"
        assert data["source"] == "none"
        assert "last_updated" in data
    
    async def test_risk_score_low_heavy_rain(self, client):
        response = await client.get("/api/v1/risk-score?segment_id=SEG_LOW_RAIN")
        assert response.status_code == 200
        data = response.json()
        assert data["segment_id"] == "SEG_LOW_RAIN"
        assert data["risk_level"] == "low"
        assert data["source"] == "weather"
    
    async def test_risk_score_low_fog(self, client):
        response = await client.get("/api/v1/risk-score?segment_id=SEG_LOW_FOG")
        assert response.status_code == 200
        data = response.json()
        assert data["segment_id"] == "SEG_LOW_FOG"
        assert data["risk_level"] == "low"
        assert data["source"] == "weather"
    
    async def test_risk_score_moderate_flood(self, client):
        response = await client.get("/api/v1/risk-score?segment_id=SEG_MODERATE_FLOOD")
        assert response.status_code == 200
        data = response.json()
        assert data["segment_id"] == "SEG_MODERATE_FLOOD"
        assert data["risk_level"] == "moderate"
        assert data["source"] == "flood"
    
    async def test_response_schema(self, client):
        response = await client.get("/api/v1/risk-score?segment_id=SEG_01")
        assert response.status_code == 200
        data = response.json()
        assert "segment_id" in data
        assert "risk_level" in data
        assert "source" in data
        assert "last_updated" in data
        assert data["risk_level"] in ["none", "low", "moderate", "severe"]
        assert data["source"] in ["flood", "weather", "none"]


class TestOpenWeatherProvider:
    @pytest.fixture
    def provider(self):
        return OpenWeatherProvider(api_key="test_key")
    
    @pytest.mark.asyncio
    async def test_successful_weather_response(self, provider):
        mock_response_data = {
            "coord": {"lon": 85.8245, "lat": 20.2961},
            "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
            "main": {"temp": 30.0, "humidity": 60},
            "visibility": 10000,
            "dt": 1694025000,
        }
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=Response(200, json=mock_response_data, request=httpx.Request("GET", "https://api.openweathermap.org/data/2.5/weather")))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_weather("SEG_01")
        
        assert result.segment_id == "SEG_01"
        assert result.source == "openweathermap"
        assert result.precipitation_mm == 0.0
        assert result.visibility_m == 10000
        assert result.condition == "clear"
        assert result.raw_data is not None
    
    @pytest.mark.asyncio
    async def test_rain_present(self, provider):
        mock_response_data = {
            "coord": {"lon": 85.8245, "lat": 20.2961},
            "weather": [{"id": 501, "main": "Rain", "description": "moderate rain", "icon": "10d"}],
            "main": {"temp": 25.0, "humidity": 85},
            "rain": {"1h": 5.5},
            "visibility": 5000,
            "dt": 1694025000,
        }
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=Response(200, json=mock_response_data, request=httpx.Request("GET", "https://api.openweathermap.org/data/2.5/weather")))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_weather("SEG_01")
        
        assert result.precipitation_mm == 5.5
        assert result.condition == "rain"
        assert result.visibility_m == 5000
    
    @pytest.mark.asyncio
    async def test_heavy_rain(self, provider):
        mock_response_data = {
            "coord": {"lon": 85.8245, "lat": 20.2961},
            "weather": [{"id": 502, "main": "Rain", "description": "heavy intensity rain", "icon": "10d"}],
            "main": {"temp": 24.0, "humidity": 90},
            "rain": {"1h": 15.0},
            "visibility": 3000,
            "dt": 1694025000,
        }
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=Response(200, json=mock_response_data, request=httpx.Request("GET", "https://api.openweathermap.org/data/2.5/weather")))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_weather("SEG_01")
        
        assert result.precipitation_mm == 15.0
        assert result.condition == "heavy_rain"
    
    @pytest.mark.asyncio
    async def test_no_rain(self, provider):
        mock_response_data = {
            "coord": {"lon": 85.8245, "lat": 20.2961},
            "weather": [{"id": 801, "main": "Clouds", "description": "few clouds", "icon": "02d"}],
            "main": {"temp": 31.0, "humidity": 50},
            "visibility": 10000,
            "dt": 1694025000,
        }
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=Response(200, json=mock_response_data, request=httpx.Request("GET", "https://api.openweathermap.org/data/2.5/weather")))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_weather("SEG_01")
        
        assert result.precipitation_mm == 0.0
        assert result.condition == "clouds"
    
    @pytest.mark.asyncio
    async def test_fog_mist(self, provider):
        mock_response_data = {
            "coord": {"lon": 85.8245, "lat": 20.2961},
            "weather": [{"id": 701, "main": "Mist", "description": "mist", "icon": "50d"}],
            "main": {"temp": 22.0, "humidity": 95},
            "visibility": 500,
            "dt": 1694025000,
        }
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=Response(200, json=mock_response_data, request=httpx.Request("GET", "https://api.openweathermap.org/data/2.5/weather")))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_weather("SEG_01")
        
        assert result.visibility_m == 500
        assert result.condition == "fog"
    
    @pytest.mark.asyncio
    async def test_http_error(self, provider):
        mock_client = AsyncMock()
        request = httpx.Request("GET", "https://api.openweathermap.org/data/2.5/weather")
        response = Response(401, json={"cod": 401, "message": "Invalid API key"}, request=request)
        mock_client.get = AsyncMock(side_effect=HTTPStatusError("401 Unauthorized", request=request, response=response))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_weather("SEG_01")
        
        assert result.condition == "http_error"
        assert result.source == "openweathermap"
        assert result.raw_data is not None
        assert "http_401" in str(result.raw_data.get("error", ""))
    
    @pytest.mark.asyncio
    async def test_timeout(self, provider):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=TimeoutException("Request timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_weather("SEG_01")
        
        assert result.condition == "timeout"
        assert result.source == "openweathermap"
        assert result.raw_data is not None
        assert "timeout" in str(result.raw_data.get("error", ""))
    
    @pytest.mark.asyncio
    async def test_malformed_response(self, provider):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=Response(200, json={"invalid": "response"}, request=httpx.Request("GET", "https://api.openweathermap.org/data/2.5/weather")))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.get_weather("SEG_01")
        
        assert result.source == "openweathermap"
        assert result.precipitation_mm == 0.0
        assert result.visibility_m is None
    
    @pytest.mark.asyncio
    async def test_missing_api_key(self):
        with pytest.raises(ValueError, match="OpenWeather API key is required"):
            OpenWeatherProvider(api_key="")
    
    @pytest.mark.asyncio
    async def test_unknown_segment(self, provider):
        result = await provider.get_weather("UNKNOWN_SEGMENT")
        
        assert result.segment_id == "UNKNOWN_SEGMENT"
        assert result.condition == "unknown"
        assert result.source == "openweathermap"


class TestOpenWeatherProviderLogging:
    @pytest.fixture
    def provider(self):
        return OpenWeatherProvider(api_key="test_key")
    
    @pytest.mark.asyncio
    async def test_logs_request_started(self, provider, caplog):
        mock_response_data = {
            "coord": {"lon": 85.8245, "lat": 20.2961},
            "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
            "main": {"temp": 30.0, "humidity": 60},
            "visibility": 10000,
            "dt": 1694025000,
        }
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=Response(200, json=mock_response_data, request=httpx.Request("GET", "https://api.openweathermap.org/data/2.5/weather")))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with caplog.at_level(logging.INFO):
            with patch("httpx.AsyncClient", return_value=mock_client):
                await provider.get_weather("SEG_01")
        
        assert any("openweathermap request started" in msg for msg in caplog.messages)
        assert any("SEG_01" in msg for msg in caplog.messages)
        assert any("lat=20.2961" in msg for msg in caplog.messages)
        assert any("lon=85.8245" in msg for msg in caplog.messages)
        # Ensure no API key in logs
        assert not any("test_key" in msg for msg in caplog.messages)
        assert not any("appid" in msg for msg in caplog.messages)
    
    @pytest.mark.asyncio
    async def test_logs_request_success(self, provider, caplog):
        mock_response_data = {
            "coord": {"lon": 85.8245, "lat": 20.2961},
            "weather": [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}],
            "main": {"temp": 30.0, "humidity": 60},
            "visibility": 10000,
            "dt": 1694025000,
        }
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=Response(200, json=mock_response_data, request=httpx.Request("GET", "https://api.openweathermap.org/data/2.5/weather")))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with caplog.at_level(logging.INFO):
            with patch("httpx.AsyncClient", return_value=mock_client):
                await provider.get_weather("SEG_01")
        
        assert any("openweathermap request success" in msg for msg in caplog.messages)
        assert any("SEG_01" in msg for msg in caplog.messages)
        assert any("200" in msg for msg in caplog.messages)
        # Ensure no API key in logs
        assert not any("test_key" in msg for msg in caplog.messages)
    
    @pytest.mark.asyncio
    async def test_logs_timeout(self, provider, caplog):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=TimeoutException("Request timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with caplog.at_level(logging.WARNING):
            with patch("httpx.AsyncClient", return_value=mock_client):
                await provider.get_weather("SEG_01")
        
        assert any("openweathermap request timeout" in msg for msg in caplog.messages)
        assert any("SEG_01" in msg for msg in caplog.messages)
        assert not any("test_key" in msg for msg in caplog.messages)
    
    @pytest.mark.asyncio
    async def test_logs_http_error(self, provider, caplog):
        mock_client = AsyncMock()
        request = httpx.Request("GET", "https://api.openweathermap.org/data/2.5/weather")
        response = Response(401, json={"cod": 401, "message": "Invalid API key"}, request=request)
        mock_client.get = AsyncMock(side_effect=HTTPStatusError("401 Unauthorized", request=request, response=response))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with caplog.at_level(logging.WARNING):
            with patch("httpx.AsyncClient", return_value=mock_client):
                await provider.get_weather("SEG_01")
        
        assert any("openweathermap request http_error" in msg for msg in caplog.messages)
        assert any("SEG_01" in msg for msg in caplog.messages)
        assert any("401" in msg for msg in caplog.messages)
        assert not any("test_key" in msg for msg in caplog.messages)
    
    @pytest.mark.asyncio
    async def test_logs_generic_error(self, provider, caplog):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=ValueError("unexpected error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        with caplog.at_level(logging.ERROR):
            with patch("httpx.AsyncClient", return_value=mock_client):
                await provider.get_weather("SEG_01")
        
        assert any("openweathermap request error" in msg for msg in caplog.messages)
        assert any("SEG_01" in msg for msg in caplog.messages)
        assert not any("test_key" in msg for msg in caplog.messages)
        # Should only log error type, not details
        assert any("ValueError" in msg for msg in caplog.messages)


class TestCWCProvider:
    def test_provider_name(self):
        provider = CWCProvider()
        assert provider.get_provider_name() == "cwc"
    
    @pytest.mark.asyncio
    async def test_returns_unavailable_for_unknown_segment(self):
        provider = CWCProvider()
        result = await provider.get_flood_status("UNKNOWN_SEGMENT")
        
        assert result.segment_id == "UNKNOWN_SEGMENT"
        assert result.status == "provider_unavailable"
        assert result.source == "cwc"
        assert result.water_level_m is None
        assert result.raw_data is not None
        assert "No CWC station mapping" in str(result.raw_data.get("error", ""))
    
    @pytest.mark.asyncio
    async def test_returns_unavailable_for_unsupported_segment(self):
        provider = CWCProvider()
        result = await provider.get_flood_status("Naraj")
        
        assert result.segment_id == "Naraj"
        assert result.status == "provider_unavailable"
        assert result.source == "cwc"
        assert result.water_level_m is None
        assert result.raw_data is not None
        assert "no verified NWDP telemetry match" in str(result.raw_data.get("error", ""))


class TestCWCProvider2026Resources:
    """Tests for CWC 2026-2030 resources and freshness handling."""
    
    @pytest.mark.asyncio
    async def test_2026_resource_ids_configured(self):
        """Verify 2026-2030 resource IDs are configured."""
        provider = CWCProvider()
        assert provider.RESOURCE_IDS["subarnarekha"] == "1e23cbb8-c1ce-4434-a635-8231535305f3"
        assert provider.RESOURCE_IDS["brahmani_baitarni"] == "178082a5-2a2b-445e-b059-97337f325cd7"
        assert provider.RESOURCE_IDS["mahanadi"] == "0ab89c38-558f-47b5-818e-eda9f17cffc4"
    
    @pytest.mark.asyncio
    async def test_station_resource_mapping(self):
        """Verify station to resource mappings."""
        provider = CWCProvider()
        assert provider.STATION_RESOURCE_MAP["Rajghat"][0] == "subarnarekha"
        assert provider.STATION_RESOURCE_MAP["Anandpur"][0] == "brahmani_baitarni"
        assert provider.STATION_RESOURCE_MAP["Akhuapada"][0] == "brahmani_baitarni"
        assert provider.STATION_RESOURCE_MAP["Jenapur"][0] == "brahmani_baitarni"
        assert provider.STATION_RESOURCE_MAP["Alipingal"][0] == "mahanadi"
        assert provider.STATION_RESOURCE_MAP["Nimapara"][0] == "mahanadi"
    
    @pytest.mark.asyncio
    async def test_freshness_threshold_configurable(self):
        """Verify freshness threshold can be configured."""
        provider = CWCProvider(freshness_threshold_days=7.0)
        assert provider.freshness_threshold_days == 7.0
        
        provider_default = CWCProvider()
        assert provider_default.freshness_threshold_days == 30.0
    
    @pytest.mark.asyncio
    async def test_evaluate_freshness_fresh(self):
        """Test freshness evaluation for fresh data."""
        provider = CWCProvider(freshness_threshold_days=30.0)
        recent_time = datetime.now(timezone.utc)
        freshness = provider._evaluate_freshness("Rajghat", recent_time)
        
        assert freshness["status"] == "fresh"
        assert freshness["is_fresh"] is True
        assert freshness["is_stale"] is False
        assert freshness["age_days"] is not None
        assert freshness["age_days"] <= 30.0
    
    @pytest.mark.asyncio
    async def test_evaluate_freshness_stale(self):
        """Test freshness evaluation for stale data."""
        provider = CWCProvider(freshness_threshold_days=30.0)
        old_time = datetime.now(timezone.utc) - timedelta(days=60)
        freshness = provider._evaluate_freshness("Rajghat", old_time)
        
        assert freshness["status"] == "stale"
        assert freshness["is_fresh"] is False
        assert freshness["is_stale"] is True
        assert freshness["age_days"] is not None
        assert freshness["age_days"] > 30.0
    
    @pytest.mark.asyncio
    async def test_evaluate_freshness_no_timestamp(self):
        """Test freshness evaluation when no timestamp available."""
        provider = CWCProvider()
        freshness = provider._evaluate_freshness("Rajghat", None)
        
        assert freshness["status"] == "unknown"
        assert freshness["is_unavailable"] is True
        assert freshness["age_days"] is None
        assert "error" in freshness
    
    @pytest.mark.asyncio
    async def test_unavailable_station_alipingal(self):
        """Test that Alipingal returns provider_unavailable (not in 2026-2030 resource)."""
        provider = CWCProvider()
        result = await provider.get_flood_status("Alipingal")
        
        assert result.segment_id == "Alipingal"
        assert result.status == "provider_unavailable"
        assert result.source == "cwc"
        assert result.water_level_m is None
        assert result.raw_data is not None
        assert "not present in 2026-2030" in str(result.raw_data.get("error", ""))
        assert result.raw_data.get("freshness") == "unavailable"
    
    @pytest.mark.asyncio
    async def test_freshness_info_included_in_raw_data(self):
        """Test that freshness info is included in raw_data for available stations."""
        provider = CWCProvider()
        # Use a station that we know returns data
        result = await provider.get_flood_status("Rajghat")
        
        assert result.raw_data is not None
        assert "freshness" in result.raw_data
        freshness = result.raw_data["freshness"]
        assert "status" in freshness
        assert "age_days" in freshness
        assert "is_fresh" in freshness
        assert "is_stale" in freshness
        assert "observed_at" in freshness
    
    @pytest.mark.asyncio
    async def test_threshold_comparison_still_works(self):
        """Test that threshold comparison still works correctly."""
        provider = CWCProvider()
        result = await provider.get_flood_status("Rajghat")
        
        assert result.warning_level_m == 9.45
        assert result.danger_level_m == 10.36
        assert result.water_level_m is not None
        # Rajghat water level (3.8) is below warning (9.45) -> status should be normal
        assert result.status == "normal"
    
    @pytest.mark.asyncio
    async def test_provider_status_includes_station_count(self):
        """Test provider status includes correct station count."""
        provider = CWCProvider()
        status = provider.get_provider_status()
        
        assert status.station_count == 6
        assert set(status.supported_stations) == {
            "Rajghat", "Anandpur", "Akhuapada", "Jenapur", "Alipingal", "Nimapara"
        }


class TestProviderStatusEndpoint:
    @pytest.fixture(autouse=True)
    async def clear_risk_cache(self):
        from app.services.risk_service import risk_service
        risk_service.clear_cache()
    
    @pytest.fixture(autouse=True)
    def use_mock_providers(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, 'weather_provider', 'mock')
        monkeypatch.setattr(settings, 'flood_provider', 'mock')
        from app.services.risk_service import create_risk_service, risk_service as rs
        rs.__init__(create_risk_service().engine.weather_provider, create_risk_service().engine.flood_provider)
    
    async def test_provider_status_mock(self, client):
        response = await client.get("/api/v1/provider-status")
        assert response.status_code == 200
        data = response.json()
        assert data["weather_provider"] == "mock"
        assert data["weather_api_configured"] is False
        assert data["last_weather_fetch_at"] is None
        assert data["last_weather_http_status"] is None
        assert data["last_weather_source"] is None
        assert data["cache_enabled"] is True
        assert data["cache_refresh_seconds"] == 600
    
    async def test_provider_status_openweather(self, client, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, 'weather_provider', 'openweathermap')
        monkeypatch.setattr(settings, 'openweather_api_key', 'test_key')
        from app.services.risk_service import create_risk_service, risk_service as rs
        rs.__init__(create_risk_service().engine.weather_provider, create_risk_service().engine.flood_provider)
        
        response = await client.get("/api/v1/provider-status")
        assert response.status_code == 200
        data = response.json()
        assert data["weather_provider"] == "openweathermap"
        assert data["weather_api_configured"] is True
        assert data["last_weather_fetch_at"] is None
        assert data["last_weather_http_status"] is None
        assert data["last_weather_source"] is None
        assert data["cache_enabled"] is True
        assert data["cache_refresh_seconds"] == 600
    
    async def test_provider_status_no_api_key_exposure(self, client):
        response = await client.get("/api/v1/provider-status")
        assert response.status_code == 200
        data = response.json()
        # Ensure no API key is in the response
        response_text = str(data)
        assert "test_key" not in response_text
        assert "api_key" not in response_text.lower()
        assert "appid" not in response_text.lower()
    
    async def test_provider_status_metadata_updates_on_call(self, client):
        # This test verifies the metadata structure is correct
        response = await client.get("/api/v1/provider-status")
        assert response.status_code == 200
        data = response.json()
        # Check all required fields exist
        required_fields = [
            "weather_provider",
            "weather_api_configured",
            "last_weather_fetch_at",
            "last_weather_http_status",
            "last_weather_source",
            "cache_enabled",
            "cache_refresh_seconds"
        ]
        for field in required_fields:
            assert field in data


class TestSegmentRegistry:
    """Tests for the segment registry and real route segmentation."""

    def test_segment_generation_produces_46_real_segments(self):
        """Test that the real route is split into 46 segments."""
        real_segments = [s for s in segment_registry.list_segments() if s.startswith("REAL_RAIL_SEG_")]
        assert len(real_segments) == 46

    def test_segment_ids_are_deterministic(self):
        """Test that segment IDs follow the expected pattern."""
        real_segments = [s for s in segment_registry.list_segments() if s.startswith("REAL_RAIL_SEG_")]
        # Should be REAL_RAIL_SEG_01 through REAL_RAIL_SEG_46
        for i in range(1, 47):
            expected_id = f"REAL_RAIL_SEG_{i:02d}"
            assert expected_id in segment_registry._segments

    def test_segment_ordering_is_correct(self):
        """Test that segments are ordered correctly by sequence."""
        for i in range(1, 47):
            seg_id = f"REAL_RAIL_SEG_{i:02d}"
            seg_info = segment_registry.get_segment_info(seg_id)
            assert seg_info is not None
            assert seg_info.sequence == i

    def test_segment_geometries_derived_from_real_geojson(self):
        """Test that segment geometries are derived from the real GeoJSON."""
        for i in range(1, 47):
            seg_id = f"REAL_RAIL_SEG_{i:02d}"
            seg_info = segment_registry.get_segment_info(seg_id)
            assert seg_info is not None
            assert seg_info.geometry is not None
            # Geometry should be a LineString
            from shapely.geometry import LineString
            assert isinstance(seg_info.geometry, LineString)
            # Should have at least 2 points
            assert len(list(seg_info.geometry.coords)) >= 2

    def test_each_segment_has_representative_coordinates(self):
        """Test that each segment has representative lat/long (centroid)."""
        for i in range(1, 47):
            seg_id = f"REAL_RAIL_SEG_{i:02d}"
            seg_info = segment_registry.get_segment_info(seg_id)
            assert seg_info is not None
            assert seg_info.representative_lat is not None
            assert seg_info.representative_long is not None
            # Should be within the route bounds
            assert 20.2 <= seg_info.representative_lat <= 20.3
            assert 85.8 <= seg_info.representative_long <= 85.9

    def test_segment_lengths_are_reasonable(self):
        """Test that segment lengths are reasonable (target ~1.35km average for 46 segments over 62.4km)."""
        lengths = []
        for i in range(1, 47):
            seg_id = f"REAL_RAIL_SEG_{i:02d}"
            seg_info = segment_registry.get_segment_info(seg_id)
            assert seg_info is not None
            assert seg_info.length_meters is not None
            # Should be roughly 1.35km average (62.4km / 46 segments)
            assert 300 <= seg_info.length_meters <= 4000
            lengths.append(seg_info.length_meters)
        
        # Average should be close to 1356m (62.4km / 46)
        avg_length = sum(lengths) / len(lengths)
        assert 1200 <= avg_length <= 1500


class TestMapMatchingRealSegments:
    """Tests for map matching with real railway segments."""

    def test_map_matching_returns_correct_real_segment_id(self):
        """Test that map matching returns the correct REAL_RAIL_SEG_XX."""
        # Test first segment
        result = map_matcher.match_position(20.277631, 85.8504012)
        assert result.matched is True
        assert result.segment_id == "REAL_RAIL_SEG_01"

    def test_map_matching_returns_correct_segment_for_middle_of_route(self):
        """Test map matching for a point in the middle of the route."""
        # Use a coordinate from the middle of the route (around segment 23)
        result = map_matcher.match_position(20.265, 85.843)
        assert result.matched is True
        assert result.segment_id is not None
        assert result.segment_id.startswith("REAL_RAIL_SEG_")
        assert result.distance_meters is not None
        assert result.distance_meters < 100

    def test_map_matching_returns_correct_segment_for_end_of_route(self):
        """Test map matching for a point near the end of the route."""
        # Test near the end of the route (around segment 46)
        result = map_matcher.match_position(20.235, 85.815)
        assert result.matched is True
        assert result.segment_id is not None
        assert result.segment_id.startswith("REAL_RAIL_SEG_")
        assert result.distance_meters is not None
        assert result.distance_meters < 100

    def test_far_away_gps_remains_unmatched(self):
        """Test that GPS points far from the route remain unmatched."""
        result = map_matcher.match_position(20.3500, 85.9000)
        assert result.matched is False
        assert result.reason == "outside_matching_threshold"
        assert result.distance_meters is not None
        assert result.distance_meters > 100

    def test_unknown_segment_risk_lookup_returns_404(self):
        """Test that unknown segment ID returns 404."""
        # This is tested via the API, but we can also test the registry
        assert not segment_registry.has_segment("UNKNOWN_SEGMENT")
        assert not segment_registry.has_segment("INVALID_SEGMENT")


class TestRiskLookupForRealSegments:
    """Tests for risk lookup with real railway segments."""

    @pytest.fixture(autouse=True)
    async def clear_risk_cache(self):
        from app.services.risk_service import risk_service
        risk_service.clear_cache()

    @pytest.fixture(autouse=True)
    def use_mock_providers(self, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, 'weather_provider', 'mock')
        monkeypatch.setattr(settings, 'flood_provider', 'mock')
        from app.services.risk_service import create_risk_service, risk_service as rs
        rs.__init__(create_risk_service().engine.weather_provider, create_risk_service().engine.flood_provider)

    @pytest.mark.asyncio
    async def test_risk_lookup_for_first_real_segment(self, client):
        """Test risk lookup for the first real segment."""
        response = await client.get("/api/v1/risk-score?segment_id=REAL_RAIL_SEG_01")
        assert response.status_code == 200
        data = response.json()
        assert data["segment_id"] == "REAL_RAIL_SEG_01"
        assert data["risk_level"] in ["none", "low", "moderate", "severe"]
        assert data["source"] in ["flood", "weather", "none"]

    @pytest.mark.asyncio
    async def test_risk_lookup_for_middle_segment(self, client):
        """Test risk lookup for a middle segment."""
        response = await client.get("/api/v1/risk-score?segment_id=REAL_RAIL_SEG_23")
        assert response.status_code == 200
        data = response.json()
        assert data["segment_id"] == "REAL_RAIL_SEG_23"

    @pytest.mark.asyncio
    async def test_risk_lookup_for_last_segment(self, client):
        """Test risk lookup for the last segment."""
        response = await client.get("/api/v1/risk-score?segment_id=REAL_RAIL_SEG_46")
        assert response.status_code == 200
        data = response.json()
        assert data["segment_id"] == "REAL_RAIL_SEG_46"

    @pytest.mark.asyncio
    async def test_risk_lookup_for_multiple_real_segments(self, client):
        """Test risk lookup for multiple real segments returns valid data."""
        for seg_num in [1, 10, 20, 30, 40, 46]:
            seg_id = f"REAL_RAIL_SEG_{seg_num:02d}"
            response = await client.get(f"/api/v1/risk-score?segment_id={seg_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["segment_id"] == seg_id
            assert data["risk_level"] in ["none", "low", "moderate", "severe"]
            assert data["source"] in ["flood", "weather", "none"]

    @pytest.mark.asyncio
    async def test_risk_cache_works_for_real_segments(self, client):
        """Test that the 10-minute risk cache works for real segments."""
        from app.services.risk_service import risk_service
        
        risk_service.clear_cache()
        
        # First request - should hit OpenWeather (or mock)
        response1 = await client.get("/api/v1/risk-score?segment_id=REAL_RAIL_SEG_01")
        assert response1.status_code == 200
        data1 = response1.json()
        last_updated_1 = data1["last_updated"]
        
        # Second request within cache window - should use cache
        response2 = await client.get("/api/v1/risk-score?segment_id=REAL_RAIL_SEG_01")
        assert response2.status_code == 200
        data2 = response2.json()
        last_updated_2 = data2["last_updated"]
        
        # Cache hit - timestamps should be identical
        assert last_updated_1 == last_updated_2