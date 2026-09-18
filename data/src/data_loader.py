"""
Stellantis Virtual EMT — Phase 2: Data Loader Module
Loads trial metadata, full time-series EMT profiles, and standard curves.
"""

import os
import pandas as pd
import numpy as np
from src.config import DATA_DIR, OVEN_SPECS, SENSOR_COLS

def load_metadata():
    """Load the master metadata CSV containing all 300 trials."""
    csv_path = os.path.join(DATA_DIR, "ALL_OVENS_metadata.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Metadata file not found at: {csv_path}")
    df = pd.read_csv(csv_path)
    df["label_binary"] = (df["result_actual"] == "NG").astype(int)
    return df

def load_oven_metadata(oven_type):
    """Load metadata for a specific oven type ('ED', 'SEALER', 'TOPCOAT')."""
    csv_path = os.path.join(DATA_DIR, oven_type, f"{oven_type}_metadata.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Oven metadata not found at: {csv_path}")
    df = pd.read_csv(csv_path)
    df["label_binary"] = (df["result_actual"] == "NG").astype(int)
    return df

def load_trial_timeseries(oven_type, trial_id):
    """Load the 1-second sampled time-series DataFrame for a single trial."""
    ts_path = os.path.join(DATA_DIR, oven_type, "timeseries", f"{trial_id}.csv")
    if not os.path.exists(ts_path):
        raise FileNotFoundError(f"Timeseries file not found: {ts_path}")
    return pd.read_csv(ts_path)

def load_standard_curve(oven_type):
    """Load standard golden reference curve for an oven."""
    std_path = os.path.join(DATA_DIR, "standard_curves", f"{oven_type}_standard_curve.csv")
    if not os.path.exists(std_path):
        raise FileNotFoundError(f"Standard curve not found: {std_path}")
    return pd.read_csv(std_path)

def load_all_timeseries_matrix(oven_type, step_s=15):
    """
    Load and resample all time-series trials for an oven into a 3D matrix:
    Shape: (N_trials, N_sensors, N_time_points)
    Returns: (Y_matrix, trial_ids, time_axis)
    """
    meta = load_oven_metadata(oven_type)
    spec = OVEN_SPECS[oven_type]
    total_time = spec["total_time_s"]
    time_len = total_time // step_s
    time_axis = np.arange(0, total_time, step_s)[:time_len]

    n_trials = len(meta)
    n_sensors = len(SENSOR_COLS)
    Y = np.zeros((n_trials, n_sensors, time_len), dtype=np.float32)
    trial_ids = meta["trial_id"].tolist()

    for i, tid in enumerate(trial_ids):
        df = load_trial_timeseries(oven_type, tid)
        for s_idx, col in enumerate(SENSOR_COLS):
            sampled = df[col].iloc[::step_s].values[:time_len]
            Y[i, s_idx, :] = sampled

    return Y, trial_ids, time_axis
