# Automotive Paint Oven — Standards & Specifications Reference
## Used for Stellantis Virtual EMT Project — Phase 0

---

## 1. Applicable Industry Standards

| Standard | Body | Scope |
|---|---|---|
| **ISO 12944-6** | ISO | Corrosion protection of steel — Performance requirements for paint systems |
| **ASTM D3363** | ASTM | Film hardness by pencil test (post-cure validation) |
| **ASTM D4541** | ASTM | Pull-off adhesion strength of coatings (post-cure) |
| **DIN 55633** | DIN | Paints and varnishes — Coating systems for hot-dip galvanized steel |
| **VDA 621-415** | VDA (German OEM) | Paint adhesion and climate testing for automotive coatings |
| **Ford FLTM BI 106-01** | Ford | Oven temperature profiling for paint cure validation |
| **SAE J2941** | SAE | Automotive paint — Performance test methods |
| **ISO 4628** | ISO | Evaluation of paint film degradation |
| **IEC 60068-2-14** | IEC | Thermal shock testing — relevant for oven temperature cycling |

---

## 2. Paint Oven Temperature Specifications (Industry-Derived)

### 2A — ED (Electrodeposition / Cathodic Dip) Oven
> Source: Industry standard for cathodic electrocoat (e-coat) curing

| Parameter | Value |
|---|---|
| **Target Metal Temperature** | 175°C – 200°C |
| **Typical Peak Temperature** | 185°C – 205°C |
| **Minimum Cure Threshold** | 165°C |
| **Time at Cure Temp (min)** | ≥ 20 minutes above 165°C |
| **Total Oven Cycle Time** | 35–45 minutes |
| **Ramp-up Rate** | 6–10°C/min |
| **Cooling Rate** | 8–15°C/min |
| **Zone Setpoints (typical)** | Z1: 140°C, Z2: 175°C, Z3: 190°C, Z4: 190°C, Z5: 180°C |
| **Conveyor Speed** | 3.0–5.0 m/min |
| **Cure Index (OK threshold)** | ≥ 220 |
| **Cure Index (NG threshold)** | < 200 |

### 2B — Sealer Oven
> Source: Sealant/PVC compound curing requirements (PPG, Sika, Henkel TDS)

| Parameter | Value |
|---|---|
| **Target Metal Temperature** | 140°C – 165°C |
| **Typical Peak Temperature** | 150°C – 170°C |
| **Minimum Cure Threshold** | 130°C |
| **Time at Cure Temp (min)** | ≥ 15 minutes above 130°C |
| **Total Oven Cycle Time** | 25–35 minutes |
| **Ramp-up Rate** | 5–8°C/min |
| **Zone Setpoints (typical)** | Z1: 120°C, Z2: 150°C, Z3: 165°C, Z4: 165°C, Z5: 150°C |
| **Conveyor Speed** | 3.5–5.5 m/min |
| **Cure Index (OK threshold)** | ≥ 180 |
| **Cure Index (NG threshold)** | < 160 |

### 2C — Topcoat Oven
> Source: Automotive clearcoat/basecoat curing (BASF, PPG, Axalta TDS)

| Parameter | Value |
|---|---|
| **Target Metal Temperature** | 130°C – 145°C |
| **Typical Peak Temperature** | 140°C – 155°C |
| **Minimum Cure Threshold** | 120°C |
| **Time at Cure Temp (min)** | ≥ 20 minutes above 120°C |
| **Total Oven Cycle Time** | 30–40 minutes |
| **Ramp-up Rate** | 4–7°C/min |
| **Zone Setpoints (typical)** | Z1: 110°C, Z2: 135°C, Z3: 145°C, Z4: 145°C, Z5: 130°C |
| **Conveyor Speed** | 3.0–5.0 m/min |
| **Cure Index (OK threshold)** | ≥ 160 |
| **Cure Index (NG threshold)** | < 140 |

---

## 3. Sensor Locations (12 Standard EMT Points — Stellantis BIW)

Based on BYK Gardner EMT standard placement for a sedan/hatchback body:

| Sensor ID | Location | Zone Sensitivity |
|---|---|---|
| S01 | LH Hood (Left Hand Hood) | High thermal mass |
| S02 | LH Fender | Medium |
| S03 | LH Front Door | Medium |
| S04 | LH Rear Door | Medium |
| S05 | LH Q/P (Quarter Panel) | Low — slow to heat |
| S06 | LH T/G (Tailgate) | Low — extremity |
| S07 | RH T/G (Right Hand Tailgate) | Low — extremity |
| S08 | RH Q/P (Quarter Panel) | Low — slow to heat |
| S09 | RH Rear Door | Medium |
| S10 | RH FR Door (Front Door) | Medium |
| S11 | RH Fender | Medium |
| S12 | RH Hood | High thermal mass |

---

## 4. Cure Index Calculation Method

### Method: Equivalent Time (Area-Under-Curve above Threshold)

The **Cure Index (CI)** is calculated as the equivalent exposure time above the minimum cure temperature, integrated over the full temperature-time profile.

```
CI = Σ [Δt × R(T)] for all t where T > T_threshold

Where:
  Δt        = time step (1 second in sampling)
  T         = measured metal temperature at time t
  T_threshold = minimum cure temperature (e.g., 165°C for ED Oven)
  R(T)      = cure rate factor at temperature T

Cure Rate Factor (Arrhenius approximation):
  R(T) = exp( (T - T_ref) / k )

Where:
  T_ref = reference temperature (e.g., 165°C)
  k     = empirical constant (typically 10–15 for automotive coatings)
```

### Simplified Linear Method (used in BYK Gardner software):
```
CI = Σ Δt  for all t where T ≥ T_threshold (in seconds)

Then convert to equivalent minutes:
  CI_minutes = CI / 60
```

### OK/NG Decision Logic:
```
For ED Oven:
  IF  (CI ≥ 220) AND (Peak_Temp ≥ 175°C) AND (Peak_Temp ≤ 210°C)
      AND (Time_above_165 ≥ 15 min) → RESULT = OK
  ELSE → RESULT = NG

  NG Sub-types:
    - UNDERCURE:  CI < 200  OR  Time_above_165 < 12 min
    - OVERCURE:   Peak_Temp > 215°C  OR  Time_above_185 > 30 min
    - UNEVEN:     Max(sensor_peaks) - Min(sensor_peaks) > 20°C
```

---

## 5. NG Failure Modes & Root Causes

| NG Code | Failure Mode | Root Cause |
|---|---|---|
| NG-01 | Peak temp too low (undercure) | Burner fault / gas pressure low |
| NG-02 | Peak temp too high (overcure) | Burner overshoot / sensor fault |
| NG-03 | Time-at-temp insufficient | Conveyor speed too high |
| NG-04 | Uneven temp distribution | Fan fault / airflow restriction |
| NG-05 | Slow ramp rate | Filter choke / damper restriction |
| NG-06 | Temperature drop mid-cycle | Intermittent burner fault |
| NG-07 | Zone-specific low temp | Individual zone burner/fan issue |
| NG-08 | All sensors consistently low | Global oven setting error |

---

## 6. Vehicle Models (Stellantis Equivalent Reference)

| Model Code | Vehicle Type | Body Style | Thermal Profile Class |
|---|---|---|---|
| CC21 | Compact Sedan | Steel BIW | Standard |
| CC31 | SUV / Crossover | Steel BIW | High Mass |
| CC41 | Hatchback | Steel BIW | Light |
| CC51 | Van / Utility | Steel BIW + Reinforced | Extra High Mass |
| CC61 | Premium Sedan | Steel + Aluminium | Mixed Thermal |

---

## 7. Process Parameter Ranges (PLC Data)

| Parameter | Normal Range | NG Trigger Range |
|---|---|---|
| Zone 1 Setpoint | 130–150°C | < 120°C or > 160°C |
| Zone 2 Setpoint | 165–185°C | < 150°C or > 195°C |
| Zone 3 Setpoint | 180–200°C | < 165°C or > 215°C |
| Zone 4 Setpoint | 180–200°C | < 165°C or > 215°C |
| Zone 5 Setpoint | 165–185°C | < 150°C or > 195°C |
| Fan Speed (%) | 70–100% | < 60% |
| Conveyor Speed (m/min) | 3.0–5.0 | > 5.5 or < 2.5 |
| Gas Pressure (mbar) | 15–25 mbar | < 12 mbar |
| Damper Position (%) | 30–70% | < 20% or > 85% |
| Exhaust Fan Speed (%) | 60–90% | < 50% |
| Burner State | ON (1) | OFF/Fault (0) |

---

*Reference compiled from: ISO 12944, VDA 621-415, Ford FLTM BI 106-01, ASTM D3363/D4541,*
*BYK Gardner Application Notes, PPG/BASF/Axalta paint TDS sheets, ResearchGate automotive curing papers.*
*Adapted for Stellantis Virtual EMT Project — Phase 0 synthetic dataset generation.*
