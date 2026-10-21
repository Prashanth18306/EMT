# Stellantis Virtual EMT — Paint Oven Thermal Validation Platform

> **CSV-driven thermal validation system for automotive paint shop ovens.**
> Validates vehicle curing across ED, Sealer, and Topcoat ovens by comparing uploaded trial telemetry against a standard goal reference curve, performing automatic zone detection, per-sensor EMT audit, fault classification, and digital quality certificate generation.

---

## What This System Does

In automotive paint shops, vehicle bodies pass through gas-fired curing ovens where temperature must be precisely controlled across 5 zones for 40 minutes. Too cold = undercure (corrosion failure). Too fast = short soak (adhesive failure). Too hot = overcure (paint burning). Too uneven = airflow fault.

This platform replaces manual physical datalogger trials by letting engineers upload CSV telemetry files and instantly receive:
- **GO / NG verdict** for the production run
- **Automatic detection of 5 oven process zones** from the temperature curve shape
- **Per-sensor analysis** (which of 12 sensors passed/failed and why)
- **Zone-sensor fault correlation** (which sensor in which zone has a defect)
- **Cure Quality Index (CQI)** score and Arrhenius-based cure index per sensor
- **Printable quality certificate** (HTML report)

---

## System Architecture

```
+------------------------------------------------------------------+
|                        FRONTEND (Browser)                        |
|                                                                  |
|  +------------------+  +-----------------+  +-----------------+  |
|  |  CSV File Drop   |  | Sample Preset   |  | Live Crosshair  |  |
|  |  (3 CSV inputs)  |  | Selector Panel  |  | Zone Timeline   |  |
|  +--------+---------+  +--------+--------+  +-----------------+  |
|           |                     |                                 |
|           +---------------------+                                 |
|                              POST /api/validate-csv               |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                  BACKEND -- FastAPI (app.py)                     |
|                                                                  |
|  +------------------------------------------------------------+  |
|  |              CSVPipeline (csv_pipeline.py)                 |  |
|  |                                                            |  |
|  |  parse_sensor_csv()  --->  parse_config_csv()             |  |
|  |         |                        |                         |  |
|  |         v                        v                         |  |
|  |  validate_trial_against_goal()  <--- ZoneDetector         |  |
|  |         |                            (zone_detector.py)   |  |
|  |         v                                                  |  |
|  |  GO / NG Verdict + Zone Table + Sensor Audit               |  |
|  +------------------------------------------------------------+  |
|                                                                  |
|  Endpoints: /api/validate-csv  /api/export-csv-certificate       |
|             /api/sample-csvs   /api/sample-csv/{file}            |
|             /api/status                                          |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|              CHART RENDERER (chart_renderer.js)                  |
|                                                                  |
|  38px Zone Timeline Track (top):                                 |
|  Zone 1 | ---- Zone 2 ---- | - Zone 3 - | - Zone 4 - | Zone 5  |
|  Entry  |    Preheat       |    Soak    | Cure Hold  | Cooling  |
|         |   12.3 min       |  6.6 min   |  10.9 min  |  9.9 min |
|                                                                  |
|  Multi-line temperature chart (12 sensors vs goal):              |
|  - Trial curves (solid lines, colour-coded S1-S12)              |
|  - Goal reference curve (dashed white)                           |
|  - Vertical dashed zone boundary dividers                        |
|  - Interactive vertical crosshair with zone progress tooltip     |
+------------------------------------------------------------------+
```

---

## Repository Structure

```
|-- dashboard/
|   |-- app.py                        # FastAPI backend -- REST API server
|   `-- static/
|       |-- index.html                # Single-page UI (dark mode industrial design)
|       |-- css/style.css             # Design system (glassmorphism, gradients)
|       `-- js/
|           |-- dashboard.js          # State management, CSV upload, API calls
|           `-- chart_renderer.js     # Chart.js renderer -- zone timeline + crosshair
|
|-- data/
|   |-- src/
|   |   |-- config.py                 # Master config: sensors, zones, oven specs, fault codes
|   |   |-- csv_pipeline.py           # Core validation engine (parse -> detect -> audit)
|   |   |-- zone_detector.py          # Automatic 5-zone segmentation from temperature curves
|   |   `-- __init__.py               # Module exports
|   `-- sample/                       # Pre-packaged OEM sample datasets (13 files)
|       |-- oven_vehicle_config_ED_CC21.csv
|       |-- oven_vehicle_config_SEALER_CC31.csv
|       |-- oven_vehicle_config_TOPCOAT_CC51.csv
|       |-- standard_goal_ED_CC21.csv
|       |-- standard_goal_SEALER_CC31.csv
|       |-- standard_goal_TOPCOAT_CC51.csv
|       |-- trial_normal_ed.csv           # Nominal run -- 1s sampling, 40 min
|       |-- trial_ed_normal_15s.csv       # Nominal run -- 15s interval
|       |-- trial_ed_normal_60s.csv       # Nominal run -- 60s interval
|       |-- trial_burner_trip_sample.csv  # Fault: burner flameout
|       |-- trial_burner_overshoot_sample.csv  # Fault: overcure +25 C
|       |-- trial_conveyor_fast_sample.csv     # Fault: conveyor overspeed
|       `-- trial_fan_degradation_sample.csv   # Fault: recirculation fan 58% RPM
|
|-- tests/
|   `-- test_csv_engine.py            # Full test suite (5 suites)
|-- requirements.txt
`-- README.md
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- Packages: `fastapi`, `uvicorn`, `pandas`, `numpy`, `scipy`

### Install and Run

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server from the project root
python dashboard/app.py
```

Open browser at **`http://localhost:8000`**

---

## Inputs -- What You Upload

The system takes **three CSV files** as inputs:

### 1. Trial CSV (Required)
Raw telemetry from the oven for a single vehicle transit (00:00 to 40:00).

| Column | Type | Description |
|--------|------|-------------|
| `timestamp` | MM:SS or seconds | Time of measurement |
| `temperature_1` ... `temperature_12` | float degC | 12 sensor readings (S1-S12) |
| `gas_pressure` | float mbar | Burner gas supply pressure |
| `conveyor_speed` | float m/min | Line conveyor speed |
| `fan_speed` | int RPM | Recirculation fan speed |
| `burner_state` | int (0/1) | Burner ON/OFF |
| `damper_opening` | float % | Fresh air damper position |
| `exhaust_fan_speed` | int RPM | Exhaust fan speed |
| `vehicle_loading` | int | Number of vehicles on line |

**Accepted sampling intervals:** Any (1s, 15s, 60s, irregular) -- the engine auto-interpolates to a common time grid.

### 2. Standard Goal CSV (Required)
Same column format as Trial CSV. Represents the validated reference cure curve from a certified physical trial. Used for deviation comparison and zone boundary benchmarking.

### 3. Config CSV (Required)
Two-row file defining the oven and vehicle combination:

| Field | Example | Description |
|-------|---------|-------------|
| `process_purpose` | Electrodeposition Primer Oven | Oven type label |
| `total_transit_time_s` | 2400 | Total oven transit duration (seconds) |
| `cure_threshold_C` | 165.0 | Minimum cure temperature (degC) |
| `target_peak_min_C` | 185.0 | Lower bound for peak cure temperature |
| `target_peak_max_C` | 205.0 | Upper bound for peak cure temperature |

---

## Oven Zones -- Architecture

The oven is divided into **5 fixed process zones**, each with dedicated sensors:

| Zone | Stage | Process Type | Sensors | Colour |
|------|-------|-------------|---------|--------|
| Zone 1 | Entry Ramp | Boundary warm-up | S5 (T_LH_Q_P), S6 (T_LH_T_G) | Blue |
| Zone 2 | Preheat | Ramp-up heating | S2 (T_LH_FENDER), S11 (T_RH_FENDER) | Indigo |
| Zone 3 | Soak and Cross-link | Active cure | S1 (T_LH_HOOD), S3 (T_LH_FRONT_DOOR), S4 (T_LH_REAR_DOOR) | Violet |
| Zone 4 | Peak Cure Hold | Thermal peak | S12 (T_RH_HOOD), S10 (T_RH_FR_DOOR), S9 (T_RH_REAR_DOOR) | Red |
| Zone 5 | Cooling Exit | Quench ramp-down | S7 (T_RH_T_G), S8 (T_RH_Q_P) | Teal |

Each zone's typical transit duration at nominal line speed:

| Zone | Typical Duration |
|------|-----------------|
| Entry Ramp (Zone 1) | ~0:20 min |
| Preheat (Zone 2) | ~12.3 min |
| Soak (Zone 3) | ~6.6 min |
| Cure Hold (Zone 4) | ~10.9 min |
| Cooling (Zone 5) | ~9.9 min |

---

## Validation Logic -- How Calculations Work

### Step 1 -- CSV Parsing (csv_pipeline.py)
- Reads Trial, Goal, and Config CSVs
- Converts MM:SS timestamps to seconds
- Extracts 12 sensor columns (temperature_1 ... temperature_12)
- Computes mean temperature across all 12 sensors
- Extracts operational parameters: gas pressure, fan speed, conveyor speed, burner state

### Step 2 -- Automatic Zone Detection (zone_detector.py)
Finds the 5 zone boundaries using **first and second derivative analysis** of the mean temperature curve:
1. Compute dT/dt (first derivative) -- rate of temperature change
2. Compute d2T/dt2 (second derivative) -- inflection points
3. Locate 4 transition timestamps by finding peaks and zero-crossings of these derivatives
4. Assign each segment to: Entry Ramp > Preheat > Soak > Cure Hold > Cooling

Done independently for both Trial and Goal curves, so timing shifts are measured.

### Step 3 -- Sensor-Level EMT Audit (per S1-S12)

| Metric | Calculation |
|--------|-------------|
| Peak temperature | max(temperature_n) over full 40-min window |
| Time at peak | Timestamp where temperature_n reaches its maximum |
| Time above cure threshold | Seconds where temperature_n >= cure_threshold_C, converted to minutes |
| Arrhenius Cure Index (CI) | Numerical integration of exp(-Ea / R*T(t)) over the cure window. Higher = better chemical cross-linking |
| Status | PASS or FAIL based on peak temp, cure time, and CI thresholds |

### Step 4 -- Zone-Level Comparison (Trial vs Goal)

| Check | Logic |
|-------|-------|
| Zone timing | Compare zone start/end timestamps of Trial vs Goal |
| Zone duration | WARN if zone is more than 15% shorter than Goal (conveyor overspeed) |
| Peak temperature | delta_peak = trial_peak minus goal_peak per zone |
| Status | PASS if delta_peak < 5 degC and duration within spec; WARN if 5-15 degC; FAIL if >15 degC |

### Step 5 -- Zone-Sensor Fault Correlation
After detecting which zones and sensors fail, the system cross-references them:
- **Zone 1 sensor failure** -- Entry ramp airflow or intake damper issue
- **Zone 2 sensor failure** -- Preheat burner or gas pressure fault
- **Zone 3/4 sensor failure** -- Active cure zone burner or fan distribution issue
- **Zone 5 sensor failure** -- Cooling fan degradation or exit airflow restriction

### Step 6 -- Global Verdict and CQI

| Metric | Formula |
|--------|---------|
| Cure Quality Index (CQI) | mean(per_sensor_cure_index) / target_cure_index * 100%, clamped 0-100 |
| Thermal Spread | max(peak_12_sensors) minus min(peak_12_sensors) -- cross-body uniformity |
| Mean Deviation from Goal | mean(abs(trial_curve minus interpolated_goal_curve)) across full timeline |
| Verdict | GO (OK) if ALL sensors PASS and ALL zones PASS and thermal spread < 25 degC |

### Step 7 -- Fault Classification
If NG, the system identifies root cause:

| Code | Fault | Trigger Condition |
|------|-------|------------------|
| NG-01 | Low peak temp | peak < target_peak_min_C |
| NG-02 | High peak temp | peak > target_peak_max_C |
| NG-03 | Short cure time | Zone 3+4 duration < 85% of goal |
| NG-04 | Uneven temperature | Thermal spread > 25 degC |
| NG-05 | Slow ramp | Zone 1 duration > 120% of goal |
| NG-06 | Mid-cycle drop | Temperature dip during Zone 3 or 4 |
| NG-07 | Zone-specific low | Single zone below threshold while others pass |
| NG-08 | Global low | All zones uniformly below target |

---

## Frontend -- User Interface

### Layout
- **Header**: System name, verdict badge (green GO / red NG), live KPI strip
- **Left Panel**: Sample preset selector, CSV upload dropzones (Trial / Goal / Config), Validate button
- **Right Panel**: Zone timeline + temperature chart + zone/sensor result tables

### Zone Timeline Track (chart_renderer.js)
A **38px dedicated track above the chart** showing:
- Colour-coded zone bands matching zone colours in config.py
- Zone name and duration badge per segment
- Vertical dashed white dividers at zone boundaries
- Interactive vertical crosshair: hover on chart to see timestamp, zone name, zone % progress, and all sensor temperatures

### Chart Rendering (chart_renderer.js)
- Powered by Chart.js with custom plugin
- 12 sensor lines (solid, colour-coded S1-S12) + 1 goal reference line (dashed white)
- Y-axis: temperature degC | X-axis: time in MM:SS
- Zone boundary dividers as vertical dashed lines at detected transition timestamps
- Chart updates on every validation response (no page reload)

### Sample Presets (dashboard.js)
7 pre-loaded scenarios accessible via single click:

| Preset | Type | Expected Verdict |
|--------|------|-----------------|
| Normal Production Run (1s) | Nominal | GO |
| Normal Production Run (15s) | Nominal sparse | GO |
| Normal Production Run (60s) | Coarse historian | GO |
| Burner Flameout | Fault | NG |
| Conveyor Overspeed | Fault | NG |
| Fan Degradation 58% RPM | Fault | NG |
| Burner Overshoot +25 degC | Fault | NG |

---

## Backend API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | / | Serve dashboard HTML |
| GET | /api/status | System health, available ovens, sensor list |
| GET | /api/sample-csvs | Catalog of pre-packaged sample datasets |
| GET | /api/sample-csv/{filename} | Raw CSV content of a sample file |
| POST | /api/validate-csv | Main validation: Trial + Goal + Config CSVs, returns full result |
| POST | /api/export-csv-certificate | Generates printable HTML quality certificate |

### POST /api/validate-csv -- Response Schema

```json
{
  "verdict": "GO (OK)",
  "is_pass": true,
  "cqi_score": 94.7,
  "quality_tier": "GOLD TIER",
  "violations": [],
  "stats": {
    "thermal_spread_C": 4.2,
    "min_cure_index": 23.1,
    "mean_deviation_from_goal_C": 1.8
  },
  "config_meta": {
    "process_purpose": "Electrodeposition Primer Oven",
    "cure_threshold": 165.0,
    "body_platform_name": "CC21"
  },
  "zone_comparison_table": [
    {
      "name": "Zone 1 (Entry Ramp)",
      "stage": "Entry Ramp",
      "trial_timing": "00:00-00:20",
      "goal_timing": "00:00-00:20",
      "trial_duration": "0.3 min",
      "goal_duration": "0.3 min",
      "trial_peak_C": 35.8,
      "goal_peak_C": 35.7,
      "delta_peak_C": 0.1,
      "status": "PASS"
    }
  ],
  "sensor_audit_table": [
    {
      "sensor": "S1 -- Zone 3 Upper Roof",
      "peak_temp_C": 192.4,
      "peak_time_mmss": "23:10",
      "cure_index": 26.3,
      "time_above_cure_min": 14.2,
      "status": "PASS",
      "failure_reasons": []
    }
  ]
}
```

---

## Supported Oven Types

| Oven | Cure Threshold | Peak Target | Total Transit |
|------|---------------|-------------|--------------|
| ED (Electrodeposition Primer) | 165 degC | 185-205 degC | 40 min |
| Sealer (PVC Underbody) | 130 degC | 150-170 degC | 30 min |
| Topcoat (Basecoat + Clearcoat) | 120 degC | 130-150 degC | 35 min |

## Supported Vehicle Platforms

CC21, CC31, CC41, CC51, CC61

Each platform applies a mass_factor (1.00-1.16) to thermal inertia calculations.

---

## Test Suite (tests/test_csv_engine.py)

```bash
python tests/test_csv_engine.py
```

| Test | What It Verifies |
|------|-----------------|
| Interval Invariance | 1s, 15s, 60s inputs all produce same GO verdict |
| 40-min Range | Timestamp range always 0-2400s regardless of interval |
| 5-Zone Detection | Auto-detects all 5 zones from derivative analysis |
| Fault Classification | Burner trip, conveyor fast, fan degradation produce NG with correct fault code |
| API Endpoints | FastAPI /api/validate-csv and /api/status respond correctly |

---

## Standards Alignment

| Standard | Scope |
|----------|-------|
| ISO 12944 | Corrosion protection of steel -- paint system requirements |
| VDA 621-415 | German automotive paint quality assessment methodology |
| Ford FLTM BI 106-01 | Ford paint cure verification -- time-temperature integration |

---

## Future -- PLC Telemetry Integration

The system is architected for live plant deployment. Planned roadmap:

1. **Real-time PLC feed**: Replace CSV upload with OPC-UA or Modbus TCP socket stream from plant PLC
2. **Live zone streaming**: Continuous zone boundary updates as vehicle progresses through oven
3. **Worker fault diagnostics**: Push NG alerts with zone-sensor fault location to floor operator tablets
4. **Digital twin visualization**: Real-time 3D vehicle body heatmap showing temperature per panel position

---

## License

Developed for the **Stellantis Virtual EMT Predictive Paint Oven Thermal Validation Initiative**.
All rights reserved.
