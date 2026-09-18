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


# Load AI System
MODELS_DIR = os.path.join(DATA_DIR, "models")
system: Optional[VirtualEMTSystem] = None
std_lib = StandardCurveLibrary()
audit_gen = AuditReportGenerator()

@app.on_event("startup")
def startup_event():
    global system
    print("[*] Loading Virtual EMT AI Models into memory...")
    try:
        system = VirtualEMTSystem.load(MODELS_DIR)
        print("    [OK] AI Models and Validation Engine successfully loaded.")
    except Exception as e:
        print(f"    [!] Error loading models: {e}")

class ValidationRequest(BaseModel):
    oven_type: str = "ED"
    vehicle_model: str = "CC21"
    plc_zone1_setpoint_C: float = 140.0
    plc_zone2_setpoint_C: float = 175.0
    plc_zone3_setpoint_C: float = 190.0
    plc_zone4_setpoint_C: float = 190.0
    plc_zone5_setpoint_C: float = 180.0
    plc_fan_speed_pct: float = 85.0
    plc_conveyor_speed_m_min: float = 2.20
    plc_gas_pressure_mbar: float = 50.0
    plc_damper_pos_pct: float = 50.0
    plc_exhaust_fan_pct: float = 75.0
    plc_burner_state: int = 1
    plc_loading_vehicles: int = 5

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
    Run full end-to-end Virtual EMT AI prediction and physical quality validation.
    """
    global system
    if system is None:
        try:
            system = VirtualEMTSystem.load(MODELS_DIR)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load Virtual EMT System: {str(e)}")

    inputs = req.dict()
    try:
        result = system.validate_trial(inputs)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")

@app.post("/api/export-certificate")
def export_certificate(req: ValidationRequest):
    """Generate and return standalone printable HTML Quality Certificate."""
    global system
    if system is None:
        system = VirtualEMTSystem.load(MODELS_DIR)

    inputs = req.dict()
    result = system.validate_trial(inputs)
    trial_id = f"VIRTUAL-{inputs['oven_type']}-{int(inputs['plc_conveyor_speed_m_min']*100)}"
    
    html = audit_gen.generate_html_report(
        validation_result=result["quality_audit"],
        trial_id=trial_id,
        plc_inputs=inputs,
        full_result=result
    )
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
