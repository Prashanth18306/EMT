"""
Generates production-grade sample CSVs for Virtual EMT testing matching the user's exact column schemas.
"""

import os
import numpy as np
import pandas as pd

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sample")
os.makedirs(SAMPLE_DIR, exist_ok=True)

# 1. Generate Combined Oven & Vehicle Config CSV
config_csv_path = os.path.join(SAMPLE_DIR, "oven_vehicle_config_sample.csv")
config_content = (
    "process_purpose,total_time_s,cure_threshold,target_peak_min,target_peak_max,cure_index_ok,cure_time_min_ok,"
    "zone_1_setpoint_entry_ramp,zone_2_setpoint_preheat,zone_3_setpoint_soak_in,zone_4_setpoint_cure_hold,zone_5_setpoint_cooling_exit,"
    "critical_band_low,critical_band_mid,critical_band_high,body_platform_name,relative_mass_factor,thermal_inertia_lag,peak_temp_offset,body_construction_note\n"
    "ED Oven,2400,165,185,205,22,12,140,175,190,190,180,150,165,185,CC21,1.0,0,0,Lightweight sheet\n"
)
with open(config_csv_path, "w", encoding="utf-8") as f:
    f.write(config_content)
print(f"Created config: {config_csv_path}")

# Helper to generate sensor curves
def generate_curve(total_s=2400, peak=195.0, burner_state=1, conveyor_speed=2.20, gas_press=51.0, fan_rpm=1480):
    t = np.arange(0, total_s, 1)
    timestamps = [f"{s//60:02d}:{s%60:02d}" for s in t]
    
    # Sigmoidal heating ramp into soak
    r_end = int(total_s * 0.22 * (2.20 / conveyor_speed))
    s_start = int(total_s * 0.50 * (2.20 / conveyor_speed))
    s_end = int(total_s * 0.78 * (2.20 / conveyor_speed))
    
    base = np.zeros(total_s)
    ambient = 26.0
    
    for i in range(r_end):
        prog = i / r_end
        base[i] = ambient + (peak * 0.65 - ambient) * (prog ** 1.3)
        
    for i in range(r_end, s_start):
        prog = (i - r_end) / max(s_start - r_end, 1)
        base[i] = base[r_end - 1] + (peak - base[r_end - 1]) * (prog ** 0.8)
        
    for i in range(s_start, s_end):
        # Plateau with minor natural oscillation
        base[i] = peak + np.sin(i / 30.0) * 0.5
        
    for i in range(s_end, total_s):
        dt = i - s_end
        base[i] = ambient + (peak - ambient) * np.exp(-0.0035 * dt)
        
    # If burner tripped, temperatures drop heavily after second 600
    if burner_state == 0:
        drop_mask = t > 550
        base[drop_mask] = base[drop_mask] - 48.0 * (1.0 - np.exp(-(t[drop_mask] - 550) / 180.0))
        
    # Generate 12 sensors with realistic spatial offsets
    offsets = [1.2, -1.0, 0.5, -0.8, -1.5, 1.8, -0.4, 0.9, -1.2, 0.4, -0.5, 1.0]
    data = {"timestamp": timestamps}
    for idx, off in enumerate(offsets):
        noise = np.random.normal(0, 0.25, total_s)
        sensor_temp = np.clip(np.round(base + off + noise, 1), 20.0, 235.0)
        data[f"temperature_{idx+1}"] = sensor_temp
        
    data["gas_pressure"] = np.round(np.full(total_s, gas_press) + np.random.normal(0, 0.1, total_s), 2)
    data["conveyor_speed"] = np.round(np.full(total_s, conveyor_speed) + np.random.normal(0, 0.02, total_s), 2)
    data["fan_speed"] = np.round(np.full(total_s, fan_rpm) + np.random.normal(0, 5, total_s), 0).astype(int)
    data["burner_state"] = np.full(total_s, burner_state, dtype=int)
    data["damper_opening"] = np.round(np.full(total_s, 55.0) + np.random.normal(0, 0.5, total_s), 1)
    data["exhaust_fan_speed"] = np.round(np.full(total_s, 1180) + np.random.normal(0, 8, total_s), 0).astype(int)
    data["vehicle_loading"] = np.full(total_s, 4, dtype=int)
    
    return pd.DataFrame(data)

# 2. Generate Standard Goal Benchmark CSV
goal_df = generate_curve(total_s=2400, peak=195.0, burner_state=1, conveyor_speed=2.18, gas_press=51.2, fan_rpm=1485)
goal_csv_path = os.path.join(SAMPLE_DIR, "standard_goal_sample.csv")
goal_df.to_csv(goal_csv_path, index=False)
print(f"Created standard goal: {goal_csv_path}")

# 3. Generate Normal Production Trial (PASS - OK)
normal_df = generate_curve(total_s=2400, peak=194.5, burner_state=1, conveyor_speed=2.19, gas_press=51.0, fan_rpm=1480)
normal_csv_path = os.path.join(SAMPLE_DIR, "trial_normal_sample.csv")
normal_df.to_csv(normal_csv_path, index=False)
print(f"Created normal trial: {normal_csv_path}")

# 4. Generate Burner Trip Anomaly Trial (FAIL - NG)
trip_df = generate_curve(total_s=2400, peak=150.0, burner_state=0, conveyor_speed=2.20, gas_press=34.0, fan_rpm=1420)
trip_csv_path = os.path.join(SAMPLE_DIR, "trial_burner_trip_sample.csv")
trip_df.to_csv(trip_csv_path, index=False)
print(f"Created burner trip trial: {trip_csv_path}")

# 5. Generate Conveyor Overspeed Trial (FAIL - NG)
fast_df = generate_curve(total_s=2400, peak=178.0, burner_state=1, conveyor_speed=2.85, gas_press=50.0, fan_rpm=1480)
fast_csv_path = os.path.join(SAMPLE_DIR, "trial_conveyor_fast_sample.csv")
fast_df.to_csv(fast_csv_path, index=False)
print(f"Created conveyor fast trial: {fast_csv_path}")
