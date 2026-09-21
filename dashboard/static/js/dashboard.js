/**
 * Stellantis Virtual EMT — 100% CSV-Driven Dashboard Controller
 * Connects UI file dropzones, OEM benchmark presets, and chart renderer
 * to the FastAPI backend (/api/validate-csv and /api/export-csv-certificate).
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Chart Renderer
    const chart = new EMTChartRenderer('emt-chart-canvas', 'chart-tooltip');

    // State Variables
    let activeTrialCSV = null;
    let activeGoalCSV = null;
    let activeConfigCSV = null;
    let currentSampleId = 'trial_normal_sample.csv';
    let lastValidationResult = null;

    // UI Element References
    const presetSelect = document.getElementById('preset-select');
    const btnLoadPreset = document.getElementById('btn-load-preset');
    const btnValidate = document.getElementById('btn-run-simulation');
    const btnExportCert = document.getElementById('btn-export-cert');
    const btnExportJson = document.getElementById('btn-export-json');

    // Dropzones & File Inputs
    const dropzoneTrial = document.getElementById('dropzone-trial');
    const fileTrialInput = document.getElementById('file-trial-csv');
    const pillTrial = document.getElementById('pill-trial-csv');
    const trialFileName = document.getElementById('trial-file-name');
    const trialFileMeta = document.getElementById('trial-file-meta');

    const dropzoneGoal = document.getElementById('dropzone-goal');
    const fileGoalInput = document.getElementById('file-goal-csv');
    const goalFileName = document.getElementById('goal-file-name');
    const goalFileMeta = document.getElementById('goal-file-meta');

    const dropzoneConfig = document.getElementById('dropzone-config');
    const fileConfigInput = document.getElementById('file-config-csv');
    const configFileName = document.getElementById('config-file-name');
    const configFileMeta = document.getElementById('config-file-meta');

    // KPI Elements
    const verdictCard = document.getElementById('kpi-verdict-card');
    const verdictPill = document.getElementById('verdict-pill');
    const verdictTitle = document.getElementById('verdict-title');
    const verdictSubtitle = document.getElementById('verdict-subtitle');
    const statusDot = document.getElementById('status-indicator-dot');

    const cqiValue = document.getElementById('cqi-value');
    const cqiBarFill = document.getElementById('cqi-bar-fill');
    const cqiTier = document.getElementById('cqi-tier');

    const kpiSpreadVal = document.getElementById('kpi-spread-val');
    const spreadTag = document.getElementById('spread-tag');

    const kpiCiVal = document.getElementById('kpi-ci-val');

    // Tables & Tabs
    const btnShowZonesTable = document.getElementById('btn-show-zones-table');
    const btnShowSensorsTable = document.getElementById('btn-show-sensors-table');
    const tableZonesContainer = document.getElementById('table-zones-container');
    const tableSensorsContainer = document.getElementById('table-sensors-container');
    const auditZonesBody = document.getElementById('audit-zones-body');
    const auditSensorsBody = document.getElementById('audit-sensors-body');

    // Diagnostics & Alerts
    const subsystemBarsList = document.getElementById('subsystem-bars-list');
    const diagRemedyText = document.getElementById('diag-remedy-text');
    const alertsScrollBox = document.getElementById('alerts-scroll-box');
    const alertsCountBadge = document.getElementById('alerts-count-badge');
    const sensorChipsBar = document.getElementById('sensor-chips-bar');

    // Filter Buttons
    const btnViewAll = document.getElementById('btn-view-all');
    const btnViewCore = document.getElementById('btn-view-core');
    const btnViewExtremity = document.getElementById('btn-view-extremity');
    const btnToggleEnvelope = document.getElementById('btn-toggle-envelope');

    // ── 2. Initialize Preset Catalog ─────────────────────────────────────
    async function loadPresetCatalog() {
        try {
            const res = await fetch('/api/sample-csvs');
            if (!res.ok) throw new Error("Failed to load sample catalog");
            const catalog = await res.json();
            
            if (presetSelect && catalog.samples) {
                presetSelect.innerHTML = "";
                catalog.samples.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.id;
                    opt.textContent = `[${s.expected_verdict === 'GO (OK)' ? 'PASS' : 'FAIL'}] ${s.name}`;
                    if (s.id === currentSampleId) opt.selected = true;
                    presetSelect.appendChild(opt);
                });
            }
        } catch (err) {
            console.warn("Using default preset dropdown:", err);
        }
    }

    // ── 3. File Drag & Drop Listeners ─────────────────────────────────────
    function setupDropzone(dropzone, fileInput, onFileLoaded) {
        if (!dropzone || !fileInput) return;

        dropzone.addEventListener('click', () => fileInput.click());

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });

        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('dragover');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleFile(e.dataTransfer.files[0], onFileLoaded);
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleFile(e.target.files[0], onFileLoaded);
            }
        });
    }

    function handleFile(file, callback) {
        if (!file.name.toLowerCase().endsWith('.csv')) {
            showToast(`Invalid file type. Please upload a .csv file.`, 'error');
            return;
        }

        const reader = new FileReader();
        reader.onload = (event) => {
            const content = event.target.result;
            callback(file.name, content);
        };
        reader.readAsText(file);
    }

    // Trial CSV handler
    setupDropzone(dropzoneTrial, fileTrialInput, (fileName, content) => {
        activeTrialCSV = content;
        currentSampleId = null; // override preset
        const lines = content.trim().split('\n');
        const rowCount = Math.max(lines.length - 1, 0);
        
        let intervalText = "custom";
        if (rowCount > 1000) intervalText = "1s interval";
        else if (rowCount > 100) intervalText = "15s interval";
        else intervalText = "60s interval";

        trialFileName.textContent = fileName;
        trialFileMeta.textContent = `${rowCount} rows • ${intervalText}`;
        pillTrial.style.display = "flex";

        showToast(`Loaded Trial CSV: ${fileName} (${rowCount} rows)`, 'success');
        runCSVValidation();
    });

    // Goal CSV handler
    setupDropzone(dropzoneGoal, fileGoalInput, (fileName, content) => {
        activeGoalCSV = content;
        const lines = content.trim().split('\n');
        goalFileName.textContent = fileName;
        goalFileMeta.textContent = `${Math.max(lines.length - 1, 0)} pts • custom target`;
        showToast(`Loaded Goal Benchmark CSV: ${fileName}`, 'success');
        runCSVValidation();
    });

    // Config CSV handler
    setupDropzone(dropzoneConfig, fileConfigInput, (fileName, content) => {
        activeConfigCSV = content;
        configFileName.textContent = fileName;
        configFileMeta.textContent = `Custom Oven/Vehicle Specs`;
        showToast(`Loaded Config CSV: ${fileName}`, 'success');
        runCSVValidation();
    });

    // ── 4. Preset Selection ──────────────────────────────────────────────
    if (presetSelect) {
        presetSelect.addEventListener('change', () => {
            currentSampleId = presetSelect.value;
            activeTrialCSV = null; // clear custom upload
            trialFileName.textContent = currentSampleId;
            trialFileMeta.textContent = currentSampleId.includes('1min') ? '41 rows • 60s' : (currentSampleId.includes('15s') ? '161 rows • 15s' : '2401 rows • 1s');
            pillTrial.style.display = "flex";
            runCSVValidation();
        });
    }

    if (btnLoadPreset) {
        btnLoadPreset.addEventListener('click', () => {
            if (presetSelect) {
                currentSampleId = presetSelect.value;
                activeTrialCSV = null;
                runCSVValidation();
            }
        });
    }

    if (btnValidate) {
        btnValidate.addEventListener('click', () => runCSVValidation());
    }

    // ── 5. Run CSV Validation Pipeline ───────────────────────────────────
    async function runCSVValidation() {
        setLoadingState(true);
        try {
            const payload = {
                trial_csv: activeTrialCSV,
                goal_csv: activeGoalCSV,
                config_csv: activeConfigCSV,
                sample_id: currentSampleId
            };

            const response = await fetch('/api/validate-csv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Validation failed");
            }

            const result = await response.json();
            lastValidationResult = result;
            updateDashboard(result);
            showToast(`Validation Complete: ${result.verdict} (CQI: ${result.cqi_score}%)`, result.is_pass ? 'success' : 'error');
        } catch (error) {
            console.error("Validation error:", error);
            showToast(`Error: ${error.message}`, 'error');
        } finally {
            setLoadingState(false);
        }
    }

    // ── 6. Update Dashboard UI with Telemetry ────────────────────────────
    function updateDashboard(result) {
        const isPass = result.is_pass;
        const verdict = result.verdict; // "GO (OK)" or "NG (NO-GO)"

        // 1. Update Verdict Card
        verdictCard.className = `kpi-card verdict-card ${isPass ? 'status-pass' : 'status-fail'}`;
        verdictPill.textContent = verdict;
        verdictPill.style.background = isPass ? "#00E676" : "#FF1744";
        verdictPill.style.color = isPass ? "#060A1D" : "#FFFFFF";

        statusDot.className = `status-indicator-dot ${isPass ? 'live-pulse' : 'fail-pulse'}`;
        statusDot.style.background = isPass ? "#00E676" : "#FF1744";

        verdictTitle.textContent = isPass ? "Automotive Quality Certified (GO)" : "Process Quality Reject (NO-GO)";
        verdictSubtitle.textContent = isPass 
            ? `Certified against OEM standard goal benchmark (${result.quality_tier})`
            : (result.violations.length > 0 ? result.violations[0] : "Physical criteria violated.");

        // 2. CQI Meter
        const cqi = result.cqi_score || 0;
        cqiValue.textContent = `${cqi.toFixed(1)}%`;
        cqiBarFill.style.width = `${Math.min(cqi, 100)}%`;
        cqiBarFill.style.background = isPass ? "linear-gradient(90deg, #00D2FF, #00E676)" : "linear-gradient(90deg, #FFA000, #FF1744)";
        cqiTier.textContent = result.quality_tier || (isPass ? "GOLD TIER" : "REJECT");
        cqiTier.style.color = isPass ? "#00E676" : "#FF1744";

        // 3. Thermal Spread
        const spread = result.stats.thermal_spread_C || 0;
        kpiSpreadVal.textContent = `${spread.toFixed(1)} °C`;
        if (spread <= 15.0) {
            spreadTag.textContent = "UNIFORM";
            spreadTag.style.color = "#00E676";
        } else if (spread <= 22.0) {
            spreadTag.textContent = "MODERATE";
            spreadTag.style.color = "#FFA000";
        } else {
            spreadTag.textContent = "IMBALANCE";
            spreadTag.style.color = "#FF1744";
        }

        // 4. Min Arrhenius Cure Index
        const minCi = result.stats.min_cure_index || 0;
        kpiCiVal.textContent = minCi.toFixed(1);
        kpiCiVal.style.color = minCi >= 22.0 ? "#00E676" : "#FF1744";

        // 5. Update Canvas Chart
        if (result.chart_series && result.trial_zones) {
            chart.setCSVData(
                result.chart_series,
                result.trial_zones,
                result.config_meta ? result.config_meta.cure_threshold : 165.0
            );
            buildSensorChips(chart);
        }

        // 6. Update Detected Zones Table
        if (auditZonesBody && result.zone_comparison_table) {
            auditZonesBody.innerHTML = "";
            result.zone_comparison_table.forEach(z => {
                const tr = document.createElement('tr');
                const badgeClass = z.status === 'PASS' ? 'badge-pass' : (z.status === 'WARN' ? 'badge-warn' : 'badge-fail');
                tr.innerHTML = `
                    <td style="font-weight:600;"><span class="zone-tag-indicator" style="background:${z.zone_id === 1 ? '#00E5FF' : (z.zone_id === 2 ? '#2979FF' : (z.zone_id === 3 ? '#E040FB' : (z.zone_id === 4 ? '#FF1744' : '#00E676')))}"></span>${z.name}</td>
                    <td>${z.stage}</td>
                    <td><code>${z.trial_timing}</code> <span style="font-size:10px; color:#8E9DBE;">(${z.trial_duration})</span></td>
                    <td><code>${z.goal_timing}</code> <span style="font-size:10px; color:#8E9DBE;">(${z.goal_duration})</span></td>
                    <td>${z.trial_peak_C}°C</td>
                    <td>${z.goal_peak_C}°C</td>
                    <td style="font-weight:600; color:${Math.abs(z.delta_peak_C) > 8 ? '#FF5252' : '#8E9DBE'};">${z.delta_peak_C > 0 ? '+' : ''}${z.delta_peak_C}°C</td>
                    <td><span class="${badgeClass}">${z.status}</span></td>
                `;
                auditZonesBody.appendChild(tr);
            });
        }

        // 7. Update 12-Sensor Details Table
        if (auditSensorsBody && result.sensor_audit_table) {
            auditSensorsBody.innerHTML = "";
            result.sensor_audit_table.forEach(s => {
                const tr = document.createElement('tr');
                tr.style.cursor = "pointer";
                tr.title = `Click to compare ${s.sensor} with Matching Standard Goal on the chart`;
                const deltaCol = (s.delta_peak_C !== undefined)
                    ? (Math.abs(s.delta_peak_C) > 8.0 ? '#FF5252' : (Math.abs(s.delta_peak_C) > 4.0 ? '#FFA000' : '#00E676'))
                    : '#8E9DBE';
                const deltaSign = (s.delta_peak_C > 0) ? '+' : '';
                const isComparingThis = chart.comparisonSensor === s.channel;
                tr.innerHTML = `
                    <td style="font-weight:600;"><span class="chip-color-dot" style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${chart.sensorColors[s.channel] || '#00D2FF'}; margin-right:6px;"></span>${s.sensor}</td>
                    <td><code>${s.channel}</code></td>
                    <td>${s.peak_temp_C}°C</td>
                    <td>${s.goal_peak_temp_C ? s.goal_peak_temp_C + '°C' : '—'}</td>
                    <td style="font-weight:700; color:${deltaCol};">${s.delta_peak_C !== undefined ? deltaSign + s.delta_peak_C + '°C' : '—'}</td>
                    <td>${s.peak_time_mmss}</td>
                    <td style="font-weight:700; color:${s.cure_index >= 20 ? '#00E676' : '#FF5252'};">${s.cure_index}</td>
                    <td><button class="btn btn-xs ${isComparingThis ? 'active' : ''}" style="padding:2px 8px; font-size:10px;">${isComparingThis ? 'Comparing' : 'Compare'}</button></td>
                `;
                tr.addEventListener('click', () => {
                    chart.setComparisonSensor(s.channel);
                    updateChipStyles(chart);
                    showToast(`Comparing ${s.sensor} vs Matching Standard Goal`, "info");
                    const chartElem = document.getElementById('emt-chart-canvas');
                    if (chartElem) chartElem.scrollIntoView({ behavior: 'smooth', block: 'center' });
                });
                auditSensorsBody.appendChild(tr);
            });
        }

        // 8. Operational SCADA Telemetry (Actuators)
        if (subsystemBarsList) {
            const ops = result.chart_series;
            // Generate telemetry rows
            subsystemBarsList.innerHTML = `
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 12px; margin-bottom: 12px;">
                    <div style="background:rgba(12,19,46,0.5); padding:10px; border-radius:6px; border:1px solid rgba(255,255,255,0.06);">
                        <span style="color:#8E9DBE; font-size:10.5px;">Mean Deviation from Goal:</span>
                        <div style="font-size:16px; font-weight:700; color:#00D2FF;">${result.stats.mean_deviation_from_goal_C}°C</div>
                    </div>
                    <div style="background:rgba(12,19,46,0.5); padding:10px; border-radius:6px; border:1px solid rgba(255,255,255,0.06);">
                        <span style="color:#8E9DBE; font-size:10.5px;">Sensor Pass Rate:</span>
                        <div style="font-size:16px; font-weight:700; color:${result.stats.sensor_pass_count >= 10 ? '#00E676' : '#FF5252'};">${result.stats.sensor_pass_count} / 12 Sensors</div>
                    </div>
                    <div style="background:rgba(12,19,46,0.5); padding:10px; border-radius:6px; border:1px solid rgba(255,255,255,0.06);">
                        <span style="color:#8E9DBE; font-size:10.5px;">Peak Metal Range:</span>
                        <div style="font-size:16px; font-weight:700;">${result.stats.min_peak_C}°C – ${result.stats.max_peak_C}°C</div>
                    </div>
                    <div style="background:rgba(12,19,46,0.5); padding:10px; border-radius:6px; border:1px solid rgba(255,255,255,0.06);">
                        <span style="color:#8E9DBE; font-size:10.5px;">Max Envelope Deviation:</span>
                        <div style="font-size:16px; font-weight:700; color:${result.stats.max_deviation_from_goal_C > 8.0 ? '#FF5252' : '#00E676'};">${result.stats.max_deviation_from_goal_C}°C</div>
                    </div>
                </div>
            `;

            diagRemedyText.textContent = isPass 
                ? "Process parameters conform to certified OEM automotive standards. Quality approved for continuous line production."
                : (result.violations.length > 0 ? `Corrective Action: ${result.violations[0]}` : "Line inspection required.");
        }

        // 9. Early Warning Alerts
        if (alertsScrollBox && alertsCountBadge) {
            if (result.violations && result.violations.length > 0) {
                alertsCountBadge.textContent = `${result.violations.length} Active Alerts`;
                alertsCountBadge.style.background = "rgba(255, 23, 68, 0.2)";
                alertsCountBadge.style.color = "#FF1744";

                alertsScrollBox.innerHTML = result.violations.map(v => `
                    <div style="display:flex; align-items:flex-start; gap:10px; padding:8px 10px; background:rgba(255,23,68,0.1); border:1px solid rgba(255,23,68,0.25); border-radius:6px; margin-bottom:8px; font-size:12px; color:#FF5252;">
                        <span style="font-weight:700; font-family:var(--font-mono); font-size:10.5px; background:rgba(255,23,68,0.25); padding:2px 6px; border-radius:3px; letter-spacing:0.5px;">ALERT</span>
                        <span>${v}</span>
                    </div>
                `).join('');
            } else {
                alertsCountBadge.textContent = "0 Active Alerts";
                alertsCountBadge.style.background = "rgba(0, 230, 118, 0.15)";
                alertsCountBadge.style.color = "#00E676";
                alertsScrollBox.innerHTML = `
                    <div class="empty-alerts">
                        <div class="status-indicator-tag" style="font-weight:700; font-family:var(--font-mono); font-size:11px; color:var(--status-ok); letter-spacing:1px; margin-bottom:6px;">[COMPLIANT]</div>
                        <p>All thermal, kinetic, and actuator parameters are currently operating within nominal quality bounds.</p>
                    </div>
                `;
            }
        }
    }

    // ── 7. Build Sensor Comparison Chips ──────────────────────────────────
    function buildSensorChips(chartInstance) {
        if (!sensorChipsBar) return;
        sensorChipsBar.innerHTML = "";

        // 1. "All 12 Sensors (Default)" chip
        const allChip = document.createElement('div');
        allChip.className = `sensor-chip chip-all ${chartInstance.comparisonSensor === null ? 'active' : ''}`;
        allChip.innerHTML = `
            <span class="chip-color-dot" style="background:#00D2FF;"></span>
            <span>All 12 Sensors (Default)</span>
        `;
        allChip.title = "Display all 12 sensors simultaneously against the standard goal benchmark";
        allChip.addEventListener('click', () => {
            chartInstance.setComparisonSensor(null);
            updateChipStyles(chartInstance);
            showToast("Displaying All 12 Sensors (Default)", "info");
        });
        sensorChipsBar.appendChild(allChip);

        // 2. Individual Sensor Chips S1 to S12
        for (let idx = 1; idx <= 12; idx++) {
            const sKey = `temperature_${idx}`;
            const color = chartInstance.sensorColors[sKey];
            const chip = document.createElement('div');
            const isComparing = chartInstance.comparisonSensor === sKey;
            chip.className = `sensor-chip ${isComparing ? 'active comparing' : ''}`;
            chip.dataset.sensorKey = sKey;
            chip.innerHTML = `
                <span class="chip-color-dot" style="background:${color};"></span>
                <span>S${idx}</span>
                ${isComparing ? '<span class="chip-compare-tag">VS STD</span>' : ''}
            `;
            chip.title = `Compare Sensor S${idx} directly with Matching Standard Goal`;
            chip.addEventListener('click', () => {
                chartInstance.setComparisonSensor(sKey);
                updateChipStyles(chartInstance);
            });
            sensorChipsBar.appendChild(chip);
        }
    }

    function updateChipStyles(chartInstance) {
        if (!sensorChipsBar) return;
        const chips = sensorChipsBar.querySelectorAll('.sensor-chip');
        chips.forEach(chip => {
            if (chip.classList.contains('chip-all')) {
                chip.classList.toggle('active', chartInstance.comparisonSensor === null);
            } else {
                const sKey = chip.dataset.sensorKey;
                const isComparing = chartInstance.comparisonSensor === sKey;
                chip.classList.toggle('active', isComparing);
                chip.classList.toggle('comparing', isComparing);
                const idx = sKey.replace('temperature_', '');
                const color = chartInstance.sensorColors[sKey];
                chip.innerHTML = `
                    <span class="chip-color-dot" style="background:${color};"></span>
                    <span>S${idx}</span>
                    ${isComparing ? '<span class="chip-compare-tag">VS STD</span>' : ''}
                `;
            }
        });
    }

    // ── 8. Table Tabs Switching ──────────────────────────────────────────
    if (btnShowZonesTable && btnShowSensorsTable) {
        btnShowZonesTable.addEventListener('click', () => {
            btnShowZonesTable.classList.add('active');
            btnShowSensorsTable.classList.remove('active');
            tableZonesContainer.style.display = 'block';
            tableSensorsContainer.style.display = 'none';
        });

        btnShowSensorsTable.addEventListener('click', () => {
            btnShowSensorsTable.classList.add('active');
            btnShowZonesTable.classList.remove('active');
            tableZonesContainer.style.display = 'none';
            tableSensorsContainer.style.display = 'block';
        });
    }

    // ── 9. Filter Controls ───────────────────────────────────────────────
    if (btnViewAll) {
        btnViewAll.addEventListener('click', () => {
            document.querySelectorAll('.chart-controls .btn').forEach(b => b.classList.remove('active'));
            btnViewAll.classList.add('active');
            chart.setComparisonSensor(null);
            updateChipStyles(chart);
            chart.setFilter('all');
            buildSensorChips(chart);
        });
    }
    if (btnViewCore) {
        btnViewCore.addEventListener('click', () => {
            document.querySelectorAll('.chart-controls .btn').forEach(b => b.classList.remove('active'));
            btnViewCore.classList.add('active');
            chart.setFilter('core');
            buildSensorChips(chart);
        });
    }
    if (btnViewExtremity) {
        btnViewExtremity.addEventListener('click', () => {
            document.querySelectorAll('.chart-controls .btn').forEach(b => b.classList.remove('active'));
            btnViewExtremity.classList.add('active');
            chart.setFilter('extremity');
            buildSensorChips(chart);
        });
    }
    if (btnToggleEnvelope) {
        btnToggleEnvelope.addEventListener('click', () => {
            chart.showEnvelope = !chart.showEnvelope;
            btnToggleEnvelope.textContent = chart.showEnvelope ? "Hide Tolerance Envelope" : "Show Tolerance Envelope";
            btnToggleEnvelope.classList.toggle('active', chart.showEnvelope);
            chart.render();
        });
    }

    // ── 10. Digital Report Export ─────────────────────────────────────────
    if (btnExportCert) {
        btnExportCert.addEventListener('click', async () => {
            try {
                const payload = {
                    trial_csv: activeTrialCSV,
                    goal_csv: activeGoalCSV,
                    config_csv: activeConfigCSV,
                    sample_id: currentSampleId
                };

                const res = await fetch('/api/export-csv-certificate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!res.ok) throw new Error("Certificate generation failed");
                const html = await res.text();
                
                // Direct file download without opening popup window
                const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
                const blobUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = blobUrl;
                a.download = `Virtual_EMT_Quality_Certificate_${Date.now()}.html`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(blobUrl);
            } catch (err) {
                console.error("Report Error:", err);
            }
        });
    }

    if (btnExportJson) {
        btnExportJson.addEventListener('click', () => {
            if (!lastValidationResult) {
                showToast("No validation telemetry available yet.", "error");
                return;
            }
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(lastValidationResult, null, 2));
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", `Virtual_EMT_Telemetry_${Date.now()}.json`);
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            downloadAnchor.remove();
            showToast("Downloaded Raw Telemetry JSON", "success");
        });
    }

    // ── 11. Helper Utilities ─────────────────────────────────────────────
    function setLoadingState(isLoading) {
        if (!btnValidate) return;
        btnValidate.disabled = isLoading;
        btnValidate.innerHTML = isLoading 
            ? `VALIDATING PROCESS TELEMETRY...` 
            : `VALIDATE PROCESS AGAINST BENCHMARK`;
    }

    function showToast(message, type = 'info') {
        // Pop-ups completely disabled per user requirement: "no need of pop ups"
        console.log(`[${type.toUpperCase()}] ${message}`);
    }

    // Initialize
    loadPresetCatalog();
    runCSVValidation();
});
