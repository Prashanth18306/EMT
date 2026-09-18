"""
Stellantis Virtual EMT — Phase 2C: Root Cause Analysis & Prescriptive Maintenance Engine
Diagnoses equipment failure modes, identifies offending subsystems, 
and generates actionable maintenance recommendations.
"""

from src.config import OVEN_SPECS, NG_ROOT_CAUSE, NG_REMEDY

class RootCauseEngine:
    """
    Expert rule engine + feature attribution system for paint oven diagnostics.
    """
    def __init__(self):
        pass

    def diagnose(self, plc_dict, virtual_stats, ng_mode=None, ng_prob=0.0):
        """
        Diagnose potential causes and recommended corrective actions.
        
        Args:
            plc_dict: dict of operational parameters
            virtual_stats: dict of extracted curve features (peaks, CIs, spread)
            ng_mode: predicted failure mode string (or None)
            ng_prob: probability of NG (0.0 to 1.0)
            
        Returns:
            dict containing root cause, recommended remedy, subsystem attribution, and early warnings.
        """
        oven_type = plc_dict.get("oven_type", "ED")
        spec = OVEN_SPECS.get(oven_type, OVEN_SPECS["ED"])
        ok_range = spec["target_peak_ok"]
        min_ci_ok = spec["cure_index_ok"]
        min_t_ok  = spec["cure_time_min_ok"]

        warnings = []
        subsystems = {
            "Burner & Gas Train": 0.0,
            "Conveyor & Drive System": 0.0,
            "Circulation Fans & Nozzles": 0.0,
            "Intake Damper & Filters": 0.0,
            "Oven Recipe & PLC Controller": 0.0,
        }

        # 1. Check Peak Temperature
        max_p = virtual_stats.get("summary_max_peak", 0.0)
        min_p = virtual_stats.get("summary_min_peak", 0.0)
        spread = virtual_stats.get("summary_spread", 0.0)

        if min_p < ok_range[0] - 10:
            warnings.append(f"Under-temperature detected: min sensor peak ({min_p:.1f}°C) is below allowable ({ok_range[0]-10:.1f}°C)")
            subsystems["Burner & Gas Train"] += 35.0
            subsystems["Oven Recipe & PLC Controller"] += 15.0

        if max_p > ok_range[1] + 10:
            warnings.append(f"Over-temperature risk: max sensor peak ({max_p:.1f}°C) exceeds upper limit ({ok_range[1]+10:.1f}°C)")
            subsystems["Burner & Gas Train"] += 25.0
            subsystems["Oven Recipe & PLC Controller"] += 25.0

        # 2. Check Temperature Spread (Airflow uniformity)
        if spread > 22.0:
            warnings.append(f"Airflow imbalance: temperature spread across car body is {spread:.1f}°C (max allowable: 22.0°C)")
            subsystems["Circulation Fans & Nozzles"] += 45.0

        # 3. Check Cure Index
        min_ci = virtual_stats.get("summary_min_ci", 0.0)
        if min_ci < min_ci_ok * 0.8:
            warnings.append(f"Cure Index deficient: min CI ({min_ci:.1f}) is below standard threshold ({min_ci_ok*0.8:.1f})")
            subsystems["Conveyor & Drive System"] += 20.0
            subsystems["Burner & Gas Train"] += 20.0

        # 4. Check PLC Operational Signals
        gas_p = plc_dict.get("plc_gas_pressure_mbar", 50.0)
        if gas_p < 40.0:
            warnings.append(f"Gas line pressure low: {gas_p:.1f} mbar (normal range 45-55 mbar)")
            subsystems["Burner & Gas Train"] += 30.0

        conv_speed = plc_dict.get("plc_conveyor_speed_m_min", 2.2)
        if conv_speed > 2.5:
            warnings.append(f"Conveyor overspeed: {conv_speed:.2f} m/min reduces oven soak time")
            subsystems["Conveyor & Drive System"] += 40.0

        fan_speed = plc_dict.get("plc_fan_speed_pct", 85.0)
        if fan_speed < 70.0:
            warnings.append(f"Circulation fan speed low: {fan_speed:.1f}% reduces convective heat transfer")
            subsystems["Circulation Fans & Nozzles"] += 35.0

        damper_pos = plc_dict.get("plc_damper_pos_pct", 50.0)
        if damper_pos < 30.0:
            warnings.append(f"Fresh air damper restricted: {damper_pos:.1f}% position may impede ventilation")
            subsystems["Intake Damper & Filters"] += 25.0

        burner_state = plc_dict.get("plc_burner_state", 1)
        if burner_state == 0:
            warnings.append("Burner flame status: OFF / tripped during cycle")
            subsystems["Burner & Gas Train"] += 50.0

        # Normalize subsystem attribution
        total_score = sum(subsystems.values())
        if total_score > 0:
            subsystems = {k: round((v / total_score) * 100.0, 1) for k, v in subsystems.items()}
        else:
            subsystems["Oven Recipe & PLC Controller"] = 100.0

        # Primary subsystem
        primary_subsystem = max(subsystems, key=subsystems.get)

        # Primary diagnosis and remedy text
        if ng_mode and ng_mode in NG_ROOT_CAUSE:
            root_cause_desc = NG_ROOT_CAUSE[ng_mode]
            remedy_desc = NG_REMEDY.get(ng_mode, "Inspect oven systems according to standard SOP.")
        elif len(warnings) > 0:
            root_cause_desc = f"Process drift detected primarily in {primary_subsystem}."
            remedy_desc = f"Schedule maintenance inspection for {primary_subsystem} components."
        else:
            root_cause_desc = "All operational parameters and virtual thermal profiles within standard tolerances."
            remedy_desc = "Standard routine maintenance. Continue production."

        is_ok = (ng_prob < 0.40) and (len(warnings) == 0 or (spread <= 25.0 and min_ci >= min_ci_ok * 0.8))

        return {
            "verdict": "OK" if is_ok else "NG",
            "ng_probability": float(round(ng_prob, 3)),
            "confidence_pct": float(round((1.0 - ng_prob if is_ok else ng_prob) * 100.0, 1)),
            "primary_subsystem": primary_subsystem,
            "subsystem_attribution": subsystems,
            "root_cause": root_cause_desc,
            "recommended_action": remedy_desc,
            "early_warning_alerts": warnings,
        }
