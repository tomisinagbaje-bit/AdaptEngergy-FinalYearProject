"""Clean and align the raw data into one half-hourly table, and write the T1 report (O1).

Run from the repo root:  python SOFTWARE/build_dataset.py [--region E] [--max-fill 6]
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

RAW, OUT, REPORTS = Path("data/raw"), Path("data/processed"), Path("reports")
LONDON = "Europe/London"
SLOT = pd.Timedelta(minutes=30)
FUELS = ["WIND", "CCGT", "NUCLEAR", "BIOMASS", "NPSHYD", "PS"]


def slot_stats(times, name):
    t = pd.DatetimeIndex(times)
    u = t.unique()
    full = pd.date_range(u.min(), u.max(), freq="30min", tz="UTC")
    missing = full.difference(u)
    return {"source": name, "first": str(u.min()), "last": str(u.max()),
            "expected_slots": len(full), "rows": len(t),
            "duplicate_slots": int(t.duplicated().sum()),
            "missing_slots": len(missing),
            "missing_pct": round(100 * len(missing) / len(full), 3),
            "off_grid_times": int(((u.minute % 30 != 0) | (u.second != 0)).sum()),
            "first_missing": [str(m) for m in missing[:5]]}


def describe(s):
    return {"min": round(s.min(), 2), "mean": round(s.mean(), 2),
            "max": round(s.max(), 2), "negative_slots": int((s < 0).sum())}


def sp_check(df):
    # SP 1 starts at local midnight, so the UTC start time must match. Catches clock-change errors.
    midnight = pd.to_datetime(df["settlementDate"]).dt.tz_localize(LONDON).dt.tz_convert("UTC")
    bad = int((midnight + SLOT * (df["settlementPeriod"] - 1) != df["startTime"]).sum())
    per_day = df.groupby("settlementDate")["settlementPeriod"].max()
    return bad, {"46_periods": sorted(per_day.index[per_day == 46]),
                 "50_periods": sorted(per_day.index[per_day == 50])}


def load_agile(region):
    path = RAW / f"octopus_agile_{region}.csv"
    name = f"Octopus Agile ({region})"
    if not path.exists():
        return None, {"source": name, "status": f"not found: {path}"}
    df = pd.read_csv(path, usecols=["valid_from", "valid_to", "value_exc_vat", "value_inc_vat"],
                     parse_dates=["valid_from", "valid_to"])
    st = slot_stats(df["valid_from"], name)
    st["not_30_min"] = int((df["valid_to"] - df["valid_from"] != SLOT).sum())
    st["price_inc_vat_p_kwh"] = describe(df["value_inc_vat"])
    # VAT on household electricity is 0% from 1 Oct 2026, so inc = exc after that.
    no_vat = (df["value_exc_vat"] != 0) & ((df["value_inc_vat"] - df["value_exc_vat"]).abs() < 1e-6)
    st["zero_vat_slots"] = int(no_vat.sum())
    st["zero_vat_from"] = str(df.loc[no_vat, "valid_from"].min()) if no_vat.any() else None
    df = (df.drop_duplicates("valid_from").set_index("valid_from")
            .rename(columns={"value_inc_vat": "agile_p_kwh_inc_vat", "value_exc_vat": "agile_p_kwh_exc_vat"}))
    return df[["agile_p_kwh_inc_vat", "agile_p_kwh_exc_vat"]], st


def load_elexon(name, cols, dtype=None):
    df = pd.read_csv(RAW / f"elexon_{name}.csv",
                     usecols=["startTime", "settlementDate", "settlementPeriod", *cols],
                     parse_dates=["startTime"], dtype=dtype)
    key = ["startTime", "fuelType"] if name == "fuelhh" else ["startTime"]
    st = slot_stats(df["startTime"], f"Elexon {name}")
    st["duplicate_slots"] = int(df.duplicated(key).sum())
    st["sp_time_mismatches"], st["clock_change_days"] = sp_check(df)
    return df, st


def build(region, max_fill):
    rep = {"built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "max_fill_slots": max_fill, "sources": [], "columns": {}}
    parts = []

    agile, st = load_agile(region)
    rep["sources"].append(st)
    if agile is not None:
        parts.append(agile)

    mid, st = load_elexon("mid", ["price", "volume"])
    no_trade = (mid["price"] == 0) & (mid["volume"] == 0)  # no trades, not a real £0
    mid.loc[no_trade, ["price", "volume"]] = float("nan")
    st["no_trade_slots_set_missing"] = int(no_trade.sum())
    st["price_gbp_mwh"] = describe(mid["price"].dropna())
    rep["sources"].append(st)
    parts.append(mid.set_index("startTime")[["price", "volume"]]
                    .set_axis(["mid_gbp_mwh", "mid_volume_mwh"], axis=1))

    dem, st = load_elexon("demand", ["initialDemandOutturn", "initialTransmissionSystemDemandOutturn"])
    rep["sources"].append(st)
    parts.append(dem.set_index("startTime").iloc[:, 2:].set_axis(["demand_indo_mw", "demand_itsdo_mw"], axis=1))

    fuel, st = load_elexon("fuelhh", ["fuelType", "generation"], dtype={"fuelType": "category"})
    wide = fuel.pivot(index="startTime", columns="fuelType", values="generation")
    inter = wide.columns.str.startswith("INT")
    gen = pd.DataFrame({"gen_total_mw": wide.loc[:, ~inter].sum(axis=1, min_count=1)})
    for f in FUELS:
        if f in wide:
            gen[f"gen_{f.lower()}_mw"] = wide[f]
    gen["wind_share"] = gen["gen_wind_mw"] / gen["gen_total_mw"]
    glitch = gen["gen_total_mw"] == 0  # every home fuel at 0 MW at once = publishing glitch
    gen[glitch] = float("nan")
    gen["interconnector_net_mw"] = wide.loc[:, inter].sum(axis=1, min_count=1)
    st["all_zero_generation_slots_set_missing"] = int(glitch.sum())
    st["all_zero_generation_first"] = [str(t) for t in gen.index[glitch][:5]]
    rep["sources"].append(st)
    parts.append(gen)

    # Common window, one UTC half-hour index.
    start, end = max(p.index.min() for p in parts), min(p.index.max() for p in parts)
    idx = pd.date_range(start, end, freq="30min", tz="UTC", name="start_utc")
    df = pd.concat([p.reindex(idx) for p in parts], axis=1)
    rep["window"] = {"start_utc": str(start), "end_utc": str(end), "slots": len(idx)}

    # Fill gaps up to max_fill slots, flag what was filled.
    before = df.isna()
    df = df.interpolate(method="time", limit=max_fill, limit_area="inside")
    filled = before & df.notna()
    after = df.isna()
    for c in df.columns:
        rep["columns"][c] = {"missing_before": int(before[c].sum()), "filled": int(filled[c].sum()),
                             "missing_after": int(after[c].sum()),
                             "missing_after_pct": round(100 * after[c].mean(), 3)}
    flags = filled.loc[:, filled.any()].add_suffix("_filled")

    local = idx.tz_convert(LONDON)
    feats = pd.DataFrame({"local_time": local.strftime("%Y-%m-%d %H:%M"),
                          "day_of_week": local.dayofweek,  # 0 = Monday
                          "is_weekend": local.dayofweek >= 5,
                          "slot_of_day": local.hour * 2 + local.minute // 30,
                          "is_peak_16_19": (local.hour >= 16) & (local.hour < 19)}, index=idx)
    df = pd.concat([feats, df, flags], axis=1)

    worst = max(v["missing_after_pct"] for v in rep["columns"].values())
    dup_out = int(df.index.duplicated().sum())
    rep["o1"] = {"worst_missing_after_pct": worst,
                 "duplicate_slots_in_sources": sum(s.get("duplicate_slots", 0) for s in rep["sources"]),
                 "duplicate_slots_in_output": dup_out, "agile_included": agile is not None,
                 "pass": agile is not None and worst < 1 and dup_out == 0}
    return df, rep


def write_md(rep, path):
    o1, w = rep["o1"], rep["window"]
    L = ["# T1 data-quality report", "",
         f"Built {rep['built']} by SOFTWARE/build_dataset.py. O1: under 1% missing after cleaning, no duplicate slots.", "",
         f"**Result: {'PASS' if o1['pass'] else 'FAIL'}.** Worst column {o1['worst_missing_after_pct']}% missing after cleaning; "
         f"{o1['duplicate_slots_in_output']} duplicate slots in the output."
         + ("" if o1["agile_included"] else " **Agile prices not included yet**, so O1 isn't met."), "",
         f"Window: {w['start_utc']} to {w['end_utc']}, {w['slots']} half-hours.", "",
         "## Raw sources", "",
         "| Source | First | Last | Expected slots | Duplicates | Missing | Missing % | SP/time mismatches | Clock-change days |",
         "|---|---|---|---|---|---|---|---|---|"]
    for s in rep["sources"]:
        if "status" in s:
            L.append(f"| {s['source']} | {s['status']} |" + " |" * 7)
            continue
        cc = s.get("clock_change_days", {})
        ccs = ", ".join([f"{d} (46)" for d in cc.get("46_periods", [])] + [f"{d} (50)" for d in cc.get("50_periods", [])])
        L.append(f"| {s['source']} | {s['first'][:16]} | {s['last'][:16]} | {s['expected_slots']} | {s['duplicate_slots']} | "
                 f"{s['missing_slots']} | {s['missing_pct']} | {s.get('sp_time_mismatches', '-')} | {ccs or '-'} |")
    L += ["", "## Columns after cleaning", "",
          f"Gaps up to {rep['max_fill_slots']} half-hours filled by linear interpolation, flagged in `<column>_filled`.", "",
          "| Column | Missing before | Filled | Missing after | Missing after % |", "|---|---|---|---|---|"]
    L += [f"| {c} | {v['missing_before']} | {v['filled']} | {v['missing_after']} | {v['missing_after_pct']} |"
          for c, v in rep["columns"].items()]
    L += ["", "## Notes", ""]
    for s in rep["sources"]:
        if s.get("no_trade_slots_set_missing"):
            L.append(f"- {s['source']}: {s['no_trade_slots_set_missing']} slots with price 0 and volume 0 (no trades) treated as missing, not £0.")
        if s.get("all_zero_generation_slots_set_missing"):
            L.append(f"- {s['source']}: {s['all_zero_generation_slots_set_missing']} slots with every home fuel at 0 MW "
                     f"({', '.join(t[:16] for t in s['all_zero_generation_first'])}): publishing glitch, treated as missing.")
        if "price_gbp_mwh" in s:
            p = s["price_gbp_mwh"]
            L.append(f"- MID £/MWh: min {p['min']}, mean {p['mean']}, max {p['max']}; {p['negative_slots']} negative slots (real, kept).")
        if "price_inc_vat_p_kwh" in s:
            p = s["price_inc_vat_p_kwh"]
            L.append(f"- Agile p/kWh inc VAT: min {p['min']}, mean {p['mean']}, max {p['max']}; {p['negative_slots']} negative slots. "
                     f"Slots not 30 min long: {s['not_30_min']}.")
            if s.get("zero_vat_slots"):
                L.append(f"- Agile: {s['zero_vat_slots']} slots from {s['zero_vat_from'][:16]} UTC have inc VAT = exc VAT. "
                         "That's the government cut of VAT on household electricity to 0% from 1 Oct 2026, not an error. "
                         "The controller uses the inc-VAT price (what the household pays).")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="E")
    ap.add_argument("--max-fill", type=int, default=6, help="longest gap to fill, in half-hours")
    a = ap.parse_args()

    df, rep = build(a.region.upper(), a.max_fill)
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "halfhourly.csv")
    (REPORTS / "T1_data_quality.json").write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
    write_md(rep, REPORTS / "T1_data_quality.md")

    o1 = rep["o1"]
    print(f"{len(df)} half-hours x {df.shape[1]} columns -> {OUT / 'halfhourly.csv'}")
    print(f"O1 {'PASS' if o1['pass'] else 'FAIL'}: worst column {o1['worst_missing_after_pct']}% missing, "
          f"{o1['duplicate_slots_in_output']} duplicate slots" + ("" if o1["agile_included"] else ", Agile file missing"))


if __name__ == "__main__":
    main()
