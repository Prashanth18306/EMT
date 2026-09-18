"""
Stellantis Virtual EMT — Phase 2: Configuration & Oven Specifications
Aligned with ISO 12944, VDA 621-415, and Ford FLTM BI 106-01 standards.
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "generated")
MODELS_DIR = os.path.join(BASE_DIR, "models")
REPORT_DIR = os.path.join(BASE_DIR, "phase2_model_report")

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)

# 12 Temperature Sensors across Oven Zones 1 to 5 (Virtual EMT Layout)
SENSORS = [
    {"name": "Zone 3 - Upper Roof", "col": "T_LH_HOOD",        "type": "cure_zone",     "mass_factor": 1.05},
    {"name": "Zone 2 - LH Wall",   "col": "T_LH_FENDER",      "type": "standard",      "mass_factor": 0.95},
    {"name": "Zone 3 - Mid Wall",   "col": "T_LH_FRONT_DOOR",  "type": "cure_zone",     "mass_factor": 1.00},
    {"name": "Zone 3 - Lower Air",  "col": "T_LH_REAR_DOOR",   "type": "cure_zone",     "mass_factor": 1.00},
    {"name": "Zone 1 - Upper Air",  "col": "T_LH_Q_P",         "type": "boundary_zone", "mass_factor": 1.10},
    {"name": "Zone 1 - Lower Air",  "col": "T_LH_T_G",         "type": "boundary_zone", "mass_factor": 1.15},
    {"name": "Zone 5 - Lower Air",  "col": "T_RH_T_G",         "type": "boundary_zone", "mass_factor": 1.15},
    {"name": "Zone 5 - Upper Exit", "col": "T_RH_Q_P",         "type": "boundary_zone", "mass_factor": 1.10},
    {"name": "Zone 4 - Lower Air",  "col": "T_RH_REAR_DOOR",   "type": "cure_zone",     "mass_factor": 1.00},
    {"name": "Zone 4 - Mid Wall",   "col": "T_RH_FR_DOOR",     "type": "cure_zone",     "mass_factor": 1.00},
    {"name": "Zone 2 - RH Wall",   "col": "T_RH_FENDER",      "type": "standard",      "mass_factor": 0.95},
    {"name": "Zone 4 - Upper Roof", "col": "T_RH_HOOD",        "type": "cure_zone",     "mass_factor": 1.05},
]

SENSOR_NAMES = [s["name"] for s in SENSORS]
SENSOR_COLS  = [s["col"]  for s in SENSORS]

# 5 Process Zones of the Paint Curing Oven (Zone-Wise Architecture)
OVEN_ZONES = [
    {
        "id": 1,
        "name": "Zone 1 (Entry Ramp)",
        "short_name": "Zone 1",
        "stage": "Entry Ramp",
        "type": "boundary_zone",
        "sensor_cols": ["T_LH_Q_P", "T_LH_T_G"],
        "color": "#00E5FF",
    },
    {
        "id": 2,
        "name": "Zone 2 (Preheat)",
        "short_name": "Zone 2",
        "stage": "Preheat",
        "type": "standard",
        "sensor_cols": ["T_LH_FENDER", "T_RH_FENDER"],
        "color": "#2979FF",
    },
    {
        "id": 3,
        "name": "Zone 3 (Soak In)",
        "short_name": "Zone 3",
        "stage": "Soak & Cross-link",
        "type": "cure_zone",
        "sensor_cols": ["T_LH_HOOD", "T_LH_FRONT_DOOR", "T_LH_REAR_DOOR"],
        "color": "#E040FB",
    },
    {
        "id": 4,
        "name": "Zone 4 (Cure Hold)",
        "short_name": "Zone 4",
        "stage": "Peak Cure Hold",
        "type": "cure_zone",
        "sensor_cols": ["T_RH_HOOD", "T_RH_FR_DOOR", "T_RH_REAR_DOOR"],
        "color": "#FF1744",
    },
    {
        "id": 5,
        "name": "Zone 5 (Cooling Exit)",
        "short_name": "Zone 5",
        "stage": "Cooling Exit",
        "type": "boundary_zone",
        "sensor_cols": ["T_RH_T_G", "T_RH_Q_P"],
        "color": "#00E676",
    },
]

ZONE_NAMES = [z["name"] for z in OVEN_ZONES]

VEHICLE_MODELS = ["CC21", "CC31", "CC41", "CC51", "CC61"]
VEHICLE_MASS_FACTOR = {
    "CC21": 1.00,
    "CC31": 1.04,
    "CC41": 1.08,
    "CC51": 1.12,
    "CC61": 1.16,
}

OVEN_SPECS = {
    "ED": {
        "name": "Electrodeposition Primer Oven",
        "total_time_s": 2400,      # 40 min
        "cure_threshold": 165.0,    # °C
        "target_peak_ok": (185.0, 205.0),
        "cure_index_ok": 22.0,
        "cure_time_min_ok": 12.0,
        "step_s": 15,              # 160 time points
    },
    "SEALER": {
        "name": "Body Sealer Curing Oven",
        "total_time_s": 1800,      # 30 min
        "cure_threshold": 130.0,    # °C
        "target_peak_ok": (150.0, 170.0),
        "cure_index_ok": 20.0,
        "cure_time_min_ok": 12.0,
        "step_s": 15,              # 120 time points
    },
    "TOPCOAT": {
        "name": "Topcoat Curing Oven",
        "total_time_s": 2100,      # 35 min
        "cure_threshold": 120.0,    # °C
        "target_peak_ok": (130.0, 150.0),
        "cure_index_ok": 18.0,
        "cure_time_min_ok": 15.0,
        "step_s": 15,              # 140 time points
    },
}

PLC_FEATURE_COLS = [
    "plc_zone1_setpoint_C",
    "plc_zone2_setpoint_C",
    "plc_zone3_setpoint_C",
    "plc_zone4_setpoint_C",
    "plc_zone5_setpoint_C",
    "plc_fan_speed_pct",
    "plc_conveyor_speed_m_min",
    "plc_gas_pressure_mbar",
    "plc_damper_pos_pct",
    "plc_exhaust_fan_pct",
    "plc_burner_state",
    "plc_loading_vehicles",
]

NG_ROOT_CAUSE = {
    "NG-01_LOW_PEAK_TEMP":     "Burner fault / gas supply pressure below specification",
    "NG-02_HIGH_PEAK_TEMP":    "Burner controller overshoot / thermocouple sensor drift",
    "NG-03_SHORT_CURE_TIME":   "Conveyor line speed exceeded calibrated speed setting",
    "NG-04_UNEVEN_TEMP":       "Circulation fan degradation / oven nozzle airflow restriction",
    "NG-05_SLOW_RAMP":         "Intake filter choking / fresh air damper mechanical restriction",
    "NG-06_MID_CYCLE_DROP":    "Intermittent burner flameout / gas solenoid valve chatter",
    "NG-07_ZONE_SPECIFIC_LOW": "Individual zone burner/fan component failure",
    "NG-08_GLOBAL_LOW":        "Global oven temperature recipe setpoint discrepancy",
}

NG_REMEDY = {
    "NG-01_LOW_PEAK_TEMP":     "Check gas line pressure regulator, clean burner nozzles, verify gas valve opening.",
    "NG-02_HIGH_PEAK_TEMP":    "Recalibrate zone thermocouple sensors, inspect PID temperature controller gain.",
    "NG-03_SHORT_CURE_TIME":   "Reset conveyor VFD drive speed to standard line speed setpoint.",
    "NG-04_UNEVEN_TEMP":       "Inspect recirculating fan belts/motors, clean air distribution nozzles.",
    "NG-05_SLOW_RAMP":         "Replace intake air filters, clean and lubricate fresh air damper actuators.",
    "NG-06_MID_CYCLE_DROP":    "Inspect burner flame ignition rod, check gas solenoid wiring and safety interlocks.",
    "NG-07_ZONE_SPECIFIC_LOW": "Inspect specific zone heating elements/burners and temperature transmitters.",
    "NG-08_GLOBAL_LOW":        "Verify PLC recipe selection matches vehicle body production schedule.",
}
