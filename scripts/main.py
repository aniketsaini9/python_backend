# ============================================================
# LILA BLACK — FastAPI Backend
# Serves processed game data as REST APIs
# ============================================================

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
from typing import Optional

app = FastAPI(title="LILA BLACK Data API")
 
# ============================================================
# CORS — allows React frontend to call this API
# Without this, browser will block the requests
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# SERVE MINIMAP IMAGES AS STATIC FILES
# Frontend loads maps from:
#   /maps/AmbroseValley_Minimap.png
#   /maps/GrandRift_Minimap.png
#   /maps/Lockdown_Minimap.jpg
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
MINIMAPS_DIR = BASE_DIR / "minimaps"
app.mount("/maps", StaticFiles(directory=MINIMAPS_DIR), name="maps")

# ============================================================
# LOAD DATA ON STARTUP
# We load all JSON files into memory once when server starts
# Much faster than reading files on every request
# ============================================================
OUTPUT_DIR = BASE_DIR / "output"

def load_json(filename):
    try:
        with open(OUTPUT_DIR / filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {filename}: {e}")
        return []

print("📦 Loading data into memory...")
EVENTS  = load_json("events.json")
MATCHES = load_json("matches.json")
SUMMARY = load_json("summary.json")
print(f"✅ Loaded {len(EVENTS):,} events, {len(MATCHES)} matches")

# ============================================================
# API ROUTE 1 — Health Check
# Just confirms the server is running
# ============================================================

@app.get("/")
def root():
    return {"status": "ok", "message": "LILA BLACK API is running 🎮"}

# ============================================================
# API ROUTE 2 — Summary Stats
# Returns overall numbers for the dashboard
# ============================================================

@app.get("/api/summary")
def get_summary():
    return SUMMARY

# ============================================================
# API ROUTE 3 — Matches List
# Returns list of matches, filterable by map and date
# Frontend uses this to populate the match dropdown
# ============================================================

@app.get("/api/matches")
def get_matches(
    map_id: Optional[str] = Query(None),
    date:   Optional[str] = Query(None),
):
    result = MATCHES

    if map_id:
        result = [m for m in result if m["map_id"] == map_id]
    if date:
        result = [m for m in result if m["date"] == date]

    return result

# ============================================================
# API ROUTE 4 — Events
# The main data route — returns events filtered by:
#   map_id   → e.g. AmbroseValley
#   date     → e.g. 2026-02-10
#   match_id → e.g. specific match UUID
# This is what the frontend uses to draw dots on the minimap
# ============================================================

@app.get("/api/events")
def get_events(
    map_id: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    match_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    start_ts: Optional[int] = Query(None),
    end_ts: Optional[int] = Query(None),
    limit: Optional[int] = Query(5000),
):
    result = EVENTS

    if map_id:
        result = [e for e in result if e["map_id"] == map_id]

    if date:
        result = [e for e in result if e["date"] == date]

    if match_id:
        result = [e for e in result if e["match_id"] == match_id]

    if event_type:
        result = [e for e in result if e["event"] == event_type]

    if start_ts:
        result = [e for e in result if e["ts_ms"] >= start_ts]

    if end_ts:
        result = [e for e in result if e["ts_ms"] <= end_ts]

    return result[:limit]

# ============================================================
# API ROUTE 5 — Maps Metadata (NEW)
# Returns available maps + dates + minimap image URLs
# Frontend uses this to populate filter dropdowns
# and know which minimap image to load
# ============================================================

@app.get("/api/maps")
def get_maps():
    maps = {}

    for m in MATCHES:
        map_id = m["map_id"]
        date   = m["date"]

        if map_id not in maps:
            maps[map_id] = {
                "map_id": map_id,
                "dates": set(),
                "total_matches": 0
            }

        maps[map_id]["dates"].add(date)
        maps[map_id]["total_matches"] += 1

    # Convert sets → sorted lists for JSON serialization
    result = []
    for map_id, data in maps.items():
        # Lockdown uses .jpg, others use .png
        ext = "jpg" if map_id == "Lockdown" else "png"
        result.append({
            "map_id":         map_id,
            "dates":          sorted(list(data["dates"])),
            "total_matches":  data["total_matches"],
            "minimap_url":    f"/maps/{map_id}_Minimap.{ext}"
        })

    return result


@app.get("/api/heatmap")
def get_heatmap(
    map_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query("Kill")
):
    result = EVENTS

    if map_id:
        result = [e for e in result if e["map_id"] == map_id]

    if event_type:
        result = [e for e in result if e["event"] == event_type]

    return result
