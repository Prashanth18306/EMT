"""
=============================================================================
Stellantis Virtual EMT — Phase 0 Synthetic Data Generator
=============================================================================
Generates realistic EMT (Effective Metal Temperature) time-series data and
PLC operational data mimicking BYK Gardner temp-gard format for:
  - ED Oven  (Electrodeposition)
  - Sealer Oven
  - Topcoat Oven

Standards basis:
  - ISO 12944, VDA 621-415, Ford FLTM BI 106-01
  - BYK Gardner temp-gard V2.3 output format
  - Stellantis CC21/CC31/CC41 vehicle model profiles
=============================================================================
"""

import numpy as np
import pandas as pd
import os
import json
import random
from datetime import datetime, timedelta

# ── Output directory ──────────────────────────────────────────────────────
OUT_DIR = os.path.join(os.path.dirname(__file__), "generated")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Reproducibility ───────────────────────────────────────────────────────
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# ─────────────────────────────────────────────────────────────────────────
# OVEN SPECIFICATIONS  (derived from industry standards research)
# ─────────────────────────────────────────────────────────────────────────
OVEN_SPECS = {
    "ED": {
        "name": "ED Oven (Electrodeposition)",
        "total_time_s": 2400,          # 40 minutes
        "ramp_end_s": 480,             # 8 min ramp
        "soak_start_s": 1200,          # 20 min
        "soak_end_s": 1800,            # 30 min
        "cool_end_s": 2400,            # 40 min
        "target_peak_ok": (185, 205),  # C OK range
        "target_peak_ng_low": (155, 174),
        "target_peak_ng_high": (206, 220),
        "cure_threshold": 165.0,       # C minimum cure temp
        "cure_time_min_ok": 12.0,      # minutes minimum above threshold
        "cure_index_ok": 22.0,         # Arrhenius equivalent-minutes threshold
        "cure_index_ng": 18.0,
        "ambient_temp": 35.0,
        "zone_setpoints_ok": [140, 175, 190, 190, 180],
        "zone_setpoints_ng_low": [110, 145, 160, 160, 150],
        "zone_setpoints_ng_high": [160, 195, 215, 215, 200],
        "conveyor_speed_ok": (3.5, 4.5),     # m/min
        "conveyor_speed_ng_fast": (5.0, 5.8),
        "fan_speed_ok": (75, 95),             # %
        "fan_speed_ng": (45, 62),
        "gas_pressure_ok": (17, 23),          # mbar
        "gas_pressure_ng": (10, 14),
    },
    "SEALER": {
        "name": "Sealer Oven",
        "total_time_s": 1800,
        "ramp_end_s": 360,
        "soak_start_s": 900,
        "soak_end_s": 1440,
        "cool_end_s": 1800,
        "target_peak_ok": (150, 170),
        "target_peak_ng_low": (120, 139),
        "target_peak_ng_high": (171, 185),
        "cure_threshold": 130.0,
        "cure_time_min_ok": 12.0,
        "cure_index_ok": 18.0,
        "cure_index_ng": 14.0,
        "ambient_temp": 35.0,
        "zone_setpoints_ok": [120, 150, 165, 165, 150],
        "zone_setpoints_ng_low": [95, 120, 135, 135, 120],
        "zone_setpoints_ng_high": [140, 170, 185, 185, 170],
        "conveyor_speed_ok": (3.5, 5.0),
        "conveyor_speed_ng_fast": (5.2, 6.0),
        "fan_speed_ok": (70, 90),
        "fan_speed_ng": (40, 58),
        "gas_pressure_ok": (15, 22),
        "gas_pressure_ng": (9, 13),
    },
    "TOPCOAT": {
        "name": "Topcoat Oven",
        "total_time_s": 2100,
        "ramp_end_s": 420,
        "soak_start_s": 1050,
        "soak_end_s": 1680,
        "cool_end_s": 2100,
        "target_peak_ok": (130, 150),
        "target_peak_ng_low": (105, 124),
        "target_peak_ng_high": (151, 165),
        "cure_threshold": 120.0,
        "cure_time_min_ok": 15.0,
        "cure_index_ok": 16.0,
        "cure_index_ng": 12.0,
        "ambient_temp": 35.0,
        "zone_setpoints_ok": [110, 135, 145, 145, 130],
        "zone_setpoints_ng_low": [85, 110, 120, 120, 108],
        "zone_setpoints_ng_high": [130, 155, 165, 165, 150],
        "conveyor_speed_ok": (3.0, 4.5),
        "conveyor_speed_ng_fast": (4.8, 5.5),
        "fan_speed_ok": (72, 92),
        "fan_speed_ng": (42, 60),
        "gas_pressure_ok": (15, 21),
        "gas_pressure_ng": (9, 13),
    },
}

# ─────────────────────────────────────────────────────────────────────────
# SENSOR DEFINITIONS  (12 sensors — BYK Gardner standard BIW placement)
# ─────────────────────────────────────────────────────────────────────────
SENSORS = [
    {"id": 5,  "name": "LH HOOD",      "lag_factor": 0.85, "mass_factor": 1.10},
    {"id": 2,  "name": "LH FENDER",    "lag_factor": 0.90, "mass_factor": 0.95},
    {"id": 7,  "name": "LH FRONT DOOR","lag_factor": 0.92, "mass_factor": 1.00},
    {"id": 8,  "name": "LH REAR DOOR", "lag_factor": 0.91, "mass_factor": 1.00},
    {"id": 9,  "name": "LH Q/P",       "lag_factor": 0.80, "mass_factor": 0.90},
    {"id": 10, "name": "LH T/G",       "lag_factor": 0.78, "mass_factor": 0.88},
    {"id": 11, "name": "RH T/G",       "lag_factor": 0.79, "mass_factor": 0.87},
    {"id": 12, "name": "RH Q/P",       "lag_factor": 0.81, "mass_factor": 0.91},
    {"id": 14, "name": "RH REAR DOOR", "lag_factor": 0.90, "mass_factor": 0.99},
    {"id": 1,  "name": "RH FR DOOR",   "lag_factor": 0.93, "mass_factor": 1.01},
    {"id": 3,  "name": "RH FENDER",    "lag_factor": 0.89, "mass_factor": 0.94},
    {"id": 4,  "name": "RH HOOD",      "lag_factor": 0.84, "mass_factor": 1.08},
]

# ─────────────────────────────────────────────────────────────────────────
# VEHICLE MODELS
# ─────────────────────────────────────────────────────────────────────────
VEHICLE_MODELS = ["CC21", "CC31", "CC41", "CC51", "CC61"]
VEHICLE_MASS_FACTOR = {
    "CC21": 1.00, "CC31": 1.12, "CC41": 0.92, "CC51": 1.20, "CC61": 1.05
}

# ─────────────────────────────────────────────────────────────────────────
# NG FAILURE MODES
# ─────────────────────────────────────────────────────────────────────────
NG_MODES = [
    "NG-01_LOW_PEAK_TEMP",
    "NG-02_HIGH_PEAK_TEMP",
    "NG-03_SHORT_CURE_TIME",
    "NG-04_UNEVEN_TEMP",
    "NG-05_SLOW_RAMP",
    "NG-06_MID_CYCLE_DROP",
    "NG-07_ZONE_SPECIFIC_LOW",
    "NG-08_GLOBAL_LOW",
]

NG_ROOT_CAUSE = {
    "NG-01_LOW_PEAK_TEMP":    "Burner fault / gas pressure low",
    "NG-02_HIGH_PEAK_TEMP":   "Burner overshoot / thermocouple fault",
    "NG-03_SHORT_CURE_TIME":  "Conveyor speed too high",
    "NG-04_UNEVEN_TEMP":      "Fan degradation / airflow restriction",
    "NG-05_SLOW_RAMP":        "Filter choke / damper restriction",
    "NG-06_MID_CYCLE_DROP":   "Intermittent burner fault",
    "NG-07_ZONE_SPECIFIC_LOW":"Zone burner/fan individual fault",
    "NG-08_GLOBAL_LOW":       "Global oven setting error",
}


# ─────────────────────────────────────────────────────────────────────────
# CORE TEMPERATURE PROFILE GENERATOR
# ─────────────────────────────────────────────────────────────────────────
def generate_temperature_profile(spec, sensor, vehicle_model, ng_mode=None, ng_severity=1.0):
    """
    Generate a realistic temperature-time profile for one sensor.
    
    Profile shape:
      [0..ramp_end]   : Sigmoid ramp from ambient to ~80% of peak
      [ramp..soak_start] : Continued rise to peak
      [soak_start..soak_end] : Plateau with small fluctuation
      [soak_end..total] : Exponential cooling
    """
    T = spec["total_time_s"]
    t = np.arange(0, T, 1, dtype=float)   # 1-second samples

    ambient   = spec["ambient_temp"]
    lag       = sensor["lag_factor"]
    mass      = sensor["mass_factor"] * VEHICLE_MASS_FACTOR[vehicle_model]

    # --- Choose peak temperature based on OK / NG mode ---
    if ng_mode is None:
        peak = np.random.uniform(*spec["target_peak_ok"])
    elif ng_mode in ("NG-01_LOW_PEAK_TEMP", "NG-08_GLOBAL_LOW"):
        peak = np.random.uniform(*spec["target_peak_ng_low"])
    elif ng_mode == "NG-02_HIGH_PEAK_TEMP":
        peak = np.random.uniform(*spec["target_peak_ng_high"])
    else:
        peak = np.random.uniform(*spec["target_peak_ok"])

    r_end = spec["ramp_end_s"]
    s_start = spec["soak_start_s"]
    s_end = spec["soak_end_s"]

    profile = np.zeros(T)

    # lag_factor: controls TIMING (how early heating starts relative to oven air)
    # mass_factor: controls minor peak variation (heavier panels = slightly lower peak)
    # In real ovens, all panels eventually approach oven temp; heavy/distant panels just take longer.

    # Apply sensor-specific peak offset: heavier/distant sensors are 5-15C below oven peak
    # lag_factor 1.0 = closest to oven; 0.78 = extremity (arrives ~2.5 min late)
    lag_delay_s = int((1.0 - lag) * 300)   # max 66 sec extra lag for lag=0.78
    mass_offset = (mass - 1.0) * (-8.0)     # heavier = slightly cooler at peak (up to -8C)
    sensor_peak = peak + mass_offset + np.random.normal(0, 1.5)
    sensor_peak = max(sensor_peak, peak - 15)   # never more than 15C below oven peak

    # Effective timing (shifted by lag delay)
    r_end_eff   = r_end   + lag_delay_s
    s_start_eff = s_start + lag_delay_s
    s_end_eff   = min(s_end + lag_delay_s, T - 10)

    # Phase 1: Before ramp start — ambient hold
    for i in range(min(lag_delay_s, T)):
        profile[i] = ambient + np.random.normal(0, 0.3)

    # Phase 2: Ramp (sigmoid from ambient to ~60% of sensor peak)
    for i in range(lag_delay_s, min(r_end_eff, T)):
        rel_i = i - lag_delay_s
        x = (rel_i / max(r_end, 1)) * 12 - 6
        sigmoid = 1 / (1 + np.exp(-x))
        profile[i] = ambient + (sensor_peak * 0.60 - ambient) * sigmoid

    # Phase 3: Continued rise to sensor peak
    for i in range(min(r_end_eff, T), min(s_start_eff, T)):
        progress = (i - r_end_eff) / max(s_start_eff - r_end_eff, 1)
        profile[i] = profile[r_end_eff - 1] + (sensor_peak - profile[r_end_eff - 1]) * np.sqrt(progress)

    # Phase 4: Soak (plateau with ±1°C drift)
    for i in range(min(s_start_eff, T), min(s_end_eff, T)):
        drift = np.random.normal(0, 0.7)
        profile[i] = sensor_peak + drift

    # Phase 5: Cooling (exponential decay)
    cool_const = 0.003 / max(mass, 0.5)
    cool_start = min(s_end_eff, T - 5)
    if cool_start < T:
        start_temp = profile[cool_start - 1] if cool_start > 0 else sensor_peak
        for i in range(cool_start, T):
            dt = i - cool_start
            profile[i] = ambient + (start_temp - ambient) * np.exp(-cool_const * dt)


    # --- Apply NG distortions ---
    if ng_mode == "NG-03_SHORT_CURE_TIME":
        # Compress soak phase — conveyor runs too fast
        factor = np.random.uniform(0.55, 0.75)
        new_s_end = int(s_start + (s_end - s_start) * factor)
        profile[new_s_end:s_end] = [
            ambient + (profile[s_start] - ambient) * np.exp(-cool_const * (k - s_end))
            for k in range(new_s_end, s_end)
        ]

    elif ng_mode == "NG-04_UNEVEN_TEMP":
        # Add ±10–15°C uneven noise to simulate airflow issues
        uneven_offset = np.random.uniform(-15, 15)
        profile += uneven_offset * np.random.uniform(0.5, 1.0)

    elif ng_mode == "NG-05_SLOW_RAMP":
        # Slow down ramp by 30–40%
        slow_factor = np.random.uniform(0.60, 0.75)
        profile[:r_end] *= slow_factor

    elif ng_mode == "NG-06_MID_CYCLE_DROP":
        # Sudden drop in middle of soak (30–60 second burner off event)
        drop_start = np.random.randint(s_start, s_start + int((s_end - s_start) * 0.5))
        drop_dur = np.random.randint(30, 90)
        drop_mag = np.random.uniform(10, 25)
        drop_end = min(drop_start + drop_dur, s_end)
        for i in range(drop_start, drop_end):
            frac = (i - drop_start) / drop_dur
            profile[i] -= drop_mag * np.sin(np.pi * frac)

    elif ng_mode == "NG-07_ZONE_SPECIFIC_LOW":
        # Only specific sensors (Q/P and T/G — extremities) are affected
        if sensor["name"] in ("LH Q/P", "LH T/G", "RH T/G", "RH Q/P"):
            profile *= np.random.uniform(0.80, 0.90)

    # Add realistic measurement noise (±0.5°C sensor noise)
    noise = np.random.normal(0, 0.5, T)
    profile += noise

    # Clamp to physically plausible range
    profile = np.clip(profile, ambient - 2, 230)

    return profile


# ─────────────────────────────────────────────────────────────────────────
# CURE INDEX CALCULATOR
# ─────────────────────────────────────────────────────────────────────────
def calculate_cure_index(profile, threshold, k=12):
    """Arrhenius-based cure index integration (1-second samples)."""
    ci = 0
    time_above = 0
    for temp in profile:
        if temp >= threshold:
            rate = np.exp((temp - threshold) / k)
            ci += rate * (1 / 60)   # convert seconds to minutes equivalent
            time_above += 1
    time_above_min = time_above / 60
    return round(ci, 1), round(time_above_min, 2)


# ─────────────────────────────────────────────────────────────────────────
# CRITICAL VALUES CALCULATOR
# ─────────────────────────────────────────────────────────────────────────
def calculate_critical_values(profile, spec):
    """Compute the same critical values shown in BYK Gardner output."""
    threshold = spec["cure_threshold"]
    T = len(profile)
    t = np.arange(T)

    above_low   = profile >= 150
    above_mid   = profile >= spec["cure_threshold"]       # e.g. 165 for ED
    above_high  = profile >= (spec["cure_threshold"] + 20)

    def first_cross(mask): return int(np.argmax(mask)) if mask.any() else T
    def last_cross(mask):  return int(T - 1 - np.argmax(mask[::-1])) if mask.any() else 0

    t_low_start  = first_cross(above_low)
    t_high_end   = last_cross(above_high)
    t_mid_start  = first_cross(above_mid)
    t_mid_end    = last_cross(above_mid)

    secs_low   = int(above_low.sum())
    secs_mid   = int(above_mid.sum())
    secs_high  = int(above_high.sum())

    def s_to_mmss(s): return f"{s//60:02d}:{s%60:02d}"

    ci, time_above = calculate_cure_index(profile, threshold)
    peak_temp = float(profile.max())
    peak_time = int(profile.argmax())

    return {
        "time_low_start":  s_to_mmss(t_low_start),
        "time_mid_start":  s_to_mmss(t_mid_start),
        "time_high_start": s_to_mmss(first_cross(above_high)),
        "equiv_time":      s_to_mmss(int(t_high_end)),
        "cure_index":      ci,
        "time_above_cure_min": time_above,
        "peak_temp_C":     round(peak_temp, 1),
        "peak_time_mmss":  s_to_mmss(peak_time),
        "duration_low_s":  secs_low,
        "duration_mid_s":  secs_mid,
        "duration_high_s": secs_high,
    }


# ─────────────────────────────────────────────────────────────────────────
# OK / NG JUDGE
# ─────────────────────────────────────────────────────────────────────────
def judge_result(sensor_summaries, spec):
    """
    Determine overall OK/NG based on all 12 sensors.
    
    Industry practice: Pass if >= 8 of 12 sensors meet cure criteria.
    Extremity sensors (Q/P, T/G, Fender) are known to run cooler
    due to thermal mass and are evaluated with relaxed criteria.
    """
    ok_range   = spec["target_peak_ok"]
    ci_ok      = spec["cure_index_ok"]
    t_ok       = spec["cure_time_min_ok"]

    # Core sensors (must pass): Hood, Door panels
    CORE_SENSORS = {"LH HOOD", "LH FRONT DOOR", "LH REAR DOOR",
                    "RH REAR DOOR", "RH FR DOOR", "RH HOOD"}
    # Extremity sensors (relaxed by 15%): Q/P, T/G, Fender
    EXTREM_SENSORS = {"LH Q/P", "LH T/G", "RH T/G", "RH Q/P",
                      "LH FENDER", "RH FENDER"}

    all_peaks = [s["peak_temp_C"] for s in sensor_summaries]
    max_peak  = max(all_peaks)
    min_peak  = min(all_peaks)
    spread    = max_peak - min_peak

    pass_count = 0
    fail_reasons = []
    sensor_fails = []

    for s in sensor_summaries:
        name = s["sensor"]
        is_core = name in CORE_SENSORS
        relax = 1.0 if is_core else 0.80   # 20% relaxation for extremities

        s_ci   = s["cure_index"]
        s_peak = s["peak_temp_C"]
        s_t    = s["time_above_cure_min"]

        s_ok = (
            s_ci   >= ci_ok * relax and
            s_peak >= (ok_range[0] - 12) and
            s_peak <= (ok_range[1] + 10) and
            s_t    >= t_ok * relax
        )
        if s_ok:
            pass_count += 1
        else:
            sensor_fails.append(name)

    # Require at least 8 of 12 sensors to pass
    if pass_count < 8:
        fail_reasons.append(
            "Only %d/12 sensors passed cure criteria (min 8 required). Failed: %s"
            % (pass_count, ", ".join(sensor_fails[:3]) + ("..." if len(sensor_fails) > 3 else ""))
        )

    # Hard limits: overall spread and absolute overcure
    if spread > 25:
        fail_reasons.append("Temperature spread: %.1fC > 25C (uneven heating)" % spread)
    if max_peak > ok_range[1] + 12:
        fail_reasons.append("Overcure: peak %.1fC > %.1fC" % (max_peak, ok_range[1]+12))

    result = "OK" if len(fail_reasons) == 0 else "NG"
    return result, fail_reasons




# ─────────────────────────────────────────────────────────────────────────
# PLC DATA GENERATOR
# ─────────────────────────────────────────────────────────────────────────
def generate_plc_data(spec, ng_mode=None):
    """Generate oven PLC operational parameters for one trial."""
    ok = ng_mode is None

    if ok:
        zone_sp = spec["zone_setpoints_ok"]
        fan     = np.random.uniform(*spec["fan_speed_ok"])
        conv    = np.random.uniform(*spec["conveyor_speed_ok"])
        gas_p   = np.random.uniform(*spec["gas_pressure_ok"])
    else:
        if ng_mode in ("NG-01_LOW_PEAK_TEMP", "NG-08_GLOBAL_LOW", "NG-05_SLOW_RAMP"):
            zone_sp = spec["zone_setpoints_ng_low"]
            gas_p   = np.random.uniform(*spec["gas_pressure_ng"])
        elif ng_mode == "NG-02_HIGH_PEAK_TEMP":
            zone_sp = spec["zone_setpoints_ng_high"]
            gas_p   = np.random.uniform(*spec["gas_pressure_ok"])
        else:
            zone_sp = spec["zone_setpoints_ok"]
            gas_p   = np.random.uniform(*spec["gas_pressure_ok"])

        fan  = np.random.uniform(*spec["fan_speed_ng"]) if ng_mode == "NG-04_UNEVEN_TEMP" else np.random.uniform(*spec["fan_speed_ok"])
        conv = np.random.uniform(*spec["conveyor_speed_ng_fast"]) if ng_mode == "NG-03_SHORT_CURE_TIME" else np.random.uniform(*spec["conveyor_speed_ok"])

    # Add slight noise to zone setpoints (±2°C)
    zone_sp_noisy = [round(z + np.random.uniform(-2, 2), 1) for z in zone_sp]

    return {
        "zone1_setpoint_C":     zone_sp_noisy[0],
        "zone2_setpoint_C":     zone_sp_noisy[1],
        "zone3_setpoint_C":     zone_sp_noisy[2],
        "zone4_setpoint_C":     zone_sp_noisy[3],
        "zone5_setpoint_C":     zone_sp_noisy[4],
        "fan_speed_pct":        round(fan, 1),
        "conveyor_speed_m_min": round(conv, 2),
        "gas_pressure_mbar":    round(gas_p, 1),
        "damper_pos_pct":       round(np.random.uniform(30, 70) if ok else np.random.uniform(15, 45), 1),
        "exhaust_fan_pct":      round(np.random.uniform(60, 90) if ok else np.random.uniform(45, 65), 1),
        "burner_state":         1 if ok or ng_mode not in ("NG-01_LOW_PEAK_TEMP",) else (1 if np.random.random() > 0.3 else 0),
        "loading_vehicles":     np.random.randint(3, 8),
    }


# ─────────────────────────────────────────────────────────────────────────
# SINGLE TRIAL GENERATOR
# ─────────────────────────────────────────────────────────────────────────
def generate_trial(trial_id, oven_type, base_date, ok_flag, vehicle_model=None):
    """Generate one complete EMT trial (all 12 sensors + metadata)."""
    spec = OVEN_SPECS[oven_type]
    T    = spec["total_time_s"]

    if vehicle_model is None:
        vehicle_model = random.choice(VEHICLE_MODELS)

    ng_mode = None
    root_cause = "N/A"
    if not ok_flag:
        ng_mode    = random.choice(NG_MODES)
        root_cause = NG_ROOT_CAUSE[ng_mode]

    # PLC data
    plc = generate_plc_data(spec, ng_mode)

    # Generate all sensor profiles
    time_axis = np.arange(0, T, 1)
    sensor_profiles = {}
    sensor_summaries = []

    for sensor in SENSORS:
        profile = generate_temperature_profile(spec, sensor, vehicle_model, ng_mode)
        cv = calculate_critical_values(profile, spec)
        sensor_profiles[sensor["name"]] = profile
        sensor_summaries.append({"sensor": sensor["name"], **cv})

    # Judge result
    result, fail_reasons = judge_result(sensor_summaries, spec)

    # Compose time-series DataFrame (BYK Gardner format)
    ts_df = pd.DataFrame({"time_s": time_axis})
    ts_df["time_mmss"] = ts_df["time_s"].apply(lambda s: f"{s//60:02d}:{s%60:02d}")
    for sensor in SENSORS:
        ts_df[f"T_{sensor['name'].replace(' ', '_').replace('/', '_')}"] = (
            sensor_profiles[sensor["name"]].round(1)
        )

    # Metadata record
    trial_date = base_date + timedelta(days=random.randint(0, 365),
                                       hours=random.randint(6, 20),
                                       minutes=random.randint(0, 59))

    metadata = {
        "trial_id":          trial_id,
        "oven_type":         oven_type,
        "oven_name":         spec["name"],
        "vehicle_model":     vehicle_model,
        "date":              trial_date.strftime("%Y-%m-%d"),
        "time":              trial_date.strftime("%H:%M:%S"),
        "operator":          random.choice(["ASHWINI", "RAJESH", "PRIYA", "SURESH", "MEENA"]),
        "serial_no":         f"13{random.randint(10000, 99999)}",
        "sampling_rate_s":   1,
        "trigger_threshold_C": 120,
        "duration_s":        T,
        "ng_mode":           ng_mode if ng_mode else "OK",
        "ng_root_cause":     root_cause,
        "result_actual":     result,
        **{f"plc_{k}": v for k, v in plc.items()},
    }

    # Add sensor summary columns to metadata
    for s in sensor_summaries:
        sname = s["sensor"].replace(" ", "_").replace("/", "_")
        metadata[f"{sname}_peak_C"]    = s["peak_temp_C"]
        metadata[f"{sname}_ci"]        = s["cure_index"]
        metadata[f"{sname}_t_cure_min"]= s["time_above_cure_min"]

    return ts_df, metadata


# ─────────────────────────────────────────────────────────────────────────
# BATCH GENERATOR  (Full Phase 0 Dataset)
# ─────────────────────────────────────────────────────────────────────────
def generate_dataset(n_ok=70, n_ng=30, oven_types=None):
    """
    Generate the full Phase 0 dataset.
    Default: 100 trials per oven type (70 OK + 30 NG).
    """
    if oven_types is None:
        oven_types = ["ED", "SEALER", "TOPCOAT"]

    base_date = datetime(2025, 1, 1)
    all_metadata = []

    for oven_type in oven_types:
        print(f"\n[GEN] Generating {oven_type} Oven trials ({n_ok} OK + {n_ng} NG)...")
        oven_ts_all = []

        trial_counter = 1
        for ok in ([True] * n_ok + [False] * n_ng):
            trial_id = f"{oven_type}-{trial_counter:04d}"
            vehicle  = random.choice(VEHICLE_MODELS)
            ts_df, meta = generate_trial(trial_id, oven_type, base_date, ok, vehicle)
            ts_df.insert(0, "trial_id", trial_id)

            # Save individual trial time-series
            ts_dir = os.path.join(OUT_DIR, oven_type, "timeseries")
            os.makedirs(ts_dir, exist_ok=True)
            ts_path = os.path.join(ts_dir, f"{trial_id}.csv")
            ts_df.to_csv(ts_path, index=False)

            all_metadata.append(meta)
            if trial_counter % 20 == 0:
                print(f"  ... {trial_counter}/{n_ok+n_ng} trials done")
            trial_counter += 1

        # Save oven-level metadata summary
        meta_df = pd.DataFrame(all_metadata[-n_ok - n_ng:])
        meta_path = os.path.join(OUT_DIR, oven_type, f"{oven_type}_metadata.csv")
        os.makedirs(os.path.join(OUT_DIR, oven_type), exist_ok=True)
        meta_df.to_csv(meta_path, index=False)
        print(f"  [SAVED] {meta_path}")

    # Save combined metadata (all ovens)
    all_meta_df = pd.DataFrame(all_metadata)
    combined_path = os.path.join(OUT_DIR, "ALL_OVENS_metadata.csv")
    all_meta_df.to_csv(combined_path, index=False)

    # Print summary
    print("\n" + "="*60)
    print("  DATASET GENERATION COMPLETE")
    print("="*60)
    ok_count = all_meta_df[all_meta_df["result_actual"] == "OK"].shape[0]
    ng_count = all_meta_df[all_meta_df["result_actual"] == "NG"].shape[0]
    print(f"  Total trials : {len(all_meta_df)}")
    print(f"  OK           : {ok_count}")
    print(f"  NG           : {ng_count}")
    print(f"  Oven types   : {', '.join(oven_types)}")
    print(f"  Output dir   : {OUT_DIR}")
    print("="*60)

    return all_meta_df


# ─────────────────────────────────────────────────────────────────────────
# EXPORT STANDARD CURVE LIBRARY
# ─────────────────────────────────────────────────────────────────────────
def export_standard_curves():
    """Generate and save golden/standard curing curves for each oven type."""
    std_dir = os.path.join(OUT_DIR, "standard_curves")
    os.makedirs(std_dir, exist_ok=True)

    for oven_type, spec in OVEN_SPECS.items():
        T = spec["total_time_s"]
        t = np.arange(0, T, 1)

        # Generate ideal reference profile (average sensor, mid-range params)
        ideal_sensor = {"id": 99, "name": "IDEAL", "lag_factor": 0.88, "mass_factor": 1.0}
        ideal_profile = generate_temperature_profile(spec, ideal_sensor, "CC21", ng_mode=None)

        std_df = pd.DataFrame({
            "time_s":       t,
            "time_mmss":    [f"{s//60:02d}:{s%60:02d}" for s in t],
            "standard_temp_C": ideal_profile.round(1),
            "lower_limit_C":  np.clip(ideal_profile - 10, 20, 230).round(1),
            "upper_limit_C":  np.clip(ideal_profile + 10, 20, 230).round(1),
            "cure_threshold":  spec["cure_threshold"],
        })

        std_path = os.path.join(std_dir, f"{oven_type}_standard_curve.csv")
        std_df.to_csv(std_path, index=False)

        # Save spec as JSON
        spec_path = os.path.join(std_dir, f"{oven_type}_spec.json")
        with open(spec_path, "w") as f:
            json.dump({k: v for k, v in spec.items() if not k.startswith("target_peak")},
                      f, indent=2)

        print(f"  [OK] Standard curve saved: {std_path}")


# ─────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Stellantis Virtual EMT - Phase 0 Data Generator")
    print("  Standards: ISO 12944, VDA 621-415, Ford FLTM BI 106-01")
    print("=" * 60)

    # Generate standard reference curves
    print("\n[*] Generating standard curves...")
    export_standard_curves()

    # Generate full dataset: 100 trials per oven (70 OK + 30 NG)
    df = generate_dataset(n_ok=70, n_ng=30)

    print("\n[DONE] All done! Check the 'generated/' folder for output files.")
    print("   Next step: Run EDA in Phase 1 -->  notebooks/01_EDA.ipynb")
