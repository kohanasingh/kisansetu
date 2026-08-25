"""Open-Meteo integration — free, no API key, real forecast data (not
mocked). Fetches short-range forecasts per FPO region (lat/lon from
db/store.py) and exposes threshold checks for heavy rain, drought risk, and
storms that agents/climate.py evaluates on each scheduler tick.
"""
