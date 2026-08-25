"""Seeded prototype dataset — stands in for real FPO-uploaded data until
FPOs are onboarded. Read ONLY through db/store.py.

Contains: 2-3 FPOs (name, region, lat/lon), 10-15 farmers (name,
registered phone, FPO membership, village, farm size, crops, lat/lon),
crop_records (past yields, used as advisory context), 4-6 warehouses
(location, capacity, occupancy, cost per quintal), and the alert feed.

Deliberately does NOT contain MSP prices or government schemes — those
are real public facts already in GPT-4o's knowledge, and fabricating
them would make advisory answers less credible, not more.

Seed quality matters: realistic Indian regions, village names, and crop
mixes. Every agent's output quality depends on this file.
"""
