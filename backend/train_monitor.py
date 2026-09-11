import asyncio
import time
import httpx
import os
from dotenv import load_dotenv
from geo_utils import interpolate_position, haversine

load_dotenv()

RAILRADAR_API_KEY = os.getenv("RAILRADAR_API_KEY", "")
RAILRADAR_BASE = "https://api.railradar.in/v1"

class TrainMonitor:
    def __init__(self):
        self.monitored_trains = ["12952", "12841"] # Default
        self.live_trains = {}
        self.ghost_trains = {}
        self.routes = {}
        self.simulation_active = False
        self.simulation_ticks = 0
        self.last_api_fetch = 0
        self.api_fetch_interval = 10

    def set_monitored_trains(self, trains):
        self.monitored_trains = [str(t).strip() for t in trains if str(t).strip()]
        self.live_trains = {}
        self.last_api_fetch = 0 # Force fetch immediately

    async def fetch_route(self, train_num):
        if train_num in self.routes:
            return self.routes[train_num]
        headers = {"Authorization": f"Bearer {RAILRADAR_API_KEY}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.get(f"{RAILRADAR_BASE}/trains/{train_num}/route", headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    self.routes[train_num] = data.get("data", {}).get("geojson", {})
                    return self.routes[train_num]
                else:
                    print(f"RailRadar: Train {train_num} route returned {r.status_code}")
            except Exception as e:
                print(f"Error fetching route for {train_num}: {e}")
        return None

    def get_cached_route(self, train_num):
        return self.routes.get(train_num, {})

    async def fetch_live_railradar_data(self):
        if not RAILRADAR_API_KEY:
            return
            
        # Skip fetching live data if we are actively running a simulation
        if self.simulation_active:
            return
            
        now = time.time()
        if now - self.last_api_fetch < self.api_fetch_interval:
            return
        self.last_api_fetch = now

        headers = {"Authorization": f"Bearer {RAILRADAR_API_KEY}"}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for train_num in self.monitored_trains:
                if train_num not in self.routes:
                    await self.fetch_route(train_num)
                    
                try:
                    r = await client.get(f"{RAILRADAR_BASE}/trains/{train_num}/live", headers=headers)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("success") and data.get("data"):
                            d = data["data"]
                            loc = d.get("currentLocation", {})
                            train_info = d.get("train", {})
                            
                            dist_km = loc.get("distanceFromOriginKm", 0)
                            
                            lat, lng = 22.0, 78.0
                            route = self.routes.get(train_num, {})
                            if route and "geometry" in route:
                                coords = route["geometry"].get("coordinates", [])
                                pos = interpolate_position(coords, dist_km)
                                if pos:
                                    lat, lng = pos
                                    
                            # Fallback if interpolation failed
                            if lat == 22.0:
                                src = train_info.get("source", {})
                                lat = src.get("lat", 22.0)
                                lng = src.get("lng", 78.0)
                            
                            self.live_trains[train_num] = {
                                "trainNumber": train_num,
                                "trainName": d.get("trainName", train_num),
                                "status": d.get("status", "unknown"),
                                "isLive": d.get("isLive", False),
                                "delayMinutes": d.get("delayMinutes", 0),
                                "currentStation": loc.get("stationName", "Unknown"),
                                "distanceFromOriginKm": dist_km,
                                "totalDistanceKm": train_info.get("distance", 1000),
                                "avgSpeed": train_info.get("avgSpeed", 60),
                                "lat": lat,
                                "lng": lng,
                                "base_route": train_num
                            }
                    else:
                        print(f"RailRadar: Train {train_num} live data returned {r.status_code}")
                except Exception as e:
                    print(f"RailRadar API error for {train_num}: {e}")

        # Ensure we have at least simulated data if real data failed
        if not self.live_trains:
            self._use_fallback_data()

    def _use_fallback_data(self):
        # Fake data if API fails (like rate limits)
        if "12952" in self.monitored_trains:
            self.live_trains["12952"] = {
                "trainNumber": "12952",
                "trainName": "Simulated Rajdhani (API Quota)",
                "status": "running",
                "isLive": False,
                "delayMinutes": 5,
                "currentStation": "Simulated Kota",
                "lat": 25.183,
                "lng": 75.83,
                "distanceFromOriginKm": 465.0,
                "base_route": "12952"
            }
            if "12952" not in self.routes:
                self.routes["12952"] = {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[77.2167, 28.6139], [75.8333, 25.1833], [72.8167, 18.9667]]
                    }
                }
                
        if "12841" in self.monitored_trains:
            self.live_trains["12841"] = {
                "trainNumber": "12841",
                "trainName": "Simulated Coromandel (API Quota)",
                "status": "running",
                "isLive": False,
                "delayMinutes": 10,
                "currentStation": "Simulated Bhubaneswar",
                "lat": 20.266,
                "lng": 85.83,
                "distanceFromOriginKm": 437.0,
                "base_route": "12841"
            }
            if "12841" not in self.routes:
                self.routes["12841"] = {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[88.3639, 22.5726], [85.8333, 20.2667], [80.2785, 13.0827]]
                    }
                }

    def get_state(self):
        merged = {**self.live_trains, **self.ghost_trains}
        return {
            "type": "train_state",
            "timestamp": time.time(),
            "trains": merged,
            "railradar_active": bool(RAILRADAR_API_KEY),
            "simulation_active": self.simulation_active
        }

    def inject_fault(self):
        """Starts a high-fidelity convergence simulation."""
        self.simulation_active = True
        self.simulation_ticks = 0
        self.ghost_trains = {}
        
        # If we have at least one live train with a route, use it as the scene
        target = None
        for t in self.live_trains.values():
            if t["base_route"] in self.routes:
                target = t
                break
                
        if not target:
            print("Cannot simulate without at least one live train and route.")
            return
            
        print(f"Starting collision simulation on route of {target['trainNumber']}")
        
        # Base setup: we take the target train, and spawn a ghost 50km ahead, heading backwards
        route_coords = self.routes[target["base_route"]]["geometry"]["coordinates"]
        
        self.sim_state = {
            "target_id": target["trainNumber"],
            "route_coords": route_coords,
            "dist_target": target["distanceFromOriginKm"],
            "dist_ghost": target["distanceFromOriginKm"] + 50.0  # 50 km ahead
        }
        
        self.ghost_trains["GHOST_SIM"] = {
            "trainNumber": "GHOST",
            "trainName": "Simulation Goods Train",
            "status": "DANGER",
            "isLive": False,
            "delayMinutes": 0,
            "currentStation": "Approaching Head-On",
            "lat": 0, "lng": 0,
            "distanceFromOriginKm": self.sim_state["dist_ghost"],
            "avgSpeed": 100
        }

    def step_simulation(self):
        if not self.simulation_active or "GHOST_SIM" not in self.ghost_trains:
            return
            
        # Move target train forward by 2 km per second (super fast for demo)
        self.sim_state["dist_target"] += 1.5
        # Move ghost train backward by 1.5 km per second
        self.sim_state["dist_ghost"] -= 1.5
        
        # Interpolate positions
        t_pos = interpolate_position(self.sim_state["route_coords"], self.sim_state["dist_target"])
        g_pos = interpolate_position(self.sim_state["route_coords"], self.sim_state["dist_ghost"])
        
        tid = self.sim_state["target_id"]
        if tid in self.live_trains and t_pos:
            self.live_trains[tid]["lat"] = t_pos[0]
            self.live_trains[tid]["lng"] = t_pos[1]
            self.live_trains[tid]["avgSpeed"] = 140 # Simulate high speed
            
        if g_pos:
            self.ghost_trains["GHOST_SIM"]["lat"] = g_pos[0]
            self.ghost_trains["GHOST_SIM"]["lng"] = g_pos[1]

    def resolve_fault(self):
        self.simulation_active = False
        self.ghost_trains = {}
        self.last_api_fetch = 0 # Force immediate refresh of real data

    def check_convergence(self):
        alerts = []
        if not self.simulation_active:
            return alerts
            
        merged = {**self.live_trains, **self.ghost_trains}
        train_ids = list(merged.keys())
        
        for i in range(len(train_ids)):
            for j in range(i + 1, len(train_ids)):
                tA = merged[train_ids[i]]
                tB = merged[train_ids[j]]
                
                # Calculate direct haversine distance
                if tA.get("lat") and tB.get("lat"):
                    dist = haversine(tA["lng"], tA["lat"], tB["lng"], tB["lat"])
                    
                    if dist < 15.0:  # Within 15km
                        alerts.append({
                            "type": "layer3_alert",
                            "layer": "Layer 3",
                            "source": "RailRadar Dynamic Monitor",
                            "timestamp": time.time(),
                            "description": f"URGENT CONVERGENCE: {tA.get('trainName')} and {tB.get('trainName')} are on the same block section! Separation: {dist:.1f}km.",
                            "affected_id": f"{train_ids[i]}-{train_ids[j]}"
                        })
        return alerts

    async def run(self):
        while True:
            await asyncio.sleep(1.0)
            if self.simulation_active:
                self.step_simulation()
            else:
                await self.fetch_live_railradar_data()

train_monitor = TrainMonitor()
