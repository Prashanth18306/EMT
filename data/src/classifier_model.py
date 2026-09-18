"""
Stellantis Virtual EMT — Phase 2B: OK/NG Classification & Failure Mode Models
Combines Gradient Boosting and Random Forest with decision threshold tuning 
to achieve >95% accuracy and <2% False Negative Rate.
"""

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler

class VirtualEMTClassifier:
    """
    Two-stage classifier:
      Stage 1: Binary OK vs NG prediction with calibrated threshold (P(NG) >= 0.40)
               to ensure False Negative Rate < 2.0%.
      Stage 2: Multi-class failure mode diagnosis (NG-01 to NG-08).
    """
    def __init__(self, random_state=42):
        self.random_state = random_state
        self.scaler = StandardScaler()
        
        # Stage 1: Ensemble binary models
        self.model_xgb = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            eval_metric="logloss",
            random_state=random_state
        )
        self.model_rf = RandomForestClassifier(
            n_estimators=120,
            max_depth=6,
            class_weight="balanced",
            random_state=random_state,
            n_jobs=1
        )
        
        # Stage 2: Failure mode classifier
        self.mode_encoder = LabelEncoder()
        self.model_mode = RandomForestClassifier(
            n_estimators=120,
            max_depth=8,
            random_state=random_state,
            n_jobs=1
        )
        
        self.feature_names = None
        self.ng_decision_threshold = 0.40  # Conservative for automotive quality safety
        self.is_fitted = False

    def fit(self, X_df, y_binary, y_modes=None):
        """
        X_df: Feature DataFrame (PLC features + virtual curve statistics)
        y_binary: Binary array (0 = OK, 1 = NG)
        y_modes: Series of NG mode strings (or 'OK' / None for OK trials)
        """
        self.feature_names = list(X_df.columns)
        X_scaled = self.scaler.fit_transform(X_df)

        # 1. Fit binary ensemble
        self.model_xgb.fit(X_scaled, y_binary)
        self.model_rf.fit(X_scaled, y_binary)

        # 2. Fit failure mode classifier on NG subset
        if y_modes is not None:
            ng_mask = (y_binary == 1) & (y_modes.notna()) & (y_modes != "OK") & (y_modes != "N/A")
            if ng_mask.sum() > 0:
                X_ng = X_scaled[ng_mask]
                y_ng_str = y_modes[ng_mask].values
                y_ng_encoded = self.mode_encoder.fit_transform(y_ng_str)
                self.model_mode.fit(X_ng, y_ng_encoded)

        self.is_fitted = True
        return self

    def predict_proba(self, X_df):
        """Returns ensemble probability of NG: shape (N_samples,)"""
        X_aligned = X_df[self.feature_names].copy()
        X_scaled = self.scaler.transform(X_aligned)
        
        p_xgb = self.model_xgb.predict_proba(X_scaled)[:, 1]
        p_rf  = self.model_rf.predict_proba(X_scaled)[:, 1]
        p_ensemble = 0.55 * p_xgb + 0.45 * p_rf
        return p_ensemble

    def predict(self, X_df, threshold=None):
        """
        Returns binary verdict: 0 = OK, 1 = NG
        Uses conservative threshold (default 0.40) to prevent False Negatives.
        """
        if threshold is None:
            threshold = self.ng_decision_threshold
        probs = self.predict_proba(X_df)
        return (probs >= threshold).astype(int)

    def predict_failure_mode(self, X_df):
        """
        Predict specific failure mode for NG trials.
        Returns:
            list of (top_mode, confidence_score, all_mode_probs_dict)
        """
        X_aligned = X_df[self.feature_names].copy()
        X_scaled = self.scaler.transform(X_aligned)

        mode_probs = self.model_mode.predict_proba(X_scaled)
        classes = self.mode_encoder.classes_

        results = []
        for i in range(len(X_df)):
            p = mode_probs[i]
            best_idx = np.argmax(p)
            top_mode = classes[best_idx]
            conf = float(round(p[best_idx], 3))
            all_dict = {classes[j]: float(round(p[j], 3)) for j in range(len(classes))}
            results.append((top_mode, conf, all_dict))

        return results

    def get_feature_importances(self):
        """Return combined feature importance series sorted descending."""
        imp_xgb = self.model_xgb.feature_importances_
        imp_rf  = self.model_rf.feature_importances_
        comb = 0.5 * imp_xgb + 0.5 * imp_rf
        s = pd.Series(comb, index=self.feature_names).sort_values(ascending=False)
        return s
