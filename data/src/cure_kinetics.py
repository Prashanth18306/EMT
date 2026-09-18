"""
Stellantis Virtual EMT — Phase 3: Cure Kinetics Engine
Arrhenius equation integration, equivalent cure time, and thermal milestones
strictly aligned with BYK Gardner temp-gard V2.3 EMT system specifications.
"""

import numpy as np
from src.config import OVEN_SPECS

class CureKineticsEngine:
    """
    Computes chemical cure kinetics, Arrhenius Equivalent Time, 
    and critical temperature milestones for paint film cross-linking.
    """
    def __init__(self, arrhenius_k=12.0):
        self.arrhenius_k = arrhenius_k

    def compute_sensor_kinetics(self, profile_1s, oven_type):
        """
        Calculates all chemical cure and thermal milestone parameters for 1-second temperature profile.
        Matches the critical values section in BYK Gardner EMT reports.

        Args:
            profile_1s: 1D numpy array of 1-second sampled temperatures (°C)
            oven_type: 'ED' | 'SEALER' | 'TOPCOAT'

        Returns:
            dict of comprehensive kinetic and milestone metrics.
        """
        spec = OVEN_SPECS.get(oven_type, OVEN_SPECS["ED"])
        cure_th = spec["cure_threshold"]
        T = len(profile_1s)
        dt_min = 1.0 / 60.0

        # Peak Temperature & Peak Time
        peak_idx = int(np.argmax(profile_1s))
        peak_temp = float(round(profile_1s[peak_idx], 1))
        peak_time_s = peak_idx
        peak_time_mmss = f"{peak_idx // 60:02d}:{peak_idx % 60:02d}"

        # Arrhenius Cure Index Integration
        above_cure = profile_1s >= cure_th
        if np.any(above_cure):
            weights = np.exp((profile_1s[above_cure] - cure_th) / self.arrhenius_k)
            cure_index = float(round(np.sum(weights) * dt_min, 1))
            time_above_cure_min = float(round(np.sum(above_cure) * dt_min, 2))
        else:
            cure_index = 0.0
            time_above_cure_min = 0.0

        # Critical Temperature Bands (Low, Mid, High, Max) matching BYK Gardner
        if oven_type == "ED":
            t_low, t_mid, t_high = 150.0, 165.0, 185.0
        elif oven_type == "SEALER":
            t_low, t_mid, t_high = 120.0, 130.0, 150.0
        else: # TOPCOAT
            t_low, t_mid, t_high = 110.0, 120.0, 135.0

        # Time of first entry into bands
        idx_low = np.where(profile_1s >= t_low)[0]
        idx_mid = np.where(profile_1s >= t_mid)[0]
        idx_high = np.where(profile_1s >= t_high)[0]

        time_low_start = f"{idx_low[0]//60:02d}:{idx_low[0]%60:02d}" if len(idx_low) > 0 else "--:--"
        time_mid_start = f"{idx_mid[0]//60:02d}:{idx_mid[0]%60:02d}" if len(idx_mid) > 0 else "--:--"
        time_high_start = f"{idx_high[0]//60:02d}:{idx_high[0]%60:02d}" if len(idx_high) > 0 else "--:--"

        # Total duration spent above bands
        dur_low_s = int(np.sum(profile_1s >= t_low))
        dur_mid_s = int(np.sum(profile_1s >= t_mid))
        dur_high_s = int(np.sum(profile_1s >= t_high))

        # Equivalent Time at Mid (Reference) Temperature:
        # EqTime = integral( exp((T - T_mid) / k) dt ) in minutes
        eq_weights = np.exp((profile_1s[profile_1s >= t_mid] - t_mid) / self.arrhenius_k)
        equiv_time_min = float(round(np.sum(eq_weights) * dt_min, 2)) if len(eq_weights) > 0 else 0.0
        equiv_time_mmss = f"{int(equiv_time_min):02d}:{int((equiv_time_min % 1) * 60):02d}"

        # Cumulative Thermal Dose (degree-seconds above ambient)
        ambient = 35.0
        cumulative_deg_s = float(round(np.sum(np.maximum(profile_1s - ambient, 0.0)), 1))

        # Maximum heating ramp rate (°C/sec over 30s rolling window)
        window = 30
        if T > window:
            diffs = (profile_1s[window:] - profile_1s[:-window]) / float(window)
            max_ramp_rate = float(round(np.max(diffs), 2))
        else:
            max_ramp_rate = 0.0

        return {
            "peak_temp_C": peak_temp,
            "peak_time_mmss": peak_time_mmss,
            "peak_time_s": peak_time_s,
            "cure_index": cure_index,
            "time_above_cure_min": time_above_cure_min,
            "equiv_time_min": equiv_time_min,
            "equiv_time_mmss": equiv_time_mmss,
            "time_low_start": time_low_start,
            "time_mid_start": time_mid_start,
            "time_high_start": time_high_start,
            "duration_low_min": round(dur_low_s / 60.0, 2),
            "duration_mid_min": round(dur_mid_s / 60.0, 2),
            "duration_high_min": round(dur_high_s / 60.0, 2),
            "max_ramp_rate_C_s": max_ramp_rate,
            "cumulative_deg_s": cumulative_deg_s,
        }
