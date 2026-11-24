# AdaptEnergy: an adaptive closed-loop home energy controller

Final year project, EE3EPJ, Aston University (Oluwatomisin Agbaje, supervisor Dr Faisal Shah).

AdaptEnergy schedules household appliances and a home battery around Octopus Agile half-hourly prices. Unlike a timer or a plan made once a day, it re-plans every half hour from what its sensors actually measured. It is evaluated against the hindsight "perfect plan" (a linear programme with perfect knowledge), so the result is the share of the best possible saving it achieves.

- **Controller:** ESP32-S3 (C++ on FreeRTOS) running a dynamic-programming planner every 30-minute slot.
- **Forecaster:** LightGBM, filling the price slots Octopus hasn't published yet.
- **Rig:** three in-house PCBs (power sensing with INA226s, an electronic load that replays real household demand, switching and protection), a 12 V lead-acid battery, LCD and LED price bar. Bench supply only, no mains.
- **Laptop:** Python for data, simulation, the LP benchmark and the forecaster; MQTT, SQLite and a Streamlit dashboard.

## Repository

| Folder | What's in it |
|---|---|
| `SOFTWARE/` | Data download scripts, the data pipeline (`build_dataset.py`) and its tests |
| `data/raw/` | Downloaded data: Elexon MID price, demand and generation by fuel; Octopus Agile prices |
| `reports/` | Test reports, starting with T1 (data quality) |
| `HARDWARE/` | Parts list and the component pack (requirements, VCRM, per-component test tables) |
| `Documentation/` | Logbook, Gantt tracker, plan, proposal deck |

## Getting the data and running T1

```
pip install -r SOFTWARE/requirements.txt
python SOFTWARE/fetch_octopus_agile.py --region E      # Agile prices, West Midlands
python SOFTWARE/fetch_elexon.py                        # Elexon MID, demand, FUELHH
python SOFTWARE/build_dataset.py                       # data/processed/halfhourly.csv + reports/T1_data_quality.md
python -m pytest SOFTWARE/tests -q
```

## Status

| Objective | What | Status |
|---|---|---|
| O1 | Data pipeline (T1) | Elexon data cleaned and aligned; Agile prices to add |
| O2 | Power-sensing PCB (T2) | Datasheet stage |
| O3 | Electronic load (T3) | Datasheet stage |
| O4 | Switching and protection PCB (T4) | Datasheet stage |
| O5 | Price forecaster (T5) | Not started |
| O6 | Adaptive controller on the ESP32 (T6) | Not started |
| O7 | Display and IoT (T7) | Not started |
| O8 | Evaluation (T8) | Not started |
