# Real Railway Route Data

This directory contains verified railway route geometry extracted from OpenStreetMap.

## File: real_railway_bhubaneswar.geojson

### Source
- **OpenStreetMap Relation**: 5699337
- **Relation Name**: "East Coast main railway line"
- **Route**: Howrah Junction → Chennai (East Coast Railway main line)
- **Type**: `route=railway`, `railway=rail`
- **Operator**: Indian Railways

### Extraction
- **Area**: Bhubaneswar section (approximate bbox: lat 20.23-20.30, lon 85.80-85.85)
- **Method**: Extracted from full relation using OSM API `/map` call + way coordinate extraction
- **Filter**: Ways with `railway=rail` within Bhubaneswar geographic bounds
- **Retrieval Date**: 2026-09-10

### Data
- **Format**: GeoJSON FeatureCollection
- **Geometry**: LineString (349 coordinates)
- **Coordinate Order**: [longitude, latitude] (GeoJSON standard)
- **Segment ID**: `REAL_RAIL_SEG_01`
- **Coordinate Bounds**: 
  - Latitude: 20.2315° to 20.2996°
  - Longitude: 85.8053° to 85.8550°

### License & Attribution
- **License**: ODbL (Open Database License v1.0)
- **Attribution**: © OpenStreetMap contributors
- **Source URL**: https://www.openstreetmap.org/relation/5699337

### Usage
This dataset is a **demonstration dataset** for the RailSentinel SIH26028 prototype. It represents a verified real railway section but is not guaranteed to be survey-grade or suitable for operational railway use.

The application loads this file by default at startup (see `backend/app/services/map_matching.py`). If the file is missing, it falls back to the synthetic `DEMO_SEG_01` route.