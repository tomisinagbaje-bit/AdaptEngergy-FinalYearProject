"""Tests for build_dataset.py on small made-up data. Run: python -m pytest SOFTWARE/tests -q"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_dataset as bd  # noqa: E402


def elexon_frame(day, periods):
    midnight = pd.Timestamp(day).tz_localize(bd.LONDON).tz_convert("UTC")
    sp = pd.Series(range(1, periods + 1))
    return pd.DataFrame({"startTime": midnight + bd.SLOT * (sp - 1),
                         "settlementDate": day, "settlementPeriod": sp})


@pytest.fixture
def raw(tmp_path, monkeypatch):
    # 26 Oct 2025 is a clock-change day (50 periods)
    days = [("2025-10-25", 48), ("2025-10-26", 50), ("2025-10-27", 48)]
    base = pd.concat([elexon_frame(d, n) for d, n in days], ignore_index=True)
    n = len(base)

    mid = base.assign(price=50.0, volume=1000.0)
    mid.loc[10, ["price", "volume"]] = 0.0  # no-trade slot
    demand = base.assign(initialDemandOutturn=25000, initialTransmissionSystemDemandOutturn=27000)
    fuel = pd.concat([base.assign(fuelType=f, generation=g) for f, g in
                      [("WIND", 8000), ("CCGT", 6000), ("NUCLEAR", 4000), ("INTFR", 1500)]], ignore_index=True)
    times = base["startTime"]
    agile = pd.DataFrame({"valid_from": times, "valid_to": times + bd.SLOT,
                          "value_exc_vat": 20.0, "value_inc_vat": 21.0, "product": "TEST"})

    for name, df in [("mid", mid), ("demand", demand), ("fuelhh", fuel)]:
        df.to_csv(tmp_path / f"elexon_{name}.csv", index=False)
    agile.to_csv(tmp_path / "octopus_agile_E.csv", index=False)
    monkeypatch.setattr(bd, "RAW", tmp_path)
    return n


def test_clock_change_day_maps_correctly(raw):
    df, report = bd.build("E", max_fill=6)
    mid = next(s for s in report["sources"] if s["source"] == "Elexon mid")
    assert mid["sp_time_mismatches"] == 0
    assert mid["clock_change_days"]["50_periods"] == ["2025-10-26"]
    assert len(df) == raw


def test_no_trade_slot_is_filled_and_flagged(raw):
    df, report = bd.build("E", max_fill=6)
    assert report["columns"]["mid_gbp_mwh"]["filled"] == 1
    assert df["mid_gbp_mwh_filled"].sum() == 1
    assert df["mid_gbp_mwh"].notna().all()


def test_o1_passes_on_clean_data(raw):
    _, report = bd.build("E", max_fill=6)
    assert report["o1"]["pass"] is True


def test_o1_fails_without_agile(raw, monkeypatch):
    (bd.RAW / "octopus_agile_E.csv").unlink()
    _, report = bd.build("E", max_fill=6)
    assert report["o1"]["agile_included"] is False
    assert report["o1"]["pass"] is False


def test_bad_settlement_period_is_caught(raw):
    path = bd.RAW / "elexon_demand.csv"
    df = pd.read_csv(path)
    df.loc[5, "settlementPeriod"] += 1
    df.to_csv(path, index=False)
    _, report = bd.build("E", max_fill=6)
    demand = next(s for s in report["sources"] if s["source"] == "Elexon demand")
    assert demand["sp_time_mismatches"] == 1
