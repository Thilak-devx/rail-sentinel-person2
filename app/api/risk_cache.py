"""Shared risk cache for Person 1 ↔ Person 2 integration.

This module provides a thread-safe cache for risk data from Person 2,
avoiding circular imports between app.main and app.api.routes.
"""

import asyncio
from typing import Any

_risk_cache: dict = {}
_risk_cache_lock = asyncio.Lock()
_risk_poll_task: asyncio.Task | None = None


async def get_risk_cache() -> dict:
    """Get a copy of the risk cache."""
    async with _risk_cache_lock:
        return dict(_risk_cache)


async def set_risk_cache(data: dict) -> None:
    """Update the risk cache with new data."""
    async with _risk_cache_lock:
        _risk_cache.clear()
        _risk_cache.update(data)


async def get_risk_for_segment(segment_id: str) -> dict | None:
    """Get risk data for a specific segment."""
    async with _risk_cache_lock:
        return _risk_cache.get(segment_id)


async def find_risk_by_station(station_name: str) -> dict | None:
    """Find risk data by station name (best effort)."""
    async with _risk_cache_lock:
        station_lower = station_name.lower()
        for seg_id, risk_info in _risk_cache.items():
            if station_lower in seg_id.lower():
                return risk_info
        return None


async def _poll_risk_scores():
    """Background task to poll risk scores from Person 2 service."""
    import httpx
    from app.config import get_settings

    settings = get_settings()
    person2_base_url = settings.get("person2_base_url", "http://127.0.0.1:8001")
    poll_interval = settings.get("risk_poll_interval_seconds", 10)

    while True:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(
                    f"{person2_base_url}/api/v1/risk-scores-all",
                    timeout=3.0,
                )
                if response.status_code == 200:
                    import logging
                    logger = logging.getLogger(__name__)
                    await set_risk_cache(response.json())
                    logging.getLogger(__name__).debug("Risk cache updated from Person 2")
                else:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Person 2 risk poll returned status {response.status_code}")
        except httpx.TimeoutException:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Person 2 risk poll timeout")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Person 2 risk poll error: {type(e).__name__}")

        await asyncio.sleep(10)


_risk_poll_task: asyncio.Task | None = None


async def start_risk_polling():
    """Start the background risk polling task."""
    global _risk_poll_task
    _risk_poll_task = asyncio.create_task(_poll_risk_scores())


async def stop_risk_polling():
    """Stop the background risk polling task."""
    global _risk_poll_task
    if _risk_poll_task:
        _risk_poll_task.cancel()
        try:
            await _risk_poll_task
        except asyncio.CancelledError:
            pass