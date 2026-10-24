"""Download a year of GB grid data from Elexon's Insights API (no key needed).

Datasets (each saved to data/raw/elexon_<name>.csv, UTC, ascending):
    mid     Market Index price (APX), £/MWh, half-hourly: the wholesale price Agile follows
    demand  National demand outturn (INDO/ITSDO), MW, half-hourly
    fuelhh  Generation by fuel type (wind, gas, nuclear ...), MW, half-hourly, long format

Usage:
    python scripts/fetch_elexon.py                       # all three, last 365 days
    python scripts/fetch_elexon.py --only mid demand --days 400
"""
import argparse
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

BASE = "https://data.elexon.co.uk/bmrs/api/v1"
CHUNK_DAYS = 7
session = requests.Session()


def get_rows(path, params, tries=4):
    params = {**params, "format": "json"}
    for attempt in range(tries):
        try:
            r = session.get(BASE + path, params=params, timeout=60)
            r.raise_for_status()
            d = r.json()
            return d["data"] if isinstance(d, dict) and "data" in d else d
        except requests.RequestException as e:
            if attempt == tries - 1:
                raise
            wait = 2 ** attempt
            print(f"  retrying in {wait}s ({e})")
            time.sleep(wait)


def chunks(start, end):
    d = start
    while d <= end:
        e = min(d + timedelta(days=CHUNK_DAYS - 1), end)
        yield d, e
        d = e + timedelta(days=1)


DATASETS = {
    # name: (path, params builder, columns to keep, de-duplication key)
    "mid": ("/balancing/pricing/market-index",
            lambda s, e: {"from": f"{s}T00:00Z", "to": f"{e + timedelta(days=1)}T00:00Z",
                          "dataProviders": "APXMIDP"},
            ["startTime", "settlementDate", "settlementPeriod", "price", "volume"],
            ["startTime"]),
    "demand": ("/demand/outturn",
               lambda s, e: {"settlementDateFrom": str(s), "settlementDateTo": str(e)},
               ["startTime", "settlementDate", "settlementPeriod",
                "initialDemandOutturn", "initialTransmissionSystemDemandOutturn"],
               ["startTime"]),
    "fuelhh": ("/datasets/FUELHH",
               lambda s, e: {"settlementDateFrom": str(s), "settlementDateTo": str(e)},
               ["startTime", "settlementDate", "settlementPeriod", "fuelType", "generation"],
               ["startTime", "fuelType"]),
}


def fetch(name, start, end, out):
    path, build, cols, key = DATASETS[name]
    frames = []
    for s, e in chunks(start, end):
        rows = get_rows(path, build(s, e)) or []
        print(f"  {name} {s} to {e}: {len(rows)} rows")
        if rows:
            frames.append(pd.DataFrame(rows))
        time.sleep(0.3)
    if not frames:
        print(f"  no data for {name}")
        return
    df = pd.concat(frames, ignore_index=True)
    df = df[[c for c in cols if c in df.columns]]
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df = df.drop_duplicates(key, keep="last").sort_values(key)
    p = out / f"elexon_{name}.csv"
    df.to_csv(p, index=False)

    times = pd.DatetimeIndex(df["startTime"].unique())
    full = pd.date_range(times.min(), times.max(), freq="30min", tz="UTC")
    print(f"Saved {len(df)} rows to {p}  ({times.min()} to {times.max()}, "
          f"{len(full.difference(times))} missing half-hours)\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--only", nargs="+", choices=list(DATASETS), default=list(DATASETS))
    ap.add_argument("--out", default="data/raw")
    a = ap.parse_args()
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=a.days - 1)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"Elexon {start} to {end}\n")
    for name in a.only:
        fetch(name, start, end, out)


if __name__ == "__main__":
    main()
