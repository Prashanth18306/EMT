"""
Stellantis Virtual EMT — Phase 2: Feature Engineering & Physics Engine
Calculates Arrhenius Cure Index, Peak Temps, Time-at-Cure, and transforms PLC inputs.
"""

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from src.config import SENSORS, SENSOR_COLS, OVEN_SPECS, PLC_FEATURE_COLS

def calculate_cure_index(profile, threshold_temp, arrhenius_k=12.0):
    """
    Arrhenius cure index integration:
    CI = sum( exp((T - threshold) / k) ) * dt_minutes (for T >= threshold)
    """
    above = profile >= threshold_temp
    if not np.any(above):
        return 0.0, 0.0
    dt_min = 1.0 / 60.0  # assuming 1-second resolution
    weights = np.exp((profile[above] - threshold_temp) / arrhenius_k)
    ci = np.sum(weights) * dt_min
    time_above_min = np.sum(above) / 60.0
    return float(round(ci, 1)), float(round(time_above_min, 2))

def extract_curve_critical_values(time_axis, sensor_curves, oven_type):
    """
    Extract physics-based critical values from predicted/actual curves:
    sensor_curves: shape (N_sensors, N_points) or dictionary of {col: array}
    Returns: dict with peak temps, cure index, time at cure for all 12 sensors.
    """
    spec = OVEN_SPECS[oven_type]
    cure_th = spec["cure_threshold"]
    total_time = spec["total_time_s"]

    # Reconstruct 1-second profile for high-precision integration
    t_1s = np.arange(0, total_time, 1)
    
    results = {}
    peaks = []
    cis = []
    t_cures = []

    for idx, s in enumerate(SENSORS):
        col = s["col"]
        name = s["name"]
        
        if isinstance(sensor_curves, dict):
            pts = sensor_curves[col]
        else:
            pts = sensor_curves[idx]

        # Spline/linear interpolation to 1s
        interp_func = interp1d(time_axis, pts, kind="linear", fill_value="extrapolate")
        profile_1s = interp_func(t_1s)

        peak_val = float(round(np.max(profile_1s), 1))
        ci_val, tc_val = calculate_cure_index(profile_1s, cure_th)

        results[f"{name}_peak_C"] = peak_val
        results[f"{name}_ci"] = ci_val
        results[f"{name}_t_cure_min"] = tc_val

        peaks.append(peak_val)
        cis.append(ci_val)
        t_cures.append(tc_val)

    results["summary_max_peak"] = float(round(max(peaks), 1))
    results["summary_min_peak"] = float(round(min(peaks), 1))
    results["summary_spread"] = float(round(max(peaks) - min(peaks), 1))
    results["summary_mean_ci"] = float(round(np.mean(cis), 1))
    results["summary_min_ci"] = float(round(min(cis), 1))
    results["summary_mean_tcure"] = float(round(np.mean(t_cures), 1))
    results["summary_min_tcure"] = float(round(min(t_cures), 1))

    return results

def prepare_plc_features(df_or_dict, feature_columns=None):
    """
    Transform raw PLC operational parameters into a standardized feature matrix.
    Supports single dict or DataFrame.
    """
    if isinstance(df_or_dict, dict):
        df = pd.DataFrame([df_or_dict])
    else:
        df = df_or_dict.copy()

    # Base PLC columns
    cols_to_use = [c for c in PLC_FEATURE_COLS if c in df.columns]
    X_num = df[cols_to_use].copy()

    # Derived physics features
    # 1. Zone gradient (heating ramp steepness across zone setpoints)
    if "plc_zone1_setpoint_C" in X_num.columns and "plc_zone3_setpoint_C" in X_num.columns:
        X_num["feat_zone_ramp_grad"] = X_num["plc_zone3_setpoint_C"] - X_num["plc_zone1_setpoint_C"]
    if "plc_zone3_setpoint_C" in X_num.columns and "plc_zone5_setpoint_C" in X_num.columns:
        X_num["feat_zone_soak_delta"] = X_num["plc_zone4_setpoint_C"] - X_num["plc_zone5_setpoint_C"]
    
    # 2. Airflow proxy (fan * damper)
    if "plc_fan_speed_pct" in X_num.columns and "plc_damper_pos_pct" in X_num.columns:
        X_num["feat_airflow_index"] = (X_num["plc_fan_speed_pct"] * X_num["plc_damper_pos_pct"]) / 100.0

    # 3. Energy index proxy (gas pressure * burner state)
    if "plc_gas_pressure_mbar" in X_num.columns and "plc_burner_state" in X_num.columns:
        X_num["feat_heat_input_index"] = X_num["plc_gas_pressure_mbar"] * X_num["plc_burner_state"]

    # 4. Residence time proxy (cycle duration / conveyor speed)
    if "plc_conveyor_speed_m_min" in X_num.columns:
        X_num["feat_residence_proxy"] = 1.0 / np.maximum(X_num["plc_conveyor_speed_m_min"], 0.1)

    # One-hot encode categorical features: vehicle_model and oven_type
    for cat_col, valid_vals in [
        ("vehicle_model", ["CC21", "CC31", "CC41", "CC51", "CC61"]),
        ("oven_type", ["ED", "SEALER", "TOPCOAT"])
    ]:
        if cat_col in df.columns:
            for val in valid_vals:
                X_num[f"{cat_col}_{val}"] = (df[cat_col] == val).astype(float)

    if feature_columns is not None:
        # Align columns with training schema
        for c in feature_columns:
            if c not in X_num.columns:
                X_num[c] = 0.0
        X_num = X_num[feature_columns]

    return X_num
