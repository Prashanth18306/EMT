"""
Stellantis Virtual EMT — Automatic Paint Oven Zone Detection Engine
Automatically segments continuous 12-sensor thermal profiles into 5 process zones:
  Zone 1: Entry Ramp (Rapid temperature rise from ambient)
  Zone 2: Preheat (Heating rate tapering into pre-soak knee point)
  Zone 3: Soak In (Crossing into chemical cure activation threshold)
  Zone 4: Peak Cure Hold (Maximum metal temperature plateau)
  Zone 5: Cooling Exit (Rapid thermal decline in cooling chamber)
Supports arbitrary sampling intervals from 1 second up to 1 minute (1s to 60s).
"""

import numpy as np
from scipy.interpolate import interp1d
from typing import Dict, Any, List, Tuple

class ZoneDetector:
    """
    Physics-based thermal zone detection engine for continuous automotive paint ovens.
    Fully invariant to sampling intervals (1s to 60s).
    """
    def __init__(self):
        pass

    def detect_zones(
        self,
        time_s: np.ndarray,
        mean_temperature: np.ndarray,
        cure_threshold: float = 165.0,
        target_peak: float = 195.0,
        conveyor_speed_m_min: float = 2.20
    ) -> Dict[str, Any]:
        """
        Detect the 5 process zones from a temperature profile with arbitrary time intervals (1s to 60s).

        Args:
            time_s: 1D array of timestamps in seconds.
            mean_temperature: 1D array of mean sensor temperatures (°C).
            cure_threshold: Temperature at which cross-linking begins (°C).
            target_peak: Expected nominal peak temperature (°C).
            conveyor_speed_m_min: Conveyor speed in m/min for physical cross-verification.

        Returns:
            Dict containing detected zone boundaries, timestamps (seconds & mm:ss),
            durations, and zone-wise statistics.
        """
        total_time = float(time_s[-1] if len(time_s) > 0 else 2400.0)

        if len(time_s) < 5 or total_time < 60:
            return self._fallback_zones(total_time)

        # 1. Continuous 1-Second Grid Resampling
        # Ensures exact derivative behavior whether raw CSV was 1s, 5s, 15s, or 60s
        if len(time_s) > 1 and ((time_s[1] - time_s[0]) > 1.2 or len(time_s) < 1000):
            interp_func = interp1d(time_s, mean_temperature, kind='linear', fill_value='extrapolate')
            grid_time = np.arange(0, int(total_time) + 1, 1.0)
            grid_temp = interp_func(grid_time)
        else:
            grid_time = time_s
            grid_temp = mean_temperature

        N = len(grid_time)

        # 2. Gaussian / Moving-Average Smoothing on 1-Second Grid (window: 25 seconds)
        w_size = 25
        kernel = np.ones(w_size) / w_size
        smoothed = np.convolve(grid_temp, kernel, mode='same')

        # 3. Time-Normalized 1st and 2nd Derivatives (°C/second and °C/second^2)
        dT_dt = np.gradient(smoothed, grid_time)
        d2T_dt2 = np.gradient(dT_dt, grid_time)

        # 4. Detect Maximum Peak (Center of Zone 4)
        peak_idx = int(np.argmax(smoothed))
        peak_temp = float(smoothed[peak_idx])
        peak_time = float(grid_time[peak_idx])

        # 5. Detect Zone 5 (Cooling Exit):
        # Starts after the peak when temperature drops consistently (dT/dt < -0.04 °C/s)
        post_peak_indices = np.where((grid_time > peak_time) & (dT_dt < -0.04))[0]
        if len(post_peak_indices) > 0:
            z5_start_idx = int(post_peak_indices[0])
        else:
            # Fallback based on conveyor speed and physical oven zone 5 entry (~80% transit)
            speed_ratio = 2.20 / max(conveyor_speed_m_min, 1.0)
            z5_start_idx = min(int(N * 0.82), peak_idx + int(300 * speed_ratio))

        z5_start_time = float(grid_time[z5_start_idx])

        # 6. Detect Zone 3 (Soak In) Entry:
        # Crosses into active chemical curing window (cure_threshold - 5.0 °C)
        soak_thresh = cure_threshold - 5.0
        cure_cross_indices = np.where((grid_time < peak_time) & (smoothed >= soak_thresh))[0]
        if len(cure_cross_indices) > 0:
            z3_start_idx = int(cure_cross_indices[0])
        else:
            # If threshold was never reached (e.g. burner trip), detect inflection at 75% of reached peak
            sub_thresh = min(soak_thresh, peak_temp * 0.75)
            cross = np.where((grid_time < peak_time) & (smoothed >= sub_thresh))[0]
            z3_start_idx = int(cross[0]) if len(cross) > 0 else int(peak_idx * 0.6)

        z3_start_time = float(grid_time[z3_start_idx])

        # 7. Detect Zone 1 (Entry Ramp) End / Zone 2 (Preheat) Start:
        # Knee point where heating acceleration ceases: d2T_dt2 reaches local minimum
        pre_soak_limit = max(int(z3_start_idx * 0.85), 30)
        pre_soak_slice = slice(20, pre_soak_limit)
        knee_candidates = np.where(d2T_dt2[pre_soak_slice] < 0)[0]
        if len(knee_candidates) > 0:
            z1_end_idx = int(knee_candidates[0] + 20)
        else:
            z1_end_idx = int(z3_start_idx * 0.45)

        z1_end_time = float(grid_time[z1_end_idx])

        # 8. Physical Boundary Constraints & Monotonicity
        if not (0 < z1_end_time < z3_start_time < z5_start_time < total_time):
            z1_end_time = min(z1_end_time, total_time * 0.22)
            z3_start_time = max(z1_end_time + 60.0, min(z3_start_time, total_time * 0.55))
            z5_start_time = max(z3_start_time + 120.0, min(z5_start_time, total_time * 0.85))

        # 9. Zone 4 (Peak Cure Hold) Entry:
        # Plateau region where temperature enters within 3.5°C of peak and slope flattens
        near_peak_indices = np.where((grid_time >= z3_start_time) & (grid_time <= z5_start_time) & (smoothed >= peak_temp - 3.5))[0]
        if len(near_peak_indices) > 0:
            z4_start_time = float(grid_time[near_peak_indices[0]])
        else:
            z4_start_time = float(z3_start_time + (z5_start_time - z3_start_time) * 0.4)

        zones = [
            {
                "zone_id": 1,
                "name": "Zone 1 (Entry Ramp)",
                "short_name": "Zone 1",
                "stage": "Entry Ramp",
                "start_s": 0.0,
                "end_s": round(z1_end_time, 1),
                "duration_s": round(z1_end_time, 1),
                "start_mmss": "00:00",
                "end_mmss": self._to_mmss(z1_end_time),
                "color": "#00E5FF",
            },
            {
                "zone_id": 2,
                "name": "Zone 2 (Preheat)",
                "short_name": "Zone 2",
                "stage": "Preheat",
                "start_s": round(z1_end_time, 1),
                "end_s": round(z3_start_time, 1),
                "duration_s": round(z3_start_time - z1_end_time, 1),
                "start_mmss": self._to_mmss(z1_end_time),
                "end_mmss": self._to_mmss(z3_start_time),
                "color": "#2979FF",
            },
            {
                "zone_id": 3,
                "name": "Zone 3 (Soak In)",
                "short_name": "Zone 3",
                "stage": "Soak & Cross-link",
                "start_s": round(z3_start_time, 1),
                "end_s": round(z4_start_time, 1),
                "duration_s": round(z4_start_time - z3_start_time, 1),
                "start_mmss": self._to_mmss(z3_start_time),
                "end_mmss": self._to_mmss(z4_start_time),
                "color": "#E040FB",
            },
            {
                "zone_id": 4,
                "name": "Zone 4 (Cure Hold)",
                "short_name": "Zone 4",
                "stage": "Peak Cure Hold",
                "start_s": round(z4_start_time, 1),
                "end_s": round(z5_start_time, 1),
                "duration_s": round(z5_start_time - z4_start_time, 1),
                "start_mmss": self._to_mmss(z4_start_time),
                "end_mmss": self._to_mmss(z5_start_time),
                "color": "#FF1744",
            },
            {
                "zone_id": 5,
                "name": "Zone 5 (Cooling Exit)",
                "short_name": "Zone 5",
                "stage": "Cooling Exit",
                "start_s": round(z5_start_time, 1),
                "end_s": round(total_time, 1),
                "duration_s": round(total_time - z5_start_time, 1),
                "start_mmss": self._to_mmss(z5_start_time),
                "end_mmss": self._to_mmss(total_time),
                "color": "#00E676",
            },
        ]

        # Compute zone metrics
        for z in zones:
            mask = (grid_time >= z["start_s"]) & (grid_time <= z["end_s"])
            if np.any(mask):
                z_temps = grid_temp[mask]
                z["mean_temp_C"] = float(round(np.mean(z_temps), 1))
                z["peak_temp_C"] = float(round(np.max(z_temps), 1))
                z["min_temp_C"]  = float(round(np.min(z_temps), 1))
                z["time_above_cure_s"] = int(np.sum(z_temps >= cure_threshold))
            else:
                z["mean_temp_C"] = 0.0
                z["peak_temp_C"] = 0.0
                z["min_temp_C"]  = 0.0
                z["time_above_cure_s"] = 0

        return {
            "total_time_s": total_time,
            "peak_temp_C": round(peak_temp, 1),
            "peak_time_s": round(peak_time, 1),
            "peak_time_mmss": self._to_mmss(peak_time),
            "zones": zones,
            "transition_points_s": [0.0, round(z1_end_time, 1), round(z3_start_time, 1), round(z4_start_time, 1), round(z5_start_time, 1), round(total_time, 1)]
        }

    def _fallback_zones(self, total_time: float) -> Dict[str, Any]:
        """Fallback zone distribution if curve length is insufficient."""
        t1 = round(total_time * 0.20, 1)
        t2 = round(total_time * 0.50, 1)
        t3 = round(total_time * 0.65, 1)
        t4 = round(total_time * 0.80, 1)
        return {
            "total_time_s": total_time,
            "peak_temp_C": 0.0,
            "peak_time_s": t3,
            "peak_time_mmss": self._to_mmss(t3),
            "zones": [
                {"zone_id": 1, "name": "Zone 1 (Entry Ramp)",   "start_s": 0.0, "end_s": t1, "start_mmss": "00:00", "end_mmss": self._to_mmss(t1), "color": "#00E5FF", "peak_temp_C": 0.0},
                {"zone_id": 2, "name": "Zone 2 (Preheat)",      "start_s": t1,  "end_s": t2, "start_mmss": self._to_mmss(t1), "end_mmss": self._to_mmss(t2), "color": "#2979FF", "peak_temp_C": 0.0},
                {"zone_id": 3, "name": "Zone 3 (Soak In)",      "start_s": t2,  "end_s": t3, "start_mmss": self._to_mmss(t2), "end_mmss": self._to_mmss(t3), "color": "#E040FB", "peak_temp_C": 0.0},
                {"zone_id": 4, "name": "Zone 4 (Cure Hold)",    "start_s": t3,  "end_s": t4, "start_mmss": self._to_mmss(t3), "end_mmss": self._to_mmss(t4), "color": "#FF1744", "peak_temp_C": 0.0},
                {"zone_id": 5, "name": "Zone 5 (Cooling Exit)", "start_s": t4,  "end_s": total_time, "start_mmss": self._to_mmss(t4), "end_mmss": self._to_mmss(total_time), "color": "#00E676", "peak_temp_C": 0.0},
            ],
            "transition_points_s": [0.0, t1, t2, t3, t4, total_time]
        }

    def _to_mmss(self, seconds: float) -> str:
        sec = int(round(seconds))
        m = sec // 60
        s = sec % 60
        return f"{m:02d}:{s:02d}"
