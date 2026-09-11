from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Tuple, List
import json
import math

from shapely.geometry import LineString, Point, shape
from shapely.ops import nearest_points


@dataclass
class SegmentInfo:
    segment_id: str
    representative_lat: float
    representative_long: float
    geometry: Optional[LineString] = None
    start_lat: Optional[float] = None
    start_long: Optional[float] = None
    end_lat: Optional[float] = None
    end_long: Optional[float] = None
    length_meters: Optional[float] = None
    sequence: int = 0


class SegmentRegistry:
    """Registry of route segments with their representative coordinates."""

    # Approximate meters per degree at this latitude
    METERS_PER_DEGREE = 111320.0
    TARGET_NUM_SEGMENTS = 46  # Target number of segments

    def __init__(self):
        self._segments: Dict[str, SegmentInfo] = {}

    def load_from_geojson(self, geojson: dict) -> None:
        """Load segment info from a GeoJSON FeatureCollection."""
        features = geojson.get("features", [])
        for feature in features:
            geom = feature.get("geometry")
            if not geom:
                continue
            shp = shape(geom)
            seg_id = feature.get("properties", {}).get("segment_id")
            if not seg_id:
                continue

            # Get representative point (centroid of the line)
            if shp.geom_type == "LineString":
                rep_point = shp.centroid
                self._segments[seg_id] = SegmentInfo(
                    segment_id=seg_id,
                    representative_lat=rep_point.y,
                    representative_long=rep_point.x,
                    geometry=shp
                )
            elif shp.geom_type == "MultiLineString":
                # Use centroid of the combined geometry
                rep_point = shp.centroid
                self._segments[seg_id] = SegmentInfo(
                    segment_id=seg_id,
                    representative_lat=rep_point.y,
                    representative_long=rep_point.x,
                    geometry=shp
                )

    def load_real_route_segments(self, geojson: dict) -> int:
        """
        Split the real route geometry into 46 segments of approximately equal length.
        
        Returns the number of segments created.
        """
        features = geojson.get("features", [])
        if not features:
            return 0

        # Extract the main LineString geometry
        all_coords = []
        for feature in features:
            geom = feature.get("geometry")
            if not geom:
                continue
            shp = shape(geom)
            if shp.geom_type == "LineString":
                all_coords.extend(list(shp.coords))
            elif shp.geom_type == "MultiLineString":
                for line in shp.geoms:
                    all_coords.extend(list(line.coords))

        if not all_coords:
            return 0

        # Create a single LineString from all coordinates
        full_route = LineString(all_coords)
        
        # Split the route into exactly 46 segments of equal length
        segment_lines = self._split_line_into_n_segments(full_route, self.TARGET_NUM_SEGMENTS)
        
        # Clear existing real segments (keep demo segments)
        self._clear_real_segments()
        
        # Create segment info for each segment
        for i, segment_line in enumerate(segment_lines):
            if segment_line.length == 0:
                continue
            
            seg_id = f"REAL_RAIL_SEG_{i+1:02d}"
            rep_point = segment_line.centroid
            
            coords = list(segment_line.coords)
            start_lat, start_lon = coords[0][1], coords[0][0]
            end_lat, end_lon = coords[-1][1], coords[-1][0]
            length_m = self._calculate_length_meters(segment_line)
            
            self._segments[f"REAL_RAIL_SEG_{i+1:02d}"] = SegmentInfo(
                segment_id=f"REAL_RAIL_SEG_{i+1:02d}",
                representative_lat=rep_point.y,
                representative_long=rep_point.x,
                geometry=segment_line,
                start_lat=start_lat,
                start_long=start_lon,
                end_lat=end_lat,
                end_long=end_lon,
                length_meters=length_m,
                sequence=i + 1
            )
        
        return len(segment_lines)

    def _calculate_length_meters(self, line: LineString) -> float:
        """Calculate the length of a LineString in meters."""
        return line.length * self.METERS_PER_DEGREE

    def _split_line_into_n_segments(self, line: LineString, num_segments: int) -> List[LineString]:
        """
        Split a LineString into exactly num_segments of equal length along the line.
        Returns a list of LineString segments.
        """
        if num_segments <= 1:
            return [line]
        
        total_length = line.length
        segment_length = line.length / num_segments
        
        segments = []
        for i in range(num_segments):
            start_dist = i * segment_length
            end_dist = min((i + 1) * segment_length, line.length)
            segment = self._cut_line(line, start_dist, end_dist)
            if segment.length > 0:
                segments.append(segment)
        
        return segments

    def _cut_line(self, line: LineString, start_dist: float, end_dist: float) -> LineString:
        """Cut a LineString between two distances along the line."""
        start_point = line.interpolate(start_dist)
        end_point = line.interpolate(end_dist)
        
        coords = list(line.coords)
        if not coords:
            return LineString()
        
        segment_coords = [list(start_point.coords)[0]]
        
        accumulated = 0.0
        for i in range(1, len(coords)):
            prev = Point(coords[i-1])
            curr = Point(coords[i])
            seg_dist = prev.distance(curr)
            
            if accumulated + seg_dist > start_dist:
                if accumulated < start_dist:
                    ratio = (start_dist - accumulated) / seg_dist
                    interp_x = coords[i-1][0] + (coords[i][0] - coords[i-1][0]) * ratio
                    interp_y = coords[i-1][1] + (coords[i][1] - coords[i-1][1]) * ratio
                    segment_coords.append((interp_x, interp_y))
            
            if start_dist <= accumulated + seg_dist <= end_dist:
                segment_coords.append(coords[i])
            elif accumulated + seg_dist > end_dist:
                # Interpolate the end point
                remaining = end_dist - accumulated
                ratio = remaining / seg_dist
                interp_x = coords[i-1][0] + (coords[i][0] - coords[i-1][0]) * ratio
                interp_y = coords[i-1][1] + (coords[i][1] - coords[i-1][1]) * ratio
                segment_coords.append((interp_x, interp_y))
                break
            
            accumulated += seg_dist
        
        if len(segment_coords) >= 2:
            return LineString(segment_coords)
        return LineString()

    def _clear_real_segments(self) -> None:
        """Remove all REAL_RAIL_SEG_* segments from the registry."""
        keys_to_remove = [k for k in self._segments.keys() if k.startswith("REAL_RAIL_SEG_")]
        for k in keys_to_remove:
            del self._segments[k]

    def load_demo_segments(self) -> None:
        """Load the hardcoded demo segments for backward compatibility."""
        demo_segments = {
            "SEG_01": (20.2961, 85.8245),
            "SEG_LOW_RAIN": (20.2971, 85.8255),
            "SEG_LOW_FOG": (20.2980, 85.8260),
            "SEG_MODERATE_FLOOD": (20.2990, 85.8270),
            "SEG_02": (20.2970, 85.8250),
            "SEG_03": (20.2980, 85.8260),
            "SEG_04": (20.2980, 85.8260),
        }
        for seg_id, (lat, lon) in demo_segments.items():
            self._segments[seg_id] = SegmentInfo(
                segment_id=seg_id,
                representative_lat=lat,
                representative_long=lon,
            )
    
    def get_coordinates(self, segment_id: str) -> Optional[Tuple[float, float]]:
        """Get representative (lat, lon) for a segment."""
        seg = self._segments.get(segment_id)
        if seg:
            return (seg.representative_lat, seg.representative_long)
        return None
    
    def get_segment_info(self, segment_id: str) -> Optional[SegmentInfo]:
        return self._segments.get(segment_id)
    
    def has_segment(self, segment_id: str) -> bool:
        return segment_id in self._segments
    
    def list_segments(self) -> list[str]:
        return list(self._segments.keys())


def load_segment_registry() -> SegmentRegistry:
    """Load the segment registry from the real route GeoJSON, with demo fallback."""
    registry = SegmentRegistry()
    
    # Load demo segments first (for backward compatibility)
    registry.load_demo_segments()
    
    # Load real route if available (overrides/adds to demo)
    route_path = Path(__file__).parent.parent.parent.parent / "data" / "routes" / "real_railway_bhubaneswar.geojson"
    if route_path.exists():
        with open(route_path, 'r') as f:
            geojson = json.load(f)
        registry.load_real_route_segments(geojson)
    
    return registry


# Global registry instance
segment_registry = load_segment_registry()