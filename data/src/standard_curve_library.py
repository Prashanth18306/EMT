"""
Stellantis Virtual EMT — Phase 3: Standard Curve Library
Manages golden reference temperature profiles, tolerance envelopes, 
and vehicle model mass compensations aligned with ISO 12944 and Ford FLTM BI 106-01.
"""

import os
import json
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from src.config import DATA_DIR, OVEN_SPECS, VEHICLE_MASS_FACTOR

class StandardCurveLibrary:
    """
    Standard Curve Library for Paint Curing Ovens.
    Provides golden reference curves and tolerance guard bands per oven type and vehicle model.
    """
    def __init__(self, data_dir=None):
        self.data_dir = data_dir or os.path.join(DATA_DIR, "standard_curves")
        self._cache = {}

    def get_standard_curve(self, oven_type, vehicle_model="CC21"):
        """
        Retrieve the golden standard curve and tolerance envelopes.
        Applies thermal mass compensation for different vehicle models.

        Returns:
            dict containing:
                - 'time_s': numpy array
                - 'time_min': numpy array
                - 'standard_temp_C': numpy array
                - 'lower_limit_C': numpy array
                - 'upper_limit_C': numpy array
                - 'cure_threshold': float
                - 'zones': dict of zone time boundaries
        """
        cache_key = f"{oven_type}_{vehicle_model}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        spec = OVEN_SPECS.get(oven_type, OVEN_SPECS["ED"])
        total_time = spec["total_time_s"]
        cure_th = spec["cure_threshold"]
        target_peak = spec["target_peak_ok"]

        # Load base golden curve from CSV if available
        csv_path = os.path.join(self.data_dir, f"{oven_type}_standard_curve.csv")
        if os.path.exists(csv_path):
            base_df = pd.read_csv(csv_path)
            time_s = base_df["time_s"].values
            base_temp = base_df["standard_temp_C"].values
        else:
            # Generate synthetic golden curve analytically
            time_s = np.arange(0, total_time, 1)
            r_end = int(total_time * 0.20)
            s_start = int(total_time * 0.50)
            s_end = int(total_time * 0.75)
            peak_nominal = np.mean(target_peak)
            ambient = 35.0

            base_temp = np.zeros(len(time_s))
            for i in range(r_end):
                x = (i / r_end) * 12 - 6
                sig = 1 / (1 + np.exp(-x))
                base_temp[i] = ambient + (peak_nominal * 0.60 - ambient) * sig

            for i in range(r_end, s_start):
                prog = (i - r_end) / max(s_start - r_end, 1)
                base_temp[i] = base_temp[r_end - 1] + (peak_nominal - base_temp[r_end - 1]) * np.sqrt(prog)

            for i in range(s_start, s_end):
                base_temp[i] = peak_nominal

            cool_const = 0.003
            for i in range(s_end, len(time_s)):
                dt = i - s_end
                base_temp[i] = ambient + (peak_nominal - ambient) * np.exp(-cool_const * dt)

        # Vehicle mass adjustment:
        # Heavier models heat up slightly later (thermal lag) and run ~1-3°C cooler at peak
        mass_factor = VEHICLE_MASS_FACTOR.get(vehicle_model, 1.0)
        mass_offset = (mass_factor - 1.0) * (-4.0) # max -1.6°C for CC61
        lag_seconds = int((mass_factor - 1.0) * 120) # up to 19s lag

        adjusted_temp = np.roll(base_temp + mass_offset, lag_seconds)
        if lag_seconds > 0:
            adjusted_temp[:lag_seconds] = base_temp[0]

        # Calculate Zone Boundaries
        r_end_s   = int(total_time * 0.20)
        s_start_s = int(total_time * 0.50)
        s_end_s   = int(total_time * 0.75)

        # Compute Zone-Specific Tolerance Guard Bands:
        # - Zone 1 (Ramp): ±12°C (natural variability during fast convection heat-up)
        # - Zone 2-4 (Soak/Cure): ±8°C (tight critical cure tolerance per VDA 621-415)
        # - Zone 5 (Cooling): ±15°C (wider allowance as cure is completed)
        upper_limit = np.zeros_like(adjusted_temp)
        lower_limit = np.zeros_like(adjusted_temp)

        for i in range(len(time_s)):
            if i < r_end_s:
                tol = 12.0
            elif i < s_end_s:
                tol = 8.0
            else:
                tol = 15.0
            upper_limit[i] = adjusted_temp[i] + tol
            lower_limit[i] = max(adjusted_temp[i] - tol, 25.0)

        curve_dict = {
            "oven_type": oven_type,
            "vehicle_model": vehicle_model,
            "time_s": time_s,
            "time_min": time_s / 60.0,
            "standard_temp_C": np.round(adjusted_temp, 1),
            "lower_limit_C": np.round(lower_limit, 1),
            "upper_limit_C": np.round(upper_limit, 1),
            "cure_threshold": cure_th,
            "zones": {
                "Zone 1 (Ramp)": (0, r_end_s),
                "Zone 2 (Preheat)": (r_end_s, s_start_s),
                "Zone 3-4 (Soak/Cure)": (s_start_s, s_end_s),
                "Zone 5 (Cooling)": (s_end_s, total_time)
            }
        }

        self._cache[cache_key] = curve_dict
        return curve_dict
