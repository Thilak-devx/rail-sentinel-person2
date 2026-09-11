import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api import positions, risk

# Configure logging so INFO logs appear in terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# Resolve the frontend directory relative to this file
BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend" / "gps-client"

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(positions.router)
app.include_router(risk.router)

# Serve GPS client at /gps-client/
if FRONTEND_DIR.exists():
    app.mount("/gps-client", StaticFiles(directory=FRONTEND_DIR, html=True), name="gps-client")


@app.get("/")
async def root():
    return {"message": "RailSentinel Position Service", "version": "1.0.0"}