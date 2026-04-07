# ============================================================
# LILA BLACK — Data Pipeline
# Reads all .nakama-0 files → outputs clean JSON for frontend
# ============================================================

import pyarrow.parquet as pq
import pandas as pd
import numpy as np
import os
import json
import re
from pathlib import Path

print("✅ All libraries imported successfully!")

# ============================================================
# PART 2A — MAP CONFIGURATION
# ============================================================

MAP_CONFIG = {
    "AmbroseValley": {"scale": 900,  "origin_x": -370, "origin_z": -473},
    "GrandRift":     {"scale": 581,  "origin_x": -290, "origin_z": -290},
    "Lockdown":      {"scale": 1000, "origin_x": -500, "origin_z": -500},
}

# ============================================================
# PART 2B — COORDINATE CONVERSION FUNCTION
# ============================================================

def world_to_pixel(x, z, map_id):
    cfg = MAP_CONFIG.get(map_id)
    if cfg is None:
        return None, None
    u = (x - cfg["origin_x"]) / cfg["scale"]
    v = (z - cfg["origin_z"]) / cfg["scale"]
    pixel_x = round(float(u * 1024), 2)
    pixel_y = round(float((1 - v) * 1024), 2)
    return pixel_x, pixel_y

# ============================================================
# PART 2C — BOT DETECTION
# ============================================================

UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)

def is_human(user_id):
    return bool(UUID_PATTERN.match(str(user_id)))

# ============================================================
# PART 2D — SINGLE FILE READER
# ============================================================

def read_nakama_file(filepath, date_str):
    try:
        df = pq.read_table(filepath).to_pandas()

        df['event'] = df['event'].apply(
            lambda x: x.decode('utf-8') if isinstance(x, bytes) else str(x)
        )

        df['is_bot'] = ~df['user_id'].apply(is_human)
        df['date'] = date_str

        df['pixel_x'] = None
        df['pixel_y'] = None

        for idx, row in df.iterrows():
            px, py = world_to_pixel(row['x'], row['z'], row['map_id'])
            df.at[idx, 'pixel_x'] = px
            df.at[idx, 'pixel_y'] = py

        df['ts_ms'] = df['ts'].astype('int64') // 1_000_000

        return df

    except Exception as e:
        print(f"  ⚠️  Skipped {filepath}: {e}")
        return None

# ============================================================
# PART 3A — READ ALL FILES FROM ALL 5 DAYS
# ============================================================

DATA_ROOT = Path("../player_data")  # ← THIS is what was missing!

DAY_MAP = {
    "February_10": "2026-02-10",
    "February_11": "2026-02-11",
    "February_12": "2026-02-12",
    "February_13": "2026-02-13",
    "February_14": "2026-02-14",
}

print("\n📂 Reading all files from all days...")

all_frames = []
skipped = 0
total = 0

for folder_name, date_str in DAY_MAP.items():
    folder_path = DATA_ROOT / folder_name

    if not folder_path.exists():
        print(f"  ⚠️  Folder not found: {folder_name}")
        continue

    files = [f for f in folder_path.iterdir() if f.is_file()]
    print(f"\n  📅 {folder_name} → {len(files)} files")

    for filepath in files:
        total += 1
        df = read_nakama_file(filepath, date_str)
        if df is not None:
            all_frames.append(df)
        else:
            skipped += 1

print(f"\n✅ Done reading! {total} files | {skipped} skipped")

# ============================================================
# PART 3B — COMBINE & CLEAN
# ============================================================

print("\n🔗 Combining all data...")
df_all = pd.concat(all_frames, ignore_index=True)
print(f"✅ Total rows: {len(df_all):,}")
print(f"✅ Unique matches: {df_all['match_id'].nunique()}")
print(f"✅ Unique players: {df_all['user_id'].nunique()}")
print(f"✅ Maps: {df_all['map_id'].unique().tolist()}")
print(f"✅ Event breakdown:\n{df_all['event'].value_counts()}")

print("\n🧹 Cleaning data...")
before = len(df_all)
df_all = df_all.dropna(subset=['pixel_x', 'pixel_y'])
after = len(df_all)
print(f"  Dropped {before - after} rows with missing coords")
df_all['match_id'] = df_all['match_id'].str.replace('.nakama-0', '', regex=False)

# ============================================================
# PART 3C — SAVE OUTPUT JSON FILES
# ============================================================

print("\n💾 Saving JSON output files...")
OUTPUT_DIR = Path("../output")
OUTPUT_DIR.mkdir(exist_ok=True)

# --- events.json ---
events_df = df_all[[
    'user_id', 'match_id', 'map_id', 'event',
    'is_bot', 'pixel_x', 'pixel_y', 'ts_ms', 'date'
]].copy()

events_df.to_json(
    OUTPUT_DIR / "events.json",
    orient='records',
    indent=2
)
print(f"  ✅ events.json saved → {len(events_df):,} rows")

# --- matches.json ---
matches = []
for match_id, group in df_all.groupby('match_id'):
    matches.append({
        "match_id": match_id,
        "map_id": group['map_id'].iloc[0],
        "date": group['date'].iloc[0],
        "human_count": int((~group['is_bot']).sum()),
        "bot_count": int(group['is_bot'].sum()),
        "total_events": len(group)
    })

with open(OUTPUT_DIR / "matches.json", 'w') as f:
    json.dump(matches, f, indent=2)
print(f"  ✅ matches.json saved → {len(matches)} matches")

# --- summary.json ---
summary = {
    "total_events": len(df_all),
    "total_matches": df_all['match_id'].nunique(),
    "total_players": df_all['user_id'].nunique(),
    "by_map": df_all.groupby('map_id')['event'].count().to_dict(),
    "by_date": df_all.groupby('date')['event'].count().to_dict(),
    "event_types": df_all['event'].value_counts().to_dict(),
}

with open(OUTPUT_DIR / "summary.json", 'w') as f:
    json.dump(summary, f, indent=2)
print(f"  ✅ summary.json saved")

print("\n🎉 BACKEND COMPLETE! Check your output/ folder.")
print(f"   📁 {OUTPUT_DIR.resolve()}")