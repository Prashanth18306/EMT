/**
 * Stellantis Virtual EMT — Canvas Thermal Profile Chart Renderer
 * High-performance multi-curve plotting with dynamic automatically detected zones,
 * standard goal benchmark curve, tolerance envelopes, and interactive crosshair tracking.
 * Time axis calibrated strictly for 00:00 to 40:00 (0 to 2400 seconds).
 */

class EMTChartRenderer {
    constructor(canvasId, tooltipId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.tooltip = document.getElementById(tooltipId);

        this.data = null;
        this.goalData = null;
        this.zones = null;
        this.activeSensors = new Set();
        this.comparisonSensor = null; // null = all 12 sensors (default), 'temperature_X' = individual comparison
        this.showEnvelope = false; // Default false: clean curves without tolerance gap band
        this.cureThreshold = 165.0;

        // Distinct colors for the 12 EMT sensors
        this.sensorColors = {
            "temperature_1":  "#4A90E2", // Primary Blue (A-Pillar / Hood)
            "temperature_2":  "#00B0FF", // Sky Blue (LH Fender)
            "temperature_3":  "#2979FF", // Royal Blue (Front Door)
            "temperature_4":  "#651FFF", // Deep Indigo (Rear Door)
            "temperature_5":  "#E040FB", // Vibrant Magenta (Quarter Panel)
            "temperature_6":  "#FF4081", // Rose Pink (Tailgate Lower)
            "temperature_7":  "#FF5252", // Bright Coral (Rocker Panel)
            "temperature_8":  "#FF9100", // Amber (Rocker Right)
            "temperature_9":  "#FFD600", // Warm Gold (Underbody Tunnel)
            "temperature_10": "#AEEA00", // Lime (Wheel Arch)
            "temperature_11": "#50E3C2", // Teal Green (Engine Bay)
            "temperature_12": "#1DE9B6", // Aqua Teal (Spare Wheel Well)
        };

        this.sensorLabels = {
            "temperature_1":  "Sensor S1 (Zone 3 Upper Roof)",
            "temperature_2":  "Sensor S2 (Zone 2 LH Wall)",
            "temperature_3":  "Sensor S3 (Zone 3 Mid Wall)",
            "temperature_4":  "Sensor S4 (Zone 3 Lower Air)",
            "temperature_5":  "Sensor S5 (Zone 1 Upper Air)",
            "temperature_6":  "Sensor S6 (Zone 1 Lower Air)",
            "temperature_7":  "Sensor S7 (Zone 5 Lower Air)",
            "temperature_8":  "Sensor S8 (Zone 5 Upper Exit)",
            "temperature_9":  "Sensor S9 (Zone 4 Lower Air)",
            "temperature_10": "Sensor S10 (Zone 4 Mid Wall)",
            "temperature_11": "Sensor S11 (Zone 2 RH Wall)",
            "temperature_12": "Sensor S12 (Zone 4 Upper Roof)",
        };

        // Zone Stage Colors for Background Shading (Clean Minimalist Palette)
        this.zoneShadeColors = [
            "rgba(74, 144, 226, 0.05)",  // Z1: Entry Ramp (Soft Blue)
            "rgba(80, 227, 194, 0.06)",  // Z2: Preheat (Soft Mint)
            "rgba(155, 89, 182, 0.05)",  // Z3: Soak In (Soft Purple)
            "rgba(231, 76, 60, 0.05)",   // Z4: Cure Hold (Soft Coral)
            "rgba(39, 174, 96, 0.05)",   // Z5: Cooling Exit (Soft Emerald)
        ];

        this.zoneBadgeColors = ["#4A90E2", "#2B9E83", "#8E44AD", "#C0392B", "#27AE60"];

        // Layout paddings
        this.padding = { top: 38, right: 35, bottom: 45, left: 60 };

        this.initCanvasResolution();
        this.bindEvents();
    }

    initCanvasResolution() {
        if (!this.canvas) return;
        const parent = this.canvas.parentElement;
        const rect = parent ? parent.getBoundingClientRect() : null;
        const dpr = window.devicePixelRatio || 1;
        
        let w = (rect && rect.width > 50) ? rect.width : (this.canvas.clientWidth || 1000);
        let h = (rect && rect.height > 50) ? rect.height : (this.canvas.clientHeight || 420);
        
        w = Math.floor(w);
        h = Math.floor(h);

        this.canvas.width = Math.floor(w * dpr);
        this.canvas.height = Math.floor(h * dpr);
        
        this.ctx.setTransform(1, 0, 0, 1, 0, 0);
        this.ctx.scale(dpr, dpr);
        
        this.width = w;
        this.height = h;
    }

    bindEvents() {
        window.addEventListener('resize', () => {
            this.initCanvasResolution();
            this.render();
        });

        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseleave', () => this.handleMouseLeave());
    }

    setCSVData(chartSeries, detectedZones, cureThreshold = 165.0) {
        this.data = chartSeries;
        this.zones = detectedZones;
        this.cureThreshold = cureThreshold;

        // Activate all 12 sensors by default ("default all of")
        this.activeSensors.clear();
        for (let i = 1; i <= 12; i++) {
            this.activeSensors.add(`temperature_${i}`);
        }

        this.initCanvasResolution();
        this.render();
    }

    setComparisonSensor(sensorKey) {
        if (!sensorKey || sensorKey === 'all') {
            this.comparisonSensor = null;
        } else if (this.comparisonSensor === sensorKey) {
            this.comparisonSensor = null; // click again to return to default all sensors
        } else {
            this.comparisonSensor = sensorKey;
        }
        this.render();
    }

    toggleSensor(sensorKey) {
        // Buttons do NOT hide data: clicking a sensor toggles individual comparison with matching standard goal
        this.setComparisonSensor(sensorKey);
    }

    setFilter(type) {
        this.comparisonSensor = null; // reset comparison
        this.activeSensors.clear();
        if (type === 'all') {
            for (let i = 1; i <= 12; i++) this.activeSensors.add(`temperature_${i}`);
        } else if (type === 'core') {
            ["temperature_1", "temperature_3", "temperature_4", "temperature_9", "temperature_10", "temperature_12"].forEach(s => this.activeSensors.add(s));
        } else if (type === 'extremity') {
            ["temperature_2", "temperature_5", "temperature_6", "temperature_7", "temperature_8", "temperature_11"].forEach(s => this.activeSensors.add(s));
        }
        this.render();
    }

    render() {
        if (!this.data || !this.data.time_s) return;
        if (!this.width || this.width <= 50 || !this.height || this.height <= 50) {
            this.initCanvasResolution();
        }

        const ctx = this.ctx;
        const w = this.width;
        const h = this.height;
        const p = this.padding;

        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = "#FFFFFF";
        ctx.fillRect(0, 0, w, h);

        const timeArr = this.data.time_s;
        const maxTime = 2400.0; // 00:00 to 40:00 minutes
        const maxTemp = 230.0;  // Max plot °C
        const minTemp = 20.0;   // Ambient start

        // Coordinate transforms
        const getX = (t) => p.left + (Math.min(t, maxTime) / maxTime) * (w - p.left - p.right);
        const getY = (temp) => (h - p.bottom) - ((temp - minTemp) / (maxTemp - minTemp)) * (h - p.top - p.bottom);

        // 1. Draw Dynamically Detected Zone Shading & Boundary Markers
        if (this.zones && this.zones.zones) {
            const zList = this.zones.zones;
            for (let i = 0; i < zList.length; i++) {
                const z = zList[i];
                const x1 = getX(z.start_s);
                const x2 = getX(z.end_s);
                const shadeColor = this.zoneShadeColors[i % this.zoneShadeColors.length];

                // Zone background tint
                ctx.fillStyle = shadeColor;
                ctx.fillRect(x1, p.top, x2 - x1, h - p.top - p.bottom);

                // Zone vertical boundary line (except at start 0)
                if (i > 0) {
                    ctx.strokeStyle = "#E0E0E0";
                    ctx.lineWidth = 1;
                    ctx.setLineDash([4, 4]);
                    ctx.beginPath();
                    ctx.moveTo(x1, p.top);
                    ctx.lineTo(x1, h - p.bottom);
                    ctx.stroke();
                    ctx.setLineDash([]);
                }

                // Zone Badge at top
                const badgeColor = this.zoneBadgeColors[i % this.zoneBadgeColors.length];
                const badgeCenterX = (x1 + x2) / 2;
                ctx.font = "bold 9.5px 'Montserrat', sans-serif";
                ctx.textAlign = "center";
                ctx.fillStyle = badgeColor;
                ctx.fillText(`Z${i+1}: ${z.stage.toUpperCase()}`, badgeCenterX, p.top - 18);
                ctx.font = "9px 'Open Sans', sans-serif";
                ctx.fillStyle = "#888888";
                ctx.fillText(`${z.start_mmss}–${z.end_mmss}`, badgeCenterX, p.top - 6);
            }
        }

        // 2. Draw Background Grid & Axis Labels
        ctx.strokeStyle = "#EAEFF5";
        ctx.lineWidth = 1;
        ctx.font = "10px 'Open Sans', sans-serif";
        ctx.fillStyle = "#666666";

        // Horizontal Grid (°C)
        for (let temp = 40; temp <= 220; temp += 20) {
            const y = getY(temp);
            ctx.beginPath();
            ctx.moveTo(p.left, y);
            ctx.lineTo(w - p.right, y);
            ctx.stroke();

            ctx.textAlign = "right";
            ctx.fillText(`${temp}°C`, p.left - 10, y + 4);
        }

        // Vertical Grid (00:00 to 40:00 minutes)
        for (let m = 0; m <= 40; m += 5) {
            const t = m * 60;
            const x = getX(t);
            ctx.beginPath();
            ctx.moveTo(x, p.top);
            ctx.lineTo(x, h - p.bottom);
            ctx.stroke();

            ctx.textAlign = "center";
            ctx.fillText(`${m}m`, x, h - p.bottom + 18);
        }

        // Axis Titles
        ctx.font = "bold 10px 'Montserrat', sans-serif";
        ctx.fillStyle = "#888888";
        ctx.textAlign = "center";
        ctx.fillText("TIME ELAPSED (00:00 TO 40:00 MINUTES)", w / 2, h - 8);

        ctx.save();
        ctx.translate(14, h / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText("EFFECTIVE METAL TEMPERATURE (°C)", 0, 0);
        ctx.restore();

        // 3. Draw Cure Activation Threshold Line (165.0°C)
        const yCure = getY(this.cureThreshold);
        ctx.strokeStyle = "rgba(230, 126, 34, 0.85)";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(p.left, yCure);
        ctx.lineTo(w - p.right, yCure);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = "#D35400";
        ctx.textAlign = "right";
        ctx.font = "bold 10px 'Montserrat', sans-serif";
        ctx.fillText(`CURE THRESHOLD: ${this.cureThreshold}°C`, w - p.right - 10, yCure - 6);

        // 4. Draw Standard Goal Tolerance Guard Bands (+/- 8°C)
        if (this.showEnvelope && this.data.upper_envelope && this.data.lower_envelope) {
            const upper = this.data.upper_envelope;
            const lower = this.data.lower_envelope;

            ctx.fillStyle = "rgba(0, 210, 255, 0.07)";
            ctx.beginPath();
            ctx.moveTo(getX(timeArr[0]), getY(upper[0]));
            for (let i = 1; i < timeArr.length; i++) {
                ctx.lineTo(getX(timeArr[i]), getY(upper[i]));
            }
            for (let i = timeArr.length - 1; i >= 0; i--) {
                ctx.lineTo(getX(timeArr[i]), getY(lower[i]));
            }
            ctx.closePath();
            ctx.fill();

            // Upper & Lower dashed envelope strokes
            ctx.strokeStyle = "rgba(0, 210, 255, 0.35)";
            ctx.lineWidth = 1;
            ctx.setLineDash([3, 4]);

            ctx.beginPath();
            ctx.moveTo(getX(timeArr[0]), getY(upper[0]));
            for (let i = 1; i < timeArr.length; i++) ctx.lineTo(getX(timeArr[i]), getY(upper[i]));
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(getX(timeArr[0]), getY(lower[0]));
            for (let i = 1; i < timeArr.length; i++) ctx.lineTo(getX(timeArr[i]), getY(lower[i]));
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // 5. Draw Standard Goal Benchmark Curve
        if (this.data.goal_mean && (!this.comparisonSensor || this.comparisonSensor === null)) {
            const g = this.data.goal_mean;
            ctx.strokeStyle = "#4A90E2";
            ctx.lineWidth = 2.4;
            ctx.setLineDash([6, 4]);
            ctx.beginPath();
            ctx.moveTo(getX(timeArr[0]), getY(g[0]));
            for (let i = 1; i < timeArr.length; i++) {
                ctx.lineTo(getX(timeArr[i]), getY(g[i]));
            }
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // 6. Draw Sensors: Individual Comparison Mode vs Default All Sensors Mode
        const isComparisonMode = Boolean(this.comparisonSensor);

        if (isComparisonMode) {
            const targetKey = this.comparisonSensor;
            const targetIdx = targetKey.replace('temperature_', '');

            // 6A. Draw other sensors in delicate background traces (NO DATA IS HIDDEN)
            ctx.lineWidth = 1.0;
            ctx.globalAlpha = 0.18;
            for (let idx = 1; idx <= 12; idx++) {
                const sKey = `temperature_${idx}`;
                if (sKey === targetKey) continue;
                const pts = this.data[sKey];
                if (!pts || pts.length === 0) continue;

                ctx.strokeStyle = this.sensorColors[sKey] || "#4A90E2";
                ctx.beginPath();
                ctx.moveTo(getX(timeArr[0]), getY(pts[0]));
                for (let i = 1; i < timeArr.length; i++) ctx.lineTo(getX(timeArr[i]), getY(pts[i]));
                ctx.stroke();
            }
            ctx.globalAlpha = 1.0;

            // 6B. Draw Matching Standard Goal Sensor Curve (Dashed line)
            const goalPts = this.data['goal_' + targetKey] || this.data.goal_mean;
            if (goalPts && goalPts.length > 0) {
                ctx.save();
                ctx.strokeStyle = "#4A90E2";
                ctx.lineWidth = 2.6;
                ctx.setLineDash([6, 4]);
                ctx.beginPath();
                ctx.moveTo(getX(timeArr[0]), getY(goalPts[0]));
                for (let i = 1; i < timeArr.length; i++) ctx.lineTo(getX(timeArr[i]), getY(goalPts[i]));
                ctx.stroke();
                ctx.restore();
            }

            // 6C. Draw Selected Trial Sensor Curve (Solid prominent line)
            const trialPts = this.data[targetKey];
            if (trialPts && trialPts.length > 0) {
                ctx.save();
                const color = this.sensorColors[targetKey] || "#4A90E2";
                ctx.strokeStyle = color;
                ctx.lineWidth = 3.2;
                ctx.lineJoin = "round";
                ctx.beginPath();
                ctx.moveTo(getX(timeArr[0]), getY(trialPts[0]));
                for (let i = 1; i < timeArr.length; i++) ctx.lineTo(getX(timeArr[i]), getY(trialPts[i]));
                ctx.stroke();
                ctx.restore();
            }

            // 6D. Draw Comparison HUD Legend Banner (Design System Card)
            ctx.save();
            const bannerW = 290;
            const bannerH = 46;
            const bannerX = w - p.right - bannerW;
            const bannerY = p.top + 6;
            ctx.fillStyle = "#FFFFFF";
            ctx.strokeStyle = "#E0E0E0";
            ctx.lineWidth = 2;
            ctx.beginPath();
            if (ctx.roundRect) {
                ctx.roundRect(bannerX, bannerY, bannerW, bannerH, 8);
            } else {
                ctx.rect(bannerX, bannerY, bannerW, bannerH);
            }
            ctx.fill();
            ctx.stroke();

            // Trial label
            ctx.fillStyle = this.sensorColors[targetKey] || "#333333";
            ctx.font = "bold 11px 'Montserrat', sans-serif";
            ctx.textAlign = "left";
            ctx.fillText(`● Trial Sensor S${targetIdx} (Actual)`, bannerX + 12, bannerY + 19);

            // Goal label
            ctx.fillStyle = "#4A90E2";
            ctx.font = "bold 11px 'Montserrat', sans-serif";
            ctx.fillText(`- - Standard Goal S${targetIdx} (Benchmark)`, bannerX + 12, bannerY + 36);
            ctx.restore();

        } else {
            // Default Mode: Render all 12 Trial Sensor Curves (Default All Of)
            for (let idx = 1; idx <= 12; idx++) {
                const sKey = `temperature_${idx}`;
                if (!this.activeSensors.has(sKey)) continue;

                const pts = this.data[sKey];
                if (!pts || pts.length === 0) continue;

                const color = this.sensorColors[sKey] || "#4A90E2";
                ctx.strokeStyle = color;
                ctx.lineWidth = 1.8;
                ctx.lineJoin = "round";
                ctx.beginPath();
                ctx.moveTo(getX(timeArr[0]), getY(pts[0]));

                for (let i = 1; i < timeArr.length; i++) {
                    ctx.lineTo(getX(timeArr[i]), getY(pts[i]));
                }
                ctx.stroke();
            }
        }
    }

    handleMouseMove(e) {
        if (!this.data || !this.data.time_s) return;

        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const p = this.padding;

        if (mouseX < p.left || mouseX > this.width - p.right) {
            this.handleMouseLeave();
            return;
        }

        const maxTime = 2400.0;
        const frac = (mouseX - p.left) / (this.width - p.left - p.right);
        const curTimeS = Math.round(frac * maxTime);

        // Find nearest index
        let bestIdx = 0;
        let minDiff = Infinity;
        for (let i = 0; i < this.data.time_s.length; i++) {
            const diff = Math.abs(this.data.time_s[i] - curTimeS);
            if (diff < minDiff) {
                minDiff = diff;
                bestIdx = i;
            }
        }

        const timeS = this.data.time_s[bestIdx];
        const m = Math.floor(timeS / 60);
        const s = Math.floor(timeS % 60);
        const mmss = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;

        // Find which zone this belongs to
        let curZoneName = "";
        if (this.zones && this.zones.zones) {
            for (const z of this.zones.zones) {
                if (timeS >= z.start_s && timeS <= z.end_s) {
                    curZoneName = `${z.short_name} (${z.stage})`;
                    break;
                }
            }
        }

        let html = `<div style="font-weight:700; color:#4A90E2; margin-bottom:4px; font-family:'Montserrat', sans-serif; font-size:11.5px;">
            TIME: ${mmss} (${timeS.toFixed(0)}s) <span style="color:#666666; font-size:10px; font-weight:600;">${curZoneName}</span>
        </div>`;

        if (this.comparisonSensor) {
            // Detailed Comparison Tooltip for Selected Sensor vs Matching Standard Goal
            const sKey = this.comparisonSensor;
            const idx = sKey.replace('temperature_', '');
            const color = this.sensorColors[sKey] || "#4A90E2";
            const trialVal = this.data[sKey] ? this.data[sKey][bestIdx] : 0;
            const goalVal = this.data['goal_' + sKey] ? this.data['goal_' + sKey][bestIdx] : (this.data.goal_mean ? this.data.goal_mean[bestIdx] : 0);
            const delta = trialVal - goalVal;
            const deltaSign = delta >= 0 ? '+' : '';

            html += `
            <div style="font-size:11px; font-weight:700; color:${color}; font-family:'Montserrat', sans-serif; margin-bottom:5px; border-bottom:1px solid #E0E0E0; padding-bottom:3px;">
                COMPARING SENSOR S${idx} (${this.sensorLabels[sKey] || ''})
            </div>
            <div style="display:flex; justify-content:space-between; gap:14px; margin-bottom:3px;">
                <span style="color:${color}; font-weight:600;">Trial Actual:</span>
                <span style="font-family:'JetBrains Mono'; font-weight:700; color:${color};">${trialVal.toFixed(1)}°C</span>
            </div>
            <div style="display:flex; justify-content:space-between; gap:14px; margin-bottom:3px;">
                <span style="color:#666666; font-weight:600;">Goal Benchmark:</span>
                <span style="font-family:'JetBrains Mono'; font-weight:700; color:#4A90E2;">${goalVal.toFixed(1)}°C</span>
            </div>
            <div style="display:flex; justify-content:space-between; gap:14px; margin-top:3px; border-top:1px solid #E0E0E0; padding-top:3px;">
                <span style="color:#888888; font-weight:600;">Deviation (Δ):</span>
                <span style="font-family:'JetBrains Mono'; font-weight:700; color:${Math.abs(delta) > 8.0 ? '#E74C3C' : '#27AE60'};">${deltaSign}${delta.toFixed(1)}°C</span>
            </div>`;
        } else {
            // Default Mode: Standard multi-sensor hover readout
            if (this.data.goal_mean) {
                const gVal = this.data.goal_mean[bestIdx];
                html += `<div style="display:flex; justify-content:space-between; gap:12px; margin-bottom:4px; border-bottom:1px solid #E0E0E0; padding-bottom:2px;">
                    <span style="color:#666666; font-weight:600;">Goal Benchmark:</span>
                    <span style="font-family:'JetBrains Mono'; font-weight:700; color:#4A90E2;">${gVal ? gVal.toFixed(1) : 0}°C</span>
                </div>`;
            }

            let count = 0;
            for (let idx = 1; idx <= 12; idx++) {
                const sKey = `temperature_${idx}`;
                if (!this.activeSensors.has(sKey)) continue;
                if (count >= 6) {
                    html += `<div style="color:#888888; font-size:10px; margin-top:2px;">+ more sensors... (Click any S1–S12 chip to compare)</div>`;
                    break;
                }
                const color = this.sensorColors[sKey];
                const tempVal = this.data[sKey] ? this.data[sKey][bestIdx] : 0;
                html += `<div style="display:flex; justify-content:space-between; gap:12px; margin-bottom:2px;">
                    <span style="color:${color}; font-weight:600;">Sensor S${idx}:</span>
                    <span style="font-family:'JetBrains Mono'; font-weight:700; color:#333333;">${tempVal.toFixed(1)}°C</span>
                </div>`;
                count++;
            }
        }

        this.tooltip.innerHTML = html;
        this.tooltip.style.display = 'block';

        let tipX = e.clientX - rect.left + 15;
        let tipY = e.clientY - rect.top - 20;
        if (tipX + 220 > this.width) tipX -= 240;
        this.tooltip.style.left = `${tipX}px`;
        this.tooltip.style.top = `${tipY}px`;
    }

    handleMouseLeave() {
        this.tooltip.style.display = 'none';
    }
}
