"""
Stellantis Virtual EMT — Phase 2: Unified Inference Pipeline
Connects Curve Predictor, Feature Extractor, Classifier, and Root Cause Engine.
"""

import os
import joblib
import pandas as pd
import numpy as np
from src.config import MODELS_DIR, OVEN_SPECS, SENSORS, SENSOR_COLS, OVEN_ZONES
from src.features import prepare_plc_features, extract_curve_critical_values
from src.root_cause import RootCauseEngine
from src.validation_engine import ValidationEngine
from src.audit_report import AuditReportGenerator

class VirtualEMTSystem:
    """
    End-to-end Virtual EMT AI Validation System.
    Given PLC operational inputs and vehicle/oven metadata, it:
      1. Predicts the continuous 12-sensor EMT temperature profile.
      2. Computes virtual physics metrics (Arrhenius Cure Index, Peak Temps, Spread).
      3. Classifies cycle status (OK vs NG) with confidence score.
      4. Diagnoses specific failure mode (NG-01 to NG-08).
      5. Runs multi-criteria physical quality validation (Golden Curve & Envelopes).
      6. Generates root cause attribution and prescriptive maintenance recommendations.
    """
    def __init__(self, curve_predictors, classifier, root_cause_engine=None, validation_engine=None):
        self.curve_predictors = curve_predictors  # dict: {"ED": model, "SEALER": model, "TOPCOAT": model}
        self.classifier = classifier
        self.root_cause_engine = root_cause_engine or RootCauseEngine()
        self.validation_engine = validation_engine or ValidationEngine()
        self.audit_generator = AuditReportGenerator()

    @classmethod
    def load(cls, models_dir=None):
        """Load trained model artifacts from disk."""
        if models_dir is None:
            models_dir = MODELS_DIR

        curve_predictors = {}
        for oven in ["ED", "SEALER", "TOPCOAT"]:
            p = os.path.join(models_dir, f"{oven.lower()}_curve_predictor.joblib")
            if os.path.exists(p):
                curve_predictors[oven] = joblib.load(p)

        clf_path = os.path.join(models_dir, "ok_ng_classifier.joblib")
        classifier = joblib.load(clf_path) if os.path.exists(clf_path) else None

        return cls(curve_predictors, classifier)

    def save(self, models_dir=None):
        """Save model artifacts to disk."""
        if models_dir is None:
            models_dir = MODELS_DIR
        os.makedirs(models_dir, exist_ok=True)

        for oven, model in self.curve_predictors.items():
            p = os.path.join(models_dir, f"{oven.lower()}_curve_predictor.joblib")
            joblib.dump(model, p)

        if self.classifier is not None:
            clf_path = os.path.join(models_dir, "ok_ng_classifier.joblib")
            joblib.dump(self.classifier, clf_path)

    def validate_trial(self, plc_inputs):
        """
        Execute full Virtual EMT validation for an oven trial.

        Args:
            plc_inputs: dict with keys:
                - 'oven_type': 'ED' | 'SEALER' | 'TOPCOAT'
                - 'vehicle_model': 'CC21' | 'CC31' | 'CC41' | 'CC51' | 'CC61'
                - 'plc_zone1_setpoint_C' ... 'plc_zone5_setpoint_C'
                - 'plc_fan_speed_pct'
                - 'plc_conveyor_speed_m_min'
                - 'plc_gas_pressure_mbar'
                - 'plc_damper_pos_pct'
                - 'plc_exhaust_fan_pct'
                - 'plc_burner_state'
                - 'plc_loading_vehicles'

        Returns:
            dict containing:
                - 'verdict': 'OK' or 'NG'
                - 'ng_probability': float
                - 'confidence_pct': float
                - 'failure_mode': str or None
                - 'failure_mode_confidence': float
                - 'root_cause': str
                - 'recommended_action': str
                - 'subsystem_attribution': dict
                - 'early_warning_alerts': list of str
                - 'virtual_metrics': dict of critical values
                - 'time_series': dict of {time_s: [...], sensor_name: [...]}
        """
        oven_type = plc_inputs.get("oven_type", "ED")
        if oven_type not in self.curve_predictors:
            raise ValueError(f"No curve predictor available for oven type: {oven_type}")

        predictor = self.curve_predictors[oven_type]
        
        # 1. Feature preparation
        X_plc = prepare_plc_features(plc_inputs, feature_columns=predictor.feature_names)
        
        # 2. Predict EMT continuous curves
        pred_3d = predictor.predict(X_plc) # (1, 12, N_points)
        time_axis = predictor.time_axis

        # Format time series output
        ts_dict = {"time_s": time_axis.tolist()}
        for s_idx, s in enumerate(SENSORS):
            ts_dict[s["name"]] = pred_3d[0, s_idx, :].tolist()
            ts_dict[s["col"]]  = pred_3d[0, s_idx, :].tolist()

        # Add 5 Process Zone Curves
        for z in OVEN_ZONES:
            z_indices = [SENSOR_COLS.index(c) for c in z["sensor_cols"] if c in SENSOR_COLS]
            if z_indices:
                z_curve = np.mean(pred_3d[0, z_indices, :], axis=0)
                ts_dict[z["name"]] = z_curve.tolist()
                ts_dict[z["short_name"]] = z_curve.tolist()

        # 3. Extract physics metrics
        virtual_metrics = extract_curve_critical_values(time_axis, pred_3d[0], oven_type)

        # 4. Classification
        X_clf = X_plc.copy()
        for k, v in virtual_metrics.items():
            X_clf[k] = v

        if self.classifier is not None:
            # Align features for classifier
            X_clf_aligned = prepare_plc_features(X_clf, feature_columns=self.classifier.feature_names)
            # Add virtual metric columns if used in classifier
            for c in self.classifier.feature_names:
                if c in virtual_metrics:
                    X_clf_aligned[c] = virtual_metrics[c]
                elif c not in X_clf_aligned.columns:
                    X_clf_aligned[c] = 0.0
            X_clf_aligned = X_clf_aligned[self.classifier.feature_names]

            ng_prob = float(self.classifier.predict_proba(X_clf_aligned)[0])
            is_ng = ng_prob >= self.classifier.ng_decision_threshold
            
            top_mode = None
            mode_conf = 0.0
            if is_ng:
                mode_res = self.classifier.predict_failure_mode(X_clf_aligned)
                top_mode, mode_conf, _ = mode_res[0]
        else:
            ng_prob = 0.05
            is_ng = False
            top_mode = None
            mode_conf = 0.0

        # 5. Root cause diagnosis
        diag = self.root_cause_engine.diagnose(
            plc_dict=plc_inputs,
            virtual_stats=virtual_metrics,
            ng_mode=top_mode,
            ng_prob=ng_prob
        )

        # 6. Physical Quality Validation Engine (Golden Envelopes & Kinetics)
        vehicle_model = plc_inputs.get("vehicle_model", "CC21")
        quality_audit = self.validation_engine.validate_curves(
            time_axis=time_axis,
            sensor_curves=pred_3d[0],
            oven_type=oven_type,
            vehicle_model=vehicle_model,
            ai_verdict=diag["verdict"],
            ai_confidence=diag["confidence_pct"],
            plc_inputs=plc_inputs
        )

        return {
            "oven_type": oven_type,
            "vehicle_model": vehicle_model,
            "verdict": diag["verdict"],
            "ng_probability": diag["ng_probability"],
            "confidence_pct": diag["confidence_pct"],
            "failure_mode": top_mode,
            "failure_mode_confidence": mode_conf,
            "primary_subsystem": diag["primary_subsystem"],
            "root_cause": diag["root_cause"],
            "recommended_action": diag["recommended_action"],
            "subsystem_attribution": diag["subsystem_attribution"],
            "early_warning_alerts": diag["early_warning_alerts"],
            "virtual_metrics": virtual_metrics,
            "quality_audit": quality_audit,
            "time_series": ts_dict,
        }
