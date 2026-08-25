"""Periodic background loop driving the climate-watch agent.

Time-driven rather than event-driven — weather has no natural trigger
event, which makes this the one background-job shape with no counterpart
in the reference project. Started once at app startup via
asyncio.create_task; wakes on an interval, calls agents/climate.py to check
each FPO region against Open-Meteo, and writes qualifying alerts to
db/store.py.

No cron, no Celery — kept in-process to match the single-instance Cloud Run
deployment (see deploy/cloud_run.md for why --no-cpu-throttling is required
for this loop to keep running between requests).
"""
