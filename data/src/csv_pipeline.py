"""
Stellantis Virtual EMT — CSV Data Ingestion, Goal Comparison & Validation Pipeline
Parses:
  1. Trial Sensor & Operational Telemetry CSV
  2. Standard Goal Benchmark CSV
  3. Combined Oven & Vehicle Parameters CSV
Performs dynamic zone detection and validates trial curves against goal curves for GO/NG verdict.
"""

import io
import csv
import numpy as np
import pandas as pd
from typing import Dict, Any, Union, Optional
from scipy.interpolate import interp1d

from src.zone_detector import ZoneDetector
from src.cure_kinetics import CureKineticsEngine

class CSVPipeline:
    """
    End-to-end pipeline for CSV-driven Virtual EMT validation.
    """
    def __init__(self):
        self.zone_detector = ZoneDetector()
        self.kinetics_engine = CureKineticsEngine()

    def parse_sensor_csv(self, file_or_content: Union[str, bytes, io.StringIO]) -> Dict[str, Any]:
        """
        Parse Trial or Standard Goal sensor telemetry CSV.

        Expected Columns:
          timestamp, temperature_1..temperature_12, gas_pressure, conveyor_speed,
          fan_speed, burner_state, damper_opening, exhaust_fan_speed, vehicle_loading
        """
        if isinstance(file_or_content, bytes):
            text = file_or_content.decode('utf-8')
            df = pd.read_csv(io.StringIO(text))
        elif isinstance(file_or_content, io.StringIO):
            df = pd.read_csv(file_or_content)
        elif isinstance(file_or_content, str):
            # Check if file path or raw CSV string
            if '\n' in file_or_content or ',' in file_or_content:
                df = pd.read_csv(io.StringIO(file_or_content))
            else:
                df = pd.read_csv(file_or_content)
        else:
            raise ValueError("Unsupported input format for sensor CSV.")

        # Clean column names (strip whitespace and lowercase)
        df.columns = [c.strip().lower() for c in df.columns]

        # Convert timestamp to seconds
        time_s = []
        for val in df['timestamp']:
            val_str = str(val).strip()
            if ':' in val_str:
                parts = val_str.split(':')
                if len(parts) == 2:
                    sec = float(parts[0]) * 60 + float(parts[1])
                elif len(parts) == 3:
                    sec = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                else:
                    sec = float(parts[0])
            else:
                sec = float(val_str)
            time_s.append(sec)

        time_arr = np.array(time_s, dtype=float)

        # Extract 12 sensor temperature columns
        temp_cols = [f"temperature_{i}" for i in range(1, 13)]
        sensors_dict = {}
        for col in temp_cols:
            if col in df.columns:
                sensors_dict[col] = df[col].astype(float).values
            else:
                # Fallback if sensor column missing
                sensors_dict[col] = np.full_like(time_arr, 25.0)

        # Mean temperature across all 12 sensors
        sensor_matrix = np.array([sensors_dict[c] for c in temp_cols])
        mean_temp = np.mean(sensor_matrix, axis=0)

        # Extract operational SCADA features (means/last states)
        ops = {
            "gas_pressure": float(df['gas_pressure'].mean()) if 'gas_pressure' in df.columns else 50.0,
            "conveyor_speed": float(df['conveyor_speed'].mean()) if 'conveyor_speed' in df.columns else 2.20,
            "fan_speed": float(df['fan_speed'].mean()) if 'fan_speed' in df.columns else 85.0,
            "burner_state": int(df['burner_state'].min()) if 'burner_state' in df.columns else 1,
            "damper_opening": float(df['damper_opening'].mean()) if 'damper_opening' in df.columns else 50.0,
            "exhaust_fan_speed": float(df['exhaust_fan_speed'].mean()) if 'exhaust_fan_speed' in df.columns else 75.0,
            "vehicle_loading": int(df['vehicle_loading'].median()) if 'vehicle_loading' in df.columns else 5,
        }

        return {
            "time_s": time_arr,
            "mean_temperature": mean_temp,
            "sensors": sensors_dict,
            "sensor_matrix": sensor_matrix,
            "operational_params": ops,
            "row_count": len(df),
            "total_time_s": float(time_arr[-1]) if len(time_arr) > 0 else 2400.0,
        }

    def parse_config_csv(self, file_or_content: Union[str, bytes, io.StringIO]) -> Dict[str, Any]:
        """
        Parse Combined Oven & Vehicle Parameters CSV.
        """
        if isinstance(file_or_content, bytes):
            text = file_or_content.decode('utf-8')
            df = pd.read_csv(io.StringIO(text))
        elif isinstance(file_or_content, io.StringIO):
            df = pd.read_csv(file_or_content)
        elif isinstance(file_or_content, str):
            if '\n' in file_or_content or ',' in file_or_content:
                df = pd.read_csv(io.StringIO(file_or_content))
            else:
                df = pd.read_csv(file_or_content)
        else:
            raise ValueError("Unsupported input format for configuration CSV.")

        df.columns = [c.strip().lower() for c in df.columns]
        row = df.iloc[0].to_dict()

        return {
            "process_purpose": str(row.get("process_purpose", "ED Oven")).strip(),
            "total_time_s": float(row.get("total_time_s", 2400)),
            "cure_threshold": float(row.get("cure_threshold", 165.0)),
            "target_peak_min": float(row.get("target_peak_min", 185.0)),
            "target_peak_max": float(row.get("target_peak_max", 205.0)),
            "cure_index_ok": float(row.get("cure_index_ok", 22.0)),
            "cure_time_min_ok": float(row.get("cure_time_min_ok", 12.0)),
            "zone_1_setpoint": float(row.get("zone_1_setpoint_entry_ramp", 140.0)),
            "zone_2_setpoint": float(row.get("zone_2_setpoint_preheat", 175.0)),
            "zone_3_setpoint": float(row.get("zone_3_setpoint_soak_in", 190.0)),
            "zone_4_setpoint": float(row.get("zone_4_setpoint_cure_hold", 190.0)),
            "zone_5_setpoint": float(row.get("zone_5_setpoint_cooling_exit", 180.0)),
            "critical_band_low": float(row.get("critical_band_low", 150.0)),
            "critical_band_mid": float(row.get("critical_band_mid", 165.0)),
            "critical_band_high": float(row.get("critical_band_high", 185.0)),
            "body_platform_name": str(row.get("body_platform_name", "CC21")).strip(),
            "relative_mass_factor": float(row.get("relative_mass_factor", 1.0)),
            "thermal_inertia_lag": float(row.get("thermal_inertia_lag", 0.0)),
            "peak_temp_offset": float(row.get("peak_temp_offset", 0.0)),
            "body_construction_note": str(row.get("body_construction_note", "Lightweight sheet")).strip(),
        }

    def validate_trial_against_goal(
        self,
        trial_data: Dict[str, Any],
        goal_data: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate Trial sensor curves against Standard Goal benchmark curves
        and evaluate zone-by-zone compliance according to the combined config.
        """
        t_trial = trial_data["time_s"]
        trial_mean = trial_data["mean_temperature"]
        trial_matrix = trial_data["sensor_matrix"]

        t_goal = goal_data["time_s"]
        goal_mean = goal_data["mean_temperature"]

        cure_th = config["cure_threshold"]
        target_peak_min = config["target_peak_min"]
        target_peak_max = config["target_peak_max"]
        target_ci = config["cure_index_ok"]
        target_time_min = config["cure_time_min_ok"]

        # 1. Automatic Zone Detection on Trial Data & Standard Goal Data
        trial_zones_info = self.zone_detector.detect_zones(
            time_s=t_trial,
            mean_temperature=trial_mean,
            cure_threshold=cure_th,
            target_peak=(target_peak_min + target_peak_max) / 2.0
        )

        goal_zones_info = self.zone_detector.detect_zones(
            time_s=t_goal,
            mean_temperature=goal_mean,
            cure_threshold=cure_th,
            target_peak=(target_peak_min + target_peak_max) / 2.0
        )

        # 2. Interpolate Goal Curve to Trial Time Axis for Precise Deviation Comparison
        f_goal = interp1d(t_goal, goal_mean, kind="linear", fill_value="extrapolate")
        goal_interp = f_goal(t_trial)

        # Guard bands (+/- 8°C from goal mean)
        upper_envelope = goal_interp + 8.0
        lower_envelope = goal_interp - 8.0

        # Point-wise deviation
        abs_dev = np.abs(trial_mean - goal_interp)
        mean_dev = float(round(np.mean(abs_dev), 2))
        max_dev = float(round(np.max(abs_dev), 2))

        # 3. Continuous 1-Second Grid Resampling for Interval Invariance (1s to 60s)
        total_time = float(t_trial[-1] if len(t_trial) > 0 else 2400.0)
        grid_time = np.arange(0, int(total_time) + 1, 1.0)
        dt_min = 1.0 / 60.0

        sensor_audits = []
        sensor_pass_count = 0
        all_cis = []
        all_peaks = []
        all_time_above = []
        grid_sensor_matrix = []

        for i in range(12):
            s_name = f"temperature_{i+1}"
            raw_curve = trial_matrix[i]
            
            # Resample onto 1s continuous grid if raw intervals are > 1.2s
            if len(t_trial) > 1 and ((t_trial[1] - t_trial[0]) > 1.2 or len(t_trial) < 1000):
                f_sens = interp1d(t_trial, raw_curve, kind="linear", fill_value="extrapolate")
                s_curve = f_sens(grid_time)
            else:
                s_curve = raw_curve
            
            grid_sensor_matrix.append(s_curve)

            s_peak = float(round(np.max(s_curve), 1))
            s_peak_idx = int(np.argmax(s_curve))
            s_peak_time_s = float(grid_time[s_peak_idx]) if len(grid_time) == len(s_curve) else float(t_trial[s_peak_idx])

            # Arrhenius Kinetics on 1-second continuous grid
            above = s_curve >= cure_th
            if np.any(above):
                weights = np.exp((s_curve[above] - cure_th) / 12.0)
                ci_val = float(round(np.sum(weights) * dt_min, 1))
                t_above_min = float(round(np.sum(above) * dt_min, 2))
            else:
                ci_val = 0.0
                t_above_min = 0.0

            all_cis.append(ci_val)
            all_peaks.append(s_peak)
            all_time_above.append(t_above_min)

            # Check individual pass/fail
            peak_pass = (target_peak_min - 8.0) <= s_peak <= (target_peak_max + 8.0)
            ci_pass = (ci_val >= target_ci * 0.80)
            time_pass = (t_above_min >= target_time_min * 0.80)
            sensor_ok = peak_pass and ci_pass and time_pass

            if sensor_ok:
                sensor_pass_count += 1

            reasons = []
            if not peak_pass: reasons.append(f"Peak {s_peak}°C out of [{target_peak_min-8:.0f} - {target_peak_max+8:.0f}°C]")
            if not ci_pass: reasons.append(f"CI {ci_val} < {target_ci*0.8:.1f}")
            if not time_pass: reasons.append(f"Cure time {t_above_min}m < {target_time_min*0.8:.1f}m")

            # Calculate goal matching curve for this sensor
            goal_raw = goal_data["sensors"].get(s_name, goal_mean)
            f_goal_s = interp1d(t_goal, goal_raw, kind="linear", fill_value="extrapolate")
            g_curve = f_goal_s(grid_time)
            
            goal_peak = float(round(np.max(g_curve), 1))
            delta_peak = float(round(s_peak - goal_peak, 1))

            g_above = g_curve >= cure_th
            if np.any(g_above):
                g_weights = np.exp((g_curve[g_above] - cure_th) / 12.0)
                g_ci_val = float(round(np.sum(g_weights) * dt_min, 1))
            else:
                g_ci_val = 0.0

            sensor_audits.append({
                "sensor": f"Sensor S{i+1}",
                "channel": s_name,
                "peak_temp_C": s_peak,
                "goal_peak_temp_C": goal_peak,
                "delta_peak_C": delta_peak,
                "peak_time_s": s_peak_time_s,
                "peak_time_mmss": self._to_mmss(s_peak_time_s),
                "cure_index": ci_val,
                "goal_cure_index": g_ci_val,
                "delta_cure_index": float(round(ci_val - g_ci_val, 1)),
                "time_above_cure_min": t_above_min,
                "status": "PASS" if sensor_ok else "FAIL",
                "failure_reasons": reasons
            })

        # 4. Whole-Body Statistics
        min_peak = float(round(min(all_peaks), 1))
        max_peak = float(round(max(all_peaks), 1))
        spread = float(round(max_peak - min_peak, 1))
        min_ci = float(round(min(all_cis), 1))
        mean_ci = float(round(np.mean(all_cis), 1))

        # 5. GO / NG Physical Rule Violations Check
        violations = []
        if min_peak < (target_peak_min - 10.0):
            violations.append(f"Under-temperature: minimum peak ({min_peak}°C) is below allowable lower limit ({target_peak_min-10:.0f}°C).")
        if max_peak > (target_peak_max + 12.0):
            violations.append(f"Overcure risk: maximum peak ({max_peak}°C) exceeds paint burning threshold ({target_peak_max+12:.0f}°C).")
        if min_ci < (target_ci * 0.65):
            violations.append(f"Deficient chemical cure: min Arrhenius CI is {min_ci} (required min {target_ci*0.65:.1f}).")
        if spread > 25.0:
            violations.append(f"Thermal gradient violation: cross-body spread is {spread}°C (maximum allowable 25.0°C). Airflow imbalance.")
        if sensor_pass_count < 8:
            violations.append(f"Insufficient sensor pass count: only {sensor_pass_count}/12 passed (minimum 8 required).")

        # Operational anomalies check
        ops = trial_data.get("operational_params", {})
        if ops.get("burner_state", 1) == 0:
            violations.append("Operational Fault: Burner offline (Flameout / Trip).")
        if ops.get("gas_pressure", 50.0) < 38.0:
            violations.append(f"Operational Warning: Gas pressure low ({ops.get('gas_pressure'):.1f} mbar < 38 mbar).")
        if ops.get("conveyor_speed", 2.20) > 2.50:
            violations.append(f"Operational Fault: Conveyor speed excessive ({ops.get('conveyor_speed'):.2f} m/min > 2.50 m/min).")

        is_pass = (len(violations) == 0)
        verdict = "GO (OK)" if is_pass else "NG (NO-GO)"

        # 6. Cure Quality Index (CQI: 0 - 100%)
        # Score components:
        # - Deviation from Standard Goal: 30 pts
        # - Cure Index Margin: 35 pts
        # - Thermal Uniformity: 20 pts
        # - Peak Centering: 15 pts
        cqi_dev = max(30.0 - (mean_dev * 2.5), 0.0)
        cqi_ci  = min(35.0 * (min_ci / max(target_ci, 1.0)), 35.0)
        cqi_uni = max(20.0 - max(spread - 12.0, 0.0) * 1.5, 0.0)
        center_target = (target_peak_min + target_peak_max) / 2.0
        cqi_pmt = max(15.0 - (abs(np.mean(all_peaks) - center_target) * 1.2), 0.0)
        cqi_score = float(round(cqi_dev + cqi_ci + cqi_uni + cqi_pmt, 1))

        quality_tier = "GOLD TIER" if (is_pass and cqi_score >= 88.0) else ("SILVER TIER" if is_pass else "PROCESS REJECT")

        # 7. Detected Zone Comparison Table (Trial vs Standard Goal)
        zone_comparison_table = []
        for i in range(5):
            tz = trial_zones_info["zones"][i]
            gz = goal_zones_info["zones"][i]
            z_pass = (abs(tz["peak_temp_C"] - gz["peak_temp_C"]) <= 12.0) and is_pass
            zone_comparison_table.append({
                "zone_id": tz["zone_id"],
                "name": tz["name"],
                "stage": tz["stage"],
                "trial_timing": f"{tz['start_mmss']} – {tz['end_mmss']}",
                "trial_duration": f"{tz['duration_s']:.0f}s",
                "goal_timing": f"{gz['start_mmss']} – {gz['end_mmss']}",
                "goal_duration": f"{gz['duration_s']:.0f}s",
                "trial_peak_C": tz["peak_temp_C"],
                "goal_peak_C": gz["peak_temp_C"],
                "delta_peak_C": round(tz["peak_temp_C"] - gz["peak_temp_C"], 1),
                "status": "PASS" if z_pass else ("FAIL" if not is_pass else "WARN"),
            })

        # 8. Time Series Data for Visual Chart
        # Format zone composite curves + sensor curves + goal curve
        chart_series = {
            "time_s": t_trial.tolist(),
            "trial_mean": trial_mean.tolist(),
            "goal_mean": goal_interp.tolist(),
            "upper_envelope": upper_envelope.tolist(),
            "lower_envelope": lower_envelope.tolist(),
        }
        for i in range(1, 13):
            col = f"temperature_{i}"
            if col in trial_data["sensors"]:
                chart_series[col] = trial_data["sensors"][col].tolist()
            if col in goal_data["sensors"]:
                f_goal_s = interp1d(t_goal, goal_data["sensors"][col], kind="linear", fill_value="extrapolate")
                chart_series[f"goal_{col}"] = f_goal_s(t_trial).tolist()
            else:
                chart_series[f"goal_{col}"] = goal_interp.tolist()

        return {
            "verdict": verdict,
            "is_pass": is_pass,
            "final_status": "CERTIFIED PASS (OK)" if is_pass else "PROCESS REJECT (NG)",
            "quality_tier": quality_tier,
            "cqi_score": cqi_score,
            "violations": violations,
            "stats": {
                "min_peak_C": min_peak,
                "max_peak_C": max_peak,
                "thermal_spread_C": spread,
                "min_cure_index": min_ci,
                "mean_cure_index": mean_ci,
                "mean_deviation_from_goal_C": mean_dev,
                "max_deviation_from_goal_C": max_dev,
                "sensor_pass_count": sensor_pass_count,
                "total_sensors": 12,
            },
            "trial_zones": trial_zones_info,
            "goal_zones": goal_zones_info,
            "zone_comparison_table": zone_comparison_table,
            "sensor_audit_table": sensor_audits,
            "chart_series": chart_series,
            "config_meta": config,
        }

    def _to_mmss(self, seconds: float) -> str:
        sec = int(round(seconds))
        m = sec // 60
        s = sec % 60
        return f"{m:02d}:{s:02d}"
