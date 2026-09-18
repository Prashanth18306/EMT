"""
=============================================================================
Stellantis Virtual EMT — Phase 3: Validation Engine & Quality Audit Runner
=============================================================================
Executes full physical and kinetic validation across all test trials:
  1. Golden Standard Curve & Tolerance Envelope Tracking
  2. Arrhenius Chemical Cure Kinetics & Milestone Computation
  3. Multi-Criteria Physical Standards Compliance
  4. Dual-Verification Synthesis (AI Verdict vs Physics Rules)
  5. Executive Digital Quality Certificates & Audit Reports (HTML & JSON)
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import (
    MODELS_DIR, OVEN_SPECS, SENSORS, SENSOR_COLS, SENSOR_NAMES,
    PLC_FEATURE_COLS
)
from src.data_loader import load_metadata, load_trial_timeseries
from src.pipeline import VirtualEMTSystem
from src.standard_curve_library import StandardCurveLibrary
from src.cure_kinetics import CureKineticsEngine
from src.validation_engine import ValidationEngine
from src.audit_report import AuditReportGenerator

warnings.filterwarnings("ignore")

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phase3_validation_report")
os.makedirs(OUT_DIR, exist_ok=True)

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

def main():
    start_time = datetime.now()
    section_header("STELLANTIS VIRTUAL EMT — PHASE 3 VALIDATION ENGINE EXECUTION")
    log(f"Execution started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Initialize System & Validation Engine
    log("\n[*] Loading Virtual EMT System & Quality Validation Engine...")
    system = VirtualEMTSystem.load()
    std_lib = StandardCurveLibrary()
    kinetics = CureKineticsEngine()
    val_engine = ValidationEngine(std_lib, kinetics)
    audit_gen = AuditReportGenerator()
    log("    [OK] Loaded trained AI models (Curve Regressors + XGB/RF Classifiers)")
    log("    [OK] Initialized Golden Curve Library with mass compensation")
    log("    [OK] Initialized Arrhenius Cure Kinetics Engine (k=12.0)")
    log("    [OK] Initialized Multi-Criteria Quality Validation Engine")

    # 2. Load Master Trials
    meta = load_metadata()
    log(f"\n[*] Loaded {len(meta)} trials from ALL_OVENS_metadata.csv")

    from sklearn.model_selection import train_test_split
    meta["strat_key"] = meta["oven_type"] + "_" + meta["result_actual"]
    _, test_meta = train_test_split(
        meta, test_size=0.20, stratify=meta["strat_key"], random_state=42
    )
    test_meta = test_meta.reset_index(drop=True)
    log(f"    Evaluating on {len(test_meta)} holdout test trials (stratified 20% sample)")
    log(f"    OK trials: {(test_meta['result_actual']=='OK').sum()} | NG trials: {(test_meta['result_actual']=='NG').sum()}")

    # 3. Batch Validation Execution
    section_header("EXECUTING MULTI-CRITERIA QUALITY VALIDATION")

    results_list = []
    concordance_matrix = {"OK_OK": 0, "OK_NG": 0, "NG_OK": 0, "NG_NG": 0}
    cqi_scores = {"OK": [], "NG": []}
    sensor_ci_matrix = [] # for heatmap
    trial_labels = []

    sample_ok_result = None
    sample_ok_id = None
    sample_ng_result = None
    sample_ng_id = None

    for i, row in test_meta.iterrows():
        tid = row["trial_id"]
        oven = row["oven_type"]
        v_model = row["vehicle_model"]
        actual_res = row["result_actual"]

        # Prepare inputs
        plc_inputs = row[PLC_FEATURE_COLS].to_dict()
        plc_inputs["oven_type"] = oven
        plc_inputs["vehicle_model"] = v_model

        # Run full validation pipeline
        val_res = system.validate_trial(plc_inputs)
        audit = val_res["quality_audit"]

        ai_v = val_res["verdict"]
        phys_v = audit["physics_verdict"]
        cqi = audit["cure_quality_index_pct"]
        cqi_scores[actual_res].append(cqi)

        # Track Dual-Verification Concordance
        conc_key = f"{ai_v}_{phys_v}"
        if conc_key in concordance_matrix:
            concordance_matrix[conc_key] += 1

        # Track Sensor CIs
        cis = [s["cure_index"] for s in audit["sensor_audit_table"]]
        sensor_ci_matrix.append(cis)
        trial_labels.append(f"{tid} ({actual_res})")

        # Save sample for HTML export
        if actual_res == "OK" and sample_ok_result is None and cqi >= 80.0:
            sample_ok_result = audit
            sample_ok_id = tid
        if actual_res == "NG" and sample_ng_result is None and len(audit["physics_violations"]) > 0:
            sample_ng_result = audit
            sample_ng_id = tid

        results_list.append({
            "trial_id": tid,
            "oven_type": oven,
            "vehicle_model": v_model,
            "actual_result": actual_res,
            "ai_verdict": ai_v,
            "ai_confidence": val_res["confidence_pct"],
            "physics_verdict": phys_v,
            "final_status": audit["final_status"],
            "cqi_pct": cqi,
            "spread_C": audit["cross_body_spread_C"],
            "pass_ratio": audit["sensor_pass_count"],
            "violations_count": len(audit["physics_violations"]),
        })

    df_res = pd.DataFrame(results_list)

    # 4. Quantitative Performance Metrics
    section_header("PHASE 3 VALIDATION ENGINE AUDIT METRICS")

    agreement = (df_res["ai_verdict"] == df_res["physics_verdict"]).mean() * 100.0
    phys_accuracy = (df_res["physics_verdict"] == df_res["actual_result"]).mean() * 100.0
    ai_accuracy = (df_res["ai_verdict"] == df_res["actual_result"]).mean() * 100.0

    mean_cqi_ok = np.mean(cqi_scores["OK"]) if cqi_scores["OK"] else 0.0
    mean_cqi_ng = np.mean(cqi_scores["NG"]) if cqi_scores["NG"] else 0.0

    log(f"\n>>> Dual-Verification Concordance:")
    log(f"    AI Model Accuracy vs Ground Truth     : {ai_accuracy:.1f}%")
    log(f"    Physics Rules Accuracy vs Ground Truth: {phys_accuracy:.1f}%")
    log(f"    AI-Physics Agreement Concordance Rate : {agreement:.1f}%")

    log(f"\n    Concordance Breakdown (AI vs Physics):")
    log(f"      - AI OK  + Physics OK  [Certified Pass]    : {concordance_matrix['OK_OK']:2d} trials")
    log(f"      - AI NG  + Physics NG  [Confirmed Reject]   : {concordance_matrix['NG_NG']:2d} trials")
    log(f"      - AI OK  + Physics NG  [Quality Hold]       : {concordance_matrix['OK_NG']:2d} trials")
    log(f"      - AI NG  + Physics OK  [Early Warning Alert]: {concordance_matrix['NG_OK']:2d} trials")

    log(f"\n>>> Cure Quality Index (CQI) Analysis (0-100%):")
    log(f"    Mean CQI for OK Cycles : {mean_cqi_ok:.1f}% (High Quality Standard)")
    log(f"    Mean CQI for NG Cycles : {mean_cqi_ng:.1f}% (Significant Thermal Deficit)")
    log(f"    Quality Separation Margin: {mean_cqi_ok - mean_cqi_ng:.1f}%")

    # 5. Export Sample HTML Certificates
    section_header("EXPORTING DIGITAL QUALITY CERTIFICATES")

    if sample_ok_result:
        html_ok_path = os.path.join(OUT_DIR, "sample_audit_OK.html")
        audit_gen.generate_html_report(sample_ok_result, sample_ok_id, output_path=html_ok_path)
        log(f"[OK] Generated Certified PASS Certificate: {html_ok_path}")

    if sample_ng_result:
        html_ng_path = os.path.join(OUT_DIR, "sample_audit_NG.html")
        audit_gen.generate_html_report(sample_ng_result, sample_ng_id, output_path=html_ng_path)
        log(f"[OK] Generated REJECTED (NG) Certificate : {html_ng_path}")

    # 6. Generate Phase 3 Visualization Figures
    section_header("GENERATING PHASE 3 VISUAL COMPLIANCE CHARTS")

    plot_tolerance_envelope_overlay(std_lib, system, test_meta)
    plot_cure_index_compliance_matrix(sensor_ci_matrix, trial_labels)
    plot_dual_verdict_agreement(concordance_matrix)
    plot_cqi_distribution(cqi_scores)

    # 7. Write Summary Text Report
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    log(f"\n[DONE] Phase 3 Validation Engine execution completed in {elapsed:.1f}s.")

    report_file = os.path.join(OUT_DIR, "phase3_validation_report.txt")
    with open(report_file, "w") as f:
        f.write("\n".join(REPORT_LOGS))
    log(f"[OK] Validation report written to: {report_file}")

# ─────────────────────────────────────────────────────────────────────────
# PLOTTING FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────
def plot_tolerance_envelope_overlay(std_lib, system, test_meta):
    """Plot predicted curves overlaid on golden reference with upper/lower envelopes."""
    fig, axes = plt.subplots(3, 2, figsize=(20, 15))
    fig.suptitle("Phase 3 — Golden Tolerance Envelope Compliance (Holdout Test Trials)",
                 fontsize=15, fontweight="bold", color=TEXT_COLOR, y=0.99)

    for r_idx, oven in enumerate(["ED", "SEALER", "TOPCOAT"]):
        std_info = std_lib.get_standard_curve(oven, "CC21")
        t_min = std_info["time_min"]
        g_temp = std_info["standard_temp_C"]
        u_lim = std_info["upper_limit_C"]
        l_lim = std_info["lower_limit_C"]
        cure_th = std_info["cure_threshold"]

        df_oven = test_meta[test_meta["oven_type"] == oven].reset_index(drop=True)
        ok_rows = df_oven[df_oven["result_actual"] == "OK"]
        ng_rows = df_oven[df_oven["result_actual"] == "NG"]

        row_ok = ok_rows.iloc[0] if len(ok_rows) > 0 else df_oven.iloc[0]
        row_ng = ng_rows.iloc[0] if len(ng_rows) > 0 else df_oven.iloc[1]

        for c_idx, (row_data, label_name, pcolor) in enumerate([
            (row_ok, "OK Cycle (Compliant Tracking)", OK_COLOR),
            (row_ng, f"NG Cycle ({row_ng['ng_mode']})", NG_COLOR)
        ]):
            ax = axes[r_idx, c_idx]

            # 1. Golden Reference and Envelope
            ax.plot(t_min, g_temp, color="#AAA", linewidth=1.5, linestyle="--", label="Golden Standard", zorder=3)
            ax.plot(t_min, u_lim, color="#5577AA", linewidth=1.2, linestyle=":", label="Upper Limit (+8/12°C)", zorder=3)
            ax.plot(t_min, l_lim, color="#5577AA", linewidth=1.2, linestyle=":", label="Lower Limit (-8/12°C)", zorder=3)
            ax.fill_between(t_min, l_lim, u_lim, color="#5577AA", alpha=0.10, label="Acceptance Envelope", zorder=2)
            ax.axhline(cure_th, color="#FFD700", linestyle="--", linewidth=1, label=f"Cure Threshold ({cure_th:.0f}°C)")

            # 2. Predict curve for this trial
            plc_dict = row_data[PLC_FEATURE_COLS].to_dict()
            plc_dict["oven_type"] = oven
            plc_dict["vehicle_model"] = row_data["vehicle_model"]
            val_out = system.validate_trial(plc_dict)
            ts = val_out["time_series"]
            time_m = np.array(ts["time_s"]) / 60.0

            # Plot Core Sensors vs Extremity Sensors
            for s in SENSORS:
                s_name = s["name"]
                s_col = s["col"]
                pts = np.array(ts[s_col])
                is_core = s["type"] == "core"
                alpha = 0.85 if is_core else 0.50
                lw = 1.6 if is_core else 1.0
                ax.plot(time_m, pts, color=pcolor, alpha=alpha, linewidth=lw,
                        label=f"Predicted ({s_name})" if s_name in ["LH HOOD", "LH T/G"] else None, zorder=5)

            tid = row_data["trial_id"]
            cqi = val_out["quality_audit"]["cure_quality_index_pct"]
            ax.set_title(f"{oven} Oven — {tid}: {label_name} [CQI: {cqi}%]", fontsize=11, fontweight="bold")
            ax.set_xlabel("Time (minutes)", fontsize=9)
            ax.set_ylabel("Temperature (°C)", fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.legend(loc="lower right", fontsize=7, ncol=2)

    plt.tight_layout()
    out_path = os.path.join(OUT_DIR, "01_tolerance_envelope_overlay.png")
    plt.savefig(out_path, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()
    log(f"[SAVED] {out_path}")

def plot_cure_index_compliance_matrix(sensor_ci_matrix, trial_labels):
    """Plot Cure Index heatmap across all 12 sensors for test trials."""
    fig, ax = plt.subplots(figsize=(18, 10))
    fig.suptitle("Phase 3 — Sensor-by-Sensor Arrhenius Cure Index Matrix (Test Trials)",
                 fontsize=14, fontweight="bold", color=TEXT_COLOR)

    # Subsample 25 trials for clean visualization
    step = max(len(sensor_ci_matrix) // 25, 1)
    matrix_sub = np.array(sensor_ci_matrix)[::step]
    labels_sub = trial_labels[::step]

    sns.heatmap(
        matrix_sub.T, ax=ax, cmap="viridis",
        yticklabels=SENSOR_NAMES,
        xticklabels=labels_sub,
        annot=True, fmt=".0f", annot_kws={"size": 7.5},
        cbar_kws={"label": "Arrhenius Cure Index (Equivalent Minutes)"}
    )
    ax.set_title("Cure Index per Sensor Location across Evaluated Cycles", fontsize=12, fontweight="bold", pad=10)
    ax.tick_params(axis="x", rotation=40, labelsize=8)
    ax.tick_params(axis="y", rotation=0, labelsize=9)

    plt.tight_layout()
    out_path = os.path.join(OUT_DIR, "02_cure_index_compliance_matrix.png")
    plt.savefig(out_path, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()
    log(f"[SAVED] {out_path}")

def plot_dual_verdict_agreement(conc_dict):
    """Plot concordance matrix between AI verdict and physical validation verdict."""
    fig, ax = plt.subplots(figsize=(8, 7))
    fig.suptitle("Phase 3 — Dual-Verification Concordance Matrix",
                 fontsize=14, fontweight="bold", color=TEXT_COLOR)

    data = np.array([
        [conc_dict["OK_OK"], conc_dict["OK_NG"]],
        [conc_dict["NG_OK"], conc_dict["NG_NG"]]
    ])

    sns.heatmap(
        data, annot=True, fmt="d", ax=ax, cmap="Blues", cbar=False,
        annot_kws={"size": 18, "fontweight": "bold"},
        xticklabels=["Physics OK", "Physics NG"],
        yticklabels=["AI Model OK", "AI Model NG"]
    )
    ax.set_title("AI Machine Learning vs Physical Quality Rules Concordance", fontsize=11, fontweight="bold", pad=10)
    ax.tick_params(labelsize=11)

    plt.tight_layout()
    out_path = os.path.join(OUT_DIR, "03_dual_verdict_agreement.png")
    plt.savefig(out_path, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()
    log(f"[SAVED] {out_path}")

def plot_cqi_distribution(cqi_scores):
    """Plot distribution of Cure Quality Index (CQI) for OK vs NG cycles."""
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle("Phase 3 — Cure Quality Index (CQI) Separation: OK vs NG",
                 fontsize=14, fontweight="bold", color=TEXT_COLOR)

    ok_scores = cqi_scores.get("OK", [])
    ng_scores = cqi_scores.get("NG", [])

    bins = np.linspace(0, 100, 25)
    ax.hist(ok_scores, bins=bins, color=OK_COLOR, alpha=0.7, label=f"OK Cycles (Mean: {np.mean(ok_scores):.1f}%)", zorder=3)
    ax.hist(ng_scores, bins=bins, color=NG_COLOR, alpha=0.7, label=f"NG Cycles (Mean: {np.mean(ng_scores):.1f}%)", zorder=3)

    # Threshold quality tier lines
    ax.axvline(85.0, color="#FFD700", linestyle="--", linewidth=1.5, label="Gold Standard Tier (≥85%)")
    ax.axvline(70.0, color=ACCENT, linestyle="--", linewidth=1.5, label="Standard Quality Minimum (≥70%)")

    ax.set_xlabel("Cure Quality Index (%)", fontsize=11)
    ax.set_ylabel("Number of Cycles", fontsize=11)
    ax.set_title("Distribution of CQI Composite Quality Scores", fontsize=12, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = os.path.join(OUT_DIR, "04_cqi_distribution_by_tier.png")
    plt.savefig(out_path, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close()
    log(f"[SAVED] {out_path}")

if __name__ == "__main__":
    main()
