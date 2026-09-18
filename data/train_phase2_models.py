"""
=============================================================================
Stellantis Virtual EMT — Phase 2: Master Training & Evaluation Pipeline
=============================================================================
Trains and validates:
  1. Virtual EMT Curve Predictor (ED, SEALER, TOPCOAT)
  2. Binary OK/NG Classification Ensemble (XGBoost + Random Forest)
  3. Multi-Class NG Failure Mode Classifier
  4. Root Cause Diagnostics & Explanations

Outputs:
  - Saved model artifacts in `models/`
  - High-resolution evaluation charts in `phase2_model_report/`
  - Comprehensive metrics report in `phase2_model_report/phase2_evaluation_report.txt`
=============================================================================
"""

import os
import sys
import json
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, roc_curve, precision_recall_curve, confusion_matrix,
    classification_report, mean_squared_error, mean_absolute_error, r2_score
)
import joblib

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import (
    MODELS_DIR, REPORT_DIR, OVEN_SPECS, SENSORS, SENSOR_COLS, SENSOR_NAMES,
    PLC_FEATURE_COLS, NG_ROOT_CAUSE
)
from src.data_loader import load_metadata, load_all_timeseries_matrix, load_trial_timeseries
from src.features import prepare_plc_features, extract_curve_critical_values
from src.curve_model import VirtualEMTCurvePredictor
from src.classifier_model import VirtualEMTClassifier
from src.root_cause import RootCauseEngine
from src.pipeline import VirtualEMTSystem

warnings.filterwarnings("ignore")

# ── Styling ────────────────────────────────────────────────────────────────
BG_COLOR    = "#0A0F2C"
GRID_COLOR  = "#1A2452"
TEXT_COLOR  = "#E8ECF5"
STELLANTIS_BLUE = "#003DA5"
OK_COLOR    = "#00A651"
NG_COLOR    = "#E31837"
ACCENT      = "#F7941D"

plt.rcParams.update({
    "figure.facecolor":  BG_COLOR,
    "axes.facecolor":    BG_COLOR,
    "axes.edgecolor":    GRID_COLOR,
    "axes.labelcolor":   TEXT_COLOR,
    "axes.titlecolor":   TEXT_COLOR,
    "xtick.color":       TEXT_COLOR,
    "ytick.color":       TEXT_COLOR,
    "text.color":        TEXT_COLOR,
    "grid.color":        GRID_COLOR,
    "grid.alpha":        0.5,
    "legend.facecolor":  "#111830",
    "legend.edgecolor":  GRID_COLOR,
    "font.family":       "DejaVu Sans",
    "figure.dpi":        130,
})

REPORT_LOGS = []

def log(msg=""):
    print(msg)
    REPORT_LOGS.append(msg)

def section_header(title):
    border = "=" * 76
    log(f"\n{border}\n  {title}\n{border}")

# ─────────────────────────────────────────────────────────────────────────
# MAIN TRAINING PIPELINE
# ─────────────────────────────────────────────────────────────────────────
def main():
    start_time = datetime.now()
    section_header("STELLANTIS VIRTUAL EMT — PHASE 2 MODEL TRAINING & EVALUATION")
    log(f"Execution started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Load Metadata
    meta = load_metadata()
    log(f"\n[*] Loaded Master Metadata: {len(meta)} total trials across 3 oven lines")
    log(f"    OK trials: {(meta['result_actual']=='OK').sum()} | NG trials: {(meta['result_actual']=='NG').sum()}")

    # 2. Train-Test Split (80% Train, 20% Test stratified by oven_type & result)
    meta["strat_key"] = meta["oven_type"] + "_" + meta["result_actual"]
    train_meta, test_meta = train_test_split(
        meta, test_size=0.20, stratify=meta["strat_key"], random_state=42
    )
    log(f"\n[*] Stratified Train/Test Split (80/20):")
    log(f"    Training trials : {len(train_meta)} (OK: {(train_meta['result_actual']=='OK').sum()}, NG: {(train_meta['result_actual']=='NG').sum()})")
    log(f"    Holdout Test trials: {len(test_meta)}  (OK: {(test_meta['result_actual']=='OK').sum()}, NG: {(test_meta['result_actual']=='NG').sum()})")

    # 3. Train Virtual EMT Curve Predictors (One per oven type)
    section_header("PHASE 2A: VIRTUAL EMT CURVE PREDICTOR TRAINING")
    
    curve_predictors = {}
    curve_metrics = {}
    test_curve_predictions = {}
    test_curve_actuals = {}

    for oven in ["ED", "SEALER", "TOPCOAT"]:
        log(f"\n>>> Training Curve Predictor for {oven} Oven ({OVEN_SPECS[oven]['name']})...")
        
        # Load timeseries matrix
        step_s = OVEN_SPECS[oven]["step_s"]
        Y_all, trial_ids, time_axis = load_all_timeseries_matrix(oven, step_s=step_s)
        
        # Map trial_ids to train/test mask
        id_to_idx = {tid: i for i, tid in enumerate(trial_ids)}
        train_ids = [tid for tid in train_meta[train_meta["oven_type"] == oven]["trial_id"] if tid in id_to_idx]
        test_ids  = [tid for tid in test_meta[test_meta["oven_type"] == oven]["trial_id"]  if tid in id_to_idx]

        train_indices = [id_to_idx[tid] for tid in train_ids]
        test_indices  = [id_to_idx[tid] for tid in test_ids]

        # Extract features
        df_oven_train = train_meta[train_meta["trial_id"].isin(train_ids)].sort_values(
            "trial_id", key=lambda x: x.map(id_to_idx)
        )
        df_oven_test = test_meta[test_meta["trial_id"].isin(test_ids)].sort_values(
            "trial_id", key=lambda x: x.map(id_to_idx)
        )

        X_train_plc = prepare_plc_features(df_oven_train)
        X_test_plc  = prepare_plc_features(df_oven_test, feature_columns=X_train_plc.columns)

        Y_train = Y_all[train_indices]
        Y_test  = Y_all[test_indices]

        # Fit model
        model = VirtualEMTCurvePredictor(oven_type=oven, n_components=6, n_estimators=120, random_state=42)
        model.fit(X_train_plc, Y_train, time_axis)
        curve_predictors[oven] = model

        # Predict on holdout test set
        Y_pred = model.predict(X_test_plc)
        test_curve_predictions[oven] = Y_pred
        test_curve_actuals[oven] = Y_test

        # Evaluate performance
        time_len = Y_test.shape[2]
        rmse_overall = np.sqrt(mean_squared_error(Y_test.reshape(-1, time_len), Y_pred.reshape(-1, time_len)))
        mae_overall  = mean_absolute_error(Y_test.reshape(-1, time_len), Y_pred.reshape(-1, time_len))
        r2_overall   = r2_score(Y_test.flatten(), Y_pred.flatten())

        sensor_rmses = {}
        for s_idx, s in enumerate(SENSORS):
            s_name = s["name"]
            s_rmse = np.sqrt(mean_squared_error(Y_test[:, s_idx, :], Y_pred[:, s_idx, :]))
            sensor_rmses[s_name] = s_rmse

        curve_metrics[oven] = {
            "rmse": rmse_overall,
            "mae": mae_overall,
            "r2": r2_overall,
            "sensor_rmses": sensor_rmses,
            "time_axis": time_axis,
            "test_ids": test_ids
        }

        log(f"    {oven} Overall Curve RMSE : {rmse_overall:.2f}°C (Target < 3-5°C)")
        log(f"    {oven} Overall Curve MAE  : {mae_overall:.2f}°C")
        log(f"    {oven} Overall Curve R²   : {r2_overall:.4f}")
        log(f"    Top 3 Sensors by Accuracy:")
        sorted_s = sorted(sensor_rmses.items(), key=lambda x: x[1])
        for s_name, s_val in sorted_s[:3]:
            log(f"      - {s_name:<16}: RMSE = {s_val:.2f}°C")

    # 4. Feature Extraction: Build Virtual Feature Matrix for Classification
    section_header("PHASE 2B: OK/NG CLASSIFICATION ENSEMBLE")

    def build_classifier_dataset(meta_df):
        X_list = []
        y_bin_list = []
        y_mode_list = []

        for _, row in meta_df.iterrows():
            oven = row["oven_type"]
            tid  = row["trial_id"]
            model = curve_predictors[oven]

            # 1. Base PLC features
            plc_row = row[PLC_FEATURE_COLS].to_dict()
            plc_row["vehicle_model"] = row["vehicle_model"]
            plc_row["oven_type"] = oven
            
            X_plc = prepare_plc_features(plc_row, feature_columns=model.feature_names)
            
            # 2. Virtual predicted curves
            pred_3d = model.predict(X_plc) # (1, 12, N_points)
            v_stats = extract_curve_critical_values(model.time_axis, pred_3d[0], oven)

            # Combine PLC features with Virtual Curve Physics stats
            feat_combined = X_plc.iloc[0].to_dict()
            feat_combined.update(v_stats)
            
            X_list.append(feat_combined)
            y_bin_list.append(row["label_binary"])
            y_mode_list.append(row["ng_mode"] if pd.notna(row["ng_mode"]) else "OK")

        return pd.DataFrame(X_list), np.array(y_bin_list), pd.Series(y_mode_list)

    log("\n[*] Extracting Virtual EMT features for Train and Test sets...")
    X_train_clf, y_train_bin, y_train_mode = build_classifier_dataset(train_meta)
    X_test_clf,  y_test_bin,  y_test_mode  = build_classifier_dataset(test_meta)

    # Align columns
    clf_features = list(X_train_clf.columns)
    X_test_clf = X_test_clf[clf_features]

    # 5. Train and Cross-Validate Classifier
    log("\n[*] Training Two-Stage Virtual EMT Classifier...")
    classifier = VirtualEMTClassifier(random_state=42)
    classifier.fit(X_train_clf, y_train_bin, y_train_mode)

    # 5-Fold Cross Validation on Training Set
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_accs = cross_val_score(classifier.model_rf, classifier.scaler.transform(X_train_clf), y_train_bin, cv=cv, scoring="accuracy")
    cv_aucs = cross_val_score(classifier.model_rf, classifier.scaler.transform(X_train_clf), y_train_bin, cv=cv, scoring="roc_auc")
    log(f"    5-Fold CV Accuracy: {cv_accs.mean()*100:.1f}% (±{cv_accs.std()*100:.1f}%)")
    log(f"    5-Fold CV ROC-AUC : {cv_aucs.mean():.4f} (±{cv_aucs.std():.4f})")

    # 6. Evaluate on Unseen Holdout Test Set (60 trials)
    y_test_probs = classifier.predict_proba(X_test_clf)
    y_test_pred  = classifier.predict(X_test_clf) # uses conservative 0.40 threshold

    test_acc  = accuracy_score(y_test_bin, y_test_pred)
    test_prec = precision_score(y_test_bin, y_test_pred, zero_division=0)
    test_rec  = recall_score(y_test_bin, y_test_pred, zero_division=0)
    test_f1   = f1_score(y_test_bin, y_test_pred, zero_division=0)
    test_auc  = roc_auc_score(y_test_bin, y_test_probs)

    # Confusion Matrix
    cm = confusion_matrix(y_test_bin, y_test_pred)
    tn, fp, fn, tp = cm.ravel()
    fnr = (fn / (fn + tp)) * 100.0 if (fn + tp) > 0 else 0.0

    log(f"\n>>> Holdout Test Set Performance (60 Trials):")
    log(f"    Accuracy               : {test_acc*100:.1f}%  (Target: >95.0%)")
    log(f"    Precision              : {test_prec*100:.1f}%")
    log(f"    Recall (Detection Rate): {test_rec*100:.1f}%")
    log(f"    F1-Score               : {test_f1:.4f}")
    log(f"    ROC-AUC Score          : {test_auc:.4f}  (Target: >0.950)")
    log(f"    False Negative Rate    : {fnr:.1f}%  (Target: <2.0% - Critical Safety KPI)")
    log(f"\n    Confusion Matrix Breakdown:")
    log(f"      True Negatives  (Actual OK -> Pred OK): {tn:2d}")
    log(f"      False Positives (Actual OK -> Pred NG): {fp:2d}")
    log(f"      False Negatives (Actual NG -> Pred OK): {fn:2d}  <-- CRITICAL")
    log(f"      True Positives  (Actual NG -> Pred NG): {tp:2d}")

    # Multi-class failure mode evaluation on test NG trials
    test_ng_mask = (y_test_bin == 1)
    if test_ng_mask.sum() > 0:
        X_test_ng = X_test_clf[test_ng_mask]
        y_test_ng_actual = y_test_mode[test_ng_mask].values
        mode_preds = classifier.predict_failure_mode(X_test_ng)
        y_test_ng_pred = [m[0] for m in mode_preds]
        mode_acc = accuracy_score(y_test_ng_actual, y_test_ng_pred)
        log(f"\n    NG Failure Mode Diagnosis Accuracy: {mode_acc*100:.1f}% on unseen NG trials")

    # Feature Importance
    feat_imp = classifier.get_feature_importances()
    log(f"\n    Top 10 Most Important Features:")
    for rank, (fname, fscore) in enumerate(feat_imp.head(10).items(), 1):
        log(f"      {rank:2d}. {fname:<35}: {fscore:.4f}")

    # 7. Save Models to Disk
    section_header("PHASE 2 MODEL PERSISTENCE & METADATA EXPORT")
    
    system = VirtualEMTSystem(curve_predictors, classifier, RootCauseEngine())
    system.save(MODELS_DIR)
    log(f"[OK] Saved model artifacts to: {MODELS_DIR}")
    for f in os.listdir(MODELS_DIR):
        log(f"     - {f}")

    # Save metadata JSON
    meta_info = {
        "version": "2.0.0",
        "trained_date": datetime.now().isoformat(),
        "standards": ["ISO 12944", "VDA 621-415", "Ford FLTM BI 106-01"],
        "num_trials_trained": len(train_meta),
        "num_trials_tested": len(test_meta),
        "curve_predictor_metrics": {
            oven: {
                "rmse": float(round(m["rmse"], 2)),
                "mae": float(round(m["mae"], 2)),
                "r2": float(round(m["r2"], 4)),
            } for oven, m in curve_metrics.items()
        },
        "classifier_metrics": {
            "test_accuracy": float(round(test_acc * 100, 1)),
            "test_precision": float(round(test_prec * 100, 1)),
            "test_recall": float(round(test_rec * 100, 1)),
            "test_f1": float(round(test_f1, 4)),
            "test_roc_auc": float(round(test_auc, 4)),
            "false_negative_rate_pct": float(round(fnr, 1)),
        },
        "ng_decision_threshold": classifier.ng_decision_threshold,
        "feature_count": len(clf_features)
    }
    with open(os.path.join(MODELS_DIR, "model_metadata.json"), "w") as f:
        json.dump(meta_info, f, indent=2)
    log(f"[OK] Saved model metadata: {os.path.join(MODELS_DIR, 'model_metadata.json')}")

    # 8. Generate Visual Evaluation Artifacts
    section_header("PHASE 2 VISUAL EVALUATION ARTIFACTS")

    # Chart 1: Curve Predictions Test Comparison
    plot_curve_comparisons(curve_metrics, test_curve_predictions, test_curve_actuals, test_meta)

    # Chart 2: Confusion Matrices
    plot_confusion_matrices(cm, y_test_ng_actual if test_ng_mask.sum() > 0 else None, 
                            y_test_ng_pred if test_ng_mask.sum() > 0 else None)

    # Chart 3: ROC & PR Curves
    plot_roc_pr_curves(y_test_bin, y_test_probs, test_auc)

    # Chart 4: Feature Importance
    plot_feature_importance(feat_imp.head(20))

    # Chart 5: Sensor Error Analysis
    plot_sensor_error_analysis(curve_metrics)

    # Save Text Report
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    log(f"\n[DONE] Phase 2 Model Training & Evaluation completed in {elapsed:.1f}s.")
    
    with open(os.path.join(REPORT_DIR, "phase2_evaluation_report.txt"), "w") as f:
        f.write("\n".join(REPORT_LOGS))
    log(f"[OK] Evaluation report written to: {os.path.join(REPORT_DIR, 'phase2_evaluation_report.txt')}")

# ─────────────────────────────────────────────────────────────────────────
# PLOTTING FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────
def plot_curve_comparisons(curve_metrics, test_preds, test_actuals, test_meta):
    """Plot actual vs predicted EMT curves for test trials across all 3 ovens."""
    fig, axes = plt.subplots(3, 2, figsize=(20, 15))
    fig.suptitle("Phase 2A — Virtual EMT: Actual vs AI-Predicted Temperature Curves (Holdout Test Set)",
                 fontsize=15, fontweight="bold", color=TEXT_COLOR, y=0.99)

    for row_idx, oven in enumerate(["ED", "SEALER", "TOPCOAT"]):
        preds = test_preds[oven]
        actuals = test_actuals[oven]
        time_axis = curve_metrics[oven]["time_axis"] / 60.0 # minutes
        spec = OVEN_SPECS[oven]
        cure_th = spec["cure_threshold"]

        # Pick one OK trial and one NG trial if available
        test_df = test_meta[test_meta["oven_type"] == oven].reset_index(drop=True)
        ok_idx = test_df[test_df["result_actual"] == "OK"].index
        ng_idx = test_df[test_df["result_actual"] == "NG"].index

        idx_ok = ok_idx[0] if len(ok_idx) > 0 else 0
        idx_ng = ng_idx[0] if len(ng_idx) > 0 else (1 if len(test_df) > 1 else 0)

        # Plot OK Trial
        ax_ok = axes[row_idx, 0]
        # Plot mean sensor curve
        ax_ok.plot(time_axis, actuals[idx_ok].mean(axis=0), color="white", linewidth=2.5,
                   linestyle="--", label="Actual EMT (Mean)", zorder=4)
        ax_ok.plot(time_axis, preds[idx_ok].mean(axis=0), color=OK_COLOR, linewidth=2.5,
                   label="Virtual EMT (Predicted)", zorder=5)
        # Shading range across 12 sensors
        ax_ok.fill_between(time_axis, actuals[idx_ok].min(axis=0), actuals[idx_ok].max(axis=0),
                           color="white", alpha=0.10, label="Actual Sensor Spread")
        ax_ok.fill_between(time_axis, preds[idx_ok].min(axis=0), preds[idx_ok].max(axis=0),
                           color=OK_COLOR, alpha=0.15, label="Predicted Spread")
        ax_ok.axhline(cure_th, color="#888", linestyle=":", label=f"Cure Threshold ({cure_th:.0f}°C)")
        
        tid_ok = test_df.loc[idx_ok, "trial_id"]
        ax_ok.set_title(f"{oven} Oven — Test Trial {tid_ok} [Actual: OK]", fontsize=11, fontweight="bold")
        ax_ok.set_xlabel("Time (minutes)", fontsize=9)
        ax_ok.set_ylabel("Temperature (°C)", fontsize=9)
        ax_ok.grid(True, alpha=0.3)
        ax_ok.legend(loc="lower right", fontsize=8)

        # Plot NG Trial
        ax_ng = axes[row_idx, 1]
        ax_ng.plot(time_axis, actuals[idx_ng].mean(axis=0), color="white", linewidth=2.5,
                   linestyle="--", label="Actual EMT (Mean)", zorder=4)
        ax_ng.plot(time_axis, preds[idx_ng].mean(axis=0), color=NG_COLOR, linewidth=2.5,
                   label="Virtual EMT (Predicted)", zorder=5)
        ax_ng.fill_between(time_axis, actuals[idx_ng].min(axis=0), actuals[idx_ng].max(axis=0),
                           color="white", alpha=0.10)
        ax_ng.fill_between(time_axis, preds[idx_ng].min(axis=0), preds[idx_ng].max(axis=0),
                           color=NG_COLOR, alpha=0.15)
        ax_ng.axhline(cure_th, color="#888", linestyle=":")

        tid_ng = test_df.loc[idx_ng, "trial_id"]
        ng_m = test_df.loc[idx_ng, "ng_mode"]
        ax_ng.set_title(f"{oven} Oven — Test Trial {tid_ng} [Actual: NG | {ng_m}]",
                        fontsize=11, fontweight="bold", color=NG_COLOR)
        ax_ng.set_xlabel("Time (minutes)", fontsize=9)
        ax_ng.set_ylabel("Temperature (°C)", fontsize=9)
        ax_ng.grid(True, alpha=0.3)
        ax_ng.legend(loc="lower right", fontsize=8)

    plt.tight_layout()
    out_path = os.path.join(REPORT_DIR, "01_curve_predictions_test.png")
    plt.savefig(out_path, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()
    log(f"[SAVED] {out_path}")

def plot_confusion_matrices(cm_bin, y_mode_actual=None, y_mode_pred=None):
    """Plot binary OK/NG and multi-class NG failure mode confusion matrices."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle("Phase 2B — Classification Confusion Matrices (Holdout Test Set)",
                 fontsize=15, fontweight="bold", color=TEXT_COLOR)

    # 1. Binary CM
    ax1 = axes[0]
    sns.heatmap(cm_bin, annot=True, fmt="d", ax=ax1, cmap="Blues", cbar=False,
                annot_kws={"size": 16, "fontweight": "bold"},
                xticklabels=["Predicted OK", "Predicted NG"],
                yticklabels=["Actual OK", "Actual NG"])
    ax1.set_title("Binary OK / NG Classification", fontsize=13, fontweight="bold", pad=10)
    ax1.tick_params(labelsize=11)

    # 2. Failure Mode CM
    ax2 = axes[1]
    if y_mode_actual is not None and len(y_mode_actual) > 0:
        labels = sorted(list(set(y_mode_actual).union(set(y_mode_pred))))
        cm_mode = confusion_matrix(y_mode_actual, y_mode_pred, labels=labels)
        short_labels = [m.replace("NG-0", "NG-").split("_", 1)[-1][:12] for m in labels]
        sns.heatmap(cm_mode, annot=True, fmt="d", ax=ax2, cmap="YlOrRd", cbar=False,
                    annot_kws={"size": 11, "fontweight": "bold"},
                    xticklabels=short_labels, yticklabels=short_labels)
        ax2.set_title("NG Failure Mode Diagnosis Matrix", fontsize=13, fontweight="bold", pad=10)
        ax2.tick_params(axis="x", rotation=35, labelsize=9)
        ax2.tick_params(axis="y", rotation=0, labelsize=9)
    else:
        ax2.text(0.5, 0.5, "No NG samples in test split", ha="center", va="center", color=TEXT_COLOR)

    plt.tight_layout()
    out_path = os.path.join(REPORT_DIR, "02_confusion_matrices.png")
    plt.savefig(out_path, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()
    log(f"[SAVED] {out_path}")

def plot_roc_pr_curves(y_test, y_probs, auc_score):
    """Plot ROC and Precision-Recall Curves."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle("Phase 2B — Diagnostic Discriminative Power (Holdout Test Set)",
                 fontsize=15, fontweight="bold", color=TEXT_COLOR)

    # ROC Curve
    ax1 = axes[0]
    fpr, tpr, _ = roc_curve(y_test, y_probs)
    ax1.plot(fpr, tpr, color=ACCENT, linewidth=3, label=f"Virtual EMT Ensemble (AUC = {auc_score:.4f})")
    ax1.plot([0, 1], [0, 1], color="#888", linestyle="--", label="Random Baseline (AUC = 0.5000)")
    ax1.fill_between(fpr, 0, tpr, color=ACCENT, alpha=0.15)
    ax1.set_xlabel("False Positive Rate", fontsize=11)
    ax1.set_ylabel("True Positive Rate (Recall)", fontsize=11)
    ax1.set_title("Receiver Operating Characteristic (ROC)", fontsize=13, fontweight="bold")
    ax1.legend(loc="lower right", fontsize=10)
    ax1.grid(True, alpha=0.3)

    # Precision-Recall Curve
    ax2 = axes[1]
    prec, rec, _ = precision_recall_curve(y_test, y_probs)
    ax2.plot(rec, prec, color=OK_COLOR, linewidth=3, label="Precision-Recall Curve")
    ax2.set_xlabel("Recall (Detection Rate)", fontsize=11)
    ax2.set_ylabel("Precision", fontsize=11)
    ax2.set_title("Precision-Recall Curve", fontsize=13, fontweight="bold")
    ax2.legend(loc="lower left", fontsize=10)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = os.path.join(REPORT_DIR, "03_roc_pr_curves.png")
    plt.savefig(out_path, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()
    log(f"[SAVED] {out_path}")

def plot_feature_importance(imp_series):
    """Plot feature importance bar chart."""
    fig, ax = plt.subplots(figsize=(12, 8))
    fig.suptitle("Phase 2 — Global Feature Importance (Virtual EMT Ensemble)",
                 fontsize=14, fontweight="bold", color=TEXT_COLOR)

    names = [n.replace("_peak_C", " Peak").replace("_ci", " Cure Index")
               .replace("_t_cure_min", " Time-at-Cure").replace("plc_", "")
               .replace("_", " ") for n in imp_series.index]

    y_pos = np.arange(len(imp_series))
    ax.barh(y_pos, imp_series.values, color=STELLANTIS_BLUE, alpha=0.85, zorder=3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=9)
    ax.invert_yaxis()  # top-down
    ax.set_xlabel("Importance Score", fontsize=11)
    ax.grid(axis="x", alpha=0.4)

    for i, v in enumerate(imp_series.values):
        ax.text(v + 0.001, i, f"{v:.4f}", va="center", fontsize=8, color=TEXT_COLOR)

    plt.tight_layout()
    out_path = os.path.join(REPORT_DIR, "04_feature_importance.png")
    plt.savefig(out_path, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()
    log(f"[SAVED] {out_path}")

def plot_sensor_error_analysis(curve_metrics):
    """Plot RMSE and MAE by sensor location across all 3 ovens."""
    fig, ax = plt.subplots(figsize=(16, 7))
    fig.suptitle("Phase 2A — Virtual EMT Prediction Error across 12 Car Body Sensors (Test Set)",
                 fontsize=14, fontweight="bold", color=TEXT_COLOR)

    ovens = ["ED", "SEALER", "TOPCOAT"]
    colors = [STELLANTIS_BLUE, OK_COLOR, ACCENT]
    x = np.arange(len(SENSOR_NAMES))
    width = 0.26

    for i, (oven, col) in enumerate(zip(ovens, colors)):
        rmses = [curve_metrics[oven]["sensor_rmses"].get(s, 0.0) for s in SENSOR_NAMES]
        rects = ax.bar(x + (i - 1) * width, rmses, width, label=f"{oven} Oven (Mean: {np.mean(rmses):.2f}°C)",
                       color=col, alpha=0.85, zorder=3)
        for rect in rects:
            h = rect.get_height()
            ax.text(rect.get_x() + rect.get_width() / 2, h + 0.08, f"{h:.1f}",
                    ha="center", va="bottom", fontsize=7.5, color=TEXT_COLOR)

    ax.axhline(3.0, color="#FF4500", linestyle="--", linewidth=1.5, label="Specification Target (<3.0°C)")
    ax.set_xticks(x)
    ax.set_xticklabels([s.replace(" ", "\n") for s in SENSOR_NAMES], fontsize=9)
    ax.set_ylabel("RMSE (°C)", fontsize=11)
    ax.set_title("Per-Sensor Root Mean Square Error (RMSE)", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10, loc="upper right")
    ax.grid(axis="y", alpha=0.4)

    plt.tight_layout()
    out_path = os.path.join(REPORT_DIR, "05_sensor_error_analysis.png")
    plt.savefig(out_path, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()
    log(f"[SAVED] {out_path}")

if __name__ == "__main__":
    main()
