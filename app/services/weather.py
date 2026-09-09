"""Open-Meteo integration — free, no API key, real forecast data (not
mocked). Fetches a short-range daily forecast per FPO region (lat/lon from
db/store.py) and evaluates it against fixed thresholds for heavy rain,
storm, and drought risk. agents/climate.py calls this on each scheduler
tick and on the /demo "Simulate Climate Alert" trigger.
"""

from __future__ import annotations

import logging

import httpx

from app.retry import with_retry

logger = logging.getLogger("kisansetu.weather")

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 3

# Fixed, documented thresholds — no ML, no historical baseline (that would
# need real climatology data this prototype doesn't have).
HEAVY_RAIN_MM = 40.0        # daily precipitation_sum over this -> heavy_rain
STORM_WIND_KMH = 40.0       # daily wind_speed_10m_max over this -> storm
STORM_WEATHERCODES = {95, 96, 99}  # WMO thunderstorm codes -> storm
DROUGHT_TOTAL_MM = 2.0      # total precip across the whole window under this -> drought risk


class WeatherError(Exception):
    """Raised after retries are exhausted fetching an Open-Meteo forecast."""


async def get_forecast(lat: float, lon: float) -> dict | None:
    """Real Open-Meteo daily forecast, retried with backoff (same pattern
    as every LLM call in app/llm.py) before giving up. Returns None only
    once retries are exhausted — callers must treat that as 'no alert this
    tick', never as license to fabricate one."""
    params = {
        "latitude": lat, "longitude": lon,
        "daily": "precipitation_sum,wind_speed_10m_max,weathercode",
        "forecast_days": FORECAST_DAYS, "timezone": "auto",
    }

    async def call():
        async with httpx.AsyncClient(timeout=15) as http:
            resp = await http.get(FORECAST_URL, params=params)
            resp.raise_for_status()
            return resp.json()

    try:
        return await with_retry(
            call, what=f"weather.get_forecast({lat},{lon})",
            exceptions=(httpx.HTTPError,), error_cls=WeatherError,
        )
    except WeatherError:
        logger.exception("open-meteo forecast fetch failed for (%s, %s) after retries", lat, lon)
        return None


def evaluate_alert(forecast: dict) -> dict | None:
    """Real threshold evaluation over the fetched forecast — no LLM
    reasoning, no invented figures. Returns {kind, severity, message} for
    the single most urgent condition found, or None if nothing crosses a
    threshold."""
    daily = forecast.get("daily", {})
    precip = daily.get("precipitation_sum", [])
    wind = daily.get("wind_speed_10m_max", [])
    codes = daily.get("weathercode", [])

    for i, mm in enumerate(precip):
        if mm is not None and mm >= HEAVY_RAIN_MM:
            return {
                "kind": "heavy_rain", "severity": "high" if mm >= 80 else "moderate",
                "message": (f"Heavy rain expected in the next {i + 1} day(s): "
                            f"{mm:.0f}mm forecast — delay harvest where possible and "
                            f"check drainage in low-lying plots."),
            }

    for i, (kmh, code) in enumerate(zip(wind, codes)):
        is_storm_wind = kmh is not None and kmh >= STORM_WIND_KMH
        is_storm_code = code in STORM_WEATHERCODES
        if is_storm_wind or is_storm_code:
            return {
                "kind": "storm", "severity": "high",
                "message": (f"Storm conditions expected in the next {i + 1} day(s) "
                            f"(wind up to {kmh:.0f} km/h) — secure stored stock and avoid "
                            f"open-field work during the warning window."),
            }

    total_precip = sum(p for p in precip if p is not None)
    if precip and total_precip < DROUGHT_TOTAL_MM:
        return {
            "kind": "drought", "severity": "low",
            "message": (f"Below-normal rainfall forecast over the next {len(precip)} days "
                         f"(only {total_precip:.1f}mm total) — monitor irrigation scheduling."),
        }

    return None
