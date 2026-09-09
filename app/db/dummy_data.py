"""Seeded prototype dataset — stands in for real FPO-uploaded data until
FPOs are onboarded. Read ONLY through db/store.py; no other module should
import this file directly.

3 FPOs across real Indian agricultural regions (Nashik grape belt, Ludhiana
wheat/rice belt, Belagavi sugarcane/cotton belt), 13 farmers with real
village names and phone-shaped numbers, 6 warehouses, a handful of crop
yield records, and a small live alert feed.

Deliberately contains NO msp_price or scheme table — those are real public
facts already in GPT-4o's own knowledge; fabricating them would make
advisory answers less credible, not more. See PROJECT_SPEC.md "Sourcing
MSP and schemes".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

FPOS = [
    {
        "id": "fpo_1",
        "name": "Nashik Grape Growers FPO",
        "region_name": "Nashik, Maharashtra",
        "lat": 19.9975,
        "lon": 73.7898,
        "contact_phone": "+919876500001",
    },
    {
        "id": "fpo_2",
        "name": "Ludhiana Wheat Producers FPO",
        "region_name": "Ludhiana, Punjab",
        "lat": 30.9010,
        "lon": 75.8573,
        "contact_phone": "+919876500002",
    },
    {
        "id": "fpo_3",
        "name": "Belagavi Sugarcane FPO",
        "region_name": "Belagavi, Karnataka",
        "lat": 15.8497,
        "lon": 74.4977,
        "contact_phone": "+919876500003",
    },
]

FARMERS = [
    # --- Nashik Grape Growers FPO ---
    {"id": "farmer_1", "name": "Ramesh Pawar", "phone": "+919812345601", "fpo_id": "fpo_1",
     "village": "Niphad", "farm_size_acres": 4.5, "crops": ["grapes", "onion"],
     "lat": 20.0865, "lon": 74.1103},
    {"id": "farmer_2", "name": "Sunita Gaikwad", "phone": "+919812345602", "fpo_id": "fpo_1",
     "village": "Dindori", "farm_size_acres": 3.0, "crops": ["grapes"],
     "lat": 20.2033, "lon": 73.8283},
    {"id": "farmer_3", "name": "Vijay Shinde", "phone": "+919812345603", "fpo_id": "fpo_1",
     "village": "Sinnar", "farm_size_acres": 6.2, "crops": ["onion", "tomato"],
     "lat": 19.8493, "lon": 73.9971},
    {"id": "farmer_4", "name": "Kavita Bhosale", "phone": "+919812345604", "fpo_id": "fpo_1",
     "village": "Igatpuri", "farm_size_acres": 2.5, "crops": ["tomato", "grapes"],
     "lat": 19.6968, "lon": 73.5626},
    {"id": "farmer_5", "name": "Anil Wagh", "phone": "+919812345605", "fpo_id": "fpo_1",
     "village": "Niphad", "farm_size_acres": 5.0, "crops": ["grapes", "onion"],
     "lat": 20.0812, "lon": 74.1050},

    # --- Ludhiana Wheat Producers FPO ---
    {"id": "farmer_6", "name": "Gurpreet Singh", "phone": "+919812345606", "fpo_id": "fpo_2",
     "village": "Khanna", "farm_size_acres": 8.0, "crops": ["wheat", "rice"],
     "lat": 30.7046, "lon": 76.2222},
    {"id": "farmer_7", "name": "Manjeet Kaur", "phone": "+919812345607", "fpo_id": "fpo_2",
     "village": "Jagraon", "farm_size_acres": 5.5, "crops": ["wheat", "potato"],
     "lat": 30.7898, "lon": 75.4756},
    {"id": "farmer_8", "name": "Harpreet Sidhu", "phone": "+919812345608", "fpo_id": "fpo_2",
     "village": "Samrala", "farm_size_acres": 7.0, "crops": ["rice", "wheat"],
     "lat": 30.8377, "lon": 76.1911},
    {"id": "farmer_9", "name": "Baljeet Kaur", "phone": "+919812345609", "fpo_id": "fpo_2",
     "village": "Payal", "farm_size_acres": 4.0, "crops": ["potato", "wheat"],
     "lat": 30.7481, "lon": 76.1728},

    # --- Belagavi Sugarcane FPO ---
    {"id": "farmer_10", "name": "Basavaraj Patil", "phone": "+919812345610", "fpo_id": "fpo_3",
     "village": "Gokak", "farm_size_acres": 6.0, "crops": ["sugarcane"],
     "lat": 16.1667, "lon": 74.8333},
    {"id": "farmer_11", "name": "Shobha Desai", "phone": "+919812345611", "fpo_id": "fpo_3",
     "village": "Chikodi", "farm_size_acres": 3.5, "crops": ["sugarcane", "cotton"],
     "lat": 16.4333, "lon": 74.5833},
    {"id": "farmer_12", "name": "Mahesh Kulkarni", "phone": "+919812345612", "fpo_id": "fpo_3",
     "village": "Bailhongal", "farm_size_acres": 4.8, "crops": ["cotton", "maize"],
     "lat": 15.8167, "lon": 74.8500},
    {"id": "farmer_13", "name": "Lakshmi Naik", "phone": "+919812345613", "fpo_id": "fpo_3",
     "village": "Khanapur", "farm_size_acres": 2.8, "crops": ["maize", "sugarcane"],
     "lat": 15.6333, "lon": 74.5000},
]

CROP_RECORDS = [
    {"farmer_id": "farmer_1", "crop": "grapes", "season": "rabi", "year": 2024, "yield_quintal": 92.0},
    {"farmer_id": "farmer_1", "crop": "onion", "season": "kharif", "year": 2023, "yield_quintal": 58.0},
    {"farmer_id": "farmer_2", "crop": "grapes", "season": "rabi", "year": 2024, "yield_quintal": 61.0},
    {"farmer_id": "farmer_3", "crop": "onion", "season": "kharif", "year": 2024, "yield_quintal": 110.0},
    {"farmer_id": "farmer_3", "crop": "tomato", "season": "rabi", "year": 2023, "yield_quintal": 74.0},
    {"farmer_id": "farmer_4", "crop": "tomato", "season": "rabi", "year": 2024, "yield_quintal": 40.0},
    {"farmer_id": "farmer_6", "crop": "wheat", "season": "rabi", "year": 2024, "yield_quintal": 155.0},
    {"farmer_id": "farmer_6", "crop": "rice", "season": "kharif", "year": 2023, "yield_quintal": 132.0},
    {"farmer_id": "farmer_7", "crop": "wheat", "season": "rabi", "year": 2024, "yield_quintal": 98.0},
    {"farmer_id": "farmer_8", "crop": "rice", "season": "kharif", "year": 2024, "yield_quintal": 121.0},
    {"farmer_id": "farmer_10", "crop": "sugarcane", "season": "kharif", "year": 2024, "yield_quintal": 410.0},
    {"farmer_id": "farmer_11", "crop": "sugarcane", "season": "kharif", "year": 2023, "yield_quintal": 265.0},
    {"farmer_id": "farmer_12", "crop": "cotton", "season": "kharif", "year": 2024, "yield_quintal": 18.5},
]

WAREHOUSES = [
    {"id": "wh_1", "name": "Niphad Cold Storage", "fpo_id": "fpo_1",
     "lat": 20.0865, "lon": 74.1103, "capacity_quintal": 5000, "occupied_quintal": 3200,
     "cost_per_quintal": 45},
    {"id": "wh_2", "name": "Sinnar Grain Warehouse", "fpo_id": "fpo_1",
     "lat": 19.8493, "lon": 73.9971, "capacity_quintal": 8000, "occupied_quintal": 6100,
     "cost_per_quintal": 38},
    {"id": "wh_3", "name": "Khanna Godown", "fpo_id": "fpo_2",
     "lat": 30.7046, "lon": 76.2222, "capacity_quintal": 12000, "occupied_quintal": 9800,
     "cost_per_quintal": 30},
    {"id": "wh_4", "name": "Samrala Storage Complex", "fpo_id": "fpo_2",
     "lat": 30.8377, "lon": 76.1911, "capacity_quintal": 6000, "occupied_quintal": 2100,
     "cost_per_quintal": 33},
    {"id": "wh_5", "name": "Gokak Warehouse", "fpo_id": "fpo_3",
     "lat": 16.1667, "lon": 74.8333, "capacity_quintal": 4000, "occupied_quintal": 3500,
     "cost_per_quintal": 40},
    {"id": "wh_6", "name": "Bailhongal Storage Yard", "fpo_id": "fpo_3",
     "lat": 15.8167, "lon": 74.8500, "capacity_quintal": 3000, "occupied_quintal": 900,
     "cost_per_quintal": 42},
]

# Known villages for identity-resolution path 3/4 (nearest-FPO-by-village).
# The prototype's stand-in for geocoding — a farmer mentioning any of these
# names resolves to real coordinates. Deliberately broader than "villages
# where a seeded farmer lives": includes a couple of real villages far from
# every FPO's catchment, so path 4 (no FPO within reach) is genuinely
# reachable, not just theoretical.
VILLAGES = [
    {"name": f["village"], "lat": f["lat"], "lon": f["lon"]} for f in FARMERS
] + [
    {"name": "Kohima", "lat": 25.6751, "lon": 94.1086},
    {"name": "Leh", "lat": 34.1526, "lon": 77.5771},
]

_now = datetime.now(timezone.utc)

ALERTS = [
    {"id": "alert_1", "fpo_id": "fpo_1", "kind": "heavy_rain", "severity": "moderate",
     "message": "Heavy rain expected across Nashik district over the next 48 hours — "
                "delay grape harvest where possible and check drainage in low-lying plots.",
     "created_at": (_now - timedelta(hours=5)).isoformat()},
    {"id": "alert_2", "fpo_id": "fpo_2", "kind": "storm", "severity": "high",
     "message": "Storm warning for Ludhiana district tomorrow — secure stored wheat stocks "
                "and avoid open-field work during the warning window.",
     "created_at": (_now - timedelta(hours=14)).isoformat()},
    {"id": "alert_3", "fpo_id": "fpo_3", "kind": "drought", "severity": "low",
     "message": "Below-normal rainfall trend observed in Belagavi region this month — "
                "monitor irrigation scheduling for sugarcane plots.",
     "created_at": (_now - timedelta(days=2)).isoformat()},
]
