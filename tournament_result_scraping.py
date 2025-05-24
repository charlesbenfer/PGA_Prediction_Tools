#!/usr/bin/env python3
import requests
import pandas as pd
import numpy as np
from datetime import datetime

# ─── CONFIG ───────────────────────────────────────────────────────────────────
HEADERS        = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
# JSON endpoint for the full season schedule
SCHEDULE_API   = "http://site.api.espn.com/apis/site/v2/sports/golf/pga/tourschedule"
# JSON endpoint for the scoreboard on a given date
SCOREBOARD_API = "https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard"

# ─── STEP 1: FETCH & FLATTEN THE SEASON SCHEDULE ──────────────────────────────
def get_espn_schedule(year: int) -> pd.DataFrame:
    """
    Returns a DataFrame of every PGA TOUR event in `year`:
      [espnId, tournamentName, startDate (YYYYMMDD), year]
    via ESPN’s tourschedule JSON API.
    """
    r = requests.get(f"{SCHEDULE_API}?season={year}", headers=HEADERS)
    r.raise_for_status()
    data = r.json()

    # find the block for that season
    seasons = data.get("seasons", [])
    block   = next(
        (s for s in seasons if s.get("year")==year),
        None
    )
    if not block:
        raise RuntimeError(f"No season data found for {year} in tourschedule API")

    rows = []
    for ev in block.get("events", []):
        eid   = ev.get("id")
        name  = ev.get("name") or ev.get("label") or ev.get("displayName")
        # ISO8601 start date → YYYYMMDD
        start = ev.get("start") or ev.get("startDate")
        dt    = datetime.fromisoformat(start.replace("Z","+00:00"))
        rows.append({
            "espnId":         str(eid),
            "tournamentName": name,
            "startDate":      dt.strftime("%Y%m%d"),
            "year":           year
        })
    return pd.DataFrame(rows)

# ─── STEP 2: FETCH ONE DAY’S FULL SCOREBOARD ─────────────────────────────────
def get_espn_scoreboard(date_str: str) -> pd.DataFrame:
    """
    Calls ESPN’s public scoreboard API for dates=YYYYMMDD and returns
    one row per player per event with [tournament, playerId, playerName,
    position, R1–R4, total, toPar].
    """
    r = requests.get(f"{SCOREBOARD_API}?dates={date_str}", headers=HEADERS)
    r.raise_for_status()
    events = r.json().get("events", [])

    recs = []
    for evt in events:
        tour = evt.get("name","")
        comps = (evt.get("competitions") or [])[:1]
        if not comps:
            continue
        for comp in comps[0].get("competitors", []):
            p   = comp.get("competitor", {})
            rec = {
                "tournament":  tour,
                "playerId":    p.get("id"),
                "playerName":  p.get("displayName"),
                "position":    comp.get("order")
            }
            # R1–R4, safe int
            for i, line in enumerate(comp.get("linescores", []), start=1):
                dv = line.get("displayValue")
                try:
                    rec[f"R{i}"] = int(dv)
                except Exception:
                    rec[f"R{i}"] = None
            # total & toPar
            summary     = comp.get("summary",{}) or {}
            rec["total"] = summary.get("score")
            rec["toPar"] = summary.get("toPar")
            recs.append(rec)
    return pd.DataFrame(recs)

# ─── STEP 3: LOOP YEARS → EVENTS → CONCAT & SAVE ─────────────────────────────
def build_full_season(start_year: int=2015, end_year: int=2025) -> pd.DataFrame:
    all_parts = []
    for yr in range(start_year, end_year+1):
        sched = get_espn_schedule(yr)
        print(f"→ {yr}: found {len(sched)} events")
        for _, row in sched.iterrows():
            ds = row["startDate"]
            tn = row["tournamentName"]
            print(f"   • {tn} on {ds} …", end="", flush=True)
            lb = get_espn_scoreboard(ds)
            lb["year"]           = yr
            lb["tournamentName"] = tn
            all_parts.append(lb)
            print(" done.")

    if not all_parts:
        raise RuntimeError("No data fetched—check your schedule API")
    master = pd.concat(all_parts, ignore_index=True)
    master.to_csv("data/espn_full_leaderboards_2015_2025.csv", index=False)
    print(f"\nDone! Wrote {len(master)} rows to espn_full_leaderboards_2015_2025.csv")
    return master

# ─── ENTRY POINT ─────────────────────────────────────────────────────────────
if __name__=="__main__":
    build_full_season(2015, 2025)
