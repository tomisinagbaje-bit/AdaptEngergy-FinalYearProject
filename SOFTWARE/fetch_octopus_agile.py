"""Download a year of Octopus Agile half-hourly import prices.

Usage:
    python scripts/fetch_octopus_agile.py                  # last 365 days, region E
    python scripts/fetch_octopus_agile.py --region C --days 400
    python scripts/fetch_octopus_agile.py --start 2025-10-01 --end 2026-10-24

Output: data/raw/octopus_agile_<region>.csv  (one row per half-hour, UTC, ascending)
No API key needed: tariff prices are public.
"""
import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://api.octopus.energy/v1"
# Older Agile versions. Their rates fill in any months the current product doesn't cover.
KNOWN_PRODUCTS = ["AGILE-24-10-01", "AGILE-24-04-03", "AGILE-23-12-06", "AGILE-FLEX-22-11-25"]
REGIONS = "ABCDEFGHJKLMNP"  # E = West Midlands (Birmingham), C = London

session = requests.Session()


def get_json(url, params=None, tries=4):
    for attempt in range(tries):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if attempt == tries - 1:
                raise
            wait = 2 ** attempt
            print(f"  retrying in {wait}s ({e})")
            time.sleep(wait)


def current_agile_products():
    """Agile import products Octopus lists right now (newest first)."""
    url, params, found = f"{BASE}/products/", {"brand": "OCTOPUS_ENERGY", "page_size": 100}, []
    while url:
        d = get_json(url, params)
        if not d:
            break
        for p in d["results"]:
            code = p["code"]
            if "AGILE" in code and "OUTGOING" not in code:
                found.append((p.get("available_from") or "", code))
        url, params = d.get("next"), None
    return [c for _, c in sorted(found, reverse=True)]


def fetch_rates(product, region, start, end):
    tariff = f"E-1R-{product}-{region}"
    url = f"{BASE}/products/{product}/electricity-tariffs/{tariff}/standard-unit-rates/"
    params = {"period_from": start.strftime("%Y-%m-%dT%H:%MZ"),
              "period_to": end.strftime("%Y-%m-%dT%H:%MZ"),
              "page_size": 1500}
    rows = []
    while url:
        d = get_json(url, params)
        if not d:
            break
        rows.extend(d["results"])
        url, params = d.get("next"), None
        time.sleep(0.2)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "payment_method" in df:
        df = df[df["payment_method"] != "NON_DIRECT_DEBIT"]
    df["product"] = product
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="E", help="DNO region letter (E = West Midlands)")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--start", help="YYYY-MM-DD (overrides --days)")
    ap.add_argument("--end", help="YYYY-MM-DD (default: tomorrow, to catch published rates)")
    ap.add_argument("--product", help="force one product code, e.g. AGILE-24-10-01")
    ap.add_argument("--out", default="data/raw")
    a = ap.parse_args()

    region = a.region.upper()
    if region not in REGIONS:
        sys.exit(f"Region must be one of {REGIONS}")
    end = (datetime.fromisoformat(a.end) if a.end
           else datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=2))
    end = end.replace(tzinfo=timezone.utc)
    start = (datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc) if a.start
             else end - timedelta(days=a.days + 2))

    products = [a.product] if a.product else list(dict.fromkeys(current_agile_products() + KNOWN_PRODUCTS))
    print(f"Region {region}, {start:%Y-%m-%d} to {end:%Y-%m-%d}")
    frames = []
    for p in products:
        print(f"Fetching {p} ...")
        df = fetch_rates(p, region, start, end)
        print(f"  {len(df)} rows")
        if len(df):
            frames.append(df)
    if not frames:
        sys.exit("No rates returned. Check the region letter and product codes.")

    # Earlier entries in `products` are newer versions, so they win on overlap.
    df = pd.concat(frames, ignore_index=True)
    df["valid_from"] = pd.to_datetime(df["valid_from"], utc=True)
    df["valid_to"] = pd.to_datetime(df["valid_to"], utc=True)
    df = df.drop_duplicates("valid_from", keep="first").sort_values("valid_from")
    df = df[(df["valid_from"] >= start) & (df["valid_from"] < end)]
    df = df[["valid_from", "valid_to", "value_exc_vat", "value_inc_vat", "product"]]

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"octopus_agile_{region}.csv"
    df.to_csv(path, index=False)

    # Quick coverage check (first step of T1)
    full = pd.date_range(df["valid_from"].min(), df["valid_from"].max(), freq="30min", tz="UTC")
    missing = full.difference(pd.DatetimeIndex(df["valid_from"]))
    print(f"\nSaved {len(df)} half-hours to {path}")
    print(f"Range: {df['valid_from'].min()} to {df['valid_from'].max()}")
    print(f"Missing half-hours inside that range: {len(missing)}")
    if len(missing):
        print("  first few:", [str(m) for m in missing[:5]])
    print(f"Price p/kWh inc VAT: min {df['value_inc_vat'].min():.2f}, "
          f"mean {df['value_inc_vat'].mean():.2f}, max {df['value_inc_vat'].max():.2f}")
    print("Products used:", df["product"].value_counts().to_dict())


if __name__ == "__main__":
    main()
