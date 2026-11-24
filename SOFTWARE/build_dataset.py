"""Build the cleaned, aligned half-hourly dataset and the T1 data-quality report (objective O1).

What it does
    1. Loads each raw file in data/raw (Octopus Agile if it's there, Elexon MID, demand and FUELHH).
    2. Checks each one: duplicate slots, missing slots, slot length, and that Elexon's settlement
       date + period really maps to the UTC start time it gives (this is where clock changes go wrong).
    3. Puts everything on one UTC half-hour index, cleans it (see CLEANING below) and adds time features.
    4. Saves data/processed/halfhourly.csv and writes reports/T1_data_quality.md + .json.

O1 pass mark: under 1% missing after cleaning, and no duplicate slots.

Usage (run from the repo root):
    python SOFTWARE/build_dataset.py
    python SOFTWARE/build_dataset.py --region E --max-fill 6

CLEANING
    - Elexon MID rows with price 0 AND volume 0 are "no trades in that slot", not a real £0 price,
      so they become missing.
    - Gaps of up to --max-fill half-hours (default 6 = 3 hours) are filled by straight-line
      interpolation and flagged in <column>_filled. Longer gaps stay missing.
    - Elexon FUELHH slots where every home fuel reads 0 MW at once are a publishing glitch and
      become missing.
    - Negative prices are real (wind-heavy nights) and are kept.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

RAW = Path("data/raw")
OUT = Path("data/processed")
REPORTS = Path("reports")
LONDON = "Europe/London"
SLOT = pd.Timedelta(minutes=30)


# ---------------------------------------------------------------- checks

def slot_stats(times, name):
    """Range, expected slots, missing and duplicate counts for one series of UTC start times."""
    times = pd.DatetimeIndex(times)
    unique = times.unique()
    full = pd.date_range(unique.min(), unique.max(), freq="30min", tz="UTC")
    missing = full.difference(unique)
    off_grid = int(((unique.minute % 30) != 0).sum() + (unique.second != 0).sum())
    return {
        "source": name,
        "first": str(unique.min()),
        "last": str(unique.max()),
        "expected_slots": len(full),
        "rows": len(times),
        "duplicate_slots": int(times.duplicated().sum()),
        "missing_slots": len(missing),
        "missing_pct": round(100 * len(missing) / len(full), 3),
        "off_grid_times": off_grid,
        "first_missing": [str(m) for m in missing[:5]],
    }


def settlement_period_check(df):
    """Elexon gives settlementDate, settlementPeriod and startTime. SP 1 starts at local midnight,
    so startTime should equal local midnight + 30 min x (SP - 1), converted to UTC.
    Returns the number of rows that disagree, and the clock-change days found (46 or 50 periods)."""
    midnight = (pd.to_datetime(df["settlementDate"]).dt.tz_localize(LONDON).dt.tz_convert("UTC"))
    expected = midnight + SLOT * (df["settlementPeriod"] - 1)
    bad = int((expected != df["startTime"]).sum())
    per_day = df.groupby("settlementDate")["settlementPeriod"].max()
    short = sorted(per_day[per_day == 46].index.tolist())
    long_ = sorted(per_day[per_day == 50].index.tolist())
    return bad, short, long_


# ---------------------------------------------------------------- loaders

def load_agile(region):
    path = RAW / f"octopus_agile_{region}.csv"
    if not path.exists():
        return None, {"source": f"Octopus Agile ({region})", "status": f"not found: {path}"}
    df = pd.read_csv(path)
    df["valid_from"] = pd.to_datetime(df["valid_from"], utc=True)
    df["valid_to"] = pd.to_datetime(df["valid_to"], utc=True)
    stats = slot_stats(df["valid_from"], f"Octopus Agile ({region})")
    stats["not_30_min"] = int(((df["valid_to"] - df["valid_from"]) != SLOT).sum())
    stats["price_inc_vat_p_kwh"] = describe(df["value_inc_vat"])
    out = (df.drop_duplicates("valid_from").set_index("valid_from")
             [["value_inc_vat", "value_exc_vat"]]
             .rename(columns={"value_inc_vat": "agile_p_kwh_inc_vat",
                              "value_exc_vat": "agile_p_kwh_exc_vat"}))
    return out, stats


def load_elexon(name):
    df = pd.read_csv(RAW / f"elexon_{name}.csv")
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    key = ["startTime", "fuelType"] if name == "fuelhh" else ["startTime"]
    stats = slot_stats(df["startTime"], f"Elexon {name}")
    stats["duplicate_slots"] = int(df.duplicated(key).sum())
    bad, short, long_ = settlement_period_check(df)
    stats["sp_time_mismatches"] = bad
    stats["clock_change_days"] = {"46_periods": short, "50_periods": long_}
    return df, stats


def describe(s):
    return {"min": round(float(s.min()), 2), "mean": round(float(s.mean()), 2),
            "max": round(float(s.max()), 2), "negative_slots": int((s < 0).sum())}


# ---------------------------------------------------------------- build

def build(region, max_fill):
    report = {"built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
              "max_fill_slots": max_fill, "sources": [], "columns": {}}
    parts = []

    agile, st = load_agile(region)
    report["sources"].append(st)
    if agile is not None:
        parts.append(agile)

    mid, st = load_elexon("mid")
    no_trade = (mid["price"] == 0) & (mid["volume"] == 0)
    st["no_trade_slots_set_missing"] = int(no_trade.sum())
    mid.loc[no_trade, ["price", "volume"]] = float("nan")
    st["price_gbp_mwh"] = describe(mid["price"].dropna())
    report["sources"].append(st)
    parts.append(mid.set_index("startTime")[["price", "volume"]]
                    .rename(columns={"price": "mid_gbp_mwh", "volume": "mid_volume_mwh"}))

    dem, st = load_elexon("demand")
    report["sources"].append(st)
    parts.append(dem.set_index("startTime")[["initialDemandOutturn", "initialTransmissionSystemDemandOutturn"]]
                    .rename(columns={"initialDemandOutturn": "demand_indo_mw",
                                     "initialTransmissionSystemDemandOutturn": "demand_itsdo_mw"}))

    fuel, st = load_elexon("fuelhh")
    report["sources"].append(st)
    wide = fuel.pivot_table(index="startTime", columns="fuelType", values="generation", aggfunc="first")
    inter = [c for c in wide.columns if c.startswith("INT")]
    home = [c for c in wide.columns if c not in inter]
    gen = pd.DataFrame(index=wide.index)
    gen["gen_total_mw"] = wide[home].sum(axis=1, min_count=1)
    for c in ["WIND", "CCGT", "NUCLEAR", "BIOMASS", "NPSHYD", "PS"]:
        if c in wide:
            gen[f"gen_{c.lower()}_mw"] = wide[c]
    gen["interconnector_net_mw"] = wide[inter].sum(axis=1, min_count=1)
    # A few slots report 0 MW for every home fuel at once (a publishing glitch, not a blackout).
    glitch = gen["gen_total_mw"] == 0
    gen.loc[glitch, [c for c in gen.columns if c != "interconnector_net_mw"]] = float("nan")
    st["all_zero_generation_slots_set_missing"] = int(glitch.sum())
    st["all_zero_generation_first"] = [str(t) for t in gen.index[glitch][:5]]
    gen["wind_share"] = gen["gen_wind_mw"] / gen["gen_total_mw"]
    parts.append(gen)

    # One UTC half-hour index over the window every source covers.
    start = max(p.index.min() for p in parts)
    end = min(p.index.max() for p in parts)
    index = pd.date_range(start, end, freq="30min", tz="UTC", name="start_utc")
    df = pd.concat([p.reindex(index) for p in parts], axis=1)
    report["window"] = {"start_utc": str(start), "end_utc": str(end), "slots": len(index)}

    # Fill short gaps, flag them, and count what's left.
    for col in df.columns:
        before = df[col].isna()
        df[col] = df[col].interpolate(method="time", limit=max_fill, limit_area="inside")
        filled = before & df[col].notna()
        if filled.any():
            df[f"{col}_filled"] = filled
        report["columns"][col] = {"missing_before": int(before.sum()), "filled": int(filled.sum()),
                                  "missing_after": int(df[col].isna().sum()),
                                  "missing_after_pct": round(100 * df[col].isna().mean(), 3)}

    # Time features in UK local time (what a household and Agile's 16:00-19:00 peak follow).
    local = index.tz_convert(LONDON)
    df.insert(0, "local_time", local.strftime("%Y-%m-%d %H:%M"))
    df.insert(1, "day_of_week", local.dayofweek)          # 0 = Monday
    df.insert(2, "is_weekend", local.dayofweek >= 5)
    df.insert(3, "slot_of_day", local.hour * 2 + local.minute // 30)  # 0..47 local
    df.insert(4, "is_peak_16_19", (local.hour >= 16) & (local.hour < 19))

    # Verdict against O1.
    value_cols = [c for c in report["columns"]]
    worst = max(report["columns"][c]["missing_after_pct"] for c in value_cols)
    dups = sum(s.get("duplicate_slots", 0) for s in report["sources"])
    report["o1"] = {"worst_missing_after_pct": worst, "duplicate_slots_in_sources": dups,
                    "duplicate_slots_in_output": int(df.index.duplicated().sum()),
                    "agile_included": agile is not None,
                    "pass": bool(agile is not None and worst < 1 and df.index.duplicated().sum() == 0)}
    return df, report


# ---------------------------------------------------------------- report

def write_report(report, path_md):
    o1 = report["o1"]
    L = [f"# T1 data-quality report",
         "",
         f"Built {report['built']} by SOFTWARE/build_dataset.py. Objective O1: under 1% missing after cleaning, no duplicate slots.",
         "",
         f"**Result: {'PASS' if o1['pass'] else 'FAIL'}.** Worst column {o1['worst_missing_after_pct']}% missing after cleaning; "
         f"{o1['duplicate_slots_in_output']} duplicate slots in the output."
         + ("" if o1["agile_included"] else " **Octopus Agile prices not included yet** (file missing), so O1 is not met until they are."),
         "",
         f"Window (all sources overlap): {report['window']['start_utc']} to {report['window']['end_utc']}, {report['window']['slots']} half-hours.",
         "",
         "## Raw sources",
         "",
         "| Source | First | Last | Expected slots | Duplicates | Missing | Missing % | SP/time mismatches | Clock-change days |",
         "|---|---|---|---|---|---|---|---|---|"]
    for s in report["sources"]:
        if "status" in s:
            L.append(f"| {s['source']} | {s['status']} | | | | | | | |")
            continue
        cc = s.get("clock_change_days", {})
        ccs = ", ".join([f"{d} (46)" for d in cc.get("46_periods", [])] + [f"{d} (50)" for d in cc.get("50_periods", [])])
        L.append(f"| {s['source']} | {s['first'][:16]} | {s['last'][:16]} | {s['expected_slots']} | {s['duplicate_slots']} | "
                 f"{s['missing_slots']} | {s['missing_pct']} | {s.get('sp_time_mismatches', '-')} | {ccs or '-'} |")
    L += ["", "## Columns after cleaning", "",
          f"Gaps up to {report['max_fill_slots']} half-hours filled by straight-line interpolation and flagged in `<column>_filled`.",
          "", "| Column | Missing before | Filled | Missing after | Missing after % |", "|---|---|---|---|---|"]
    for c, v in report["columns"].items():
        L.append(f"| {c} | {v['missing_before']} | {v['filled']} | {v['missing_after']} | {v['missing_after_pct']} |")
    L += ["", "## Notes", ""]
    for s in report["sources"]:
        if s.get("no_trade_slots_set_missing"):
            L.append(f"- {s['source']}: {s['no_trade_slots_set_missing']} slots with price 0 and volume 0 (no trades) treated as missing, not as £0.")
        if s.get("all_zero_generation_slots_set_missing"):
            L.append(f"- {s['source']}: {s['all_zero_generation_slots_set_missing']} slots report 0 MW for every home fuel at once "
                     f"({', '.join(t[:16] for t in s['all_zero_generation_first'])}). That's a publishing glitch, so they're treated as missing.")
        if "price_gbp_mwh" in s:
            p = s["price_gbp_mwh"]
            L.append(f"- MID price £/MWh: min {p['min']}, mean {p['mean']}, max {p['max']}; {p['negative_slots']} negative slots (kept: they are real).")
        if "price_inc_vat_p_kwh" in s:
            p = s["price_inc_vat_p_kwh"]
            L.append(f"- Agile p/kWh inc VAT: min {p['min']}, mean {p['mean']}, max {p['max']}; {p['negative_slots']} negative slots.")
            L.append(f"- Agile slots not exactly 30 minutes long: {s['not_30_min']}.")
    path_md.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="E", help="Agile region letter (E = West Midlands)")
    ap.add_argument("--max-fill", type=int, default=6, help="longest gap to interpolate, in half-hours")
    a = ap.parse_args()

    df, report = build(a.region.upper(), a.max_fill)
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "halfhourly.csv")
    (REPORTS / "T1_data_quality.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_report(report, REPORTS / "T1_data_quality.md")

    o1 = report["o1"]
    print(f"Saved {len(df)} half-hours x {df.shape[1]} columns to {OUT / 'halfhourly.csv'}")
    print(f"O1: {'PASS' if o1['pass'] else 'FAIL'} (worst column {o1['worst_missing_after_pct']}% missing, "
          f"{o1['duplicate_slots_in_output']} duplicate slots)")
    if not o1["agile_included"]:
        print("Octopus Agile file not found: run SOFTWARE/fetch_octopus_agile.py first.")
    print(f"Report: {REPORTS / 'T1_data_quality.md'}")


if __name__ == "__main__":
    main()
