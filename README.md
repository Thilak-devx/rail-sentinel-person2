# RailSentinel — Live Position & Risk Data Layer

Person 2 module for SIH26028: Live ETA & Safety Prediction System.

## Responsibilities

1. **Live Position Feed** — Receive GPS positions from coach phones via REST API
2. **Map Matching** — Snap raw GPS points to railway route geometry
3. **Disaster Risk Data Layer** — Route-segment risk scoring (flood/weather)

## Architecture

```
backend/
  app/
    main.py                         # FastAPI application entry point
    core/config.py                  # Configuration via Pydantic Settings
    models/schemas.py               # Pydantic models for requests/responses
    services/gps_service.py         # In-memory GPS storage + speed calculation
    services/map_matching.py        # Map matching service (Shapely + GeoJSON)
    services/risk_service.py        # Risk engine + caching
    providers/weather_provider.py   # Weather provider interface + mock
    providers/flood_provider.py     # Flood provider interface + mock
    api/positions.py                # REST endpoints for position data
    api/risk.py                     # REST endpoints for risk scoring
  tests/
    test_positions.py               # Unit + integration tests
```

## Quick Start

### Prerequisites
- Python 3.11+

### Installation

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -e .
```

### Running the Server

```bash
venv\Scripts\uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server will be available at `http://localhost:8000`

### Running Tests

```bash
venv\Scripts\pytest tests/ -v
```

## API Endpoints

### Health Check
```
GET /api/v1/health
```
Response:
```json
{
  "status": "healthy",
  "service": "RailSentinel Position Service",
  "version": "1.0.0"
}
```

### Submit Position
```
POST /api/v1/position
```
Request:
```json
{
  "coach_id": "S1",
  "lat": 20.2961,
  "long": 85.8245,
  "speed": 42.3,
  "timestamp": "2026-09-06T18:30:00Z"
}
```
Response (201):
```json
{
  "coach_id": "S1",
  "lat": 20.2961,
  "long": 85.8245,
  "speed": 42.3,
  "calculated_speed": 41.8,
  "timestamp": "2026-09-06T18:30:00Z",
  "matched_lat": 20.2961,
  "matched_long": 85.8245,
  "match_distance_meters": 0.0,
  "route_segment_id": "DEMO_SEG_01",
  "matched": true
}
```

### Map Matching

The service snaps raw GPS points to the nearest point on a railway route polyline.

**How it works:**
1. Load a GeoJSON route (LineString or MultiLineString) — currently a demo route
2. For each incoming GPS position, find the nearest point on the route using Shapely
3. If the distance is within the configured threshold (`MAP_MATCHING_MAX_DISTANCE`, default 100m), return the matched position
4. If outside threshold, return `matched: false` with reason `outside_matching_threshold`

**Coordinate Order:** GeoJSON uses `[longitude, latitude]` (x, y). The API accepts `lat` and `long` separately. The matcher correctly handles this conversion.

**Demo Route Disclaimer:** The included `DEMO_ROUTE_GEOJSON` in `backend/app/services/map_matching.py` is synthetic test geometry. It is NOT an actual Indian Railways route. 

**Real Route (Production Default):** The application now loads `data/routes/real_railway_bhubaneswar.geojson` by default when available. This is a verified extract from OpenStreetMap (OSM Relation 5699337 — "East Coast main railway line", Howrah Junction → Chennai), filtered to the Bhubaneswar area. See `data/routes/README.md` for full provenance.

**Example Successful Match:**
```json
{
  "coach_id": "S1",
  "lat": 20.2961,
  "long": 85.8245,
  "speed": 42.3,
  "calculated_speed": 41.8,
  "timestamp": "2026-09-06T18:30:00Z",
  "matched_lat": 20.2961,
  "matched_long": 85.8245,
  "match_distance_meters": 0.0,
  "route_segment_id": "DEMO_SEG_01",
  "matched": true
}
```

**Example Rejected Match (outside threshold):**
```json
{
  "coach_id": "S1",
  "lat": 20.5000,
  "long": 86.0000,
  "speed": 50.0,
  "calculated_speed": null,
  "timestamp": "2026-09-06T18:30:00Z",
  "matched_lat": null,
  "matched_long": null,
  "match_distance_meters": 29594.58,
  "route_segment_id": null,
  "matched": false
}
```

### Get Live Positions
```
GET /api/v1/live-positions
```
Response:
```json
[
  {
    "coach_id": "S1",
    "lat": 20.2961,
    "long": 85.8245,
    "speed": 42.3,
    "calculated_speed": 41.8,
    "timestamp": "2026-09-06T18:30:00Z"
  }
]
```

### Risk Score
```
GET /api/v1/risk-score?segment_id=SEG_01
```
Response (200):
```json
{
  "segment_id": "SEG_01",
  "risk_level": "none",
  "source": "none",
  "last_updated": "2026-09-06T18:30:00Z"
}
```
Response (404 for unknown segments):
```json
{"detail": "Segment not found"}
```

### Risk Scoring Rules

The risk engine applies deterministic rules in priority order:

1. **SEVERE** — Water level ≥ danger level (flood source)
2. **MODERATE** — Water level ≥ warning level (flood source)
3. **LOW** — Heavy rain (precipitation ≥ 10mm) OR fog (visibility < 1000m) (weather source)
4. **NONE** — None of the above

**Priority:** Flood conditions (SEVERE, MODERATE) override weather conditions (LOW). If both flood and weather contribute, the highest priority determines the risk level and source.

**Demo Segments (NOT real railway infrastructure):**
| Segment | Flood Status | Weather | Expected Risk |
|---------|-------------|---------|---------------|
| SEG_01 | Normal (5.0m) | Clear | NONE |
| SEG_LOW_RAIN | Normal (5.0m) | Heavy rain (15mm) | LOW (weather) |
| SEG_LOW_FOG | Normal (5.0m) | Fog (200m visibility) | LOW (weather) |
| SEG_MODERATE_FLOOD | Warning (9.0m) | Clear | MODERATE (flood) |
| SEG_03 | Danger (10.5m) | Fog | SEVERE (flood overrides) |

**Source Values:**
- `flood` — Risk driven by water level (MODERATE/SEVERE)
- `weather` — Risk driven by rain/fog (LOW)
- `none` — No risk factors present

## Configuration

Environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | RailSentinel Position Service | Service name |
| `DEBUG` | true | Debug mode |
| `CORS_ORIGINS` | ["*"] | Allowed CORS origins |
| `POSITION_HISTORY_SIZE` | 50 | Max GPS points stored per coach |
| `MAP_MATCHING_MAX_DISTANCE` | 100.0 | Max distance (meters) to snap GPS to route |
| `WEATHER_PROVIDER` | mock | Weather provider: `mock` or `openweathermap` |
| `FLOOD_PROVIDER` | mock | Flood provider: `mock` or `cwc` |
| `RISK_REFRESH_INTERVAL_SECONDS` | 600 | Risk data cache TTL (seconds) |
| `OPENWEATHER_API_KEY` | | API key for OpenWeather Current Weather API (real provider) |
| `CWC_API_KEY` | | API key for CWC/WRIS (real provider - not yet implemented) |
| `HOST` | 0.0.0.0 | Server host |
| `PORT` | 8000 | Server port |

## GPS Client (Frontend)

A simple HTML/JS client is in `frontend/gps-client/index.html`. Open in a browser, enter a coach ID (e.g., `S1`), and it will send GPS positions every 2-3 seconds.

## Data Storage

- In-memory storage using `deque` with configurable maxlen
- Stores latest N positions per coach
- Calculates speed from consecutive GPS points using Haversine formula
- Both phone-reported speed and calculated speed are retained

## Integration for Teammates

- **Person 1 (Anomaly Detection)**: Consume `GET /api/v1/live-positions`
- **Person 3 (ETA Prediction)**: Consume `GET /api/v1/live-positions` + position history
- **Person 4 (Dashboard)**: Consume both position and risk endpoints

## Real vs Mock Data

Currently all data is real (from GPS client). Risk layer distinguishes:
- `source: "flood"` — real CWC/WRIS data (not yet implemented)
- `source: "weather"` — real OpenWeatherMap data (available via `WEATHER_PROVIDER=openweathermap`)
- `source: "mock"` — development/demo data only (default)
- `source: "cwc_unconfigured"` — CWC provider boundary (returns provider_unavailable)

Never present mock values as real measurements.

## Provider Abstraction

The risk layer uses a provider abstraction so the engine doesn't depend on specific external APIs:

- **WeatherProvider interface** — `get_weather(segment_id)` returns precipitation, visibility, condition
- **FloodProvider interface** — `get_flood_status(segment_id)` returns water level, warning/danger thresholds
- **Mock providers** — Deterministic demo data for development/testing (default)
- **Real providers** — Can be implemented by subclassing the interfaces

### OpenWeatherMap Provider (Implemented)

**Endpoint:** `https://api.openweathermap.org/data/2.5/weather` (Current Weather API)

**Configuration:**
```bash
WEATHER_PROVIDER=openweathermap
OPENWEATHER_API_KEY=your_api_key_here
```

**Segment-to-coordinates mapping** (in `OpenWeatherProvider._segment_coords`):
- SEG_01 → (20.2961, 85.8245)
- SEG_LOW_RAIN → (20.2971, 85.8255)
- SEG_LOW_FOG → (20.2980, 85.8260)
- SEG_MODERATE_FLOOD → (20.2990, 85.8270)

**Parsed fields from OpenWeather response:**
- `rain.1h` / `rain.3h` → precipitation_mm (rain volume in mm)
- `visibility` → visibility_m (meters, capped at 10000)
- `weather[0].main` / `weather[0].description` → condition (clear, rain, heavy_rain, fog, clouds, snow, etc.)
- `dt` → observed_at (Unix timestamp)

**Error handling:**
- Timeout → condition="timeout", source="openweathermap", raw_data.error="timeout"
- HTTP 4xx/5xx → condition="http_error", source="openweathermap", raw_data.error="http_<status>"
- Other errors → condition="error", source="openweathermap", raw_data.error="<message>"

**Missing data policy:** Never fabricate precipitation or visibility values. If fields are absent from the API response, they remain `None`/`0.0` in the observation.

### CWC / India-WRIS Flood Provider (Boundary Only)

**Status:** NOT IMPLEMENTED — No verified public machine-readable REST endpoint found in official CWC/India-WRIS documentation.

**Configuration (placeholder):**
```bash
FLOOD_PROVIDER=cwc
CWC_API_KEY=your_api_key_here
```

**Current behavior:** Returns `provider_unavailable` status for all segments with clear error message in `raw_data`.

**Required for implementation:**
1. Official CWC/WRIS API documentation with verified endpoints
2. Authentication mechanism (API key, OAuth, etc.)
3. Data format specification (water level, warning/danger thresholds per station)
4. Station-to-segment mapping

Do NOT substitute random third-party flood data and call it CWC.

Configure via `WEATHER_PROVIDER` and `FLOOD_PROVIDER` environment variables.

## Cache / Refresh Behavior

- Risk assessments are cached per segment for `RISK_REFRESH_INTERVAL_SECONDS` (default 600s / 10min)
- Providers are only called on cache miss or expiry
- Call `risk_service.clear_cache()` to force refresh

## Limitations

- Demo segments and mock data are synthetic — NOT real Indian Railways infrastructure
- Real provider implementations not yet built (OpenWeatherMap, CWC/WRIS)
- Flood thresholds are simplified — real systems use complex hydrological models
- No authentication/authorization on risk endpoints

## License

Internal — SIH26026