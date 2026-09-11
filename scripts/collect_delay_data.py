"""Script for collecting delay observations from runningstatus.in.

Person 1 — Data & Prediction Engine.

This script is designed for collecting observations from runningstatus.in,
containing at minimum:
- train_number
- station
- scheduled_time
- actual_time
- delay_minutes
- observation_timestamp

The script includes robust structure and parsing logic that can be completed
once the site's current HTML/data format is inspected.

Features:
- Sensible logging
- Error handling for unreachable website
- Configurable request intervals (to respect reasonable limits)
- No aggressive scraping behavior
- Output saved to project data directories in standard format
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# Project imports
from src.data import validate_schedule_df, clean_schedule_df
from app.config import get_settings

# Configure project-level logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Default scraping settings (can be overridden via environment)
DEFAULT_SCRAPING_INTERVAL_SECONDS = int(
    __import__("os").getenv("SCRAPING_INTERVAL_SECONDS", "300")
)
DEFAULT_REQUEST_TIMEOUT_SECONDS = int(
    __import__("os").getenv("REQUEST_TIMEOUT_SECONDS", "30")
)
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 5

# runningstatus.in base URL
RUNNINGSTATUS_BASE_URL = "https://runningstatus.in"


# ---------------------------------------------------------------------------
# Helper functions for HTML parsing
# ---------------------------------------------------------------------------

def _fetch_page(train_number: str, station: str = "") -> Optional[str]:
    """Fetch the HTML page for a train's running status.

    Parameters
    ----------
    train_number : str
        Train number identifier.
    station : str, optional
        Station name, if applicable for the query.

    Returns
    -------
    Optional[str]
        HTML content of the page, or ``None`` if the fetch failed.
    """
    import urllib.parse

    # Construct the runningstatus.in URL
    # The pattern is typically: https://runningstatus.in/<train_number>
    path = urllib.parse.quote(train_number, safe="")
    url = f"{RUNNINGSTATUS_BASE_URL}/{path}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    for attempt in range(DEFAULT_MAX_RETRIES):
        try:
            logger.debug("Fetching running status page (attempt %d): %s", attempt + 1, url)
            response = requests.get(
                url,
                headers=headers,
                timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as exc:
            logger.warning(
                "Fetch attempt %d failed for %s: %s", attempt + 1, url, exc
            )
            if attempt < DEFAULT_MAX_RETRIES - 1:
                time.sleep(DEFAULT_RETRY_DELAY_SECONDS)
            else:
                logger.error(
                    "All %d fetch attempts failed for %s", DEFAULT_MAX_RETRIES, url
                )
                return None


def _parse_observations(html: str, train_number: str) -> List[Dict[str, str]]:
    """Parse delay observations from the runningstatus.in HTML.

    This is a placeholder parser. The exact HTML structure of runningstatus.in
    will determine the parsing logic. After the real dataset is inspected,
    this function will be updated with the correct selectors.

    Parameters
    ----------
    html : str
        HTML content of the runningstatus.in page.
    train_number : str
        Train number for context.

    Returns
    -------
    List[Dict[str, str]]
        List of observation dictionaries with keys:
        - station
        - scheduled_time
        - actual_time
        - delay_minutes
    """
    observations: List[Dict[str, str]] = []
    soup = BeautifulSoup(html, "html.parser")

    # TODO: After inspecting the actual runningstatus.in HTML structure,
    # update the selectors below to match the real page layout.
    # Current placeholders assume common table-row patterns.

    # Example placeholder: look for a table with observation data
    # tables = soup.find_all("table")
    # for table in tables:
    #     rows = table.find_all("tr")
    #     for row in rows:
    #         cols = row.find_all("td")
    #         if len(cols) >= 3:
    #             station = cols[0].get_text(strip=True)
    #             scheduled = cols[1].get_text(strip=True)
    #             actual = cols[2].get_text(strip=True)
    #             # Compute delay
    #             delay = _compute_delay_from_times(scheduled, actual)
    #             observations.append({
    #                 "train_number": train_number,
    #                 "station": station,
    #                 "scheduled_time": scheduled,
    #                 "actual_time": actual,
    #                 "delay_minutes": str(delay) if delay is not None else "0",
    #             })

    logger.info("Parsed %d observations from runningstatus.in (placeholder parser)", len(observations))
    return observations


def _compute_delay_from_times(scheduled: str, actual: str) -> Optional[float]:
    """Compute delay in minutes from scheduled and actual time strings.

    Placeholder implementation. Exact parsing depends on the time format
    used by runningstatus.in and will be refined after the real dataset
    is inspected.

    Parameters
    ----------
    scheduled : str
        Scheduled time string.
    actual : str
        Actual time string.

    Returns
    -------
    Optional[float]
        Delay in minutes, or ``None`` if times cannot be parsed.
    """
    # Placeholder: return None until proper time-format parsing is defined
    # after the real dataset is available.
    return None


# ---------------------------------------------------------------------------
# Main collection function
# ---------------------------------------------------------------------------

def collect_train_observations(
    train_number: str,
    station: str = "",
    output_dir: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Collect delay observations for a train from runningstatus.in.

    This is the primary entry point for the data collection script. It
    fetches the running status page, parses the observations, and saves
    them to the project's data directory in CSV format.

    Parameters
    ----------
    train_number : str
        Train number to collect observations for.
    station : str, optional
        Specific station, if querying a particular station.
    output_dir : str, optional
        Base output directory. Defaults to project-relative ``data/raw``.
    force : bool, optional
        If ``True``, overwrite existing data. If ``False`` (default), skip
        if data already exists.

    Returns
    -------
    Dict[str, Any]
        Dictionary with collection results:
        - ``success``: whether collection succeeded
        - ``train_number``: the train number queried
        - ``observations_count``: number of observations collected
        - ``saved_path``: path where data was saved (if successful)
        - ``error``: error message (if unsuccessful)
    """
    import logging
    logger = logging.getLogger(__name__)

    # Determine output directory
    if output_dir is None:
        settings = get_settings()
        output_dir = str(Path(settings["raw_data_dir"]))

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Fetch the page
    html = _fetch_page(train_number, station)
    if html is None:
        return {
            "success": False,
            "train_number": train_number,
            "observations_count": 0,
            "saved_path": None,
            "error": "Failed to fetch running status page",
        }

    # Parse observations
    observations = _parse_observations(html, train_number)
    observations_count = len(observations)

    if observations_count == 0:
        return {
            "success": False,
            "train_number": train_number,
            "observations_count": 0,
            "saved_path": None,
            "error": "No observations parsed from the page",
        }

    # Convert to DataFrame and save
    try:
        import pandas as pd

        # Build records with train_number included
        records = []
        for obs in observations:
            record = {
                "train_number": train_number,
                "station": obs.get("station", ""),
                "scheduled_time": obs.get("scheduled_time", ""),
                "actual_time": obs.get("actual_time", ""),
                "delay_minutes": obs.get("delay_minutes", "0"),
                "observation_timestamp": datetime.utcnow().isoformat() + "Z",
            }
            records.append(record)

        df = pd.DataFrame(records)

        # Save to CSV
        filename = f"train_{train_number}_observations.csv"
        save_file = output_path / filename
        df.to_csv(save_file, index=False)

        logger.info(
            "Collected %d observations for train %s, saved to %s",
            observations_count,
            train_number,
            save_file,
        )

        return {
            "success": True,
            "train_number": train_number,
            "observations_count": observations_count,
            "saved_path": str(save_file),
            "error": None,
        }

    except Exception as exc:  # pragma: no cover
        logger.error("Failed to save observations: %s", exc)
        return {
            "success": False,
            "train_number": train_number,
            "observations_count": observations_count,
            "saved_path": None,
            "error": f"Failed to save observations: {exc}",
        }


# ---------------------------------------------------------------------------
# Batch collection utility
# ---------------------------------------------------------------------------

def batch_collect(
    train_numbers: List[str],
    station: str = "",
    output_dir: Optional[str] = None,
    interval_seconds: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Collect observations for multiple trains in batch.

    Parameters
    ----------
    train_numbers : List[str]
        List of train numbers to collect.
    station : str, optional
        Specific station for all queries.
    output_dir : str, optional
        Base output directory.
    interval_seconds : int, optional
        Seconds to wait between consecutive requests. Defaults to
        ``SCRAPING_INTERVAL_SECONDS`` env var or 300.

    Returns
    -------
    List[Dict[str, Any]]
        List of result dictionaries, one per train number.
    """
    if interval_seconds is None:
        interval_seconds = DEFAULT_SCRAPING_INTERVAL_SECONDS

    results: List[Dict[str, Any]] = []
    for i, train_number in enumerate(train_numbers):
        result = collect_train_observations(train_number, station)
        results.append(result)

        # Respect rate limiting: wait between requests (not after the last one)
        if i < len(train_numbers) - 1:
            logger.info(
                "Waiting %d seconds before next train collection...",
                interval_seconds,
            )
            time.sleep(interval_seconds)

    return results