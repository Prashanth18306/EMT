/**
 * Stellantis Virtual EMT — Interactive Dashboard Controller
 * Connects UI controls to the FastAPI backend, coordinates the canvas renderer,
 * and handles live parameter simulations and certificate exports.
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Chart Renderer
    const chart = new EMTChartRenderer('emt-chart-canvas', 'chart-tooltip');

    // State Variables
    let currentOven = 'ED';
    let currentVehicle = 'CC21';
    let currentStandardCurve = null;
    let currentValidationResult = null;
    let currentPresets = {};

    // 2. Setup Slider Display Listeners
    setupSliderListeners();

    // 3. Bind Control Buttons (Bind FIRST so buttons are always responsive)
    const runBtn = document.getElementById('btn-run-simulation');
    if (runBtn) {
        runBtn.addEventListener('click', (e) => {
            if (e) e.preventDefault();
            fetchAndRunSimulation();
        });
    }

    const presetBtn = document.getElementById('btn-load-preset');
    if (presetBtn) {
        presetBtn.addEventListener('click', (e) => {
            if (e) e.preventDefault();
            const select = document.getElementById('preset-select');
            const key = select ? select.value : '';
            if (key && currentPresets[key]) {
                applyPresetData(currentPresets[key].data);
                fetchAndRunSimulation();
            }
        });
    }

    // Oven type change -> update zone sliders to default nominal ranges
    const ovenSelect = document.getElementById('oven-type');
    if (ovenSelect) {
        ovenSelect.addEventListener('change', (e) => {
            currentOven = e.target.value;
            adjustNominalSlidersForOven(currentOven);
            fetchAndRunSimulation();
        });
    }

    const vehicleSelect = document.getElementById('vehicle-model');
    if (vehicleSelect) {
        vehicleSelect.addEventListener('change', (e) => {
            currentVehicle = e.target.value;
            fetchAndRunSimulation();
        });
    }

    // Chart Filter Controls
    const btnAll = document.getElementById('btn-view-all');
    if (btnAll) {
        btnAll.addEventListener('click', (e) => {
            setFilterActive(e.target);
            chart.setFilter('all');
            updateSensorChipsVisuals();
        });
    }

    const btnCore = document.getElementById('btn-view-core');
    if (btnCore) {
        btnCore.addEventListener('click', (e) => {
            setFilterActive(e.target);
            chart.setFilter('core');
            updateSensorChipsVisuals();
        });
    }

    const btnExtremity = document.getElementById('btn-view-extremity');
    if (btnExtremity) {
        btnExtremity.addEventListener('click', (e) => {
            setFilterActive(e.target);
            chart.setFilter('extremity');
            updateSensorChipsVisuals();
        });
    }

    const btnEnvelope = document.getElementById('btn-toggle-envelope');
    if (btnEnvelope) {
        btnEnvelope.addEventListener('click', (e) => {
            chart.showEnvelope = !chart.showEnvelope;
            e.target.textContent = chart.showEnvelope ? 'Hide Envelope' : 'Show Envelope';
            e.target.classList.toggle('active', chart.showEnvelope);
            chart.render();
        });
    }

    // Certificate & Telemetry Export
    const btnCert = document.getElementById('btn-export-cert');
    if (btnCert) btnCert.addEventListener('click', exportCertificate);

    const btnJson = document.getElementById('btn-export-json');
    if (btnJson) btnJson.addEventListener('click', exportTelemetryJSON);

    // 4. Load System Presets & Run Default Initial Simulation
    loadPresets().then(() => {
        fetchAndRunSimulation();
    }).catch(err => {
        console.warn("Preset prefetch failed, running default simulation:", err);
        fetchAndRunSimulation();
    });

    /* =========================================================================
       HELPER FUNCTIONS
       ========================================================================= */

    function setupSliderListeners() {
        const sliders = [
            { id: 'zone1-sp', badge: 'val-zone1' },
            { id: 'zone2-sp', badge: 'val-zone2' },
            { id: 'zone3-sp', badge: 'val-zone3' },
            { id: 'zone4-sp', badge: 'val-zone4' },
            { id: 'zone5-sp', badge: 'val-zone5' },
            { id: 'conv-speed', badge: 'val-conv' },
            { id: 'fan-speed', badge: 'val-fan' },
            { id: 'gas-press', badge: 'val-gas' },
            { id: 'damper-pos', badge: 'val-damper' },
            { id: 'exhaust-fan', badge: 'val-exhaust' },
        ];

        sliders.forEach(s => {
            const input = document.getElementById(s.id);
            const badge = document.getElementById(s.badge);
            if (input && badge) {
                input.addEventListener('input', () => {
                    badge.textContent = input.value;
                });
            }
        });
    }

    function setFilterActive(btn) {
        document.querySelectorAll('.chart-controls .btn').forEach(b => {
            if (b.id !== 'btn-toggle-envelope') b.classList.remove('active');
        });
        if (btn) btn.classList.add('active');
    }

    function adjustNominalSlidersForOven(oven) {
        if (oven === 'ED') {
            setSliderVal('zone1-sp', 140.5, 'val-zone1');
            setSliderVal('zone2-sp', 175.2, 'val-zone2');
            setSliderVal('zone3-sp', 190.1, 'val-zone3');
            setSliderVal('zone4-sp', 190.8, 'val-zone4');
            setSliderVal('zone5-sp', 180.3, 'val-zone5');
        } else if (oven === 'SEALER') {
            setSliderVal('zone1-sp', 120.0, 'val-zone1');
            setSliderVal('zone2-sp', 150.0, 'val-zone2');
            setSliderVal('zone3-sp', 165.0, 'val-zone3');
            setSliderVal('zone4-sp', 165.0, 'val-zone4');
            setSliderVal('zone5-sp', 150.0, 'val-zone5');
        } else if (oven === 'TOPCOAT') {
            setSliderVal('zone1-sp', 110.0, 'val-zone1');
            setSliderVal('zone2-sp', 135.0, 'val-zone2');
            setSliderVal('zone3-sp', 145.0, 'val-zone3');
            setSliderVal('zone4-sp', 145.0, 'val-zone4');
            setSliderVal('zone5-sp', 130.0, 'val-zone5');
        }
    }

    function setSliderVal(id, val, badgeId) {
        if (val === undefined || val === null) return;
        const el = document.getElementById(id);
        const badge = document.getElementById(badgeId);
        if (el) el.value = val;
        if (badge) badge.textContent = val;
    }

    function collectFormPayload() {
        return {
            oven_type: document.getElementById('oven-type')?.value || 'ED',
            vehicle_model: document.getElementById('vehicle-model')?.value || 'CC21',
            plc_zone1_setpoint_C: parseFloat(document.getElementById('zone1-sp')?.value || 140.5),
            plc_zone2_setpoint_C: parseFloat(document.getElementById('zone2-sp')?.value || 175.2),
            plc_zone3_setpoint_C: parseFloat(document.getElementById('zone3-sp')?.value || 190.1),
            plc_zone4_setpoint_C: parseFloat(document.getElementById('zone4-sp')?.value || 190.8),
            plc_zone5_setpoint_C: parseFloat(document.getElementById('zone5-sp')?.value || 180.3),
            plc_conveyor_speed_m_min: parseFloat(document.getElementById('conv-speed')?.value || 2.18),
            plc_fan_speed_pct: parseFloat(document.getElementById('fan-speed')?.value || 86.4),
            plc_gas_pressure_mbar: parseFloat(document.getElementById('gas-press')?.value || 51.2),
            plc_damper_pos_pct: parseFloat(document.getElementById('damper-pos')?.value || 52.0),
            plc_exhaust_fan_pct: parseFloat(document.getElementById('exhaust-fan')?.value || 78.5),
            plc_burner_state: document.getElementById('burner-state')?.checked ? 1 : 0,
            plc_loading_vehicles: 5
        };
    }

    function applyPresetData(data) {
        if (!data) return;
        const ovenEl = document.getElementById('oven-type');
        const vehEl = document.getElementById('vehicle-model');
        if (ovenEl) ovenEl.value = data.oven_type;
        if (vehEl) vehEl.value = data.vehicle_model;
        currentOven = data.oven_type;
        currentVehicle = data.vehicle_model;

        setSliderVal('zone1-sp', data.plc_zone1_setpoint_C, 'val-zone1');
        setSliderVal('zone2-sp', data.plc_zone2_setpoint_C, 'val-zone2');
        setSliderVal('zone3-sp', data.plc_zone3_setpoint_C, 'val-zone3');
        setSliderVal('zone4-sp', data.plc_zone4_setpoint_C, 'val-zone4');
        setSliderVal('zone5-sp', data.plc_zone5_setpoint_C, 'val-zone5');
        setSliderVal('conv-speed', data.plc_conveyor_speed_m_min, 'val-conv');
        setSliderVal('fan-speed', data.plc_fan_speed_pct, 'val-fan');
        setSliderVal('gas-press', data.plc_gas_pressure_mbar, 'val-gas');
        setSliderVal('damper-pos', data.plc_damper_pos_pct, 'val-damper');
        setSliderVal('exhaust-fan', data.plc_exhaust_fan_pct, 'val-exhaust');

        const burner = document.getElementById('burner-state');
        if (burner) burner.checked = (data.plc_burner_state === 1);
    }

    async function loadPresets() {
        try {
            const res = await fetch('/api/presets');
            if (res.ok) {
                currentPresets = await res.json();
            }
        } catch (e) {
            console.warn("Could not load presets:", e);
        }
    }

    /* =========================================================================
       MAIN INFERENCE API CALL & UI UPDATE
       ========================================================================= */

    async function fetchAndRunSimulation() {
        const runBtn = document.getElementById('btn-run-simulation');
        if (runBtn) {
            runBtn.innerHTML = '<span class="btn-icon">⏳</span> RUNNING VALIDATION...';
            runBtn.disabled = true;
        }

        try {
            const payload = collectFormPayload();
            currentOven = payload.oven_type;
            currentVehicle = payload.vehicle_model;

            // 1. Fetch Golden Standard Curve
            try {
                const stdRes = await fetch(`/api/standard-curve/${currentOven}/${currentVehicle}`);
                if (stdRes.ok) {
                    currentStandardCurve = await stdRes.json();
                }
            } catch (scErr) {
                console.warn("Standard curve fetch error:", scErr);
            }

            // 2. Fetch Prediction from AI Engine
            const predRes = await fetch('/api/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!predRes.ok) {
                throw new Error(`Inference error ${predRes.status}: ${await predRes.text()}`);
            }

            const result = await predRes.json();
            currentValidationResult = result;

            // 3. Update Dashboard Panels safely
            try { updateKPIBanner(result); } catch (e) { console.error("KPI update error:", e); }
            try { updateThermalChart(result, currentStandardCurve); } catch (e) { console.error("Chart update error:", e); }
            try { updateDiagnosticsPanel(result); } catch (e) { console.error("Diagnostics update error:", e); }
            try { updateAuditTable(result); } catch (e) { console.error("Audit table update error:", e); }

        } catch (err) {
            console.error("Simulation failed:", err);
            alert(`Virtual EMT Simulation Error: ${err.message}`);
        } finally {
            if (runBtn) {
                runBtn.innerHTML = '<span class="btn-icon">⚡</span> RUN VIRTUAL EMT VALIDATION';
                runBtn.disabled = false;
            }
        }
    }

    function updateKPIBanner(result) {
        const audit = result.quality_audit;
        if (!audit) return;
        const isPass = (result.verdict === 'OK');

        // Verdict Card
        const verdictCard = document.getElementById('kpi-verdict-card');
        const verdictPill = document.getElementById('verdict-pill');
        const verdictTitle = document.getElementById('verdict-title');
        const verdictSubtitle = document.getElementById('verdict-subtitle');

        if (verdictCard) verdictCard.className = `kpi-card verdict-card ${isPass ? 'status-pass' : 'status-fail'}`;
        if (verdictPill) verdictPill.textContent = audit.final_status || (isPass ? 'CERTIFIED PASS (OK)' : 'PROCESS REJECT (NG)');
        if (verdictTitle) verdictTitle.textContent = isPass ? 'Automotive Quality Pass' : 'Curing Quality Reject';
        if (verdictSubtitle) {
            const conf = typeof result.confidence_pct === 'number' ? result.confidence_pct.toFixed(1) : '95.0';
            const phys = audit.physics_verdict || (isPass ? 'Compliant' : 'Violations Detected');
            verdictSubtitle.textContent = `Dual-Verification: AI Model (${conf}%) + Physical Rules (${phys})`;
        }

        // CQI Card
        const cqiVal = typeof audit.cure_quality_index_pct === 'number' ? audit.cure_quality_index_pct : 85.0;
        const cqiEl = document.getElementById('cqi-value');
        if (cqiEl) cqiEl.textContent = `${cqiVal.toFixed(1)}%`;
        const cqiBar = document.getElementById('cqi-bar-fill');
        if (cqiBar) cqiBar.style.width = `${Math.min(cqiVal, 100)}%`;
        const cqiTier = document.getElementById('cqi-tier');
        if (cqiTier) cqiTier.textContent = audit.quality_tier || (cqiVal >= 90 ? 'GOLD TIER' : (cqiVal >= 75 ? 'SILVER TIER' : 'REJECT'));

        // Thermal Spread Card
        const spread = typeof audit.cross_body_spread_C === 'number' ? audit.cross_body_spread_C : (audit.cross_zone_spread_C || 10.0);
        const spreadEl = document.getElementById('kpi-spread-val');
        if (spreadEl) spreadEl.textContent = `${spread.toFixed(1)} °C`;
        const spreadTag = document.getElementById('spread-tag');
        if (spreadTag) {
            if (spread <= 18.0) {
                spreadTag.textContent = 'EXCELLENT';
                spreadTag.style.color = '#00E676';
            } else if (spread <= 22.0) {
                spreadTag.textContent = 'ACCEPTABLE';
                spreadTag.style.color = '#FFD700';
            } else {
                spreadTag.textContent = 'IMBALANCE (FAIL)';
                spreadTag.style.color = '#FF5252';
            }
        }

        // Min Cure Index Card
        const vm = result.virtual_metrics || {};
        const minCi = typeof vm.summary_min_ci === 'number' ? vm.summary_min_ci.toFixed(1) : '0.0';
        const ciEl = document.getElementById('kpi-ci-val');
        if (ciEl) ciEl.textContent = minCi;
    }

    function updateThermalChart(result, stdCurve) {
        if (!result || !result.time_series) return;
        const cureTh = stdCurve ? (stdCurve.cure_threshold || 165.0) : 165.0;
        chart.setData(result.time_series, stdCurve, cureTh);
        buildSensorChipsBar();
    }

    function buildSensorChipsBar() {
        const bar = document.getElementById('sensor-chips-bar');
        if (!bar) return;
        bar.innerHTML = '';

        for (const [sName, color] of Object.entries(chart.sensorColors)) {
            const chip = document.createElement('div');
            chip.className = `sensor-chip ${chart.activeSensors.has(sName) ? 'active' : ''}`;
            chip.dataset.sensor = sName;
            chip.style.setProperty('--chip-color', color);
            chip.innerHTML = `<span class="chip-color-dot" style="background:${color};"></span><span>${sName}</span>`;

            chip.addEventListener('click', () => {
                chart.toggleSensor(sName);
                chip.classList.toggle('active', chart.activeSensors.has(sName));
            });

            bar.appendChild(chip);
        }
    }

    function updateSensorChipsVisuals() {
        const chips = document.querySelectorAll('.sensor-chip');
        chips.forEach(chip => {
            const sName = chip.dataset.sensor || chip.textContent.trim();
            chip.classList.toggle('active', chart.activeSensors.has(sName));
        });
    }

    function updateDiagnosticsPanel(result) {
        const list = document.getElementById('subsystem-bars-list');
        if (list) {
            list.innerHTML = '';
            const subAttrs = result.subsystem_attribution || {};
            for (const [subName, score] of Object.entries(subAttrs)) {
                const sNum = Number(score) || 0;
                const isCrit = (sNum >= 35.0);
                const row = document.createElement('div');
                row.className = 'subsystem-row';
                row.innerHTML = `
                    <div class="subsystem-meta">
                        <span class="subsystem-name">${subName}</span>
                        <span class="subsystem-pct" style="color:${isCrit ? '#FF5252' : '#F4F7FC'};">${sNum.toFixed(1)}%</span>
                    </div>
                    <div class="subsystem-bar-track">
                        <div class="subsystem-bar-fill ${isCrit ? 'critical' : ''}" style="width: ${Math.min(sNum, 100)}%;"></div>
                    </div>
                `;
                list.appendChild(row);
            }
        }

        const remedyEl = document.getElementById('diag-remedy-text');
        if (remedyEl) remedyEl.textContent = result.recommended_action || 'Standard routine maintenance. Continue production.';

        const alertsBox = document.getElementById('alerts-scroll-box');
        const countBadge = document.getElementById('alerts-count-badge');
        const alerts = result.early_warning_alerts || [];

        if (countBadge) {
            countBadge.textContent = `${alerts.length} Active Alert${alerts.length === 1 ? '' : 's'}`;
            if (alerts.length > 0) {
                countBadge.style.background = 'rgba(227, 24, 55, 0.2)';
                countBadge.style.color = '#FF5252';
            } else {
                countBadge.style.background = 'rgba(0, 166, 81, 0.2)';
                countBadge.style.color = '#00E676';
            }
        }

        if (alertsBox) {
            if (alerts.length > 0) {
                let html = '';
                alerts.forEach(al => {
                    const isWarn = al.toLowerCase().includes('overspeed') || al.toLowerCase().includes('conveyor');
                    html += `
                        <div class="alert-item ${isWarn ? 'warning' : ''}">
                            <span>${isWarn ? '⚠️' : '🚨'}</span>
                            <div>${al}</div>
                        </div>
                    `;
                });
                alertsBox.innerHTML = html;
            } else {
                alertsBox.innerHTML = `
                    <div class="empty-alerts">
                        <span class="check-icon">✓</span>
                        <p>All thermal, kinetic, and actuator parameters are operating within nominal quality bounds.</p>
                    </div>
                `;
            }
        }
    }

    function updateAuditTable(result) {
        const audit = result.quality_audit;
        if (!audit) return;
        const tbody = document.getElementById('audit-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        const tableData = audit.zone_audit_table || audit.sensor_audit_table || [];
        tableData.forEach(s => {
            const tr = document.createElement('tr');
            const isPass = (s.status === 'PASS');
            const zoneName = s.zone || s.sensor || 'Zone';
            const stageName = s.stage || s.type || 'Process';
            const reasonsTitle = (!isPass && s.failure_reasons && s.failure_reasons.length > 0)
                ? `title="Failure: ${s.failure_reasons.join(' | ')}"`
                : '';
            tr.innerHTML = `
                <td><strong>${zoneName}</strong></td>
                <td><span class="tag">${stageName}</span></td>
                <td>${Number(s.peak_temp_C || 0).toFixed(1)} °C</td>
                <td style="font-family:'JetBrains Mono'">${s.peak_time || '00:00'}</td>
                <td><strong>${Number(s.cure_index || 0).toFixed(1)}</strong></td>
                <td>${Number(s.time_above_cure_min || 0).toFixed(2)} min</td>
                <td>${Number(s.equiv_time_min || 0).toFixed(2)} min</td>
                <td style="${(s.max_deviation_C || 0) > 6.5 ? 'color: #FF5252; font-weight: 700;' : ''}">${Number(s.max_deviation_C || 0).toFixed(1)} °C</td>
                <td><span class="${isPass ? 'pill-pass' : 'pill-fail'}" ${reasonsTitle}>${s.status}</span></td>
            `;
            tbody.appendChild(tr);
        });

        const passStr = audit.zone_pass_count ? `Pass Ratio: ${audit.zone_pass_count} Zones` : (audit.sensor_pass_count ? `Pass Ratio: ${audit.sensor_pass_count}` : 'Pass Ratio: 5 / 5 Zones');
        const chipPass = document.getElementById('chip-pass-ratio');
        if (chipPass) chipPass.textContent = passStr;
        const chipPeak = document.getElementById('chip-peak-range');
        if (chipPeak) chipPeak.textContent = `Peak: ${audit.peak_range_C || 'N/A'}`;
    }

    /* =========================================================================
       EXPORT ACTIONS
       ========================================================================= */

    async function exportCertificate() {
        const payload = collectFormPayload();
        try {
            const res = await fetch('/api/export-certificate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const htmlContent = await res.text();
                const blob = new Blob([htmlContent], { type: 'text/html' });
                const url = URL.createObjectURL(blob);
                const win = window.open(url, '_blank');
                if (!win) {
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `BYK_Gardner_EMT_Report_${payload.oven_type}_${payload.vehicle_model}.html`;
                    a.click();
                }
            } else {
                alert("Failed to export certificate.");
            }
        } catch (e) {
            console.error("Export cert failed:", e);
        }
    }

    function exportTelemetryJSON() {
        if (!currentValidationResult) {
            alert("No simulation results available to export.");
            return;
        }
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(currentValidationResult, null, 2));
        const a = document.createElement('a');
        a.href = dataStr;
        a.download = `Virtual_EMT_Telemetry_${currentOven}_${currentVehicle}.json`;
        a.click();
    }
});
