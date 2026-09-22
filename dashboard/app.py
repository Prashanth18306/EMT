"""
Stellantis Virtual EMT — Phase 4: Production Web API & Dashboard Server
FastAPI backend providing real-time AI curve prediction, physics validation,
preset loading, and digital audit certificate export.
"""

import os
import sys
import json
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
sys.path.insert(0, DATA_DIR)

from src.config import OVEN_SPECS, SENSORS, SENSOR_COLS, SENSOR_NAMES, VEHICLE_MODELS
from src.pipeline import VirtualEMTSystem
from src.standard_curve_library import StandardCurveLibrary
from src.audit_report import AuditReportGenerator
from src.csv_pipeline import CSVPipeline

SAMPLE_DIR = os.path.join(DATA_DIR, "sample")
csv_pipeline = CSVPipeline()

app = FastAPI(
    title="Stellantis Virtual EMT — Predictive Paint Oven API",
    description="Automotive AI Predictive Validation System aligned with ISO 12944 & VDA 621-415",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Initialize Virtual EMT Physics & Validation System
system: VirtualEMTSystem = VirtualEMTSystem()
std_lib = StandardCurveLibrary()
audit_gen = AuditReportGenerator()

@app.on_event("startup")
def startup_event():
    print("[*] Virtual EMT Thermodynamic Physics & Validation Engine initialized.")

class ValidationRequest(BaseModel):
    oven_type: str = "ED"
    vehicle_model: str = "CC21"
    plc_zone1_setpoint_C: Optional[float] = None
    plc_zone2_setpoint_C: Optional[float] = None
    plc_zone3_setpoint_C: Optional[float] = None
    plc_zone4_setpoint_C: Optional[float] = None
    plc_zone5_setpoint_C: Optional[float] = None
    plc_fan_speed_pct: Optional[float] = None
    plc_conveyor_speed_m_min: Optional[float] = None
    plc_gas_pressure_mbar: Optional[float] = None
    plc_damper_pos_pct: Optional[float] = None
    plc_exhaust_fan_pct: Optional[float] = None
    plc_burner_state: Optional[int] = None
    plc_loading_vehicles: Optional[int] = None

@app.get("/api/status")
def get_system_status():
    """Return system readiness, available ovens, and specs."""
    return {
        "status": "ONLINE",
        "system_name": "Stellantis Virtual EMT Predictive Paint Validation",
        "standards": ["ISO 12944", "VDA 621-415", "Ford FLTM BI 106-01"],
        "oven_types": list(OVEN_SPECS.keys()),
        "vehicle_models": VEHICLE_MODELS,
        "sensor_count": len(SENSORS),
        "sensors": SENSORS,
        "oven_specs": OVEN_SPECS
    }

@app.get("/api/presets")
def get_presets():
    """Return standard plant operation scenarios for testing."""
    return {
        "normal_ed": {
            "name": "Normal Production Run (ED Oven)",
            "description": "Standard nominal parameters for CC21 primer curing.",
            "data": {
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
                "plc_loading_vehicles": 5
            }
        },
        "conveyor_fast": {
            "name": "Conveyor Overspeed (Topcoat Oven)",
            "description": "Line speed 2.82 m/min exceeds 2.2 m/min limit -> risk of undercure.",
            "data": {
                "oven_type": "TOPCOAT",
                "vehicle_model": "CC51",
                "plc_zone1_setpoint_C": 110.2,
                "plc_zone2_setpoint_C": 134.8,
                "plc_zone3_setpoint_C": 145.1,
                "plc_zone4_setpoint_C": 144.9,
                "plc_zone5_setpoint_C": 130.4,
                "plc_fan_speed_pct": 84.1,
                "plc_conveyor_speed_m_min": 2.85,
                "plc_gas_pressure_mbar": 49.5,
                "plc_damper_pos_pct": 48.0,
                "plc_exhaust_fan_pct": 75.0,
                "plc_burner_state": 1,
                "plc_loading_vehicles": 6
            }
        },
        "burner_trip": {
            "name": "Burner Flameout / Low Pressure (ED Oven)",
            "description": "Burner tripped, gas supply pressure dropped to 34 mbar -> severe failure.",
            "data": {
                "oven_type": "ED",
                "vehicle_model": "CC31",
                "plc_zone1_setpoint_C": 128.0,
                "plc_zone2_setpoint_C": 158.5,
                "plc_zone3_setpoint_C": 169.2,
                "plc_zone4_setpoint_C": 168.0,
                "plc_zone5_setpoint_C": 155.0,
                "plc_fan_speed_pct": 82.0,
                "plc_conveyor_speed_m_min": 2.22,
                "plc_gas_pressure_mbar": 34.2,
                "plc_damper_pos_pct": 28.0,
                "plc_exhaust_fan_pct": 52.0,
                "plc_burner_state": 0,
                "plc_loading_vehicles": 4
            }
        },
        "fan_degradation": {
            "name": "Airflow Imbalance / Fan Degradation (Sealer Oven)",
            "description": "Recirculation fan speed low (58%) -> high thermal gradient across body.",
            "data": {
                "oven_type": "SEALER",
                "vehicle_model": "CC41",
                "plc_zone1_setpoint_C": 119.5,
                "plc_zone2_setpoint_C": 149.8,
                "plc_zone3_setpoint_C": 164.2,
                "plc_zone4_setpoint_C": 165.1,
                "plc_zone5_setpoint_C": 150.0,
                "plc_fan_speed_pct": 58.5,
                "plc_conveyor_speed_m_min": 2.20,
                "plc_gas_pressure_mbar": 50.1,
                "plc_damper_pos_pct": 40.0,
                "plc_exhaust_fan_pct": 60.0,
                "plc_burner_state": 1,
                "plc_loading_vehicles": 5
            }
        },
        "burner_overshoot": {
            "name": "Overcure / High Peak Temp (Sealer Oven)",
            "description": "Zone setpoints set too high (+25°C) -> paint film yellowing/burning risk.",
            "data": {
                "oven_type": "SEALER",
                "vehicle_model": "CC21",
                "plc_zone1_setpoint_C": 138.0,
                "plc_zone2_setpoint_C": 172.0,
                "plc_zone3_setpoint_C": 185.0,
                "plc_zone4_setpoint_C": 186.0,
                "plc_zone5_setpoint_C": 170.0,
                "plc_fan_speed_pct": 88.0,
                "plc_conveyor_speed_m_min": 2.05,
                "plc_gas_pressure_mbar": 54.0,
                "plc_damper_pos_pct": 55.0,
                "plc_exhaust_fan_pct": 80.0,
                "plc_burner_state": 1,
                "plc_loading_vehicles": 5
            }
        }
    }

@app.get("/api/standard-curve/{oven_type}/{vehicle_model}")
def get_standard_curve(oven_type: str, vehicle_model: str = "CC21"):
    """Fetch the golden standard curve and upper/lower guard bands."""
    if oven_type not in OVEN_SPECS:
        raise HTTPException(status_code=400, detail=f"Invalid oven type: {oven_type}")
    
    curve_data = std_lib.get_standard_curve(oven_type, vehicle_model)
    return {
        "oven_type": curve_data["oven_type"],
        "vehicle_model": curve_data["vehicle_model"],
        "time_s": curve_data["time_s"].tolist(),
        "time_min": curve_data["time_min"].tolist(),
        "standard_temp_C": curve_data["standard_temp_C"].tolist(),
        "lower_limit_C": curve_data["lower_limit_C"].tolist(),
        "upper_limit_C": curve_data["upper_limit_C"].tolist(),
        "cure_threshold": curve_data["cure_threshold"],
        "zones": curve_data["zones"]
    }

@app.post("/api/predict")
def predict_virtual_emt(req: ValidationRequest):
    """
    Run full end-to-end Virtual EMT thermodynamic prediction and physical quality validation.
    """
    inputs = req.model_dump()
    try:
        result = system.validate_trial(inputs)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")

@app.post("/api/export-certificate")
def export_certificate(req: ValidationRequest):
    """Generate and return standalone printable HTML Quality Certificate."""
    inputs = req.model_dump()
    result = system.validate_trial(inputs)
    trial_id = f"VIRTUAL-{inputs['oven_type']}-{int(inputs['plc_conveyor_speed_m_min']*100)}"
    
    html = audit_gen.generate_html_report(
        validation_result=result["quality_audit"],
        trial_id=trial_id,
        plc_inputs=inputs,
        full_result=result
    )
    return HTMLResponse(content=html, status_code=200)

class CSVValidationRequest(BaseModel):
    trial_csv: Optional[str] = None
    goal_csv: Optional[str] = None
    config_csv: Optional[str] = None
    sample_id: Optional[str] = None

@app.get("/api/sample-csvs")
def list_sample_csvs():
    """Return catalog of pre-packaged OEM sample CSV datasets."""
    samples = [
        {
            "id": "trial_normal_sample.csv",
            "name": "Normal Production Run (1s sampling)",
            "description": "Standard nominal parameters for CC21 primer curing. 2,401 rows (00:00 - 40:00).",
            "interval": "1 second",
            "expected_verdict": "GO (OK)",
            "badge": "Nominal 1s",
            "badge_color": "#50E3C2",
            "type": "trial"
        },
        {
            "id": "trial_ed_normal_15s.csv",
            "name": "Normal Production Run (15s sampling)",
            "description": "Standard plant logger with 15-second downsampling. 161 rows (00:00 - 40:00).",
            "interval": "15 seconds",
            "expected_verdict": "GO (OK)",
            "badge": "Nominal 15s",
            "badge_color": "#50E3C2",
            "type": "trial"
        },
        {
            "id": "trial_sparse_1min_sample.csv",
            "name": "Normal Production Run (1-Minute sampling)",
            "description": "Plant historian coarse export with 60-second sampling. 41 rows (00:00 - 40:00).",
            "interval": "60 seconds (1 min)",
            "expected_verdict": "GO (OK)",
            "badge": "Nominal 1 min",
            "badge_color": "#50E3C2",
            "type": "trial"
        },
        {
            "id": "trial_burner_trip_sample.csv",
            "name": "Burner Flameout / Low Gas Pressure",
            "description": "Zone 2 burner flameout, gas supply drops to 34.2 mbar -> severe undercure.",
            "interval": "1 second",
            "expected_verdict": "NG (NO-GO)",
            "badge": "Burner Trip",
            "badge_color": "#FF1744",
            "type": "trial"
        },
        {
            "id": "trial_conveyor_fast_sample.csv",
            "name": "Conveyor Line Overspeed (2.85 m/min)",
            "description": "Line speed 2.85 m/min exceeds 2.20 m/min limit -> shortened soak duration.",
            "interval": "1 second",
            "expected_verdict": "NG (NO-GO)",
            "badge": "Overspeed",
            "badge_color": "#FFA000",
            "type": "trial"
        },
        {
            "id": "trial_fan_degradation_sample.csv",
            "name": "Recirculation Fan Degradation (58% RPM)",
            "description": "Degraded fan airflow causing high cross-body thermal gradient > 25°C.",
            "interval": "1 second",
            "expected_verdict": "NG (NO-GO)",
            "badge": "Airflow Imbalance",
            "badge_color": "#FF5252",
            "type": "trial"
        },
        {
            "id": "trial_burner_overshoot_sample.csv",
            "name": "High Peak Overcure (+25°C Setpoint)",
            "description": "Zone setpoints overshooting nominal target -> paint film burning risk.",
            "interval": "1 second",
            "expected_verdict": "NG (NO-GO)",
            "badge": "Overcure Risk",
            "badge_color": "#FF1744",
            "type": "trial"
        }
    ]
    return {"samples": samples, "default_goal": "standard_goal_sample.csv", "default_config": "oven_vehicle_config_sample.csv"}

@app.get("/api/sample-csv/{filename}")
def get_sample_csv_content(filename: str):
    """Retrieve raw text content of a sample CSV file."""
    # Sanitize filename
    safe_name = os.path.basename(filename)
    path = os.path.join(SAMPLE_DIR, safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Sample CSV {safe_name} not found.")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(content=content, media_type="text/csv")

@app.post("/api/validate-csv")
def validate_csv(req: CSVValidationRequest):
    """
    Ingests Trial CSV, Standard Goal CSV, and Combined Config CSV.
    Executes dynamic gradient zone detection and full GO/NG validation.
    """
    try:
        # 1. Resolve Trial CSV
        if req.trial_csv and len(req.trial_csv.strip()) > 0:
            trial_source = req.trial_csv
        elif req.sample_id:
            sample_path = os.path.join(SAMPLE_DIR, os.path.basename(req.sample_id))
            if not os.path.exists(sample_path):
                raise HTTPException(status_code=404, detail=f"Sample {req.sample_id} not found.")
            with open(sample_path, "r", encoding="utf-8") as f:
                trial_source = f.read()
        else:
            default_trial = os.path.join(SAMPLE_DIR, "trial_normal_sample.csv")
            with open(default_trial, "r", encoding="utf-8") as f:
                trial_source = f.read()

        # 2. Resolve Goal CSV
        if req.goal_csv and len(req.goal_csv.strip()) > 0:
            goal_source = req.goal_csv
        else:
            default_goal = os.path.join(SAMPLE_DIR, "standard_goal_sample.csv")
            with open(default_goal, "r", encoding="utf-8") as f:
                goal_source = f.read()

        # 3. Resolve Config CSV
        if req.config_csv and len(req.config_csv.strip()) > 0:
            config_source = req.config_csv
        else:
            default_config = os.path.join(SAMPLE_DIR, "oven_vehicle_config_sample.csv")
            with open(default_config, "r", encoding="utf-8") as f:
                config_source = f.read()

        # Parse CSVs
        trial_data = csv_pipeline.parse_sensor_csv(trial_source)
        goal_data  = csv_pipeline.parse_sensor_csv(goal_source)
        config     = csv_pipeline.parse_config_csv(config_source)

        # Execute Validation & Dynamic Zone Detection
        result = csv_pipeline.validate_trial_against_goal(trial_data, goal_data, config)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"CSV Validation Error: {str(e)}")

@app.post("/api/export-csv-certificate")
def export_csv_certificate(req: CSVValidationRequest):
    """Generate printable HTML report for the CSV trial validation."""
    val_res = validate_csv(req)
    cfg = val_res.get("config_meta", {})
    stats = val_res.get("stats", {})
    verdict = val_res.get("verdict", "NG (NO-GO)")
    is_pass = val_res.get("is_pass", False)
    badge_bg = "#50E3C2" if is_pass else "#FF1744"
    badge_color = "#0A0D14" if is_pass else "#FFFFFF"

    # Build detected zone rows
    zone_rows = ""
    for z in val_res.get("zone_comparison_table", []):
        st_color = "#50E3C2" if z["status"] == "PASS" else ("#FFA000" if z["status"] == "WARN" else "#FF5252")
        zone_rows += f"""
        <tr>
            <td style="font-weight:600;">{z['name']}</td>
            <td>{z['stage']}</td>
            <td><code>{z['trial_timing']}</code> ({z['trial_duration']})</td>
            <td><code>{z['goal_timing']}</code> ({z['goal_duration']})</td>
            <td>{z['trial_peak_C']}°C</td>
            <td>{z['goal_peak_C']}°C</td>
            <td>{z['delta_peak_C']:+.1f}°C</td>
            <td style="color:{st_color}; font-weight:700;">{z['status']}</td>
        </tr>
        """

    # Build sensor rows
    sensor_rows = ""
    for s in val_res.get("sensor_audit_table", []):
        s_col = "#50E3C2" if s["status"] == "PASS" else "#FF5252"
        reasons = "<br>".join(s.get("failure_reasons", [])) or "None"
        sensor_rows += f"""
        <tr>
            <td style="font-weight:600;">{s['sensor']}</td>
            <td>{s['peak_temp_C']}°C</td>
            <td>{s['peak_time_mmss']}</td>
            <td>{s['cure_index']}</td>
            <td>{s['time_above_cure_min']} min</td>
            <td style="color:{s_col}; font-weight:700;">{s['status']}</td>
            <td style="font-size:11px; color:#9E9E9E;">{reasons}</td>
        </tr>
        """

    violations_html = ""
    if val_res.get("violations"):
        v_items = "".join([f"<li style='color:#FF5252; margin-bottom:4px;'><strong>[VIOLATION]</strong> {v}</li>" for v in val_res["violations"]])
        violations_html = f"<div style='background:#1a0f12; border:1px solid #FF5252; border-radius:6px; padding:12px; margin-top:16px;'><strong style='color:#FF5252;'>Compliance Violations Detected:</strong><ul style='margin-top:6px; padding-left:20px;'>{v_items}</ul></div>"

    html = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Stellantis Virtual EMT — Quality Certificate</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0e14; color: #E0E0E0; margin: 0; padding: 24px; }}
            .container {{ max-width: 960px; margin: 0 auto; background: #121722; border: 1px solid #232c3d; border-radius: 8px; padding: 32px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }}
            .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #232c3d; padding-bottom: 16px; margin-bottom: 24px; }}
            .brand {{ font-size: 20px; font-weight: 800; letter-spacing: 1px; color: #FFFFFF; }}
            .sub {{ font-size: 11px; color: #4A90E2; font-family: monospace; letter-spacing: 1.5px; }}
            .verdict-pill {{ background: {badge_bg}; color: {badge_color}; font-size: 16px; font-weight: 800; padding: 8px 18px; border-radius: 20px; display: inline-block; letter-spacing: 0.5px; }}
            .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
            .kpi-card {{ background: #171e2c; border: 1px solid #232c3d; border-radius: 6px; padding: 14px; }}
            .kpi-title {{ font-size: 11px; color: #8C9BAE; text-transform: uppercase; font-weight: 600; margin-bottom: 6px; }}
            .kpi-val {{ font-size: 22px; font-weight: 700; color: #FFFFFF; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
            th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #1f2737; }}
            th {{ background: #171e2c; color: #8C9BAE; font-size: 11px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }}
            code {{ font-family: monospace; color: #4A90E2; }}
            .section-title {{ font-size: 14px; font-weight: 700; color: #FFFFFF; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 28px; margin-bottom: 8px; border-left: 3px solid #4A90E2; padding-left: 8px; }}
            @media print {{ body {{ background: #FFF; color: #000; }} .container {{ background: #FFF; border: none; box-shadow: none; padding: 0; }} th {{ background: #EEE; color: #000; }} td {{ border-bottom: 1px solid #DDD; }} }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div>
                    <div class="brand">STELLANTIS VIRTUAL EMT</div>
                    <div class="sub">AUTOMATIC PAINT OVEN ZONE DETECTION & QUALITY AUDIT REPORT</div>
                </div>
                <div>
                    <span class="verdict-pill">{verdict}</span>
                </div>
            </div>

            <div style="font-size: 12px; color: #8C9BAE; margin-bottom: 20px; line-height: 1.6;">
                <strong>Process Purpose:</strong> {cfg.get('process_purpose', 'ED Oven')} &nbsp;|&nbsp;
                <strong>Body Platform:</strong> {cfg.get('body_platform_name', 'CC21')} &nbsp;|&nbsp;
                <strong>Max Transit Time:</strong> 00:00 – 40:00 (2400s) &nbsp;|&nbsp;
                <strong>Cure Threshold:</strong> {cfg.get('cure_threshold', 165.0)}°C &nbsp;|&nbsp;
                <strong>Quality Tier:</strong> {val_res.get('quality_tier', 'GOLD TIER')}
            </div>

            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-title">Cure Quality Index (CQI)</div>
                    <div class="kpi-val" style="color:#4A90E2;">{val_res.get('cqi_score', 0)}%</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Cross-Body Thermal Spread</div>
                    <div class="kpi-val">{stats.get('thermal_spread_C', 0)}°C</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Min Arrhenius Cure Index</div>
                    <div class="kpi-val">{stats.get('min_cure_index', 0)}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-title">Mean Deviation from Goal</div>
                    <div class="kpi-val">{stats.get('mean_deviation_from_goal_C', 0)}°C</div>
                </div>
            </div>

            {violations_html}

            <div class="section-title">1. Dynamically Detected Oven Process Zones (Trial vs Standard Goal)</div>
            <table>
                <thead>
                    <tr>
                        <th>Zone</th>
                        <th>Process Stage</th>
                        <th>Trial Timing (0-40m)</th>
                        <th>Goal Benchmark</th>
                        <th>Trial Peak</th>
                        <th>Goal Peak</th>
                        <th>Δ Peak</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {zone_rows}
                </tbody>
            </table>

            <div class="section-title">2. 12-Sensor Effective Metal Temperature (EMT) Audit</div>
            <table>
                <thead>
                    <tr>
                        <th>Sensor Channel</th>
                        <th>Peak Temp (°C)</th>
                        <th>Time at Peak</th>
                        <th>Arrhenius CI</th>
                        <th>Time &gt; Threshold</th>
                        <th>Status</th>
                        <th>Notes / Boundary Flags</th>
                    </tr>
                </thead>
                <tbody>
                    {sensor_rows}
                </tbody>
            </table>

            <div style="margin-top: 32px; font-size: 11px; color: #5C6B7E; border-top: 1px solid #1f2737; padding-top: 14px; text-align: center;">
                Generated by Stellantis Virtual EMT Predictive Platform • Aligned with ISO 12944, VDA 621-415, and Ford FLTM BI 106-01 • Timestamp: 0 to 40 min range invariant.
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)

# Serve static dashboard assets
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Stellantis Virtual EMT Dashboard</h1><p>Static files loading...</p>"

if __name__ == "__main__":
    import uvicorn
    print("[*] Starting Stellantis Virtual EMT Server on http://localhost:8000 ...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
