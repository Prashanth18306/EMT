"""
Stellantis Virtual EMT — Unified Physics & Quality Verification Pipeline
Pure Thermodynamic & First-Principles Architecture (Zero ML Dependencies).
Connects Thermodynamic Physics Engine, Kinetics Extractor, Root Cause Engine, 
and Multi-Criteria Dual-Verification Engine.
Aligned with ISO 12944, VDA 621-415, and Ford FLTM BI 106-01 standards.
"""

import os
import numpy as np
from src.config import OVEN_SPECS, SENSORS, SENSOR_COLS, OVEN_ZONES
from src.features import extract_curve_critical_values
from src.physics_engine import ThermodynamicPhysicsEngine
from src.root_cause import RootCauseEngine
from src.validation_engine import ValidationEngine
from src.audit_report import AuditReportGenerator

class VirtualEMTSystem:
    """
    End-to-end Virtual EMT AI/Physics Validation System.
    Given PLC operational inputs and vehicle/oven metadata, it:
      1. Simulates continuous 12-sensor EMT temperature profiles via thermodynamic transfer.
      2. Computes virtual physics metrics (Arrhenius Cure Index, Peak Temps, Spread).
      3. Diagnoses specific failure mode (NG-01 to NG-08) and suspect subsystems.
      4. Runs multi-criteria physical quality validation (Golden Curve & Envelopes).
      5. Generates root cause attribution and prescriptive maintenance recommendations.
      6. Outputs digital quality certificates matching BYK-Gardner temp-gard standards.
    """
    def __init__(self, physics_engine=None, root_cause_engine=None, validation_engine=None):
        self.physics_engine = physics_engine or ThermodynamicPhysicsEngine()
        self.root_cause_engine = root_cause_engine or RootCauseEngine()
        self.validation_engine = validation_engine or ValidationEngine()
        self.audit_generator = AuditReportGenerator()

    @classmethod
    def load(cls, models_dir=None):
        """Instantiate the Virtual EMT System (pure physics engine, no disk artifacts required)."""
        return cls()

    def validate_trial(self, plc_inputs):
        """
        Execute full Virtual EMT validation for an oven trial.

        Args:
            plc_inputs: dict of operational parameters

        Returns:
            dict containing comprehensive verdict, audit scorecard, and time series
        """
        oven_type = plc_inputs.get("oven_type", "ED")
        vehicle_model = plc_inputs.get("vehicle_model", "CC21")
        spec = OVEN_SPECS.get(oven_type, OVEN_SPECS["ED"])

        # 1. Simulate continuous 12-sensor EMT curves via thermodynamics
        time_axis, curves_2d = self.physics_engine.simulate_thermal_profile(plc_inputs)

        # Format time series output
        ts_dict = {"time_s": time_axis.tolist()}
        for s_idx, s in enumerate(SENSORS):
            sensor_vals = curves_2d[s_idx, :].tolist()
            ts_dict[s["name"]] = sensor_vals
            ts_dict[s["col"]]  = sensor_vals

        # Add 5 Process Zone Curves
        for z in OVEN_ZONES:
            z_indices = [SENSOR_COLS.index(c) for c in z["sensor_cols"] if c in SENSOR_COLS]
            if z_indices:
                z_curve = np.mean(curves_2d[z_indices, :], axis=0)
                ts_dict[z["name"]] = z_curve.tolist()
                ts_dict[z["short_name"]] = z_curve.tolist()

        # 2. Extract physics milestones and Arrhenius cure index metrics
        virtual_metrics = extract_curve_critical_values(time_axis, curves_2d, oven_type)

        # 3. Physical Quality Validation Engine (Golden Envelopes, Arrhenius Kinetics, Limits)
        quality_audit = self.validation_engine.validate_curves(
            time_axis=time_axis,
            sensor_curves=curves_2d,
            oven_type=oven_type,
            vehicle_model=vehicle_model,
            ai_verdict=None,
            ai_confidence=100.0,
            plc_inputs=plc_inputs
        )

        is_ng = (quality_audit["final_status"] == "REJECTED (NG)")
        
        # Determine failure mode if NG
        top_mode = None
        if is_ng:
            min_peak = virtual_metrics.get("summary_min_peak", 0.0)
            max_peak = virtual_metrics.get("summary_max_peak", 0.0)
            min_ci = virtual_metrics.get("summary_min_ci", 0.0)
            spread = virtual_metrics.get("summary_spread", 0.0)

            if min_peak < spec["target_peak_ok"][0] - 5:
                top_mode = "NG-01_LOW_PEAK_TEMP"
            elif max_peak > spec["target_peak_ok"][1] + 5:
                top_mode = "NG-02_HIGH_PEAK_TEMP"
            elif min_ci < spec["cure_index_ok"] * 0.8:
                top_mode = "NG-03_SHORT_CURE_TIME"
            elif spread > 22.0:
                top_mode = "NG-04_UNEVEN_TEMP"
            else:
                top_mode = "NG-08_GLOBAL_LOW"

        ng_prob = 0.95 if is_ng else 0.04

        # 4. Root cause diagnosis and subsystem attribution
        diag = self.root_cause_engine.diagnose(
            plc_dict=plc_inputs,
            virtual_stats=virtual_metrics,
            ng_mode=top_mode,
            ng_prob=ng_prob
        )

        final_verdict = "NG" if is_ng else "OK"

        return {
            "oven_type": oven_type,
            "vehicle_model": vehicle_model,
            "verdict": final_verdict,
            "ng_probability": ng_prob,
            "confidence_pct": round(quality_audit["cure_quality_index_pct"], 1),
            "failure_mode": top_mode,
            "failure_mode_confidence": round(quality_audit["cure_quality_index_pct"], 1),
            "primary_subsystem": diag["primary_subsystem"],
            "root_cause": diag["root_cause"],
            "recommended_action": diag["recommended_action"],
            "subsystem_attribution": diag["subsystem_attribution"],
            "early_warning_alerts": diag["early_warning_alerts"],
            "virtual_metrics": virtual_metrics,
            "quality_audit": quality_audit,
            "time_series": ts_dict,
        }
