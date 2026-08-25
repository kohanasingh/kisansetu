"""Agent — Climate watch. On each scheduler tick, checks every FPO region's
Open-Meteo forecast against alert thresholds (heavy rain, drought risk,
storm) and writes qualifying alerts to the shared feed in db/store.py.

The feed is read by web/fpo.html (dashboard alert card) and web/demo.html
(where firing an alert is one of the demo control buttons — an external
event a conversation can't produce on its own). Over the real WhatsApp
transport these become outbound advisory messages to affected farmers.
"""
