/**
 * Stellantis Virtual EMT — Canvas Thermal Profile Chart Renderer
 * High-performance multi-curve plotting with tolerance envelopes,
 * crosshair tracking, and interactive sensor highlighting.
 */

class EMTChartRenderer {
    constructor(canvasId, tooltipId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.tooltip = document.getElementById(tooltipId);

        this.data = null;
        this.standardData = null;
        this.activeSensors = new Set();
        this.showEnvelope = true;
        this.cureThreshold = 165.0;

        // Palette for the 5 Oven Process Zones
        this.sensorColors = {
            "Zone 1 (Entry Ramp)":   "#00E5FF", // Cyan (Z1 Entry)
            "Zone 2 (Preheat)":      "#2979FF", // Royal Blue (Z2 Preheat)
            "Zone 3 (Soak In)":      "#E040FB", // Magenta (Z3 Soak)
            "Zone 4 (Cure Hold)":    "#FF1744", // Coral Red (Z4 Cure)
            "Zone 5 (Cooling Exit)": "#00E676", // Mint Green (Z5 Exit)
        };

        // Layout paddings
        this.padding = { top: 30, right: 30, bottom: 45, left: 60 };

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
        
        // Reset transform to identity then scale by devicePixelRatio
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

    setData(timeSeriesData, standardCurveData, cureThreshold) {
        this.data = timeSeriesData;
        this.standardData = standardCurveData;
        this.cureThreshold = cureThreshold || 165.0;

        // Activate all zones by default
        if (this.activeSensors.size === 0) {
            Object.keys(this.sensorColors).forEach(s => this.activeSensors.add(s));
        }

        this.initCanvasResolution();
        this.render();
    }

    toggleSensor(sensorName) {
        if (this.activeSensors.has(sensorName)) {
            this.activeSensors.delete(sensorName);
        } else {
            this.activeSensors.add(sensorName);
        }
        this.render();
    }

    setFilter(type) {
        const cureZones = [
            "Zone 3 (Soak In)",
            "Zone 4 (Cure Hold)"
        ];
        const transitionZones = [
            "Zone 1 (Entry Ramp)",
            "Zone 2 (Preheat)",
            "Zone 5 (Cooling Exit)"
        ];

        this.activeSensors.clear();
        if (type === 'all') {
            Object.keys(this.sensorColors).forEach(s => this.activeSensors.add(s));
        } else if (type === 'core') {
            cureZones.forEach(s => this.activeSensors.add(s));
        } else if (type === 'extremity') {
            transitionZones.forEach(s => this.activeSensors.add(s));
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

        const timeArr = this.data.time_s;
        const maxTime = timeArr[timeArr.length - 1] || 2400;
        const maxTemp = 230; // Max plot °C
        const minTemp = 20;  // Ambient start

        // Coordinate transforms
        const getX = (t) => p.left + (t / maxTime) * (w - p.left - p.right);
        const getY = (temp) => (h - p.bottom) - ((temp - minTemp) / (maxTemp - minTemp)) * (h - p.top - p.bottom);

        // 1. Draw Background Grid & Axis Labels
        ctx.strokeStyle = "rgba(255, 255, 255, 0.07)";
        ctx.lineWidth = 1;
        ctx.font = "10.5px 'JetBrains Mono', monospace";
        ctx.fillStyle = "#8E9DBE";

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

        // Vertical Grid (Minutes)
        const totalMin = Math.ceil(maxTime / 60);
        const minStep = totalMin > 35 ? 5 : 5;
        for (let m = 0; m <= totalMin; m += minStep) {
            const t = m * 60;
            if (t > maxTime) break;
            const x = getX(t);
            ctx.beginPath();
            ctx.moveTo(x, p.top);
            ctx.lineTo(x, h - p.bottom);
            ctx.stroke();

            ctx.textAlign = "center";
            ctx.fillText(`${m}m`, x, h - p.bottom + 18);
        }

        // Axis Titles
        ctx.font = "10px 'Outfit', sans-serif";
        ctx.fillStyle = "#6576A0";
        ctx.textAlign = "center";
        ctx.fillText("TIME ELAPSED (MINUTES)", w / 2, h - 8);

        ctx.save();
        ctx.translate(14, h / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText("EFFECTIVE METAL TEMPERATURE (°C)", 0, 0);
        ctx.restore();

        // 2. Draw Cure Activation Threshold Line
        const yCure = getY(this.cureThreshold);
        ctx.strokeStyle = "rgba(255, 215, 0, 0.75)";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(p.left, yCure);
        ctx.lineTo(w - p.right, yCure);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = "#FFD700";
        ctx.textAlign = "right";
        ctx.fillText(`CURE THRESHOLD: ${this.cureThreshold}°C`, w - p.right - 10, yCure - 6);

        // 3. Draw Golden Standard Curve & Tolerance Acceptance Envelopes
        if (this.standardData && this.showEnvelope) {
            const stdTimes = this.standardData.time_s;
            const stdTemps = this.standardData.standard_temp_C;
            const upper = this.standardData.upper_limit_C;
            const lower = this.standardData.lower_limit_C;

            // Shaded Acceptance Envelope
            ctx.fillStyle = "rgba(0, 144, 255, 0.08)";
            ctx.beginPath();
            ctx.moveTo(getX(stdTimes[0]), getY(upper[0]));
            for (let i = 1; i < stdTimes.length; i++) {
                ctx.lineTo(getX(stdTimes[i]), getY(upper[i]));
            }
            for (let i = stdTimes.length - 1; i >= 0; i--) {
                ctx.lineTo(getX(stdTimes[i]), getY(lower[i]));
            }
            ctx.closePath();
            ctx.fill();

            // Upper & Lower Bounds
            ctx.strokeStyle = "rgba(0, 210, 255, 0.35)";
            ctx.lineWidth = 1;
            ctx.setLineDash([3, 4]);

            // Upper bound
            ctx.beginPath();
            ctx.moveTo(getX(stdTimes[0]), getY(upper[0]));
            for (let i = 1; i < stdTimes.length; i++) ctx.lineTo(getX(stdTimes[i]), getY(upper[i]));
            ctx.stroke();

            // Lower bound
            ctx.beginPath();
            ctx.moveTo(getX(stdTimes[0]), getY(lower[0]));
            for (let i = 1; i < stdTimes.length; i++) ctx.lineTo(getX(stdTimes[i]), getY(lower[i]));
            ctx.stroke();

            // Golden Reference Curve
            ctx.strokeStyle = "#FFFFFF";
            ctx.lineWidth = 2;
            ctx.setLineDash([6, 4]);
            ctx.beginPath();
            ctx.moveTo(getX(stdTimes[0]), getY(stdTemps[0]));
            for (let i = 1; i < stdTimes.length; i++) ctx.lineTo(getX(stdTimes[i]), getY(stdTemps[i]));
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // 4. Draw Individual Sensor Curves
        for (const [sensorName, color] of Object.entries(this.sensorColors)) {
            if (!this.activeSensors.has(sensorName)) continue;

            const pts = this.data[sensorName];
            if (!pts || pts.length === 0) continue;

            ctx.strokeStyle = color;
            ctx.lineWidth = 2.0;
            ctx.lineJoin = "round";
            ctx.beginPath();
            ctx.moveTo(getX(timeArr[0]), getY(pts[0]));

            for (let i = 1; i < timeArr.length; i++) {
                ctx.lineTo(getX(timeArr[i]), getY(pts[i]));
            }
            ctx.stroke();
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

        const maxTime = this.data.time_s[this.data.time_s.length - 1];
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
        const mmss = `${Math.floor(timeS / 60).toString().padStart(2, '0')}:${(timeS % 60).toString().padStart(2, '0')}`;

        // Build Tooltip HTML
        let html = `<div style="font-weight:700; color:#00D2FF; margin-bottom:4px; font-family:'JetBrains Mono';">TIME: ${mmss} (${timeS}s)</div>`;
        let count = 0;

        for (const [sName, color] of Object.entries(this.sensorColors)) {
            if (!this.activeSensors.has(sName)) continue;
            if (count >= 6) { // limit height
                html += `<div style="color:#8E9DBE; font-size:10px;">+ more sensors...</div>`;
                break;
            }
            const tempVal = this.data[sName][bestIdx];
            html += `<div style="display:flex; justify-content:space-between; gap:12px; margin-bottom:2px;">
                <span style="color:${color}; font-weight:600;">${sName}:</span>
                <span style="font-family:'JetBrains Mono'; font-weight:700;">${tempVal.toFixed(1)}°C</span>
            </div>`;
            count++;
        }

        this.tooltip.innerHTML = html;
        this.tooltip.style.display = 'block';

        // Position tooltip
        let tipX = e.clientX - rect.left + 15;
        let tipY = e.clientY - rect.top - 20;
        if (tipX + 180 > this.width) tipX -= 200;
        this.tooltip.style.left = `${tipX}px`;
        this.tooltip.style.top = `${tipY}px`;
    }

    handleMouseLeave() {
        this.tooltip.style.display = 'none';
    }
}
