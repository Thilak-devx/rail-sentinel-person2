"""RailSentinel SIH26028 - Main FastAPI application.

Person 1 — Data & Prediction Engine only.
No disaster-management or incident-detection functionality.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.exceptions import HTTPException

from app.config import get_settings
from app.api.routes import router

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="RailSentinel — ETA Prediction Engine",
    version="0.1.0",
    description="Person 1 responsibility: ETA forecasting using railway schedule data",
)

# Include ETA prediction API router
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint returning basic service info."""
    return {
        "service": "RailSentinel ETA Prediction",
        "version": "0.1.0",
        "person": "1 — Data & Prediction Engine",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/frontend/{path:path}")
async def serve_frontend(path: str):
    """Serve the frontend HTML files."""
    frontend_dir = PROJECT_ROOT / "frontend"
    file_path = frontend_dir / path

    # If file exists and is an HTML file, serve it
    if file_path.exists() and file_path.suffix in ['.html', '.css', '.js', '']:
        if path == '' or path == 'index.html':
            return FileResponse(frontend_dir / 'index.html')
        return FileResponse(file_path)

    # Default to index.html for any other path
    return FileResponse(frontend_dir / 'index.html')


@app.get("/predict-eta", response_model=None)
async def predict_eta_legacy():
    """Legacy endpoint - redirect to the new /predict-eta/ route."""
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app
    raise HTTPException(
        status_code=307,
        detail="/predict-eta/ (POST method required)",
    )