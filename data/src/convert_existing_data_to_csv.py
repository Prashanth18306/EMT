"""
Stellantis Virtual EMT — Convert all existing system data, specs, presets, and standard curves into CSV format.
Stores all generated CSVs in data/sample/ directory matching the user's exact 3 CSV schemas.
"""

import os
import sys
import numpy as np
import pandas as pd

# Add project paths
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.dirname(CURRENT_DIR)
WORKSPACE_DIR = os.path.dirname(DATA_DIR)
sys.path.insert(0, DATA_DIR)
sys.path.insert(0, CURRENT_DIR)

from src.config import OVEN_SPECS, VEHICLE_MODELS, VEHICLE_MASS_FACTOR
from src.physics_engine import ThermodynamicPhysicsEngine

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample")
os.makedirs(SAMPLE_DIR, exist_ok=True)

physics_engine = ThermodynamicPhysicsEngine()

# Nominal zone setpoints per oven type
OVEN_ZONE_SETPOINTS = {
    "ED": (140.0, 175.0, 190.0, 190.0, 180.0),
    "SEALER": (120.0, 150.0, 165.0, 165.0, 150.0),
    "TOPCOAT": (110.0, 135.0, 145.0, 145.0, 130.0),
    "CLEARCOAT": (115.0, 140.0, 150.0, 150.0, 135.0),
}

CRITICAL_BANDS = {
    "ED": (150.0, 165.0, 185.0),
    "SEALER": (120.0, 130.0, 150.0),
    "TOPCOAT": (110.0, 120.0, 140.0),
    "CLEARCOAT": (115.0, 125.0, 145.0),
}

def create_config_csv(oven_type="ED", vehicle_model="CC21", filename=None):
    """Generate Combined Oven & Vehicle Parameters CSV with max 40 minutes (2400s)."""
    spec = OVEN_SPECS.get(oven_type, OVEN_SPECS["ED"])
    z_sets = OVEN_ZONE_SETPOINTS.get(oven_type, (140.0, 175.0, 190.0, 190.0, 180.0))
    bands = CRITICAL_BANDS.get(oven_type, (150.0, 165.0, 185.0))
    mass_f = VEHICLE_MASS_FACTOR.get(vehicle_model, 1.0)
    lag = int((mass_f - 1.0) * 120)
    offset = round((mass_f - 1.0) * (-4.0), 1)

    csv_line_header = (
        "process_purpose,total_time_s,cure_threshold,target_peak_min,target_peak_max,cure_index_ok,cure_time_min_ok,"
        "zone_1_setpoint_entry_ramp,zone_2_setpoint_preheat,zone_3_setpoint_soak_in,zone_4_setpoint_cure_hold,zone_5_setpoint_cooling_exit,"
        "critical_band_low,critical_band_mid,critical_band_high,body_platform_name,relative_mass_factor,thermal_inertia_lag,peak_temp_offset,body_construction_note\n"
    )
    # Ensure total_time_s is 2400 (40 minutes)
    total_time_s = 2400
    csv_line_val = (
        f"{spec['name']},{total_time_s},{spec['cure_threshold']},{spec['target_peak_ok'][0]},{spec['target_peak_ok'][1]},"
        f"{spec['cure_index_ok']},{spec['cure_time_min_ok']},{z_sets[0]},{z_sets[1]},{z_sets[2]},{z_sets[3]},{z_sets[4]},"
        f"{bands[0]},{bands[1]},{bands[2]},{vehicle_model},{mass_f},{lag},{offset},Lightweight sheet and structural BIW\n"
    )

    if not filename:
        filename = f"oven_vehicle_config_{oven_type}_{vehicle_model}.csv"
    path = os.path.join(SAMPLE_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv_line_header)
        f.write(csv_line_val)
    print(f"Generated Config CSV: {path}")
    return path

def generate_sensor_df(plc_inputs, step_s=1):
    """Simulate 12 sensors and format into exact CSV dataframe from 00:00 to 40:00."""
    inputs = dict(plc_inputs)
    inputs["total_time_s"] = 2400
    
    # Simulate up to 2400s
    time_axis, curves_2d = physics_engine.simulate_thermal_profile(inputs)
    
    # Ensure time_axis reaches 2400s
    if len(time_axis) < 2401:
        # pad to 2401 points (0..2400s)
        pad_len = 2401 - len(time_axis)
        t_ext = np.arange(len(time_axis), 2401, 1, dtype=float)
        time_axis = np.concatenate([time_axis, t_ext])
        c_last = curves_2d[:, -1:]
        # cool down towards ambient 26°C in exit
        ambient = 26.0
        ext_curves = np.zeros((12, pad_len))
        for i in range(pad_len):
            dt = i + 1
            ext_curves[:, i] = ambient + (c_last[:, 0] - ambient) * np.exp(-0.003 * dt)
        curves_2d = np.concatenate([curves_2d, ext_curves], axis=1)

    total_time = 2400
    indices = np.arange(0, total_time + 1, step_s)
    t_sub = time_axis[indices]
    curves_sub = curves_2d[:, indices]
    
    timestamps = [f"{int(s)//60:02d}:{int(s)%60:02d}" for s in t_sub]
    data = {"timestamp": timestamps}
    
    for i in range(12):
        data[f"temperature_{i+1}"] = np.round(curves_sub[i, :], 1)
        
    conveyor = inputs.get("plc_conveyor_speed_m_min", 2.20)
    gas = inputs.get("plc_gas_pressure_mbar", 51.0)
    fan = int(inputs.get("plc_fan_speed_pct", 85.0) * 17.5)
    burner = int(inputs.get("plc_burner_state", 1))
    damper = inputs.get("plc_damper_pos_pct", 52.0)
    exh = int(inputs.get("plc_exhaust_fan_pct", 75.0) * 15.5)
    loading = int(inputs.get("plc_loading_vehicles", 5))
    
    data["gas_pressure"] = np.round(gas + np.random.normal(0, 0.05, len(t_sub)), 2)
    data["conveyor_speed"] = np.round(conveyor + np.random.normal(0, 0.01, len(t_sub)), 2)
    data["fan_speed"] = np.round(fan + np.random.normal(0, 3, len(t_sub)), 0).astype(int)
    data["burner_state"] = np.full(len(t_sub), burner, dtype=int)
    data["damper_opening"] = np.round(damper + np.random.normal(0, 0.2, len(t_sub)), 1)
    data["exhaust_fan_speed"] = np.round(exh + np.random.normal(0, 4, len(t_sub)), 0).astype(int)
    data["vehicle_loading"] = np.full(len(t_sub), loading, dtype=int)
    
    return pd.DataFrame(data)

def main():
    print("[*] Converting existing system data into CSV files...")
    
    # 1. Config CSVs
    configs = [
        ("ED", "CC21", "oven_vehicle_config_sample.csv"),
        ("ED", "CC21", "oven_vehicle_config_ED_CC21.csv"),
        ("SEALER", "CC31", "oven_vehicle_config_SEALER_CC31.csv"),
        ("TOPCOAT", "CC51", "oven_vehicle_config_TOPCOAT_CC51.csv"),
        ("CLEARCOAT", "CC21", "oven_vehicle_config_CLEARCOAT_CC21.csv"),
    ]
    for ov, vm, fn in configs:
        create_config_csv(ov, vm, fn)

    # 2. Standard Goal Golden Benchmarks
    standard_goals = {
        "standard_goal_sample.csv": {
            "oven_type": "ED", "vehicle_model": "CC21",
            "plc_zone1_setpoint_C": 140.0, "plc_zone2_setpoint_C": 175.0,
            "plc_zone3_setpoint_C": 190.0, "plc_zone4_setpoint_C": 190.0,
            "plc_zone5_setpoint_C": 180.0, "plc_fan_speed_pct": 86.0,
            "plc_conveyor_speed_m_min": 2.18, "plc_gas_pressure_mbar": 51.2,
            "plc_damper_pos_pct": 52.0, "plc_exhaust_fan_pct": 78.0,
            "plc_burner_state": 1, "plc_loading_vehicles": 5
        },
        "standard_goal_ED_CC21.csv": {
            "oven_type": "ED", "vehicle_model": "CC21",
            "plc_zone1_setpoint_C": 140.0, "plc_zone2_setpoint_C": 175.0,
            "plc_zone3_setpoint_C": 190.0, "plc_zone4_setpoint_C": 190.0,
            "plc_zone5_setpoint_C": 180.0, "plc_fan_speed_pct": 86.0,
            "plc_conveyor_speed_m_min": 2.18, "plc_gas_pressure_mbar": 51.2,
            "plc_damper_pos_pct": 52.0, "plc_exhaust_fan_pct": 78.0,
            "plc_burner_state": 1, "plc_loading_vehicles": 5
        },
        "standard_goal_TOPCOAT_CC51.csv": {
            "oven_type": "TOPCOAT", "vehicle_model": "CC51",
            "plc_zone1_setpoint_C": 110.0, "plc_zone2_setpoint_C": 135.0,
            "plc_zone3_setpoint_C": 145.0, "plc_zone4_setpoint_C": 145.0,
            "plc_zone5_setpoint_C": 130.0, "plc_fan_speed_pct": 85.0,
            "plc_conveyor_speed_m_min": 2.15, "plc_gas_pressure_mbar": 50.5,
            "plc_damper_pos_pct": 50.0, "plc_exhaust_fan_pct": 75.0,
            "plc_burner_state": 1, "plc_loading_vehicles": 5
        },
        "standard_goal_SEALER_CC31.csv": {
            "oven_type": "SEALER", "vehicle_model": "CC31",
            "plc_zone1_setpoint_C": 120.0, "plc_zone2_setpoint_C": 150.0,
            "plc_zone3_setpoint_C": 165.0, "plc_zone4_setpoint_C": 165.0,
            "plc_zone5_setpoint_C": 150.0, "plc_fan_speed_pct": 85.0,
            "plc_conveyor_speed_m_min": 2.15, "plc_gas_pressure_mbar": 50.5,
            "plc_damper_pos_pct": 50.0, "plc_exhaust_fan_pct": 75.0,
            "plc_burner_state": 1, "plc_loading_vehicles": 5
        }
    }
    for fn, params in standard_goals.items():
        df = generate_sensor_df(params, step_s=1)
        p = os.path.join(SAMPLE_DIR, fn)
        df.to_csv(p, index=False)
        print(f"Generated Goal CSV ({len(df)} rows): {p}")

    # 3. Existing Presets & Trials
    trials = {
        "trial_normal_sample.csv": {
            "params": standard_goals["standard_goal_sample.csv"],
            "step": 1
        },
        "trial_normal_ed.csv": {
            "params": standard_goals["standard_goal_sample.csv"],
            "step": 1
        },
        "trial_conveyor_fast_sample.csv": {
            "params": {
                "oven_type": "TOPCOAT", "vehicle_model": "CC51",
                "plc_zone1_setpoint_C": 110.2, "plc_zone2_setpoint_C": 134.8,
                "plc_zone3_setpoint_C": 145.1, "plc_zone4_setpoint_C": 144.9,
                "plc_zone5_setpoint_C": 130.4, "plc_fan_speed_pct": 84.1,
                "plc_conveyor_speed_m_min": 2.85, "plc_gas_pressure_mbar": 49.5,
                "plc_damper_pos_pct": 48.0, "plc_exhaust_fan_pct": 75.0,
                "plc_burner_state": 1, "plc_loading_vehicles": 6
            },
            "step": 1
        },
        "trial_burner_trip_sample.csv": {
            "params": {
                "oven_type": "ED", "vehicle_model": "CC31",
                "plc_zone1_setpoint_C": 128.0, "plc_zone2_setpoint_C": 158.5,
                "plc_zone3_setpoint_C": 169.2, "plc_zone4_setpoint_C": 168.0,
                "plc_zone5_setpoint_C": 155.0, "plc_fan_speed_pct": 82.0,
                "plc_conveyor_speed_m_min": 2.22, "plc_gas_pressure_mbar": 34.2,
                "plc_damper_pos_pct": 28.0, "plc_exhaust_fan_pct": 52.0,
                "plc_burner_state": 0, "plc_loading_vehicles": 4
            },
            "step": 1
        },
        "trial_fan_degradation_sample.csv": {
            "params": {
                "oven_type": "SEALER", "vehicle_model": "CC41",
                "plc_zone1_setpoint_C": 119.5, "plc_zone2_setpoint_C": 149.8,
                "plc_zone3_setpoint_C": 164.2, "plc_zone4_setpoint_C": 165.1,
                "plc_zone5_setpoint_C": 150.0, "plc_fan_speed_pct": 58.5,
                "plc_conveyor_speed_m_min": 2.20, "plc_gas_pressure_mbar": 50.1,
                "plc_damper_pos_pct": 40.0, "plc_exhaust_fan_pct": 60.0,
                "plc_burner_state": 1, "plc_loading_vehicles": 5
            },
            "step": 1
        },
        "trial_burner_overshoot_sample.csv": {
            "params": {
                "oven_type": "ED", "vehicle_model": "CC21",
                "plc_zone1_setpoint_C": 165.0, "plc_zone2_setpoint_C": 198.0,
                "plc_zone3_setpoint_C": 218.0, "plc_zone4_setpoint_C": 220.0,
                "plc_zone5_setpoint_C": 205.0, "plc_fan_speed_pct": 92.0,
                "plc_conveyor_speed_m_min": 1.95, "plc_gas_pressure_mbar": 56.0,
                "plc_damper_pos_pct": 60.0, "plc_exhaust_fan_pct": 85.0,
                "plc_burner_state": 1, "plc_loading_vehicles": 5
            },
            "step": 1
        },
        # Arbitrary interval test files:
        "trial_ed_normal_15s.csv": {
            "params": standard_goals["standard_goal_sample.csv"],
            "step": 15
        },
        "trial_sparse_1min_sample.csv": {
            "params": standard_goals["standard_goal_sample.csv"],
            "step": 60
        },
        "trial_ed_normal_60s.csv": {
            "params": standard_goals["standard_goal_sample.csv"],
            "step": 60
        }
    }

    for fn, t_info in trials.items():
        df = generate_sensor_df(t_info["params"], step_s=t_info["step"])
        p = os.path.join(SAMPLE_DIR, fn)
        df.to_csv(p, index=False)
        print(f"Generated Trial CSV ({len(df)} rows, step {t_info['step']}s): {p}")

    print("[SUCCESS] All existing data successfully converted to CSV and stored in data/sample/!")

if __name__ == "__main__":
    main()
