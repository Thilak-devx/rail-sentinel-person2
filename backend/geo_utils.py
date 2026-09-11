import math

def haversine(lon1, lat1, lon2, lat2):
    R = 6371.0 # Earth radius in kilometers
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def interpolate_position(route_coords, target_distance_km):
    if not route_coords or len(route_coords) < 2:
        return None
    
    current_dist = 0.0
    for i in range(len(route_coords) - 1):
        lon1, lat1 = route_coords[i]
        lon2, lat2 = route_coords[i+1]
        
        segment_dist = haversine(lon1, lat1, lon2, lat2)
        if current_dist + segment_dist >= target_distance_km:
            if segment_dist == 0:
                return (lat1, lon1)
            # Interpolate
            ratio = (target_distance_km - current_dist) / segment_dist
            lat = lat1 + (lat2 - lat1) * ratio
            lon = lon1 + (lon2 - lon1) * ratio
            return (lat, lon)
            
        current_dist += segment_dist
        
    # If we overshoot, return the last coordinate
    return (route_coords[-1][1], route_coords[-1][0])
