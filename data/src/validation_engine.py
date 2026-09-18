"""
Stellantis Virtual EMT — Phase 3: Multi-Criteria Physical Validation Engine
Evaluates tolerance envelopes, Peak Metal Temp (PMT), Arrhenius Cure Index, 
Thermal Uniformity, and Ramp Rates for ISO 12944 / VDA 621-415 compliance.
Synthesizes physics rules with AI machine learning verdict for Dual-Verification.
"""

import numpy as np
from scipy.interpolate import interp1d
from src.config import SENSORS, SENSOR_COLS, OVEN_SPECS, OVEN_ZONES
from src.standard_curve_library import StandardCurveLibrary
from src.cure_kinetics import CureKineticsEngine

class ValidationEngine:
    """
    Automotive Paint Shop Physical Quality Validation Engine.
    Performs multi-criteria compliance checking against golden reference envelopes
    and metallurgical / chemical curing standards.
    """
    def __init__(self, standard_library=None, kinetics_engine=None):
        self.std_lib = standard_library or StandardCurveLibrary()
        self.kinetics = kinetics_engine or CureKineticsEngine()

    def validate_curves(self, time_axis, sensor_curves, oven_type, vehicle_model="CC21", ai_verdict="OK", ai_confidence=95.0, plc_inputs=None):
        """
        Validate multi-sensor EMT temperature profiles against standards.

        Args:
            time_axis: 1D array of time stamps in seconds
            sensor_curves: dict mapping sensor_name/col -> 1D array, or 2D array (12, N_points)
            oven_type: 'ED' | 'SEALER' | 'TOPCOAT'
            vehicle_model: 'CC21' | 'CC31' | 'CC41' | 'CC51' | 'CC61'
            ai_verdict: 'OK' | 'NG' from Phase 2 model
            ai_confidence: confidence score of AI prediction (%)

        Returns:
            dict containing comprehensive compliance scorecard, sensor audit, 
            envelope tracking, and dual-verification decision.
        """
        spec = OVEN_SPECS.get(oven_type, OVEN_SPECS["ED"])
        total_time = spec["total_time_s"]
        ok_peak_range = spec["target_peak_ok"]
        target_ci = spec["cure_index_ok"]
        target_time_at_cure = spec["cure_time_min_ok"]

        # 1. Retrieve Golden Standard Curve & Envelopes
        std_info = self.std_lib.get_standard_curve(oven_type, vehicle_model)
        golden_time = std_info["time_s"]
        golden_temp = std_info["standard_temp_C"]
        upper_limit = std_info["upper_limit_C"]
        lower_limit = std_info["lower_limit_C"]

        # Interpolate golden curve to input time_axis if needed
        if len(time_axis) != len(golden_time):
            f_std = interp1d(golden_time, golden_temp, kind="linear", fill_value="extrapolate")
            f_upp = interp1d(golden_time, upper_limit, kind="linear", fill_value="extrapolate")
            f_low = interp1d(golden_time, lower_limit, kind="linear", fill_value="extrapolate")
            ref_temp = f_std(time_axis)
            ref_upper = f_upp(time_axis)
            ref_lower = f_low(time_axis)
        else:
            ref_temp = golden_temp
            ref_upper = upper_limit
            ref_lower = lower_limit

        # High-resolution 1-second time axis for kinetics integration
        t_1s = np.arange(0, total_time, 1)

        sensor_results = []
        envelope_violations = []
        all_peaks = []
        all_cis = []
        all_tcures = []
        envelope_errors = []

        # 2. Sensor-by-Sensor Compliance Audit across Oven Zones
        for s_idx, s in enumerate(SENSORS):
            s_name = s["name"]
            s_col  = s["col"]
            is_core = s.get("type") in ("cure_zone", "core")
            ci_relax = 1.0 if is_core else 0.80

            # Extract sensor curve
            if isinstance(sensor_curves, dict):
                curve_pts = sensor_curves.get(s_col, sensor_curves.get(s_name))
            else:
                curve_pts = sensor_curves[s_idx]

            # Reconstruct continuous 1s profile
            f_curve = interp1d(time_axis, curve_pts, kind="linear", fill_value="extrapolate")
            prof_1s = f_curve(t_1s)

            # Compute chemical kinetics
            kin = self.kinetics.compute_sensor_kinetics(prof_1s, oven_type)
            peak_temp = kin["peak_temp_C"]
            cure_index = kin["cure_index"]
            t_above_min = kin["time_above_cure_min"]

            all_peaks.append(peak_temp)
            all_cis.append(cure_index)
            all_tcures.append(t_above_min)

            # Tolerance Envelope Tracking
            # Compare at time_axis points
            over_upper = np.maximum(curve_pts - ref_upper, 0.0)
            under_lower = np.maximum(ref_lower - curve_pts, 0.0)
            dev_mag = np.maximum(over_upper, under_lower)
            
            time_out_s = int(np.sum(dev_mag > 0.5) * (total_time / len(time_axis)))
            max_dev_C  = float(round(np.max(dev_mag), 1))
            mae_from_golden = float(round(np.mean(np.abs(curve_pts - ref_temp)), 2))
            envelope_errors.append(mae_from_golden)

            # Pass/Fail Criteria for individual sensor
            peak_ok = (peak_temp >= ok_peak_range[0] - 12.0) and (peak_temp <= ok_peak_range[1] + 10.0)
            ci_ok   = (cure_index >= target_ci * ci_relax)
            time_ok = (t_above_min >= target_time_at_cure * ci_relax)
            env_ok  = (max_dev_C <= 12.0) and (time_out_s <= total_time * 0.10)

            sensor_pass = peak_ok and ci_ok and time_ok and env_ok

            fail_reasons_s = []
            if not peak_ok:
                fail_reasons_s.append(f"Peak {peak_temp:.1f}°C out of range [{ok_peak_range[0]-12:.0f}-{ok_peak_range[1]+10:.0f}°C]")
            if not ci_ok:
                fail_reasons_s.append(f"Cure Index {cure_index:.1f} < threshold {target_ci*ci_relax:.1f}")
            if not time_ok:
                fail_reasons_s.append(f"Cure time {t_above_min:.1f}m < {target_time_at_cure*ci_relax:.1f}m")
            if not env_ok:
                fail_reasons_s.append(f"Envelope dev {max_dev_C:.1f}°C ({time_out_s}s out)")

            sensor_results.append({
                "sensor": s_name,
                "type": s["type"],
                "peak_temp_C": peak_temp,
                "peak_time": kin["peak_time_mmss"],
                "cure_index": cure_index,
                "time_above_cure_min": t_above_min,
                "equiv_time_min": kin["equiv_time_min"],
                "max_deviation_C": max_dev_C,
                "time_out_of_envelope_s": time_out_s,
                "mae_from_golden_C": mae_from_golden,
                "status": "PASS" if sensor_pass else "FAIL",
                "failure_reasons": fail_reasons_s,
                "max_ramp_rate": kin["max_ramp_rate_C_s"],
            })

            if not env_ok:
                envelope_violations.append(f"{s_name}: {max_dev_C:.1f}°C deviation for {time_out_s}s")

        # 3. Whole-Body Aggregate Checks
        max_peak = float(round(max(all_peaks), 1))
        min_peak = float(round(min(all_peaks), 1))
        spread   = float(round(max_peak - min_peak, 1))
        min_ci   = float(round(min(all_cis), 1))
        mean_ci  = float(round(np.mean(all_cis), 1))
        min_tcure = float(round(min(all_tcures), 1))
        mean_tcure = float(round(np.mean(all_tcures), 1))
        mean_mae_golden = float(round(np.mean(envelope_errors), 2))

        pass_count = sum(1 for s in sensor_results if s["status"] == "PASS")
        core_pass_count = sum(1 for s in sensor_results if s["status"] == "PASS" and s["type"] in ("cure_zone", "core"))

        # Global Physical Rules:
        # 1. At least 8 of 12 sensors must pass
        # 2. At least 5 of 6 cure zone sensors must pass
        # 3. Overall cross-zone temperature spread <= 25.0°C
        # 4. Max peak must not exceed upper safety threshold (overcure/burn risk)
        # 5. Min CI across monitored zones >= 15.0
        phys_violations = []
        if pass_count < 8:
            phys_violations.append(f"Insufficient sensor pass count: {pass_count}/12 passed (min 8 required).")
        if core_pass_count < 5:
            phys_violations.append(f"Cure zone sensors compromised: {core_pass_count}/6 cure zone sensors passed (min 5 required).")
        if spread > 25.0:
            phys_violations.append(f"Thermal spread excessive: {spread:.1f}°C across car body (max 25.0°C allowed). Airflow failure.")
        if max_peak > ok_peak_range[1] + 12.0:
            phys_violations.append(f"Overcure danger: peak temperature {max_peak:.1f}°C exceeds burn limit {ok_peak_range[1]+12:.1f}°C.")
        if min_ci < target_ci * 0.65:
            phys_violations.append(f"Severely deficient cure index: min CI is {min_ci:.1f} (absolute minimum {target_ci*0.65:.1f}).")

        physics_verdict = "OK" if len(phys_violations) == 0 else "NG"

        # 4. Cure Quality Index (CQI: 0 - 100%)
        # Score components:
        # - Envelope tracking: 25 pts (penalized by MAE from golden)
        # - Cure Index margin: 35 pts (rewarded if min_ci >= target_ci)
        # - Thermal uniformity: 25 pts (penalized if spread > 15°C)
        # - Peak centering: 15 pts (proximity to nominal peak)
        cqi_env = max(25.0 - (mean_mae_golden * 2.0), 0.0)
        cqi_ci  = min(35.0 * (min_ci / max(target_ci, 1.0)), 35.0)
        cqi_uni = max(25.0 - max(spread - 12.0, 0.0) * 1.8, 0.0)
        target_center = np.mean(ok_peak_range)
        peak_center_err = abs(np.mean(all_peaks) - target_center)
        cqi_pmt = max(15.0 - (peak_center_err * 1.2), 0.0)
        cqi_total = float(round(cqi_env + cqi_ci + cqi_uni + cqi_pmt, 1))

        # 5. Dual-Verification Synthesis
        if ai_verdict == "OK" and physics_verdict == "OK":
            final_status = "CERTIFIED PASS (OK)"
            quality_tier = "GOLD STANDARD" if cqi_total >= 85 else "STANDARD PASS"
            action_code = "RELEASE_TO_NEXT_PROCESS"
            remedy_summary = "Cycle meets all paint curing standards. Car body cleared for downstream operations."
        elif ai_verdict == "NG" and physics_verdict == "NG":
            final_status = "REJECTED (NG)"
            quality_tier = "CRITICAL DEFECT"
            action_code = "HOLD_FOR_INSPECTION_OR_REBAKE"
            remedy_summary = "Curing failure confirmed by both AI model and physical thermal envelopes. Route body to repair / rebake buffer."
        elif ai_verdict == "OK" and physics_verdict == "NG":
            final_status = "QUALITY WARNING (HOLD)"
            quality_tier = "BORDERLINE DRIFT"
            action_code = "ENGINEERING_REVIEW"
            remedy_summary = "AI predicted normal state, but physical standards detected localized thermal violations. Quality engineer sign-off required."
        else: # AI NG, Physics OK
            final_status = "EARLY WARNING ALERT"
            quality_tier = "PROCESS DEVIATION"
            action_code = "PREVENTIVE_MAINTENANCE"
            remedy_summary = "Physical cure criteria marginally passed, but AI detected early-stage equipment drift. Schedule preventive inspection."

        # 6. Zone-Wise Compliance Audit across 5 Process Zones
        zone_results = []
        for z in OVEN_ZONES:
            z_curves = []
            for c in z["sensor_cols"]:
                if isinstance(sensor_curves, dict):
                    c_data = sensor_curves.get(c)
                    if c_data is None:
                        for s in SENSORS:
                            if s["col"] == c and s["name"] in sensor_curves:
                                c_data = sensor_curves[s["name"]]
                                break
                else:
                    c_idx = SENSOR_COLS.index(c) if c in SENSOR_COLS else 0
                    c_data = sensor_curves[c_idx]
                if c_data is not None:
                    z_curves.append(np.array(c_data))

            if len(z_curves) > 0:
                z_mean_curve = np.mean(z_curves, axis=0)
            else:
                z_mean_curve = ref_temp.copy()

            f_z = interp1d(time_axis, z_mean_curve, kind="linear", fill_value="extrapolate")
            z_1s = f_z(t_1s)
            z_kin = self.kinetics.compute_sensor_kinetics(z_1s, oven_type)

            z_peak = z_kin["peak_temp_C"]
            z_ci = z_kin["cure_index"]
            z_tcure = z_kin["time_above_cure_min"]

            over_upp = np.maximum(z_mean_curve - ref_upper, 0.0)
            under_low = np.maximum(ref_lower - z_mean_curve, 0.0)
            z_dev = np.maximum(over_upp, under_low)
            z_max_dev = float(round(np.max(z_dev), 1))
            z_time_out_s = int(np.sum(z_dev > 0.5) * (total_time / len(time_axis)))

            is_cure = z["type"] in ("cure_zone", "core")

            # Rigorous physical and kinetic thresholds
            if is_cure:
                z_peak_ok = (z_peak >= ok_peak_range[0] - 5.0) and (z_peak <= ok_peak_range[1] + 5.0)
                z_ci_ok = (z_ci >= target_ci * 0.85)
                z_time_ok = (z_tcure >= target_time_at_cure * 0.85)
            else:
                z_peak_ok = (z_peak <= ok_peak_range[1] + 5.0)
                z_ci_ok = True
                z_time_ok = True

            z_env_ok = (z_max_dev <= 6.5) and (z_time_out_s <= total_time * 0.08)

            # Check individual sensors in this zone
            z_matching_sensors = [
                s for s in sensor_results 
                if any(c in z["sensor_cols"] for c in [sen["col"] for sen in SENSORS if sen["name"] == s["sensor"]])
            ]
            z_failed_sensors = [s for s in z_matching_sensors if s["status"] == "FAIL"]
            if len(z["sensor_cols"]) <= 2:
                z_sensors_ok = (len(z_failed_sensors) == 0)
            else:
                z_sensors_ok = (len(z_failed_sensors) <= 1)

            # Process parameters correlation (equipment trips, fan degradation, conveyor speed)
            plc = plc_inputs or {}
            fan_speed = float(plc.get("plc_fan_speed_pct", 85.0))
            burner_state = int(plc.get("plc_burner_state", 1))
            gas_pressure = float(plc.get("plc_gas_pressure_mbar", 50.0))
            conv_speed = float(plc.get("plc_conveyor_speed_m_min", 2.20))

            fail_reasons_z = []
            if not z_peak_ok:
                fail_reasons_z.append(f"Peak {z_peak:.1f}°C out of spec [{ok_peak_range[0]-5:.0f}-{ok_peak_range[1]+5:.0f}°C]")
            if not z_ci_ok:
                fail_reasons_z.append(f"Cure Index {z_ci:.1f} < threshold {target_ci*0.85:.1f}")
            if not z_time_ok:
                fail_reasons_z.append(f"Cure time {z_tcure:.1f}m < threshold {target_time_at_cure*0.85:.1f}m")
            if not z_env_ok:
                fail_reasons_z.append(f"Envelope dev {z_max_dev:.1f}°C ({z_time_out_s}s out of envelope)")
            if not z_sensors_ok:
                fail_reasons_z.append(f"{len(z_failed_sensors)} of {len(z_matching_sensors)} sensors failed: {', '.join(s['sensor'] for s in z_failed_sensors)}")

            # Equipment trip correlation:
            if burner_state == 0 and z["short_name"] in ("Zone 2", "Zone 3", "Zone 4"):
                fail_reasons_z.append("Burner flameout trip: heat supply offline")
            if gas_pressure < 40.0 and z["short_name"] in ("Zone 2", "Zone 3", "Zone 4"):
                fail_reasons_z.append(f"Gas pressure low ({gas_pressure:.1f} mbar < 40.0 mbar)")
            if fan_speed < 65.0 and z["short_name"] in ("Zone 2", "Zone 3", "Zone 4"):
                fail_reasons_z.append(f"Circulation fan starved ({fan_speed:.1f}% < 65.0%)")
            if conv_speed > 2.50:
                fail_reasons_z.append(f"Conveyor overspeed ({conv_speed:.2f} m/min > 2.50 m/min limit)")

            z_status = "PASS" if len(fail_reasons_z) == 0 else "FAIL"

            zone_results.append({
                "zone": z["name"],
                "sensor": z["name"],
                "short_name": z["short_name"],
                "stage": z["stage"],
                "type": z["stage"],
                "peak_temp_C": z_peak,
                "peak_time": z_kin["peak_time_mmss"],
                "cure_index": z_ci,
                "time_above_cure_min": z_tcure,
                "equiv_time_min": z_kin["equiv_time_min"],
                "max_deviation_C": z_max_dev,
                "time_out_of_envelope_s": z_time_out_s,
                "status": z_status,
                "failure_reasons": fail_reasons_z,
                "curve": z_mean_curve.tolist()
            })

        zone_pass_count = sum(1 for z in zone_results if z["status"] == "PASS")

        return {
            "oven_type": oven_type,
            "vehicle_model": vehicle_model,
            "final_status": final_status,
            "quality_tier": quality_tier,
            "action_code": action_code,
            "cure_quality_index_pct": cqi_total,
            "ai_verdict": ai_verdict,
            "ai_confidence_pct": ai_confidence,
            "physics_verdict": physics_verdict,
            "zone_pass_count": f"{zone_pass_count}/5",
            "sensor_pass_count": f"{zone_pass_count}/5",
            "core_pass_count": f"{core_pass_count}/6",
            "cross_body_spread_C": spread,
            "cross_zone_spread_C": spread,
            "peak_range_C": f"{min_peak:.1f}°C to {max_peak:.1f}°C",
            "cure_index_summary": f"Mean {mean_ci:.1f} (Min {min_ci:.1f})",
            "time_at_cure_summary": f"Mean {mean_tcure:.1f} min (Min {min_tcure:.1f} min)",
            "mean_envelope_mae_C": mean_mae_golden,
            "physics_violations": phys_violations,
            "remedy_summary": remedy_summary,
            "zone_audit_table": zone_results,
            "sensor_audit_table": zone_results,
            "individual_sensor_audit": sensor_results,
            "golden_curve_reference": {
                "time_s": golden_time.tolist(),
                "standard_temp_C": golden_temp.tolist(),
                "upper_limit_C": upper_limit.tolist(),
                "lower_limit_C": lower_limit.tolist(),
            }
        }
