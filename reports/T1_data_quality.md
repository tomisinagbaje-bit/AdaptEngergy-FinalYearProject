# T1 data-quality report

Built 2026-11-24 21:38 UTC by SOFTWARE/build_dataset.py. O1: under 1% missing after cleaning, no duplicate slots.

**Result: PASS.** Worst column 0.0% missing after cleaning; 0 duplicate slots in the output.

Window: 2025-11-24 00:00:00+00:00 to 2026-11-23 23:30:00+00:00, 17520 half-hours.

## Raw sources

| Source | First | Last | Expected slots | Duplicates | Missing | Missing % | SP/time mismatches | Clock-change days |
|---|---|---|---|---|---|---|---|---|
| Octopus Agile (E) | 2025-11-24 00:00 | 2026-11-25 22:30 | 17614 | 0 | 0 | 0.0 | - | - |
| Elexon mid | 2025-11-24 00:00 | 2026-11-24 00:00 | 17521 | 0 | 0 | 0.0 | 0 | 2026-03-29 (46), 2026-10-25 (50) |
| Elexon demand | 2025-11-24 00:00 | 2026-11-23 23:30 | 17520 | 0 | 0 | 0.0 | 0 | 2026-03-29 (46), 2026-10-25 (50) |
| Elexon fuelhh | 2025-11-24 00:00 | 2026-11-23 23:30 | 17520 | 0 | 0 | 0.0 | 0 | 2026-03-29 (46), 2026-10-25 (50) |

## Columns after cleaning

Gaps up to 6 half-hours filled by linear interpolation, flagged in `<column>_filled`.

| Column | Missing before | Filled | Missing after | Missing after % |
|---|---|---|---|---|
| agile_p_kwh_inc_vat | 0 | 0 | 0 | 0.0 |
| agile_p_kwh_exc_vat | 0 | 0 | 0 | 0.0 |
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
| wind_share | 4 | 4 | 0 | 0.0 |
| interconnector_net_mw | 0 | 0 | 0 | 0.0 |

## Notes

- Agile p/kWh inc VAT: min -11.67, mean 23.47, max 94.76; 492 negative slots. Slots not 30 min long: 0.
- Agile: 2688 slots from 2026-09-30 23:00 UTC have inc VAT = exc VAT. That's the government cut of VAT on household electricity to 0% from 1 Oct 2026, not an error. The controller uses the inc-VAT price (what the household pays).
- Elexon mid: 12 slots with price 0 and volume 0 (no trades) treated as missing, not £0.
- MID £/MWh: min -58.54, mean 110.11, max 560.81; 350 negative slots (real, kept).
- Elexon fuelhh: 4 slots with every home fuel at 0 MW (2026-02-24 11:30, 2026-07-07 10:00, 2026-07-07 10:30, 2026-10-22 10:00): publishing glitch, treated as missing.
