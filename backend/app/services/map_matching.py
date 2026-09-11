from typing import Optional
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import Point, LineString, shape
from shapely.ops import nearest_points

from app.services.segment_registry import segment_registry


@dataclass
class MapMatchResult:
    matched: bool
    raw_lat: float
    raw_long: float
    matched_lat: Optional[float] = None
    matched_long: Optional[float] = None
    distance_meters: Optional[float] = None
    segment_id: Optional[str] = None
    reason: Optional[str] = None


class MapMatcher:
    def __init__(self, max_matching_distance: float = 100.0):
        self.max_matching_distance = max_matching_distance
        self._segments: list[tuple[LineString, str]] = []
        self._route_loaded = False

    def load_route_geojson(self, geojson: dict) -> None:
        """Legacy method for backward compatibility."""
        if geojson.get("type") != "FeatureCollection":
            raise ValueError("Expected FeatureCollection GeoJSON")

        features = geojson.get("features", [])
        if not features:
            raise ValueError("No features in GeoJSON")

        all_coords = []
        self._segments = []
        
        for feature in features:
            geom = feature.get("geometry")
            if not geom:
                continue
            shp = shape(geom)
            if shp.geom_type == "LineString":
                seg_id = feature.get("properties", {}).get("segment_id", f"seg_{len(self._segments)}")
                self._segments.append((shp, seg_id))
            elif shp.geom_type == "MultiLineString":
                for line in shp.geoms:
                    seg_id = feature.get("properties", {}).get("segment_id", f"seg_{len(self._segments)}")
                    self._segments.append((line, seg_id))

        # Build combined route for backward compatibility
        all_coords = []
        for seg, _ in self._segments:
            all_coords.extend(list(seg.coords))
        
        if all_coords:
            from shapely.geometry import LineString
            self._route = LineString(all_coords)

    def load_route_linestring(self, coordinates: list[tuple[float, float]]) -> None:
        from shapely.geometry import LineString
        self._route = LineString(coordinates)
        self._segments = [(self._route, "route_0")]
        self._route_loaded = True

    def load_from_registry(self) -> bool:
        """Load route and segments from the global segment registry."""
        # Build segments from registry (real + demo)
        self._segments = []
        
        # Get all segments with geometry from registry, sorted by sequence
        sorted_segments = sorted(
            [(seg_id, info) for seg_id, info in segment_registry._segments.items() 
             if info.geometry is not None],
            key=lambda x: x[1].sequence
        )
        
        if not sorted_segments:
            return False
        
        all_coords = []
        for seg_id, seg_info in sorted_segments:
            coords = list(seg_info.geometry.coords)
            self._segments.append((seg_info.geometry, seg_id))
            all_coords.extend(coords)
        
        if all_coords:
            from shapely.geometry import LineString
            self._route = LineString(all_coords)
            return True
        
        return False

    def match_position(self, lat: float, long: float) -> MapMatchResult:
        if not self._segments:
            return MapMatchResult(
                matched=False,
                raw_lat=lat,
                raw_long=long,
                reason="no_route_loaded"
            )

        point = Point(long, lat)
        
        # Find the nearest segment directly (more robust than using full route)
        min_dist = float('inf')
        best_seg_id = None
        best_nearest_point = None
        
        for seg, seg_id in self._segments:
            # Project point onto segment
            proj_dist = seg.project(point)
            nearest_point = seg.interpolate(proj_dist)
            distance = point.distance(nearest_point)
            
            if distance < min_dist:
                min_dist = distance
                best_seg_id = seg_id
                best_nearest_point = nearest_point
        
        if best_seg_id is None or best_nearest_point is None:
            return MapMatchResult(
                matched=False,
                raw_lat=lat,
                raw_long=long,
                reason="no_segments_available"
            )

        # Convert distance to meters
        approx_meters_per_degree = 111320.0
        distance_meters = min_dist * approx_meters_per_degree

        if distance_meters > self.max_matching_distance:
            return MapMatchResult(
                matched=False,
                raw_lat=lat,
                raw_long=long,
                distance_meters=distance_meters,
                reason="outside_matching_threshold"
            )

        return MapMatchResult(
            matched=True,
            raw_lat=lat,
            raw_long=long,
            matched_lat=best_nearest_point.y,
            matched_long=best_nearest_point.x,
            distance_meters=round(distance_meters, 2),
            segment_id=best_seg_id
        )


# Backward compatibility: load the default route on module import
def load_real_route_geojson() -> dict:
    """Load the real railway route GeoJSON from the data/routes directory."""
    route_path = Path(__file__).parent.parent.parent.parent / "data" / "routes" / "real_railway_bhubaneswar.geojson"
    if route_path.exists():
        import json
        with open(route_path, 'r') as f:
            return json.load(f)
    return DEMO_ROUTE_GEOJSON


DEMO_ROUTE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "segment_id": "DEMO_SEG_01",
                "description": "Demo segment - NOT a real railway route"
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [85.8240, 20.2950],
                    [85.8245, 20.2961],
                    [85.8250, 20.2971],
                    [85.8255, 20.2980],
                    [85.8260, 20.2990]
                ]
            }
        }
    ]
}


# Global matcher instance
map_matcher = MapMatcher()
map_matcher.load_from_registry()