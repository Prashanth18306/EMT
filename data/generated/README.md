# Phase 0 — Synthetic Dataset README
## Stellantis Virtual EMT Predictive Validation System

---

## Dataset Summary

| Item | Value |
|---|---|
| **Total Trials Generated** | 300 |
| **OK Trials** | 232 (77%) |
| **NG Trials** | 68 (23%) |
| **Oven Types** | ED, SEALER, TOPCOAT |
| **Trials per oven** | 100 (70 OK + 30 NG attempted) |
| **Sensors per trial** | 12 (full BIW coverage) |
| **Sampling rate** | 1 second |
| **Time-series files** | 300 individual CSVs |
| **Generated date** | September 2026 |

---

## Standards Basis

| Standard | How Applied |
|---|---|
| **ISO 12944** | Corrosion protection cure requirements |
| **VDA 621-415** | German OEM paint temperature specs |
| **Ford FLTM BI 106-01** | Oven profiling methodology |
| **BYK Gardner temp-gard V2.3** | Output format, sensor names, critical values |
| **Arrhenius cure kinetics** | Cure index calculation formula |
| **Industry TDS data** | Temperature setpoints (PPG, BASF, Axalta) |

---

## File Structure

```
generated/
├── ALL_OVENS_metadata.csv          ← Combined metadata for all 300 trials
│
├── ED/
│   ├── ED_metadata.csv             ← ED oven: 100 trial summaries + labels
│   └── timeseries/
│       ├── ED-0001.csv             ← 2400 rows × 14 columns (time + 12 sensors)
│       ├── ED-0002.csv
│       └── ... (100 files)
│
├── SEALER/
│   ├── SEALER_metadata.csv         ← Sealer oven: 100 trial summaries
│   └── timeseries/
│       └── ... (100 files)
│
├── TOPCOAT/
│   ├── TOPCOAT_metadata.csv        ← Topcoat oven: 100 trial summaries
│   └── timeseries/
│       └── ... (100 files)
│
└── standard_curves/
    ├── ED_standard_curve.csv       ← Golden reference curve + upper/lower limits
    ├── ED_spec.json                ← ED oven specifications
    ├── SEALER_standard_curve.csv
    ├── SEALER_spec.json
    ├── TOPCOAT_standard_curve.csv
    └── TOPCOAT_spec.json
```

---

## Column Reference

### metadata.csv columns
| Column | Description |
|---|---|
| `trial_id` | Unique trial identifier (e.g., ED-0001) |
| `oven_type` | ED / SEALER / TOPCOAT |
| `vehicle_model` | CC21/CC31/CC41/CC51/CC61 |
| `date` | Trial date (YYYY-MM-DD) |
| `time` | Trial start time |
| `operator` | Simulated operator name |
| `result_actual` | **OK** or **NG** — ground truth label |
| `ng_mode` | Failure mode code (if NG) |
| `ng_root_cause` | Human-readable root cause |
| `plc_zone1..5_setpoint_C` | Zone temperature setpoints (°C) |
| `plc_fan_speed_pct` | Oven fan speed (%) |
| `plc_conveyor_speed_m_min` | Conveyor speed (m/min) |
| `plc_gas_pressure_mbar` | Gas supply pressure (mbar) |
| `plc_damper_pos_pct` | Air damper position (%) |
| `plc_burner_state` | Burner ON=1 / OFF=0 |
| `plc_loading_vehicles` | Number of vehicles in oven |
| `{SENSOR}_peak_C` | Peak temperature per sensor (°C) |
| `{SENSOR}_ci` | Cure index (Arrhenius equivalent-minutes) |
| `{SENSOR}_t_cure_min` | Minutes above cure threshold |

### timeseries/*.csv columns
| Column | Description |
|---|---|
| `trial_id` | Links back to metadata |
| `time_s` | Elapsed seconds (0 to total_time) |
| `time_mmss` | Human-readable mm:ss |
| `T_LH_HOOD` ... `T_RH_HOOD` | Temperature reading per sensor (°C) |

---

## Oven Specifications Used

### ED Oven (Electrodeposition)
- Target peak: **185–205°C** | Cure threshold: **165°C**
- Cure time minimum: **12 min** above 165°C
- Cycle time: **40 minutes** (2400 seconds)
- 5 zones: 140 / 175 / 190 / 190 / 180°C (setpoints)

### Sealer Oven
- Target peak: **150–170°C** | Cure threshold: **130°C**
- Cure time minimum: **12 min** above 130°C
- Cycle time: **30 minutes** (1800 seconds)
- 5 zones: 120 / 150 / 165 / 165 / 150°C (setpoints)

### Topcoat Oven
- Target peak: **130–150°C** | Cure threshold: **120°C**
- Cure time minimum: **15 min** above 120°C
- Cycle time: **35 minutes** (2100 seconds)
- 5 zones: 110 / 135 / 145 / 145 / 130°C (setpoints)

---

## NG Failure Mode Distribution

| Code | Failure Mode | Root Cause |
|---|---|---|
| NG-01 | Low peak temperature | Burner fault / gas pressure low |
| NG-02 | High peak temperature | Burner overshoot / thermocouple fault |
| NG-03 | Short cure time | Conveyor speed too high |
| NG-04 | Uneven temperature | Fan degradation / airflow restriction |
| NG-05 | Slow ramp rate | Filter choke / damper restriction |
| NG-06 | Mid-cycle temperature drop | Intermittent burner fault |
| NG-07 | Zone-specific low temp | Individual zone fault |
| NG-08 | Global low temperature | Global oven setting error |

---

## Sensor Locations (12 sensors — BYK Gardner placement)

| Sensor | Location | Thermal Behavior |
|---|---|---|
| LH HOOD | Left Hand Hood | Slight lag (high mass) |
| LH FENDER | Left Fender | Normal |
| LH FRONT DOOR | Left Front Door | Normal / Core |
| LH REAR DOOR | Left Rear Door | Normal / Core |
| LH Q/P | Left Quarter Panel | Slower (extremity) |
| LH T/G | Left Tailgate | Slowest (extremity) |
| RH T/G | Right Tailgate | Slowest (extremity) |
| RH Q/P | Right Quarter Panel | Slower (extremity) |
| RH REAR DOOR | Right Rear Door | Normal / Core |
| RH FR DOOR | Right Front Door | Normal / Core |
| RH FENDER | Right Fender | Normal |
| RH HOOD | Right Hand Hood | Slight lag (high mass) |

---

## How to Use

### Load metadata
```python
import pandas as pd
df = pd.read_csv('generated/ALL_OVENS_metadata.csv')
print(df['result_actual'].value_counts())
```

### Load a time-series trial
```python
ts = pd.read_csv('generated/ED/timeseries/ED-0001.csv')
ts.plot(x='time_s', y=[c for c in ts.columns if c.startswith('T_')])
```

### Load standard curve
```python
std = pd.read_csv('generated/standard_curves/ED_standard_curve.csv')
```

---

*Generated by: Stellantis Virtual EMT Phase 0 Data Generator v1.0*
*Standards: ISO 12944, VDA 621-415, Ford FLTM BI 106-01, BYK Gardner format*
