# T1 data-quality report

Built 2026-11-24 21:12 UTC by SOFTWARE/build_dataset.py. Objective O1: under 1% missing after cleaning, no duplicate slots.

**Result: FAIL.** Worst column 0.0% missing after cleaning; 0 duplicate slots in the output. **Octopus Agile prices not included yet** (file missing), so O1 is not met until they are.

Window (all sources overlap): 2025-10-24 00:00:00+00:00 to 2026-10-23 22:30:00+00:00, 17518 half-hours.

## Raw sources

| Source | First | Last | Expected slots | Duplicates | Missing | Missing % | SP/time mismatches | Clock-change days |
|---|---|---|---|---|---|---|---|---|
| Octopus Agile (E) | not found: data\raw\octopus_agile_E.csv | | | | | | | |
| Elexon mid | 2025-10-24 00:00 | 2026-10-24 00:00 | 17521 | 0 | 0 | 0.0 | 0 | 2026-03-29 (46), 2025-10-26 (50) |
| Elexon demand | 2025-10-23 23:00 | 2026-10-23 22:30 | 17520 | 0 | 0 | 0.0 | 0 | 2026-03-29 (46), 2025-10-26 (50) |
| Elexon fuelhh | 2025-10-23 23:00 | 2026-10-23 22:30 | 17520 | 0 | 0 | 0.0 | 0 | 2026-03-29 (46), 2025-10-26 (50) |

## Columns after cleaning

Gaps up to 6 half-hours filled by straight-line interpolation and flagged in `<column>_filled`.

| Column | Missing before | Filled | Missing after | Missing after % |
|---|---|---|---|---|
| mid_gbp_mwh | 12 | 12 | 0 | 0.0 |
| mid_volume_mwh | 12 | 12 | 0 | 0.0 |
| demand_indo_mw | 0 | 0 | 0 | 0.0 |
| demand_itsdo_mw | 0 | 0 | 0 | 0.0 |
| gen_total_mw | 4 | 4 | 0 | 0.0 |
| gen_wind_mw | 4 | 4 | 0 | 0.0 |
| gen_ccgt_mw | 4 | 4 | 0 | 0.0 |
| gen_nuclear_mw | 4 | 4 | 0 | 0.0 |
| gen_biomass_mw | 4 | 4 | 0 | 0.0 |
| gen_npshyd_mw | 4 | 4 | 0 | 0.0 |
| gen_ps_mw | 4 | 4 | 0 | 0.0 |
| interconnector_net_mw | 0 | 0 | 0 | 0.0 |
| wind_share | 4 | 4 | 0 | 0.0 |

## Notes

- Elexon mid: 12 slots with price 0 and volume 0 (no trades) treated as missing, not as £0.
- MID price £/MWh: min -58.54, mean 99.85, max 560.81; 367 negative slots (kept: they are real).
- Elexon fuelhh: 4 slots report 0 MW for every home fuel at once (2026-02-24 11:30, 2026-07-07 10:00, 2026-07-07 10:30, 2026-10-22 10:00). That's a publishing glitch, so they're treated as missing.
