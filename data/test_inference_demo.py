"""
=============================================================================
Stellantis Virtual EMT — Phase 2: Live Inference & System Demonstration
=============================================================================
Loads the trained VirtualEMTSystem and demonstrates live prediction for:
  Scenario 1: Normal Production Cycle (ED Oven, Model CC21) -> Expected: OK
  Scenario 2: Conveyor Overspeed Cycle (Topcoat Oven, Model CC51) -> Expected: NG (NG-03)
  Scenario 3: Burner Flameout / Low Gas Pressure (ED Oven, Model CC31) -> Expected: NG (NG-01)
  Scenario 4: Fan Degradation / Airflow Imbalance (Sealer Oven, Model CC41) -> Expected: NG (NG-04)
=============================================================================
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import VirtualEMTSystem

def run_demo():
    print("=" * 76)
    print("  STELLANTIS VIRTUAL EMT — PHASE 2 LIVE INFERENCE DEMONSTRATION")
    print("=" * 76)

    # 1. Load Trained System
    print("\n[*] Loading Virtual EMT AI Models from `models/`...")
    system = VirtualEMTSystem.load()
    print("    [OK] Loaded curve predictors: ED, SEALER, TOPCOAT")
    print("    [OK] Loaded OK/NG classification ensemble")
    print("    [OK] Loaded root cause diagnostics engine")

    # 2. Define Test Scenarios
    scenarios = [
        {
            "name": "Scenario 1: Normal Production Cycle (ED Oven, Model CC21)",
            "inputs": {
                "oven_type": "ED",
                "vehicle_model": "CC21",
                "plc_zone1_setpoint_C": 140.5,
                "plc_zone2_setpoint_C": 175.2,
                "plc_zone3_setpoint_C": 190.1,
                "plc_zone4_setpoint_C": 190.8,
                "plc_zone5_setpoint_C": 180.3,
                "plc_fan_speed_pct": 86.4,
                "plc_conveyor_speed_m_min": 2.18,
                "plc_gas_pressure_mbar": 51.2,
                "plc_damper_pos_pct": 52.0,
                "plc_exhaust_fan_pct": 78.5,
                "plc_burner_state": 1,
                "plc_loading_vehicles": 5,
            }
        },
        {
            "name": "Scenario 2: Conveyor Speed Too Fast (Topcoat Oven, Model CC51)",
            "inputs": {
                "oven_type": "TOPCOAT",
                "vehicle_model": "CC51",
                "plc_zone1_setpoint_C": 110.2,
                "plc_zone2_setpoint_C": 134.8,
                "plc_zone3_setpoint_C": 145.1,
                "plc_zone4_setpoint_C": 144.9,
                "plc_zone5_setpoint_C": 130.4,
                "plc_fan_speed_pct": 84.1,
                "plc_conveyor_speed_m_min": 2.82,  # Overspeed! Standard is 2.0-2.4
                "plc_gas_pressure_mbar": 49.5,
                "plc_damper_pos_pct": 48.0,
                "plc_exhaust_fan_pct": 75.0,
                "plc_burner_state": 1,
                "plc_loading_vehicles": 6,
            }
        },
        {
            "name": "Scenario 3: Burner Trip / Low Gas Pressure (ED Oven, Model CC31)",
            "inputs": {
                "oven_type": "ED",
                "vehicle_model": "CC31",
                "plc_zone1_setpoint_C": 128.0,  # Below setpoint
                "plc_zone2_setpoint_C": 158.5,
                "plc_zone3_setpoint_C": 169.2,
                "plc_zone4_setpoint_C": 168.0,
                "plc_zone5_setpoint_C": 155.0,
                "plc_fan_speed_pct": 82.0,
                "plc_conveyor_speed_m_min": 2.22,
                "plc_gas_pressure_mbar": 34.2,  # Low gas pressure!
                "plc_damper_pos_pct": 28.0,
                "plc_exhaust_fan_pct": 52.0,
                "plc_burner_state": 0,          # Burner tripped!
                "plc_loading_vehicles": 4,
            }
        },
        {
            "name": "Scenario 4: Recirculation Fan Degradation (Sealer Oven, Model CC41)",
            "inputs": {
                "oven_type": "SEALER",
                "vehicle_model": "CC41",
                "plc_zone1_setpoint_C": 119.5,
                "plc_zone2_setpoint_C": 149.8,
                "plc_zone3_setpoint_C": 164.2,
                "plc_zone4_setpoint_C": 165.1,
                "plc_zone5_setpoint_C": 150.0,
                "plc_fan_speed_pct": 58.5,      # Low fan speed!
                "plc_conveyor_speed_m_min": 2.20,
                "plc_gas_pressure_mbar": 50.1,
                "plc_damper_pos_pct": 40.0,
                "plc_exhaust_fan_pct": 60.0,
                "plc_burner_state": 1,
                "plc_loading_vehicles": 5,
            }
        },
    ]

    # 3. Execute Predictions
    for sc in scenarios:
        print("\n" + "-" * 76)
        print(f"  {sc['name']}")
        print("-" * 76)
        
        res = system.validate_trial(sc["inputs"])
        
        verdict_color = "[PASS - OK]" if res["verdict"] == "OK" else "[FAIL - NG]"
        print(f"  AI Verdict            : {verdict_color}")
        print(f"  Confidence            : {res['confidence_pct']:.1f}%  (P(NG) = {res['ng_probability']:.3f})")
        
        if res["failure_mode"]:
            print(f"  Predicted Failure Mode: {res['failure_mode']} (Confidence: {res['failure_mode_confidence']*100:.1f}%)")
        
        print(f"  Root Cause Diagnosis  : {res['root_cause']}")
        print(f"  Recommended Action    : {res['recommended_action']}")
        print(f"  Primary Subsystem     : {res['primary_subsystem']}")
        
        # Virtual Thermal Metrics
        vm = res["virtual_metrics"]
        print(f"\n  Virtual EMT Metrics:")
        print(f"    - Peak Temp Range   : {vm['summary_min_peak']:.1f}°C to {vm['summary_max_peak']:.1f}°C (Spread: {vm['summary_spread']:.1f}°C)")
        print(f"    - Mean Cure Index   : {vm['summary_mean_ci']:.1f}  (Min Sensor CI: {vm['summary_min_ci']:.1f})")
        print(f"    - Mean Time-at-Cure : {vm['summary_mean_tcure']:.1f} min (Min: {vm['summary_min_tcure']:.1f} min)")

        # Subsystem Attribution
        print(f"\n  Subsystem Health Attribution:")
        for subsys, score in res["subsystem_attribution"].items():
            bar = "#" * int(score / 5)
            print(f"    {subsys:<30}: {score:5.1f}% | {bar}")

        if res["early_warning_alerts"]:
            print(f"\n  Early Warning Alerts ({len(res['early_warning_alerts'])}):")
            for alert in res["early_warning_alerts"]:
                print(f"    [!] {alert}")

    print("\n" + "=" * 76)
    print("  INFERENCE DEMONSTRATION COMPLETE — SYSTEM READY FOR PHASE 3 & 4")
    print("=" * 76)

if __name__ == "__main__":
    run_demo()
