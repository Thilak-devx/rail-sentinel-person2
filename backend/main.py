import asyncio
import json
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from scada_simulator import scada_sim
from verification_engine import VerificationEngine
from train_monitor import train_monitor
from alert_manager import alert_manager
from eta_engine import predict_for_train

PERSON2_BASE = "http://localhost:8001"

# Cached person2 state — updated by background task
_coach_positions: list = []
_risk_scores: dict = {}


async def fetch_person2_state():
    """Poll person2 service every 3 seconds for coach positions and risk scores."""
    global _coach_positions, _risk_scores
    async with httpx.AsyncClient(timeout=3.0) as client:
        while True:
            await asyncio.sleep(3.0)
            try:
                r = await client.get(f"{PERSON2_BASE}/api/v1/live-positions")
                if r.status_code == 200:
                    _coach_positions = r.json()
            except Exception:
                pass
            try:
                r2 = await client.get(f"{PERSON2_BASE}/api/v1/risk-scores-all")
                if r2.status_code == 200:
                    _risk_scores = r2.json()
            except Exception:
                pass

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

verification_engine = VerificationEngine()

# Connection manager for WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                self.disconnect(connection)

manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(scada_sim.run())
    asyncio.create_task(train_monitor.run())
    asyncio.create_task(alert_manager.run_escalation_checker())
    asyncio.create_task(broadcast_state_loop())
    asyncio.create_task(fetch_person2_state())

async def broadcast_state_loop():
    while True:
        await asyncio.sleep(1.0)

        # Get SCADA state and verify Layer 1
        scada_state = scada_sim.get_state()
        layer1_alerts = verification_engine.verify_layer_1(scada_state)

        # Get Train Monitor state and verify Layer 3
        train_state = train_monitor.get_state()
        layer3_alerts = train_monitor.check_convergence()

        # Process alerts
        all_new_alerts = layer1_alerts + layer3_alerts
        alert_manager.process_new_alerts(all_new_alerts)

        # Compute ETA predictions for live (non-ghost) trains
        eta_data = {}
        for tid, tdata in train_state.get("trains", {}).items():
            if not tid.startswith("GHOST"):
                pred = predict_for_train(tdata)
                if pred:
                    eta_data[tid] = pred

        # Build composite payload
        payload = {
            "scada": scada_state,
            "trains": train_state,
            "alerts": alert_manager.get_all_alerts(),
            "eta": eta_data,
            "coach_positions": _coach_positions,
            "risk_scores": _risk_scores,
        }

        await manager.broadcast(json.dumps(payload))

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/api/inject_signal_mismatch")
def inject_signal_mismatch():
    scada_sim.inject_fault()
    return {"status": "Fault injected: Signal Mismatch (Balasore-style)"}

@app.post("/api/resolve_signal_mismatch")
def resolve_signal_mismatch():
    scada_sim.resolve_fault()
    return {"status": "Fault resolved: Signal Mismatch"}

@app.post("/api/inject_converging_trains")
def inject_converging_trains():
    train_monitor.inject_fault()
    return {"status": "Fault injected: Converging Trains"}

@app.post("/api/resolve_converging_trains")
def resolve_converging_trains():
    train_monitor.resolve_fault()
    return {"status": "Fault resolved: Converging Trains"}

@app.post("/api/acknowledge_alert/{alert_id}")
def acknowledge_alert(alert_id: str):
    success = alert_manager.acknowledge_alert(alert_id)
    if success:
        return {"status": "success", "message": f"Alert {alert_id} acknowledged."}
    else:
        return {"status": "error", "message": "Alert not found or already processed."}

# ---- New endpoints ----

@app.get("/api/route/{train_number}")
async def get_route(train_number: str):
    route = train_monitor.get_cached_route(train_number)
    return route or {"error": "Route not found"}

@app.get("/api/escalation_status")
def escalation_status():
    return {
        "escalation_timeout": alert_manager.escalation_timeout,
        "escalated_alerts": [a for a in alert_manager.get_all_alerts() if a["status"] == "Escalated"]
    }

@app.post("/api/escalation_config")
def escalation_config(timeout: int = 15, phone: str = ""):
    alert_manager.escalation_timeout = timeout
    if phone:
        import escalation
        escalation.ESCALATION_TARGET = phone
    return {"status": "ok", "timeout": timeout}

from pydantic import BaseModel
class TrainList(BaseModel):
    trains: list[str]

@app.post("/api/set_trains")
def set_trains(payload: TrainList):
    train_monitor.set_monitored_trains(payload.trains)
    return {"status": "ok", "trains": train_monitor.monitored_trains}

@app.get("/api/eta_status")
def eta_status():
    import eta_engine, sys
    return {
        "model_loaded": eta_engine._model is not None,
        "load_attempted": eta_engine._load_attempted,
        "model_path": str(eta_engine._MODEL_PATH),
        "model_path_exists": eta_engine._MODEL_PATH.exists(),
        "python": sys.executable,
    }

@app.get("/api/eta/{train_number}")
def get_eta(train_number: str):
    train = train_monitor.live_trains.get(train_number)
    if not train:
        return {"error": "Train not found or not yet fetched"}
    pred = predict_for_train(train)
    return pred or {"error": "ETA model unavailable"}

@app.get("/api/debug_trains")
def debug_trains():
    return train_monitor.get_state()

# ---- Person2 proxy endpoints ----

@app.get("/api/coach_positions")
def coach_positions():
    return _coach_positions

@app.get("/api/risk_scores")
def risk_scores():
    return _risk_scores

@app.post("/api/position")
async def relay_position(request: Request):
    """Relay GPS position to person2 service."""
    body = await request.json()
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.post(f"{PERSON2_BASE}/api/v1/position",
                                  json=body,
                                  headers={"Content-Type": "application/json"})
            return JSONResponse(content=r.json(), status_code=r.status_code)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=503)

@app.get("/api/risk_score")
async def risk_score(segment_id: str):
    """Proxy risk score query to person2 service."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.get(f"{PERSON2_BASE}/api/v1/risk-score",
                                 params={"segment_id": segment_id})
            return JSONResponse(content=r.json(), status_code=r.status_code)
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=503)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
