# 🏭 PROJECT: Virtual EMT — Predictive Paint Oven Validation System
### Client: **Stellantis** | Domain: **Automotive Paint Shop AI/ML**

---

## 📌 Executive Summary

Stellantis currently performs physical **EMT (Effective Metal Temperature)** validation in paint shop ovens using sensor-based equipment installed on vehicle bodies. This is a **manual, time-consuming, and resource-intensive** process. The goal of this project is to build an **AI/ML-powered Virtual EMT system** that learns from historical oven data and predicts whether a paint curing cycle will pass (**OK**) or fail (**NG**) — without needing to physically install the EMT hardware for every validation cycle.

---

## 🔍 Problem Statement Analysis

### Process Context (Paint Shop Flow)
```
BIW / Car Body → PT/ED Process → ED Oven → Sealer Application → Sealer Oven
                                                                        ↓
To Assembly ← Repair ← Inspection Station ← Topcoat Oven ← Topcoat Booth
```

### Three Oven Types in Scope
| Oven Type | Purpose |
|---|---|
| **ED Oven** | Cures the electrodeposition primer (~180–200°C) |
| **Sealer Oven** | Cures the body sealer compound |
| **Topcoat Oven** | Cures the final visible paint layer |

### Core Formula
> **Correct Temperature + Correct Time + Uniform Airflow = Proper Curing → Required Paint Quality & Durability**

---

## 🚨 Problem Statement (Detailed)

### Current Pain Points
| # | Issue | Impact |
|---|---|---|
| 1 | EMT system physically installed on vehicle body | Time delay, resource cost |
| 2 | Manual data collection via physical oven trial | Operator dependency |
| 3 | Any deviation → NG result → Repeat trial | Downtime, cost escalation |
| 4 | Multiple oven parameters affect outcome | Complex root cause analysis |
| 5 | No predictive early warning system | Reactive, not proactive |

### Variables That Affect Oven Temperature Profile
- Filter choking / airflow restriction
- Gas pressure fluctuations
- Burner / gas train malfunction
- Fan performance degradation
- Damper position variation
- Oven temperature sensor malfunction
- Exhaust airflow variation
- Conveyor speed variation
- Vehicle body model variation
- Loading variation (number of vehicles in oven)

### Current Workflow (Manual)
```
Oven Trial → Physical EMT Installation → Vehicle Passage → Data Collection (Graph) → Analysis → OK/NG Decision
```

### Proposed AI Workflow
```
Real-Time Oven Data → AI Virtual Prediction → Virtual EMT Curve → Standard Comparison → OK/NG → Early Warning
```

---

## 📊 Sample Data Analysis (ST3.jpg — BYK Gardner EMT System)

From the actual EMT data file observed (`ED OVEN AUG 3/08/2026`):

### Key Data Points Available
| Field | Value |
|---|---|
| Product | CC21 |
| Site | TRL |
| Sampling Rate | 1 second |
| Trigger Mode | Threshold 120°C |
| Duration | 24:00:00 |
| Target Range (Comments) | 180–195°C |

### Sensor Locations Tracked (Oven Zone Architecture)
- **Legacy Physical EMT Trial (Offline Baseline, ST3.jpg)**: 12 thermocouples were physically taped to fixed body points (`LH Hood, LH Fender, LH Front Door, LH Rear Door, LH Q/P, LH T/G, RH T/G, RH Q/P, RH Rear Door, RH FR Door, RH Fender, RH Hood`).
- **Modern Virtual EMT System (Continuous Production)**: Temperature is measured with the **stationary temperature sensors in the oven zones**, predicting metal thermal curves:
  - **Zone 1 (Entry Ramp)**: `Zone 1 - Upper Air`, `Zone 1 - Lower Air`
  - **Zone 2 (Preheat Zone)**: `Zone 2 - LH Wall`, `Zone 2 - RH Wall`
  - **Zone 3 (Soak Zone)**: `Zone 3 - Upper Roof`, `Zone 3 - Mid Wall`, `Zone 3 - Lower Air`
  - **Zone 4 (Cure Hold Zone)**: `Zone 4 - Upper Roof`, `Zone 4 - Mid Wall`, `Zone 4 - Lower Air`
  - **Zone 5 (Cooling Exit)**: `Zone 5 - Lower Air`, `Zone 5 - Upper Exit`

### Critical Value Thresholds
| Zone | Temperature |
|---|---|
| Min | 0.0°C |
| Low | 150.0°C |
| Mid | 165.0°C |
| High | 185.0°C |
| Max | 0.0°C |
| Equivalent Time | 15:00 min |

### Observed Cure Index Range
- Sensors show **Cure Index: 233–248** (all sensors)
- Peak temperatures: **195.6°C – 211.0°C** across all zones

---

## 🎯 Project Goals

1. **Virtual EMT Prediction**: Predict the EMT temperature profile using real-time oven operational data (temperature setpoints, burner state, fan speed, conveyor speed, etc.)
2. **OK/NG Classification**: Compare predicted curve against the standard curing curve and classify as OK or NG
3. **Early Warning System**: Flag deviations before the oven cycle completes
4. **Root Cause Indication**: Identify which oven parameter is likely causing a deviation

---

## 🏗️ Proposed Solution Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAYER                               │
│  Historical EMT Records + Oven PLC Data + Process Params   │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                  FEATURE ENGINEERING                        │
│  Time-series features, Temperature gradients, Zone mapping  │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│               AI/ML MODEL LAYER                             │
│  LSTM / Transformer for curve prediction                    │
│  Random Forest / XGBoost for OK/NG classification          │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│               VALIDATION ENGINE                             │
│  Standard Curve Comparison, Cure Index Calculation,        │
│  Threshold Checking (Low/Mid/High/Max zones)               │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│               DASHBOARD / UI                                │
│  Real-time EMT Curve Display, OK/NG Status,                │
│  Early Warning Alerts, Root Cause Hints                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📐 Technical Stack

| Layer | Technology |
|---|---|
| **Data Ingestion** | Python (pandas, openpyxl for .mdb/.csv EMT files) |
| **Feature Engineering** | Python (scipy, numpy, sklearn preprocessing) |
| **Time-Series Prediction Model** | LSTM (Keras/TensorFlow) or Temporal Fusion Transformer |
| **Classification Model** | XGBoost / Random Forest / LightGBM |
| **Cure Index Calculation** | Custom physics-based formula engine |
| **Backend API** | FastAPI (Python) |
| **Frontend Dashboard** | React.js + Recharts / Plotly for curve visualization |
| **Database** | PostgreSQL or TimescaleDB (for time-series) |
| **Deployment** | Docker + Streamlit (quick MVP) or React (production) |

---

## 🗓️ Project Roadmap (Phase-by-Phase)

### Phase 0: Discovery & Data Collection (Week 1–2)
- [ ] Gather historical EMT validation records (BYK Gardner .mdb files)
- [ ] Collect corresponding oven PLC data (temperature setpoints, burner, fan, conveyor speed)
- [ ] Map labeled OK/NG outcomes for each historical trial
- [ ] Define standard curing curves for all 3 oven types (ED, Sealer, Topcoat)
- [ ] Define cure index calculation method (Equivalent Time above 165°C / 180°C)
- **Deliverable**: Cleaned, labeled dataset

---

### Phase 1: Data Pipeline & EDA (Week 2–3)
- [ ] Build data ingestion pipeline (EMT file parser + PLC data merger)
- [ ] Perform Exploratory Data Analysis (EDA)
  - Temperature profile shapes per zone
  - Variance between OK and NG runs
  - Sensor-to-sensor correlation
  - Outlier detection (faulty sensor readings)
- [ ] Feature engineering:
  - Peak temperature per zone
  - Time above threshold (150/165/185°C)
  - Cure Index per sensor
  - Temperature ramp rate (dT/dt)
  - Airflow proxies (fan speed, damper position)
- **Deliverable**: Feature matrix + EDA report

---

### Phase 2: Model Development (Week 3–5)

#### 2A — Curve Prediction Model
- **Input**: Oven operational parameters (set temps, fan speed, conveyor speed, vehicle model, zone config)
- **Output**: Predicted EMT temperature curve (time-series per sensor location)
- **Algorithm**: LSTM or Temporal Fusion Transformer (TFT)
- **Validation metric**: RMSE, MAPE vs. actual EMT curves

#### 2B — OK/NG Classification Model
- **Input**: Predicted EMT curve features (cure index, peak temp, time above thresholds)
- **Output**: OK / NG binary prediction + confidence score
- **Algorithm**: XGBoost / Random Forest
- **Validation metric**: F1-Score, Precision, Recall, AUC-ROC

#### 2C — Root Cause Flagging (Rule Engine)
- If peak temp low → Check burner/gas pressure
- If ramp rate slow → Check fan/airflow
- If time-at-temp insufficient → Check conveyor speed
- **Algorithm**: Rule-based + SHAP explainability for ML models

- **Deliverable**: Trained, validated models with performance reports

---

### Phase 3: Validation Engine (Week 5–6)
- [ ] Build standard curve library (per oven type, per vehicle model)
- [ ] Implement cure index calculation engine
  - Formula: Equivalent time at cure temperature using Arrhenius equation or empirical threshold method
- [ ] Build threshold comparison logic (Low/Mid/High/Max zone checks)
- [ ] Generate automated OK/NG decision with supporting data
- **Deliverable**: Validation engine module

---

### Phase 4: Dashboard & UI (Week 6–8)

#### MVP Version (Streamlit — 1 week)
- Real-time EMT curve plot (predicted vs. standard)
- Sensor-wise breakdown (12 sensor locations)
- OK/NG verdict display with confidence score
- Cure Index table per sensor
- Parameter input form (oven settings for prediction)

#### Production Version (React — 2 weeks)
- Multi-oven support (ED / Sealer / Topcoat)
- Historical trial comparison view
- Early warning alert banner
- Root cause suggestion panel
- Export report to PDF

- **Deliverable**: Functional dashboard

---

### Phase 5: Integration & Testing (Week 8–10)
- [ ] Integrate with live PLC data feed (OPC-UA or MQTT from plant)
- [ ] Real-time prediction pipeline (streaming data → live curve update)
- [ ] End-to-end system testing with actual plant data
- [ ] UAT (User Acceptance Testing) with paint shop engineers
- [ ] Model retraining pipeline (as new EMT data comes in)
- **Deliverable**: Integrated system on staging environment

---

### Phase 6: Deployment & Handover (Week 10–12)
- [ ] Production deployment (on-premises server or cloud)
- [ ] Documentation (User manual, API docs, Model cards)
- [ ] Training for paint shop operators and engineers
- [ ] Monitoring setup (model drift detection, data quality alerts)
- [ ] Handover to Stellantis IT/Engineering team
- **Deliverable**: Production-ready system + knowledge transfer

---

## 📈 Key Performance Indicators (KPIs)

| KPI | Target |
|---|---|
| EMT Curve Prediction RMSE | < 3°C average |
| OK/NG Classification Accuracy | > 95% |
| False Negative Rate (NG classified as OK) | < 2% |
| Early Warning Lead Time | ≥ 10 min before end of cycle |
| System Response Time (prediction) | < 5 seconds |
| Reduction in Physical EMT Trials | > 70% |

---

## ⚠️ Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Insufficient historical EMT data | Medium | High | Start with 50+ labeled runs; use data augmentation |
| PLC integration complexity | High | Medium | Start with CSV/manual upload; live integration in Phase 5 |
| Model overfitting to specific vehicle model | Medium | High | Train on diverse vehicle models, add regularization |
| Plant network security restrictions | Medium | Medium | On-premises deployment, no cloud dependency |
| Operator adoption resistance | Low | Medium | Intuitive UI + pilot validation period |
| Sensor malfunction in training data | High | Medium | Data cleaning + anomaly detection in pipeline |

---

## 👥 Team Structure

| Role | Responsibility |
|---|---|
| **Project Manager** | Timeline, stakeholder communication, risk management |
| **Data Engineer** | EMT file parsing, PLC data integration, data pipeline |
| **ML Engineer (x2)** | LSTM curve prediction, XGBoost classification, model validation |
| **Backend Developer** | FastAPI, validation engine, cure index calculation |
| **Frontend Developer** | React dashboard, curve visualization, alert system |
| **Domain Expert (Paint Shop)** | Standard curve definition, OK/NG criteria, UAT |
| **QA Engineer** | System testing, edge case validation |

---

## 💰 Estimated Effort

| Phase | Duration | Team Members |
|---|---|---|
| Phase 0 — Discovery | 2 weeks | PM + Domain Expert + Data Eng |
| Phase 1 — Data Pipeline | 2 weeks | Data Eng + ML Eng |
| Phase 2 — Model Development | 3 weeks | ML Eng x2 |
| Phase 3 — Validation Engine | 2 weeks | Backend Dev + Domain Expert |
| Phase 4 — Dashboard | 2 weeks | Frontend Dev + Backend Dev |
| Phase 5 — Integration | 2 weeks | Full team |
| Phase 6 — Deployment | 2 weeks | DevOps + PM |
| **Total** | **~12–15 weeks** | **7 people** |

---

## 🎯 Immediate Next Steps (Week 1 Actions)

1. **Data Audit**: Collect all historical BYK Gardner EMT files (.mdb format) — minimum 100 labeled runs
2. **PLC Data Request**: Request oven operational logs from plant IT (conveyor speed, burner state, fan RPM, zone setpoints)
3. **Standard Curve Definition**: Work with paint engineering team to define the "golden" curing curve for each oven
4. **Tool Selection**: Confirm tech stack preferences (cloud vs. on-prem, Python approval)
5. **Kickoff Meeting**: Align all stakeholders on scope, timelines, and success criteria

---

## ✅ Success Criteria

The project will be considered **complete and successful** when:
1. The Virtual EMT system can predict the temperature curve for any input oven parameters within **±3°C RMSE**
2. OK/NG predictions match actual physical EMT results with **>95% accuracy**
3. The system provides an **early warning** (mid-cycle) at least 10 minutes before the oven cycle ends
4. The dashboard is live, accessible to plant engineers, and shows both predicted EMT curve and OK/NG verdict
5. Physical EMT trials are reduced by **>70%** in the validated oven types
6. The system is **documented and handed over** with retraining capability for new vehicle models

---

*Document prepared by: AI Project Manager | Date: September 2026 | Version: 1.0*
*Client: Stellantis | Project: Virtual EMT Predictive Paint Oven Validation System*
