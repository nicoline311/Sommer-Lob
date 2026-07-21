"""
Henter aktiviteter fra to Strava-klubber, fjerner alt der lå der FØR
konkurrencen startede (1. juli), og bygger en samlet, dedupliceret liste
over alle løb der er kommet til siden. Til sidst skrives docs/leaderboard.json
som webappen (docs/index.html) læser.

VIGTIGT AT FORSTÅ - Stravas klub-endpoint:
- Returnerer INGEN aktivitets-ID og INGEN dato/tidspunkt (kun de seneste
  ca. 200 aktiviteter, "nyeste først"). Vi kan derfor ikke bruge et ID til
  at kende en aktivitet, og vi kan ikke filtrere på dato direkte i API'et.
- Løsning: vi laver selv en "fingeraftryk"-nøgle ud fra atlet + navn +
  distance + tid, og gemmer alle nøgler vi har set i data/activities_store.json.
  Alt der matcher en nøgle i "før juli"-filerne bliver droppet. Alt nyt bliver
  føjet til store'en, som vokser over tid og er den "database" vi har.
- Konsekvens: scriptet SKAL køre jævnligt (fx hver 3.-6. time) via GitHub
  Actions, ellers kan meget aktive klubber skubbe aktiviteter helt ud af
  de seneste 200, før vi når at se dem.
"""

import hashlib
import json
import os
import time
from pathlib import Path

import requests

BASE_URL = "https://www.strava.com/api/v3/"
DATA_DIR = Path("data")
DOCS_DIR = Path("docs")
STORE_FILE = DATA_DIR / "activities_store.json"
OUTPUT_FILE = DOCS_DIR / "leaderboard.json"

# Konfiguration af de to klubber. Navne og id'er kommer fra GitHub Actions
# "variables", tokens fra GitHub Actions "secrets" (se README).
CLUBS = [
    {
        "id": os.environ["KLUB1_ID"],
        "name": os.environ["KLUB1_NAVN"],
        "refresh_token": os.environ["STRAVA_REFRESH_TOKEN_1"],
        "baseline_file": DATA_DIR / "baseline_klub1.json",
    },
    {
        "id": os.environ["KLUB2_ID"],
        "name": os.environ["KLUB2_NAVN"],
        "refresh_token": os.environ["STRAVA_REFRESH_TOKEN_2"],
        "baseline_file": DATA_DIR / "baseline_klub2.json",
    },
]

CLIENT_ID = os.environ["STRAVA_CLIENT_ID"]
CLIENT_SECRET = os.environ["STRAVA_CLIENT_SECRET"]


def refresh_access_token(refresh_token: str) -> str:
    resp = requests.post(
        f"{BASE_URL}oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_all_club_activities(club_id: str, access_token: str) -> list:
    """Henter ALLE sider (ikke kun sidste side - det var en bug i det
    oprindelige script, hvor filen blev overskrevet i hvert loop)."""
    activities = []
    page = 1
    per_page = 200
    headers = {"Authorization": f"Bearer {access_token}"}

    while True:
        resp = requests.get(
            f"{BASE_URL}clubs/{club_id}/activities",
            params={"per_page": per_page, "page": page},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        activities.extend(batch)
        if len(batch) < per_page:
            break
        page += 1
        time.sleep(2)

    return activities


def activity_key(activity: dict, club_id: str) -> str:
    """Laver en stabil 'fingeraftryk'-nøgle for en aktivitet, siden Strava
    ikke giver os et ID eller en dato på klub-endpointet."""
    athlete = activity.get("athlete", {})
    raw = "|".join(
        [
            club_id,
            athlete.get("firstname", ""),
            athlete.get("lastname", ""),
            activity.get("name", ""),
            str(activity.get("distance", "")),
            str(activity.get("moving_time", "")),
            str(activity.get("elapsed_time", "")),
            activity.get("type", ""),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_json(path: Path, default):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def load_baseline_keys(club: dict) -> set:
    """Læser jeres 'klubnavn_før_juli.json' og regner keys ud, så vi kan
    ekskludere alt der allerede lå der inden konkurrencen startede."""
    baseline = load_json(club["baseline_file"], [])
    return {activity_key(a, club["id"]) for a in baseline}


def main():
    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)

    store = load_json(STORE_FILE, [])
    store_keys = {row["key"] for row in store}

    new_rows = []

    for club in CLUBS:
        print(f"Henter aktiviteter for {club['name']}...")
        access_token = refresh_access_token(club["refresh_token"])
        activities = fetch_all_club_activities(club["id"], access_token)
        baseline_keys = load_baseline_keys(club)

        added = 0
        for activity in activities:
            key = activity_key(activity, club["id"])

            # Spring over hvis den lå i "før juli"-filen ELLER vi allerede
            # har set den i en tidligere kørsel.
            if key in baseline_keys or key in store_keys:
                continue

            athlete = activity.get("athlete", {})
            row = {
                "key": key,
                "club": club["name"],
                "athlete": f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
                "name": activity.get("name", ""),
                "distance_km": round(activity.get("distance", 0) / 1000, 2),
                "type": activity.get("type", ""),
                "first_seen": int(time.time()),
            }
            store.append(row)
            store_keys.add(key)
            new_rows.append(row)
            added += 1

        print(f"  {added} nye aktiviteter fundet.")

    with open(STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)

    build_leaderboard(store)


def build_leaderboard(store: list):
    club_totals = {}
    athlete_totals = {}

    for row in store:
        club = row["club"]
        athlete_key = (row["athlete"], club)

        club_totals[club] = club_totals.get(club, 0) + row["distance_km"]
        athlete_totals[athlete_key] = athlete_totals.get(athlete_key, 0) + row["distance_km"]

    clubs_out = [
        {"club": club, "total_km": round(total, 1)}
        for club, total in sorted(club_totals.items(), key=lambda x: -x[1])
    ]

    athletes_out = [
        {"athlete": athlete, "club": club, "total_km": round(total, 1)}
        for (athlete, club), total in sorted(athlete_totals.items(), key=lambda x: -x[1])
    ]

    output = {
        "generated_at": int(time.time()),
        "competition_start": "2026-07-01",
        "clubs": clubs_out,
        "athletes": athletes_out,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Skrev {OUTPUT_FILE} med {len(clubs_out)} klubber og {len(athletes_out)} atleter.")


if __name__ == "__main__":
    main()
